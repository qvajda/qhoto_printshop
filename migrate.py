"""GL-35: the single idempotent entrypoint that applies every pending
migrate_*.py script in order and records progress in schema_version. Each
migrate_*.py script is independently idempotent (safe to call migrate() any
number of times) - this runner adds ordering and a version record so
"has this DB been migrated" is a single fast SELECT, not re-running every
script's own internal existence checks on every cron cycle.

check(db_path) is the fail-fast guard both entrypoints call before doing
anything else: it never writes, it only compares schema_version.version
against len(MIGRATIONS) and raises if the DB is behind. Discovering a stale
schema three stages into an unattended batch run (GL-13's failure mode) is
worse than refusing to start.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pipeline.artwork_store as artwork_store
import pipeline.db as db
import migrate_base_artwork_columns
import migrate_candidates_art_brief
import migrate_candidates_dominant_colour
import migrate_critic_pass_attempts_columns
import migrate_generation_attempts_table
import migrate_gl31_reminder_sent_at
import migrate_gl32_create_intent
import migrate_gl36_listing_missing
import migrate_gl45_db_identity
import migrate_gl51_relative_artefact_paths
import migrate_group_products_candidate_id
import migrate_pending_decisions
import migrate_v412_gallery

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

# (version, name, migrate(db_path) callable). Order matters: each is applied in
# sequence and the recorded version is the count of entries applied so far, not
# a semantic release number. Append new migrations here - never reorder or
# remove past entries, or an already-migrated DB's recorded version becomes
# meaningless.
MIGRATIONS = [
    (1, "base_artwork_columns", migrate_base_artwork_columns.migrate),
    (2, "candidates_art_brief", migrate_candidates_art_brief.migrate),
    (3, "critic_pass_attempts_columns", migrate_critic_pass_attempts_columns.migrate),
    (4, "generation_attempts_table", migrate_generation_attempts_table.migrate),
    (5, "group_products_candidate_id", migrate_group_products_candidate_id.migrate),
    (6, "v412_gallery", migrate_v412_gallery.migrate),
    (7, "gl36_listing_missing", migrate_gl36_listing_missing.migrate),
    (8, "gl45_db_identity", migrate_gl45_db_identity.migrate),
    (9, "pending_decisions", migrate_pending_decisions.migrate),
    (10, "gl51_relative_artefact_paths", migrate_gl51_relative_artefact_paths.migrate),
    (11, "candidates_dominant_colour", migrate_candidates_dominant_colour.migrate),
    (12, "gl31_reminder_sent_at", migrate_gl31_reminder_sent_at.migrate),
    (13, "gl32_create_intent", migrate_gl32_create_intent.migrate),
]


class StaleSchemaError(Exception):
    pass


def _current_version(conn) -> int:
    # C1 fix: on a real production DB that predates db/schema.sql's
    # schema_version/heartbeats additions, this table doesn't exist at all (not
    # just an empty row) - check() must still read this as version 0 and raise
    # StaleSchemaError, never leak the raw OperationalError.
    try:
        row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row[0] if row else 0


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        # C1 fix: bootstrap schema_version/heartbeats (and every other table in
        # db/schema.sql) before anything else. The real qhoto.sqlite3 only ever
        # went through the individual migrate_*.py scripts, never
        # pipeline.db.init_db() - every CREATE TABLE in schema.sql is
        # IF NOT EXISTS, so this is a safe no-op on an already-current DB.
        db.init_db(conn)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)"
        )
        conn.commit()
        current = _current_version(conn)

        applied = []
        for version, name, migrate_fn in MIGRATIONS:
            if version <= current:
                continue
            migrate_fn(db_path)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
            conn.commit()
            applied.append(name)
            current = version

        return {"applied": applied, "current_version": current}
    finally:
        conn.close()


def post_merge(db_path) -> dict:
    """GL-... : the attended step a `post-merge` git hook calls so a migration
    appended to MIGRATIONS reaches the live DB the moment the merge that added
    it lands, instead of waiting for a human to remember `migrate.py`.

    Two skips, both load-bearing:
    - missing file: sqlite3.connect() creates a file on open, so without this
      check a pull inside any worktree (`.qops/wt/<name>`) would fabricate a
      fresh db/qhoto.sqlite3 there.
    - non-canonical file (db_identity.canonical_path set and different from
      this path, same check as pipeline.db.assert_canonical): a pull inside a
      restored .bak-* checkout must never migrate that copy as if it were the
      live DB.
    """
    resolved = Path(db_path).resolve()
    if not resolved.exists():
        return {"skipped": "missing", "applied": [], "current_version": None}

    conn = sqlite3.connect(db_path)
    try:
        try:
            row = conn.execute(
                "SELECT canonical_path FROM db_identity WHERE id = 1"
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
    finally:
        conn.close()
    if row and row[0] and os.path.normcase(os.path.realpath(row[0])) != os.path.normcase(str(resolved)):
        return {"skipped": "non-canonical", "applied": [], "current_version": None}

    result = migrate(db_path)
    result["skipped"] = None
    return result


def check(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        current = _current_version(conn)
        expected = len(MIGRATIONS)
        if current < expected:
            raise StaleSchemaError(
                f"schema_version is {current}, expected {expected} - run migrate.py before starting"
            )
        return current
    finally:
        conn.close()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    db_path = Path(args[0]) if args else DEFAULT_DB_PATH
    if "--bless" in sys.argv:
        print(f"canonical_path={migrate_gl45_db_identity.bless(db_path)}")
        return
    if "--check-artefacts" in sys.argv:
        report = artwork_store.sweep_artefacts(db_path)
        print(
            f"resolvable={report['resolvable']}, "
            f"missing={len(report['missing'])}, skipped={report['skipped']}"
        )
        for row in report["missing"]:
            print(f"{row['table']} {row['row_id']} {row['value']}")
        sys.exit(1 if report["missing"] else 0)

    check_only = "--check" in sys.argv
    if check_only:
        version = check(db_path)
        print(f"schema_version={version}, up to date")
        return
    if "--post-merge" in sys.argv:
        result = post_merge(db_path)
        if result["skipped"]:
            print(f"skipped: {result['skipped']}")
            return
        if result["applied"]:
            print(f"applied: {', '.join(result['applied'])}")
        else:
            print("nothing to apply")
        print(f"schema_version={result['current_version']}")
        return
    result = migrate(db_path)
    if result["applied"]:
        print(f"applied: {', '.join(result['applied'])}")
    else:
        print("nothing to apply")
    print(f"schema_version={result['current_version']}")


if __name__ == "__main__":
    main()
