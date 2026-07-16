from datetime import datetime, timezone

import pipeline.config as config
import pipeline.group_product as group_product


def build_mockup_title(candidate: dict) -> str:
    return f"{candidate['niche']} - primary mockup"


def get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'pending_generation', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None,
                           store_id: str = None, api_key: str = None,
                           poll_interval: float = 3.0, poll_timeout: float = 90.0,
                           now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_primary_group(conn, candidate_id, now=now)

    result = group_product.create_or_reuse_group_product(
        conn, group_id, ["8x12"], candidate, static_config, build_mockup_title(candidate),
        store_id=store_id, api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
    )

    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": result["group_product_id"],
            "gelato_product_id": result["gelato_product_id"]}


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
