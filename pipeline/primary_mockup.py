import time
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client


class GelatoMockupTimeoutError(Exception):
    pass


def build_mockup_title(candidate: dict) -> str:
    return f"{candidate['niche']} - primary mockup"


def get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'pending_generation', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def poll_until_ready(product_id: str, *, store_id: str = None, api_key: str = None,
                      poll_interval: float = 3.0, timeout: float = 90.0,
                      sleep_fn=time.sleep, now_fn=time.monotonic) -> dict:
    deadline = now_fn() + timeout
    while True:
        product = gelato_client.get_product(product_id, store_id=store_id, api_key=api_key)
        if product.get("isReadyToPublish"):
            return product
        if now_fn() >= deadline:
            raise GelatoMockupTimeoutError(
                f"Gelato product {product_id} did not become ready to publish within "
                f"{timeout:.0f}s. The one observed real render took ~9s for a 4-image "
                f"gallery - this likely indicates a Gelato-side delay or outage, not a "
                f"pipeline bug."
            )
        sleep_fn(poll_interval)


def create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None,
                           store_id: str = None, api_key: str = None,
                           poll_interval: float = 3.0, poll_timeout: float = 90.0,
                           now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_primary_group(conn, candidate_id, now=now)

    template = config.get_template_variant(static_config, "8x12", "portrait")
    price_eur = static_config["prices_eur"]["8x12"]

    cursor = conn.execute(
        """
        INSERT INTO group_products
          (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
        VALUES (?, '8x12', 'portrait', ?, ?, 'pending', ?, ?)
        """,
        (group_id, template["template_id"], price_eur, timestamp, timestamp),
    )
    conn.commit()
    group_product_id = cursor.lastrowid

    try:
        response = gelato_client.create_product_from_template(
            template["template_id"], template["template_variant_id"],
            template["image_placeholder_name"], candidate["base_image_url"],
            build_mockup_title(candidate), store_id=store_id, api_key=api_key,
        )
        gelato_product_id = response["id"]
        conn.execute(
            "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
            (gelato_product_id, timestamp, group_product_id),
        )
        conn.commit()

        if response.get("_dry_run"):
            # In dry-run mode, synthesize a single flat mockup placeholder
            preview_url = response.get("previewUrl") or "placeholder://dry-run-image"
            images = [{"fileUrl": preview_url, "isPrimary": True}]
        else:
            product = poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
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
            """
            INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type)
            VALUES (?, ?, '', ?, ?)
            """,
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


def run_primary_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                              api_key: str = None, poll_interval: float = 3.0,
                              poll_timeout: float = 90.0, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT id FROM candidates
            WHERE status = 'generating'
              AND base_image_url IS NOT NULL
              AND id NOT IN (
                SELECT g.candidate_id FROM groups g
                JOIN group_products gp ON gp.group_id = g.id
                WHERE g.group_type = 'primary'
              )
            ORDER BY id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            create_primary_mockup(
                conn, candidate_id, static_config=static_config, store_id=store_id,
                api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
            )
        except Exception as exc:
            print(f"create_primary_mockup failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
