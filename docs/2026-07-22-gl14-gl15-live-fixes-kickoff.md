# Implementation kickoff — GL-14 + GL-15 (live-findings fix cluster) — 2026-07-22

Ready-to-paste prompt for a **Claude Code session**. Both items were found live
in the v4.11 Round-1 test (GL-9); see `docs/2026-07-22-go-live-plan-of-attack.md`
(GL-14, GL-15) and the bug writeup
`docs/2026-07-22-group-crop-not-sent-to-gelato-bug.md`.

Pair these two in one small branch. **GL-16 (resilience hardening) is a
separate, larger branch — do not fold it in here.**

---

## PROMPT — paste from here down

You are fixing two bugs found during the v4.11 Round-1 live test, in the
qhoto_printshop repo. Read first, in order: `CLAUDE.md` (hard constraints —
v4.11), `docs/2026-07-22-group-crop-not-sent-to-gelato-bug.md` (GL-14 full
writeup + fix shape), and the GL-14/GL-15 rows in
`docs/2026-07-22-go-live-plan-of-attack.md`. Don't guess at behavior already
specified.

### Method — SDD, same convention as the base-artwork / live-readiness branches

Follow `.superpowers/sdd/progress.md`:
- Branch off master: `fix/live-findings-crop-and-token`. **Stage 0:** confirm
  the tree is clean and the full suite is green; record the baseline count.
- One task = one commit; task brief before, task report after, append to a new
  `.superpowers/sdd/` ledger (don't touch prior ones).
- Full suite green after every task — a task isn't done below full green.
- Final whole-branch review (fresh reviewer pass over the full diff) before
  merge; fix + re-review findings.

### Hard rules (CLAUDE.md + reversibility)

- **No real external calls without explicit per-call go-ahead.** All dev runs
  use dry-run flags (`GELATO_LIVE_MODE`/`ETSY_LIVE_MODE` unset) or mocks. The
  only live step is Task 3, which is proposal-then-STOP.
- **Never `create_draft_listing`** — Gelato pushes, we patch.
- **All Gelato creates stay routed through
  `group_product.create_or_reuse_group_product`** — don't fork a second create
  path.
- The create-path **fail-loud guards stay** (placeholder template ID, outgoing
  `replicate.delivery` URL, <150 DPI) — the new crop must *clear* them, not
  bypass them.
- **No `urllib` in `pipeline/`** (grep-test it — a prior task's claim to have
  removed it quietly regressed once). Route every HTTP call through
  `pipeline/http.py`.
- `TELEGRAM_ADMIN_CHAT_ID` stays env-only.
- If a fix seems to need changing a CLAUDE.md hard constraint, **stop and
  raise it** — don't edit the constraint.

### Task 1 — GL-14: send a real cover-crop to Gelato for 5x7 / 10x24

**Bug:** `group_product.create_or_reuse_group_product` passes the full uncropped
`candidate["base_image_url"]` to `create_product_from_template` for *every*
group type. Gelato then letterboxes it into the target ratio → the 10x24
white-bar defect the v4.11 group flow was meant to kill. `image_crop.cover_crop`
/ `target_ratio_for_group_type` are correct but currently feed only the
downsized Telegram *preview* thumbnail (`crop_for_group`,
`PREVIEW_MAX_EDGE=2000`), never the print file.

Fix (per the writeup §"Fix shape"):
1. For `5x7` and `10x24` group types, produce a **full-resolution** (print-DPI,
   *not* the 2000px preview) cover-crop of the master using the existing
   `image_crop.cover_crop(image, target_ratio_for_group_type(group_type))`.
   Do **not** reuse `crop_for_group()` as-is — its `thumbnail()` downsize must
   stay preview-only. Factor the shared crop math so both the print crop and the
   preview crop call the same `cover_crop`, but only the preview downsizes.
2. **Host the print crop at a durable URL Gelato can fetch.** Reuse the R2
   infra in `pipeline/artwork_store.py` (mirror `persist_base_artwork` /
   `_r2_put_object`); add an idempotent helper keyed e.g.
   `base/{candidate_id}_{group_type}_crop.png` (skip re-upload on matching
   content, same as base artwork). If R2 isn't configured, fail loud on a real
   create for these group types — do **not** silently fall back to the uncropped
   master (that's the bug).
3. Pass that hosted crop URL as `image_url` for `5x7`/`10x24`. It must still
   satisfy the create-path guards (no `replicate.delivery`; ≥150 DPI at the
   group's largest size).
4. **Primary group (8x12/A3/A2/A1, ISO A-series):** CLAUDE.md frames this as
   "a small crop, not a re-composition," so it *may* keep the raw master —
   but **verify** it clears the DPI guard and doesn't itself letterbox at the
   A-series ratio before assuming it's fine. State the finding in the report; if
   it does letterbox, crop it too.
5. Keep `create_or_reuse_group_product` idempotent end-to-end (reuse stored
   `gelato_product_id`; the hosted crop is idempotent too).

Tests: `cover_crop` fills the target ratio with no letterbox for both 5x7 and
10x24 (assert output ratio == target, no added margin); the print crop is
full-res (not capped at 2000px); the crop URL — not the raw master — is what
reaches `create_product_from_template` for non-primary groups (mock the Gelato
call, assert the `image_url`); R2-absent + real create for a secondary group
fails loud; preview path unchanged.

### Task 2 — GL-15: Etsy OAuth auto-refresh on 401

**Bug:** the Etsy access token expired mid-round; nothing in the pipeline
refreshes it (`refresh_etsy_token.py` is a manual standalone using `urllib`).
Unattended cron can't hand-fix this.

Fix:
1. Add a shared refresh function (new `pipeline/etsy_auth.py`, or inside
   `etsy_client.py`) that does the `refresh_token` grant against
   `https://api.etsy.com/v3/public/oauth/token` **via `pipeline/http.py`, not
   `urllib`**, returns the new `access_token`, and **persists the (possibly
   rotated) `refresh_token`** — Etsy rotates it, and dropping the new one breaks
   the *next* refresh. Update both `.env` and `os.environ` so in-process callers
   see the new token (`refresh_etsy_token.py`'s `set_env_var` logic is reusable;
   have the standalone script call the shared function so there's one code path).
2. Wrap the authenticated Etsy calls so a **401 triggers one refresh + one
   retry** with the new token (the calls that carry `Authorization: Bearer` —
   `update_listing`, `update_listing_inventory`, `upload_listing_image`,
   `update_listing_state` even if unused, `resolve_etsy_listing_id`'s reads,
   etc.). `http.send` raises `HTTPError` with `status_code` — catch 401 there or
   in a thin wrapper. Refresh at most once per call to avoid loops.
3. Propagate the refreshed token to in-flight call sites: today
   `publish_primary_group` threads `etsy_access_token=` through every call, read
   once at startup. Choose the cleanest propagation — a small in-process token
   holder the Etsy client reads, or re-reading `ETSY_ACCESS_TOKEN` from env after
   refresh — and note the choice in the report. Don't scatter refresh logic per
   call site.

Tests: a mocked 401 → refresh called once → original call retried with the new
token → succeeds; a rotated `refresh_token` is persisted to `.env`; a second
401 after a refresh does **not** loop; no `urllib` remains in `pipeline/`
(grep-test); dry-run/mocked throughout (no live token call in the suite).

### Task 3 — live verification (STOP — go-ahead gate)

No code beyond the checklist. Produce it, then wait for explicit approval.
- **State cleanup (reversibility — user-gated deletes):** candidate 39's
  group_products 11 (5x7, `1bc0abf3-…`) and 12 (10x24, `5c9be5ec-…`) are live
  on Gelato, `created`, with the *uncropped* image. They must be **DELETEd and
  recreated** once the fix lands — name each `DELETE` before firing.
- Re-run `group_mockup` for candidate 39's (or a fresh candidate's) 5x7 + 10x24
  and confirm **both** crops fill the frame with no white bars — at the Gelato
  preview level and, if feasible, by checking the submitted image ratio. (5x7's
  old preview *looked* fine only because it was the local thumbnail, not what
  Gelato printed — re-verify it too.)
- For GL-15, a full live token-expiry test is impractical to force; rely on the
  unit proof here and fold a real-token smoke into the next live pass. **This
  Task 3 crop re-verification is a natural fit to run inside GL-13/GL-17
  (Round 2 + residuals)** rather than a standalone live session — flag that.
- Failure protocol: incident note to `.remember/today-2026-07-22.md` first
  (what failed, stage, exact error/CF-Ray/API response, state left behind with
  ids), then a resume prompt in `docs/` if diagnosable; end with a handoff.

### Explicitly deferred — do NOT build here

- **GL-16 resilience hardening** (retry/backoff, self-healing state) — separate
  branch; do not add retry logic beyond GL-15's single refresh-retry here.
- Any mockup/compositor work (GL-4/GL-5).

### Definition of done

Suite green throughout; for `5x7`/`10x24`, the image reaching Gelato is a
full-res cover-crop hosted on R2 that fills the frame (proven in unit tests, live
re-verification checklist ready); a mocked Etsy 401 auto-refreshes + retries with
a persisted rotated refresh token; no `urllib` in `pipeline/`; whole-branch
review clean; live steps individually pre-approved; failure protocol + handoff
apply regardless of outcome.
