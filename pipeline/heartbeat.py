"""GL-7 §2 item 7: 'a run that does not happen is detectable.' One row per job
name, overwritten on every run - last() answers 'when did this job last run,
and did it succeed' in one indexed lookup, which is what a soak-watching
status check and a stale-run alert both need."""
from datetime import datetime, timezone


def record(conn, job_name: str, *, ok: bool, detail: str = None, now=None) -> None:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        "INSERT INTO heartbeats (job_name, ran_at, ok, detail) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(job_name) DO UPDATE SET ran_at = excluded.ran_at, ok = excluded.ok, "
        "detail = excluded.detail",
        (job_name, now.isoformat(), 1 if ok else 0, detail),
    )
    conn.commit()


def last(conn, job_name: str) -> dict | None:
    row = conn.execute(
        "SELECT job_name, ran_at, ok, detail FROM heartbeats WHERE job_name = ?",
        (job_name,),
    ).fetchone()
    if row is None:
        return None
    return {
        "job_name": row["job_name"],
        "ran_at": row["ran_at"],
        "ok": bool(row["ok"]),
        "detail": row["detail"],
    }
