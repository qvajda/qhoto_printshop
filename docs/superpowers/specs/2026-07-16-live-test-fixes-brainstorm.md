# Live-test feedback: root-cause brainstorm & fix plan (2026-07-16)

Context: first end-to-end live run surfaced 11 defects. This doc traces each
to a root cause and proposes the fix. Two architecture decisions were made up
front and drive most of the plan:

- **Etsy integration model → "Gelato pushes, we patch".** The Gelato store is
  connected to Etsy and auto-creates listings (it created ~49 shipping
  profiles on connect). We lean into that: Gelato creates ONE listing per
  design, then we PATCH it via the Etsy API to fix metadata. We stop creating
  listings ourselves.
- **Listing shape → one listing per design, sizes as variants.** The 12
  config slots are really 2 Gelato multi-variant templates (portrait/
  landscape) with size as the variant. One Gelato product with N size
  variants → one Etsy listing with N variations + per-variant price.

This supersedes SPEC v4.10's "one listing per size" model (section 3, step 7 /
section 4). SPEC must be updated to v4.11 as part of this work.

---

## The central root cause

`gelato_client.create_product_from_template` calls
`ecommerce.gelatoapis.com/v1/stores/{storeId}/products` — the **Gelato Store**
integration, which mirrors products into the connected Etsy shop as listings.
The pipeline ALSO builds listings directly via `etsy_client.create_draft_listing`.
The two collide. What reached Etsy live was Gelato's push (Gelato-format
titles, default description, no tags/section/partner) — our rich
`build_size_listing_data` never governed the live listing.

Everything below is either a direct consequence of this collision or an
independent bug the live run exposed.

---

## Item-by-item

### 1. Generated images are lifestyle mockups, not the art itself
**Root cause.** `generate.py` `NICHE_STYLE_SCAFFOLD` = "A minimalist botanical/
nature wall art print: {niche}…" and niches from `research.py` contain phrases
like "wall poster" / "wall art and posters". FLUX.1 reads "wall poster / wall
art print" as a *scene* and renders a framed poster hanging on a wall in a
room. That room photo then becomes the printed artwork.

**Fix.** Prompt engineering only (no model change — FLUX.1 [schnell] stays):
- Rewrite the scaffold to force flat 2D artwork that fills the frame:
  e.g. "flat 2D artwork, full-bleed, fills the entire frame edge to edge, no
  frame, no border, no wall, no room, no mockup, no photograph of a poster".
- Sanitize the niche before injection — the niche should describe the
  *subject/style* ("mid-century botanical line art"), not the product
  container ("wall poster"). Either strip "poster/wall art/print" tokens from
  the niche string before formatting, or change `research.py` to emit
  subject-only niches.
- Add one runnable check: assert the built prompt contains the flat-art
  guardrails and no scene tokens.

### 2. Only 5 publishes reached Etsy/Gelato
**Root cause.** Downstream of the collision + retries + Gelato timeouts, not a
standalone bug. Per-size publish loop (`publish_primary_group`) swallows
per-size exceptions and continues, so partial fan-out leaves gaps. The
variant consolidation (item 6) collapses N per-size calls into 1 per listing,
removing most partial-failure surface. Re-evaluate after items 3/4/6 land.

### 3. A design reached Etsy without Telegram review
**Root cause.** `primary_mockup` creates the Gelato store product *before*
review (to get a mockup image for the digest). Because the store is
Etsy-connected, that pre-review product creation pushes a listing to Etsy.
`isVisibleInTheOnlineStore: False` did not prevent a live listing appearing.

**Fix (needs Gelato behavior verification).** Options, in preference order:
- (a) Do not create a store product pre-review. Get the mockup preview from a
  non-publishing Gelato preview path if one exists; create the store product
  only on approval. Cleanest — no pre-review Etsy surface at all. **Caveat:**
  the digest's review images come *only* from the productImages of a created
  store product (`primary_mockup.py:83`, `group_mockup.py:83`). Approach (a) is
  viable only if Open Q3 finds a non-publishing preview endpoint; otherwise the
  review gate loses its image and (b) is forced.
- (b) Keep pre-review creation but guarantee it stays a non-synced draft, and
  only trigger the Etsy sync/activate on approval. Requires confirming exactly
  what `isVisibleInTheOnlineStore` and Gelato's publish flag do.
- Decision gated on a Gelato dashboard/API check (see Open Questions).

### 4. Candidate 3: only 10x24 and 5x7, twice each; no primary sizes
**Root cause (two bugs).**
- *Twice each:* creation is non-idempotent on retry. Note there is **no
  shared helper** — three distinct create paths call
  `create_product_from_template`: `primary_mockup.py:83`, `group_mockup.py:83`
  (double-attempt at 105-109), and `publish_primary_group.create_gelato_product`
  (`:117`, retried at 240-251). Each re-calls create on retry without reusing/
  deleting a product the first attempt may have already made server-side
  (create succeeds, then polling times out → retry duplicates).
- *No primary sizes:* `publish_primary_group.py:323` flips the whole primary
  group to `approved_published` and the candidate to `completed` when *any*
  size published (`any_published`). So an 8x12 failure with some other size
  "published" still opens the 5x7/10x24 fan-out gate (`group_mockup.py:151-155`),
  producing secondary products for a design whose primary size never shipped.

**Fix.**
- Refactor the three create paths to ONE shared `create_or_reuse_gelato_product`
  helper, then put the idempotency guard there (true root-cause, per the
  sibling-caller rule): before creating, if `group_products.gelato_product_id`
  is set, poll/reuse it; on a genuine failed-create retry, delete the orphan
  first. **Residual window:** the id is persisted only *after* a successful
  create (`group_mockup.py:89`); if the create HTTP call itself times out, no
  id is stored and a retry can still duplicate. Mitigate with a
  short pre-create existence check (list store products by title/externalId)
  or accept-and-reconcile in cleanup — flag, don't over-build.
- The `any_published` gate is largely dissolved by item 6 (primary becomes a
  single atomic create/publish call, so "some sizes published" stops being a
  reachable state). Confirm after item 6 lands.

### 5. 10x24 is the ISO image dropped in the middle with white bars
**Root cause.** `group_mockup.py` line 85 passes `candidate['base_image_url']`
untouched into the 10x24 template. No per-aspect-ratio re-crop exists anywhere
(the spec's "re-crop of the same approved artwork" was never implemented).
Gelato places the ~1:1.414 image into the elongated 10x24 placeholder in
"fit/contain" mode → white bars top and bottom.

**Correct source ratio.** Generation is `aspect_ratio: "2:3"` = 0.667
(`replicate_client.py:57`), NOT ISO 1:1.414. And the primary group is itself
**not single-ratio**: 8x12 = 2:3 (0.667) but A3/A2/A1 = ISO (0.707) — so
"primary → no crop" is false, and CLAUDE.md's "renders identically, just
scaled" is imprecise. Base all crop math on the real 2:3 source.

**Fix (recommended: center-crop cover, no outpaint).** Every target ratio is
reachable as a pure cover-crop from the 2:3 source:
- 10x24 (w/h ≈ 0.417, narrower/taller than 0.667) → crop the sides, keep full
  height.
- 5x7 (≈ 0.714, wider) → crop top/bottom, keep full width.
- A3/A2/A1 (0.707, slightly wider than 0.667) → tiny top/bottom crop.
- 8x12 (0.667) → no crop.

Two-tier fix, laziest first:
- First check whether the Gelato template placeholder can be set to
  "fill/cover" instead of "fit" in the dashboard (zero code, Open Q5). If focal
  control is adequate for centered minimalist art, done.
- Else add a small `crop_to_ratio(image, w, h)` step (Pillow center-crop,
  cover). One function, one assert-based test (output dimensions match target
  ratio). No outpaint cost/risk.
- **Hosting gap:** a cropped file needs a public `fileUrl` for Gelato — base
  images are Replicate-hosted (`replicate_client.py:49`) and there is **no
  image-upload/hosting helper in the pipeline today** (only Etsy byte-upload
  and Gelato fetch-by-URL). The code-crop path requires deciding where the
  cropped file is hosted (reuse Replicate output, a bucket, or Gelato's own
  asset upload if it has one). This is a real sub-task, not a detail — it also
  favors the dashboard fill-mode path, which needs no hosting at all.
- Side-cropping loses ~37% width on 10x24; acceptable for v1, leave a tuning
  note. Revisit outpaint only if compositions demonstrably break.

### 6. Each publish is a separate listing instead of size variants
**Root cause.** One Gelato product is created per size (each with a single
`templateVariantId`), so Gelato mirrors one Etsy listing per size.

**Fix (the big one).** Create ONE Gelato product per listing, passing all of
that group's sizes in the `variants` array of the template call:
- Primary listing = 1 product, variants [8x12, A3, A2, A1].
- 5x7 listing = 1 product, variant [5x7] (its own crop).
- 10x24 listing = 1 product, variant [10x24] (its own crop).
→ 3 Etsy listings max per design, each with its size variations.
- Per-variant price: verify whether Gelato's create-from-template accepts a
  per-variant price; if not, set prices via Etsy `updateListingInventory`
  during the patch step (item 7). Either way, price moves off the listing body
  and onto variants — the single `price_eur` on the listing becomes per-variant.

**DB migration — broader than "group_products only" (trace before coding):**
- `group_products` (schema.sql:67-70): today one row per size holding its own
  `gelato_product_id`/`etsy_listing_id`/`title`/`price_eur`. New shape: one
  Gelato product + one Etsy listing per *group*; sizes become variant rows
  under it. `gelato_product_id`/`etsy_listing_id` move up to the group;
  `price_eur` stays per-variant; per-size `title` largely goes away (see below).
- `product_images` FKs `group_product_id` (schema.sql:80) — images are now
  per-listing, not per-size.
- `listing_metrics_snapshots` FKs `group_product_id` (schema.sql:106) — metrics
  become per-listing (per-variant granularity is lost/changes; the future
  performance monitor, spec §6, must roll up at the listing not size).
- **Review-query invariant:** `critic_pass.py:57`, `group_critic_pass.py:20`,
  `group_digest.py:15,30` all assume exactly one `status='created'`
  group_product per group. The reshape MUST preserve that invariant (one
  product per group already satisfies it — verify each query still holds).
- `SIZE_TITLE_SUFFIXES` + per-size title in `build_size_listing_data`
  (`publish_primary_group.py:21-28`) become wrong: a variant listing has ONE
  title with no size suffix. Item 7's "reuse the field set, repoint
  create→patch" is therefore NOT wholesale — drop the size suffix, move price
  to inventory. Shipping-profile mapping stays per-group (already is), and each
  group is one listing, so the existing `get_group_type_for_size` →
  `get_shipping_profile_id` per-group resolution still works unchanged.

### 7-8, 10-11. Title, description, tags, shop section, production partner missing
**Root cause.** All four are consequences of item's central cause: Gelato's
push created the listing, so our rich `build_size_listing_data`
(title/description/tags/section/partner/who_made/taxonomy) never applied.

**Fix.** Under "Gelato pushes, we patch": after Gelato creates & syncs the
listing, resolve the Etsy `listing_id`, then call Etsy `updateListing` to set
title, description, tags, `taxonomy_id`, `who_made`, `when_made`, `is_supply`,
`shop_section_id`, and `production_partner_ids`. Reuse the
`build_size_listing_data` field set (minus the per-size title suffix and price,
per item 6), repointed from create to patch. Add an idempotency guard so
re-patching an already-patched listing is a no-op.

**Load-bearing unknown (see Open Q1).** `create_product_from_template` returns
only Gelato's product id (`gelato_client.py:88`), NOT an Etsy `listing_id`.
Gelato's Etsy sync is asynchronous — the listing_id almost certainly is not in
the create response and must be polled (likely `externalId` via `get_product`).
The *entire* patch approach depends on reliably obtaining that id. This is the
biggest hole in the plan; resolve it first.

### 9. Etsy "What tools are used?" → "An AI generator" not ticked
**Root cause.** Never set — no code touches it.
**Likely infeasible via API — mostly already answered.** CLAUDE.md + verified
user memory state Etsy `who_made` has only 3 enum values and "no separate
AI-disclosure field exists anywhere in the spec"; the "made with AI / tools
used" label is the display name for `i_did`, not a distinct listing-API field.
So "set a structured AI flag in the patch step" is probably NOT possible via the
API — the written description disclosure stays the compliance mechanism. Action:
a short confirmation against the current Etsy API (has an AI-tools field been
added since?), but expect the answer to be "keep the description disclosure, no
API field to set." Downgraded from a build task to a verify-and-document task.

---

## Cross-cutting work
- **SPEC bump to v4.11** capturing: variant-listing model, Gelato-pushes-we-
  patch integration, re-crop step, AI-tools attribute. Update CLAUDE.md
  hard-constraints (the "one listing per size" and "12 single-variant
  templates" language is now wrong).
- **DB migration** for the group→one-listing/product, size→variant reshape
  (item 6). Existing live rows from the smoke test are disposable.
- **Idempotency** is a recurring theme (items 3, 4, 7) — make Gelato create
  and Etsy patch safe to re-run; the pipeline is crash-and-retry by design.

## Open questions (verify before/while implementing — do not guess APIs)
1. **(Highest — gates the whole patch approach.)** How do we get the Etsy
   `listing_id` after Gelato's async sync? `create_product_from_template`
   returns only the Gelato product id (`gelato_client.py:88`). Is it
   `externalId` on `get_product`, and how long until it populates? Items
   7/8/9/10/11 all depend on this.
2. Gelato: does `isVisibleInTheOnlineStore:False` prevent the Etsy listing
   from appearing, or only hide it? What flag actually triggers the Etsy
   sync/activate? (Gates item 3's approach a vs b.)
3. **(Load-bearing for the review mechanic.)** Gelato: is there a mockup-
   preview endpoint that does NOT create a store product? Digest images today
   come only from creating a store product (`primary_mockup.py:83`,
   `group_mockup.py:83`). If item 3 takes approach (a) and no such endpoint
   exists, the review gate has no image to show. Must resolve before
   committing item 3's direction — not late.
4. Gelato: does create-from-template accept per-variant prices, or must price
   be set via Etsy `updateListingInventory` post-sync? (Gates item 6/7 pricing.)
5. Gelato: can the template placeholder be set to fill/cover in-dashboard,
   avoiding a code crop step + image hosting entirely? (Gates item 5's laziest
   path — strongly preferred since the code path needs new image hosting.)
6. (Low, likely already answered — see item 9.) Confirm Etsy still has no
   AI-tools API field; expect to keep the description disclosure.

## Suggested sequencing
1. **SPEC v4.11 + CLAUDE.md update FIRST.** The "one listing per size" flow and
   "12 single-variant templates" language are *hard constraints*; leaving them
   in place while implementing items 6/7 means any agent works against
   contradictory project instructions. Rewrite the constraints before touching
   code.
2. Item 1 (prompt) — isolated, unblocks producing real art to test the rest.
3. Resolve Open Q1 + Q3 + Q5 (Gelato behavior probes) — they gate items 3, 5,
   6, 7 and are cheap to answer against the live API/dashboard.
4. Item 5 crop — needed before any secondary-group mockup looks right.
5. Item 6 variant consolidation + DB migration — the structural core.
6. Item 7/8/10/11 patch step — builds on item 6's single listing.
7. Item 9 — verify-and-document (expected: keep description disclosure).
8. Item 3 pre-review leak — depends on item 6's create flow + Q2/Q3.
9. Item 4 idempotent-retry refactor (shared create-or-reuse helper) — harden
   once the create flow is settled.
10. Item 2 — re-measure; likely resolved by the above.
