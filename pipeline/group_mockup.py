from datetime import datetime, timezone

import pipeline.config as config
import pipeline.group_product as group_product


def get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, ?, 'pending_generation', ?, ?)
        """,
        (candidate_id, group_type, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _group_sizes(static_config: dict, group_type: str) -> list:
    return static_config["aspect_ratio_groups"][group_type]


def create_group_mockup(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                         store_id: str = None, api_key: str = None,
                         poll_interval: float = 10.0, poll_timeout: float = 300.0,
                         now=None) -> dict | None:
    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    static_config = static_config if static_config is not None else config.load_static_config()

    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)

    group_status_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    if group_status_row["status"] in ("failed_abandoned", "rejected"):
        return None

    live_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published')",
        (group_id,),
    ).fetchone()
    if live_row is not None:
        return None

    sizes = _group_sizes(static_config, group_type)

    def attempt():
        # Gelato pushes this as the Etsy draft title; Etsy hard-caps titles at 140 chars
        # and rejects the create otherwise. The real title is set later on the listing patch.
        title = f"{candidate['niche']} - {group_type} mockup"[:140]
        return group_product.create_or_reuse_group_product(
            conn, group_id, sizes, candidate, static_config, title,
            store_id=store_id, api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
        )

    try:
        result = attempt()
    except Exception:
        result = attempt()

    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": result["group_product_id"],
            "gelato_product_id": result["gelato_product_id"]}


GROUP_TYPES = ("5x7", "10x24")


def run_group_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                            api_key: str = None, poll_interval: float = 10.0,
                            poll_timeout: float = 300.0, now=None) -> list:
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
            # No scene bundles authored yet for this group_type (5x7/10x24 today) ->
            # skip entirely, don't create a groups/group_products row for a gallery
            # that can never be rendered. create_group_mockup always defaults to
            # portrait orientation (landscape fan-out isn't wired up yet), so that's
            # the orientation checked here too.
            if not config.get_mockup_templates(static_config, group_type, "portrait"):
                continue
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
