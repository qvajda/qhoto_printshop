import json
import urllib.parse
import urllib.request
import uuid

import pipeline.config as config
import pipeline.etsy_auth as etsy_auth
import pipeline.http as http

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"


def _headers(api_key: str, api_secret: str, access_token: str = None) -> dict:
    headers = {"x-api-key": f"{api_key}:{api_secret}"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _call_with_refresh(build_request, access_token: str):
    """Sends build_request(access_token); on a 401, refreshes the Etsy access
    token once and retries with the new token. Never retries more than once -
    a refresh that still 401s means something other than an expired token, so
    it raises rather than looping."""
    try:
        return http.send(build_request(access_token))
    except http.HTTPError as exc:
        if exc.status_code != 401:
            raise
        new_access_token = etsy_auth.refresh()["access_token"]
        return http.send(build_request(new_access_token))


def get_seller_taxonomy_nodes(*, api_key: str = None, api_secret: str = None, access_token: str = None) -> list:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/seller-taxonomy/nodes"

    def _build(token):
        return urllib.request.Request(url, headers=_headers(api_key, api_secret, token), method="GET")

    result = _call_with_refresh(_build, access_token)
    return result["results"]


def create_draft_listing(
    shop_id: str, listing_data: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": "DRY_RUN_LISTING_ID", "state": "draft", "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings"
    body = json.dumps(listing_data).encode("utf-8")
    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)


def upload_listing_image(
    shop_id: str,
    listing_id: str,
    image_bytes: bytes,
    *,
    api_key: str = None,
    api_secret: str = None,
    access_token: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_image_id": "DRY_RUN_IMAGE_ID", "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}/images"

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="image.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    def _build(token):
        headers = _headers(api_key, api_secret, token)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        return urllib.request.Request(url, data=body, headers=headers, method="POST")

    return _call_with_refresh(_build, access_token)


def update_listing_state(
    shop_id: str, listing_id: str, state: str, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    # DELIBERATELY UNWIRED. Nothing in the pipeline calls this, by design (B1).
    # Gelato syncs every listing as an Etsy *draft* (isVisibleInTheOnlineStore=False,
    # confirmed live 2026-07-18) and the pipeline keeps it that way: Etsy charges
    # $0.20 per listing activation, so activation is a manual, per-listing dashboard
    # decision by the owner, not an automated step. This function exists for a future
    # production go-live decision; wiring it in is a deliberate non-feature until then.
    # See test_patch_etsy_listing_never_activates_a_listing for the guard.
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": listing_id, "state": state, "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}"
    body = json.dumps({"state": state}).encode("utf-8")

    def _build(token):
        headers = _headers(api_key, api_secret, token)
        headers["Content-Type"] = "application/json"
        return urllib.request.Request(url, data=body, headers=headers, method="PATCH")

    return _call_with_refresh(_build, access_token)


def update_listing(
    shop_id: str, listing_id: str, listing_data: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": listing_id, "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}"
    body = json.dumps(listing_data).encode("utf-8")

    def _build(token):
        headers = _headers(api_key, api_secret, token)
        headers["Content-Type"] = "application/json"
        return urllib.request.Request(url, data=body, headers=headers, method="PATCH")

    return _call_with_refresh(_build, access_token)


def get_listing_inventory(
    shop_id: str, listing_id: str, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"products": [], "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/listings/{listing_id}/inventory"

    def _build(token):
        return urllib.request.Request(url, headers=_headers(api_key, api_secret, token), method="GET")

    return _call_with_refresh(_build, access_token)


_INVENTORY_READONLY_PRODUCT_FIELDS = ("product_id", "is_deleted")
_INVENTORY_READONLY_OFFERING_FIELDS = ("offering_id", "is_deleted")
_INVENTORY_READONLY_PROPERTY_VALUE_FIELDS = ("scale_name",)


def update_listing_inventory(
    shop_id: str, listing_id: str, size_to_price: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    inventory = get_listing_inventory(
        shop_id, listing_id, api_key=api_key, api_secret=api_secret,
        access_token=access_token, dry_run=dry_run,
    )
    if dry_run:
        return {"products": [], "_dry_run": True}

    # A single-size group has no Etsy variation property at all (Gelato only creates one
    # when there's more than one size), so property_values is empty - the single product
    # unambiguously IS that one size, no name-matching needed or possible.
    single_size_no_variation = (
        len(size_to_price) == 1 and len(inventory["products"]) == 1
        and not inventory["products"][0]["property_values"]
    )

    matched_sizes = set()
    products = []
    for product in inventory["products"]:
        matched_size = None
        if single_size_no_variation:
            matched_size = next(iter(size_to_price))
        for prop in product["property_values"]:
            for value in prop["values"]:
                for size in size_to_price:
                    if size.lower() in value.lower():
                        matched_size = size
        clean_product = {k: v for k, v in product.items() if k not in _INVENTORY_READONLY_PRODUCT_FIELDS}
        clean_product["offerings"] = [
            {k: v for k, v in offering.items() if k not in _INVENTORY_READONLY_OFFERING_FIELDS}
            for offering in product["offerings"]
        ]
        clean_product["property_values"] = [
            {k: v for k, v in prop.items() if k not in _INVENTORY_READONLY_PROPERTY_VALUE_FIELDS}
            for prop in product["property_values"]
        ]
        if matched_size is not None:
            matched_sizes.add(matched_size)
            for offering in clean_product["offerings"]:
                offering["price"] = size_to_price[matched_size]
        products.append(clean_product)

    missing = set(size_to_price) - matched_sizes
    if missing:
        raise ValueError(
            f"update_listing_inventory: no inventory product matched size(s) {sorted(missing)} "
            f"for listing {listing_id} — refusing to silently drop a size's price."
        )

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/listings/{listing_id}/inventory"
    body = json.dumps({
        "products": products,
        "price_on_property": inventory.get("price_on_property", []),
        "quantity_on_property": inventory.get("quantity_on_property", []),
        "sku_on_property": inventory.get("sku_on_property", []),
    }).encode("utf-8")

    def _build(token):
        headers = _headers(api_key, api_secret, token)
        headers["Content-Type"] = "application/json"
        return urllib.request.Request(url, data=body, headers=headers, method="PUT")

    return _call_with_refresh(_build, access_token)


def find_all_listings_active(
    keywords: str,
    *,
    limit: int = None,
    offset: int = None,
    sort_on: str = None,
    sort_order: str = None,
    min_price: float = None,
    max_price: float = None,
    taxonomy_id: str = None,
    shop_location: str = None,
    is_safe: bool = None,
    currency: str = None,
    buyer_country: str = None,
    api_key: str = None,
    api_secret: str = None,
) -> dict:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")

    params = {"keywords": keywords}
    optional_params = {
        "limit": limit, "offset": offset, "sort_on": sort_on, "sort_order": sort_order,
        "min_price": min_price, "max_price": max_price, "taxonomy_id": taxonomy_id,
        "shop_location": shop_location, "is_safe": is_safe, "currency": currency,
        "buyer_country": buyer_country,
    }
    for key, value in optional_params.items():
        if value is not None:
            params[key] = value

    query = urllib.parse.urlencode(params)
    url = f"{ETSY_API_BASE}/listings/active?{query}"
    request = urllib.request.Request(url, headers=_headers(api_key, api_secret), method="GET")
    return http.send(request)
