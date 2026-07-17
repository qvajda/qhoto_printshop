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
    url = f"{TELEGRAM_API_BASE}{bot_token}/{method}"
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    for name, path in files.items():
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8")
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
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    local_paths = [p for p in photo_urls if not p.startswith(("http://", "https://"))]
    if not local_paths:
        media = [{"type": "photo", "media": url} for url in photo_urls]
        return _post("sendMediaGroup", {"chat_id": chat_id, "media": media}, bot_token)

    # Locally cover-cropped previews (pipeline.image_crop) have no public URL, so
    # they must be uploaded as multipart attachments instead of referenced by URL.
    media = []
    files = {}
    for i, item in enumerate(photo_urls):
        if item.startswith(("http://", "https://")):
            media.append({"type": "photo", "media": item})
        else:
            attach_name = f"attach{i}"
            media.append({"type": "photo", "media": f"attach://{attach_name}"})
            files[attach_name] = item
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
