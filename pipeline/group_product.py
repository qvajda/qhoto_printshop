import io
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import pipeline.artwork_store as artwork_store
import pipeline.config as config
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.http as http
import pipeline.image_crop as image_crop
import pipeline.mockup_render as mockup_render


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


# Group types whose target aspect ratio genuinely differs from the master's own
# 2:3 ratio (see image_crop.target_ratio_for_group_type - these are the only
# group_type names shaped like WIDTHxHEIGHT). The primary group (8x12/A3/A2/A1)
# is close enough to 2:3 that CLAUDE.md frames it as "a small crop, not a
# re-composition", and live evidence (candidate 39, GL-9) published it with no
# white-bar defect - so it keeps submitting the raw master, uncropped here.
_PRINT_CROP_GROUP_TYPES = {"5x7", "10x24"}


def _group_print_crop(candidate: dict, group_type: str) -> dict:
    """Builds a full-resolution cover-crop of the master for group_type and hosts it
    (persist_group_crop's local archive + optional R2 upload) - so the Gelato print
    submission fills the frame instead of Gelato's own fit/letterbox behavior (the
    10x24 white-bar bug), AND (Task 3) so the self-hosted mockup gallery has a local
    file to render from for this group's own aspect ratio. Returns the full
    persist_group_crop dict (not just durable_url) so both callers can each take the
    field they need - built once per create_or_reuse_group_product call, not twice:
    persist_group_crop's R2 PUT is an unconditional overwrite every call, so a second
    call with identical bytes would be a wasted duplicate network write."""
    local_path = candidate.get("base_image_local_path")
    if not local_path or not Path(local_path).exists():
        raise PrintResolutionError(
            f"Cannot build a {group_type} print crop: base_image_local_path missing "
            f"or unreadable ({local_path!r}). The master must be archived locally "
            f"before a real Gelato create or mockup render for a non-primary group."
        )
    cropped_bytes = image_crop.print_crop_bytes(Path(local_path).read_bytes(), group_type)
    return artwork_store.persist_group_crop(candidate["id"], group_type, cropped_bytes)


def _jittered(interval: float) -> float:
    # +-20% jitter desynchronizes polling so a run isn't a metronome of identical
    # fresh connections (a Cloudflare bot-rate signal). rand=1.0 when interval is 0.
    return interval * random.uniform(0.8, 1.2)


def _image_is_fetchable(url: str) -> bool:
    try:
        # GET, not HEAD: Gelato's S3 preview URLs are SigV4-presigned for GET only -
        # the method is part of the signed canonical request, so HEAD against a
        # GET-signed URL 403s (SignatureDoesNotMatch) regardless of whether the
        # object is actually there (confirmed live 2026-07-19: HEAD 403, GET 200
        # on the same URL). A HEAD-based check can never observe true readiness.
        http.fetch_bytes(url, timeout=10)
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

    # A mockup_failed row whose Gelato product was actually created (gelato_product_id is
    # set) is NOT stale: the create succeeded and only the readiness poll timed out (Gelato
    # image rehosting can lag past the poll window - seconds to >5 min). Reuse that product
    # and just re-poll; deleting + recreating would restart the same slow clock and churn a
    # real Gelato product every retry, which the idempotency constraint forbids. Genuinely
    # stale rows (publish_failed, or a mockup_failed create that never returned a product id)
    # are still deleted + recreated.
    stale_row = conn.execute(
        "SELECT id, gelato_product_id, status FROM group_products WHERE group_id = ? "
        "AND status IN ('mockup_failed', 'publish_failed')",
        (group_id,),
    ).fetchone()
    reuse_group_product_id = None
    reuse_gelato_product_id = None
    if stale_row is not None:
        if stale_row["status"] == "mockup_failed" and stale_row["gelato_product_id"]:
            reuse_group_product_id = stale_row["id"]
            reuse_gelato_product_id = stale_row["gelato_product_id"]
            conn.execute(
                "UPDATE group_products SET status = 'pending', updated_at = ? WHERE id = ?",
                (timestamp, reuse_group_product_id),
            )
            conn.commit()
        else:
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

    if reuse_group_product_id is not None:
        group_product_id = reuse_group_product_id
        gelato_product_id = reuse_gelato_product_id
    else:
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
        group_type = config.get_group_type_for_size(static_config, sizes[0])
        # Built once per call (not per branch below) - see _group_print_crop's
        # docstring for why a second call would be a wasted duplicate R2 PUT.
        crop_result = _group_print_crop(candidate, group_type) if group_type in _PRINT_CROP_GROUP_TYPES else None

        if reuse_group_product_id is None:
            # Non-primary groups (5x7/10x24) are a genuinely different aspect ratio
            # from the master - Gelato's own template fits/letterboxes rather than
            # fills, so a real cover-crop must be hosted before it's submitted. Only
            # matters for a real (non-dry-run) create: dry-run never reads image_url
            # (create_product_from_template's dry_run branch returns before the
            # variant loop).
            image_url = candidate["base_image_url"]
            if crop_result is not None and config.is_live_mode("GELATO"):
                image_url = crop_result["durable_url"]

            response = gelato_client.create_product_from_template(
                template_id,
                [
                    {"template_variant_id": t["template_variant_id"], "image_placeholder_name": t["image_placeholder_name"],
                     "image_url": image_url}
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
            is_dry_run = bool(response.get("_dry_run"))
        else:
            is_dry_run = False

        if not is_dry_run:
            # Gelato's own gallery is never consumed for the storefront (below) - this
            # poll still matters because it's the only signal that Gelato's own print
            # asset actually rehosted and the product is ready to publish/fulfil.
            poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )

        # --- self-hosted mockup gallery (GL-5 task 3) ---
        # The storefront gallery is rendered locally, never sourced from Gelato's
        # product images - no fallback to a Gelato/base image if this fails; any
        # failure here is a real mockup_failed, same as a DPI or Gelato-create error.
        scene_ids = config.get_mockup_templates(static_config, group_type, orientation)
        images = []
        if scene_ids:
            if group_type == "primary":
                # Primary is close enough to the master's own ratio that CLAUDE.md
                # already treats it as "a small crop, not a re-composition" - render
                # straight from the archived master, no crop step.
                render_source_path = candidate.get("base_image_local_path")
                if not render_source_path or not Path(render_source_path).exists():
                    raise PrintResolutionError(
                        f"Cannot render mockups: base_image_local_path missing or "
                        f"unreadable ({render_source_path!r}). The master must be "
                        f"archived locally before mockups can be composited."
                    )
            else:
                render_source_path = crop_result["local_path"]

            art = Image.open(render_source_path).convert("RGB")
            for index, scene_id in enumerate(scene_ids):
                bundle = mockup_render.load_bundle(config.mockup_bundle_dir(group_type, orientation, scene_id))
                rendered = mockup_render.render_scene(art, bundle)
                buf = io.BytesIO()
                rendered.save(buf, format="PNG")
                persisted = artwork_store.persist_mockup_render(group_product_id, index, buf.getvalue())
                image_type = "flat_mockup" if bundle.tag == "flat" else "lifestyle"
                images.append({"fileUrl": persisted["durable_url"], "image_type": image_type})
        # else: no bundles authored yet for this group_type/orientation (5x7, 10x24,
        # primary/landscape today) - a valid, expected zero-image gallery, not an
        # error (Task 2's contract; see docs/superpowers/sdd/gl5-task-3-brief.md).
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    # Idempotent on reuse: a re-polled (previously timed-out) product, or a retried
    # render, may already have a partial gallery from an earlier attempt - clear it
    # before reinserting. scene_ids order is already render/rank order (flat scenes
    # first per Task 2's config), so gallery_order is just the loop index.
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (group_product_id,))
    for order, image in enumerate(images):
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, image["fileUrl"], order, image["image_type"]),
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
