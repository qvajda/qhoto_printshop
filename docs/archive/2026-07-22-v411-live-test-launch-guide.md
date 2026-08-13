# v4.11 live-test launch guide — Round 1 (pre-mockup) — 2026-07-22

**This is the go-live gate for the v4.11 re-architecture (GL-9).** It proves
the publish rework (Gelato-pushes-we-patch, variant listings, idempotent
create) and the never-tested control paths (Kill, 3-attempt-fail + DELETE,
allowlist) **live, for the first time** — while the surface is still simple,
before the Addendum-A mockup change lands.

Deliberately scoped to the **mockup-independent** slice. The storefront
gallery imagery + critic-over-gallery get re-tested in **Round 2** (post-mockup,
see `2026-07-22-go-live-plan-of-attack.md` → GL-13); don't over-invest in
scrutinising the Gelato default gallery here.

## Ground rules (CLAUDE.md §4 reversibility)

- Branch = `master` (GL-1 merged). Full test suite green before any live call.
- **Every live call is named before it fires; no call runs without an explicit
  per-call go-ahead.** Same STOP-gate discipline as the 2026-07-18 runbook.
- **`GELATO_LIVE_MODE` / `ETSY_LIVE_MODE` (in `.env`) stay `false` for every
  scenario that doesn't strictly need a live write.** Flip to `true` only for
  S3 and S4, only for the calls named live.
- Etsy shop is still in **Developer Mode** — listings created stay non-public
  drafts; never call `update_listing_state` / activate. Gelato has **no** dev
  mode: products created are real and must be deleted at cleanup.
- **One candidate at a time** (M1 cost convention). Back up the DB first:
  `cp db/qhoto.sqlite3 db/qhoto.sqlite3.bak-2026-07-22-pre-v411-e2e`.

## Run order (cheap-and-independent first, spend last)

S0 pre-flight → **S1 allowlist** (no gen) → **S2 Kill** (no gen) →
**S3 happy-path E2E** (the one real generate + publish) →
**S4 3-attempt-fail + DELETE** (reuses a condemned master, no new generate) →
S5 idempotency (optional). This burns exactly **one** generation for the whole
round.

---

## S0 — Pre-flight (read-only, LIVE_MODE off)

**Hypothesis:** environment + external state are clean before we write.

- Confirm suite green; `git rev-parse` shows master with GL-1 merged.
- Confirm `config.is_r2_configured()` is `True` (durable base-artwork URL).
- Confirm no Gelato template is a `PLACEHOLDER_` (all 12 resolve to the 2 real
  multi-variant IDs) — `config.is_placeholder` on each.
- **Named live read:** Gelato `list_products` (`GET /v1/stores/{storeId}/products`)
  → diff against DB `group_products.gelato_product_id`; report orphans. Cross-check
  Etsy **Drafts** count vs DB `etsy_listing_id`. **Delete orphans only on explicit
  per-id go-ahead.**

**Pass:** env clean, no placeholders, orphan set known.

---

## S1 — Allowlist rejection (no generation, near-zero cost)

**Hypothesis:** the bot acts only on the admin ID; anything else is discarded
and logged, never acted on (CLAUDE.md security constraint — the admin ID is the
only access-control layer).

- From a **second Telegram account** (non-admin), send the bot a command and
  press an Approve/Reject-style callback aimed at any live message.
- Run the Telegram poll (`publish_primary_group.process_update` path via
  `run_publish_primary_group_cycle`, or `get_updates` directly).

**Named live calls:** Telegram `getUpdates` (read). No Gelato/Etsy calls.
**Pass:** the non-admin update is discarded; a row lands in `telegram_events`
with `accepted=0`; **no** decision recorded, **no** publish triggered. Verify
`is_admin()` returned False for that id.

---

## S2 — Kill branch (no generation, near-zero cost)

**Hypothesis:** a Kill-classified candidate never reaches generation (budget
guard) — it's logged Kill and skipped.

- Seed one candidate with `demand_ratio = 0.001` (below
  `research.KILL_DEMAND_RATIO_THRESHOLD = 0.002`) and a `listing_count` set, so
  `research.classify` → `go_hold_kill = "kill"`.
- Run `generate.run_generate_cycle`.

**Named live calls:** none (this is the point — no Replicate spend).
**Pass:** candidate persisted with `go_hold_kill='kill'` + `kill_reason`; the
generate cycle makes **no Replicate call** and does not advance it to
`generating`. (Optionally also seed a timing-based `hold` and confirm it's
parked with a `hold_recheck_date`.)

---

## S3 — Happy-path v4.11 E2E (the core — one real generation)

**Hypothesis:** a GO candidate flows generate → publish under the **v4.11
patch path**, producing one Gelato product + one Etsy draft listing per
aspect-ratio group with sizes as **variants**, correctly patched — and the
group flow handles an approve *and* a reject.

Seed one fresh GO candidate. Then, each stage (driver:
`run_m1_live_test.py`, LIVE_MODE flipped on only from primary_mockup onward):

1. **Generate** — real FLUX.1 [schnell] + ESRGAN. **Pass:** flat full-bleed art
   (no frame/room/mockup leak), passes the local sanity gate (`cov`), master
   ≥150 DPI at A1, and `base_image_url` is a **durable R2 URL, not
   `replicate.delivery`** (the base-artwork-persistence fix).
2. **Primary mockup** — Gelato `create-from-template`, **one** product via
   `create_or_reuse_group_product`. **Named live call:** Gelato create.
   **Pass:** exactly one product; re-running the stage **reuses** the stored
   `gelato_product_id` (no duplicate — the idempotency fix).
3. **Compliance draft → critic pass (expect PASS) → primary digest.**
   **Pass:** digest arrives as **two** calls (`sendMediaGroup` gallery, then
   `sendMessage` with the Approve/Edit/Reject inline keyboard), tagged to the
   group.
4. **Approve the primary group (admin).** **Named live calls:** Gelato push →
   Etsy. **Pass, v4.11-specific — this is the crux:**
   - The pipeline does **not** call `create_draft_listing`. Gelato's push
     auto-creates the Etsy listing; the pipeline resolves the Etsy `listing_id`
     from the Gelato product `externalId` (`resolve_etsy_listing_id`) and
     **patches** it (`update_listing` + `update_listing_inventory`).
   - The one listing carries **4 size variants** (8x12/A3/A2/A1) at **per-variant
     prices** €24 / €35 / €39 / €49; `taxonomy_id=1027`,
     `shop_section_id=59380312`, `production_partner_ids=[5717252]`,
     `who_made='i_did'`, `is_supply=false`, `when_made='made_to_order'`,
     shipping = **Large `287910565714`**; ≤13 tags ≤20 chars; title ≤140.
   - Listing stays a **draft** (never activated).
5. **5x7 + 10x24 groups** — each cover-cropped from the same master, own critic
   pass, own digest entry **in the same run**. **Pass:** two more digest entries;
   10x24 crop fills the frame (no white bars).
6. **Secondary decisions — one approve, one reject:**
   - **Approve 5x7** → its own one-listing/one-Gelato-product, shipping **Small
     `287910553824`**, price €19, patched, draft.
   - **Reject 10x24** → group logged `rejected`/abandoned; if a Gelato product
     was created for it, confirm it's **DELETEd** (no dangling product); the
     already-published primary + 5x7 groups are **untouched**.

**Round-report pass criteria:** DB Gelato-product count == Gelato store count
(no duplicates); zero `create_draft_listing` calls in the log; all listings
drafts; `publish_failed` empty or surfaced; per-variant prices + shipping tier
correct per group.

---

## S4 — 3-attempt critic fail + DELETE cleanup (reuses a condemned master)

**Hypothesis:** three failed critic attempts on a group hit the cap, abandon
the group, and the **live** Gelato `DELETE` actually removes the product; at
the primary-group level this also fires the Go/Hold/Kill Kill-fallback on the
whole candidate.

- **Injection (no new generation):** point a fresh candidate's `base_image_url`
  at a **known-condemned S4-a master** (must-FAIL set {4,6,7}) so the critic
  genuinely rejects it. (If three genuine fails can't be guaranteed from art
  alone, a temporary local monkeypatch forcing `passed=False` is acceptable —
  note it in the incident log; do **not** commit it.)
- Run primary mockup (Gelato create — **named live call**) → critic pass; let
  it fail attempts 1, 2, 3.

**Pass:** `critic_pass_attempts` shows 3 failed rows; group marked `failed`;
Go/Hold/Kill fallback Kills the candidate; **named live call** Gelato
`DELETE /v1/stores/{storeId}/products/{productId}` fires and a follow-up
`get_product`/`list_products` confirms the product is **gone**.
**Optional S4b (group-level scope):** drive one of {5x7, 10x24} to 3 fails and
confirm **only that group** is deleted — the design's other published groups
stay live.

---

## S5 — Idempotency / orphan-delete (optional, no new generation)

**Hypothesis:** a create-retry after a simulated poll timeout reuses the stored
product; a failed-create retry deletes the orphan before re-creating.

- Re-invoke `create_or_reuse_group_product` on an existing group. **Pass:** it
  reuses `gelato_product_id`, no second product; on a forced failed-create path,
  the orphan is deleted first (matches the live-run duplication bug's fix).

---

## Cleanup & exit

- **Named live calls:** Gelato `DELETE` on every product created this round
  (per-id go-ahead). Etsy drafts can be left (non-public in Dev Mode) or deleted.
- Restore/annotate the DB; keep the `.bak` until the round is signed off.

## Failure protocol (reused from the 2026-07-18 runbook)

1. **Incident note to memory FIRST** — append to `.remember/today-2026-07-22.md`:
   what failed, which stage, exact error / CF-Ray / API response, what was ruled
   out, and state left behind (DB rows, Gelato product ids, Etsy draft ids).
2. **If diagnosable**, write a resume prompt to
   `docs/v411_live_test_retry_kickoff_2026-07-22.md` (3-sentence context,
   incident summary, what to fix/re-verify first, how to resume without redoing
   passed scenarios).
3. Success or failure, end with a handoff: branch state, external-account state
   (Gelato products, Etsy drafts, with ids), and the single next action.

## Exit criteria → go-live gate

Round 1 passes when S1–S4 pass (S5 optional). That clears the v4.11 publish
rework + all previously-untested control paths. **Remaining before public
launch:** mockups decision (GL-2, post-prototype), cron runtime (GL-7),
storefront (GL-10), **Round 2 re-test** (GL-13, the mockup-dependent slice),
and Etsy Developer-Mode revert (GL-11).
