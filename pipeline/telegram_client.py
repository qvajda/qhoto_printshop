import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramAPIError(Exception):
    pass


def _post(method: str, payload: dict, bot_token: str) -> dict:
    url = f"{TELEGRAM_API_BASE}{bot_token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    result = http.send(request)
    if not result.get("ok"):
        raise TelegramAPIError(result.get("description", "Unknown Telegram API error"))
    return result


def send_media_group(chat_id: str, photo_urls: list, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    media = [{"type": "photo", "media": url} for url in photo_urls]
    return _post("sendMediaGroup", {"chat_id": chat_id, "media": media}, bot_token)


def send_message(chat_id: str, text: str, reply_markup: dict = None, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload, bot_token)


def get_updates(offset: int = None, timeout: int = 0, *, bot_token: str = None) -> list:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    result = _post("getUpdates", payload, bot_token)
    return result["result"]


def answer_callback_query(callback_query_id: str, text: str = None, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"callback_query_id": callback_query_id}
    if text is not None:
        payload["text"] = text
    return _post("answerCallbackQuery", payload, bot_token)
