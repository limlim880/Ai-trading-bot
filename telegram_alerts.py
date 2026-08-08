import requests

from config import settings


def send_telegram_message(message: str) -> None:
    url = (
        f"https://api.telegram.org/bot"
        f"{settings.telegram_bot_token}/sendMessage"
    )

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        details = ""
        if getattr(exc, "response", None) is not None:
            details = f" Telegram response: {exc.response.text}"
        raise RuntimeError(
            f"Telegram message could not be sent.{details}"
        ) from exc
