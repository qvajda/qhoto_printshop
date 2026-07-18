# E2E Live-Run Runbook — Task 10 (STOP gate)

Branch: `fix/live-test-readiness`. Prereq: full suite green (343/343), final
whole-branch review clean. **No step below runs without explicit per-call
user go-ahead** (reversibility policy). Every live call is named before it is
made.

Purpose: one clean end-to-end run per CLAUDE.md's aspect-ratio-group flow,
exercising the Task 1–9 fixes live for the first time (the critic rubric and
the local sanity gate have never run live — `critic_pass_attempts` is empty).

---

## Step 1 — Pre-run manual items (user)

1a. **Confirm the Gelato-dashboard 10x24 placeholder fix (B2).** In Gelato
    Studio, verify the 10x24 variant's image placeholder box spans the full
    250×600mm page (not the old 261×392mm box that left white bars).
    - If confirmed → 10x24 leg runs normally.
    - If NOT confirmed → run the E2E with the **10x24 group expected-fail**,
      and queue the code-crop-with-R2-hosting fallback (deferred B2) as a
      follow-up branch. Do not block the primary + 5x7 legs on it.

1b. **DB triage (DESTRUCTIVE — explicit user confirm required).** All 7 queued
    candidates are condemned by the owner's artwork review.
    - Back up first: `cp db/qhoto.sqlite3 db/qhoto.sqlite3.bak-2026-07-18-pre-e2e`
    - Then prune all 7 candidates (and their groups/group_products/variants/
      images rows). Let the run generate fresh candidates through the Task 4
      (scale=8) + Task 8 (hardened prompt) + Task 9 (sanity gate) pipeline.
    - Seed exactly ONE fresh candidate for the E2E (M1 convention bounds API
      cost — `run_m1_live_test.py` seeds one deliberately).

## Step 2 — B5 verify (ONE live Replicate call)

Named call: `nightmareai/real-esrgan` at `scale: 8` on one real FLUX master.
- Confirm Replicate **accepts** scale=8 at 832×1216 input (output-size limits
  at this input are unverified server-side — this is the gate).
- Confirm output dims == **6656×9728** (the DPI math: ~285 DPI at A1).
- If scale=8 is rejected Replicate-side → fall back to a chained 4×→2× pass
  (two upscale calls) to reach the same dims; update `replicate_client.py`.
- Do this BEFORE burning a candidate on a full generate, so a scale-8
  rejection is caught cheaply.

## Step 3 — H3 reconcile (live read-only, then user-gated deletes)

- Named call: Gelato `GET /v1/stores/{storeId}/products` (`list_products`).
- Diff the returned product ids against the DB `group_products.gelato_product_id`
  set. Report orphans (Gelato products with no DB row) — the untracked-window
  residue of the 1010-blocked runs.
- Cross-check the Etsy **Drafts** tab count against DB `etsy_listing_id` rows.
- **Delete orphans ONLY on explicit user instruction** (per product id).

## Step 4 — The E2E run (each live call named before it fires)

Fresh single candidate, full flow:
1. Generate (real FLUX schnell + real ESRGAN scale=8) → flat art, no scene
   leak, passes the Task 9 local sanity gate, master ≥150 DPI at A1.
2. Primary mockup (Gelato create, one product) → primary critic pass (extended
   rubric — **first live exercise**) → primary digest (Telegram).
3. Approve the primary → primary group publishes as ONE Gelato product / ONE
   Etsy listing, 4 size variants, fully patched (title/description/tags/
   section/partner/who_made/per-variant price), sitting as an **Etsy draft**.
4. 5x7 and 10x24 groups each cover-cropped, own critic pass, own digest entry
   **in the same evening run**.
5. Across the two secondary groups: at least **one approve and one reject**
   (M1 matrix, SPEC section 5) — each processed independently.

Verify in the run report:
- All resulting listings are **drafts**; no listing state ever changed (Task 6
  invariant); owner activates manually if quality warrants.
- No duplicate Gelato products: DB product count == Gelato store count after.
- No group silently stalled: `publish_failed` empty or surfaced in a digest.
- Gelato dashboard shows **≥150 DPI on every offered variant**.

---

## Failure protocol (user-mandated — applies on any failure OR partial success)

1. **Incident note to memory FIRST** — append to `.remember/today-2026-07-18.md`
   a compact entry: what failed, at which pipeline stage, the exact error /
   CF-Ray / API response, what was ruled out, and the state left behind (DB
   rows, Gelato products, Etsy drafts created — **ids included**).
2. **If diagnosable**, also write a next-session start-up prompt to
   `docs/e2e_retry_kickoff_prompt_2026-07-18.md`: context in three sentences,
   the incident summary, what to fix/re-verify first, and how to resume the
   E2E without redoing completed verifications.
3. **Either way — success or failure — Task 10 ends the session** (context
   reset is planned). Final message is a handoff: state of the branch (merged
   or not), state of external accounts (Gelato products, Etsy drafts), and the
   single next action.

## Explicitly deferred (do NOT build here)
- Etsy activation flow (manual dashboard only, Task 6 documents it).
- B2 code-crop fallback (only if the dashboard fix is confirmed impossible).
- M2 secondary crop variation / edit-note plumbing.
- M4 cron entrypoints (separate small branch after the E2E passes).
