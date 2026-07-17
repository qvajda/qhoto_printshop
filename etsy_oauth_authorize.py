"""One-time: start the Etsy OAuth authorization-code+PKCE flow to mint a
NEW access/refresh token pair with a chosen scope set (e.g. adding write
scopes that the current token was never granted). refresh_etsy_token.py
cannot do this -- refresh only renews the scopes a token already has.

Usage:
    python etsy_oauth_authorize.py

Prints an authorize URL. Open it, log in as the shop owner, approve, and
you'll land on the app's redirect_uri with ?code=...&state=... in the
address bar (the page itself may 404 -- that's fine, only the URL matters).
Copy the full redirected URL and pass it to etsy_oauth_exchange.py.
"""
import base64
import hashlib
import json
import secrets
import sys
import urllib.parse
from pathlib import Path

from pipeline import config

STATE_PATH = Path(__file__).resolve().parent / ".etsy_oauth_state.json"
AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"

# Must exactly match a Redirect URI registered on the app in the Etsy
# Developer dashboard.
DEFAULT_REDIRECT_URI = "https://www.example.com/oauth/redirect"

# SPEC_v4.4: shop-section (shops_w) + listing patch (listings_w) both needed;
# _r counterparts needed to read what we're patching; transactions_r for
# order data.
SCOPES = "listings_r listings_w shops_r shops_w transactions_r"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def main():
    config.load_env()
    client_id = config.require_env("ETSY_API_KEY")
    redirect_uri = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REDIRECT_URI

    code_verifier = _b64url(secrets.token_bytes(48))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(16))

    STATE_PATH.write_text(json.dumps({
        "code_verifier": code_verifier,
        "state": state,
        "redirect_uri": redirect_uri,
    }), encoding="utf-8")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    print(f"scopes requested: {SCOPES}\n")
    print("Open this URL, log in as the shop owner, and approve:\n")
    print(url)
    print("\nThen run:")
    print('  python etsy_oauth_exchange.py "<full redirected URL>"')


if __name__ == "__main__":
    main()
