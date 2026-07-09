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
