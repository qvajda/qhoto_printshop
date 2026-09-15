# Etsy AI POD pipeline

One shop selling AI-generated wall art as print-on-demand posters. Vocabulary:
`CONTEXT.md`. Spec: `docs/SPEC_v4.12.md` (one listing per artwork; supersedes
v4.11 §3–4 — read `docs/SPEC_v4.11.md` for §1–2 and §5–9). Shop currency EUR.
**Read the relevant spec section before touching a pipeline stage** — don't
guess at behavior that is already specified.

This file is hot path: it enters every session unasked, and it is capped at
**150 lines** by `groom.yml` and by `tests/test_qops.py`. Data belongs in
`docs/reference/`, decisions in `docs/adr/`, external facts in
`docs/constraints/`. The 372-line version is `docs/archive/2026-08-14-claude-md-pre-slim.md`.

## Standing owner decisions — not planning variables

**Activation.** No listing is activated until the pipeline is fully clear AND
the shop is out of developer mode. The owner decides when drafts get published;
it is not gated on any board row, is never a step in a session plan, and is
**not to be raised as a question, recommendation or reminder** (2026-08-12).
Planning docs may state what a defect *would* cost on a live listing — that is a
technical fact — but must not propose or prompt for an activation. Everything
stays a draft, so gallery/alt-text repair stays free indefinitely.

**Git history is not rewritten.** Closed, not deferred. **Never propose,
schedule or recommend a `filter-repo` / `filter-branch` / BFG / force-push
session** (2026-08-13). E13a scanned all 392 commits and 1357 reachable blobs
with three instruments and found no live credential
(`docs/archive/2026-08-13-e13a-findings.md`). The repo is public: a rewrite
reduces *convenient* access to something already in history, it never un-leaks
it. Forward rule: **if a secret is found, rotate it first**, and treat rewriting
as a separate decision even then. Reopens on exactly one condition — a future
scan finding a real live credential.

## Hard constraints — do not change without flagging first

Each line is the rule; the link is the reasoning. Changing one means amending
its record, not editing this list.

- **Artwork generation is Replicate + FLUX.1 [schnell] only.** Never substitute
  the `dev` variant without raising it explicitly — different commercial
  licence. Governs `pipeline/generate.py` and nothing else. A design is
  image-generated **once**; group-level crop/retry reuses the same base image.
  → `docs/constraints/001-flux-schnell-licence.md`
- **Mockup *scene* generation is a separate concern and is not bound to
  schnell.** Nano Banana Pro (`google/nano-banana-pro`) is the default scene
  generator; every output carries a SynthID watermark; scenes are hand-run by
  the owner into `assets/mockups/inflow/` and need no batch harness.
  → `docs/adr/0008-scene-generation-not-bound-to-schnell.md`
- **Aspect is specified with a geometry card, not with prose.** No image model
  converts "A1" or "2:3" into a rendered rectangle. Pass
  `assets/mockups/geometry_cards/<group>` as a reference image.
- **Generated image = flat full-bleed artwork, never a poster-in-a-room
  render.** The injected niche is subject/style only — never scene words, never
  a dated event. → `docs/adr/0010-flat-full-bleed-artwork.md`
- **Runtime is discrete scheduled functions on two cron cadences**, one function
  per stage — not a persistent service, not one agent loop. **One exemption
  (2026-08-17): the Telegram ack** — poll, admin check, record decision, ack — may
  be an always-on listener. It never publishes.
  → `docs/adr/0005-discrete-scheduled-functions.md`
- **Telegram digest = `sendMediaGroup` + a separate `sendMessage`**, one pair
  per entry, never one combined call. Up to **three** entries per design.
- **Critic-pass retry cap is exactly 3 attempts per group**, then abandon that
  group only (`failed_abandoned`): exclude its sizes/images from the listing
  build and **leave the shared product/listing alone**. At the primary-group
  level this still triggers Go/Hold/Kill.
  → `docs/adr/0006-critic-retry-cap.md`
- **One Etsy listing per artwork; sizes are variants (v4.12).** One Gelato
  product, one Etsy listing, created **once** when all three groups have reached
  a terminal decision — never incrementally. Adding a variant to an existing
  Gelato product has no API path (confirmed live, GL-22a Q2).
  → `docs/adr/0003-one-listing-per-artwork.md`
- **Gelato pushes, we patch.** The Gelato store is Etsy-connected and
  auto-creates the listing. The pipeline never creates an Etsy listing itself;
  resolve the Etsy `listing_id` from the Gelato product `externalId` and PATCH
  (`updateListing` + `updateListingInventory`).
  → `docs/adr/0004-gelato-pushes-we-patch.md`
- **Gelato create must be idempotent.** Reuse a stored `gelato_product_id`
  before creating; delete orphans on a failed-create retry; route every create
  path through one shared create-or-reuse helper.
- **The compositor is fixed, never worked around from the assets.** If the
  composite is wrong, fix `pipeline/mockup_render.py` and add a test. If a
  constraint blocks the correct fix, flag it and stop. `overlay.png` may only
  paint where the print is. Authoring is gated by `scripts/mockup_qa.py` before
  any owner review. → `docs/adr/0007-self-hosted-compositor.md`
- **The 2 % crop budget is measured against the ratios a group *prints*,** not
  against the master, and applies to both paths that lose print — the
  cover-crop and the matte. Over budget, `render_scene` fails loud: never
  stretch a print a buyer pays for. `pipeline/image_crop.SIZE_INCHES` is the one
  table those ratios and the Gelato DPI guard both read.
- **Aspect-ratio-group review flow** — the core mechanic, spec §3 steps 6–7:
  only the primary size is generated and reviewed; on approval the whole primary
  group publishes with no further review; the 5x7 and 10x24 groups each get
  their own cover-crop, critic pass and digest entry. 4, 5 or 6 sizes is
  expected, not a bug.
- **Storage is SQLite.** One `groups` row per aspect-ratio group. Under v4.12
  the product/listing unit is the **candidate**, so `group_products` is a
  misnomer — it is the candidate's listing record and `gelato_product_id` is
  NULL for the whole review window. **Anything sweeping `pending` rows with no
  product id must know that is normal.** `group_product_variants` and
  `product_images` carry a `group_id`; every delete against them must scope by
  it, or one group's rebuild wipes another's reviewed gallery.
- **Static config is resolved once and read from config**, never discovered at
  runtime. Values: `docs/reference/static-config.md` + `config/static_config.json`.

## Conventions

- One module per pipeline stage, independently testable. Commit after each
  stage passes its manual M1 test.
- **Never call Etsy publish or Gelato product-create against real endpoints
  without an explicit go-ahead** during development.
- **Dry-run changes what a call *does*, never which code path reaches it.**
  Gate the side effect — the HTTP call, the write — not the value being
  computed. GL-48: the 10x24 crop was gated on `GELATO_LIVE_MODE`, so two soak
  nights were structurally incapable of observing the defect they existed to
  catch.
- **Verify a Gelato integration by measurement, not by status code.** GL-22a Q2:
  Gelato returns `200` for changes it silently drops. After any live create run
  `python scripts/gelato_template_check.py <product_id>`. `productImages[]` are
  1000×1000 scene previews, not the submitted print file.
- **A swallowed per-item exception must always leave a state change behind.** A
  `try/except: continue` in a stage loop must (a) write a status plus a reason
  onto the row and (b) still fail the stage once, after the loop. GL-46: 8 of 8
  candidates sat at `pending` overnight with nothing saying so.
- **An instruction in a prompt is a preference, not a control.** If a decision
  says the copy must never contain something, an assertion has to say so too, in
  code, next to the decision. GL-53: `DISCLOSURE_TEXT` was emptied and 27 of 27
  drafts kept the sentence. When auditing one field, read the whole row.
- **Assert the state, not the bookkeeping that was supposed to produce it.**
  GL-48 (status code), GL-53 (prompt instruction), #219 (`schema_version`) all
  read green while the real thing was wrong. Measure the live shape/output.
- **Listing copy is evergreen.** No dated event, festival or retail moment —
  sanitised before the drafting prompt and checked after
  (`compliance_draft.SEASONAL_TERMS`). Telegram's `📝 Redo copy only` redrafts
  text and **never** regenerates artwork.

## Ways of working

**Two trackers since 2026-08-19 (ADR-0023), and reading the wrong one is the
failure mode that costs.** This repo's issues are the **shop's**:
`gh issue list` on `qvajda/qhoto_printshop`. The substrate's own work — qops
bugs, its portability, its next phase — lives in `qvajda/qops` and never here.
`qops brief` names the repo it queried, every session; believe it over habit.
The issue wins over any planning doc.

Session state, the guard and the metrics are `qops`, consumed here as a **pinned
tag** — `python -m qops brief|ledger|resume|guard|close|install|doctor|metrics`,
configured entirely by `.qops/config.yml`. Upgrading it is an act, not a drift.
Agent docs: `docs/agents/`.
