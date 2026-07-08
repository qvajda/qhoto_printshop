import json
import urllib.request
import uuid

import pipeline.config as config
import pipeline.http as http

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"


def _headers(api_key: str, access_token: str) -> dict:
    return {"x-api-key": api_key, "Authorization": f"Bearer {access_token}"}


def get_seller_taxonomy_nodes(*, api_key: str = None, access_token: str = None) -> list:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/seller-taxonomy/nodes"
    request = urllib.request.Request(url, headers=_headers(api_key, access_token), method="GET")
    result = http.send(request)
    return result["results"]


def create_draft_listing(
    shop_id: str, listing_data: dict, *, api_key: str = None, access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": "DRY_RUN_LISTING_ID", "state": "draft", "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings"
    body = json.dumps(listing_data).encode("utf-8")
    headers = _headers(api_key, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)


def upload_listing_image(
    shop_id: str,
    listing_id: str,
    image_bytes: bytes,
    *,
    api_key: str = None,
    access_token: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_image_id": "DRY_RUN_IMAGE_ID", "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}/images"

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="image.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = _headers(api_key, access_token)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)
