# Notificaciones por Telegram usando la API sendMessage.
# Usa env.TELEGRAM_BOT_TOKEN y env.TELEGRAM_CHAT_ID (nunca hardcodear).

import json
from workers import fetch

TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_telegram_notification(text: str, env) -> bool:
    """
    Envía un mensaje al chat configurado usando parse_mode=HTML.
    Devuelve True si se envió correctamente, False en caso contrario.
    """
    token = getattr(env, "TELEGRAM_BOT_TOKEN", None) or (
        env.get("TELEGRAM_BOT_TOKEN") if callable(getattr(env, "get", None)) else None
    )
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", None) or (
        env.get("TELEGRAM_CHAT_ID") if callable(getattr(env, "get", None)) else None
    )
    if not token or not chat_id:
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = await fetch(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=_to_json(payload),
        )
        return response.status >= 200 and response.status < 300
    except Exception:
        return False


def _to_json(obj):
    return json.dumps(obj)
