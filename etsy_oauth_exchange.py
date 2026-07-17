"""One-time: finish the flow started by etsy_oauth_authorize.py. Trades the
authorization code (from the redirected URL) for a fresh access_token +
refresh_token pair carrying the new scopes, and writes both into .env --
same fields refresh_etsy_token.py maintains from then on.

Usage:
    python etsy_oauth_exchange.py "<full redirected URL, or just the code>"
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline import config

ENV_PATH = Path(__file__).resolve().parent / ".env"
STATE_PATH = Path(__file__).resolve().parent / ".etsy_oauth_state.json"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def set_env_var(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    return text.rstrip("\n") + f"\n{key}={value}\n"


def _extract_code_and_state(raw: str) -> tuple:
    if "code=" not in raw and "state=" not in raw:
        return raw, None  # raw code, no state to check
    parsed = urllib.parse.urlparse(raw)
    query = urllib.parse.parse_qs(parsed.query)
    code = query["code"][0]
    state = query.get("state", [None])[0]
    return code, state


def main():
    if len(sys.argv) < 2:
        print('usage: python etsy_oauth_exchange.py "<full redirected URL>"')
        sys.exit(1)

    saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    code, state = _extract_code_and_state(sys.argv[1])
    if state is not None and state != saved["state"]:
        print("state mismatch -- this code wasn't issued for the last "
              "etsy_oauth_authorize.py run. Aborting.")
        sys.exit(1)

    config.load_env()
    client_id = config.require_env("ETSY_API_KEY")

    body = json.dumps({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": saved["redirect_uri"],
        "code": code,
        "code_verifier": saved["code_verifier"],
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))

    text = ENV_PATH.read_text(encoding="utf-8")
    text = set_env_var(text, "ETSY_ACCESS_TOKEN", result["access_token"])
    text = set_env_var(text, "ETSY_REFRESH_TOKEN", result["refresh_token"])
    ENV_PATH.write_text(text, encoding="utf-8")

    STATE_PATH.unlink(missing_ok=True)
    print(f"new token written to .env: expires_in={result.get('expires_in')}s")


if __name__ == "__main__":
    main()
