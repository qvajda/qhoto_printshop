from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.primary_mockup as primary_mockup


def get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, ?, 'pending_generation', ?, ?)
        """,
        (candidate_id, group_type, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _group_size(static_config: dict, group_type: str) -> str:
    return static_config["aspect_ratio_groups"][group_type][0]


def create_group_mockup(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                         store_id: str = None, api_key: str = None,
                         poll_interval: float = 3.0, poll_timeout: float = 90.0,
                         now=None) -> dict | None:
    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)
    size = _group_size(static_config, group_type)

    existing = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = ? AND status IN ('created', 'published')",
        (group_id, size),
    ).fetchone()
    if existing is not None:
        return None

    row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = ? AND status != 'deleted'",
        (group_id, size),
    ).fetchone()
    if row is not None:
        group_product_id = row["id"]
    else:
        template = config.get_template_variant(static_config, size, "portrait")
        cursor = conn.execute(
            """
            INSERT INTO group_products
              (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
            VALUES (?, ?, 'portrait', ?, ?, 'pending', ?, ?)
            """,
            (group_id, size, template["template_id"], static_config["prices_eur"][size], timestamp, timestamp),
        )
        conn.commit()
        group_product_id = cursor.lastrowid

    template = config.get_template_variant(static_config, size, "portrait")

    def attempt():
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

        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or "placeholder://dry-run-image", "isPrimary": True}]
        else:
            product = primary_mockup.poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
        return gelato_product_id, images

    try:
        try:
            gelato_product_id, images = attempt()
        except Exception:
            gelato_product_id, images = attempt()
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
    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": group_product_id, "gelato_product_id": gelato_product_id}


GROUP_TYPES = ("5x7", "10x24")


def run_group_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                            api_key: str = None, poll_interval: float = 3.0,
                            poll_timeout: float = 90.0, now=None) -> list:
    static_config = static_config if static_config is not None else config.load_static_config()

    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
                          AND g.status = 'approved_published'
            ORDER BY c.id
            """
        ).fetchall()
    ]

    processed = []
    for candidate_id in candidate_ids:
        for group_type in GROUP_TYPES:
            try:
                result = create_group_mockup(
                    conn, candidate_id, group_type, static_config=static_config,
                    store_id=store_id, api_key=api_key, poll_interval=poll_interval,
                    poll_timeout=poll_timeout, now=now,
                )
            except Exception as exc:
                print(f"create_group_mockup failed for candidate {candidate_id} "
                      f"group_type {group_type}: {exc}")
                continue
            if result is not None:
                processed.append({
                    "candidate_id": candidate_id,
                    "group_type": group_type,
                    "gelato_product_id": result["gelato_product_id"],
                })
    return processed
