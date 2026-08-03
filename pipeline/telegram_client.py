import json
import mimetypes
import os
import uuid
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


def _post_multipart(method: str, fields: dict, files: dict, bot_token: str) -> dict:
    """files maps name -> (filename, bytes). Callers own fetching the bytes (a local
    path read or a downloaded URL) - this just builds the multipart body."""
    url = f"{TELEGRAM_API_BASE}{bot_token}/{method}"
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    for name, (filename, data) in files.items():
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8")
            + data + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST"
    )
    result = http.send(request)
    if not result.get("ok"):
        raise TelegramAPIError(result.get("description", "Unknown Telegram API error"))
    return result


def send_media_group(chat_id: str, photo_urls: list, *, bot_token: str = None) -> dict:
    """Always uploads as multipart, never references a URL in the request. Telegram's
    own server-side URL fetch (used when 'media' is a bare URL string) is unreliable
    for our composited galleries - live gallery images run 500KB-7.5MB and it failed
    with WEBPAGE_CURL_FAILED partway through a 10-image group (GL-13 R3, 2026-08-02).
    Downloading here and attaching removes that fetch from the failure path entirely,
    at the cost of one extra round-trip per image."""
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    media = []
    files = {}
    for i, item in enumerate(photo_urls):
        attach_name = f"attach{i}"
        media.append({"type": "photo", "media": f"attach://{attach_name}"})
        if item.startswith(("http://", "https://")):
            filename = item.rsplit("/", 1)[-1] or f"{attach_name}.png"
            files[attach_name] = (filename, http.fetch_bytes(item))
        else:
            with open(item, "rb") as f:
                files[attach_name] = (os.path.basename(item), f.read())
    return _post_multipart(
        "sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(media)}, files, bot_token,
    )


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
