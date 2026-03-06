"""
QuestBound Analytics v0.3
=========================
Rastreia sessões, turnos, erros e eventos no Supabase.
Regra #1: NUNCA quebrar o jogo. Se analytics falhar, falha silenciosamente.
"""

import uuid
import hashlib
import traceback
from datetime import datetime

_client = None
_enabled = False


def init(supabase_url: str, supabase_key: str):
    """Inicializa conexão com Supabase."""
    global _client, _enabled
    if not supabase_url or not supabase_key:
        _enabled = False
        return False
    try:
        from supabase import create_client
        _client = create_client(supabase_url, supabase_key)
        _enabled = True
        return True
    except Exception:
        _enabled = False
        return False


def _gerar_user_id(api_key: str) -> str:
    """Gera ID anônimo a partir da API key (hash, sem armazenar a key)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _safe(func):
    """Decorator: se analytics falhar, falha silenciosamente."""
    def wrapper(*args, **kwargs):
        if not _enabled:
            return None
        try:
            return func(*args, **kwargs)
        except Exception:
            return None
    return wrapper


# ================================================================
# SESSÕES
# ================================================================

@_safe
def session_start(api_key: str, player_name: str, player_desc: str, adventure: str) -> str:
    """Registra início de sessão. Retorna session_id."""
    user_id = _gerar_user_id(api_key)
    session_id = str(uuid.uuid4())

    _client.table("sessions").insert({
        "id": session_id,
        "user_id": user_id,
        "player_name": player_name,
        "player_desc": player_desc,
        "adventure": adventure,
        "status": "active",
    }).execute()

    # Evento: session_start
    event(api_key, session_id, "session_start", {
        "adventure": adventure,
        "player_name": player_name,
    })

    # Verificar se é retorno
    existing = _client.table("sessions")\
        .select("id")\
        .eq("user_id", user_id)\
        .execute()
    if len(existing.data) > 1:
        event(api_key, session_id, "return_visit", {
            "total_sessions": len(existing.data)
        })

    return session_id


@_safe
def session_end(session_id: str, total_turns: int, total_tokens: int, cost_usd: float):
    """Registra fim de sessão."""
    _client.table("sessions").update({
        "ended_at": datetime.now().isoformat(),
        "total_turns": total_turns,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "status": "completed",
    }).eq("id", session_id).execute()


@_safe
def session_update(session_id: str, total_turns: int, total_tokens: int, cost_usd: float):
    """Atualiza sessão em andamento (a cada turno)."""
    _client.table("sessions").update({
        "total_turns": total_turns,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }).eq("id", session_id).execute()


# ================================================================
# TURNOS
# ================================================================

@_safe
def track_turn(session_id: str, turn_number: int, player_action: str,
               dm_response: str, kael: str = "", sera: str = "", thorne: str = "",
               dice_result: str = "", tokens: int = 0, cost: float = 0):
    """Registra um turno completo."""
    _client.table("turns").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "player_action": player_action[:500],    # Limita tamanho
        "dm_response": dm_response[:1000],
        "kael_response": kael[:500],
        "sera_response": sera[:500],
        "thorne_response": thorne[:500],
        "dice_result": dice_result[:200],
        "tokens_used": tokens,
        "cost_usd": cost,
    }).execute()


# ================================================================
# ERROS
# ================================================================

@_safe
def track_error(api_key: str, session_id: str, error_type: str,
                error_message: str, context: str = ""):
    """Registra um erro."""
    user_id = _gerar_user_id(api_key) if api_key else "unknown"
    _client.table("error_log").insert({
        "session_id": session_id,
        "user_id": user_id,
        "error_type": error_type,
        "error_message": str(error_message)[:1000],
        "context": context[:500],
    }).execute()


# ================================================================
# EVENTOS
# ================================================================

@_safe
def event(api_key: str, session_id: str, event_type: str, data: dict = None):
    """Registra evento genérico."""
    import json
    user_id = _gerar_user_id(api_key) if api_key else "unknown"
    _client.table("analytics_events").insert({
        "user_id": user_id,
        "session_id": session_id,
        "event_type": event_type,
        "event_data": json.dumps(data or {}),
    }).execute()


# ================================================================
# MÉTRICAS (para dashboard)
# ================================================================

@_safe
def get_global_metrics() -> dict:
    """Busca métricas globais."""
    result = _client.table("global_metrics").select("*").execute()
    if result.data:
        return result.data[0]
    return {}


@_safe
def get_user_metrics() -> list:
    """Busca métricas por usuário."""
    result = _client.table("user_metrics").select("*")\
        .order("total_sessions", desc=True).limit(50).execute()
    return result.data or []


@_safe
def get_recent_sessions(limit: int = 20) -> list:
    """Busca sessões recentes."""
    result = _client.table("sessions").select("*")\
        .order("started_at", desc=True).limit(limit).execute()
    return result.data or []


@_safe
def get_recent_errors(limit: int = 20) -> list:
    """Busca erros recentes."""
    result = _client.table("error_log").select("*")\
        .order("created_at", desc=True).limit(limit).execute()
    return result.data or []
