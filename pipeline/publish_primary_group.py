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

    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")

    # Reuse an already-created draft on retry instead of calling create_draft_listing again —
    # otherwise a retry after create_draft_listing succeeded but update_listing_state failed
    # would leave an orphaned duplicate Etsy draft behind on every retry.
    existing_row = conn.execute(
        "SELECT etsy_listing_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if existing_row is not None and existing_row["etsy_listing_id"] is not None:
        listing_id = existing_row["etsy_listing_id"]
    else:
        listing_data = build_size_listing_data(dict(listing_text_row), size, price_eur)
        draft = etsy_client.create_draft_listing(
            shop_id, listing_data, api_key=etsy_api_key, api_secret=etsy_api_secret,
            access_token=etsy_access_token, dry_run=dry_run,
        )
        listing_id = draft["listing_id"]
        conn.execute(
            "UPDATE group_products SET etsy_listing_id = ?, updated_at = ? WHERE id = ?",
            (str(listing_id), timestamp, group_product_id),
        )
        conn.commit()

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

    # status IN ('created', 'published') rather than just 'created': a re-run after a crash
    # (e.g. process died between 8x12 and the other sizes finishing) must still pass this
    # guard even though 8x12 already made it all the way to 'published'.
    existing_8x12 = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12' AND status IN ('created', 'published')",
        (group_id,),
    ).fetchone()
    if existing_8x12 is None:
        raise ValueError(f"No live 8x12 group_product for candidate {candidate_id}'s primary group")

    # Only create rows for sizes that don't have one yet, so re-running this function after a
    # partial failure doesn't spawn duplicate group_products/Gelato products/Etsy drafts for
    # sizes that already succeeded or are mid-retry.
    secondary_sizes = [s for s in static_config["aspect_ratio_groups"]["primary"] if s != "8x12"]
    for size in secondary_sizes:
        existing_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND size = ? AND status != 'deleted'",
            (group_id, size),
        ).fetchone()
        if existing_row is None:
            template = config.get_template_variant(static_config, size, "portrait")
            create_group_product_row(
                conn, group_id, size, "portrait", template["template_id"],
                static_config["prices_eur"][size], now=now,
            )

    group_products = conn.execute(
        "SELECT id, size, status FROM group_products WHERE group_id = ? AND status != 'deleted' ORDER BY id",
        (group_id,),
    ).fetchall()

    results = {}
    any_published = False
    for row in group_products:
        gp_id, size, status = row["id"], row["size"], row["status"]
        if status == "published":
            results[size] = "published"
            any_published = True
            continue
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


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        record_decision(conn, group_id, "approved", decision_notes, now=now)
        results = publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", "results": results}

    if action == "edit":
        record_decision(conn, group_id, "edited", decision_notes, now=now)
        resolved_static_config = static_config if static_config is not None else config.load_static_config()

        old_gp_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12' AND status = 'created'",
            (group_id,),
        ).fetchone()
        if old_gp_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, old_gp_row["id"], store_id=store_id, api_key=gelato_api_key,
            )
        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=decision_notes, api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=resolved_static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=resolved_static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        return {"action": "edit"}

    if action == "reject":
        record_decision(conn, group_id, "rejected", decision_notes, now=now)
        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'failed', failed_reason = 'primary group rejected', "
            "updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()
        return {"action": "reject"}

    raise ValueError(f"Unknown action {action!r}")


def get_telegram_offset(conn) -> int | None:
    row = conn.execute("SELECT last_update_id FROM telegram_offset WHERE id = 1").fetchone()
    return row["last_update_id"] if row is not None else None


def set_telegram_offset(conn, last_update_id: int) -> None:
    conn.execute(
        "INSERT INTO telegram_offset (id, last_update_id) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_update_id = excluded.last_update_id",
        (last_update_id,),
    )
    conn.commit()


def process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None,
                    store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None,
                    etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None,
                    anthropic_api_key=None, dry_run=None, now=None) -> dict | None:
    admin_chat_id = admin_chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    parsed = resolve_callback(update)
    if parsed is None:
        return None

    if not is_admin(parsed["telegram_user_id"], admin_chat_id):
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: not admin", now=now)
        return None

    message_row = conn.execute(
        "SELECT chat_id, telegram_message_id FROM group_messages WHERE group_id = ?",
        (parsed["group_id"],),
    ).fetchone()
    if message_row is None or str(message_row["chat_id"]) != str(parsed["chat_id"]) \
            or message_row["telegram_message_id"] != parsed["message_id"]:
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: callback does not match a known group_messages row", now=now)
        return None

    group_row = conn.execute(
        "SELECT candidate_id FROM groups WHERE id = ?", (parsed["group_id"],)
    ).fetchone()
    candidate_id = group_row["candidate_id"]

    log_telegram_event(conn, parsed["telegram_user_id"], update, True, parsed["action"], now=now)
    telegram_client.answer_callback_query(parsed["callback_query_id"], bot_token=bot_token)

    result = handle_decision(
        conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
        store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
        etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
        dry_run=dry_run, now=now,
    )
    return {"candidate_id": candidate_id, "group_id": parsed["group_id"], **result}


def run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None, static_config=None,
                                     store_id=None, gelato_api_key=None, shop_id=None,
                                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                                     replicate_api_token=None, anthropic_api_key=None,
                                     dry_run=None, now=None) -> list:
    last_offset = get_telegram_offset(conn)
    offset = last_offset + 1 if last_offset is not None else None
    updates = telegram_client.get_updates(offset=offset, bot_token=bot_token)

    processed = []
    max_update_id = last_offset
    for update in updates:
        update_id = update["update_id"]
        max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
        try:
            result = process_update(
                conn, update, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
                etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
                replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                dry_run=dry_run, now=now,
            )
        except Exception as exc:
            # process_update can raise after resolve_callback succeeds but before/during
            # handle_decision — this cron has no console to watch, so a print() alone leaves
            # no durable trace that the admin's tap was dropped. accepted=True distinguishes
            # "this was a real event that failed" from the accepted=False discard-path rows
            # log_telegram_event already writes for non-admin/unknown-group callbacks.
            telegram_user_id = update.get("callback_query", {}).get("from", {}).get("id")
            log_telegram_event(conn, telegram_user_id, update, True, f"error: {exc}", now=now)
            print(f"process_update failed for update {update_id}: {exc}")
            continue
        if result is not None:
            processed.append(result)

    if max_update_id is not None:
        set_telegram_offset(conn, max_update_id)

    return processed
