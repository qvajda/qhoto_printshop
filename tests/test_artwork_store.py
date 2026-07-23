import hashlib
from unittest.mock import MagicMock, patch

import pipeline.artwork_store as artwork_store
import pipeline.http as http


def test_persist_base_artwork_writes_file_and_returns_correct_hash_and_path(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    raw = b"fake png bytes"

    result = artwork_store.persist_base_artwork(candidate_id=42, raw_bytes=raw)

    expected_path = tmp_path / "42.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["local_path"] == str(expected_path)


def test_persist_base_artwork_is_idempotent_when_bytes_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    raw = b"same bytes every time"

    artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=raw)
    archive_path = tmp_path / "7.png"
    first_mtime = archive_path.stat().st_mtime_ns

    result = artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=raw)

    assert archive_path.stat().st_mtime_ns == first_mtime
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()


def test_persist_base_artwork_overwrites_when_bytes_differ_for_same_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    archive_path = tmp_path / "7.png"

    artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=b"first generate attempt")
    result = artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=b"retry produced new bytes")

    assert archive_path.read_bytes() == b"retry produced new bytes"
    assert result["sha256"] == hashlib.sha256(b"retry produced new bytes").hexdigest()


def test_persist_base_artwork_return_shape_has_expected_keys_and_types(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    result = artwork_store.persist_base_artwork(candidate_id=99, raw_bytes=b"shape check")

    assert isinstance(result["durable_url"], str)
    assert isinstance(result["local_path"], str)
    assert isinstance(result["sha256"], str)
    assert len(result["sha256"]) == 64


# --- SigV4 signer: fixed test vector ---
#
# Derived from AWS's own published SigV4 worked example ("GET Object" with a
# Range header), documented at
# https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
# (also mirrored in the aws-sig-v4-test-suite). Verified independently by
# hand-computing canonical request -> hash -> string-to-sign -> derived
# signing key -> signature with a standalone hmac/hashlib script (not this
# module's code) before pinning the expected values below - see
# .superpowers/sdd/artwork-task-2-report.md for the derivation transcript.
AWS_EXAMPLE_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_EXAMPLE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_EXAMPLE_EMPTY_PAYLOAD_HASH = hashlib.sha256(b"").hexdigest()

EXPECTED_CANONICAL_REQUEST = (
    "GET\n"
    "/test.txt\n"
    "\n"
    "host:examplebucket.s3.amazonaws.com\n"
    "range:bytes=0-9\n"
    f"x-amz-content-sha256:{AWS_EXAMPLE_EMPTY_PAYLOAD_HASH}\n"
    "x-amz-date:20130524T000000Z\n"
    "\n"
    "host;range;x-amz-content-sha256;x-amz-date\n"
    f"{AWS_EXAMPLE_EMPTY_PAYLOAD_HASH}"
)
EXPECTED_CANONICAL_REQUEST_HASH = "7344ae5b7ee6c3e7e6b0fe0640412a37625d1fbfff95c48bbb2dc43964946972"
EXPECTED_STRING_TO_SIGN = (
    "AWS4-HMAC-SHA256\n"
    "20130524T000000Z\n"
    "20130524/us-east-1/s3/aws4_request\n"
    f"{EXPECTED_CANONICAL_REQUEST_HASH}"
)
EXPECTED_SIGNATURE = "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"


def test_sigv4_canonical_request_matches_aws_published_example():
    headers = {
        "host": "examplebucket.s3.amazonaws.com",
        "range": "bytes=0-9",
        "x-amz-content-sha256": AWS_EXAMPLE_EMPTY_PAYLOAD_HASH,
        "x-amz-date": "20130524T000000Z",
    }

    canonical_request, signed_headers = artwork_store.build_canonical_request(
        "GET", "/test.txt", headers, AWS_EXAMPLE_EMPTY_PAYLOAD_HASH
    )

    assert canonical_request == EXPECTED_CANONICAL_REQUEST
    assert signed_headers == "host;range;x-amz-content-sha256;x-amz-date"


def test_sigv4_sign_request_matches_aws_published_example():
    headers = {
        "host": "examplebucket.s3.amazonaws.com",
        "range": "bytes=0-9",
        "x-amz-content-sha256": AWS_EXAMPLE_EMPTY_PAYLOAD_HASH,
        "x-amz-date": "20130524T000000Z",
    }

    result = artwork_store.sign_request(
        method="GET",
        path="/test.txt",
        headers=headers,
        payload_hash=AWS_EXAMPLE_EMPTY_PAYLOAD_HASH,
        access_key=AWS_EXAMPLE_ACCESS_KEY,
        secret_key=AWS_EXAMPLE_SECRET_KEY,
        region="us-east-1",
        service="s3",
        amzdate="20130524T000000Z",
        datestamp="20130524",
    )

    assert result["canonical_request"] == EXPECTED_CANONICAL_REQUEST
    assert result["canonical_request_hash"] == EXPECTED_CANONICAL_REQUEST_HASH
    assert result["string_to_sign"] == EXPECTED_STRING_TO_SIGN
    assert result["signature"] == EXPECTED_SIGNATURE
    assert (
        result["authorization"]
        == "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        f"Signature={EXPECTED_SIGNATURE}"
    )


# --- persist_base_artwork with R2 configured ---

R2_ENV = {
    "R2_ACCOUNT_ID": "test-account",
    "R2_ACCESS_KEY_ID": "test-access-key",
    "R2_SECRET_ACCESS_KEY": "test-secret-key",
    "R2_BUCKET": "test-bucket",
    "R2_ENDPOINT": "https://test-account.r2.cloudflarestorage.com",
    "R2_PUBLIC_BASE_URL": "https://cdn.example.com",
}


def _set_r2_env(monkeypatch):
    for key, value in R2_ENV.items():
        monkeypatch.setenv(key, value)


def test_persist_base_artwork_uploads_to_r2_unconditionally(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"brand new artwork bytes"

    calls = []

    def fake_put(url, data, headers, **kwargs):
        calls.append((url, data, headers))
        return MagicMock()

    with patch("pipeline.artwork_store.http.put_bytes", side_effect=fake_put):
        result = artwork_store.persist_base_artwork(candidate_id=5, raw_bytes=raw)

    assert len(calls) == 1  # exactly one PUT, no HEAD/existence check
    url, data, headers = calls[0]
    assert url == "https://test-account.r2.cloudflarestorage.com/test-bucket/base/5.png"
    assert data == raw
    # SigV4 headers pass through untouched to the shared client.
    assert headers["x-amz-content-sha256"] == hashlib.sha256(raw).hexdigest()
    assert "x-amz-date" in headers
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256")
    assert result["durable_url"] == "https://cdn.example.com/base/5.png"
    assert result["local_path"] == str(tmp_path / "5.png")
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "5.png").read_bytes() == raw


def test_persist_base_artwork_reuploads_to_r2_when_bytes_differ_for_same_candidate(tmp_path, monkeypatch):
    # Regression test for the stale-R2-artwork bug: a critic-reject
    # regeneration produces new bytes for the SAME candidate_id. The old
    # HEAD-before-PUT skip-if-exists logic would find the object already
    # there and never re-upload, leaving R2 (Gelato's fetch source) serving
    # the rejected artwork. This must fail against that old code and pass
    # against the always-PUT fix.
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)

    put_bodies = []

    def fake_put(url, data, headers, **kwargs):
        put_bodies.append(data)
        return MagicMock()

    with patch("pipeline.artwork_store.http.put_bytes", side_effect=fake_put):
        artwork_store.persist_base_artwork(candidate_id=6, raw_bytes=b"first attempt bytes")
        result = artwork_store.persist_base_artwork(candidate_id=6, raw_bytes=b"regenerated bytes")

    assert put_bodies == [b"first attempt bytes", b"regenerated bytes"]
    assert result["durable_url"] == "https://cdn.example.com/base/6.png"
    assert result["sha256"] == hashlib.sha256(b"regenerated bytes").hexdigest()


def test_persist_base_artwork_raises_on_failed_put(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"upload will fail"

    put_failure = http.HTTPError(500, "Internal Server Error")

    with patch("pipeline.artwork_store.http.put_bytes", side_effect=put_failure):
        try:
            artwork_store.persist_base_artwork(candidate_id=8, raw_bytes=raw)
            assert False, "expected HTTPError to propagate"
        except http.HTTPError as e:
            assert e.status_code == 500

    # local write still happened even though R2 upload failed
    assert (tmp_path / "8.png").read_bytes() == raw


# --- persist_group_crop (GL-14: full-res print crop hosting) ---

def test_persist_group_crop_uploads_to_r2_and_returns_durable_url(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"cropped 10x24 print bytes"

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_group_crop(39, "10x24", raw)

    mock_put.assert_called_once()
    put_url = mock_put.call_args[0][0]
    assert put_url == "https://test-account.r2.cloudflarestorage.com/test-bucket/base/39_10x24_crop.png"
    assert result["durable_url"] == "https://cdn.example.com/base/39_10x24_crop.png"
    assert (tmp_path / "39_10x24_crop.png").read_bytes() == raw


def test_persist_group_crop_stays_local_only_when_r2_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    for key in artwork_store.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_group_crop(39, "5x7", b"crop bytes")

    mock_put.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "39_5x7_crop.png")


# --- persist_mockup_render (GL-5 task 3: self-hosted mockup gallery) ---

def test_persist_mockup_render_uploads_to_r2_and_returns_durable_url(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"rendered mockup composite bytes"

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_mockup_render(7, 0, raw)

    mock_put.assert_called_once()
    put_url = mock_put.call_args[0][0]
    assert put_url == "https://test-account.r2.cloudflarestorage.com/test-bucket/base/7_mockup_0.png"
    assert result["durable_url"] == "https://cdn.example.com/base/7_mockup_0.png"
    assert (tmp_path / "7_mockup_0.png").read_bytes() == raw


def test_persist_mockup_render_stays_local_only_when_r2_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    for key in artwork_store.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_mockup_render(7, 2, b"scene bytes")

    mock_put.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "7_mockup_2.png")


def test_persist_mockup_render_idempotent_on_same_bytes_overwrites_on_different(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    for key in artwork_store.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    first = artwork_store.persist_mockup_render(3, 1, b"scene one")
    mtime_after_first = (tmp_path / "3_mockup_1.png").stat().st_mtime_ns

    # Same bytes, same slot - file left untouched (idempotent).
    same = artwork_store.persist_mockup_render(3, 1, b"scene one")
    assert same["sha256"] == first["sha256"]
    assert (tmp_path / "3_mockup_1.png").stat().st_mtime_ns == mtime_after_first

    # A retry re-render with different bytes for the same slot overwrites, not
    # accumulates - this is the whole point of keying by group_product_id+index.
    different = artwork_store.persist_mockup_render(3, 1, b"scene one RETRIED")
    assert different["sha256"] != first["sha256"]
    assert (tmp_path / "3_mockup_1.png").read_bytes() == b"scene one RETRIED"


# --- persist_base_artwork with R2 NOT configured (Task 1 behavior unchanged) ---

def test_persist_base_artwork_stays_local_only_when_r2_env_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    for key in artwork_store.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    raw = b"no r2 configured"

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_base_artwork(candidate_id=9, raw_bytes=raw)

    mock_put.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "9.png")


def test_persist_base_artwork_stays_local_only_when_some_r2_vars_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    monkeypatch.delenv("R2_PUBLIC_BASE_URL", raising=False)  # partial config
    raw = b"partial r2 config"

    with patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        result = artwork_store.persist_base_artwork(candidate_id=10, raw_bytes=raw)

    mock_put.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "10.png")


def test_no_urllib_urlopen_remains_in_pipeline():
    # H2 regression: the R2 PUT was the last raw urllib.request.urlopen in the
    # hot path (a fresh bot-fingerprint handshake per candidate to a Cloudflare
    # endpoint). Guard against it - or any sibling - creeping back into pipeline/.
    import pathlib
    pipeline_dir = pathlib.Path(artwork_store.__file__).resolve().parent
    offenders = [
        str(py) for py in pipeline_dir.glob("*.py")
        if "urllib.request.urlopen" in py.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"raw urlopen resurfaced in pipeline/: {offenders}"
