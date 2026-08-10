import json
import mimetypes
import os
import time
import uuid
import urllib.request
from pathlib import Path

import pipeline.config as config
import pipeline.http as http

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# GL-45: Telegram makes allowed_updates STICKY - it persists from whatever was
# last passed to setWebhook/getUpdates until explicitly changed, across
# restarts. get_updates never passed it, so the effective list was whatever
# any tool had last set, possibly years ago. Assert it on every call rather
# than inherit it from Telegram's memory of something we did not do.
ALLOWED_UPDATES = ["message", "callback_query"]

# GL-45 H3 instrumentation: the raw getUpdates response, verbatim, to a file
# and not to the DB - a DB-write failure must not be able to hide the one
# measurement that discriminates "Telegram never sent it" from "we lost it".
RAW_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "telegram_getupdates.log"


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


def _log_raw_updates(offset, result, raw_log_path) -> None:
    """One JSON line per poll. Never raises - instrumentation must not be able
    to fail a run."""
    try:
        path = Path(raw_log_path or RAW_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "offset": offset,
            "response": result,
        })
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"failed to write getUpdates raw log: {exc}")


def get_updates(offset: int = None, timeout: int = 0, *, bot_token: str = None,
                raw_log_path=None) -> list:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"timeout": timeout, "allowed_updates": ALLOWED_UPDATES}
    if offset is not None:
        payload["offset"] = offset
    result = _post("getUpdates", payload, bot_token)
    _log_raw_updates(offset, result, raw_log_path)
    return result["result"]


def edit_message_reply_markup(chat_id, message_id: int, reply_markup: dict = None, *,
                              bot_token: str = None) -> dict:
    """Replace (or clear, with None) a message's inline keyboard. GL-45: this is
    what makes a tap visibly land - the answerCallbackQuery toast disappears,
    the edited keyboard does not."""
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("editMessageReplyMarkup", payload, bot_token)


def answer_callback_query(callback_query_id: str, text: str = None, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"callback_query_id": callback_query_id}
    if text is not None:
        payload["text"] = text
    return _post("answerCallbackQuery", payload, bot_token)
