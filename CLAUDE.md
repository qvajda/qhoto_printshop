# Etsy AI POD pipeline

Full spec: docs/SPEC_v4.12.md (one listing per artwork; supersedes
docs/SPEC_v4.11.md sections 3-4 — read v4.11 for sections 1-2 and 5-9, which
are unchanged). Root-cause analysis of the first live run's defects:
docs/superpowers/specs/2026-07-16-live-test-fixes-brainstorm.md.
Changelog/decision history: CHANGELOG.md.
Gelato cost reference: gelato_premium_matte_poster_prices_BE_2026-07-05.csv.
Shop currency: EUR. Read the relevant spec section before touching a
pipeline stage — don't guess at behavior that's already specified.

## Hard constraints — do not change without flagging first
- **Artwork generation (the thing that gets printed and sold): Replicate +
  FLUX.1 [schnell] only.** Never substitute FLUX.1 [dev] without raising it
  explicitly (different commercial license). A design is only ever
  image-generated once — group-level crop/retry (below) reuses the same base
  image, it never triggers a new generation call. This constraint governs
  `pipeline/generate.py` and nothing else; its rationale is the licence of the
  artefact a buyer pays for.
- **Mockup *scene* generation is a separate concern and is not bound to
  schnell (owner decision, 2026-07-29).** A scene is offline authoring input —
  a listing photograph, never a printed product — so the bar is "commercial
  use permitted", not "Apache-2.0 weights". **Nano Banana Pro
  (`google/nano-banana-pro`, Gemini 3 Pro Image, on Replicate) is the default
  scene generator.** schnell could not do this job: it ignores stated
  proportions (54 of 61 images in the P4b1 batch failed `aspect`; the 10x24
  group went 0/18 with a minimum gap of 0.20 against a 0.02 budget) and it has
  no negative channel, so "no mat, no glazing" reliably summons both. Two
  things to carry: every Nano Banana output has a **SynthID watermark**, and
  scene generation is **hand-run by the owner into
  `assets/mockups/inflow/`** — there is no batch harness and it does not need
  one, because the reason `scene_generate.py` existed was schnell needing ~60
  attempts per usable scene.
- **Aspect is specified with a geometry card, not with prose.** No image model
  reliably converts "A1" or "20cm by 30cm" or "2:3" into a rendered rectangle.
  `assets/mockups/geometry_cards/` holds one card per group at the midpoint of
  that group's printed ratio range; pass it as a reference image. This is what
  took a scene from 0.7572 (6.6 % outside the printed range, rejected) to
  0.6967 (inside, 9/9 on the screen) on the next attempt.
- **Generated image = flat full-bleed artwork, NOT a poster-in-a-room
  render.** The prompt must force flat 2D art filling the frame (no frame,
  border, wall, room, mockup) and the injected niche must be subject/style
  only, never scene words like "wall poster". The first live run printed
  lifestyle mockups *as* the artwork because of this — see spec section 3
  step 2.
- Runtime is discrete scheduled functions on two cron cadences (hourly
  Telegram poll, twice-daily batch) — not a persistent service, not one
  agent loop. One function per pipeline stage (research, generate,
  primary-mockup, compliance-draft, critic-pass, digest,
  publish-primary-group, group-mockup, group-critic-pass, group-digest,
  publish-group, cleanup).
- Telegram digest = sendMediaGroup (gallery) + separate sendMessage
  (text + buttons), one pair per digest entry. Never one combined call.
  There are up to **three** digest entries per design now, not one — see
  the aspect-ratio-group rule below.
- Critic-pass retry cap is exactly 3 attempts per group, then abandon
  that group only: log locally as `failed`. **Under v4.12 this never
  deletes a Gelato product or Etsy listing** — the product/listing belongs
  to the candidate, not the group, and other groups (already published or
  still pending) depend on it surviving. Abandoning a group means: mark
  that group `failed_abandoned`, exclude its sizes/images from the
  candidate's listing build, and leave the shared product/listing alone.
  At the primary-group level this still triggers the Go/Hold/Kill
  fallback (abandoning the whole candidate before any listing exists) —
  unchanged, because the primary group is decided first and no shared
  product exists yet if it fails.
- **One Etsy listing per artwork, sizes are variants (v4.12).** All six
  sizes are Etsy variations of ONE listing for a candidate, each at its
  own price — not one listing per aspect-ratio group. There is **one**
  Gelato multi-variant template pair (portrait + landscape, unchanged from
  v4.11) and the candidate's listing is one Gelato product created (or
  grown) with whichever sizes have passed review as that product's
  variants. A design still ends up offering 4, 5, or 6 sizes depending on
  whether the 5x7/10x24 groups each pass their own review (unchanged from
  v4.11) — it now offers them from one listing instead of up to three.
  Adding a variant to an existing Gelato product has no API path
  (confirmed live, GL-22a Q2 — `PUT` on the product resource silently
  drops the added variant and severs the Etsy sync; the `/variants`
  sub-resource is a different, incompatible custom-priced-product flow;
  re-`create-from-template` with the same title creates a second product).
  The listing is therefore created **once, when all three groups have
  reached a terminal decision** (approved/edited/rejected) — never
  incrementally.
- **Etsy integration = Gelato pushes, we patch (v4.11).** The Gelato store is
  Etsy-connected and auto-creates the listing. The pipeline must NOT create
  Etsy listings itself (doing so collided with Gelato's push in the live
  run). After Gelato's async sync, resolve the Etsy `listing_id` (Gelato
  product `externalId`) and PATCH it (`updateListing` +
  `updateListingInventory`) to set title/description/tags/section/partner/
  who_made/per-variant price. Never call `create_draft_listing`.
- **Gelato create must be idempotent.** Reuse a stored `gelato_product_id`
  before creating; delete orphans on a failed-create retry. The live run
  duplicated products (create succeeded, poll timed out, retry re-created).
  Route all create paths through one shared create-or-reuse helper.
- **Mockup compositor: unfrozen, and never worked around from the assets
  (GL-21, 2026-07-26).** `pipeline/mockup_render.py` was treated as frozen
  during GL-19. GL-6 attempt 2 honoured that over fixing a measured border
  defect and repainted the photograph over every print's outer 3 px instead —
  a dark hairline traded for a bright one across four bundles. The freeze is
  lifted (owner-approved). Standing rule: **if the composite is wrong, fix the
  compositor and add a test; never work around a compositor defect in a
  bundle.** If a constraint blocks the correct fix, flag it and stop — don't
  route around it. Current contract: the colour warp uses `BORDER_REPLICATE`
  (mask warp stays `BORDER_CONSTANT`); an optional per-pixel `matte.png` in the
  bundle decides what is *visible* (the quad only decides where the art is
  *projected*) and absent ⇒ pre-GL-21 behaviour; the artwork is cover-cropped
  to the quad's aspect and a crop over 2 % fails loud — never stretch a print a
  buyer pays for. `overfill` is deprecated for matte bundles, and **`overlay.png`
  may only paint where the print is** (it carries the matte-masked gain map and
  nothing else — an unmasked one is a full-frame wash). Authoring is gated by
  `scripts/mockup_qa.py` (eight detectors + contact sheet) before any owner
  review; `load_bundle`/`render_scene`/the bundle-on-disk contract are
  unchanged. See docs/SPEC_v4.10_addendum_custom_mockups.md §2.
- **The 2 % crop budget is measured against the ratios a group *prints*, not
  against the master (GL-21 P3.5, owner 2026-07-28).** The primary group prints
  at 0.6667 (8x12) and 0.7071 (A3/A2/A1); the master's own 0.6842 sits between
  them, so no single aspect is within 2 % of both ends and a master-relative
  rule would reject the master itself. A panel inside that range shows a crop
  between two the buyer genuinely receives; more than 2 % outside it, the mockup
  shows a crop no size in the group is ever cropped to and `render_scene` fails
  loud. The budget applies to **both** paths that lose print — the cover-crop
  (C3) and the matte (`matte-hidden`, added P3.5) — with no exceptions: a scene
  whose panel proportions don't match the product is re-authored, never
  exempted. `pipeline/image_crop.SIZE_INCHES` is the one table those ratios and
  the Gelato DPI guard both read.
- **Aspect-ratio-group review flow (the core mechanic — see spec section
  3, steps 6–7):**
  1. Only the primary size (21x29.7cm/8x12″) gets generated, critic-passed,
     and shown in the first digest entry.
  2. On approval, the **primary group** (8x12″ + A3 + A2 + A1, ISO A-series
     ratio) publishes immediately as ONE listing with those four sizes as
     variants, **no further review** — same composition, just scaled (the
     8x12/2:3 vs A-series 0.707 difference is a small crop, not a
     re-composition).
  3. Independently, the **5x7 group** and the **10x24 group** (each a
     genuinely different aspect ratio) each get their own **cover-crop** of
     the approved artwork (a real crop that fills the frame, never a
     fit/letterbox — the live run's 10x24 white bars were a missing crop),
     their own critic pass, and their own follow-up digest entry +
     Approve/Edit/Reject, sent in the same evening run.
  4. A design can end up selling at 4, 5, or 6 sizes depending on whether
     the 5x7/10x24 groups each pass their own review — this is expected,
     not a bug.
- Data storage is SQLite, not a flat file. One `groups` row per aspect-ratio
  group per candidate, each carrying its own decision and critic-pass
  history — **that part is unchanged.** What changed in v4.12: the
  **product/listing unit is the candidate, not the group** — ONE Gelato
  product + ONE Etsy listing per candidate, with the validated sizes as
  variants. `group_products` is therefore a **misnomer**: it is the
  candidate's *listing record*, and `gelato_product_id` is one nullable
  column on it, NULL for the whole multi-day review window until the single
  create at publish. **Anything that sweeps `pending` rows with no product
  id must know that** — under v4.12 that is the normal state, not a stranded
  one. `group_product_variants` and `product_images` each carry a `group_id`
  recording which group produced them; every delete against them must scope
  by it, or one group's rebuild wipes another's reviewed gallery.
- Static config (Gelato template IDs, Etsy taxonomy_id, shipping_profile_id,
  production_partner_ids, who_made value, Telegram admin/allowlist user ID)
  is resolved once and hardcoded/read from config — never discovered
  dynamically at runtime.
- **Telegram admin/allowlist user ID has two jobs, both required:** (1) every
  inbound getUpdates message and button callback is checked against it
  before being treated as a real command/decision — anything else is
  discarded and logged, never acted on; (2) it's also the chat_id target
  for every outbound sendMediaGroup/sendMessage digest call. There is no
  other access-control layer on the bot, so treat this ID with the same
  care as an API key — **read it from `.env` (e.g. `TELEGRAM_ADMIN_CHAT_ID`),
  never hardcode it in this file.** Unlike the Gelato/Etsy static IDs below,
  it's not project documentation, it's closer to a credential.
- **Placeholder policy for Gelato template IDs:** the template/variant slots
  below (2 templates × 6 size-variants each) may start out as placeholder
  strings (real ones require a manual step in the Gelato dashboard). Build
  and test everything against placeholders freely. The one rule: if a
  still-placeholder templateId/variantId ever reaches a real (non-mocked)
  `products:create-from-template` call, that must fail loudly with a
  clear error — never silently skip the size or proceed with a fake ID.

## Standing owner decision — git history is not rewritten (2026-08-13)
**The rewrite question is closed, not deferred. Never propose, schedule or
recommend a `filter-repo` / `filter-branch` / BFG / force-push session.** E13a
scanned all 392 commits and 1357 reachable blobs with three independent
instruments and found **no live credential of this project anywhere in
history** (`docs/2026-08-13-e13a-findings.md`). A rewrite would cost new SHAs
for every commit, re-pointing 24 tags and 14 remote branches, and orphaning
every existing clone and open PR — and it would buy nothing, because this repo
is public: a rewrite reduces *convenient* access to something already in
history, it never un-leaks it. **The forward rule: if a secret is ever found,
rotate the credential first, and treat rewriting as a separate decision even
then.** This reopens on exactly one condition — a future scan finding a real
live credential in history. Not on a new scanner, a new ruleset, or the known
Gelato expired-presigned-URL false positive re-tripping a future run.

## Standing owner decision — activation/publishing is not a planning variable
**No listing is activated until the pipeline is fully clear AND the shop is out
of developer mode. The owner decides when drafts get published; it is not gated
on any board row, is never a step in a session plan, and is not to be raised as
a question, recommendation or reminder** (owner, 2026-08-12). Planning docs may
state what a defect *would* cost on a live listing — that is a technical fact —
but must not propose, schedule or prompt for an activation. Two consequences
that matter downstream: everything stays a draft, so gallery/alt-text repair
stays free indefinitely and the 2026-08-12 "hold the first activation until
GL-69 and GL-71 land" urgency is void; and the GL-37 manual disclosure step
above is documentation of how publishing works when the owner chooses to do it,
**not** a to-do to surface.

## Static config values (see docs/SPEC_v4.11.md section 4 for the full cost/
price table and per-size notes; prices below are final, not placeholders)
- Telegram admin/allowlist user ID: **not listed here** — read from
  `TELEGRAM_ADMIN_CHAT_ID` in `.env` (git-ignored), same as the bot token.
  This file is committed to git, so it's the wrong place for it.
- Gelato templates: **2 multi-variant templates (portrait + landscape),
  sizes are the variants** — not 12 separate templates. In
  `config/static_config.json`, `gelato_templates` is keyed
  `<size>_<orientation>` → `{template_id, template_variant_id,
  image_placeholder_name}`; all six portrait keys share one `template_id`
  (distinct `template_variant_id` per size), all six landscape keys share
  another. Real IDs are already filled in. Final EUR retail prices per size
  (set per-variant on the listing):
    5x7 €19 (entry) · 8x12 €24 (entry, primary size) · A3 €35 ·
    A2 €39 (both orientations same price) · 10x24 €45 · A1 €49
- Etsy taxonomy_id: **1027** ("Home & Living > Home Decor > Wall Decor" —
  resolved via live `getSellerTaxonomyNodes`; Etsy has no plain
  "Posters"/"Wall Art" leaf, this parent node was chosen over
  "Art & Collectibles > Prints > Giclée" (id 121) as the better fit)
- Etsy shipping_profile_id: **resolved once per candidate, not per group
  (v4.12) — `288734253315` ("Gelato: Free shipping", €0 to
  every destination, confirmed live 2026-08-01 via `GET
  /v3/application/shops/{shop_id}/shipping-profiles`; owner decision
  2026-08-01).** One listing gets
  exactly one Etsy shipping profile; under v4.12 that's resolved once for
  the whole candidate rather than once per aspect-ratio group. The
  previous per-group Small/Large split (5x7 → Small `287910553824`,
  primary + 10x24 → Large `287910565714`) no longer applies once sizes
  share a listing. **Retail prices are unchanged** — Gelato's per-item
  shipping (€5.10–€5.86) is billed to the seller whichever profile is
  set, and is already inside the cost basis those prices were built on;
  all six sizes clear cost at 21–44 % with €0 shown at checkout. See
  `docs/2026-08-01-gl22a-findings.md` GL-22b and this PRD's margin table.
- Etsy production_partner_ids (Gelato): **[5717252]** — resolved via live
  `getShopProductionPartners` after Gelato was manually added as a
  production partner in Shop Manager → Settings → Partners you work
  with (listed there as "A print shop", Brussels, Belgium).
- Etsy who_made value: **"i_did"** — verified live: the API's `who_made`
  enum has only 3 raw values (`i_did`/`someone_else`/`collective`), no
  separate AI-disclosure/"tools used" field exists in the listing API.
  Etsy's "Designed by a seller / made with an AI generator" label is just
  the display name for `i_did`, not a distinct settable value — so the AI
  disclosure stays via `who_made: i_did` + the written description text;
  the "What tools are used?" question is not API-settable (keep the
  description disclosure, don't drop it). Must be paired with
  `is_supply: false` and `when_made: "made_to_order"`.
  **Re-verified 2026-08-06 (GL-37) — the answer stands, and now has a
  tracking link and a consequence.** Both Creativity Standards questions —
  "How does your shop produce this item?" (`production_process`) and "What
  tools are used to make this item?" (`tools_used`, where "an AI generator"
  lives) — are **absent from the v3 API entirely**: not on the listing
  (verified by a full raw `GET /listings/{id}` dump on two live listings,
  not a field-name grep), not among `taxonomy_id` 1027's 15 properties, and
  **not settable as a shop-level default**. Upstream tracking:
  **`etsy/open-api` GitHub Discussion #1630** (opened 2026-06-22, unactioned
  as of 2026-08-06) requests exactly these two fields. Full evidence:
  `docs/2026-08-06-gl37-findings.md`. **The operational consequence, which
  matters more than the API answer:** the only way to set them is the web
  listing editor, and **the editor's sole save action is "Activate with
  changes" — there is no draft-save, so ticking the disclosure activates the
  listing.** Owner decision 2026-08-06: **accept the manual per-listing
  step — the owner is the publish gatekeeper, and ticks "an AI generator" as
  part of the same editor save that takes the listing live.** This is the one
  part of the pipeline that is not unattended, by Etsy's design and not ours.
  **Two consequences that are now load-bearing, so do not undo either half
  without re-reading the other:** (1) **the prose AI/production-partner
  disclosure has been removed from listing descriptions**
  (`compliance_draft.DISCLOSURE_TEXT` is `""` and the draft prompt forbids
  reintroducing one) — that is only safe because the structured tick happens
  at publish; and (2) **GL-29, programmatic draft→active activation, is
  cancelled** (parked as GL-29b) — `etsy_client.update_listing_state` stays
  `# DELIBERATELY UNWIRED` with its guard test intact. **Wiring up automated
  activation while the description carries no disclosure would publish a
  listing with neither the structured field nor the text.** If either half is
  ever revisited, revisit both. Re-check quarterly (plan item GL-39) and start
  from Discussion #1630 rather than re-deriving; if it ever looks shipped,
  confirm with a full response dump, not a field lookup. Under v4.11 these are
  applied on the **listing patch** (`updateListing`), not at listing
  creation (Gelato creates the listing — see the integration constraint).
- Etsy shop_section_id: **59380312** — manually created "Posters" section
  in Shop Manager (per spec section 1's dedicated-section note); applied via
  `shop_section_id` on the **listing patch**, shared across all groups for a
  candidate (`config/static_config.json`'s `etsy_shop_section_id`). NOTE:
  the current code still sets these fields at create time via
  `build_size_listing_data()` in `pipeline/publish_primary_group.py` /
  `publish_group.py`; the v4.11 rework repoints that field set from create
  to patch (title loses its per-size suffix, price moves to per-variant
  inventory).
- Shop listing currency: **EUR** (resolved, spec section 1)

## Conventions
- One module per pipeline stage, independently testable, per section 4.
- Commit after each stage passes its manual M1 test.
- Never call Etsy publish or Gelato product-create against real
  endpoints without an explicit go-ahead during development — use
  Gelato/Etsy sandbox or dry-run flags where available while iterating.
- Before the first real M1 manual run: at minimum, the 8x12″ (primary)
  templates must be real. Before the M1 multi-size fan-out test: at
  minimum, one secondary size's templates must also be real.
- **Dry-run changes what a call *does*, never which code path reaches it.**
  A dry run that takes a different branch from live is not a rehearsal, it is
  a different program — and it proves nothing about the branch it skipped.
  GL-48: the 10x24 print crop was gated on `GELATO_LIVE_MODE`, so two soak
  nights submitted the uncropped master and were structurally incapable of
  observing the defect they were meant to catch. Gate the *side effect* (the
  HTTP call, the write), not the value being computed.
- **Verify a Gelato integration by measurement, not by status code.** GL-22a
  Q2 proved Gelato returns `200` for changes it silently drops. After any live
  create, run `python scripts/gelato_template_check.py <product_id>` — it
  diffs `static_config.json` against the live templates and prints the placed
  artwork aspect per variant. Note that `productImages[]` are 1000×1000 scene
  previews, **not** the submitted print file: the file's own aspect is not
  readable from the API, only the rectangle the artwork occupies on the paper.
  The script does print the submitted file's own dimensions and aspect next to
  the placed one (GL-53 rider), so "what we sent" vs "what the template did
  with it" is one line of output rather than a trip to the Design editor.
- **A swallowed per-item exception must always leave a state change behind.**
  GL-7's per-stage isolation stops one stage's crash killing a whole run, and
  in exchange it made per-item failures invisible at *both* levels: a
  `try/except: continue` inside a stage loop leaves the row exactly as it was,
  so it reads as "hasn't run yet", and the stage returns success, so no
  Telegram notification fires. GL-46: 8 of 8 candidates sat at `pending`
  overnight with nothing anywhere saying so. Any per-item catch inside a stage
  loop must (a) write the failure onto the row — a status plus a reason — and
  (b) let the stage still fail once at the end, after the loop has given the
  other items their turn. Self-healing on the next cycle is not a substitute:
  it hides a persistent failure behind a transient one's recovery.
- **Listing copy is evergreen, and copy is recoverable without touching the art
  (GL-55/GL-56, owner 2026-08-10).** A listing stays up all year, so the copy
  never names a dated event, festival or retail moment — the niche is sanitised
  before the drafting prompt sees it and the output is checked after
  (`compliance_draft.SEASONAL_TERMS`, used at both ends; the principle is
  "calendar date or named festival", while atmospheric words for a season of
  nature stay allowed). Letting the event inform genuinely tasteful copy is the
  eventual target and belongs with GL-10c, not here. The other half: Telegram's
  `📝 Redo copy only` (`redraft:{group_id}`) redrafts the listing text and
  **never** regenerates the artwork — it exists because `✏️ Edit` destroys a
  design the owner already liked, and because a design is only ever
  image-generated once. `critic_pass.run_critic_pass(copy_only=True)` carries
  that guarantee into the retry loop.
- **An instruction in a prompt is a preference, not a control.** If a decision
  says the copy must never contain something, an assertion has to say so too, in
  code, next to the decision and cross-referenced from it. GL-53: `DISCLOSURE_TEXT`
  was emptied on 08-06 and 27 of 27 drafts kept the AI-disclosure sentence,
  because the prompt was the only thing enforcing it — and the same prompt's
  opening line handed the model the vocabulary it then asked it not to use.
  Also: when auditing one field, read the whole row. Drift class (c), the
  digital-download wording on a physical product, was the most serious of the
  three and nobody was looking for it.
