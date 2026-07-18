import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import pipeline.config as config
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.http as http
import pipeline.image_crop as image_crop


class GelatoMockupTimeoutError(Exception):
    pass


class EtsyListingSyncTimeoutError(Exception):
    pass


class PrintResolutionError(Exception):
    pass


MIN_PRINT_DPI = 150

# Physical print dimensions (short_edge_in, long_edge_in) per offered size, for the
# pre-create DPI guard only. Gelato enforces its own DPI at product creation; this
# fails loud *before* a live call when the upscaled master can't clear 150 DPI
# (Gelato's stated poster minimum) at a group's largest size (B5). A-series inches
# are the ISO mm sizes converted (A3 297x420mm, A2 420x594mm, A1 594x841mm).
_SIZE_INCHES = {
    "5x7": (5, 7),
    "8x12": (8, 12),
    "A3": (11.69, 16.54),
    "A2": (16.54, 23.39),
    "A1": (23.39, 33.11),
    "10x24": (10, 24),
}


def _assert_print_dpi(sizes: list, local_path) -> None:
    """Refuse a live Gelato create if the archived master resolves below 150 DPI at
    any offered size. Reads pixel dims from the local archive - no network call."""
    if not local_path or not Path(local_path).exists():
        raise PrintResolutionError(
            f"Cannot verify print DPI: base_image_local_path missing or unreadable "
            f"({local_path!r}). The upscaled master must be archived locally before a "
            f"live Gelato create so its print resolution can be checked."
        )
    with Image.open(local_path) as im:
        px_w, px_h = im.size
    px_short, px_long = min(px_w, px_h), max(px_w, px_h)
    worst = None
    for size in sizes:
        if size not in _SIZE_INCHES:
            continue
        short_in, long_in = _SIZE_INCHES[size]
        dpi = min(px_short / short_in, px_long / long_in)
        if worst is None or dpi < worst[1]:
            worst = (size, dpi)
    if worst is not None and worst[1] < MIN_PRINT_DPI:
        raise PrintResolutionError(
            f"Refusing a live Gelato create: master {px_w}x{px_h}px yields only "
            f"{worst[1]:.0f} DPI at size {worst[0]} (min {MIN_PRINT_DPI} for posters). "
            f"Upscale the master further before printing this group."
        )


def _jittered(interval: float) -> float:
    # +-20% jitter desynchronizes polling so a run isn't a metronome of identical
    # fresh connections (a Cloudflare bot-rate signal). rand=1.0 when interval is 0.
    return interval * random.uniform(0.8, 1.2)


def _image_is_fetchable(url: str) -> bool:
    try:
        http.head(url, timeout=10)
        return True
    except Exception:
        # Any failure (non-2xx, connect/timeout) means the object isn't fetchable
        # yet - same broad catch as the old urllib URLError/HTTPError pair.
        return False


def poll_until_ready(product_id: str, *, store_id: str = None, api_key: str = None,
                      poll_interval: float = 10.0, timeout: float = 300.0,
                      sleep_fn=time.sleep, now_fn=time.monotonic) -> dict:
    deadline = now_fn() + timeout
    while True:
        product = gelato_client.get_product(product_id, store_id=store_id, api_key=api_key)
        images = product.get("productImages", [])
        # Gelato can report isReadyToPublish=true and a gelato-hosted fileUrl before the
        # underlying S3 object is actually fetchable (live probe, 2026-07-17) - a real GET
        # is the only way to catch that race, a domain-name check alone isn't enough.
        images_rehosted = all(
            gelato_client.GELATO_IMAGE_HOST in image.get("fileUrl", "") and _image_is_fetchable(image["fileUrl"])
            for image in images
        )
        if product.get("isReadyToPublish") and images_rehosted:
            return product
        if now_fn() >= deadline:
            raise GelatoMockupTimeoutError(
                f"Gelato product {product_id} did not become ready to publish within "
                f"{timeout:.0f}s. isReadyToPublish flips in ~9s, but a live probe "
                f"(2026-07-17) saw actual image rehosting lag anywhere from seconds to "
                f"~5 minutes - this likely indicates a Gelato-side delay or outage, not a "
                f"pipeline bug."
            )
        sleep_fn(_jittered(poll_interval))


def resolve_etsy_listing_id(product_id: str, *, store_id: str = None, api_key: str = None,
                             poll_interval: float = 30.0, timeout: float = 1200.0,
                             sleep_fn=time.sleep, now_fn=time.monotonic) -> str:
    deadline = now_fn() + timeout
    while True:
        listing_id = gelato_client.get_etsy_listing_id(product_id, store_id=store_id, api_key=api_key)
        if listing_id is not None:
            return listing_id
        if now_fn() >= deadline:
            raise EtsyListingSyncTimeoutError(
                f"Gelato product {product_id}'s externalId (Etsy listing_id) did not populate "
                f"within {timeout:.0f}s. Live probe (2026-07-16) observed ~8 min sync lag - "
                f"this likely means Gelato's async Etsy sync is stalled or failed, not a "
                f"pipeline bug."
            )
        sleep_fn(_jittered(poll_interval))


def _primary_flat_image_url(conn, group_id: int, *, store_id: str = None, api_key: str = None) -> str | None:
    row = conn.execute(
        """
        SELECT gp.gelato_product_id FROM group_products gp
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = (SELECT candidate_id FROM groups WHERE id = ?)
          AND g.group_type = 'primary' AND gp.status IN ('created', 'published')
        ORDER BY gp.id DESC LIMIT 1
        """,
        (group_id,),
    ).fetchone()
    if row is None or not row["gelato_product_id"]:
        return None
    product = gelato_client.get_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
    images = product.get("productImages") or []
    if not images:
        return None
    primary_image = next((img for img in images if img.get("isPrimary")), images[0])
    return primary_image.get("fileUrl")


def create_or_reuse_group_product(conn, group_id: int, sizes: list, candidate: dict, static_config: dict,
                                   title: str, orientation: str = "portrait", *, store_id: str = None,
                                   api_key: str = None, poll_interval: float = 10.0,
                                   poll_timeout: float = 300.0, now=None) -> dict:
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    live_row = conn.execute(
        "SELECT id, gelato_product_id FROM group_products WHERE group_id = ? AND status IN ('created', 'published')",
        (group_id,),
    ).fetchone()
    if live_row is not None:
        existing_sizes = {
            row["size"] for row in conn.execute(
                "SELECT size FROM group_product_variants WHERE group_product_id = ?", (live_row["id"],)
            ).fetchall()
        }
        if existing_sizes == set(sizes):
            return {"group_product_id": live_row["id"], "gelato_product_id": live_row["gelato_product_id"]}
        # Requested sizes changed (e.g. primary_mockup.py's 8x12-only row now needs the full
        # 4-size fan-out on approval) - the existing Gelato product no longer matches, so it's
        # stale in the same sense as a mockup_failed/publish_failed row: delete it and fall
        # through to a fresh create with the newly requested variant set.
        stale_row = live_row
        if stale_row["gelato_product_id"]:
            gelato_client.delete_product(stale_row["gelato_product_id"], store_id=store_id, api_key=api_key)
        conn.execute(
            "DELETE FROM group_product_variants WHERE group_product_id = ?", (stale_row["id"],),
        )
        conn.execute(
            "UPDATE group_products SET status = 'deleted', updated_at = ? WHERE id = ?",
            (timestamp, stale_row["id"]),
        )
        conn.commit()

    stale_row = conn.execute(
        "SELECT id, gelato_product_id FROM group_products WHERE group_id = ? "
        "AND status IN ('mockup_failed', 'publish_failed')",
        (group_id,),
    ).fetchone()
    if stale_row is not None:
        if stale_row["gelato_product_id"]:
            gelato_client.delete_product(stale_row["gelato_product_id"], store_id=store_id, api_key=api_key)
        conn.execute(
            "DELETE FROM group_product_variants WHERE group_product_id = ?", (stale_row["id"],),
        )
        conn.execute(
            "UPDATE group_products SET status = 'deleted', updated_at = ? WHERE id = ?",
            (timestamp, stale_row["id"]),
        )
        conn.commit()

    # DPI guard fires only on real creates (dry-run/test masters are synthetic and
    # have no local archive). Placed before any DB write so a too-small master fails
    # fast without orphaning a group_products row.
    if config.is_live_mode("GELATO"):
        _assert_print_dpi(sizes, candidate.get("base_image_local_path"))

    templates = [config.get_template_variant(static_config, size, orientation) for size in sizes]
    template_id = templates[0]["template_id"]

    cursor = conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'pending', ?, ?)",
        (group_id, template_id, timestamp, timestamp),
    )
    conn.commit()
    group_product_id = cursor.lastrowid

    for size, template in zip(sizes, templates):
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (group_product_id, size, orientation, template["template_variant_id"],
             static_config["prices_eur"][size], timestamp),
        )
    conn.commit()

    try:
        response = gelato_client.create_product_from_template(
            template_id,
            [
                {"template_variant_id": t["template_variant_id"], "image_placeholder_name": t["image_placeholder_name"],
                 "image_url": candidate["base_image_url"]}
                for t in templates
            ],
            title, store_id=store_id, api_key=api_key,
        )
        gelato_product_id = response["id"]
        conn.execute(
            "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
            (gelato_product_id, timestamp, group_product_id),
        )
        conn.commit()

        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or candidate["base_image_url"], "isPrimary": True}]
        else:
            product = poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
            if not images:
                # ponytail: Gelato never renders a mockup preview for single-variant
                # products (its primaryPreviewProductVariantKey defaults to a larger
                # size not present in a 1-variant product, confirmed live 2026-07-17) -
                # fall back to a flat image so critic review + digest gallery aren't
                # stuck with 0 images. Prefer the primary group's already-rehosted
                # Gelato image (re-fetched live, so it's never stale) over the raw
                # candidate.base_image_url - Replicate's delivery links expire within
                # a couple hours (confirmed live 2026-07-17), well within the time a
                # design can sit waiting for admin approval.
                fallback_url = (
                    _primary_flat_image_url(conn, group_id, store_id=store_id, api_key=api_key)
                    or candidate["base_image_url"]
                )
                if len(sizes) == 1:
                    # ponytail: the primary group's preview is composed for its own
                    # (portrait) aspect ratio - showing it uncropped to a 5x7/10x24
                    # group's critic review makes any composition look wrong (subject
                    # crammed in a corner). Gelato itself cover-crops correctly at
                    # print time for the physical poster; this crop is only to make
                    # the *review/digest preview* honestly represent that group's
                    # aspect ratio (spec: "their own cover-crop... a real crop that
                    # fills the frame").
                    fallback_url = image_crop.crop_for_group(fallback_url, sizes[0], group_product_id)
                images = [{"fileUrl": fallback_url, "isPrimary": True}]
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
    for order, image in enumerate(ordered_images):
        image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, image.get("fileUrl"), order, image_type),
        )

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()

    return {"group_product_id": group_product_id, "gelato_product_id": gelato_product_id}


def patch_etsy_listing(conn, group_product_id: int, group_type: str, listing_text: dict, static_config: dict, *,
                        shop_id: str = None, etsy_api_key: str = None, etsy_api_secret: str = None,
                        etsy_access_token: str = None, dry_run: bool = None, now=None) -> str:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")

    gp_row = conn.execute(
        "SELECT gelato_product_id, etsy_listing_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if gp_row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")

    listing_id = gp_row["etsy_listing_id"]
    if listing_id is None:
        # ponytail: resolving listing_id is a Gelato-side lookup (externalId sync), not an
        # Etsy write, so it's gated on Gelato's own liveness (is a real product) - not on
        # this function's dry_run, which only covers the Etsy update_listing/
        # update_listing_inventory calls below. gelato_client.get_product has no dry_run of
        # its own and always makes a real HTTP call, so calling it against the fake
        # "DRY_RUN_PRODUCT_ID" from a dry-run create would crash or hang.
        if config.is_live_mode("GELATO"):
            listing_id = resolve_etsy_listing_id(gp_row["gelato_product_id"], api_key=None)
        else:
            listing_id = "DRY_RUN_ETSY_LISTING_ID"
        conn.execute(
            "UPDATE group_products SET etsy_listing_id = ?, updated_at = ? WHERE id = ?",
            (listing_id, timestamp, group_product_id),
        )
        conn.commit()

    shipping_profile_id = config.get_shipping_profile_id(static_config, group_type)
    listing_data = {
        "title": listing_text["title"],
        "description": listing_text["description"],
        "tags": json.loads(listing_text["tags"]),
        "taxonomy_id": int(listing_text["taxonomy_id"]),
        "who_made": listing_text["who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "shop_section_id": static_config["etsy_shop_section_id"],
        "production_partner_ids": json.loads(listing_text["production_partner_ids"]),
        "shipping_profile_id": shipping_profile_id,
    }
    etsy_client.update_listing(
        shop_id, listing_id, listing_data, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?", (group_product_id,)
    ).fetchall()
    size_to_price = {row["size"]: row["price_eur"] for row in variant_rows}
    etsy_client.update_listing_inventory(
        shop_id, listing_id, size_to_price, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    conn.execute(
        "UPDATE group_products SET status = 'published', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()
    return listing_id
