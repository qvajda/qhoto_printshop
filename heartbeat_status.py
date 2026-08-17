"""GL-7 I3: one command to answer "did hourly/batch actually run recently."
heartbeat.record()/last() already exist; nothing read last() until now. This
is deliberately not a watchdog - it just prints both jobs' last heartbeat so
an operator (or a future cron-driven check) has one place to look."""
import sys
from pathlib import Path

import pipeline.db as db
import pipeline.heartbeat as heartbeat

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
JOB_NAMES = ("hourly", "batch", "listener")


def format_status(job_name: str, row: dict | None) -> str:
    if row is None:
        return f"{job_name}: never ran"
    status = "ok" if row["ok"] else "FAILED"
    detail = f" ({row['detail']})" if row["detail"] else ""
    return f"{job_name}: {status} at {row['ran_at']}{detail}"


def main(db_path=None) -> None:
    db_path = db_path or DEFAULT_DB_PATH
    conn = db.get_connection(db_path)
    for job_name in JOB_NAMES:
        print(format_status(job_name, heartbeat.last(conn, job_name)))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
