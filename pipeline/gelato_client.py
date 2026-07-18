import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

GELATO_API_BASE = "https://ecommerce.gelatoapis.com/v1"
# Gelato's own preview image host. A live probe (2026-07-17) found a product still
# reports isReadyToPublish=true while one productImages entry echoes back our
# submitted source URL (Replicate's, which expires) instead of Gelato's rehosted
# preview - that entry gets replaced by a real Gelato URL moments later. Callers
# poll on this too, not just isReadyToPublish, to avoid capturing the transient echo.
GELATO_IMAGE_HOST = "gelato-api-live.s3"


class GelatoPlaceholderTemplateError(Exception):
    pass


class GelatoReplicateURLError(Exception):
    pass


class GelatoInvalidImageURLError(Exception):
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
    variants: list,
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

    for variant in variants:
        for label in ("template_variant_id", "image_placeholder_name"):
            value = variant[label]
            if config.is_placeholder(value):
                raise GelatoPlaceholderTemplateError(
                    f"Refusing to create a real Gelato product with a placeholder "
                    f"{label} ({value!r}). Fill in the real value in "
                    f"config/static_config.json before making a live call."
                )
    if config.is_placeholder(template_id):
        raise GelatoPlaceholderTemplateError(
            f"Refusing to create a real Gelato product with a placeholder "
            f"template_id ({template_id!r}). Fill in the real value in "
            f"config/static_config.json before making a live call."
        )

    for variant in variants:
        image_url = variant["image_url"]
        if "replicate.delivery" in image_url:
            raise GelatoReplicateURLError(
                f"Refusing to create a real Gelato product with a replicate.delivery "
                f"image_url ({image_url!r}). Replicate delivery URLs expire; Gelato "
                f"needs a durable, persisted URL (e.g. R2/local artwork store) before "
                f"making a live call."
            )
        if not image_url.startswith("http://") and not image_url.startswith("https://"):
            raise GelatoInvalidImageURLError(
                f"Refusing to create a real Gelato product with a non-http(s) "
                f"image_url ({image_url!r}). Gelato needs a fetchable http(s) URL it "
                f"can GET (e.g. an R2 public URL) - a local filesystem path only "
                f"resolves on this machine and R2 is not configured for this call."
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
                "templateVariantId": variant["template_variant_id"],
                "imagePlaceholders": [
                    {"name": variant["image_placeholder_name"], "fileUrl": variant["image_url"]}
                ],
            }
            for variant in variants
        ],
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=_headers(api_key), method="POST")
    return http.send(request)


def get_etsy_listing_id(product_id: str, *, store_id: str = None, api_key: str = None) -> str | None:
    product = get_product(product_id, store_id=store_id, api_key=api_key)
    return product.get("externalId") or None


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
