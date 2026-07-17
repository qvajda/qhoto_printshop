# Claude Code prompt — implement base-artwork persistence (PRD 2026-07-17)

> Paste everything below the line into a fresh Claude Code session started from
> the `qhoto_printshop` repo root. `.env` already contains the real R2
> credentials. The PRD is approved; this is a build task, not a design task.

---

You are implementing an **approved PRD** in this repo. Do not redesign it — build
what it specifies. Work stage by stage, run tests after each stage, and commit
per stage (repo convention).

## Read first (in this order)
1. `docs/superpowers/specs/2026-07-17-base-artwork-persistence-prd.md` — the spec you're building. Follow §5 (design), §7 (build order), §8/§9 (locked decisions + deliverables).
2. `docs/r2-setup-guide.md` — bucket/URL model. The Cloudflare side is already done; `.env` is populated.
3. `CLAUDE.md` (root + repo) and `docs/SPEC_v4.11.md` §3–4 — the hard constraints below come from here.

## Non-negotiable constraints (violating any of these is a bug)
- **Zero new runtime dependencies. Stdlib only.** The whole codebase talks HTTP via `urllib` + `pipeline/http.py`; every client (`gelato_client`, `etsy_client`, `telegram_client`) hand-rolls its requests. **Do NOT add boto3/botocore or any package.** Implement the R2 (S3-compatible) auth with a small, isolated **AWS SigV4 signer using `hmac`/`hashlib`**. Keep it in one place so boto3 remains a future escape hatch if ever needed.
- **`base_image_url` changes meaning: it now holds a durable public URL, not a Replicate delivery URL.** Every existing consumer already treats it as "a fetchable URL for the master" (`primary_mockup.py`, `group_product.py`, `image_crop.crop_for_group`), so repointing it fixes them with no consumer changes. Verify that assumption while you work.
- **Generate-once invariant.** Persistence happens inside the single generate call, keyed by `candidate_id`; group-level crop/critic retries must never re-generate or re-persist. Don't touch the artwork or the FLUX.1 [schnell] prompt.
- **Secrets from `.env` only** (already populated; git-ignored). Never hardcode, never commit.
- **Fail-loud, mirroring the placeholder rule:** a `replicate.delivery` URL reaching a real (non-dry-run) Gelato create must raise a clear error, never proceed.
- **One module per stage, independently testable. Commit after each stage passes its tests.** Use dry-run/mock for anything external while iterating.

## Env vars already in `.env`
`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
`R2_ENDPOINT`, `R2_PUBLIC_BASE_URL` (and an unused `R2_TOKEN` — the S3 SigV4 path
uses ACCESS_KEY_ID + SECRET_ACCESS_KEY + ENDPOINT, not the token). If R2 vars are
absent, the code must degrade to **local-only** (dry-run) so tests and offline dev
never need R2.

## Build stages

### Stage 0 — Reset ghost state (do this first, it's the reason for a clean start)
Every existing row in `db/qhoto.sqlite3` from prior test runs points at
Replicate delivery URLs that **expired long ago** — the base masters no longer
exist anywhere, so under the new durable-URL contract those rows are
unrecoverable ghosts. Do **not** try to migrate or backfill them.
- Back up the current DB (e.g. `db/qhoto.sqlite3.bak-<date>-pre-persistence`).
- Drop and recreate the database empty from `db/schema.sql` (after Stage 3's
  schema change is in), so the first real run starts clean.
- Also clear local derived-image caches tied to those ghosts:
  `db/base_artwork/` (new), `db/group_preview_images/` (existing crop cache).
- **External test artifacts (flag, don't auto-delete):** if prior runs created
  Gelato products or Etsy draft listings, list them and ask me before deleting —
  those are external-account actions (reversibility rule). Prefer the existing
  Gelato delete path / dry-run.

### Stage 1 — `pipeline/artwork_store.py`, local backend
`persist_base_artwork(candidate_id, raw_bytes) -> {"durable_url", "local_path", "sha256"}`.
- SHA256 of bytes.
- Local archive write to `db/base_artwork/<candidate_id>.png` (mirror the
  `image_crop` local-path convention). Skip re-write if the file exists with a
  matching hash (idempotent).
- Backend selection from env; a no-R2/dry-run mode returns the local path (or
  `file://`) as `durable_url`.
- Unit tests: write, idempotent re-run, dry-run return shape.

### Stage 2 — R2 backend (stdlib SigV4) in `artwork_store.py`
- S3-compatible `PUT` + `HEAD` to `R2_ENDPOINT`, bucket `R2_BUCKET`, key
  `base/<candidate_id>.png`.
- Idempotent: `HEAD` first; if the object exists, reuse it (no re-upload). On a
  failed-create retry, don't leave a corrupt object.
- Return `f"{R2_PUBLIC_BASE_URL}/base/<candidate_id>.png"`.
- SigV4 signer isolated (its own function/section). Unit-test it for
  deterministic canonical-request / string-to-sign / signature output against
  fixed inputs (ideally an AWS SigV4 published test vector). The live proof is
  the Stage 7 healthcheck.

### Stage 3 — Config + schema
- `config.py`: helpers to read the R2 env group and the archive root; treat
  missing R2 config as local-only.
- Schema: `ALTER TABLE candidates ADD COLUMN` for `base_image_local_path`,
  `base_image_sha256`, `base_replicate_delivery_url`. Update `db/schema.sql`.
  Provide an idempotent migration path (and remember Stage 0 recreates the DB
  from the updated schema anyway).

### Stage 4 — Wire capture into `pipeline/generate.py`
Right after `replicate_client.upscale_image(...)` returns (URL still live) and
before the `UPDATE candidates` write:
1. `raw = http.fetch_bytes(upscaled["image_url"])`
2. `result = artwork_store.persist_base_artwork(candidate_id, raw)`
3. Write columns: `base_image_url = result["durable_url"]`,
   `base_image_local_path = result["local_path"]`,
   `base_image_sha256 = result["sha256"]`,
   `base_replicate_delivery_url = upscaled["image_url"]` (disposable/debug).
Update `tests/test_generate.py`: the existing tests assert
`base_image_url == "https://replicate.delivery/..."` — those assertions must
change to the durable URL, and the fetch/persist must be mocked so tests stay
offline. Preserve the "upscale fails → row untouched" behavior.

### Stage 5 — Gelato guard
In the Gelato create path (`pipeline/group_product.py` /
`pipeline/gelato_client.py`), before a real create, assert the outgoing
`image_url` contains no `replicate.delivery`; raise a clear error otherwise.
Skip the assertion in dry-run. Add a test.

### Stage 6 — Full suite green
Run the entire `pytest` suite; everything passes, no skips introduced. Fix any
consumer that turns out to depend on the old `base_image_url` semantics.

### Stage 7 — Healthcheck + docs + commits
- A small healthcheck script (per `docs/r2-setup-guide.md` §7): `PUT`
  `base/_healthcheck.png`, `GET` it back via `R2_PUBLIC_BASE_URL` (200 + bytes
  match), and confirm `GET {R2_PUBLIC_BASE_URL}/` returns **no listing**. Run it
  against live R2 and report the result.
- `docs/CHANGELOG.md` entry; a note in `docs/SPEC_v4.11.md` §3 that
  `base_image_url` now means "durable public URL".
- Commit per stage with clear messages.

## Out of scope (do not build)
- The custom-mockup addendum (`docs/SPEC_v4.10_addendum_custom_mockups.md`).
  PRD §5.6 already rules that mockups stay **local-only** and reuse
  `artwork_store` later — don't implement that here.
- Backfilling old rows (see Stage 0 — they're dropped, not migrated).

## Definition of done
1. Full `pytest` suite green.
2. Live R2 healthcheck passes (PUT/GET round-trip + no bucket listing).
3. A dry-run generate on a fresh candidate yields: an R2 object at
   `base/<id>.png`, a local archive file at `db/base_artwork/<id>.png`, and all
   three new columns populated, with `base_image_url` = the durable R2 URL.
4. The Gelato guard rejects a `replicate.delivery` URL on a real create.
5. Old ghost DB reset; no row references an expired Replicate URL.
6. No new runtime dependency added (stdlib only); `git diff` shows a clean,
   per-stage commit history.

Ask me before any external-account deletion (Gelato/Etsy). Everything else,
proceed autonomously and show me the diff + test output at the end.
