
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

st.set_page_config(
    page_title="AutoTrade Mobile",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container {
        max-width: 520px;
        padding-top: 1rem;
        padding-bottom: 6rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(120,120,120,0.08);
        border-radius: 16px;
        padding: 12px;
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
    .disclaimer {
        font-size: 0.82rem;
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
    "posicao": None,
    "historico": [],
    "equity": [1000.0],
    "pnl_dia": 0.0,
    "operacoes": 0,
    "vitorias": 0,
    "derrotas": 0,
    "perfil": "Moderado",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def params(perfil):
    tabela = {
        "Conservador": {"risco": 0.003, "stop": 0.006, "alvo": 0.010, "stop_dia": 0.015},
        "Moderado": {"risco": 0.005, "stop": 0.008, "alvo": 0.014, "stop_dia": 0.020},
        "Agressivo": {"risco": 0.010, "stop": 0.012, "alvo": 0.022, "stop_dia": 0.035},
    }
    return tabela[perfil]

def gerar_preco(preco):
    retorno = np.random.normal(0.00015, 0.0055)
    return max(1.0, preco * (1 + retorno))

def sinal():
    # Apenas para demonstração do fluxo automático.
    return np.random.random() > 0.84

def abrir_posicao():
    p = params(st.session_state.perfil)
    saldo = st.session_state.saldo
    preco = st.session_state.preco
    risco_reais = saldo * p["risco"]
    distancia_stop = preco * p["stop"]
    quantidade = max(0.0001, risco_reais / distancia_stop)
    st.session_state.posicao = {
        "entrada": preco,
        "stop": preco * (1 - p["stop"]),
        "alvo": preco * (1 + p["alvo"]),
        "quantidade": quantidade,
        "hora": datetime.now().strftime("%H:%M:%S")
    }

def fechar_posicao(preco_saida, motivo):
    pos = st.session_state.posicao
    pnl = (preco_saida - pos["entrada"]) * pos["quantidade"]
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
        "Saída": round(preco_saida, 2),
        "Resultado": round(pnl, 2),
        "Motivo": motivo,
    })
    st.session_state.posicao = None

# Cabeçalho
st.title("📈 AutoTrade Mobile")
st.caption("MVP de trading automático — modo simulado")

status_class = "status-running" if st.session_state.running else "status-stopped"
status_text = "🟢 ROBÔ OPERANDO" if st.session_state.running else "⚪ ROBÔ PARADO"
st.markdown(f'<div class="{status_class}">{status_text}</div>', unsafe_allow_html=True)

# Configuração principal
st.subheader("Configuração")

capital = st.number_input(
    "Capital simulado",
    min_value=100.0,
    value=float(st.session_state.capital),
    step=100.0,
    format="%.2f",
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
    if st.button("▶ INICIAR", use_container_width=True, disabled=st.session_state.running):
        st.session_state.capital = capital
        st.session_state.saldo = capital
        st.session_state.perfil = perfil
        st.session_state.pnl_dia = 0.0
        st.session_state.operacoes = 0
        st.session_state.vitorias = 0
        st.session_state.derrotas = 0
        st.session_state.historico = []
        st.session_state.equity = [capital]
        st.session_state.posicao = None
        st.session_state.running = True
        st.rerun()

with c2:
    if st.button("■ PARAR", use_container_width=True, disabled=not st.session_state.running):
        st.session_state.running = False
        st.rerun()

# Motor simulado
if st.session_state.running:
    st.session_state.preco = gerar_preco(st.session_state.preco)
    p = params(st.session_state.perfil)
    limite = -st.session_state.capital * p["stop_dia"]

    if st.session_state.pnl_dia <= limite:
        st.session_state.running = False
        st.error("Limite diário de perda atingido. O robô foi desligado.")

    elif st.session_state.posicao:
        pos = st.session_state.posicao
        if st.session_state.preco <= pos["stop"]:
            fechar_posicao(pos["stop"], "Stop-loss")
        elif st.session_state.preco >= pos["alvo"]:
            fechar_posicao(pos["alvo"], "Take-profit")

    elif sinal():
        abrir_posicao()

    st.session_state.equity.append(st.session_state.saldo)

st.divider()
st.subheader("Painel")

m1, m2 = st.columns(2)
m1.metric("Saldo", f"R$ {st.session_state.saldo:,.2f}")
m2.metric("Hoje", f"R$ {st.session_state.pnl_dia:,.2f}")

m3, m4 = st.columns(2)
m3.metric("Operações", st.session_state.operacoes)
taxa = (
    st.session_state.vitorias / st.session_state.operacoes * 100
    if st.session_state.operacoes else 0
)
m4.metric("Acerto", f"{taxa:.1f}%")

st.subheader("Curva de capital")
st.line_chart(pd.DataFrame({"Saldo": st.session_state.equity}))

st.subheader("Posição atual")
if st.session_state.posicao:
    pos = st.session_state.posicao
    st.write(f"Entrada: **{pos['entrada']:.2f}**")
    st.write(f"Preço atual: **{st.session_state.preco:.2f}**")
    st.write(f"Stop: **{pos['stop']:.2f}**")
    st.write(f"Alvo: **{pos['alvo']:.2f}**")
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
Este aplicativo é apenas um simulador educacional. Não há garantia de lucro e
nenhuma ordem real é enviada ao mercado.
</div>
""", unsafe_allow_html=True)

if st.session_state.running:
    time.sleep(1)
    st.rerun()
