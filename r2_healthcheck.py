"""One-time: verify live R2 access matches the durable-artwork contract
(docs/r2-setup-guide.md section 7). PUTs a test object, GETs it back via the
public base URL, and confirms the bucket root doesn't return a listing.
"""
import sys
import urllib.error
import urllib.request

from pipeline import artwork_store, config

HEALTHCHECK_KEY = "base/_healthcheck.png"
HEALTHCHECK_BYTES = b"qhoto-r2-healthcheck"
# Cloudflare's default bot protection 403s urllib's default "Python-urllib/x.y"
# User-Agent on the public r2.dev domain - a real browser UA passes fine.
USER_AGENT = "Mozilla/5.0 (compatible; qhoto-printshop-pipeline/1.0)"


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=30)


def main():
    config.load_env()
    if not config.is_r2_configured():
        print("R2 not configured (missing R2_* env vars) - nothing to check.")
        return 1

    r2 = artwork_store._r2_config()

    print(f"PUT {HEALTHCHECK_KEY} ...")
    artwork_store._r2_put_object(HEALTHCHECK_KEY, HEALTHCHECK_BYTES, r2)
    print("  OK")

    public_url = f"{r2['R2_PUBLIC_BASE_URL']}/{HEALTHCHECK_KEY}"
    print(f"GET {public_url} ...")
    with _get(public_url) as response:
        status = response.status
        body = response.read()
    if status != 200 or body != HEALTHCHECK_BYTES:
        print(f"  FAILED: status={status}, bytes_match={body == HEALTHCHECK_BYTES}")
        return 1
    print(f"  OK (200, {len(body)} bytes match)")

    root_url = f"{r2['R2_PUBLIC_BASE_URL']}/"
    print(f"GET {root_url} (expecting no listing) ...")
    try:
        with _get(root_url) as response:
            root_status = response.status
            root_body = response.read()
    except urllib.error.HTTPError as e:
        root_status = e.code
        root_body = e.read()
    is_listing = b"<ListBucketResult" in root_body or b"<Contents>" in root_body
    if is_listing:
        print(f"  FAILED: bucket root returned a listing (status={root_status})")
        return 1
    print(f"  OK (status={root_status}, no listing markup)")

    print("\nAll checks passed: R2 is fetchable by key, and the bucket isn't listable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
