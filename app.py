
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

st.set_page_config(
    page_title="AutoTrade AI",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container {
    max-width: 540px;
    padding-top: 1rem;
    padding-bottom: 6rem;
}
div[data-testid="stMetric"] {
    background: rgba(120,120,120,0.08);
    border-radius: 16px;
    padding: 12px;
}
.card {
    background: rgba(120,120,120,0.08);
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 12px;
}
.status-running {
    padding: 12px;
    border-radius: 16px;
    background: rgba(0,180,90,0.12);
    font-weight: 700;
    text-align: center;
    margin-bottom: 12px;
}
.status-stopped {
    padding: 12px;
    border-radius: 16px;
    background: rgba(120,120,120,0.10);
    font-weight: 700;
    text-align: center;
    margin-bottom: 12px;
}
.ai-buy {
    padding: 14px;
    border-radius: 16px;
    background: rgba(0,180,90,0.12);
    font-weight: 700;
}
.ai-wait {
    padding: 14px;
    border-radius: 16px;
    background: rgba(220,160,0,0.10);
    font-weight: 700;
}
.disclaimer {
    font-size: .8rem;
    opacity: .72;
    text-align: center;
    margin-top: 1.5rem;
}
.stButton > button {
    border-radius: 14px;
    min-height: 48px;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

defaults = {
    "running": False,
    "capital": 1000.0,
    "saldo": 1000.0,
    "preco": 100.0,
    "precos": [100.0],
    "posicao": None,
    "historico": [],
    "equity": [1000.0],
    "pnl_dia": 0.0,
    "operacoes": 0,
    "vitorias": 0,
    "derrotas": 0,
    "perfil": "Moderado",
    "ai_confidence": 0.0,
    "ai_action": "AGUARDAR",
    "ai_reasons": ["Coletando dados de mercado..."],
    "max_equity": 1000.0
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def risk_params(perfil):
    return {
        "Conservador": {
            "risk_trade": 0.003,
            "stop": 0.006,
            "target": 0.010,
            "daily_stop": 0.015,
            "ai_threshold": 0.76
        },
        "Moderado": {
            "risk_trade": 0.005,
            "stop": 0.008,
            "target": 0.014,
            "daily_stop": 0.020,
            "ai_threshold": 0.70
        },
        "Agressivo": {
            "risk_trade": 0.010,
            "stop": 0.012,
            "target": 0.022,
            "daily_stop": 0.035,
            "ai_threshold": 0.64
        }
    }[perfil]

def simulate_price(price):
    # Mercado fictício com regimes leves para o MVP.
    drift = 0.00015
    shock = np.random.normal(0, 0.0048)
    return max(1.0, price * (1 + drift + shock))

def rsi(series, period=14):
    if len(series) <= period:
        return 50.0
    s = pd.Series(series, dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    if pd.isna(last_loss):
        return 50.0
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return float(100 - (100 / (1 + rs)))

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def ai_decision(prices, perfil):
    """
    Motor de decisão inspirado em ML:
    transforma múltiplos sinais quantitativos em uma probabilidade.
    No MVP, os pesos são fixos e explicáveis, para evitar uma "caixa-preta".
    """
    if len(prices) < 25:
        return "AGUARDAR", 0.0, ["A IA precisa de pelo menos 25 candles simulados."]

    s = pd.Series(prices, dtype=float)
    ma5 = float(s.tail(5).mean())
    ma20 = float(s.tail(20).mean())
    current = float(s.iloc[-1])

    ret1 = float(s.pct_change().iloc[-1])
    ret5 = float(current / s.iloc[-6] - 1)
    vol10 = float(s.pct_change().tail(10).std())
    rsi14 = rsi(prices, 14)

    trend = (ma5 / ma20 - 1) * 100
    momentum = ret5 * 100
    short_momentum = ret1 * 100
    volatility = vol10 * 100 if not np.isnan(vol10) else 0

    # Score explicável. Não é uma promessa de capacidade preditiva real.
    score = (
        1.45 * trend
        + 0.95 * momentum
        + 0.35 * short_momentum
        + (0.35 if 45 <= rsi14 <= 68 else -0.25)
        - 0.45 * max(0, volatility - 0.55)
    )

    confidence = float(sigmoid(score))
    threshold = risk_params(perfil)["ai_threshold"]

    reasons = []
    reasons.append(
        f"Tendência curta {'acima' if ma5 > ma20 else 'abaixo'} da média longa."
    )
    reasons.append(
        f"RSI em {rsi14:.1f} ({'neutro/positivo' if 45 <= rsi14 <= 68 else 'fora da zona preferida'})."
    )
    reasons.append(
        f"Momentum de 5 períodos: {momentum:+.2f}%."
    )
    reasons.append(
        f"Volatilidade recente: {volatility:.2f}%."
    )

    action = "COMPRAR" if confidence >= threshold else "AGUARDAR"
    return action, confidence, reasons

def open_position():
    p = risk_params(st.session_state.perfil)
    saldo = st.session_state.saldo
    preco = st.session_state.preco

    risk_brl = saldo * p["risk_trade"]
    stop_distance = preco * p["stop"]
    qty = max(0.0001, risk_brl / stop_distance)

    st.session_state.posicao = {
        "entrada": preco,
        "stop": preco * (1 - p["stop"]),
        "alvo": preco * (1 + p["target"]),
        "quantidade": qty,
        "hora": datetime.now().strftime("%H:%M:%S"),
        "ai_confidence": st.session_state.ai_confidence
    }

def close_position(exit_price, reason):
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
        "IA": f"{pos['ai_confidence']*100:.1f}%",
        "Motivo": reason
    })

    st.session_state.posicao = None

# -----------------------
# Header
# -----------------------
st.title("🤖 AutoTrade AI")
st.caption("MVP mobile com motor de decisão por IA — simulação")

status_class = "status-running" if st.session_state.running else "status-stopped"
status_text = "🟢 IA OPERANDO" if st.session_state.running else "⚪ ROBÔ PARADO"
st.markdown(f'<div class="{status_class}">{status_text}</div>', unsafe_allow_html=True)

# -----------------------
# Config
# -----------------------
st.subheader("Configuração")

capital = st.number_input(
    "Capital simulado (R$)",
    min_value=100.0,
    value=float(st.session_state.capital),
    step=100.0,
    format="%.2f",
    disabled=st.session_state.running
)

perfil = st.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Agressivo"],
    index=["Conservador","Moderado","Agressivo"].index(st.session_state.perfil),
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
        st.session_state.pnl_dia = 0.0
        st.session_state.operacoes = 0
        st.session_state.vitorias = 0
        st.session_state.derrotas = 0
        st.session_state.historico = []
        st.session_state.equity = [capital]
        st.session_state.max_equity = capital
        st.session_state.posicao = None
        st.session_state.ai_confidence = 0.0
        st.session_state.ai_action = "AGUARDAR"
        st.session_state.ai_reasons = ["Coletando dados de mercado..."]
        st.session_state.running = True
        st.rerun()

with c2:
    if st.button("■ PARAR", use_container_width=True, disabled=not st.session_state.running):
        st.session_state.running = False
        st.rerun()

# -----------------------
# Engine
# -----------------------
if st.session_state.running:
    st.session_state.preco = simulate_price(st.session_state.preco)
    st.session_state.precos.append(st.session_state.preco)

    # Mantém histórico leve.
    if len(st.session_state.precos) > 500:
        st.session_state.precos = st.session_state.precos[-500:]

    action, confidence, reasons = ai_decision(
        st.session_state.precos,
        st.session_state.perfil
    )

    st.session_state.ai_action = action
    st.session_state.ai_confidence = confidence
    st.session_state.ai_reasons = reasons

    p = risk_params(st.session_state.perfil)
    daily_limit = -st.session_state.capital * p["daily_stop"]

    if st.session_state.pnl_dia <= daily_limit:
        st.session_state.running = False
        st.error("Stop diário atingido. A IA foi desligada automaticamente.")

    elif st.session_state.posicao:
        pos = st.session_state.posicao

        if st.session_state.preco <= pos["stop"]:
            close_position(pos["stop"], "Stop-loss")

        elif st.session_state.preco >= pos["alvo"]:
            close_position(pos["alvo"], "Take-profit")

        # Saída defensiva: a IA perde convicção depois da entrada.
        elif len(st.session_state.precos) >= 25 and confidence < 0.38:
            close_position(st.session_state.preco, "Saída defensiva da IA")

    elif action == "COMPRAR":
        open_position()

    st.session_state.equity.append(st.session_state.saldo)
    st.session_state.max_equity = max(
        st.session_state.max_equity,
        st.session_state.saldo
    )

# -----------------------
# AI Card
# -----------------------
st.divider()
st.subheader("🧠 Decisão da IA")

if st.session_state.ai_action == "COMPRAR":
    css = "ai-buy"
    emoji = "🟢"
else:
    css = "ai-wait"
    emoji = "🟡"

st.markdown(
    f"""
    <div class="{css}">
    {emoji} Decisão: {st.session_state.ai_action}<br>
    Confiança: {st.session_state.ai_confidence*100:.1f}%
    </div>
    """,
    unsafe_allow_html=True
)

with st.expander("Por que a IA tomou essa decisão?"):
    for reason in st.session_state.ai_reasons:
        st.write("• " + reason)

# -----------------------
# Dashboard
# -----------------------
st.subheader("Painel")

m1, m2 = st.columns(2)
m1.metric("Saldo", f"R$ {st.session_state.saldo:,.2f}")
m2.metric("Hoje", f"R$ {st.session_state.pnl_dia:,.2f}")

m3, m4 = st.columns(2)
m3.metric("Operações", st.session_state.operacoes)

win_rate = (
    st.session_state.vitorias / st.session_state.operacoes * 100
    if st.session_state.operacoes else 0
)
m4.metric("Taxa de acerto", f"{win_rate:.1f}%")

dd = (
    (st.session_state.saldo / st.session_state.max_equity - 1) * 100
    if st.session_state.max_equity > 0 else 0
)

m5, m6 = st.columns(2)
m5.metric("Drawdown", f"{dd:.2f}%")
m6.metric("Preço simulado", f"{st.session_state.preco:.2f}")

st.subheader("Curva de capital")
st.line_chart(pd.DataFrame({"Saldo": st.session_state.equity}))

st.subheader("Mercado simulado")
st.line_chart(pd.DataFrame({"Preço": st.session_state.precos[-120:]}))

st.subheader("Posição atual")
if st.session_state.posicao:
    pos = st.session_state.posicao
    st.write(f"Entrada: **{pos['entrada']:.2f}**")
    st.write(f"Preço atual: **{st.session_state.preco:.2f}**")
    st.write(f"Stop: **{pos['stop']:.2f}**")
    st.write(f"Alvo: **{pos['alvo']:.2f}**")
    st.write(f"Confiança na entrada: **{pos['ai_confidence']*100:.1f}%**")
else:
    st.info("Nenhuma posição aberta.")

st.subheader("Últimas operações")
if st.session_state.historico:
    st.dataframe(
        pd.DataFrame(st.session_state.historico),
        use_container_width=True,
        hide_index=True
    )
else:
    st.caption("Nenhuma operação encerrada ainda.")

st.markdown("""
<div class="disclaimer">
⚠️ Protótipo educacional em simulação. A “IA” usa sinais quantitativos e pesos
explicáveis sobre preços fictícios. Ela não prevê lucro e não envia ordens reais.
Antes de qualquer uso real, seria necessário validar a estratégia com dados
históricos, paper trading, custos, slippage e regras da corretora.
</div>
""", unsafe_allow_html=True)

if st.session_state.running:
    time.sleep(1)
    st.rerun()
