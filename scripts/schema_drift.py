"""`qops doctor` check: the live DB has every table/column db/schema.sql declares.

Moved out of the substrate in qops v0.5.0 (qops#210) and registered back via
`doctor_checks:` in `.qops/config.yml`. schema.sql is all
`CREATE TABLE IF NOT EXISTS`, so a column added there is a silent no-op
against a table that already exists - GL-32 (#160) shipped a migration nothing
ran and nothing checked for. A missing live DB (fresh checkout, CI) is not
drift; there is nothing to compare against.
"""

import re
import sqlite3
from pathlib import Path

SCHEMA_SQL = "db/schema.sql"
LIVE_DB = "db/qhoto.sqlite3"

_CREATE_TABLE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);",
                           re.DOTALL)
_TABLE_LEVEL = ("UNIQUE(", "UNIQUE (", "FOREIGN KEY", "CHECK(", "CHECK (",
                "CONSTRAINT", "PRIMARY KEY(", "PRIMARY KEY (")


def _split_top_level(body: str) -> list[str]:
    """Comma-separated clauses, ignoring commas nested inside `CHECK(...)`."""
    clauses, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            clauses.append(body[start:i])
            start = i + 1
    clauses.append(body[start:])
    return clauses


def _declared_schema(schema_sql: str) -> dict[str, set[str]]:
    declared = {}
    for table, body in _CREATE_TABLE.findall(schema_sql):
        declared[table] = {c.strip().split()[0] for c in _split_top_level(body)
                           if c.strip() and not c.strip().startswith(_TABLE_LEVEL)}
    return declared


def schema_drift(root, cfg=None, db_path=None) -> list[str]:
    root = Path(root)
    db_path = Path(db_path) if db_path is not None else root / LIVE_DB
    if not db_path.exists():
        return []
    declared = _declared_schema((root / SCHEMA_SQL).read_text(encoding="utf-8"))
    problems = []
    conn = sqlite3.connect(str(db_path))
    try:
        for table, columns in declared.items():
            live = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not live:
                problems.append(f"schema drift: table `{table}` is in {SCHEMA_SQL} "
                                f"and missing from the live DB")
                continue
            for col in sorted(columns - live):
                problems.append(f"schema drift: `{table}.{col}` is in {SCHEMA_SQL} "
                                f"and missing from the live DB - run its migration")
    finally:
        conn.close()
    return problems
