# PRD — v4.12: one Etsy listing per artwork (GL-22)

Status: **decisions signed off 2026-08-01 — cleared to build in two sessions.**
Research gate: `docs/2026-08-01-gl22a-findings.md` (four measured answers,
live-call ledger, impact map, GL-22b/c arithmetic — read that first, this
PRD assumes it). Supersedes SPEC v4.11 sections 3 and 4. Plan of record:
`docs/2026-07-22-go-live-plan-of-attack.md`, GL-22/22a/22b/22c/22d.
Build kickoffs: session 1 ✅ `docs/2026-08-01-gl22-session1-kickoff.md`
(landed `6df9ba5`, `ed660c1`, `b0560df`, `4c878b3`); session 2
`docs/2026-08-02-gl22-session2-kickoff.md`.

## Session 1 outcome — one PRD assumption was wrong

Session 1 delivered its three workstreams, and found that **the function
this PRD scoped as "a small change at the caller" is welded to something
else**. Recorded here because it re-shapes session 2, not because it changes
any decision:

- **`create_or_reuse_group_product` does two jobs**: it creates the Gelato
  product *and* renders the local compositor mockups the review gallery is
  made of (`group_product.py:411–415`). Under `[D1]` those two have
  incompatible timings — review mockups must exist *before* any decision,
  the Gelato product can only be created *after* all of them. **The weld has
  to be cut**; no ordering satisfies both jobs while they share a function.
  Session 2 splits it into `render_group_mockups` and
  `create_candidate_gelato_product`.
- **The secondary path is deliberately broken between the two sessions.**
  With the reuse key on `candidate_id`, `group_mockup` for 5x7/10x24
  resolves the candidate's primary product, mismatches sizes and hits
  session 1's new `SharedProductVariantError`. Dry-run-only ground, nothing
  live runs — but real, not latent, and it is session 2's first task.
- **The shared-product collision resolved as this PRD's plan predicted.**
  The sizes-changed delete now fires only when every variant belongs to the
  calling group; otherwise `SharedProductVariantError`. A review pass found
  one hole — pre-migration variants carry `group_id NULL`, so a legacy
  product reads as unshared however many sizes it backs, and candidate 39's
  id-10 row (live listing `4542159277`) would have cleared the check.
  Unreachable under current callers; closed anyway by refusing the recreate
  on any `published` row.
- **The "gallery assembly is the sharpest risk" call was right, and is now
  concrete rather than hypothetical.** `group_product.py:433` and
  `critic_pass.py:446` both run `DELETE FROM product_images WHERE
  group_product_id = ?`; under a candidate-keyed product, 5x7 rendering its
  mockups deletes the primary's gallery. Seven call sites read
  `product_images` by that key.
- **Owner decision, 2026-08-01: `group_id` scopes, the FK stays.**
  `product_images` keeps both `group_product_id` and `group_id`; deletes
  gain `AND group_id = ?`. Making `group_product_id` nullable was rejected —
  it forces a SQLite table rebuild and breaks the additive-migration
  guarantee this PRD's rollback story rests on. Renaming `group_products`
  (now a misnomer: it is the candidate's *listing record*, with
  `gelato_product_id` as one nullable column) was also rejected as a
  repo-wide diff landing on top of the riskiest change. **SPEC v4.12 should
  state the naming instead.**
- **A process failure worth carrying forward.** A subagent ran `git stash`
  to "compare against a clean checkout" and wiped the working tree —
  its own work, the parallel agent's, and the owner's in-flight edits.
  Recovered in full. **Standing rule: subagent briefs need a command
  denylist, not just a file allowlist** — the destructive command took no
  file arguments, so the allowlist could not catch it. Session 2's kickoff
  carries the denylist (§4).

## Owner decisions — signed off 2026-08-01

Three decisions were open when this PRD was written. All three are now
closed. Nothing else in the PRD was re-opened by them; the deltas each one
causes are folded into Scope and Plan below and marked `[D1]`/`[D2]`/`[D3]`.

- **[D1] Publish timing = GL-22c option (b), create-once-when-all-groups-are-
  decided.** The listing is created when all three groups have reached a
  terminal decision, and carries **only the sizes that were validated** —
  a rejected or abandoned group contributes no variant and no gallery image.
  This was already the PRD's assumed shape (options a and c were killed by
  Q2/Q4); the sign-off makes it the decision rather than the last one
  standing.
- **[D2] Stall rule = a long timeout, no reminder** (GL-22c shape i, revised
  by the owner 2026-08-01 after an initial "48 h nudge → 96 h skip"
  decision). If a secondary group sits `pending_review` past **14 days**,
  the candidate stops waiting: that group is marked `stalled_skipped` and
  the listing publishes with whatever *was* decided. **The reminder ping is
  deferred to post-go-live** (GL-31). See the Stall rule section below.
- **[D3] Shipping profile = `Gelato: Free shipping` (`288734253315`),
  €0 to every destination, resolved once per candidate.** Retail prices are
  **unchanged** — see the margin check below for why no re-pricing is needed.

### The margin check behind [D3]

The owner's framing was "free shipping shown to customers, costs covered
within the listed price". That is correct in effect but worth stating
precisely, because it implies a re-pricing that is **not** required:
Gelato's per-item shipping (€5.10–€5.86) is billed to the seller regardless
of which Etsy profile the listing carries, and it is **already inside** the
cost figures the current retail prices were set against. Recomputed from
`docs/Premium Matte Paper Poster_BE_2026-07-05.csv` at Etsy's 9.5 % + €0.25:

| Size | Gelato total cost | Retail | Net | Margin | Margin if Offsite Ads fires (15 %) |
|---|---|---|---|---|---|
| 5x7 | €12.88 | €19 | €4.06 | 21.4 % | 16.4 % |
| 8x12 | €13.64 | €24 | €7.83 | 32.6 % | 27.6 % |
| A3 | €17.92 | €35 | €13.50 | 38.6 % | 33.6 % |
| A2 (portrait) | €20.21 | €39 | €14.84 | 38.0 % | 33.0 % |
| A2 (landscape) | €19.60 | €39 | €15.45 | 39.6 % | 34.6 % |
| 10x24 | €20.57 | €45 | €19.91 | 44.2 % | 39.2 % |
| A1 | €23.45 | €49 | €20.64 | 42.1 % | 37.1 % |

Every size clears cost with no price change, and the spread reproduces SPEC
v4.11 section 4's stated ~21–44 %. What free shipping actually forfeits is
the shipping **surcharge** the Small/Large profiles collected on top of item
price from default-region and US buyers — revenue the margin table never
counted (EU buyers see €5.86–€7.04 either way, so the change is close to
neutral for the likely-majority segment). The thinnest case, a 5x7 sold
through Offsite Ads, still nets 16.4 %; flagged as the floor, not as a
blocker.

### The stall rule [D2] — small, because the reminder is deferred

Dropping the nudge removes the reason this needed a stage of its own. With
nothing to *send*, the rule is a **predicate, not a process**: the publish
gate already asks "have all three groups reached a terminal decision?" and
now also accepts "…or has an undecided group aged past the window?". Two
additions, both small:

1. **`stalled_skipped`** added to the `groups.status` CHECK constraint, and
   set on a group the gate ages out. `groups.updated_at` already carries the
   timestamp the window is measured from — **no new column**.
2. **`GROUP_REVIEW_STALL_DAYS = 14`**, a named constant in `pipeline/config`
   (not a literal inside the gate), so the window is tunable without a code
   change.

**No `stall_sweep` stage, no `reminder_sent_at`.** Both were consequences of
the nudge and both are struck. The `Runtime is discrete scheduled functions`
list in `CLAUDE.md` therefore needs **no** new stage name.

**The GL-7 dependency survives, in weaker form.** There is no scheduler
today — `run_m1_live_test.py` is the only entrypoint — so the gate is only
evaluated when something runs it. Until GL-7's twice-daily batch exists, the
*effective* behaviour is wait-indefinitely. That is harmless while every run
is hand-triggered and the owner is present by definition, but it means
**"the stall rule fires" is a GL-7 DoD item, not a GL-22 one**. Recorded
here so nobody later reads "14-day timeout" in the spec and assumes it is
live.

**Why 14 days, and what it costs.** A `stalled_skipped` group is
**revisitable in principle only** — Q2 proved there is no API path to add a
variant to a published product, so recovering a skipped size means
re-publishing the candidate's listing from scratch. The window is therefore
a real forfeit, and that argues for erring long: the cost of waiting too
long is a design sitting unpublished, which is recoverable by tapping a
button; the cost of aging out too early is a size permanently missing from a
live listing, which is not. 14 days is two full weeks of the owner seeing
the same pending digest entry — not 14 days of pipeline latency, since all
three entries go out in the same evening run. It is one constant; argue with
the number, not the mechanism.

### [D1] also closes GL-29's open ordering question

The go-live plan flagged that GL-29 (draft→active activation behind a flag)
had a real ordering decision "under publish-primary-patch-later". Under [D1]
that decision disappears: the listing is created once with every validated
size and its full gallery already assembled, so **activation is
unambiguously the last step of the publish path** and nothing is added to a
buyer-visible listing afterwards. GL-29 needs no ordering logic beyond
"call it last".

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
- Shipping profile: resolved once per candidate instead of once per group —
  **`288734253315` "Gelato: Free shipping"** per `[D3]`. `static_config`'s
  `etsy_shipping_profile_id` collapses from a per-group-type dict back to a
  single value; `pipeline/config.get_shipping_profile_id()` loses its
  group argument (`get_group_type_for_size()` stays — it has other callers).
- **`[D2]` The stall rule**: `stalled_skipped` in the `groups.status` CHECK,
  a `GROUP_REVIEW_STALL_DAYS = 14` constant, and one extra clause in the
  publish gate's all-groups-decided predicate. No new stage, no new column.
  Built in session 2; only *fires* once GL-7 runs the gate on a cadence.
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
- No implementation ships before the CLAUDE.md rewrites below are reviewed.
  ✅ GL-22b and GL-22c are decided (`[D1]`/`[D2]`/`[D3]` above).

## Plan

Split into **two coding sessions**, at the boundary between the create path
and gallery assembly — the gallery is where the sharpest correctness risk
lives (one group's rebuild wiping another's images) and it deserves its own
session and its own PR rather than riding along behind a schema migration.

**Session 1 — steps 2–4** (`docs/2026-08-01-gl22-session1-kickoff.md`):
`etsy_client` fixes, the additive schema migration, the candidate-keyed
create path. Self-contained, dry-run-only, no gallery behaviour touched.

**Session 2 — steps 5–10**: gallery assembly, abandon/reject/cleanup, the
shipping-profile collapse, the stall sweep `[D2]`, the digest/mockup/critic
pass, tests, SPEC v4.12, CLAUDE.md rewrites.

1. ✅ **Owner sign-off** — done 2026-08-01, including GL-22b and GL-22c.
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
   hardcoded to `288734253315` per `[D3]`; `static_config`'s per-group-type
   dict collapses to a single value.
7b. **`[D2]` Stall rule**: `stalled_skipped` in the `groups.status` CHECK,
   `GROUP_REVIEW_STALL_DAYS = 14` in `pipeline/config`, and the extra clause
   in the publish gate. Measured off `groups.updated_at`. Dormant until GL-7
   evaluates the gate on a cadence.
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
config values) **with** (value now fixed by `[D3]`, no longer a placeholder):

> - Etsy shipping_profile_id: **resolved once per candidate, not per group
>   (v4.12) — `288734253315` ("Gelato: Free shipping", €0 to
>   every destination, confirmed live 2026-08-01 via `GET
>   /v3/application/shops/{shop_id}/shipping-profiles`; owner decision
>   2026-08-01).** One listing gets
>   exactly one Etsy shipping profile; under v4.12 that's resolved once for
>   the whole candidate rather than once per aspect-ratio group. The
>   previous per-group Small/Large split (5x7 → Small `287910553824`,
>   primary + 10x24 → Large `287910565714`) no longer applies once sizes
>   share a listing. **Retail prices are unchanged** — Gelato's per-item
>   shipping (€5.10–€5.86) is billed to the seller whichever profile is
>   set, and is already inside the cost basis those prices were built on;
>   all six sizes clear cost at 21–44 % with €0 shown at checkout. See
>   `docs/2026-08-01-gl22a-findings.md` GL-22b and this PRD's margin table.

**4. No fourth change needed.** An earlier draft of `[D2]` would have added a
`stall-sweep` stage to the `Runtime is discrete scheduled functions` bullet's
stage list. With the reminder deferred, the stall rule is a predicate inside
the existing publish gate, not a stage — that bullet is untouched.

## Open questions

Resolved since the first draft: GL-22b (→ `[D3]`), GL-22c shape (→ `[D1]`),
GL-22c stall rule (→ `[D2]`), the image-upload loop and the
`group_mockup`/`group_critic_pass`/`digest` extent (both below). Still open:

- ✅ **`patch_etsy_listing`'s image upload loop — answered 2026-08-01.**
  `group_product.py:482–494` uploads **every** image row unconditionally on
  every call: a full re-upload, no delta, no dedup. Under `[D1]` it is
  called once per candidate with the full assembled gallery, so the
  append-across-two-reviews concern this question was asked about
  **dissolves**. What replaces it: **retry safety** — a second call after a
  partial failure duplicates the whole gallery on the listing. Session 2
  must make it idempotent and test that.
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
- **The 14-day stall window `[D2]`** — picked as a deliberately long first
  cut, not measured against owner behaviour (there is no behaviour to
  measure yet: the pipeline has never run unattended). One named constant;
  revisit after GL-7's soak gives a real sense of decision latency.
- **The deferred reminder (GL-31)** — deferring it is right for go-live, but
  it means the *only* signal that a group is aging out is the owner
  remembering an untapped digest entry. Worth revisiting early post-launch
  rather than letting it sit at the bottom of the queue, precisely because a
  timed-out size cannot be added back.

---

**Decisions signed off 2026-08-01. Session 1 ✅ landed; session 2 is cleared
to start — `docs/2026-08-02-gl22-session2-kickoff.md`.**
