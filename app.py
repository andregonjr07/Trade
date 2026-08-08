
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

st.set_page_config(page_title="AutoTrade MVP", page_icon="📈", layout="wide")

# -------------------------
# Estado
# -------------------------
defaults = {
    "running": False,
    "capital_inicial": 1000.0,
    "saldo": 1000.0,
    "preco": 100.0,
    "posicao": None,
    "historico": [],
    "equity": [1000.0],
    "pnl_dia": 0.0,
    "operacoes": 0,
    "vitorias": 0,
    "derrotas": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------
# Estratégia simulada
# -------------------------
def gerar_preco(preco_atual):
    retorno = np.random.normal(0.0002, 0.006)
    return max(1, preco_atual * (1 + retorno))

def parametros_risco(perfil):
    return {
        "Conservador": {"risco": 0.003, "stop": 0.006, "alvo": 0.010, "stop_dia": 0.015},
        "Moderado":    {"risco": 0.005, "stop": 0.008, "alvo": 0.014, "stop_dia": 0.020},
        "Agressivo":   {"risco": 0.010, "stop": 0.012, "alvo": 0.022, "stop_dia": 0.035},
    }[perfil]

def decidir_entrada():
    # MVP: sinal estatístico simples, deliberadamente simulado.
    return np.random.random() > 0.82

def abrir_posicao(preco, saldo, perfil):
    p = parametros_risco(perfil)
    risco_reais = saldo * p["risco"]
    distancia_stop = preco * p["stop"]
    quantidade = max(0.0001, risco_reais / distancia_stop)
    return {
        "entrada": preco,
        "quantidade": quantidade,
        "stop": preco * (1 - p["stop"]),
        "alvo": preco * (1 + p["alvo"]),
        "hora": datetime.now().strftime("%H:%M:%S"),
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
        "Horário": datetime.now().strftime("%H:%M:%S"),
        "Entrada": round(pos["entrada"], 2),
        "Saída": round(preco_saida, 2),
        "Resultado (R$)": round(pnl, 2),
        "Motivo": motivo,
    })
    st.session_state.posicao = None

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("⚙️ Configuração")

capital = st.sidebar.number_input(
    "Capital simulado (R$)",
    min_value=100.0,
    value=float(st.session_state.capital_inicial),
    step=100.0,
    disabled=st.session_state.running,
)

perfil = st.sidebar.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Agressivo"],
    index=1,
    disabled=st.session_state.running,
)

st.sidebar.caption("Esta versão opera somente em SIMULAÇÃO. Não envia ordens reais.")

col_a, col_b = st.sidebar.columns(2)
with col_a:
    if st.button("▶ Iniciar", use_container_width=True, disabled=st.session_state.running):
        st.session_state.capital_inicial = capital
        st.session_state.saldo = capital
        st.session_state.pnl_dia = 0.0
        st.session_state.operacoes = 0
        st.session_state.vitorias = 0
        st.session_state.derrotas = 0
        st.session_state.historico = []
        st.session_state.equity = [capital]
        st.session_state.posicao = None
        st.session_state.running = True
        st.rerun()

with col_b:
    if st.button("■ Parar", use_container_width=True, disabled=not st.session_state.running):
        st.session_state.running = False
        st.rerun()

# -------------------------
# Motor
# -------------------------
if st.session_state.running:
    st.session_state.preco = gerar_preco(st.session_state.preco)

    p = parametros_risco(perfil)
    limite_perda = -st.session_state.capital_inicial * p["stop_dia"]

    if st.session_state.pnl_dia <= limite_perda:
        st.session_state.running = False
        st.warning("Stop diário atingido. O robô foi desligado automaticamente.")

    elif st.session_state.posicao:
        pos = st.session_state.posicao
        if st.session_state.preco <= pos["stop"]:
            fechar_posicao(pos["stop"], "Stop-loss")
        elif st.session_state.preco >= pos["alvo"]:
            fechar_posicao(pos["alvo"], "Take-profit")

    elif decidir_entrada():
        st.session_state.posicao = abrir_posicao(
            st.session_state.preco,
            st.session_state.saldo,
            perfil
        )

    st.session_state.equity.append(st.session_state.saldo)

# -------------------------
# Interface
# -------------------------
st.title("📈 AutoTrade MVP")
st.caption("Protótipo educacional de trading automático — modo simulado")

status = "🟢 OPERANDO" if st.session_state.running else "⚪ PARADO"
st.subheader(status)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Saldo", f"R$ {st.session_state.saldo:,.2f}")
c2.metric("Resultado do dia", f"R$ {st.session_state.pnl_dia:,.2f}")
c3.metric("Operações", st.session_state.operacoes)
taxa = (st.session_state.vitorias / st.session_state.operacoes * 100) if st.session_state.operacoes else 0
c4.metric("Taxa de acerto", f"{taxa:.1f}%")

st.divider()

c5, c6 = st.columns([2,1])

with c5:
    st.subheader("Evolução do capital")
    df_eq = pd.DataFrame({"Saldo": st.session_state.equity})
    st.line_chart(df_eq)

with c6:
    st.subheader("Posição atual")
    if st.session_state.posicao:
        pos = st.session_state.posicao
        st.write(f"**Entrada:** {pos['entrada']:.2f}")
        st.write(f"**Preço atual:** {st.session_state.preco:.2f}")
        st.write(f"**Stop:** {pos['stop']:.2f}")
        st.write(f"**Alvo:** {pos['alvo']:.2f}")
        st.write(f"**Quantidade:** {pos['quantidade']:.4f}")
    else:
        st.info("Nenhuma posição aberta.")

st.subheader("Histórico de operações")
if st.session_state.historico:
    st.dataframe(pd.DataFrame(st.session_state.historico), use_container_width=True)
else:
    st.caption("As operações aparecerão aqui.")

st.divider()
st.caption(
    "Aviso: este MVP não prevê lucro e não usa dinheiro real. "
    "Trading envolve risco de perda. Antes de qualquer integração real, "
    "a estratégia precisa ser validada com backtest e paper trading."
)

if st.session_state.running:
    time.sleep(1)
    st.rerun()
