
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

st.set_page_config(
    page_title="AutoTrade AI Reversal",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container {
    max-width: 560px;
    padding-top: 1rem;
    padding-bottom: 6rem;
}
div[data-testid="stMetric"] {
    background: rgba(120,120,120,0.08);
    border-radius: 16px;
    padding: 12px;
}
.stButton > button {
    border-radius: 14px;
    min-height: 48px;
    font-weight: 700;
}
.status {
    padding: 12px;
    border-radius: 16px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 12px;
}
.on { background: rgba(0,180,90,0.12); }
.off { background: rgba(120,120,120,0.10); }
.ai-card {
    padding: 16px;
    border-radius: 18px;
    background: rgba(100,100,100,0.08);
    margin-bottom: 12px;
}
.small {
    font-size: .82rem;
    opacity: .72;
}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "running": False,
    "capital": 1000.0,
    "saldo": 1000.0,
    "perfil": "Moderado",
    "preco": 100.0,
    "precos": [100.0],
    "equity": [1000.0],
    "posicao": None,
    "historico": [],
    "pnl_dia": 0.0,
    "operacoes": 0,
    "vitorias": 0,
    "derrotas": 0,
    "estado_ia": "COLETANDO DADOS",
    "confianca": 0.0,
    "motivos": ["Aguardando dados suficientes para análise."],
    "max_equity": 1000.0
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def params(perfil):
    return {
        "Conservador": {
            "risk_trade": 0.003,
            "stop": 0.007,
            "target": 0.015,
            "trail_trigger": 0.010,
            "trail_gap": 0.006,
            "daily_stop": 0.015,
            "buy_threshold": 0.78
        },
        "Moderado": {
            "risk_trade": 0.005,
            "stop": 0.010,
            "target": 0.025,
            "trail_trigger": 0.014,
            "trail_gap": 0.008,
            "daily_stop": 0.020,
            "buy_threshold": 0.72
        },
        "Agressivo": {
            "risk_trade": 0.010,
            "stop": 0.015,
            "target": 0.040,
            "trail_trigger": 0.020,
            "trail_gap": 0.012,
            "daily_stop": 0.035,
            "buy_threshold": 0.66
        }
    }[perfil]

def simulate_price(price):
    # Mercado fictício com pequenos regimes aleatórios.
    regime = np.random.choice([-1, 0, 1], p=[0.34, 0.32, 0.34])
    drift = regime * 0.0007
    shock = np.random.normal(0, 0.0045)
    return max(1.0, price * (1 + drift + shock))

def calc_rsi(prices, period=14):
    if len(prices) <= period:
        return 50.0
    s = pd.Series(prices, dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    g = gain.iloc[-1]
    l = loss.iloc[-1]
    if pd.isna(g) or pd.isna(l):
        return 50.0
    if l == 0:
        return 100.0
    rs = g / l
    return float(100 - (100 / (1 + rs)))

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def ai_reversal_analysis(prices, perfil):
    if len(prices) < 30:
        return "COLETANDO DADOS", 0.0, ["A IA precisa de pelo menos 30 candles simulados."]

    s = pd.Series(prices, dtype=float)
    current = float(s.iloc[-1])
    ma5 = float(s.tail(5).mean())
    ma10 = float(s.tail(10).mean())
    ma20 = float(s.tail(20).mean())
    rsi14 = calc_rsi(prices, 14)

    ret1 = float(s.pct_change().iloc[-1])
    ret3 = float(current / s.iloc[-4] - 1)
    ret5 = float(current / s.iloc[-6] - 1)
    ret10 = float(current / s.iloc[-11] - 1)
    vol10 = float(s.pct_change().tail(10).std())

    # Queda recente: últimos 5/10 períodos negativos e preço abaixo da média longa
    queda = (ret5 < -0.006 or ret10 < -0.010) and current < ma20

    # Reversão: preço começa a recuperar e a média curta encosta/supera média de 10
    reversao = (
        ret1 > 0
        and ret3 > 0
        and ma5 >= ma10 * 0.998
        and rsi14 >= 34
        and rsi14 <= 62
    )

    # Score de compra após queda + início de reversão
    score = 0.0
    score += 1.3 if queda else -0.5
    score += 1.4 if reversao else -0.4
    score += 0.9 if rsi14 < 50 else 0.2
    score += min(0.8, max(-0.8, -ret5 * 40))
    score += min(0.8, max(-0.8, ret3 * 80))
    score -= 0.6 if vol10 > 0.012 else 0.0

    confidence = float(sigmoid(score - 1.2))
    threshold = params(perfil)["buy_threshold"]

    motivos = [
        f"Variação 5 períodos: {ret5*100:+.2f}%.",
        f"Variação 10 períodos: {ret10*100:+.2f}%.",
        f"RSI: {rsi14:.1f}.",
        f"Média curta {'recuperando' if ma5 >= ma10*0.998 else 'ainda fraca'} frente à média de 10.",
        f"Volatilidade recente: {vol10*100:.2f}%."
    ]

    if queda and not reversao:
        return "AGUARDANDO REVERSÃO", confidence, motivos

    if queda and reversao and confidence >= threshold:
        return "COMPRAR", confidence, motivos

    if ret5 < -0.004:
        return "PREVÊ QUEDA", confidence, motivos

    return "AGUARDAR", confidence, motivos

def open_position():
    p = params(st.session_state.perfil)
    preco = st.session_state.preco
    saldo = st.session_state.saldo

    risco_brl = saldo * p["risk_trade"]
    dist_stop = preco * p["stop"]
    qty = max(0.0001, risco_brl / dist_stop)

    st.session_state.posicao = {
        "entrada": preco,
        "quantidade": qty,
        "stop_inicial": preco * (1 - p["stop"]),
        "stop_atual": preco * (1 - p["stop"]),
        "alvo": preco * (1 + p["target"]),
        "max_preco": preco,
        "hora": datetime.now().strftime("%H:%M:%S"),
        "confianca": st.session_state.confianca
    }

def close_position(exit_price, motivo):
    pos = st.session_state.posicao
    pnl = (exit_price - pos["entrada"]) * pos["quantidade"]

    st.session_state.saldo += pnl
    st.session_state.pnl_dia += pnl
    st.session_state.operacoes += 1

    if pnl >= 0:
        st.session_state.vitorias += 1
    else:
        st.session_state.derrotas += 1

    st.session_state.historico.insert(0, {
        "Hora": datetime.now().strftime("%H:%M:%S"),
        "Entrada": round(pos["entrada"], 2),
        "Saída": round(exit_price, 2),
        "Resultado (R$)": round(pnl, 2),
        "Confiança IA": f"{pos['confianca']*100:.1f}%",
        "Motivo": motivo
    })
    st.session_state.posicao = None

def manage_position():
    p = params(st.session_state.perfil)
    pos = st.session_state.posicao
    preco = st.session_state.preco

    if preco > pos["max_preco"]:
        pos["max_preco"] = preco

    lucro_pct = preco / pos["entrada"] - 1

    # Ativa trailing stop após lucro mínimo
    if lucro_pct >= p["trail_trigger"]:
        trailing = pos["max_preco"] * (1 - p["trail_gap"])
        pos["stop_atual"] = max(pos["stop_atual"], trailing)

    if preco <= pos["stop_atual"]:
        motivo = "Trailing stop" if pos["stop_atual"] > pos["stop_inicial"] else "Stop-loss"
        close_position(pos["stop_atual"], motivo)
        return

    if preco >= pos["alvo"]:
        close_position(pos["alvo"], "Alvo de lucro")
        return

    # Saída por perda de força após estar no lucro
    if lucro_pct > 0.005:
        s = pd.Series(st.session_state.precos, dtype=float)
        ret3 = float(preco / s.iloc[-4] - 1) if len(s) >= 4 else 0
        rsi_now = calc_rsi(st.session_state.precos, 14)
        if ret3 < -0.004 and rsi_now > 60:
            close_position(preco, "IA detectou perda de força")
            return

# ---------------- UI ----------------

st.title("🤖 AutoTrade AI v4")
st.caption("Compra em reversão após queda + venda automática com proteção de lucro")

status = "🟢 IA OPERANDO" if st.session_state.running else "⚪ ROBÔ PARADO"
cls = "status on" if st.session_state.running else "status off"
st.markdown(f'<div class="{cls}">{status}</div>', unsafe_allow_html=True)

st.subheader("Configuração")
capital = st.number_input(
    "Capital simulado (R$)",
    min_value=100.0,
    value=float(st.session_state.capital),
    step=100.0,
    disabled=st.session_state.running
)
perfil = st.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Agressivo"],
    index=["Conservador", "Moderado", "Agressivo"].index(st.session_state.perfil),
    disabled=st.session_state.running
)

c1, c2 = st.columns(2)
with c1:
    if st.button("▶ INICIAR IA", use_container_width=True, disabled=st.session_state.running):
        st.session_state.capital = capital
        st.session_state.saldo = capital
        st.session_state.perfil = perfil
        st.session_state.preco = 100.0
        st.session_state.precos = [100.0]
        st.session_state.equity = [capital]
        st.session_state.posicao = None
        st.session_state.historico = []
        st.session_state.pnl_dia = 0.0
        st.session_state.operacoes = 0
        st.session_state.vitorias = 0
        st.session_state.derrotas = 0
        st.session_state.estado_ia = "COLETANDO DADOS"
        st.session_state.confianca = 0.0
        st.session_state.motivos = ["Aguardando dados suficientes para análise."]
        st.session_state.max_equity = capital
        st.session_state.running = True
        st.rerun()

with c2:
    if st.button("■ PARAR", use_container_width=True, disabled=not st.session_state.running):
        st.session_state.running = False
        st.rerun()

# ---------------- Engine ----------------
if st.session_state.running:
    st.session_state.preco = simulate_price(st.session_state.preco)
    st.session_state.precos.append(st.session_state.preco)
    if len(st.session_state.precos) > 600:
        st.session_state.precos = st.session_state.precos[-600:]

    estado, conf, motivos = ai_reversal_analysis(
        st.session_state.precos,
        st.session_state.perfil
    )
    st.session_state.estado_ia = estado
    st.session_state.confianca = conf
    st.session_state.motivos = motivos

    p = params(st.session_state.perfil)
    limite_dia = -st.session_state.capital * p["daily_stop"]

    if st.session_state.pnl_dia <= limite_dia:
        st.session_state.running = False
        st.error("Limite diário de perda atingido. A IA foi desligada.")

    elif st.session_state.posicao:
        manage_position()

    elif estado == "COMPRAR":
        open_position()

    st.session_state.equity.append(st.session_state.saldo)
    st.session_state.max_equity = max(st.session_state.max_equity, st.session_state.saldo)

# ---------------- Decision ----------------
st.divider()
st.subheader("🧠 Decisão da IA")

emoji = {
    "COLETANDO DADOS": "🔵",
    "PREVÊ QUEDA": "🔻",
    "AGUARDANDO REVERSÃO": "🟠",
    "COMPRAR": "🟢",
    "AGUARDAR": "🟡",
}.get(st.session_state.estado_ia, "🤖")

st.markdown(
    f"""
    <div class="ai-card">
        <b>{emoji} {st.session_state.estado_ia}</b><br>
        Confiança da IA: <b>{st.session_state.confianca*100:.1f}%</b>
    </div>
    """,
    unsafe_allow_html=True
)

with st.expander("Ver análise da IA"):
    for item in st.session_state.motivos:
        st.write("• " + item)

# ---------------- Position ----------------
st.subheader("Posição atual")
if st.session_state.posicao:
    pos = st.session_state.posicao
    atual = st.session_state.preco
    lucro_pct = (atual / pos["entrada"] - 1) * 100
    pnl_aberto = (atual - pos["entrada"]) * pos["quantidade"]

    st.write(f"Entrada: **{pos['entrada']:.2f}**")
    st.write(f"Preço atual: **{atual:.2f}**")
    st.write(f"Lucro aberto: **R$ {pnl_aberto:.2f} ({lucro_pct:+.2f}%)**")
    st.write(f"Stop atual: **{pos['stop_atual']:.2f}**")
    st.write(f"Alvo: **{pos['alvo']:.2f}**")
    st.write(f"Máxima após entrada: **{pos['max_preco']:.2f}**")
else:
    st.info("Nenhuma posição aberta.")

# ---------------- Dashboard ----------------
st.subheader("Painel")
m1, m2 = st.columns(2)
m1.metric("Saldo", f"R$ {st.session_state.saldo:,.2f}")
m2.metric("Resultado do dia", f"R$ {st.session_state.pnl_dia:,.2f}")

m3, m4 = st.columns(2)
m3.metric("Operações", st.session_state.operacoes)
taxa = (
    st.session_state.vitorias / st.session_state.operacoes * 100
    if st.session_state.operacoes else 0
)
m4.metric("Taxa de acerto", f"{taxa:.1f}%")

dd = (
    (st.session_state.saldo / st.session_state.max_equity - 1) * 100
    if st.session_state.max_equity > 0 else 0
)

m5, m6 = st.columns(2)
m5.metric("Drawdown", f"{dd:.2f}%")
m6.metric("Preço simulado", f"{st.session_state.preco:.2f}")

st.subheader("Mercado simulado")
st.line_chart(pd.DataFrame({"Preço": st.session_state.precos[-150:]}))

st.subheader("Curva de capital")
st.line_chart(pd.DataFrame({"Saldo": st.session_state.equity}))

st.subheader("Histórico")
if st.session_state.historico:
    st.dataframe(
        pd.DataFrame(st.session_state.historico),
        use_container_width=True,
        hide_index=True
    )
else:
    st.caption("Nenhuma operação encerrada ainda.")

st.markdown("""
<div class="small">
⚠️ Esta versão continua em simulação. A IA não prevê o mercado com certeza e não
garante lucro. A estratégia foi desenhada para esperar sinais de reversão após
quedas, usar stop-loss obrigatório e proteger lucro com trailing stop.
</div>
""", unsafe_allow_html=True)

if st.session_state.running:
    time.sleep(1)
    st.rerun()
