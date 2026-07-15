import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

GELATO_API_BASE = "https://ecommerce.gelatoapis.com/v1"


class GelatoPlaceholderTemplateError(Exception):
    pass


def _headers(api_key: str) -> dict:
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; qhoto-printshop-pipeline/1.0)",
    }


def get_template(template_id: str, *, api_key: str = None) -> dict:
    api_key = api_key or config.require_env("GELATO_API_KEY")
    url = f"{GELATO_API_BASE}/templates/{template_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    return http.send(request)


def get_product(product_id: str, *, store_id: str = None, api_key: str = None) -> dict:
    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products/{product_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    return http.send(request)


def create_product_from_template(
    template_id: str,
    template_variant_id: str,
    image_placeholder_name: str,
    image_url: str,
    title: str,
    *,
    store_id: str = None,
    api_key: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return {
            "id": "DRY_RUN_PRODUCT_ID",
            "storeId": store_id or "DRY_RUN_STORE_ID",
            "title": title,
            "status": "created",
            "previewUrl": None,
            "productImages": [],
            "isReadyToPublish": False,
            "_dry_run": True,
        }

    for label, value in (
        ("template_id", template_id),
        ("template_variant_id", template_variant_id),
        ("image_placeholder_name", image_placeholder_name),
    ):
        if config.is_placeholder(value):
            raise GelatoPlaceholderTemplateError(
                f"Refusing to create a real Gelato product with a placeholder "
                f"{label} ({value!r}). Fill in the real value in "
                f"config/static_config.json before making a live call."
            )

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products:create-from-template"
    body = json.dumps({
        "templateId": template_id,
        "title": title,
        "isVisibleInTheOnlineStore": False,
        "variants": [
            {
                "templateVariantId": template_variant_id,
                "imagePlaceholders": [
                    {"name": image_placeholder_name, "fileUrl": image_url}
                ],
            }
        ],
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=_headers(api_key), method="POST")
    return http.send(request)


def delete_product(product_id: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> None:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products/{product_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="DELETE")
    http.send(request)
