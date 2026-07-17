"""One-time: refresh the Etsy OAuth access token via the stored refresh_token,
and write the new access_token (and rotated refresh_token, if issued) back to .env.
"""
import json
import re
import urllib.request
from pathlib import Path

from pipeline import config

ENV_PATH = Path(__file__).resolve().parent / ".env"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def set_env_var(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    return text.rstrip("\n") + f"\n{key}={value}\n"


def main():
    config.load_env()
    client_id = config.require_env("ETSY_API_KEY")
    refresh_token = config.require_env("ETSY_REFRESH_TOKEN")

    body = json.dumps({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))

    new_access_token = result["access_token"]
    new_refresh_token = result.get("refresh_token", refresh_token)

    text = ENV_PATH.read_text(encoding="utf-8")
    text = set_env_var(text, "ETSY_ACCESS_TOKEN", new_access_token)
    text = set_env_var(text, "ETSY_REFRESH_TOKEN", new_refresh_token)
    ENV_PATH.write_text(text, encoding="utf-8")

    print(f"refreshed: expires_in={result.get('expires_in')}s, "
          f"refresh_token_rotated={new_refresh_token != refresh_token}")


if __name__ == "__main__":
    main()
