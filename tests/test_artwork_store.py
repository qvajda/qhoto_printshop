import hashlib
import io
import urllib.error
from unittest.mock import MagicMock, patch

import pipeline.artwork_store as artwork_store


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


def _mock_response():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b""
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_persist_base_artwork_uploads_to_r2_when_object_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"brand new artwork bytes"

    not_found = urllib.error.HTTPError(
        url="https://test-account.r2.cloudflarestorage.com/test-bucket/base/5.png",
        code=404, msg="Not Found", hdrs=None, fp=io.BytesIO(b""),
    )
    calls = []

    def fake_urlopen(request, timeout=30):
        calls.append(request.get_method())
        if request.get_method() == "HEAD":
            raise not_found
        return _mock_response()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = artwork_store.persist_base_artwork(candidate_id=5, raw_bytes=raw)

    assert calls == ["HEAD", "PUT"]
    assert result["durable_url"] == "https://cdn.example.com/base/5.png"
    assert result["local_path"] == str(tmp_path / "5.png")
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "5.png").read_bytes() == raw


def test_persist_base_artwork_reuses_existing_r2_object_without_reuploading(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"already uploaded bytes"

    calls = []

    def fake_urlopen(request, timeout=30):
        calls.append(request.get_method())
        return _mock_response()  # HEAD succeeds -> object exists

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = artwork_store.persist_base_artwork(candidate_id=6, raw_bytes=raw)

    assert calls == ["HEAD"]  # no PUT - reused
    assert result["durable_url"] == "https://cdn.example.com/base/6.png"


def test_persist_base_artwork_raises_on_failed_put(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    raw = b"upload will fail"

    not_found = urllib.error.HTTPError(
        url="https://test-account.r2.cloudflarestorage.com/test-bucket/base/8.png",
        code=404, msg="Not Found", hdrs=None, fp=io.BytesIO(b""),
    )
    put_failure = urllib.error.HTTPError(
        url="https://test-account.r2.cloudflarestorage.com/test-bucket/base/8.png",
        code=500, msg="Internal Server Error", hdrs=None, fp=io.BytesIO(b"boom"),
    )

    def fake_urlopen(request, timeout=30):
        if request.get_method() == "HEAD":
            raise not_found
        raise put_failure

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            artwork_store.persist_base_artwork(candidate_id=8, raw_bytes=raw)
            assert False, "expected HTTPError to propagate"
        except urllib.error.HTTPError as e:
            assert e.code == 500

    # local write still happened even though R2 upload failed
    assert (tmp_path / "8.png").read_bytes() == raw


# --- persist_base_artwork with R2 NOT configured (Task 1 behavior unchanged) ---

def test_persist_base_artwork_stays_local_only_when_r2_env_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    for key in artwork_store.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    raw = b"no r2 configured"

    with patch("urllib.request.urlopen") as mock_urlopen:
        result = artwork_store.persist_base_artwork(candidate_id=9, raw_bytes=raw)

    mock_urlopen.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "9.png")


def test_persist_base_artwork_stays_local_only_when_some_r2_vars_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    _set_r2_env(monkeypatch)
    monkeypatch.delenv("R2_PUBLIC_BASE_URL", raising=False)  # partial config
    raw = b"partial r2 config"

    with patch("urllib.request.urlopen") as mock_urlopen:
        result = artwork_store.persist_base_artwork(candidate_id=10, raw_bytes=raw)

    mock_urlopen.assert_not_called()
    assert result["durable_url"] == str(tmp_path / "10.png")
