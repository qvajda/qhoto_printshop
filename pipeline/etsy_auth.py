"""Shared Etsy OAuth refresh-token grant. Used both by the pipeline's
401-triggered auto-refresh (etsy_client.py) and the manual refresh_etsy_token.py
standalone script, so there's exactly one code path that talks to Etsy's token
endpoint and one that writes the result back to .env.
"""
import json
import os
import re
import urllib.request

import pipeline.config as config
import pipeline.http as http

TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def _set_env_var(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    return text.rstrip("\n") + f"\n{key}={value}\n"


def refresh(*, client_id: str = None, refresh_token: str = None, env_path=None) -> dict:
    """Performs the refresh_token grant, persists the new access_token and the
    (possibly rotated) refresh_token to both .env and os.environ, and returns
    them. Etsy rotates refresh_token on every use - dropping the new one would
    break the *next* refresh, so it's always written back even though only
    access_token is needed by the immediate caller."""
    client_id = client_id or config.require_env("ETSY_API_KEY")
    refresh_token = refresh_token or config.require_env("ETSY_REFRESH_TOKEN")
    env_path = env_path or config.DEFAULT_ENV_PATH

    body = json.dumps({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL, data=body, method="POST", headers={"Content-Type": "application/json"},
    )
    result = http.send(request)

    new_access_token = result["access_token"]
    new_refresh_token = result.get("refresh_token", refresh_token)

    text = env_path.read_text(encoding="utf-8")
    text = _set_env_var(text, "ETSY_ACCESS_TOKEN", new_access_token)
    text = _set_env_var(text, "ETSY_REFRESH_TOKEN", new_refresh_token)
    env_path.write_text(text, encoding="utf-8")

    os.environ["ETSY_ACCESS_TOKEN"] = new_access_token
    os.environ["ETSY_REFRESH_TOKEN"] = new_refresh_token

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "rotated": new_refresh_token != refresh_token,
        "expires_in": result.get("expires_in"),
    }
