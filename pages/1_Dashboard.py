"""
📊 QuestBound — Dashboard de Métricas
Acessível via sidebar no app principal
"""

import streamlit as st
import os
import analytics

st.set_page_config(page_title="QuestBound Dashboard 📊", page_icon="📊", layout="wide")

st.markdown("# 📊 QuestBound — Dashboard")
st.markdown("Métricas da Fase 0 de validação")

# Init analytics
sb_url = os.environ.get("SUPABASE_URL", "")
sb_key = os.environ.get("SUPABASE_KEY", "")
try:
    if not sb_url and hasattr(st, 'secrets'):
        sb_url = st.secrets.get("SUPABASE_URL", "")
        sb_key = st.secrets.get("SUPABASE_KEY", "")
except Exception:
    pass

if not sb_url or not sb_key:
    st.warning("⚠️ Supabase não configurado. Adicione SUPABASE_URL e SUPABASE_KEY nos secrets.")
    st.info("Vá em Settings → Secrets no Streamlit Cloud e adicione:\n"
            "```\nSUPABASE_URL = \"https://xxx.supabase.co\"\nSUPABASE_KEY = \"eyJ...\"\n```")
    st.stop()

analytics.init(sb_url, sb_key)

# ================================================================
# MÉTRICAS GLOBAIS
# ================================================================
st.markdown("---")
st.markdown("## 🌍 Métricas Globais")

global_data = analytics.get_global_metrics()
if global_data:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Usuários Únicos", global_data.get("total_users", 0))
    col2.metric("🎮 Sessões Total", global_data.get("total_sessions", 0))
    col3.metric("🔄 Retornaram", f"{global_data.get('retention_pct', 0)}%")
    col4.metric("💰 Custo Total", f"${global_data.get('total_cost', 0):.4f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("🎯 Turnos Total", global_data.get("total_turns", 0))
    col6.metric("📊 Média Turnos/Sessão", f"{global_data.get('avg_turns_per_session', 0):.1f}")
    col7.metric("🔁 Usuários que Voltaram", global_data.get("returning_users", 0))
    col8.metric("📈 Taxa de Retenção", f"{global_data.get('retention_pct', 0)}%")
else:
    st.info("Nenhum dado ainda. Jogue uma sessão primeiro!")

# ================================================================
# SESSÕES RECENTES
# ================================================================
st.markdown("---")
st.markdown("## 🕐 Sessões Recentes")

sessions = analytics.get_recent_sessions(20)
if sessions:
    for s in sessions:
        status_icon = "🟢" if s.get("status") == "active" else "✅"
        with st.expander(
            f"{status_icon} {s.get('player_name', '?')} — {s.get('adventure', '?')} "
            f"| {s.get('total_turns', 0)} turnos | ${s.get('cost_usd', 0):.4f}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Jogador:** {s.get('player_name', '?')}")
            col1.write(f"**Descrição:** {s.get('player_desc', '-')}")
            col2.write(f"**Aventura:** {s.get('adventure', '?')}")
            col2.write(f"**Status:** {s.get('status', '?')}")
            col3.write(f"**Início:** {s.get('started_at', '?')[:19]}")
            col3.write(f"**Fim:** {(s.get('ended_at') or 'em andamento')[:19]}")
            st.write(f"**Turnos:** {s.get('total_turns', 0)} | "
                     f"**Tokens:** {s.get('total_tokens', 0):,} | "
                     f"**Custo:** ${s.get('cost_usd', 0):.4f}")
else:
    st.info("Nenhuma sessão registrada ainda.")

# ================================================================
# MÉTRICAS POR USUÁRIO
# ================================================================
st.markdown("---")
st.markdown("## 👤 Métricas por Usuário")

users = analytics.get_user_metrics()
if users:
    import pandas as pd
    df = pd.DataFrame(users)
    # Rename columns for display
    rename = {
        "user_id": "ID (anônimo)", "total_sessions": "Sessões",
        "total_turns": "Turnos", "avg_turns_per_session": "Média Turnos",
        "total_cost": "Custo ($)", "first_session": "Primeira",
        "last_session": "Última", "active_days": "Dias Ativos",
        "returned": "Voltou?"
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    st.dataframe(df, use_container_width=True)
else:
    st.info("Nenhum dado de usuário ainda.")

# ================================================================
# ERROS RECENTES
# ================================================================
st.markdown("---")
st.markdown("## ⚠️ Erros Recentes")

errors = analytics.get_recent_errors(10)
if errors:
    for e in errors:
        with st.expander(f"❌ {e.get('error_type', '?')} — {e.get('created_at', '?')[:19]}"):
            st.write(f"**Tipo:** {e.get('error_type', '?')}")
            st.write(f"**Mensagem:** {e.get('error_message', '?')}")
            st.write(f"**Contexto:** {e.get('context', '-')}")
            st.write(f"**Usuário:** {e.get('user_id', '?')[:8]}...")
else:
    st.success("✅ Nenhum erro registrado!")

# ================================================================
# KPIs DA FASE 0
# ================================================================
st.markdown("---")
st.markdown("## 🎯 KPIs da Fase 0 (Business Plan)")

if global_data:
    st.markdown("""
    | KPI | Meta | Atual | Status |
    |-----|------|-------|--------|
    | Retenção (voltaram) | >40% | {ret}% | {ret_s} |
    | Sessões médias/usuário | >4 | {avg:.1f} | {avg_s} |
    | Custo/sessão | <$0.50 | ${cost:.4f} | {cost_s} |
    """.format(
        ret=global_data.get("retention_pct", 0),
        ret_s="✅" if (global_data.get("retention_pct", 0) or 0) >= 40 else "⏳",
        avg=global_data.get("avg_turns_per_session", 0) or 0,
        avg_s="✅" if (global_data.get("avg_turns_per_session", 0) or 0) >= 4 else "⏳",
        cost=(global_data.get("total_cost", 0) or 0) / max(global_data.get("total_sessions", 1), 1),
        cost_s="✅" if ((global_data.get("total_cost", 0) or 0) / max(global_data.get("total_sessions", 1), 1)) < 0.5 else "⚠️",
    ))
else:
    st.info("Jogue sessões primeiro para ver KPIs.")

st.markdown("---")
st.caption("QuestBound Analytics — Fase 0 Validation Dashboard")
