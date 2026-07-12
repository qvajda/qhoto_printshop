import json
from datetime import datetime, timezone

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.http as http
import pipeline.primary_mockup as primary_mockup
import pipeline.telegram_client as telegram_client



# Etsy has no "unlimited stock" flag for made-to-order POD items; 999 is the
# conventional large-placeholder quantity for this listing style.
LISTING_QUANTITY = 999

SIZE_TITLE_SUFFIXES = {
    "8x12": "",
    "A3": " - A3 Print",
    "A2": " - A2 Print",
    "A1": " - A1 Print",
}


def resolve_callback(update: dict) -> dict | None:
    callback_query = update.get("callback_query")
    if callback_query is None:
        return None

    action, _, group_id = callback_query["data"].partition(":")
    return {
        "telegram_user_id": callback_query["from"]["id"],
        "callback_query_id": callback_query["id"],
        "action": action,
        "group_id": int(group_id),
        "message_id": callback_query["message"]["message_id"],
        "chat_id": callback_query["message"]["chat"]["id"],
    }


def is_admin(telegram_user_id, admin_chat_id) -> bool:
    return str(telegram_user_id) == str(admin_chat_id)


def log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken=None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO telegram_events_log (received_at, telegram_user_id, raw_payload, accepted, action_taken)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, str(telegram_user_id), json.dumps(raw_payload), 1 if accepted else 0, action_taken),
    )
    conn.commit()
    return cursor.lastrowid


def record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET decision = ?, decision_notes = ?, decided_at = ?, updated_at = ? WHERE id = ?",
        (decision, decision_notes, timestamp, timestamp, group_id),
    )
    conn.commit()


def build_size_listing_data(listing_text: dict, size: str, price_eur: float) -> dict:
    tags = json.loads(listing_text["tags"])
    title = f"{listing_text['title']}{SIZE_TITLE_SUFFIXES[size]}"
    compliance_draft.validate_listing_text(title, tags)
    return {
        "title": title,
        "description": listing_text["description"],
        "price": price_eur,
        "quantity": LISTING_QUANTITY,
        "who_made": listing_text["who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "taxonomy_id": listing_text["taxonomy_id"],
        "shipping_profile_id": listing_text["shipping_profile_id"],
        "production_partner_ids": json.loads(listing_text["production_partner_ids"]),
        "tags": tags,
    }


def create_group_product_row(conn, group_id, size, orientation, template_id, price_eur, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO group_products
          (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (group_id, size, orientation, template_id, price_eur, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def create_gelato_product(conn, group_product_id, candidate, static_config, size, orientation, *,
                           store_id=None, api_key=None, now=None) -> str:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    template = config.get_template_variant(static_config, size, orientation)

    response = gelato_client.create_product_from_template(
        template["template_id"], template["template_variant_id"], template["image_placeholder_name"],
        candidate["base_image_url"], f"{candidate['niche']} - {size} print",
        store_id=store_id, api_key=api_key,
    )
    gelato_product_id = response["id"]
    conn.execute(
        "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
        (gelato_product_id, timestamp, group_product_id),
    )
    conn.commit()

    try:
        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or "placeholder://dry-run-image", "isPrimary": True}]
        else:
            product = primary_mockup.poll_until_ready(gelato_product_id, store_id=store_id, api_key=api_key)
            images = product["productImages"]

        ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
        for order, image in enumerate(ordered_images):
            image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
            conn.execute(
                "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
                "VALUES (?, ?, '', ?, ?)",
                (group_product_id, image.get("fileUrl"), order, image_type),
            )
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()
    return gelato_product_id


def publish_to_etsy(conn, group_product_id, candidate_id, size, price_eur, *, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     dry_run=None, now=None) -> str:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    listing_data = build_size_listing_data(dict(listing_text_row), size, price_eur)

    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")
    draft = etsy_client.create_draft_listing(
        shop_id, listing_data, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )
    listing_id = draft["listing_id"]

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (group_product_id,),
    ).fetchall()
    for row in image_rows:
        image_bytes = b"" if dry_run else http.fetch_bytes(row["image_url"])
        etsy_client.upload_listing_image(
            shop_id, listing_id, image_bytes, api_key=etsy_api_key, api_secret=etsy_api_secret,
            access_token=etsy_access_token, dry_run=dry_run,
        )

    etsy_client.update_listing_state(
        shop_id, listing_id, "active", api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    conn.execute(
        "UPDATE group_products SET etsy_listing_id = ?, status = 'published', updated_at = ? WHERE id = ?",
        (str(listing_id), timestamp, group_product_id),
    )
    conn.commit()
    return str(listing_id)


def publish_group_product(conn, group_product_id, candidate, static_config, *, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> str:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    def attempt():
        row = conn.execute("SELECT * FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        if row["status"] != "created":
            create_gelato_product(
                conn, group_product_id, candidate, static_config, row["size"], row["orientation"],
                store_id=store_id, api_key=gelato_api_key, now=now,
            )
        return publish_to_etsy(
            conn, group_product_id, candidate["id"], row["size"], row["price_eur"],
            shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
            etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
        )

    try:
        return attempt()
    except Exception:
        try:
            return attempt()
        except Exception:
            conn.execute(
                "UPDATE group_products SET status = 'publish_failed', updated_at = ? WHERE id = ?",
                (timestamp, group_product_id),
            )
            conn.commit()
            raise


def publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    existing_8x12 = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12' AND status = 'created'",
        (group_id,),
    ).fetchone()
    if existing_8x12 is None:
        raise ValueError(f"No live 8x12 group_product for candidate {candidate_id}'s primary group")

    secondary_sizes = [s for s in static_config["aspect_ratio_groups"]["primary"] if s != "8x12"]
    for size in secondary_sizes:
        template = config.get_template_variant(static_config, size, "portrait")
        create_group_product_row(
            conn, group_id, size, "portrait", template["template_id"],
            static_config["prices_eur"][size], now=now,
        )

    group_product_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status != 'deleted' ORDER BY id",
            (group_id,),
        ).fetchall()
    ]

    results = {}
    any_published = False
    for gp_id in group_product_ids:
        size = conn.execute("SELECT size FROM group_products WHERE id = ?", (gp_id,)).fetchone()["size"]
        try:
            publish_group_product(
                conn, gp_id, candidate, static_config, store_id=store_id, gelato_api_key=gelato_api_key,
                shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
            )
            results[size] = "published"
            any_published = True
        except Exception as exc:
            results[size] = "publish_failed"
            print(f"publish_group_product failed for candidate {candidate_id} size {size}: {exc}")

    if any_published:
        conn.execute(
            "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'completed', updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()

    return results
