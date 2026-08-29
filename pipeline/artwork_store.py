import datetime
import hashlib
import hmac
import os
import sqlite3
import urllib.parse
from pathlib import Path

from pipeline import config
from pipeline import http

ARTWORK_CACHE_DIR = config.artefact_root()

# GL-51b: table, column pairs holding stored artefact paths - one row per DB
# column swept. product_images.image_url is required (never NULL); candidates'
# base_image_local_path is nullable, hence the extra WHERE.
_ARTEFACT_COLUMNS = [
    ("candidates", "base_image_local_path"),
    ("product_images", "image_url"),
]


def sweep_artefacts(db_path) -> dict:
    """Reads every stored artefact path across _ARTEFACT_COLUMNS and reports
    resolvable vs missing vs skipped. Read-only (no writes to db_path), never
    raises on a bad row - a per-row failure lands in "missing" with the
    exception text as its value (GL-46), so the report never silently drops
    a row instead of counting it.

    Resolution goes through resolve_artefact_path: since #200 (GL-51a) stored
    local values are relative to config.artefact_root(), so checking Path(value)
    raw resolves them against the CWD and reports every migrated row missing.
    """
    resolvable = 0
    skipped = 0
    missing = []

    conn = sqlite3.connect(db_path)
    try:
        for table, column in _ARTEFACT_COLUMNS:
            rows = conn.execute(
                f"SELECT id, {column} FROM {table} "
                f"WHERE {column} IS NOT NULL AND {column} != ''"
            ).fetchall()
            for row_id, value in rows:
                try:
                    if value.startswith("http://") or value.startswith("https://"):
                        skipped += 1
                    elif Path(resolve_artefact_path(value)).exists():
                        resolvable += 1
                    else:
                        missing.append({"table": table, "row_id": row_id, "value": value})
                except OSError as exc:
                    missing.append({"table": table, "row_id": row_id, "value": str(exc)})
    finally:
        conn.close()

    return {"resolvable": resolvable, "skipped": skipped, "missing": missing}

# Kept as an alias for existing callers/tests; config.R2_ENV_VARS is now the
# source of truth (see config.is_r2_configured).
R2_ENV_VARS = config.R2_ENV_VARS

R2_REGION = "auto"
R2_SERVICE = "s3"


def _persist_artifact(local_filename: str, r2_key: str, raw_bytes: bytes) -> dict:
    """Shared local-archive + R2-upload logic for a durable artifact. Idempotent
    locally (same sha256 bytes leave the file untouched); the R2 PUT is an
    unconditional overwrite every call (see persist_base_artwork's docstring for
    why - a skip-if-exists check would serve stale bytes after a regeneration)."""
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    ARTWORK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARTWORK_CACHE_DIR / local_filename

    if not archive_path.exists() or hashlib.sha256(archive_path.read_bytes()).hexdigest() != sha256:
        archive_path.write_bytes(raw_bytes)

    # GL-51a (#200): stored relative to ARTWORK_CACHE_DIR and POSIX-separated, so the
    # DB is portable across hosts - resolve_artefact_path re-roots it at read time.
    local_path = archive_path.relative_to(ARTWORK_CACHE_DIR).as_posix()
    durable_url = local_path

    r2 = _r2_config()
    if r2 is not None:
        _r2_put_object(r2_key, raw_bytes, r2)
        durable_url = f"{r2['R2_PUBLIC_BASE_URL']}/{r2_key}"

    return {
        "durable_url": durable_url,
        "local_path": local_path,
        "sha256": sha256,
    }


def resolve_artefact_path(value: str | None) -> str | None:
    """Maps a stored candidates.base_image_local_path / product_images.image_url
    value to a path this host can actually open. An http(s) value (an R2-hosted
    URL) is returned unchanged - callers already branch on scheme before treating
    a value as a local file. An absolute value is returned unchanged too: it is a
    legacy row predating this migration, and survives until
    migrate_gl51_relative_artefact_paths.py rewrites it. Anything else is relative
    and gets joined onto the configured artefact root."""
    if value is None or value.startswith(("http://", "https://")) or Path(value).is_absolute():
        return value
    return str(config.artefact_root() / value)


def persist_base_artwork(candidate_id: int, raw_bytes: bytes) -> dict:
    """Archives a candidate's base artwork bytes locally, keyed by candidate_id.

    Idempotent: if the archive already holds bytes with the same sha256, the
    file is left untouched. A different hash for the same candidate_id (a
    generate-retry) overwrites it - last write wins, no versioning.

    The local write (Task 1) always happens - it's the permanent local backup
    per PRD 5.5. If all R2_* env vars are set (Task 2), the bytes are also
    PUT to R2 (Cloudflare, S3-compatible) at key base/<candidate_id>.png -
    unconditionally, every call, no existence check first. A PUT is an
    idempotent overwrite, so identical bytes re-uploading is just wasted
    bandwidth; the alternative (skip-if-exists) would silently leave stale
    bytes in R2 after a critic-reject regeneration produces new bytes for
    the same candidate_id. If R2 env vars are absent, durable_url stays the
    local path and no network calls are made at all (this is the
    offline/dry-run mode).
    """
    return _persist_artifact(f"{candidate_id}.png", f"base/{candidate_id}.png", raw_bytes)


def persist_group_crop(candidate_id: int, group_type: str, raw_bytes: bytes) -> dict:
    """Archives a group's full-resolution print cover-crop (5x7/10x24 - see
    image_crop.print_crop_bytes), same idempotency semantics as
    persist_base_artwork. Reuses ARTWORK_CACHE_DIR - it's the same durable-artifact
    concern as the base master, just a different derived file."""
    filename = f"{candidate_id}_{group_type}_crop.png"
    return _persist_artifact(filename, f"base/{filename}", raw_bytes)


def persist_mockup_render(group_product_id: int, group_id: int, index: int, raw_bytes: bytes) -> dict:
    """Archives one self-hosted mockup-render composite (GL-5 task 3), same
    idempotency semantics as persist_group_crop. Keyed by group_product_id +
    group_id + its scene index (not candidate_id) so a re-render on retry
    overwrites the same slot instead of accumulating orphan files - mirrors the
    idempotency comment in group_product.py about clearing product_images before
    reinserting. v4.12: group_id is part of the key because one group_products row
    is now shared by up to three groups - without it, the 5x7 group's scene 0 would
    overwrite the primary group's scene 0 file on disk."""
    filename = f"{group_product_id}_{group_id}_mockup_{index}.png"
    return _persist_artifact(filename, f"base/{filename}", raw_bytes)


def _r2_config() -> dict | None:
    """All-or-nothing R2 env var gate (see config.is_r2_configured). Absence
    means "R2 not configured", not an error, so this returns None rather
    than raising like config.require_env would."""
    if not config.is_r2_configured():
        return None
    return {key: os.environ.get(key) for key in config.R2_ENV_VARS}


# --- R2 object operations (S3-compatible PUT, SigV4-signed) ---

def _r2_put_object(key: str, raw_bytes: bytes, r2: dict) -> None:
    url = f"{r2['R2_ENDPOINT']}/{r2['R2_BUCKET']}/{key}"
    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    headers = _sigv4_headers("PUT", url, payload_hash, r2)
    # Route through the shared httpx client (keep-alive, honest UA, 1010 backoff)
    # instead of a fresh urllib bot-fingerprint handshake per candidate against
    # this Cloudflare-fronted endpoint. http.put_bytes raises HTTPError on any
    # non-2xx - fail loud, don't leave a partial object uncaught.
    http.put_bytes(url, raw_bytes, headers)


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
