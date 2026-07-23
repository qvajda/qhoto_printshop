import json
import logging
import random
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

# GL-16: general transient-fault backoff (connection resets/timeouts, 5xx, 429
# without a usable Retry-After) - short, this is a network blip not a WAF ban.
# Deliberately much shorter than the CF-1010 table above (that's a reputation
# score you make worse by hammering; this is "the vendor's TCP stack hiccuped").
_TRANSIENT_BACKOFFS = (2, 5, 10)

# 429 Retry-After is honored as given (Replicate/Gelato may ask for it), but
# capped so one vendor's oversized ask can't stall a whole batch run.
_RETRY_AFTER_CAP = 120.0

# Retried exactly once (not on the general transient table) - these normally mean
# a genuine bad request/missing resource, but GL-9 observed a live Replicate 404
# ("No adapter found for model") on a call that succeeded seconds later on retry.
# One retry catches that vendor-side fluke without masking a real payload bug
# past a single attempt.
_BOUNDED_RETRY_STATUS_CODES = (400, 404, 422)

_TRANSIENT_CONNECTION_ERRORS = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)


def _jittered(interval: float) -> float:
    # +-20% jitter, same convention as group_product._jittered - desynchronizes
    # retries so a run isn't a metronome of identical fresh connections.
    return interval * random.uniform(0.8, 1.2)


def _retry_after_seconds(headers) -> float | None:
    """Case-insensitive Retry-After lookup, capped at _RETRY_AFTER_CAP. Only
    handles the numeric-seconds form (both vendors in this pipeline use it);
    returns None if absent or unparseable."""
    for key, value in (headers or {}).items():
        if key.lower() == "retry-after":
            try:
                return min(float(value), _RETRY_AFTER_CAP)
            except (TypeError, ValueError):
                return None
    return None

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
    cf_1010_waits = iter(_CF_1010_BACKOFFS)
    transient_waits = iter(_TRANSIENT_BACKOFFS)
    bounded_retry_available = True

    while True:
        try:
            response = _client.request(method, url, headers=headers, content=content, timeout=timeout)
        except _TRANSIENT_CONNECTION_ERRORS as exc:
            wait = next(transient_waits, None)
            if wait is None:
                raise
            logger.warning(
                "Transient connection fault (%s) on %s; retrying in %.1fs",
                type(exc).__name__, url, wait,
            )
            sleep_fn(_jittered(wait))
            continue

        if response.is_success:
            return response

        body = response.text
        status = response.status_code

        if status == 403:
            # CF-Ray is the ID Cloudflare/vendor support needs to trace the block.
            logger.warning("HTTP 403 from %s (CF-Ray: %s)", url, response.headers.get("cf-ray"))
            if _is_cf_1010(body):
                wait = next(cf_1010_waits, None)
                if wait is not None:
                    logger.warning("Cloudflare 1010 block; backing off %ss before retry", wait)
                    sleep_fn(wait)
                    continue
            raise HTTPError(status, body, response.headers)

        if status == 429:
            wait = _retry_after_seconds(response.headers)
            if wait is None:
                fallback = next(transient_waits, None)
                if fallback is None:
                    raise HTTPError(status, body, response.headers)
                wait = _jittered(fallback)
            logger.warning("HTTP 429 from %s; retrying in %.1fs", url, wait)
            sleep_fn(wait)
            continue

        if 500 <= status < 600:
            wait = next(transient_waits, None)
            if wait is None:
                raise HTTPError(status, body, response.headers)
            logger.warning("HTTP %s from %s; retrying in %.1fs", status, url, wait)
            sleep_fn(_jittered(wait))
            continue

        if status in _BOUNDED_RETRY_STATUS_CODES and bounded_retry_available:
            bounded_retry_available = False
            wait = _jittered(_TRANSIENT_BACKOFFS[0])
            logger.warning(
                "HTTP %s from %s; retrying once in %.1fs (vendor-side fluke, not blind-retried further)",
                status, url, wait,
            )
            sleep_fn(wait)
            continue

        raise HTTPError(status, body, response.headers)


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
