# PRD — Durable persistence of the base upscaled artwork

**Date:** 2026-07-17
**Status:** Open questions resolved (§8) — awaiting final go before build
**Owner:** Quentin
**Supersedes/relates:** SPEC_v4.11.md §3 (generate/upscale), the expiry note
already in `pipeline/group_product.py` (~L199), live-test-fixes brainstorm
(2026-07-16).

---

## 1. Problem

The only durable-looking reference to a candidate's true source artwork — the
upscaled 300-DPI master — is `candidates.base_image_url`, which stores a
Replicate **`replicate.delivery`** URL returned by `replicate_client.upscale_image`
(written in `generate.py`).

That URL is not durable. Confirmed via Replicate docs (2026-07):

- API-prediction output URLs expire **1 hour** after the prediction (not the
  ~2h assumed).
- At that same 1-hour mark Replicate deletes the prediction's inputs, outputs,
  output files and logs by default.

A design routinely sits **hours to days** between generation and Telegram
approval. By publish time the URL is dead. Two concrete failures follow:

1. **Gelato print submission breaks.** `create_product_from_template` is passed
   `image_url: candidate["base_image_url"]`, which **Gelato fetches
   server-side** at create time. A dead URL means Gelato cannot pull the print
   file. The existing fallback to `candidate["base_image_url"]` in
   `group_product.py` is fetching a corpse.
2. **No archive exists.** If anything downstream needs the master again
   (re-crop, re-list, dispute, portfolio, future reuse), it's simply gone.

The previously-suggested fix — Replicate **Files API** — does not solve this:
those uploads expire after **24h** and exist to feed files *into* models as
inputs, not to archive outputs. It's a longer-lived band-aid that keeps the most
important asset coupled to Replicate's lifecycle. Rejected.

## 2. Success criteria

- **SC1 — Survives the wait.** The base master is retrievable at a stable,
  public HTTPS URL from the moment of generation until at least the last group's
  Gelato create completes, independent of Replicate's 1h window.
- **SC2 — Gelato fetches durable, never Replicate.** Every
  `create_product_from_template` call sends a durable URL. A `replicate.delivery`
  URL reaching a real (non-dry-run) Gelato create **fails loudly** (mirrors the
  placeholder-ID fail-loud rule in CLAUDE.md).
- **SC3 — Permanent local archive.** Every generated master is also written to a
  local archive on the desktop, keyed by candidate, and is never auto-deleted by
  the pipeline.
- **SC4 — Integrity + idempotency.** Each master has a stored SHA256; re-runs
  don't duplicate or corrupt, and a completed persist is reused rather than
  redone.
- **SC5 — Vendor-swappable.** Storage sits behind a thin interface so
  local-only, R2, or S3 are config/credential swaps, not code rewrites — no new
  hard coupling to replace the old one.

## 3. Scope

### In
- New capture step in the **generate stage**: download the upscaled bytes while
  the Replicate URL is still live, then persist.
- New `pipeline/artwork_store.py` helper with a small backend abstraction:
  `local` (always) + `r2` (S3-compatible).
- Schema change on `candidates`: durable URL, local archive path, SHA256.
- Repointing `base_image_url` semantics from "Replicate delivery URL" to
  "durable public URL"; keeping the raw Replicate URL only as a disposable
  debug field.
- Guard that blocks a `replicate.delivery` URL from reaching real Gelato create.
- Config/env for R2 credentials + archive root; dry-run path for tests.
- Unit + M1 manual test coverage.

### Out (not this PRD)
- Migrating existing dead rows (there's no recoverable source for already-expired
  candidates — they re-generate).
- Backing up mockups/crops/lifestyle images (Gelato already rehosts those; only
  the *base master* is the irreplaceable source).
- Switching Gelato to file-upload instead of URL-fetch (kept as an alternative in
  Open Questions).
- A public-facing CDN, resizing, or serving art anywhere other than to Gelato.

## 4. Constraints & alignment with existing hard rules

- **Generate-once still holds.** Persist is keyed by `candidate_id` and runs
  inside the single generate call; group-level crop/critic retries reuse the
  stored master and never re-generate or re-persist (CLAUDE.md hard constraint).
- **Flat full-bleed master unchanged.** This PRD only moves bytes; it never
  touches the prompt or the artwork itself.
- **Discrete scheduled functions.** Capture lives in the existing generate
  function — no new daemon, no persistent service.
- **SQLite is the store.** New fields are columns on `candidates`, not a flat
  file. The local archive lives alongside the DB (same persistent disk that
  already holds `db/qhoto.sqlite3` and `db/group_preview_images/`).
- **Secrets in `.env`.** R2 credentials read from `.env` (git-ignored), never
  committed — same handling as the Gelato/Etsy/Telegram secrets.
- **Reuse existing patterns.** `http.fetch_bytes` for download; the local-path
  convention already established by `image_crop.crop_for_group`
  (`db/group_preview_images/{id}.jpg`) — mirror it with `db/base_artwork/`.

## 5. Design

### 5.1 Capture point (`pipeline/generate.py`)
Immediately after `replicate_client.upscale_image(...)` returns (URL live), and
before the `UPDATE candidates` write:

1. `raw = http.fetch_bytes(upscaled["image_url"])`
2. `result = artwork_store.persist_base_artwork(candidate_id, raw)`
3. Write to `candidates`:
   - `base_image_url` = `result.durable_url`  ← now the durable URL
   - `base_image_local_path` = `result.local_path`
   - `base_image_sha256` = `result.sha256`
   - `base_replicate_delivery_url` = `upscaled["image_url"]`  ← disposable, debug only
   - (existing `base_*_prediction_id` unchanged)

Because every downstream consumer already treats `base_image_url` as "a
fetchable URL for the master" (`primary_mockup.py`, `group_product.py`,
`image_crop.crop_for_group`), repointing it to the durable URL fixes them all
with **zero consumer changes** — the Gelato fallback stops fetching a corpse
automatically.

### 5.2 `pipeline/artwork_store.py` (new, thin)
```
persist_base_artwork(candidate_id, raw_bytes) -> {durable_url, local_path, sha256}
```
- Compute SHA256.
- **Local backend (always on):** write `db/base_artwork/{candidate_id}.png`
  (archive root configurable). Skip re-write if file exists with matching hash.
- **R2 backend (when configured):** idempotent `put` to key
  `base/{candidate_id}.png`; if the object already exists, reuse it (don't
  re-upload). Return `{R2_PUBLIC_BASE_URL}/base/{candidate_id}.png`.
- Backend selected by config/env; a `dry_run`/no-R2 mode returns a `file://` or
  local path as the "durable" URL so tests and offline dev never need R2.
- Kept deliberately small (ponytail): one module, one interface, no framework.

### 5.3 Guard (SC2)
In the Gelato create path (`group_product.py` / `gelato_client.py`), before a
real create, assert the outgoing `image_url` does **not** contain
`replicate.delivery`; raise a clear error if it does. Skipped in dry-run.

### 5.4 Schema change
`ALTER TABLE candidates ADD COLUMN` for `base_image_local_path`,
`base_image_sha256`, `base_replicate_delivery_url`; update `db/schema.sql` and
add a one-off migration. Back up `db/qhoto.sqlite3` first (convention already in
the repo).

### 5.5 Lifecycle / cleanup
- **Local archive:** permanent. `cleanup.py` never deletes `db/base_artwork/`.
- **R2 object:** only needs to survive until the candidate's last group has been
  created on Gelato (Gelato rehosts; Etsy pulls from Gelato). Default for v1:
  **retain** (cost is trivial). Optional later optimization: prune the R2 object
  when the candidate reaches a terminal published/killed state, making R2 a
  durable *staging* layer and the desktop the permanent archive. Flagged as a
  decision, not built in v1.

### 5.6 Applicability to the custom-mockup addendum (SPEC_v4.10 Addendum A)

The addendum's self-hosted compositor produces ~10 mockups per scene set (up to
~30 per design across the three groups). **They reuse the same `artwork_store`
helper and archive convention, but default to local-only — not R2.** Reasoning,
grounded in the current code:

- **They need no public URL.** The only reason R2 is load-bearing for the base
  master is Gelato fetching it server-side. Every mockup consumer takes *bytes or
  a local path*, not a URL: `etsy_client.upload_listing_image(image_bytes=...)`
  is a multipart byte upload; `telegram_client.send_media_group` already uploads
  local paths as multipart attachments (the existing `image_crop` crop path);
  the critic pass reads local files via `anthropic_client`. So mockups never
  need to be publicly hosted.
- **They're derived and regenerable.** A mockup is a deterministic function of
  (durable base master + static scene bundle in `assets/mockups/` + the
  compositor). Once this PRD guarantees the base is durable, any mockup can be
  re-rendered offline for €0. The base master is the only irreplaceable asset;
  mockups don't need R2's durability to be recoverable.
- **They're the bulk, and R2 is capacity-capped for now.** ~30 mockups/design
  vs. 1 base means routing mockups to R2 would hit the 10 GB free tier ~30×
  faster — for zero durability benefit — directly working against the
  "retain, revisit at 10 GB" decision.

Net: `artwork_store` gets a local archive root for mockups (e.g.
`db/mockups/<group_product_id>/<rank>.jpg`, mirroring `db/base_artwork/` and the
existing `db/group_preview_images/`); the R2 backend stays reserved for the base
master. If a future need arises to serve a mockup by URL, generate a short-lived
signed URL at upload time rather than durably hosting it. This is recorded here
so the addendum's implementation inherits a settled storage stance; it is **not**
built as part of this PRD.

## 6. Cost

Negligible and not the deciding factor. Cloudflare R2: ~$0.015/GB-month,
**zero egress** (matters — Gelato + any re-fetch read repeatedly), 10 GB free.
Even at 30 masters/day × ~15 MB that's ~13 GB/month of growth ≈ a couple euros a
year before any pruning. R2 chosen over S3 for zero egress and over Backblaze B2
for S3-API ubiquity; all three remain swappable via the backend interface.

## 7. Plan (build order, each independently testable per repo convention)

1. `artwork_store.py` + unit tests (local backend, hashing, idempotency) — no
   network.
2. R2 backend behind the same interface + env wiring in `config.py` /
   `.env.example`; dry-run mode.
3. Schema migration + `schema.sql` update (+ DB backup).
4. Wire capture into `generate.py`; repoint `base_image_url`; update
   `tests/test_generate.py`.
5. Gelato `replicate.delivery` guard + test.
6. M1 manual run: generate one candidate → confirm R2 object + local archive +
   three populated columns → dry-run Gelato create receives the durable URL.
7. CHANGELOG + spec note (SPEC §3) that `base_image_url` now means "durable URL".

## 8. Open questions — resolved 2026-07-17

1. **R2 vs. avoid a new vendor:** ✅ **R2.** A setup how-to is a build
   deliverable (see `docs/r2-setup-guide.md`).
2. **R2 object retention:** ✅ **retain for now** — revisit only once fully live
   and approaching the 10 GB free tier, at which point pruning-on-terminal-state
   is the lever.
3. **Archive format/location:** ✅ default location is good —
   `db/base_artwork/{candidate_id}.png`, same disk as the DB.
4. **Public vs. signed R2 URLs:** ✅ **non-listable public bucket** dedicated to
   base artwork.

## 9. Deliverables checklist (on build)

- [ ] `docs/r2-setup-guide.md` — account, bucket, non-listable public access,
      credentials into `.env` (drafted 2026-07-17, ahead of build).
- [ ] `pipeline/artwork_store.py` + tests.
- [ ] Schema migration + `schema.sql` + DB backup.
- [ ] `generate.py` capture wiring + `test_generate.py` update.
- [ ] Gelato `replicate.delivery` guard + test.
- [ ] M1 manual run verification.
- [ ] CHANGELOG + SPEC §3 note.
```
