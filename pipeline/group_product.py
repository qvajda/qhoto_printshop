import io
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import pipeline.artwork_store as artwork_store
import pipeline.compliance_draft as compliance_draft
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


class SharedProductVariantError(Exception):
    """Raised when the candidate's already-created Gelato product does not carry the
    size set the caller is asking for. Under v4.12 the product/listing belongs to the
    candidate and is created ONCE with every validated size (D1); GL-22a Q2 proved
    there is no API path to add a variant afterwards, and deleting + recreating would
    destroy sizes another group already published. So a mismatch here is a bug or a
    hand-edited DB, not something to route around - it fails loud.

    GL-58: `permanent` is read by every stage's per-item handler (the GL-54 shape) and
    means "retrying this can never succeed" - the item is marked terminal and alerts
    once, instead of re-failing and re-alerting on every batch cycle forever. Any new
    exception with the same property sets this attribute; handlers stay duck-typed on
    `getattr(exc, 'permanent', False)` so there is nothing to import."""

    permanent = True


def record_group_failure(conn, group_id: int, reason_prefix: str, exc: Exception, *, now=None) -> bool:
    """GL-54's per-item failure write, plus GL-58's permanence branch. Returns True if
    the failure was permanent (the group is now 'failed_abandoned' and will never be
    retried or re-alerted), False if it stays retryable at 'pending_generation'.

    A stage loop still appends to `failures` and still fails once at the end either way
    - permanence changes how often the item is retried, never whether the stage reports
    (CLAUDE.md's swallowed-exception rule)."""
    permanent = getattr(exc, "permanent", False)
    timestamp = now if isinstance(now, str) else (
        now or datetime.now(timezone.utc).replace(tzinfo=None)
    ).isoformat()
    reason = f"{reason_prefix}{' (permanent)' if permanent else ''}: {exc}"
    if permanent:
        conn.execute(
            "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? "
            "WHERE id = ?",
            (reason, timestamp, group_id),
        )
    else:
        conn.execute(
            "UPDATE groups SET failed_reason = ?, updated_at = ? WHERE id = ?",
            (reason, timestamp, group_id),
        )
    conn.commit()
    return permanent


class GalleryTooLargeError(Exception):
    """Etsy caps a listing at 20 photos. Asserted, never assumed (PRD scope) - today's
    worst case is 10 primary + 1 5x7 + 2 10x24 = 13, but the scene library grows."""


ETSY_MAX_LISTING_IMAGES = 20

# Gallery rank order across the candidate's groups: primary's mockups first, then the
# secondary crops in size order. One listing, one gallery (v4.12).
_GROUP_RANK_SQL = "CASE g.group_type WHEN 'primary' THEN 0 WHEN '5x7' THEN 1 ELSE 2 END"

# A group whose review did not pass contributes no variant and no gallery image to the
# candidate's listing ([D1]); it is excluded, never deleted (CLAUDE.md, v4.12).
_INCLUDED_GROUP_SQL = (
    "g.decision IN ('approved','edited') "
    "AND g.status NOT IN ('rejected','failed_abandoned','stalled_skipped')"
)


MIN_PRINT_DPI = 150

# Physical print dimensions, used here for the pre-create DPI guard only. Gelato
# enforces its own DPI at product creation; this fails loud *before* a live call
# when the upscaled master can't clear 150 DPI (Gelato's stated poster minimum)
# at a group's largest size (B5). The table itself lives in image_crop, next to
# the aspect ratios derived from it.
from pipeline.image_crop import SIZE_INCHES as _SIZE_INCHES  # noqa: E402


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


def _find_product_row(conn, candidate_id: int, group_id: int = None, statuses: tuple = ()):
    """v4.12: the Gelato product / Etsy listing belongs to the CANDIDATE, not to one
    aspect-ratio group, so the reuse key is candidate_id. Pre-migration rows (GL-9 era,
    candidate_id NULL) are still resolved by their original group_id - they predate the
    new shape and must keep reusing their real, already-published Gelato product rather
    than being duplicated by a candidate-keyed miss. New-shape rows win the tie."""
    placeholders = ", ".join("?" * len(statuses))
    return conn.execute(
        f"SELECT id, gelato_product_id, status, candidate_id FROM group_products "
        f"WHERE (candidate_id = ? OR (candidate_id IS NULL AND group_id = ?)) "
        f"AND status IN ({placeholders}) "
        f"ORDER BY candidate_id IS NULL, id LIMIT 1",
        (candidate_id, group_id, *statuses),
    ).fetchone()


_ACTIVE_STATUSES = ("pending", "created", "published", "mockup_failed", "publish_failed")


def live_product_row(conn, candidate_id: int, group_id: int = None):
    """The candidate's listing record, or None. v4.12: `group_products` is no longer
    "the Gelato product row" - it is the CANDIDATE's LISTING RECORD, of which
    gelato_product_id is one nullable column (NULL for the whole review window, filled
    in once at publish by create_candidate_gelato_product). There is at most one active
    row per candidate; every stage that used to find one by group_id + status='created'
    goes through here instead."""
    return _find_product_row(conn, candidate_id, group_id, _ACTIVE_STATUSES)


def included_group_ids(conn, candidate_id: int) -> list:
    """The groups whose review passed, in gallery rank order - the single definition of
    "what goes on this candidate's listing". A rejected / abandoned / stalled group is
    excluded here and deleted nowhere (CLAUDE.md v4.12)."""
    return [
        row["id"] for row in conn.execute(
            f"SELECT g.id FROM groups g WHERE g.candidate_id = ? AND {_INCLUDED_GROUP_SQL} "
            f"ORDER BY {_GROUP_RANK_SQL}",
            (candidate_id,),
        ).fetchall()
    ]


def _ensure_product_row(conn, candidate_id: int, group_id: int, template_id: str, timestamp: str) -> int:
    row = live_product_row(conn, candidate_id, group_id)
    if row is not None:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', ?, ?)",
        (candidate_id, group_id, template_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _render_scenes(candidate: dict, group_type: str, orientation: str, static_config: dict,
                    group_product_id: int, group_id: int) -> list:
    """The self-hosted mockup gallery (GL-5 task 3). The storefront gallery is rendered
    locally, never sourced from Gelato's product images - no fallback to a Gelato/base
    image if this fails; any failure here is a real mockup_failed."""
    scene_ids = config.get_mockup_templates(static_config, group_type, orientation)
    if not scene_ids:
        # No bundles authored yet for this group_type/orientation - a valid, expected
        # zero-image gallery, not an error (Task 2's contract).
        return []

    if group_type == "primary":
        # Primary is close enough to the master's own ratio that CLAUDE.md already
        # treats it as "a small crop, not a re-composition" - render straight from the
        # archived master, no crop step.
        render_source_path = candidate.get("base_image_local_path")
        if not render_source_path or not Path(render_source_path).exists():
            raise PrintResolutionError(
                f"Cannot render mockups: base_image_local_path missing or unreadable "
                f"({render_source_path!r}). The master must be archived locally before "
                f"mockups can be composited."
            )
    else:
        render_source_path = _group_print_crop(candidate, group_type)["local_path"]

    art = Image.open(render_source_path).convert("RGB")
    images = []
    for index, scene_id in enumerate(scene_ids):
        bundle = mockup_render.load_bundle(config.mockup_bundle_dir(group_type, orientation, scene_id))
        rendered = mockup_render.render_scene(art, bundle)
        buf = io.BytesIO()
        rendered.save(buf, format="PNG")
        persisted = artwork_store.persist_mockup_render(group_product_id, group_id, index, buf.getvalue())
        image_type = "flat_mockup" if bundle.tag == "flat" else "lifestyle"
        images.append({"fileUrl": persisted["durable_url"], "image_type": image_type})
    return images


def render_group_mockups(conn, group_id: int, sizes: list, candidate: dict, static_config: dict,
                          orientation: str = "portrait", *, now=None) -> dict:
    """v4.12: the RENDER half of the old create_or_reuse_group_product. Produces one
    aspect-ratio group's review gallery and records that group's variant rows. It makes
    no Gelato call at all - the candidate's Gelato product is created once, at publish,
    by create_candidate_gelato_product.

    The two jobs had to be split because their timings are incompatible: the review
    mockups must exist BEFORE any group is decided (they are what the owner reviews),
    and the Gelato product can only be created AFTER every group is decided, with all
    validated sizes in one call ([D1], forced by GL-22a Q2 - no API path adds a variant
    post-create). Every write here is scoped to `group_id`, so one group's re-render
    never touches another group's reviewed gallery."""
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    candidate_id = candidate["id"]
    group_type = conn.execute(
        "SELECT group_type FROM groups WHERE id = ?", (group_id,)
    ).fetchone()["group_type"]

    # DPI guard before any DB write. It guards that the master is large enough to PRINT
    # each size - a print concern, not a Gelato one - so under v4.12 it belongs on the
    # render path: a too-small master now fails before the owner spends a review on it
    # rather than after. Still gated on GELATO live mode (dry-run/test masters are
    # synthetic and have no local archive) and still ahead of every write, so the
    # "fails fast without orphaning a row" property it was written for is unchanged.
    if config.is_live_mode("GELATO"):
        _assert_print_dpi(sizes, candidate.get("base_image_local_path"))

    templates = [config.get_template_variant(static_config, size, orientation) for size in sizes]
    group_product_id = _ensure_product_row(
        conn, candidate_id, group_id, templates[0]["template_id"], timestamp
    )

    # Once the candidate's Gelato product exists, its variant set is frozen: GL-22a Q2
    # proved there is no API path to add one, and the product must not be deleted and
    # recreated because other groups' sizes are already on it. So a group arriving with
    # sizes AFTER the create fails loud here rather than quietly recording a variant row
    # for a size the product will never carry. (A group that already has variant rows is
    # just re-rendering - that is fine and changes nothing Gelato-side.)
    existing_row = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if existing_row["gelato_product_id"] and not conn.execute(
        "SELECT 1 FROM group_product_variants WHERE group_product_id = ? AND group_id = ? LIMIT 1",
        (group_product_id, group_id),
    ).fetchone():
        raise SharedProductVariantError(
            f"Candidate {candidate_id}'s Gelato product "
            f"{existing_row['gelato_product_id']} already exists; refusing to add group "
            f"{group_id}'s sizes {sorted(sizes)} to it. A variant cannot be added to an "
            f"existing product (GL-22a Q2)."
        )

    conn.execute(
        "DELETE FROM group_product_variants WHERE group_product_id = ? AND group_id = ?",
        (group_product_id, group_id),
    )
    for size, template in zip(sizes, templates):
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, group_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (group_product_id, group_id, size, orientation, template["template_variant_id"],
             static_config["prices_eur"][size], timestamp),
        )
    conn.commit()

    try:
        images = _render_scenes(
            candidate, group_type, orientation, static_config, group_product_id, group_id
        )
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    # Idempotent on retry: a re-render may find a partial gallery from an earlier
    # attempt. The `AND group_id = ?` is the whole point of GL-22 session 2 - without
    # it, 5x7 rendering its mockups would silently wipe the primary group's already-
    # reviewed gallery off the shared listing record. scene_ids order is already
    # render/rank order, so gallery_order is just the loop index.
    conn.execute(
        "DELETE FROM product_images WHERE group_product_id = ? AND group_id = ?",
        (group_product_id, group_id),
    )
    for order, image in enumerate(images):
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, '', ?, ?)",
            (group_product_id, group_id, image["fileUrl"], order, image["image_type"]),
        )
    # 'pending' is exactly right for a row that exists with no Gelato product yet; a
    # previously mockup_failed row is healthy again now its render succeeded. A row
    # already 'created'/'published' keeps its status - its Gelato product still exists.
    conn.execute(
        "UPDATE group_products SET status = 'pending', updated_at = ? WHERE id = ? "
        "AND status IN ('pending', 'mockup_failed')",
        (timestamp, group_product_id),
    )
    conn.commit()

    return {"group_product_id": group_product_id, "image_count": len(images)}


def create_candidate_gelato_product(conn, candidate_id: int, candidate: dict, static_config: dict,
                                     title: str, *, store_id: str = None, api_key: str = None,
                                     poll_interval: float = 10.0, poll_timeout: float = 300.0,
                                     now=None) -> dict:
    """v4.12 [D1]: the GELATO half of the old create_or_reuse_group_product. ONE
    create-from-template call per candidate, made at publish time once every group has
    reached a terminal decision, carrying every validated size as a variant with its own
    group's fileUrl (GL-22a Q1 proved two variants sharing an image_placeholder_name
    accept independently-submitted fileUrls in a single call)."""
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    product_row = live_product_row(conn, candidate_id)
    if product_row is None:
        raise ValueError(f"No group_products (listing record) row for candidate {candidate_id}")
    group_product_id = product_row["id"]

    group_ids = included_group_ids(conn, candidate_id)
    if not group_ids:
        raise ValueError(f"Candidate {candidate_id} has no group whose review passed - nothing to publish")
    placeholders = ", ".join("?" * len(group_ids))
    variant_rows = conn.execute(
        f"SELECT v.size, v.orientation, v.gelato_template_variant_id, g.group_type "
        f"FROM group_product_variants v JOIN groups g ON g.id = v.group_id "
        f"WHERE v.group_product_id = ? AND v.group_id IN ({placeholders}) "
        f"ORDER BY {_GROUP_RANK_SQL}, v.id",
        (group_product_id, *group_ids),
    ).fetchall()
    if not variant_rows:
        raise ValueError(f"Candidate {candidate_id}'s included groups carry no sizes to publish")

    # An excluded group's variant rows come off the listing record here, so what the
    # table holds is exactly what the Gelato product carries - which is what makes the
    # reuse check below exact rather than approximate. Scoped by group_id: it drops that
    # group's own rows and nothing else, and its gallery images stay put (the gallery
    # filters on the group's decision, it doesn't delete).
    conn.execute(
        f"DELETE FROM group_product_variants WHERE group_product_id = ? "
        f"AND group_id NOT IN ({placeholders})",
        (group_product_id, *group_ids),
    )
    conn.commit()

    if product_row["gelato_product_id"]:
        # Idempotency, a hard constraint (the first live run duplicated products: create
        # succeeded, the readiness poll timed out, the retry re-created). A product id on
        # the row means the create already succeeded, whatever happened afterwards -
        # never create a second one. There is no delete-and-recreate fallback under
        # create-once: Q2 proved a product's variant set cannot be changed, and the
        # product is the candidate's, so deleting it would destroy other groups' sizes.
        existing = {row["size"] for row in conn.execute(
            "SELECT size FROM group_product_variants WHERE group_product_id = ?", (group_product_id,)
        ).fetchall()}
        wanted = {row["size"] for row in variant_rows}
        if not wanted <= existing:
            raise SharedProductVariantError(
                f"Candidate {candidate_id}'s Gelato product {product_row['gelato_product_id']} "
                f"carries sizes {sorted(existing)}, but the validated groups need "
                f"{sorted(wanted)}. A variant cannot be added to an existing product "
                f"(GL-22a Q2) and the product must not be deleted - it is the candidate's."
            )
        gelato_product_id = product_row["gelato_product_id"]
        is_dry_run = False
    else:
        template_id = config.get_template_variant(
            static_config, variant_rows[0]["size"], variant_rows[0]["orientation"]
        )["template_id"]
        # One crop per distinct non-primary group_type, built once per call - see
        # _group_print_crop's docstring for why a second call with identical bytes would
        # be a wasted duplicate R2 PUT. (The render path builds its own crop earlier, in
        # a different run; that is a separate phase, not a duplicate within one call.)
        crops = {
            gt: _group_print_crop(candidate, gt)
            for gt in dict.fromkeys(row["group_type"] for row in variant_rows)
            if gt in _PRINT_CROP_GROUP_TYPES
        }

        def _image_url_for(row):
            # GL-48: NOT gated on live mode. A dry run that takes a different branch
            # from live is not a rehearsal, it is a different program - the old
            # `and config.is_live_mode("GELATO")` meant every dry run submitted the
            # uncropped master, so the two-night soak was structurally incapable of
            # observing the crop path at all. Without R2 the crop's durable_url is a
            # local filesystem path; that is still the right URL to hand over, because
            # create_product_from_template's non-http(s) guard then fails loud on a
            # live call and returns before any guard on a dry-run one.
            crop = crops.get(row["group_type"])
            if crop is not None:
                return crop["durable_url"]
            return candidate["base_image_url"]

        # GL-32: written and committed BEFORE the POST. A crash between the POST
        # returning and the id-recording UPDATE below leaves this timestamp set with
        # gelato_product_id still NULL - the one signal that a real Gelato product may
        # exist with no DB row pointing at it. See reconcile.find_unconfirmed_gelato_creates.
        conn.execute(
            "UPDATE group_products SET gelato_create_intent_at = ?, gelato_template_id = ?, updated_at = ? WHERE id = ?",
            (timestamp, template_id, timestamp, group_product_id),
        )
        conn.commit()

        response = gelato_client.create_product_from_template(
            template_id,
            [
                {"template_variant_id": row["gelato_template_variant_id"],
                 "image_placeholder_name": config.get_template_variant(
                     static_config, row["size"], row["orientation"])["image_placeholder_name"],
                 "image_url": _image_url_for(row)}
                for row in variant_rows
            ],
            title, store_id=store_id, api_key=api_key,
        )
        gelato_product_id = response["id"]
        conn.execute(
            "UPDATE group_products SET gelato_product_id = ?, gelato_template_id = ?, "
            "gelato_create_intent_at = NULL, updated_at = ? WHERE id = ?",
            (gelato_product_id, template_id, timestamp, group_product_id),
        )
        conn.commit()
        is_dry_run = bool(response.get("_dry_run"))

    if not is_dry_run:
        # Gelato's own gallery is never consumed for the storefront - this poll still
        # matters because it's the only signal that Gelato's print asset actually
        # rehosted and the product is ready to publish/fulfil.
        poll_until_ready(
            gelato_product_id, store_id=store_id, api_key=api_key,
            poll_interval=poll_interval, timeout=poll_timeout,
        )

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()

    return {"group_product_id": group_product_id, "gelato_product_id": gelato_product_id}



def patch_etsy_listing(conn, group_product_id: int, listing_text: dict, static_config: dict, *,
                        shop_id: str = None, etsy_api_key: str = None, etsy_api_secret: str = None,
                        etsy_access_token: str = None, dry_run: bool = None, now=None) -> str:
    """v4.12: patches the CANDIDATE's one listing. The gallery is assembled across every
    group whose review passed, in rank order; a rejected/abandoned/stalled group
    contributes nothing and loses nothing."""
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")

    # GL-63b / #157: this is the one function every publish path routes through, so the
    # forbidden/seasonal-term guard belongs here rather than in each caller (a stale
    # pre-guardrail listing_texts row, or a hand-edited one, must never reach Etsy).
    # Checked before any upload/reconcile work, not just before update_listing, and
    # never gated on dry_run - CLAUDE.md: dry-run gates the HTTP call, never the code path.
    compliance_draft.validate_listing_text(
        listing_text["title"], json.loads(listing_text["tags"]), listing_text["description"],
    )

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

    image_rows = conn.execute(
        f"SELECT pi.id, pi.image_url, pi.etsy_listing_image_id, pi.alt_text, pi.image_type "
        f"FROM product_images pi JOIN groups g ON g.id = pi.group_id "
        f"WHERE pi.group_product_id = ? AND {_INCLUDED_GROUP_SQL} "
        f"ORDER BY {_GROUP_RANK_SQL}, pi.gallery_order",
        (group_product_id,),
    ).fetchall()
    if len(image_rows) > ETSY_MAX_LISTING_IMAGES:
        raise GalleryTooLargeError(
            f"Candidate listing {listing_id} would carry {len(image_rows)} gallery images; "
            f"Etsy caps a listing at {ETSY_MAX_LISTING_IMAGES}."
        )
    for rank, row in enumerate(image_rows, start=1):
        # GL-57: rank is the row's 1-based position in the _GROUP_RANK_SQL order above -
        # counted over the whole ordered list, including rows skipped just below, so a
        # resumed upload lands in the same slot it would have on a clean run. Sent on
        # every image rather than only rank=1, so the gallery does not depend on an
        # Etsy default-ordering rule nobody has verified.
        #
        # Idempotent: this loop is a full re-upload with no delta, so a second call after
        # a partial failure would duplicate the whole gallery on the live listing. Rows
        # that already uploaded carry Etsy's own listing_image_id and are skipped.
        if row["etsy_listing_image_id"]:
            continue
        url = row["image_url"]
        image_bytes = b"" if dry_run else (
            http.fetch_bytes(url) if url.startswith(("http://", "https://")) else Path(url).read_bytes()
        )
        # GL-69: alt text is set at upload or never - Etsy v3 has no update-image
        # endpoint. The primary gallery carries model-written alt text
        # (compliance_draft.update_gallery_alt_text); secondary groups (5x7 / 10x24)
        # were never given any, so they get one derived from the listing title, written
        # back to the row so the DB stays the thing a live read-back is checked against.
        alt_text = row["alt_text"]
        if not alt_text:
            alt_text = compliance_draft.fallback_alt_text(
                listing_text["title"], row["image_type"]
            )
            conn.execute(
                "UPDATE product_images SET alt_text = ? WHERE id = ?", (alt_text, row["id"])
            )
            conn.commit()
        if not alt_text:
            # Fails loud rather than uploading an empty string: an empty alt_text is
            # unrepairable after upload, and silence is exactly how GL-69 survived.
            raise ValueError(
                f"product_images row {row['id']} has no alt text and none could be "
                f"derived; refusing to upload an image whose alt text can never be set"
            )
        response = etsy_client.upload_listing_image(
            shop_id, listing_id, image_bytes, rank=rank, alt_text=alt_text,
            api_key=etsy_api_key, api_secret=etsy_api_secret,
            access_token=etsy_access_token, dry_run=dry_run,
        )
        conn.execute(
            "UPDATE product_images SET etsy_listing_image_id = ? WHERE id = ?",
            (str(response.get("listing_image_id")), row["id"]),
        )
        conn.commit()

    # GL-33: Gelato's product-create push seeds the listing with its own generic preview
    # images. Reconcile after our uploads (never before - deleting first would leave the
    # listing briefly imageless) and before update_listing: delete every Etsy image whose
    # id this candidate does not positively own. "Own" is derived, never guessed - a row
    # in product_images scoped to THIS group_product_id, the same scoping discipline
    # _INCLUDED_GROUP_SQL uses elsewhere, so a wrong scope here can't delete another
    # group's reviewed gallery.
    owned_image_ids = {
        row["etsy_listing_image_id"] for row in conn.execute(
            "SELECT etsy_listing_image_id FROM product_images "
            "WHERE group_product_id = ? AND etsy_listing_image_id IS NOT NULL",
            (group_product_id,),
        ).fetchall()
    }
    current_images = etsy_client.get_listing_images(
        listing_id, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )
    for image in current_images.get("results", []):
        foreign_id = str(image["listing_image_id"])
        if foreign_id in owned_image_ids:
            continue
        etsy_client.delete_listing_image(
            shop_id, listing_id, foreign_id, api_key=etsy_api_key, api_secret=etsy_api_secret,
            access_token=etsy_access_token, dry_run=dry_run,
        )
        print(
            f"[group_product] deleted foreign Etsy image {foreign_id} from listing {listing_id} "
            f"(group_product_id={group_product_id})",
            file=sys.stderr,
        )

    shipping_profile_id = config.get_shipping_profile_id(static_config)
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
        f"SELECT v.size, v.price_eur FROM group_product_variants v "
        f"JOIN groups g ON g.id = v.group_id "
        f"WHERE v.group_product_id = ? AND {_INCLUDED_GROUP_SQL}",
        (group_product_id,),
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
