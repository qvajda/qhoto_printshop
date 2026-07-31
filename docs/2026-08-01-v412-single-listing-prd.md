# PRD — v4.12: one Etsy listing per artwork (GL-22)

Status: **awaiting owner sign-off — no implementation until approved.**
Research gate: `docs/2026-08-01-gl22a-findings.md` (four measured answers,
live-call ledger, impact map, GL-22b/c arithmetic — read that first, this
PRD assumes it). Supersedes SPEC v4.11 sections 3 and 4. Plan of record:
`docs/2026-07-22-go-live-plan-of-attack.md`, GL-22/22a/22b/22c/22d.

## Problem

v4.11 publishes a design as **three** Etsy listings — one per aspect-ratio
group (primary, 5x7, 10x24). This works and sells today, but three
near-identical listings per design cannibalise each other's search placement
and split reviews/favorites across three pages for what a buyer experiences
as one product in different sizes. The owner's direction (2026-07-31): one
listing per artwork, all six sizes as variants of it, gallery = primary
mockups always + 5x7 mockups if that crop passed review + 10x24 mockups if
that one did. The review flow (three digest entries, three independent
Approve/Edit/Reject decisions) does not change — only the product/listing
shape underneath.

## Success criteria

- A design that has passed primary review, and optionally 5x7 and/or 10x24
  review, exists as **exactly one** Etsy listing carrying every approved
  size as a variant, at that size's own price.
- The gallery on that listing contains the primary mockups always, plus the
  5x7 group's mockups if and only if that group's decision is `approved` (or
  `edited`), plus the 10x24 group's mockups under the same rule — and grows
  in place as later groups are decided, without disturbing images already
  uploaded from an earlier-decided group.
- Rejecting or abandoning the 5x7 or 10x24 group deletes **nothing** on the
  Gelato/Etsy side — the shared product/listing and every other group's
  variants and images are untouched.
- No pipeline code path can silently drop or duplicate a size's price, image,
  or variant during the multi-group build-up.
- The two CLAUDE.md constraints this change makes wrong are rewritten before
  any live write happens under the new shape.

## Scope

**In scope:**
- Schema: `group_products` (and the tables hanging off it) move from
  per-group to per-candidate ownership, additively (Task 2 of the findings
  doc has the concrete column/table list).
- `create_or_reuse_group_product`: reuse-key changes from `group_id` to
  `candidate_id`; the create call carries a per-group image per variant in
  one `create-from-template` call (Q1: proven to work in one call, no
  Gelato template edit needed).
- Gallery assembly: images from up to three groups compose one listing's
  gallery, in rank order, with a `len(images) <= 20` assertion (not an
  assumption) and correct scoping so one group's image rebuild never wipes
  another group's already-uploaded images (findings doc flags this as the
  sharpest correctness risk in the create path).
- Abandon/reject/cleanup: `critic_pass.discard_superseded_attempt`,
  `cleanup.py`'s two Gelato-product-deleting queries, and (no change needed,
  confirmed) `publish_group.py`'s reject branch — all stop deleting a shared
  product on a single group's rejection.
- Shipping profile: resolved once per candidate instead of once per group
  (GL-22b decides which profile).
- `group_mockup.py`, `group_critic_pass.py`, `digest.py`/`group_digest.py`
  wording and data-shape changes as needed (exact extent flagged as open in
  the findings doc's impact map — not fully traced this pass).
- `run_m1_live_test.py` and the test suite updated for the new shape.
- SPEC v4.12 (new doc, supersedes SPEC v4.11 §§3–4).
- The CLAUDE.md constraint rewrites below.
- A `delete_listing` function added to `etsy_client.py` and a re-authorised
  Etsy OAuth token with `listings_d` scope (this session needed to delete
  two research-artefact drafts and could not — see the findings doc's
  cleanup section).
- A fix to `update_listing_inventory` in `etsy_client.py`: it currently
  raises `HTTP 400: Expected float value for 'price' (got array)` whenever
  the inventory contains a product whose size isn't in the caller's
  `size_to_price` map, because it only normalises the `price` field for
  *matched* products — this is a live, previously-unexercised bug (found
  during Q4), and it will fire the first time any code calls this function
  with a real subset of a listing's sizes, which v4.12 does not currently
  need (the second GL-22c fallback that would have needed it is dead — see
  below) but which is worth fixing regardless since it's a landmine for the
  next thing that touches this function.

**Out of scope (this PRD, deferred to the sign-off decision or later work):**
- GL-22d, the owner's Gelato template edit — **struck**. Q1 proved it
  unnecessary: two variants sharing one `image_placeholder_name` carry
  independently-submitted artwork.
- Landscape orientation (GL-18) — unaffected by this change, same deferral
  as today.
- Any change to the review flow itself (digest cadence, Approve/Edit/Reject
  semantics) — explicitly unchanged per the brief.
- Publishing on primary approval and patching sizes in later (GL-22c option
  a) — **dead**, Q2 found no API path. Not built, not designed around.
- Creating all six variants up front and pruning rejected sizes Etsy-side
  (GL-22c option c) — **dead**, Q4 found the dropped variant does not
  self-heal on the Gelato side. Not built, not designed around.

## Constraints

- Live calls against Gelato/Etsy remain gated by `*_LIVE_MODE` env vars and
  the existing placeholder/replicate-URL guards in `gelato_client.py` —
  unchanged by this PRD.
- Artwork generation stays Replicate + FLUX.1 [schnell]-only; this PRD does
  not touch generation, only what happens to already-generated/already-
  cropped images at publish time.
- A design still offers 4, 5, or 6 sizes depending on which crops passed
  review (unchanged product behavior, changed only in that it's now one
  listing rather than up to three).
- Etsy's 20-photo cap is a hard ceiling the build must assert against, not
  assume compliance with.
- No implementation ships before the two CLAUDE.md rewrites below are
  reviewed and the owner has picked a GL-22b shipping-profile option and
  signed off on GL-22c's stall-rule shape (b-i vs b-ii, see Plan below).

## Plan

1. **Owner sign-off on this PRD**, including the GL-22b shipping profile
   pick and the GL-22c stall-rule shape (both prepared with arithmetic in
   the findings doc, not decided here).
2. **Schema migration** (additive): `group_products.candidate_id`,
   `group_product_variants.group_id`, `product_images.group_id`. No
   existing row rewritten; the four GL-9-era rows keep resolving under
   today's code path (see Migration and rollback below).
3. **`etsy_client.py` fixes**, independent of the rest: the
   `update_listing_inventory` float-price bug, and a new `delete_listing`
   function (needs a re-authorised token with `listings_d` — a manual step,
   same PKCE flow used for the 2026-07-17 scope change).
4. **`create_or_reuse_group_product` rework**: candidate-keyed reuse, per-
   group image resolution inside one multi-variant create call.
5. **Gallery assembly rework**: scoped image clear/rebuild per group, the
   20-image assertion, and resolving whether `patch_etsy_listing`'s image
   upload loop is a full re-upload or a delta (flagged unanswered in the
   findings doc — must be resolved in this step, before the delta-vs-full
   behavior is assumed for the append-across-two-reviews use case).
6. **Abandon/reject/cleanup rework**: the three call sites named in the
   impact map, each changed to stop deleting a shared product.
7. **Shipping profile**: one resolution point at candidate-level publish,
   per GL-22b's picked profile.
8. **Digest/mockup/critic wording + data-shape pass**: `group_mockup.py`,
   `group_critic_pass.py`, `digest.py`/`group_digest.py` — extent to be
   confirmed at implementation time per the impact map's flag.
9. **`run_m1_live_test.py` + test suite** updated for one-listing-per-
   candidate assertions.
10. **SPEC v4.12** written, superseding SPEC v4.11 §§3–4.
11. **Live-test delta** (GL-13, sequenced after this per the plan of
    record): see below.

## Migration and rollback

The four real rows from the GL-9 live run
(`group_products` ids 9/10/11/12/13 under candidate 39 — id 10 `published`
with real Etsy listing `4542159277`; id 12 `created` with no Etsy listing
id resolved yet) are **left alone**. The migration adds nullable columns and
a new join shape; it does not touch or backfill existing rows. Any code path
written for v4.12 must only ever see the new shape on `group_products` rows
created after the migration ships (a `candidate_id IS NOT NULL` gate is
sufficient — pre-migration rows keep `candidate_id NULL` and old code paths,
if any are still reachable, keep working against `group_id`).

**Rollback:** because the schema change is additive and no row is rewritten,
rollback is "stop calling the new code path," not a down-migration. If the
first live publish under v4.12 goes wrong (e.g. gallery assembly corrupts
across two reviews, or a shared-product delete guard has a gap and a
rejection deletes a live product other groups still need), the safe recovery
is: (1) do not delete the Gelato product or Etsy listing by hand — confirm
via `GET` what state it's actually in first, since Q2/Q3 both showed the
product/listing pair can silently desync without anything having "gone
wrong" from the buyer's side; (2) the affected candidate's `group_products`
row(s) can be manually flagged `publish_failed`/`deleted` in the DB to stop
the pipeline from retrying against a known-bad product, same as the existing
`publish_failed` recovery path from the first live run; (3) worst case, the
candidate's listing is deleted by hand (once `delete_listing` exists) and
the candidate is re-published from scratch — expensive but bounded, since
nothing before the Gelato/Etsy layer (generation, crops, critic passes) is
touched by this change.

## The live-test delta (GL-13)

Round 1 (the pending live re-test) proved the v4.11 shape: one listing per
group, gallery in rank order, critic pass over custom scenes,
`mockup_failed` retry with no Gelato fallback, the placeholder fail-loud
guard, real cover-crop reaching Gelato. Under v4.12, GL-13 must additionally
cover, none of which Round 1 exercised:
- **One listing carrying 4, 5, and 6 variants** across its lifecycle — start
  at 4 (primary approved, 5x7/10x24 still pending), grow to 5 or 6 as later
  groups are decided, without a duplicate product ever being created (the
  Q2 finding that `create-from-template` duplicates on a title collision
  makes this the single highest-value thing to prove live, not just in
  tests).
- **A gallery that grows across two reviews** — confirm the primary
  gallery's images survive untouched when the 5x7 group's mockups are
  appended later (the scoped-clear fix from the impact map, proven against
  a real Etsy listing, not just the DB).
- **A rejected secondary group that deletes nothing** — reject 5x7 or 10x24
  on a real candidate mid-run and confirm the shared product/listing and the
  other groups' data are untouched afterward (`GET` the product, count
  variants, before and after).
- **The stall rule** (per whichever GL-22c shape the owner picks) exercised
  for real — leave a secondary group `pending_review` past whatever window
  the PRD's sign-off settles on, and confirm the pipeline behaves as
  specified rather than either publishing early or hanging silently.

## Phasing

Everything through step 9 above (schema, create path, gallery assembly,
abandon/cleanup, shipping profile, digest/mockup wording, test suite) can
land behind the existing `GELATO_LIVE_MODE`/`ETSY_LIVE_MODE` dry-run flags
exactly as today's code does — dry-run mode already returns synthetic
IDs/responses without any network call (`gelato_client.create_product_from_
template`, `etsy_client.update_listing`, etc. all check `is_live_mode`
first). No live write is required to build or unit-test any of this. The
first live write under v4.12 should be a single manually-triggered
candidate, not a batch run, and should follow the same "two throwaway
products max, delete after" discipline this research session used, until
GL-13's delta above has passed once.

## The CLAUDE.md constraint rewrites

Two constraints in `CLAUDE.md` are made wrong by this change (per the
research session's brief); a third related paragraph (the per-group shipping
profile explanation) is also affected. No other constraint was found wrong
in this pass — flagging that absence rather than silently declaring the
audit complete, per the brief's own instruction to flag a third if found
rather than edit silently.

**1. Replace the "One Etsy listing per aspect-ratio group" bullet** (the one
reading `**One Etsy listing per aspect-ratio group, sizes are variants
(v4.11).**` …) **with:**

> - **One Etsy listing per artwork, sizes are variants (v4.12).** All six
>   sizes are Etsy variations of ONE listing for a candidate, each at its
>   own price — not one listing per aspect-ratio group. There is **one**
>   Gelato multi-variant template pair (portrait + landscape, unchanged from
>   v4.11) and the candidate's listing is one Gelato product created (or
>   grown) with whichever sizes have passed review as that product's
>   variants. A design still ends up offering 4, 5, or 6 sizes depending on
>   whether the 5x7/10x24 groups each pass their own review (unchanged from
>   v4.11) — it now offers them from one listing instead of up to three.
>   Adding a variant to an existing Gelato product has no API path
>   (confirmed live, GL-22a Q2 — `PUT` on the product resource silently
>   drops the added variant and severs the Etsy sync; the `/variants`
>   sub-resource is a different, incompatible custom-priced-product flow;
>   re-`create-from-template` with the same title creates a second product).
>   The listing is therefore created **once, when all three groups have
>   reached a terminal decision** (approved/edited/rejected) — never
>   incrementally.

**2. Replace the critic-pass retry-cap paragraph's group-abandonment
sentence** (the one reading `at the 5x7/10x24-group level it only abandons
that one group … its Gelato product(s) via DELETE …`) **with:**

> - Critic-pass retry cap is exactly 3 attempts per group, then abandon
>   that group only: log locally as `failed`. **Under v4.12 this never
>   deletes a Gelato product or Etsy listing** — the product/listing belongs
>   to the candidate, not the group, and other groups (already published or
>   still pending) depend on it surviving. Abandoning a group means: mark
>   that group `failed_abandoned`, exclude its sizes/images from the
>   candidate's listing build, and leave the shared product/listing alone.
>   At the primary-group level this still triggers the Go/Hold/Kill
>   fallback (abandoning the whole candidate before any listing exists) —
>   unchanged, because the primary group is decided first and no shared
>   product exists yet if it fails.

**3. Replace the shipping-profile paragraph's "per aspect-ratio group, not
per size" framing** (the `etsy_shipping_profile_id` bullet under Static
config values) **with** (exact replacement value depends on the GL-22b
decision — placeholder shown for the recommended option, `Free shipping`;
swap in Large/Small/re-price text if the owner picks differently):

> - Etsy shipping_profile_id: **resolved once per candidate, not per group
>   (v4.12) — recommended: `288734253315` ("Gelato: Free shipping", €0 to
>   every destination, confirmed live 2026-08-01 via `GET
>   /v3/application/shops/{shop_id}/shipping-profiles`).** One listing gets
>   exactly one Etsy shipping profile; under v4.12 that's resolved once for
>   the whole candidate rather than once per aspect-ratio group. The
>   previous per-group Small/Large split (5x7 → Small `287910553824`,
>   primary + 10x24 → Large `287910565714`) no longer applies once sizes
>   share a listing. See `docs/2026-08-01-gl22a-findings.md` GL-22b for the
>   margin arithmetic behind this pick.

## Open questions

- **`patch_etsy_listing`'s image upload loop** — full re-upload or delta on
  each call? Not resolved in this research pass (flagged in the impact
  map); must be answered before the gallery-assembly step is implemented,
  since it decides whether appending 5x7/10x24 images later is cheap or
  re-uploads the primary gallery every time.
- **GL-22c stall rule, shape (i) vs (ii)** — auto-publish-primary-only after
  a timeout and treat un-decided secondary groups as revisitable, or no
  timeout and let the whole listing wait indefinitely on a slow secondary
  decision? Needs explicit owner sign-off, not a default.
- **GL-22b final pick** — this PRD recommends `Free shipping`
  (`288734253315`) with the arithmetic in the findings doc, but it's a real
  revenue trade-off on default-region/US orders, not a strictly-better
  option; needs the owner's sign-off, not an assumed default.
- **`group_mockup.py`/`group_critic_pass.py`/`digest.py` exact diff size** —
  named as touched in the impact map but not fully traced this pass; budget
  in this session went to the live-call questions per the brief's stated
  priority order (Q1 first because it could delete GL-22d, which it did).
- **Q3's confound** — "does Gelato re-push and overwrite our patch" was only
  tested through an edit path (`PUT`) that itself breaks the Etsy sync; a
  cleaner test (a Gelato-side edit that does *not* go through `PUT`, if one
  exists — possibly only reachable from the Gelato dashboard) would need
  its own authorisation and live-call budget, not spent in this session.
  Treat "Gelato might re-push after a dashboard-driven edit" as an open
  risk in the PRD's plan, not a closed one.

---

**Awaiting owner sign-off — no implementation until approved.**
