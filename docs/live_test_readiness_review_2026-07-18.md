# Live-test readiness review — 2026-07-18

Read-only review before live E2E run #2. Scope: what still stands between the
current tree and one clean, unattended end-to-end run (generate → primary
review → primary publish → 5x7/10x24 fan-out → their own review/publish),
beyond what's already logged as fixed. Baseline: CLAUDE.md (v4.11 hard
constraints), SPEC_v4.11, the 2026-07-16 brainstorm doc, the Cloudflare 1010
investigation, CHANGELOG tail, `.remember/today-2026-07-18.md`, `git log`/
`git status`, and a full source + test-suite pass. **Test suite: 316 passed,
0 failed, 0 skipped, 8.6s** (after installing pytest/httpx[http2]/pillow/
socksio in the sandbox — see finding C1 on why pillow isn't declared).

Verdict up front: the 1010 transport fix is real and mostly complete (shared
httpx client, honest UA, tested backoff), idempotency genuinely runs through
one shared helper now, config/secrets are clean. What blocks a clean run is
**not** the things already logged as fixed — it's (B1) no mechanism anywhere
to make an approved listing actually go *live* on Etsy, (B2) the unverified
Gelato dashboard fix for the 10x24 placeholder, (B3) a missed 3s-poll default
on the exact fan-out path the 1010 fix was for, and (B4/H2) residual
idempotency + stall paths that only bite when a run is unattended.

---

## ADDENDUM — 2026-07-18 evening, after owner's manual dashboard + artwork inspection

Supersedes parts of the findings below; finding IDs stay stable because the
kickoff prompt references them.

- **B1 reclassified: not a blocker — drafts are the intended state.**
  Owner confirmed manually that every Etsy publish so far landed as a
  **draft** — Open Q2's empirical half is now closed: `isVisibleInTheOnlineStore:
  False` works as documented, and the pre-review-leak defense holds. And the
  "fix" is inverted: Etsy charges **$0.20 per listing activation**, so during
  testing listings must *stay* drafts; activation is a manual dashboard
  decision per listing. Do NOT wire `update_listing_state("active")` into the
  patch. Residual work is documentation + a guard that nothing auto-activates
  (see kickoff Task 6), and an eventual production-time decision on
  activation that is explicitly out of scope now.
- **Meta-information confirmed correct** on the patched Etsy listings
  (title/tags/section/partner/etc.) — the v4.11 patch step works.
- **NEW B5 — print DPI shortfall above A4 (blocker for A3/A2/A1/10x24 legs).**
  Dashboard shows DPI too low for every variant above A4, down to ~135 DPI
  at A1. Grounded in code: FLUX schnell runs at `megapixels: "1"`, 2:3 →
  832×1216, ESRGAN `scale: 4` → **3328×4864** (verified: all 7 archived
  masters are exactly 3328×4864). At final print size that is ~416 DPI
  (8x12), ~285 (A3), ~201 (A2), **~142 (A1)** — vs. Gelato's stated minimum
  of **150 DPI, 300 ideal**, for posters. The `replicate_client.py:17-19`
  comment already conceded this ("A2/A1/10x24 need more linear scale"). Fix
  direction: larger upscale (ESRGAN `scale: 8` → 6656×9728 ≈ 284 DPI at A1,
  or a chained 4×→2× pass — the code session must verify Replicate-side
  output-size limits empirically), **plus a pre-create guard** that computes
  px ÷ largest-size-inches per group and fails loudly below 150 DPI —
  same fail-loud family as the placeholder/replicate-URL guards. Watch
  downstream: bigger masters inflate the local crop JPEGs (Telegram's ~5-10MB
  photo caps — a cap already bitten once, commit b3977d1) and R2 objects.
- **NEW H5 — generation quality: 5 of 7 masters are unusable, and the critic
  has never actually run.** Owner review of the 7 archived masters: #2 and
  #6 are near-empty cream gradients (no subject at all); #3 and #4 are line
  art but far too empty; #7 is completely off-center, mostly empty, subject
  nonsensical (half-chair/half-animal + palm trunk); #1 passable but the
  trunk/leaves design is incoherent and centering is off; #5 the best, but
  smudging around fine details — notable because the "clean zones of
  monocolor" style makes smudging conspicuous. DB fact: `critic_pass_attempts`
  is **empty** (mockups all failed on the 1010 block before any critic ran),
  so the rubric is unexercised, not merely insufficient — but by inspection
  it also checks none of these failure modes (no emptiness/centering/subject-
  coherence/smudge criteria). Fix is two-layered: **prevent** at generation
  (prompt must demand a single clear centered subject with substantial
  coverage) and **detect** at critic time (a zero-cost local pixel-statistics
  gate for near-empty images before spending a vision call, plus rubric
  criteria for emptiness, centering, subject coherence, and smudging), all
  inside the existing 3-attempt critic loop — no new retry budget
  (CLAUDE.md's one-generation-per-design rule refers to group-level
  crop/retry; critic-fail regeneration is the already-specified mechanic).
- **H3 sharpened: prune all 7 candidates.** Every one is condemned by the
  artwork review, so the pre-run triage is no longer "keep 1-2": back up,
  prune all 7, and let run #2 generate fresh candidates through the improved
  prompt + DPI pipeline.

---

## Blockers — would stop or corrupt an unattended E2E run

### B1. ~~Nothing ever promotes an Etsy listing from draft to active~~ — RECLASSIFIED, see Addendum (drafts are intended; activation is manual and costs $0.20)
Original analysis kept for the record; the *code evidence* (no
`update_listing_state` callers, flag hardcoded False) is accurate — only the
conclusion is inverted.

(brainstorm item 3 / Open Q2 — empirical half now closed by owner's manual check)
- **Root cause.** Every Gelato create hardcodes `isVisibleInTheOnlineStore:
  False` (`pipeline/gelato_client.py:113`) — correct pre-review, per Q2's
  finding that this syncs the listing as an Etsy *draft*. But approval never
  flips it: `group_product.patch_etsy_listing`
  (`pipeline/group_product.py:251-315`) patches title/description/tags/
  metadata/inventory and marks the group `published`, and never touches
  listing state. `etsy_client.update_listing_state`
  (`pipeline/etsy_client.py:84-102`) exists — evidently built for exactly
  this — and **has zero callers** in `pipeline/` (grep-verified).
- **Consequence.** If Gelato behaves as its docs say, every "published"
  listing in the E2E run lands as a draft and stays there — the run completes
  green while selling nothing. If instead the flag doesn't hold (live run #1
  leaked one live listing pre-review), the pre-review leak recurs on the
  primary mockup. Either branch fails the run; we don't know which branch is
  real because Q2's create→approve cycle was never verified.
- **Severity: blocker.**
- **Fix.** (1) Call `update_listing_state(shop_id, listing_id, "active")` at
  the end of `patch_etsy_listing`, after `update_listing_inventory`, gated on
  the same `dry_run`. (2) Keep `isVisibleInTheOnlineStore: False` at create
  time — that's the pre-review-leak defense. (3) **Requires one live
  verification** (needs your go-ahead, proposed as the last implementation
  step): one create→sync→inspect-listing-state→patch→activate cycle on a
  single test product, confirming (a) pre-patch state is `draft` (leak
  defense holds) and (b) the state PATCH flips it to active. Etsy is in
  Developer Mode, which bounds the blast radius. Consistent with CLAUDE.md's
  Gelato-pushes-we-patch constraint — activation is part of the patch, not a
  listing create.

### B2. 10x24 white-bars fix is a manual Gelato-dashboard task with no confirmation it happened (brainstorm item 5 / Open Q5 — still open)
- **Root cause.** Verified live 2026-07-16: all template placeholders are
  2:3 (match the source), and the white bars are the 10x24 variant's
  placeholder box (261×392mm) not spanning its 250×600mm page — a template
  property fixable only in Gelato Studio, not via API. The brainstorm ends
  with "user is checking/fixing this in the Gelato dashboard directly."
  Neither CHANGELOG nor any `.remember/` note since records that the
  dashboard fix was completed.
- **Evidence.** The print path still submits the uncropped base artwork for
  every group (`group_product.py:176-184` passes
  `candidate["base_image_url"]` for all variants); `image_crop.crop_for_group`
  is only applied to the *review preview* for single-size groups
  (`group_product.py:214-224`) — deliberate, per the brainstorm's update
  ("Gelato itself cover-crops correctly at print time"). That's only true if
  the placeholder geometry was fixed.
- **Severity: blocker for the 10x24 leg** (5x7 and primary unaffected).
- **Fix.** Not code. Confirm in the Gelato dashboard that the 10x24
  (and check 5x7/A-series) placeholder spans the full page, and record the
  confirmation in CHANGELOG/`.remember`. If it can't be fixed there, the
  brainstorm's fallback (crop-per-live-placeholder-ratio + hosting via R2,
  which now exists — the original "no hosting" objection is gone) becomes a
  code task. Open Q5's fit/fill-toggle question dies either way.

### B3. `group_mockup.py` still defaults `poll_interval=3.0` — the calm-the-poll fix missed the fan-out path
- **Root cause.** The 1010 fix's step 3 (10s + jitter) landed in
  `group_product.py` (`poll_until_ready` default 10.0, `_jittered` ±20%,
  lines 21-24/38) and `primary_mockup.py` (10.0, lines 34/62) — but
  `group_mockup.py:33` and `:85` still default `poll_interval: float = 3.0`
  and pass it down into `create_or_reuse_group_product`, overriding the 10s
  default. `run_m1_live_test.py` calls `run_group_mockup_cycle` without an
  override, so the live run polls the 5x7 and 10x24 creations at ~3s.
- **Consequence.** The evening fan-out — two products created back-to-back,
  each polled up to ~100× — is exactly the burst pattern the investigation
  blamed for tripping the 1010 score. This is the one place the fix's own
  claim ("poll_interval 3s → 10s + jitter") is not true in code.
- **Severity: blocker-adjacent** (probabilistic — it re-creates the
  conditions that killed run #1).
- **Fix.** Change both defaults in `group_mockup.py` to 10.0. Two characters
  ×2, plus a test asserting the default (see H4 on why the existing suite
  didn't catch it).

### B4. Idempotency residual window is still open — and the live DB shows the blast radius
- **Root cause.** The shared helper is real: all three create paths route
  through `group_product.create_or_reuse_group_product` (verified:
  `primary_mockup.py:46`, `group_mockup.py:60`,
  `publish_primary_group.py:84`), with reuse-if-sizes-match, stale-row
  delete, and recreate-on-size-change. But the brainstorm's flagged residual
  window was never mitigated: `gelato_product_id` is persisted only *after*
  a successful create response (`group_product.py:185-190`). A create whose
  HTTP call times out after succeeding server-side leaves the row
  `mockup_failed` with `gelato_product_id = NULL` — the stale-row cleanup
  can't delete a product it has no id for, and the retry creates a
  duplicate. No pre-create existence check (list store products by title)
  and no reconcile-in-cleanup exists.
- **Evidence of blast radius.** `db/qhoto.sqlite3` currently holds **41
  group_products rows for 7 never-published candidates** — 34 `deleted` + 7
  `mockup_failed`, every one with a real Gelato product id — the residue of
  the 1010-blocked runs. (These all *have* ids, so the tracked cleanup works;
  the untracked-orphan window is the one that leaves products nothing can
  ever delete.)
- **Severity: high → blocker in combination with 403-retry behavior** (the
  new 1010 backoff retries the create POST after 60s+ waits — if the 403
  masked a server-side success, that's this window).
- **Fix.** Smallest honest version, per the brainstorm's own "flag, don't
  over-build": before a create where no `gelato_product_id` is stored, list
  store products filtered by this group's title and reuse/delete any match;
  or add a reconcile pass to `cleanup.py` that lists store products and
  flags any id not present in the DB. Either satisfies the CLAUDE.md
  idempotency constraint's intent without changing it.

---

## High — unattended run stalls, or degrades silently

### H1. `publish_failed` is a dead-end state: no retry, no digest surfacing
- **Root cause.** Spec section 3 step 7: operational publish failure →
  "retry once automatically; if it still fails … surface the failure in the
  next digest." Reality: the primary path does retry once
  (`publish_primary_group.py:94-98`), but the 5x7/10x24 approve path has
  **no retry at all** (`publish_group.py:41-53` — one attempt, mark
  `publish_failed`, raise). And nothing anywhere selects
  `groups.status='publish_failed'` for retry or reports it: no digest query
  includes it, `cleanup.py:15` only touches *product*-level
  `publish_failed`. The admin's approve is recorded, the Telegram offset
  advances (`publish_primary_group.py:288-297` logs and continues), and the
  design stalls forever, silently.
- **Severity: high** — this is precisely the "unattended run fails partway
  invisibly" class.
- **Fix.** Add retry-once to `publish_group.handle_decision` (mirror the
  primary's nested-try); add a `publish_failed` line to the next digest run
  (a plain `sendMessage` listing stalled groups satisfies "surface"), and/or
  make the poll cycle re-attempt `publish_failed` groups whose decision was
  `approved`. Aligns with the spec text; no constraint change.

### H2. R2 upload bypasses the shared HTTP client — one urllib bot-fingerprint call per candidate, to a Cloudflare property
- **Root cause.** `artwork_store._r2_put_object`
  (`pipeline/artwork_store.py:74-83`) uses raw
  `urllib.request.urlopen` — fresh TLS handshake, HTTP/1.1, default
  `Python-urllib/3.x` UA — the exact signature the 1010 rewrite eliminated.
  It fires once per candidate in the generate stage, inside the batch burst,
  against R2 (Cloudflare-fronted). The commit message's "route through
  shared httpx client" claim is true for the API clients and
  `_image_is_fetchable` (f2f2762) but not here.
- **Mitigating context.** SigV4-authenticated S3-endpoint traffic is less
  likely to be SBFM-scored than public-domain traffic, and volume is low
  (1/candidate). But it's the one remaining stdlib-urllib call in the hot
  path, and `fetch_bytes` of the R2 *public* URL later (Telegram/critic
  paths) shares the client already — asymmetric.
- **Severity: high** (probabilistic, same class as B3).
- **Fix.** Send the PUT through `http.py` (needs a small
  `send_raw`/`put_bytes` helper that returns the response without JSON
  parsing, headers passed through — SigV4 signs only
  host/x-amz-date/x-amz-content-sha256, so httpx's extra default headers are
  fine). Keep the fail-loud non-2xx behavior.

### H3. First-run DB starting state will fan out 7 candidates at once
- **Evidence.** All 7 candidates sit at `status='generating'` with R2-hosted
  `base_image_url`s; each has a `mockup_failed` group_products row with a
  live Gelato product id. The next batch will, for each of the 7: delete the
  stale Gelato product, create a new one, poll it — a delete+create+poll
  burst ×7 at 5s spacing (`primary_mockup.py:64` `inter_candidate_delay=5.0`),
  the same shape as the run the 1010 investigation dissected. It also means
  7 simultaneous review digests and up to 21 listings from run #2, vs. the
  M1 convention of "single candidate to bound API cost"
  (`run_m1_live_test.py` seeds exactly one for that reason).
- **Severity: high for run quality** (cost, 1010 exposure, review noise) —
  not a code bug.
- **Fix.** Manual pre-run triage (needs your decision, it deletes data):
  keep 1-2 candidates for the clean E2E, mark the rest `failed`/pruned. Also
  worth reconciling Gelato-side: the 7 `mockup_failed` products (and
  spot-check the 34 `deleted` ones) may still exist as Gelato products /
  Etsy draft rows. I have not called any external API to check — that's a
  live-call verification to bundle with B1's.

### H4. The 1010 fix's backoff is tested; the poll-interval claim isn't
- **Evidence.** `tests/test_http.py:77-105` covers 1010 backoff (60/120
  waits, give-up after 3, CF-Ray propagation, plain-403-no-retry) — good.
  But nothing asserts the *poll defaults*, which is why B3 survived a
  316-test green run.
- **Severity: medium-high (regression insurance).**
- **Fix.** One test asserting `create_group_mockup`/`run_group_mockup_cycle`
  poll at ≥10s by default (e.g. inspect the call into
  `create_or_reuse_group_product`), and one asserting `_jittered` bounds.

---

## Medium — degraded behavior, survivable for one supervised run

### M1. Digest two-call race can duplicate galleries and then eat real decisions
- `send_group_digest` (`group_digest.py:70-82`) and the primary digest send
  `sendMediaGroup`, then `sendMessage`, then insert the `group_messages`
  row. If `sendMessage` fails after the gallery went out, no row is written
  and the next cycle re-sends both (duplicate gallery — cosmetic). The
  sharper edge: `process_update` (`publish_primary_group.py:222-230`)
  validates callbacks with `fetchone()` against `group_messages` — if a
  group ever gets two rows, taps on the *second* message fail the
  message-id match and are discarded as unknown. Fix: insert the row keyed
  to the send atomically (write row after `sendMessage` — already the case —
  plus a UNIQUE(group_id) constraint or `WHERE group_id=?` re-send guard,
  and match callbacks against *any* row for the group).

### M2. Secondary-group crop "retries" are deterministic no-ops
- `run_group_critic_pass` retry loop (`group_critic_pass.py:90-98`) recreates
  the group product via `create_group_mockup`, which reproduces the *same*
  center-crop of the *same* artwork — attempts 2 and 3 are guaranteed
  identical to attempt 1, so a failing group always burns 3 Gelato
  create/delete cycles + 3 critic calls to reach `failed_abandoned`.
  Related: a group-level `edit` decision (`publish_group.py:82-98`) records
  the note and discards the product, but the note is never fed into the
  recreate. Spec's "crop/composition retry attempts" implies variation that
  doesn't exist. Fix (cheap): cap secondary-group critic attempts at 1, or
  vary the crop anchor (top/center/bottom) per attempt. Flagging rather than
  prescribing — either reading is a small spec interpretation call.

### M3. `resolve_etsy_listing_id` margin is thin
- Timeout 600s vs. ~8min (480s) *observed typical* sync lag (Open Q1) —
  one slow sync blows it, marking the group `publish_failed` (→ H1's dead
  end, on the secondary path with no retry). 30s interval is fine; raise
  timeout to ~1200s. (`group_product.py:64-79`.)

### M4. "Unattended" isn't wired yet
- The runtime constraint is two cron cadences; what exists is
  `run_m1_live_test.py`, a manual script you re-run to advance stages (its
  own header: "Not wired to cron yet"). For the *this-milestone* definition
  (one clean E2E), manually triggering stages may be acceptable — but if
  the DoD is literally "unattended," the two entrypoints (hourly poll,
  twice-daily batch) plus scheduling are missing and are a small, separate
  task. Flagged so the DoD is chosen consciously, not defaulted.

---

## Low / cosmetic / housekeeping

### C1. Runtime dependencies aren't declared
- Only `requirements-dev.txt` exists (pytest, httpx[http2]). **Pillow is not
  declared anywhere** yet `image_crop.py` imports PIL at module load, and
  `group_product.py` imports `image_crop` — every pipeline entrypoint now
  requires Pillow. The brainstorm noted "Pillow … would need adding"; it was
  used but never added. A fresh environment (the future cloud VM — 1010 fix
  step 7) cannot run the pipeline. Fix: add `requirements.txt` (httpx[http2],
  pillow), keep dev extras separate.

### C2. The uncommitted 60-file diff is pure line-endings; 17 commits unpushed
- `git diff --stat`: 17,446 insertions, 17,446 deletions;
  `git diff --ignore-all-space` is **empty** — a CRLF/LF normalization sweep
  touched 64 files with zero content change. Untracked: `.agents/`,
  `.claude/`, `db/base_artwork/`, three `db/*.bak-*` backups,
  `docs/cloudflare_1010_issue_investigation.md`,
  `docs/cowork_fable_deep_review_prompt.md`, `skills-lock.json`. Also
  **master is 17 commits ahead of origin** — all post-live-run fixes exist
  on this machine only. Per your instruction I'm noting, not deciding: the
  EOL churn will pollute every future `git blame`/diff until resolved one way
  (commit it) or the other (checkout + `.gitattributes`/`core.autocrlf`),
  and the unpushed commits are a single-disk-failure risk. The 1010-fix
  commits (70318a6/f2f2762) are committed and not part of the churn.

### C3. Remaining honest-UA stragglers (out of hot path)
- `r2_healthcheck.py:15` keeps a fake `Mozilla/5.0 (compatible; …)` UA —
  deliberate per its comment (public r2.dev fetch), but it's the exact
  UA-on-non-browser-TLS mismatch the investigation called a bot-score
  increase; the honest `http.py` UA would do. `refresh_etsy_token.py`,
  `etsy_oauth_exchange.py` use raw urlopen (rare, manual, one-shot — fine).
- `run_m1_live_test.py` matches pytest's `*_test.py` collection pattern and
  is imported on every test run (harmless today — import-safe, no test
  functions — but one module-level side effect away from not being). Rename
  (`m1_live_run.py`) or add `collect_ignore` to `conftest.py`.
- `.env` carries a legacy `ALLOWED_TELEGRAM_USER_ID` no code reads
  (`TELEGRAM_ADMIN_CHAT_ID` is the real one) — drop to avoid confusion.
- `update_listing_inventory`'s size match is substring-based
  (`etsy_client.py:170` `size.lower() in value.lower()`) — currently safe
  for this size set and it fails loud on no-match (good), but it's fragile
  against Gelato variant-title format changes.

---

## Verified clean (claims checked, no action)

- **Shared client:** `http.py` is one module-level `httpx.Client(http2=True)`
  with keep-alive and the honest UA; all five API clients + `fetch_bytes` +
  `head` route through it (grep-verified; only exceptions are H2/C3 above).
- **Fake Mozilla UA:** gone from `pipeline/` entirely; sole survivor is
  `r2_healthcheck.py` (C3).
- **403/1010 backoff:** implemented with long waits (60/120/240), CF-Ray
  logging, plain-403 not retried — and covered by 4 tests (H4's gap is the
  poll defaults, not the backoff).
- **Idempotency architecture:** one shared create-or-reuse helper, all three
  create paths delegate; `any_published` gate is gone (primary is one atomic
  create+patch); reject/edit paths synchronously delete Gelato products.
  Remaining gap is the known residual window (B4), not path divergence.
- **Placeholder guard:** fail-loud on template/variant/placeholder-name
  (`gelato_client.py:74-88`), tested (`test_gelato_client.py:55,68,136`);
  moot in practice — all 12 config slots hold real IDs. Same pattern guards
  `replicate.delivery` and non-http image URLs, both also load-bearing
  (R2 is configured; DB `base_image_url`s are all `r2.dev`).
- **TELEGRAM_ADMIN_CHAT_ID:** read via `config.require_env` only; not in any
  tracked file; `.env`/`.env.*` git-ignored; allowlist check + unknown-
  callback discard + event logging all present (`publish_primary_group.py:
  212-230`).
- **Schema:** `db/schema.sql` and the live `db/qhoto.sqlite3` are
  structurally identical (11 tables compared column-for-column, no drift);
  base-artwork columns present; FK pragma on.
- **Brainstorm item 1** (lifestyle-mockup prompt): scaffold rewritten to
  flat/full-bleed, `sanitize_niche` strips scene tokens at the single
  funnel point, no-go list baked in (`generate.py:9-50`).
- **Brainstorm item 9** (AI-tools tick): correctly closed as
  verify-and-document; `who_made: i_did` + description disclosure applied at
  patch time; CLAUDE.md documents it.
- **Brainstorm item 2** (partial publishes): structurally dissolved by the
  variant consolidation as predicted — per-size loops are gone; residual
  exposure is H1's stall path, not partial fan-out.
- **Local-path preview plumbing:** cropped previews (local files) are
  correctly special-cased in both consumers — Telegram multipart upload
  (`telegram_client.py:57-77`) and Anthropic base64 blocks
  (`anthropic_client.py:91-107`).

## Live-call verifications proposed (not run — need explicit go-ahead)
1. ~~B1 verify~~ — closed by owner's manual dashboard check (all publishes
   are drafts; meta correctly patched). No live call needed.
2. **H3 reconcile:** GET Gelato store product list; diff against DB ids;
   check Etsy Drafts tab count.
3. **B5 verify:** one real ESRGAN call at the chosen larger scale to confirm
   Replicate accepts it and the output dimensions/DPI math holds, before the
   E2E run burns a candidate on it.
4. **1010 fix A/B (investigation step 5):** same script, hotspot/VPN egress,
   to size the residual IP component. Optional, 10 minutes.
