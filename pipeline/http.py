import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# One honest User-Agent for all first-party API traffic. Set once on the shared
# client - no per-client UA (a fake "Mozilla/..." on a non-browser TLS handshake
# is a bot-score *increase*, see docs/cloudflare_1010_issue_investigation.md).
USER_AGENT = "qhoto-printshop/1.0 (+qvajda@hotmail.fr)"

# Cloudflare 1010 = browser-signature ban, not a rate-limit. Never tight-retry it
# (hammering worsens the score); wait long, a few times, then give up.
_CF_1010_BACKOFFS = (60, 120, 240)

# Module-level, reused across every call: one TLS handshake per run (keep-alive +
# HTTP/2 multiplexing) instead of a fresh urllib bot-fingerprint handshake per
# request. follow_redirects matches urllib's old auto-follow behavior.
_client = httpx.Client(
    http2=True,
    follow_redirects=True,
    headers={"User-Agent": USER_AGENT},
    timeout=30.0,
)


class HTTPError(Exception):
    def __init__(self, status_code: int, body: str, headers=None):
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers) if headers else {}
        super().__init__(f"HTTP {status_code}: {body}")


def _is_cf_1010(body: str) -> bool:
    return "1010" in body


def _request(method: str, url: str, *, headers=None, content=None, timeout: int = 30,
             sleep_fn=time.sleep) -> httpx.Response:
    for wait in (*_CF_1010_BACKOFFS, None):
        response = _client.request(method, url, headers=headers, content=content, timeout=timeout)
        if response.is_success:
            return response
        body = response.text
        if response.status_code == 403:
            # CF-Ray is the ID Cloudflare/vendor support needs to trace the block.
            logger.warning("HTTP 403 from %s (CF-Ray: %s)", url, response.headers.get("cf-ray"))
            if _is_cf_1010(body) and wait is not None:
                logger.warning("Cloudflare 1010 block; backing off %ss before retry", wait)
                sleep_fn(wait)
                continue
        raise HTTPError(response.status_code, body, response.headers)
    # Unreachable: the wait=None iteration always raises above.
    raise HTTPError(response.status_code, response.text, response.headers)


def send(request, timeout: int = 30, sleep_fn=time.sleep) -> dict:
    """Send a urllib.request.Request through the shared client; parse JSON body."""
    response = _request(
        request.get_method(), request.full_url,
        headers=dict(request.header_items()), content=request.data,
        timeout=timeout, sleep_fn=sleep_fn,
    )
    raw_body = response.text
    if not raw_body:
        return {}
    return json.loads(raw_body)


def fetch_bytes(url: str, timeout: int = 30, sleep_fn=time.sleep) -> bytes:
    return _request("GET", url, timeout=timeout, sleep_fn=sleep_fn).content


def head(url: str, timeout: int = 30, sleep_fn=time.sleep) -> httpx.Response:
    return _request("HEAD", url, timeout=timeout, sleep_fn=sleep_fn)


def put_bytes(url: str, data: bytes, headers: dict, timeout: int = 30,
              sleep_fn=time.sleep) -> httpx.Response:
    """PUT raw bytes and return the response (no JSON parsing). Inherits the
    shared client's keep-alive, honest UA, and 1010 backoff; non-2xx raises
    HTTPError via _request. Caller-supplied headers (e.g. SigV4) pass through -
    httpx's own default headers don't collide with what SigV4 signs."""
    return _request("PUT", url, headers=headers, content=data, timeout=timeout, sleep_fn=sleep_fn)
