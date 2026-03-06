"""
⚔️ QuestBound — Interface Web v0.3
Rode: streamlit run app.py
"""

import streamlit as st
import anthropic
import random, json, os
from datetime import datetime
from engine import (
    Memoria, Stats, Dado, Stat, Tier, rolar, detectar_stat, detectar_tipo,
    pc_quer_rolar, pc_fez_pergunta, GUIAS, PC_STATS, AVENTURAS,
    MODELO_MESTRE, MODELO_PC,
    PROMPT_MESTRE, PROMPT_MESTRE_RESPONDE_PCS,
    PROMPT_KAEL, PROMPT_SERA, PROMPT_THORNE, STAT_NOME
)
import analytics

# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(page_title="QuestBound ⚔️", page_icon="⚔️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #1a1a2e; color: #e0e0e0; }
    .main-title { text-align: center; color: #c4a747; font-size: 2.5em;
                  font-family: Georgia, serif; margin-bottom: 0; }
    .sub-title { text-align: center; color: #888; font-size: 1em; margin-top: 0; }
    .mestre-msg { background-color: #16213e; border-left: 4px solid #c4a747;
                  padding: 15px; border-radius: 0 8px 8px 0; margin: 10px 0; }
    .kael-msg { background-color: #1a1a2e; border-left: 4px solid #e74c3c;
                padding: 12px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .sera-msg { background-color: #1a1a2e; border-left: 4px solid #f39c12;
                padding: 12px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .thorne-msg { background-color: #1a1a2e; border-left: 4px solid #3498db;
                  padding: 12px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .jogador-msg { background-color: #0f3460; border-left: 4px solid #27ae60;
                   padding: 12px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .dado-msg { background-color: #2c2c54; border: 2px solid #c4a747;
                padding: 12px; border-radius: 8px; margin: 10px 0;
                text-align: center; font-size: 1.1em; }
    .sistema-msg { background-color: #1e1e3a; border-left: 4px solid #888;
                   padding: 10px; border-radius: 0 8px 8px 0; margin: 6px 0;
                   font-style: italic; color: #aaa; }
    div[data-testid="stChatMessage"] { background-color: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# STATE INIT
# ================================================================
def init_state():
    if "mem" not in st.session_state:
        st.session_state.mem = Memoria()
    if "msgs" not in st.session_state:
        st.session_state.msgs = []  # [{role, name, content, css_class}]
    if "started" not in st.session_state:
        st.session_state.started = False
    if "nome" not in st.session_state:
        st.session_state.nome = ""
    if "desc" not in st.session_state:
        st.session_state.desc = ""
    if "client" not in st.session_state:
        st.session_state.client = None
    if "aventura" not in st.session_state:
        st.session_state.aventura = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "api_key_raw" not in st.session_state:
        st.session_state.api_key_raw = ""

init_state()


# ================================================================
# API CALL
# ================================================================
def chamar_api(sys_prompt, msg, modelo=MODELO_PC, max_t=600):
    try:
        r = st.session_state.client.messages.create(
            model=modelo, max_tokens=max_t, system=sys_prompt,
            messages=[{"role": "user", "content": msg}],
        )
        st.session_state.mem.track(r.usage.input_tokens, r.usage.output_tokens)
        return r.content[0].text
    except Exception as e:
        analytics.track_error(
            st.session_state.api_key_raw,
            st.session_state.session_id,
            "api_error", str(e), f"modelo={modelo}"
        )
        return f"[Erro: {e}]"


def add_msg(role, name, content, css_class="sistema-msg"):
    st.session_state.msgs.append({
        "role": role, "name": name, "content": content, "css": css_class
    })


# ================================================================
# GAME LOGIC
# ================================================================
def abertura():
    av = st.session_state.aventura
    add_msg("sistema", "📜", f"**{av['titulo']}** — {av['tom']}", "sistema-msg")

    prompt = PROMPT_MESTRE.format(context="Nova aventura.")
    msg = (f"Nova aventura. Gancho: {av['gancho']}\n"
           f"Jogador: {st.session_state.nome}, {st.session_state.desc}.\n"
           f"Grupo: Kael, Sera, Thorne.\n\n"
           f"Descreva o CENÁRIO em detalhes. Comece devagar, deixe o mundo respirar.")

    r = chamar_api(prompt, msg, MODELO_MESTRE, 900)
    add_msg("mestre", "📖 Mestre", r, "mestre-msg")
    st.session_state.mem.add("mestre", "narracao", r)

    reacoes_pc(f"O Mestre narrou a abertura:\n{r}\n\nReaja. NÃO combate. Observe, comente. Breve.")


def reacoes_pc(situacao):
    agentes = [("Kael","🗡️",PROMPT_KAEL,"kael","kael-msg"),
               ("Sera","✨",PROMPT_SERA,"sera","sera-msg"),
               ("Thorne","🛡️",PROMPT_THORNE,"thorne","thorne-msg")]
    ctx = st.session_state.mem.contexto()
    perguntas_pcs = []

    for nome, ic, pr, key, css in agentes:
        r = chamar_api(pr + f"\n\nCONTEXTO:\n{ctx}", situacao, MODELO_PC, 300)
        add_msg("pc", f"{ic} {nome}", r, css)
        st.session_state.mem.add(key, "acao", r)

        # Detecta se PC pediu dados
        if pc_quer_rolar(r):
            rolar_pc(key, nome, ic, r, css)

        # Coleta perguntas ao Mestre
        if pc_fez_pergunta(r):
            perguntas_pcs.append(f"{nome}: {r}")

    # === NOVO: Mestre responde perguntas dos PCs ===
    if perguntas_pcs:
        mestre_responde_pcs(perguntas_pcs)


def mestre_responde_pcs(perguntas):
    """O Mestre responde às perguntas que os PCs fizeram."""
    ctx = st.session_state.mem.contexto()
    prompt = PROMPT_MESTRE_RESPONDE_PCS.format(context=ctx)
    msg = "Os companheiros fizeram perguntas e observações:\n\n"
    for p in perguntas:
        msg += f"- {p}\n"
    msg += "\nResponda cada uma BREVEMENTE (1-2 frases cada). Natural, integrado à narrativa."

    r = chamar_api(prompt, msg, MODELO_MESTRE, 400)
    add_msg("mestre", "📖 Mestre (respondendo o grupo)", r, "mestre-msg")
    st.session_state.mem.add("mestre", "resposta_pcs", r)


def rolar_pc(key, nome, ic, resp, css):
    stat = detectar_stat(resp)
    res = rolar(stat, PC_STATS[key], nome)
    add_msg("dado", "🎲", str(res), "dado-msg")
    st.session_state.mem.add("sistema", "dado", str(res))

    guia = GUIAS.get(detectar_tipo(resp), GUIAS["investigar"])
    ctx = st.session_state.mem.contexto()
    r = chamar_api(
        PROMPT_MESTRE.format(context=ctx),
        f"{nome} tentou: {resp}\nDados:\n{res}\nGuia: {guia[res.tier]}\n\n"
        f"Narre BREVEMENTE (2-3 frases) o resultado de {nome}.",
        MODELO_MESTRE, 250
    )
    add_msg("mestre", f"📖 Mestre ({nome})", r, "mestre-msg")
    st.session_state.mem.add("mestre", "narracao", r)


def processar_acao(inp):
    """Processa ação do jogador."""
    add_msg("jogador", f"🎮 {st.session_state.nome}", inp, "jogador-msg")
    st.session_state.mem.add("jogador", "acao", inp)

    ctx = st.session_state.mem.contexto(20)
    msg = (f"O jogador ({st.session_state.nome}) faz: {inp}\n\n"
           f"Se exigir teste, peça para rolar dados e diga qual atributo. "
           f"NÃO resolva automaticamente. Termine com gancho.")

    r = chamar_api(PROMPT_MESTRE.format(context=ctx), msg, MODELO_MESTRE, 800)
    add_msg("mestre", "📖 Mestre", r, "mestre-msg")
    st.session_state.mem.add("mestre", "narracao", r)

    reacoes_pc(
        f"Jogador ({st.session_state.nome}) fez: {inp}\n"
        f"Mestre: {r}\n\nReaja em personagem. Breve e natural."
    )


def processar_dado(inp):
    """Jogador rola dados."""
    stat = detectar_stat(inp)
    acao = inp

    res = rolar(stat, Stats(forca=1, destreza=1, intelecto=1, coracao=0, sombra=0),
                st.session_state.nome)
    add_msg("jogador", f"🎮 {st.session_state.nome}", acao, "jogador-msg")
    add_msg("dado", "🎲", str(res), "dado-msg")
    st.session_state.mem.add("jogador", "acao", acao)
    st.session_state.mem.add("sistema", "dado", str(res))

    guia = GUIAS.get(detectar_tipo(acao), GUIAS["investigar"])
    ctx = st.session_state.mem.contexto(20)
    msg = (f"Jogador ({st.session_state.nome}) tentou: {acao}\n"
           f"Dados:\n{res}\nGuia: {guia[res.tier]}\n\nNarre resultado. Respeite dados. Gancho.")

    r = chamar_api(PROMPT_MESTRE.format(context=ctx), msg, MODELO_MESTRE, 800)
    add_msg("mestre", "📖 Mestre", r, "mestre-msg")
    st.session_state.mem.add("mestre", "narracao", r)

    reacoes_pc(f"Jogador tentou: {acao}\nDados: {res}\nMestre: {r}\n\nReaja. Breve.")


# ================================================================
# UI
# ================================================================

# HEADER
st.markdown('<h1 class="main-title">⚔️ QuestBound ⚔️</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">RPG de Mesa com Parceiros de IA — v0.3</p>', unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.markdown("### ⚙️ Configuração")
    api_key = st.text_input("🔑 API Key Anthropic", type="password",
                            help="Pega em console.anthropic.com → API Keys")

    if api_key and not st.session_state.client:
        st.session_state.client = anthropic.Anthropic(api_key=api_key)
        st.session_state.api_key_raw = api_key
        st.success("✅ Conectado!")

    # Analytics (Supabase) — config via secrets ou env vars
    sb_url = os.environ.get("SUPABASE_URL", "")
    sb_key = os.environ.get("SUPABASE_KEY", "")
    try:
        if not sb_url and hasattr(st, 'secrets'):
            sb_url = st.secrets.get("SUPABASE_URL", "")
            sb_key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        pass
    if sb_url and sb_key:
        analytics.init(sb_url, sb_key)

    st.markdown("---")
    st.markdown("### 📊 Sessão")
    c = st.session_state.mem.custo()
    st.metric("Turno", st.session_state.mem.turno)
    st.metric("Custo", f"${c['usd']:.4f}")
    st.metric("Chamadas API", c['ch'])

    st.markdown("---")
    st.markdown("### 🗡️ Grupo")
    st.markdown("""
    **Kael** — Ladino Sombrio
    `PV:8/8 | D:2 S:2 I:1`

    **Sera** — Clériga de Batalha
    `PV:10/10 | I:2 C:2 F:1`

    **Thorne** — Cavaleiro Desgraçado
    `PV:12/12 | F:2 S:1 C:1`
    """)

    st.markdown("---")
    if st.button("🆕 Nova Aventura"):
        c = st.session_state.mem.custo()
        analytics.session_end(st.session_state.session_id,
                              st.session_state.mem.turno, c["ti"]+c["to"], c["usd"])
        st.session_state.mem = Memoria()
        st.session_state.msgs = []
        st.session_state.started = False
        st.session_state.session_id = None
        st.rerun()


# SETUP SCREEN
if not st.session_state.started:
    if not st.session_state.client:
        st.info("👈 Cole sua API Key na barra lateral para começar.")
        st.stop()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("🧙 Nome do personagem", value="", placeholder="Ex: Raven")
    with col2:
        desc = st.text_input("📝 Descrição", value="", placeholder="Ex: Elfa rastreadora com arco longo")

    aventura_idx = st.selectbox("📜 Escolha a aventura",
                                options=range(len(AVENTURAS)),
                                format_func=lambda i: f"{AVENTURAS[i]['titulo']} ({AVENTURAS[i]['tom']})")

    if st.button("⚔️ Começar Aventura!", type="primary", use_container_width=True):
        if nome:
            st.session_state.nome = nome
            st.session_state.desc = desc or "Aventureiro errante"
            st.session_state.aventura = AVENTURAS[aventura_idx]
            st.session_state.started = True
            # Track session start
            st.session_state.session_id = analytics.session_start(
                st.session_state.api_key_raw, nome, desc or "",
                AVENTURAS[aventura_idx]["titulo"]
            )
            with st.spinner("📖 O Mestre está preparando o mundo..."):
                abertura()
            st.rerun()
        else:
            st.warning("Dê um nome ao seu personagem!")
    st.stop()


# GAME SCREEN — Display messages
for msg in st.session_state.msgs:
    st.markdown(f'<div class="{msg["css"]}"><strong>{msg["name"]}</strong><br>{msg["content"]}</div>',
                unsafe_allow_html=True)

# INPUT
st.markdown("---")
col_input, col_dado = st.columns([4, 1])

with col_input:
    acao = st.chat_input(f"O que {st.session_state.nome} faz?")

with col_dado:
    rolar_btn = st.button("🎲 Rolar Dados", use_container_width=True)

if rolar_btn:
    dado_acao = st.session_state.get("_dado_acao", "")
    if not dado_acao:
        add_msg("sistema", "⚙️", "Digite uma ação primeiro, depois clique em Rolar Dados.", "sistema-msg")
        st.rerun()

if acao:
    cmd = acao.lower().strip()

    # Check if it's a dice roll command
    if cmd.startswith("rolar") or cmd.startswith("dado") or cmd.startswith("roll"):
        with st.spinner("🎲 Rolando dados..."):
            processar_dado(acao)
    else:
        with st.spinner("📖 O Mestre está narrando..."):
            processar_acao(acao)

    # Auto-save + Analytics
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessoes")
    os.makedirs(save_dir, exist_ok=True)
    st.session_state.mem.salvar_estado(
        os.path.join(save_dir, "_autosave.json"),
        st.session_state.nome, st.session_state.desc
    )
    # Track turn in Supabase
    c = st.session_state.mem.custo()
    analytics.session_update(
        st.session_state.session_id,
        st.session_state.mem.turno,
        c["ti"] + c["to"],
        c["usd"]
    )
    st.rerun()
