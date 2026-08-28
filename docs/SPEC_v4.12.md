# Etsy AI-assisted POD pipeline — spec v4.12 (one listing per artwork)

**Supersedes `docs/SPEC_v4.11.md` sections 3 and 4.** Sections 1, 2 and 5–9 of
v4.11 are unchanged and remain the reference — read them there. This document
is deliberately a **delta**, not a re-transcription: v4.11's research inputs,
event calendar, compliance rules, milestones and open questions did not change,
and copying them here would only create two copies to keep in sync.

Decision record: `docs/2026-08-01-v412-single-listing-prd.md` (`[D1]`/`[D2]`/
`[D3]`). Measured constraints: `docs/2026-08-01-gl22a-findings.md`.
Build sessions: `docs/2026-08-01-gl22-session1-kickoff.md`,
`docs/2026-08-02-gl22-session2-kickoff.md`.

---

## Why v4.12 exists

v4.11 published a design as **three** Etsy listings, one per aspect-ratio group
(primary / 5x7 / 10x24). That works and sells, but three near-identical
listings per design cannibalise each other's search placement and split
reviews and favourites across three pages for what a buyer experiences as one
product in different sizes.

v4.12 makes a design **one Etsy listing**, with every size that passed review
as a variant of it. The review flow does not change: three digest entries,
three independent Approve/Edit/Reject decisions. Only the product/listing
shape underneath changes.

## The constraint everything is shaped by

**There is no API path to add a variant to an existing Gelato product**
(GL-22a Q2, measured live):

- `PUT` on the product resource silently drops the added variant *and* severs
  the Etsy sync.
- The `/variants` sub-resource belongs to a different, incompatible
  custom-priced-product flow.
- Re-`create-from-template` with the same title creates a **second** product.

So the listing cannot be grown incrementally. It is created **once**, when
every group has reached a terminal decision, carrying exactly the sizes that
were validated (`[D1]`). Everything below follows from that.

A second measured result makes the single call possible: **two variants
sharing one `image_placeholder_name` accept independently-submitted
`fileUrl`s in one `create-from-template` call** (Q1). The 8x12 variant carries
the master while the 5x7 variant carries the 5x7 cover-crop, in the same call.
This is what killed GL-22d (the owner's manual Gelato template edit) — it was
never needed.

---

## 3. Pipeline layer (superseding v4.11 §3)

### 3.1 Naming — read this before the code

`group_products` is **no longer "the Gelato product row"**. Under v4.12 it is
**the candidate's listing record**: one row per candidate, shared by all three
aspect-ratio groups, of which `gelato_product_id` is one *nullable* column —
NULL for the entire review window, filled in once at publish. The table was
deliberately **not renamed** (owner decision, 2026-08-01): a repo-wide rename
landing on top of this change's riskiest diff buys nothing the reader of this
paragraph doesn't already have.

`group_products.group_id` still records which group first opened the record.
It is not the owner of the row and must never be used as a reuse key —
`candidate_id` is. Pre-migration rows (GL-9 era) carry `candidate_id NULL` and
are still resolved by `group_id`, so their real, already-published Gelato
product is reused rather than duplicated by a candidate-keyed miss.

### 3.2 The stages, and where the weld was cut

The stage list is unchanged (research, generate, primary-mockup,
compliance-draft, critic-pass, digest, publish-primary-group, group-mockup,
group-critic-pass, group-digest, publish-group, cleanup). What changed is what
the mockup stages do.

Under v4.11, `create_or_reuse_group_product` did two jobs: it created the
Gelato product **and** rendered the local compositor mockups the review gallery
is made of. Under `[D1]` those two have incompatible timings — the review
mockups must exist **before** any group is decided, and the Gelato product can
only be created **after** every group is decided. No ordering satisfies both
while they share a function, so the weld was cut:

| Function | When | What it does |
|---|---|---|
| `group_product.render_group_mockups(conn, group_id, sizes, candidate, static_config, …)` | mockup stages, before any decision | Ensures the candidate's listing record exists (`status='pending'`, `gelato_product_id` NULL). Renders that group's scenes, writes its `product_images` and its `group_product_variants`. **No Gelato call.** |
| `group_product.create_candidate_gelato_product(conn, candidate_id, candidate, static_config, title, …)` | publish, once, after every group is decided | The single `create-from-template` call, carrying every validated size as a variant with **its own group's** `fileUrl`. Polls readiness. Flips the record to `created`. |

`group_products.status` needed no new value: `pending` already means "record
exists, no Gelato product yet", and `mockup_failed` now accurately means the
**local render** failed.

**Everything `render_group_mockups` writes is scoped `AND group_id = ?`.** This
is the whole point of the change. With one record per candidate, an unscoped
`DELETE FROM product_images WHERE group_product_id = ?` means the 5x7 group
rendering its mockups silently destroys the primary group's already-reviewed
gallery — and nothing downstream notices until a buyer sees the listing. The
same applies to the archive on disk: `artwork_store.persist_mockup_render` is
keyed `group_product_id + group_id + index`, because without `group_id` the
5x7 group's scene 0 overwrites the primary group's scene 0 file.

The **print-DPI guard** (`_assert_print_dpi`, 150 DPI floor) moved from the
create path to the render path. It guards that the master is large enough to
*print* each size — a print concern, not a Gelato one — so a too-small master
now fails before the owner spends a review on it rather than after. It still
runs before any DB write, so the "fails fast without orphaning a row" property
it was written for is intact.

### 3.3 The publish gate `[D1]`

`publish_primary_group.candidate_publish_plan(conn, candidate_id, static_config, *, now=None)`
returns `{"ready", "waiting_on", "stalled"}`. It is ready when:

1. the **primary** group's `decision` is `approved` (a rejected primary fails
   the whole candidate; an `edited` primary is mid-regeneration), **and**
2. every secondary group type **that has authored scene bundles** has reached
   a terminal state — `decision` in (`approved`, `rejected`), or `status` in
   (`rejected`, `failed_abandoned`, `stalled_skipped`).

`edited` is deliberately **not** terminal: it means "redo this one", and the
decision is overwritten by the next tap. A group type with no authored scenes
is skipped entirely, because `group_mockup` never creates a row for one and
waiting on it would deadlock the candidate forever.

`publish_primary_group.publish_primary_group()` keeps its name — it is still
the entry point of every approve path and of the M1 harness — but it now means
"evaluate the gate, publish if ready". **Approving the primary group publishes
nothing on its own.** Both the primary and the secondary approve paths, and the
secondary *reject* path, re-evaluate the gate; whichever decision is last
releases it.

`publish_candidate()` then does the two writes: one Gelato product, one Etsy
listing patch. Every included group flips to `approved_published` and the
candidate to `completed`; on failure every included group flips to
`publish_failed` and `retry_publish_failed_groups` re-attempts **per candidate**
(not per group) on the next poll cycle.

### 3.4 The stall rule `[D2]`

A predicate, not a stage. If a secondary group sits undecided past
`config.GROUP_REVIEW_STALL_DAYS` (**14**), the candidate stops waiting: the
group is marked `stalled_skipped` (added to the `groups.status` CHECK) and the
listing publishes with whatever *was* decided. The window is measured off
`groups.updated_at`; a group type whose row does not exist yet is measured off
the primary group's, so a permanently-broken secondary render cannot hang a
candidate forever.

**The reminder ping (GL-31).** `candidate_publish_plan` also reads the same
age helper to flag a secondary group still `pending_review` at or past
`config.GROUP_REVIEW_REMINDER_DAYS` (**10**, below the 14-day stall window) as
`reminder_due`, provided its digest already went out (a `group_messages` row
exists) and `groups.reminder_sent_at` is still NULL. `group_digest`'s cycle
re-sends that group's digest entry — the same `sendMediaGroup` + separate
`sendMessage` pair, bypassing the ordinary duplicate-send guard — and writes
`reminder_sent_at` in the same commit, so it fires at most once per group.
This is still only a predicate the gate's own evaluation surfaces; it does not
mark anything `stalled_skipped` and does not perturb `ready`/`waiting_on`.

**It does not fire until GL-7 evaluates the gate on a cadence.** There is no
scheduler today, so the effective behaviour is wait-indefinitely, which is
harmless while every run is hand-triggered. "The stall rule fires" is a GL-7
DoD item, not a GL-22 one. Test it by lowering the constant, never by waiting.

Why 14 days: a `stalled_skipped` group is revisitable **in principle only** —
Q2 means recovering a skipped size requires re-publishing the listing from
scratch. Waiting too long costs a design sitting unpublished, recoverable by
tapping a button; ageing out too early costs a size permanently missing from a
live listing, which is not. Argue with the number, not the mechanism.

### 3.5 Gallery assembly

The candidate's gallery is assembled across every group whose review passed, in
rank order (**primary → 5x7 → 10x24**), each group's own images in
`gallery_order`. A group whose decision is `rejected`, or whose status is
`failed_abandoned` / `stalled_skipped`, contributes **nothing** — it is
excluded, never deleted. `group_product.included_group_ids()` is the single
definition of "what goes on this listing"; every consumer reads it rather than
re-deriving the rule.

Etsy caps a listing at **20 photos**. That is **asserted, not assumed**:
`patch_etsy_listing` raises `GalleryTooLargeError` above the cap before it
uploads anything. Today's worst case is 10 primary + 1 5x7 + 2 10x24 = 13; the
assert is for when the scene library grows.

**`patch_etsy_listing` is idempotent.** Its upload loop is a full re-upload
with no delta and no dedup, so a second call after a partial failure would
duplicate the entire gallery on the live listing. Each uploaded row records
Etsy's own `listing_image_id` (`product_images.etsy_listing_image_id`, added in
this session) and rows carrying one are skipped.

### 3.6 Abandon, reject, cleanup — the deletion rules

**Net rule: abandoning a group marks it and excludes it. It deletes nothing.**

- `critic_pass.discard_superseded_attempt(conn, group_product_id, group_id, …)`
  deletes only that group's `product_images`, scoped by `group_id`. No Gelato
  `delete_product`, no `group_products` row delete. The group's variant rows
  stay — a retry re-renders the same sizes at the same prices, only the artwork
  changes.
- `cleanup.cleanup_orphaned_gelato_products` is **whole-candidate teardown
  only** (`candidates.status IN ('failed','abandoned')`, or a `publish_failed`
  record). The old "this group is rejected/abandoned" rule survives for
  pre-migration rows (`candidate_id IS NULL`) alone, where one product really
  did belong to one group.
- `cleanup.reclaim_stranded_pending_group_products` additionally requires the
  pending row to carry **no variants and no images**. Without that clause it
  would delete every live listing record ten minutes into its review window,
  since `pending` with no `gelato_product_id` is now the normal state for days.
- `publish_group`'s reject branch needs no special handling beyond the above —
  verified, not assumed.

There is **no delete-and-recreate fallback** anywhere in the create path. A
product whose variant set does not match what the validated groups need raises
`SharedProductVariantError` rather than routing around it; and
`render_group_mockups` refuses to record variant rows for a group arriving
*after* the product exists, for the same reason.

---

## 4. Technical layer (superseding v4.11 §4)

Unchanged from v4.11 unless listed here.

### 4.1 Schema deltas (all additive except one widened CHECK)

| Table | Column | Meaning |
|---|---|---|
| `group_products` | `candidate_id INTEGER` (nullable) | the listing record belongs to the candidate. NULL ⇒ pre-migration row, old resolution path. |
| `group_product_variants` | `group_id INTEGER` (nullable) | which group contributed this size. |
| `product_images` | `group_id INTEGER` (nullable) | which group contributed this image — what makes the scoped gallery rebuild possible at all. |
| `product_images` | `etsy_listing_image_id TEXT` (nullable) | Etsy's own id for an uploaded photo; presence ⇒ skip on re-patch. |
| `groups` | `status` CHECK gains `'stalled_skipped'` | `[D2]`. SQLite cannot widen a CHECK in place, so `groups` is rebuilt (rows copied verbatim, constraint only widens). |

Migrations: `migrate_group_products_candidate_id.py` (session 1),
`migrate_v412_gallery.py` (session 2). Both idempotent, both safe to re-run.
**Rollback is "stop calling the new code path", not a down-migration** — no
existing row is rewritten or backfilled, and the widened CHECK admits strictly
more than before, so pre-v4.12 code keeps working against it.

### 4.2 Static config

- `etsy_shipping_profile_id` collapses from a per-group-type dict to the single
  string **`"288734253315"`** ("Gelato: Free shipping", €0 to every
  destination) `[D3]`. `config.get_shipping_profile_id(static_config)` loses
  its `group_type` argument. `config.get_group_type_for_size()` is unchanged —
  it has other callers.
- **Retail prices are unchanged.** Gelato's per-item shipping (€5.10–€5.86) is
  billed to the seller whichever profile is set and was already inside the cost
  basis those prices were built on; every size clears cost at 21–44 %. What
  free shipping forfeits is the shipping *surcharge* the Small/Large profiles
  collected from default-region and US buyers — revenue the margin table never
  counted. Thinnest case (a 5x7 sold through Offsite Ads) still nets 16.4 %.
- `config.GROUP_REVIEW_STALL_DAYS = 14` `[D2]` — a named constant, not a
  literal in the gate, so the window is tunable without a code change.

### 4.3 What GL-13's live re-test must prove

Everything below is asserted in dry-run only and cannot be proven offline:

- **One listing carrying 4, 5, and 6 variants across its lifecycle** without a
  duplicate product ever being created. Q2's finding that
  `create-from-template` duplicates on a title collision makes this the single
  highest-value thing to prove live.
- **A gallery that grew across two reviews** — the primary group's images
  survive untouched when the 5x7 group's are appended, proven against a real
  Etsy listing rather than the DB.
- **A rejected secondary group that deleted nothing** — `GET` the product and
  count variants before and after.
- **The 20-image cap and the idempotent re-patch** against real Etsy responses;
  the `listing_image_id` shape is currently only exercised against a stub.
- **The stall rule**, which cannot fire at all until GL-7 runs the gate on a
  cadence.

Open risk carried forward from GL-22a: **Q3's confound.** "Does Gelato re-push
and overwrite our patch" was only tested through an edit path (`PUT`) that
itself breaks the Etsy sync. Treat "Gelato might re-push after a
dashboard-driven edit" as an open risk, not a closed one.
