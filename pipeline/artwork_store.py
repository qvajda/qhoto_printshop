import datetime
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ARTWORK_CACHE_DIR = Path(__file__).resolve().parent.parent / "db" / "base_artwork"

R2_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_ENDPOINT",
    "R2_PUBLIC_BASE_URL",
)

R2_REGION = "auto"
R2_SERVICE = "s3"


def persist_base_artwork(candidate_id: int, raw_bytes: bytes) -> dict:
    """Archives a candidate's base artwork bytes locally, keyed by candidate_id.

    Idempotent: if the archive already holds bytes with the same sha256, the
    file is left untouched. A different hash for the same candidate_id (a
    generate-retry) overwrites it - last write wins, no versioning.

    The local write (Task 1) always happens - it's the permanent local backup
    per PRD 5.5. If all R2_* env vars are set (Task 2), the bytes are also
    uploaded to R2 (Cloudflare, S3-compatible) at key base/<candidate_id>.png,
    HEAD-checked first so an existing object is reused rather than
    re-uploaded, and durable_url becomes the R2 public URL instead of the
    local path. If R2 env vars are absent, durable_url stays the local path
    and no network calls are made at all (this is the offline/dry-run mode).
    """
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    ARTWORK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARTWORK_CACHE_DIR / f"{candidate_id}.png"

    if not archive_path.exists() or hashlib.sha256(archive_path.read_bytes()).hexdigest() != sha256:
        archive_path.write_bytes(raw_bytes)

    durable_url = str(archive_path)

    r2 = _r2_config()
    if r2 is not None:
        key = f"base/{candidate_id}.png"
        if not _r2_object_exists(key, r2):
            _r2_put_object(key, raw_bytes, r2)
        durable_url = f"{r2['R2_PUBLIC_BASE_URL']}/{key}"

    return {
        "durable_url": durable_url,
        "local_path": str(archive_path),
        "sha256": sha256,
    }


def _r2_config() -> dict | None:
    """All-or-nothing R2 env var gate. Matches config.is_live_mode's style of
    reading straight from os.environ (these are optional, so require_env's
    raise-on-missing doesn't fit - absence means "R2 not configured", not an
    error)."""
    values = {key: os.environ.get(key) for key in R2_ENV_VARS}
    if not all(values.values()):
        return None
    return values


# --- R2 object operations (S3-compatible PUT/HEAD, SigV4-signed) ---

def _r2_object_exists(key: str, r2: dict) -> bool:
    url = f"{r2['R2_ENDPOINT']}/{r2['R2_BUCKET']}/{key}"
    headers = _sigv4_headers("HEAD", url, hashlib.sha256(b"").hexdigest(), r2)
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=30):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def _r2_put_object(key: str, raw_bytes: bytes, r2: dict) -> None:
    url = f"{r2['R2_ENDPOINT']}/{r2['R2_BUCKET']}/{key}"
    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    headers = _sigv4_headers("PUT", url, payload_hash, r2)
    request = urllib.request.Request(url, data=raw_bytes, headers=headers, method="PUT")
    # urlopen raises urllib.error.HTTPError for any non-2xx status - that
    # propagates untouched, which is the "fail loud, don't leave a partial
    # object uncaught" requirement.
    with urllib.request.urlopen(request, timeout=30):
        pass


# --- AWS SigV4 signer (hmac/hashlib only - no boto3/botocore) ---

def _sigv4_headers(method: str, url: str, payload_hash: str, r2: dict) -> dict:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"

    now = datetime.datetime.now(datetime.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    headers_to_sign = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amzdate,
    }

    authorization = sign_request(
        method=method,
        path=path,
        headers=headers_to_sign,
        payload_hash=payload_hash,
        access_key=r2["R2_ACCESS_KEY_ID"],
        secret_key=r2["R2_SECRET_ACCESS_KEY"],
        region=R2_REGION,
        service=R2_SERVICE,
        amzdate=amzdate,
        datestamp=datestamp,
    )["authorization"]

    return {
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amzdate,
        "Authorization": authorization,
    }


def build_canonical_request(method: str, path: str, headers: dict, payload_hash: str) -> tuple:
    """headers: dict of lowercase header name -> value, must include at least
    'host' and 'x-amz-date' (and 'x-amz-content-sha256' for S3). No query
    string support needed - every R2 call here is a plain PUT/HEAD on an
    object key, never a query-string request.

    Returns (canonical_request, signed_headers_str).
    """
    sorted_keys = sorted(headers.keys())
    canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in sorted_keys)
    signed_headers = ";".join(sorted_keys)
    canonical_request = "\n".join([
        method,
        path,
        "",  # canonical query string - always empty here
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    return canonical_request, signed_headers


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(secret_key: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), datestamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "aws4_request")


def sign_request(
    *,
    method: str,
    path: str,
    headers: dict,
    payload_hash: str,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    amzdate: str,
    datestamp: str,
) -> dict:
    """Standard AWS SigV4 signing (canonical request -> string-to-sign ->
    derived signing key -> signature -> Authorization header), per
    https://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
    Returns a dict with every intermediate value so tests can assert on each
    stage independently, plus the final 'authorization' header value.
    """
    canonical_request, signed_headers = build_canonical_request(method, path, headers, payload_hash)
    canonical_request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amzdate,
        credential_scope,
        canonical_request_hash,
    ])

    signing_key = _derive_signing_key(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "canonical_request": canonical_request,
        "canonical_request_hash": canonical_request_hash,
        "string_to_sign": string_to_sign,
        "signature": signature,
        "authorization": authorization,
    }
