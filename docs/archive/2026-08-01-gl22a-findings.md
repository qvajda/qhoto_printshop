# GL-22a findings — v4.12 research gate (2026-08-01)

Research session for GL-22 ("one Etsy listing per artwork"). Live-call
authorisation: at most two throwaway Gelato products, both deleted, no Etsy
listing ever activated. This doc is written as artefacts are created, per the
session prompt's rule — the cleanup ledger below is live, not reconstructed
after the fact.

## Cleanup ledger (live, updated as artefacts are created)

| # | Type | ID | Created | Deleted | Delete call |
|---|---|---|---|---|---|
| 1 | Gelato product | `c389a81e-ad72-47ee-aa5d-8b743af3de86` (store `a2dab3b5-b2ed-4d3e-95c7-615ad0d2f48a`) | 2026-07-31T22:34:32Z | **deleted** (`DELETE /v1/stores/{storeId}/products/c389a81e-…` → `200`; re-`GET` → `404`, confirmed) | — |
| 1a | Etsy draft (pushed by #1) | `4547726856` | 2026-07-31T22:34:53Z (Gelato push) | **not deleted — see bold note below** | Attempted `DELETE /v3/application/listings/4547726856` → `403 {"error":"Access token lacks scope for this request (requires scope: listings_d)."}` |
| 2 | Gelato product (Q2 duplicate-title probe, second and last authorised throwaway) | `49bd3ea7-fe01-4a05-879e-1ac8d926000d` (store `a2dab3b5-b2ed-4d3e-95c7-615ad0d2f48a`) | 2026-07-31T~22:41Z | **deleted** (`DELETE` → `200`; re-`GET` → `404`, confirmed) | — |
| 2a | Etsy draft (pushed by #2, used for the clean Q3 test) | `4547717123` | 2026-07-31T~22:52Z | **not deleted — see bold note below** | Same `403`, same missing scope |

**Cannot delete programmatically — manual step required.** Both Gelato products
are confirmed deleted (`404` on re-`GET`), but deleting a Gelato product does
**not** delete the Etsy draft it pushed — `4547726856` and `4547717123` both
still `GET` as `{"state": "draft"}` after their Gelato product was deleted.
The current `ETSY_ACCESS_TOKEN` lacks the `listings_d` scope (`etsy_client.py`
has no `delete_listing` function at all — this session is the first time
anything in this repo needed one). Neither listing was ever activated
(`isVisibleInTheOnlineStore: false` the whole time, confirmed by every read
in this doc showing `"state": "draft"`), so this costs nothing — Etsy's
$0.20 activation fee is never charged on a draft. **The owner must delete
these two drafts by hand in Shop Manager → Listings → Drafts** (titles
`GL-22a Q1 research probe - DELETE ME` and `GL-22a Q1 research probe - DELETE ME`
respectively, both still carrying that title), or re-run the PKCE
authorize/exchange scripts at the repo root (see the 2026-07-17 OAuth scope
change) with `listings_d` added to request a token that can delete them via
the API instead.

---

## Q1 — Does a shared `image_placeholder_name` force a shared image?

*Method:* live `products:create-from-template`, one product, two portrait
variants — 8x12 (`a55fef92-…`) and 5x7 (`91514a4b-…`) — both using the same
`image_placeholder_name` (`003_flower_in_stream_madeira_color.JPG`) but two
different R2-hosted `fileUrl`s:
- 8x12 → `https://pub-5b3dbc93d44a48b1972e2854136ae9e7.r2.dev/base/39.png`
  (candidate 39's approved master, already durable from the live GL-9 run)
- 5x7 → `https://pub-5b3dbc93d44a48b1972e2854136ae9e7.r2.dev/base/39_5x7_crop.png`
  (generated for this session via `image_crop.print_crop_bytes(raw, "5x7")` +
  `artwork_store.persist_group_crop(39, "5x7", crop)` — a real cover-crop of
  the same master, not a placeholder image)

`POST /v1/stores/{storeId}/products:create-from-template` → `200`, product id
`c389a81e-ad72-47ee-aa5d-8b743af3de86`, `status: "created"`,
`isReadyToPublish: false`, `variants: []`, `productImages: []` (Gelato
processes the template asynchronously — see `GELATO_IMAGE_HOST` polling
comment in `gelato_client.py`).

Polling `GET /v1/stores/{storeId}/products/c389a81e-…` (first poll, ~20s
later) → `isReadyToPublish: true`, `status: "publishing"`, 2 `variants[]`
(5x7 `36723d28-…`, 8x12 `989b4ed3-…`), 2 `productImages[]`, each carrying a
different `productVariantIds` and a different signed `fileUrl`:
- 5x7 variant image `33c97024-…` → sha256 `f10bd9fc99a70f1e…`, 208206 bytes
- 8x12 variant image `1a18c072-…` → sha256 `044e3b2b535a4687…`, 201907 bytes

Downloaded both (`outputs/_gl22a_probe/q1_5x7.jpg`, `q1_8x12.jpg`) and viewed
them: the 5x7 preview is visibly the tighter vertical cover-crop
(`image_crop.print_crop_bytes(raw, "5x7")` output), the 8x12 preview is the
untouched master framing — same meadow illustration, different crop line,
exactly the two source files submitted.

`externalId` on the product was `4547726856` — Gelato's push to Etsy. Read it
back with `GET /v3/application/listings/4547726856?includes=Images` →
`200`, `state: "draft"` (never activated, confirmed), `has_variations: true`,
2 entries under `images[]`: `listing_image_id` `8371664173` (rank 1) and
`8323771964` (rank 2), two distinct `il_570xN` URLs.

**Answer: the two variants carry different artwork**, confirmed at both the
Gelato product level (different `fileUrl`/sha256 per `productImages[]` entry)
and the pushed Etsy draft level (two distinct `listing_image_id`s). **GL-22d
(the owner's Gelato template edit adding a second/third placeholder) is
unnecessary — struck from the plan.** The single shared
`image_placeholder_name` in `static_config.json` only names a *slot* in the
template's print-file layout; the per-variant `fileUrl` in the create call is
what actually populates it, and Gelato keys the resulting image to the
variant it was submitted against, not to the placeholder name.

---

## Q2 — Is there any API path to add a variant to an existing store product?

*Reference check:* `dashboard.gelato.com/docs/ecommerce/...` and the support
articles under `support.gelato.com` all returned `403` to `WebFetch` in this
session (bot-blocked, same class of thing as the Cloudflare 1010 issue this
repo already tracks for other vendors) — the documentation angle is
**inconclusive**, not answered. The empirical angle below is authoritative.

*Method 1 — `PUT` the product resource* (`/v1/stores/{storeId}/products/{id}`,
Q1's product `c389a81e-…`) with a 3-variant body (adding 10x24
`be74451a-…` to the existing 5x7 + 8x12 pair) → **`200`**, echoes back a
product object. This looks like success. It is not: polling
`GET` on the same product for the next **~80 s** (5 polls, 8–20 s apart)
shows `variants` staying at **2**, never 3 — the third variant was silently
dropped, not added. Worse, the response's `externalId` field flipped from
`"4547726856"` to `null` and stayed `null` through every subsequent poll —
the PUT also severed Gelato's own record of the Etsy listing it had already
pushed (**confirmed twice**: a second, isolated `PUT {"title": …}` — no
variants touched — on a *different*, freshly-created single-variant product
(`49bd3ea7-…`, listing `4547717123`) produced the exact same
`externalId → null` transition on the very next read). `PUT` is a full
replace that (a) does not honor a variants array reliably and (b) is
destructive to the product↔listing link — **not a usable "add a variant"
path, and not safe to call on a live synced product at all.**

`PATCH` on the same resource → **`405 METHOD_NOT_ALLOWED`**,
`Allow: GET, PUT, DELETE` header — not implemented.

*Method 2 — the `/variants` sub-resource.* `POST .../products/{id}/variants`
exists (it responds with a real validation error, not a 404), but its shape
is for **manually-priced custom products**, not template-linked ones: a bare
`{templateVariantId, imagePlaceholders}` body → `400 BAD_REQUEST`, `details`
list `title`/`price`/`cost`/`currency` all "should not be blank". Filling
those in (`title`, `price: 45`, `cost: 20`, `currency: "EUR"` alongside
`templateVariantId`) → **`550 INTERNAL_SERVER_ERROR`** — the endpoint does
not accept a `templateVariantId` at all once the required custom-product
fields are present; it is a different creation flow (self-priced items),
incompatible with template-priced sizes. `PUT .../variants` →
`405 METHOD_NOT_ALLOWED`, `Allow: POST, GET`.

*Method 3 — duplicate-title `create-from-template`.* A second
`products:create-from-template` call, same store, same title
(`"GL-22a Q1 research probe - DELETE ME"`), single 8x12 variant → **`200`**,
a **new** product id (`49bd3ea7-fe01-4a05-879e-1ac8d926000d`), distinct from
`c389a81e-…`. Confirms the GL-9-era suspicion the plan already carried:
create-from-template always creates, title collisions duplicate rather than
update — this is why the create path must stay idempotent through one
helper, and it rules out "just call create again with more variants" as an
add-variant substitute.

**Answer: no API path — dashboard only, confirmed empirically (`PUT`
no-ops the variant list and breaks the sync; `PATCH` is `405`; the `/variants`
sub-resource is a different, incompatible product-creation flow; duplicate
create makes a second product, not an update).** This selects the
**pre-committed fallback in GL-22c**: publish-on-primary-approval-then-patch
is not buildable — **fall back to create-once-when-all-groups-are-decided.**

---

## Q3 — Does Gelato re-push and overwrite our Etsy patch?

*Method:* on the freshly-created, still-synced product `49bd3ea7-…`
(listing `4547717123`) — chosen over `c389a81e-…` because that one's sync
was already severed by the Q2 `PUT` test, which would confound this
question — patched the Etsy draft's `title`/`tags`/`description` via
`update_listing` (`200`, echoed back the patched values). Then made a
Gelato-side product change: `PUT` the product with `{"title": "GL-22a Q3
gelato-side title change #2"}` (the smallest possible Gelato-side edit).
Re-read the Etsy listing 3 times over the next **~85 s**: `title` stayed
`"GL22A-Q3-CLEAN-PATCH-MARKER Wildflower Print"` — our patch — the whole
time; it never reverted to the Gelato-side title.

**Caveat, stated honestly per the standing rule against overclaiming
safety:** this `PUT` is the same call that severed `externalId` in the Q2
test on the other product, and it did so again here (`externalId` read
`null` immediately after). So this result is consistent with two different
explanations — "Gelato never re-pushes over a patch" or "this specific edit
path breaks sync before it would have re-pushed" — and this session's
authorised live-call budget (two products, both now spent) does not stretch
to a third, cleaner test that changes a product **without** going through
the same `PUT`. **Answer: our fields survived every re-read in the ~85 s
window given; whether that is because Gelato doesn't re-push, or because the
one edit path this session could reach happens to break the sync first, is
unobserved — report as "no overwrite observed, confounded," not as a safety
guarantee.** The PRD should treat "Gelato might re-push after a
dashboard-driven product edit" as an open risk, not a closed one.

---

## Q4 — What happens to the Gelato↔Etsy mapping when we drop a variation?

*Method:* on `c389a81e-…`'s Etsy draft (`4547726856`, still holding real
5x7 + 8x12 inventory products `33292344659` / `33292344657` at this point,
independent of the product-level `externalId` already broken by Q2 — the
**per-variant** `connectionStatus` was still `"connected"` for both sizes,
confirmed by `GET` on the product), called `update_listing_inventory` with
only `{"5x7": 19}`.

The pipeline's own `update_listing_inventory` helper (`etsy_client.py`)
**cannot do this today** — it raised `HTTP 400: Expected float value for
'price' (got array)` on the first attempt, because it only overwrites
`offering["price"]` for *matched* sizes and leaves every unmatched product's
offering `price` as the raw nested `{"amount", "divisor", "currency_code"}`
object `get_listing_inventory` returned, which Etsy's `PUT` rejects outright
for *any* product in the payload, matched or not. **This is a real,
previously-unexercised bug**, not a v4.12-specific one — nothing in the
current v4.11 pipeline ever calls `update_listing_inventory` with a subset
of a listing's sizes (a group's listing only ever has the sizes it was
created with), so this path has never run in production. Built the PUT body
by hand instead (drop the 8x12 entry, keep only 5x7, with correct float
prices and `readiness_state_id`) → **`200`**, the listing now shows one
product (`33292344659`, 5x7 only).

Reading the Gelato side immediately after, and again **45 s later**: both
variants on `c389a81e-…` still report `connectionStatus: "connected"`,
including the 8x12 one still pointing at `externalId: "33292344657"` — **the
Etsy inventory product Gelato thinks it owns**. Then re-added an 8x12
product to the Etsy inventory (same size, price, property values) via a
second `update_listing_inventory` PUT → Etsy assigned it a **brand-new**
`product_id` (`33636758666`), not `33292344657`. Re-read Gelato **30 s**
later: the 8x12 variant still reports `connectionStatus: "connected"`,
`externalId: "33292344657"` — the **old, now-nonexistent** id. Gelato never
noticed the drop, never noticed the re-add, and is left pointing at an Etsy
inventory product that no longer exists.

**Answer: the mapping breaks silently and does not self-heal.** Gelato's
view of a variant's connection is a cache it does not refresh by polling
Etsy; dropping a size from the Etsy inventory patch does not tell Gelato
anything, and re-adding it creates an unrelated new Etsy `product_id` rather
than reconnecting to the original — confirmed by direct comparison of the
`externalId` before/after. Within this session's observation window (through
~75 s after the re-add) this needed no human intervention *to complete the
Etsy-side operations* (both PUTs succeeded), but the **Gelato-side variant
record is now permanently stale** unless something re-syncs it — and Q2 already
established there is no API call in this session that successfully updated a
Gelato variant to point at a different Etsy product id. **The second
GL-22c fallback (create all six, prune rejected sizes from the Etsy
inventory patch) is dead**: it leaves an orphaned/misrouted Gelato variant
with no confirmed API-only recovery path, on top of the pipeline bug above
that must be fixed regardless of which GL-22c branch ships (any inventory
PUT that omits a size will hit it).

---

## Cleanup — final state

Both authorised live Gelato products deleted and confirmed gone
(`DELETE` → `200`, re-`GET` → `404` on both `c389a81e-…` and `49bd3ea7-…`).
**Two Etsy drafts (`4547726856`, `4547717123`) could not be deleted
programmatically — the live `ETSY_ACCESS_TOKEN` lacks the `listings_d`
scope, and `etsy_client.py` has no `delete_listing` function to begin
with.** Both are confirmed still `state: "draft"` (never activated, so this
costs nothing) as of the last read in this session. **Manual step: delete
both from Shop Manager → Listings → Drafts** (both still titled
`GL-22a Q1 research probe - DELETE ME` at last read), or add `listings_d` to
a re-authorised OAuth token and give `etsy_client.py` a `delete_listing`
function before the next session that needs one.

---

## Task 2 — impact map

Verified against the live code, not re-guessed from the plan's audit.

**Schema (`db/schema.sql`).** `groups` is unchanged — it stays the review
unit exactly as-is (`group_type`, `decision`, `status`). `group_products`
today is 1:1 with `groups` (`group_id INTEGER NOT NULL REFERENCES groups(id)`,
no uniqueness constraint stopping multiple rows per group, but
`create_or_reuse_group_product` treats it as effectively 1:1-per-group via
its reuse query). Under v4.12 the product/listing FK needs to move from
`group_id` to `candidate_id` — concretely: add `candidate_id INTEGER NOT
NULL REFERENCES candidates(id)` to `group_products`, drop the `group_id` FK
(a product is no longer owned by one group), and add a join table (or a
`group_product_id` FK moved the other direction, `groups.group_product_id`)
recording which groups' images/variants have been folded into the shared
product — `group_product_variants` needs a `group_id` of its own now (today
it only carries `size`/`orientation`, implicitly the parent product's single
group; under v4.12 a variant's group is only inferable from `size` via
`config.get_group_type_for_size`, which is fragile enough to want an
explicit column). `product_images` stays keyed to `group_product_id` (fine —
one shared product, images from up to three groups all attach to it) but
needs a `group_id` too, so gallery re-assembly can tell which images came
from which group when a group is later rejected and its images must be
pulled back out. `listing_metrics_snapshots` stays keyed to
`group_product_id`, unaffected in shape (there's just one product now
instead of up to three, so a candidate gets one row-series instead of
three). **The four real rows from the GL-9 live run**
(`group_products` ids 9/10/11/12/13, candidate 39: id 10 `published` with
real `etsy_listing_id` `4542159277`, id 12 `created` with no listing id
yet — see the DB dump earlier in this repo's history) are pre-v4.12-shape
data. Migration: these are left alone, not backfilled into the new
candidate-level shape — the schema migration should be additive (new
nullable `candidate_id` column, new table) so old rows keep resolving under
the code that already shipped for them, and any v4.12 write path simply
never touches a `group_products` row created before the migration.
**Rollback:** the migration is additive-only by construction (no column
dropped, no row rewritten), so rollback is "stop writing the new shape,"
not a down-migration — the risk is entirely in the *runtime* switch (the
create/patch/abandon call sites below), not the schema.

**Create path.** `create_or_reuse_group_product` (`group_product.py:165`)
today: reuse-keys on `group_id` (`SELECT ... FROM group_products WHERE
group_id = ?`, line 172), builds one `image_url` for the *whole group*
(`_group_print_crop` for 5x7/10x24, `candidate["base_image_url"]` for
primary, lines 275–286) and stamps that same URL onto every
`variant["image_url"]` in the create call. v4.12 needs this to key on
`candidate_id` instead, and to accept a **per-group** image (primary sizes
→ master, 5x7 sizes → 5x7 crop, 10x24 sizes → 10x24 crop) inside the same
`create-from-template` call — Q1 already proved the API supports this in one
call (`variants[].imagePlaceholders[].fileUrl` differs per variant
regardless of shared `image_placeholder_name`). Concretely: the function's
sizes/variants loop needs the image resolved **per size's owning group**,
not once for the whole call. The stale-row reuse/delete logic (lines 165–236,
`gelato_client.delete_product` on a stale row) stays, just keyed differently.

**Gallery assembly.** `product_images` inserts happen at lines 355–369,
cleared and reinserted (`DELETE FROM product_images WHERE
group_product_id = ?` then re-`INSERT`) every call — today that's a
**per-group** wipe-and-rebuild (safe, because each group owns its own
product). Under v4.12 that same clear-and-reinsert pattern, run
unconditionally for the *whole* product on every group's mockup/patch call,
would **delete the other two groups' already-uploaded images** every time
one group's mockups are (re)built — this is the sharpest correctness risk
in the create path, not just a nice-to-have: the delete must be scoped to
the calling group's own images (`WHERE group_product_id = ? AND group_id =
?` once that column exists), or gallery order will drop to whatever's left
after a partial wipe. `patch_etsy_listing` (`group_product.py:372`) reads
all `product_images` in `gallery_order` (line 405) and re-uploads via
`upload_listing_image` for the Etsy PATCH — need to trace whether this
re-uploads every image every call or only new ones (worth confirming: the
loop at 405+ was not fully read in this pass — flag as a PRD open question,
not answered here) — that answer decides whether appending 5x7/10x24 images
later is a cheap delta-patch or a full 13-image re-upload each time a group
is decided. **Etsy's cap is 20** (raised Aug 2025) — 10 (primary) + up to 4
(5x7, revised target) + up to 4 (10x24, revised target) = up to 18 today,
inside the cap but with only 2 of headroom against the *revised* 2–4-per-
secondary-group target (Part 1's "primary 10, secondary 2–4 each") — the
build must assert `len(images) <= 20` and fail loud rather than silently
truncate or let Etsy's own near-cap `rank` fussiness produce an
unpredictable gallery order.

**Abandon / reject / cleanup — every Gelato-product-deleting call site,
verified by grep, not assumed:**
- `critic_pass.py:437` `discard_superseded_attempt(conn, group_product_id, …)`
  — reads `gelato_product_id` for that `group_product_id` (line 439) and
  calls `gelato_client.delete_product` (line 444) unconditionally if one
  exists. Under v4.12 this must become a **no-op for delete** when the
  product is shared across groups (i.e., always, once v4.12 ships) — it
  should still discard the *group's own* superseded attempt bookkeeping,
  just never call `delete_product`.
- `cleanup.py:10–22` — a query joining `group_products` on
  `gp.gelato_product_id IS NOT NULL` (line 13) that calls `delete_product`
  per orphaned row (line 22), and a second query at line 84
  (`gp.gelato_product_id IS NOT NULL AND gp.status != 'deleted'`) doing
  similar reclaim work. Both need a guard: don't delete a `group_products`
  row's Gelato product if any *other* group under the same candidate is
  still `approved_published` or `pending_review` — the shared product must
  outlive any single group's abandonment.
- `publish_group.py:70–88` (`handle_decision`, `action == "reject"`) —
  today just flips `groups.status` to `'rejected'` (line 84) and does
  **not** itself call `delete_product`; the deletion for a rejected group
  happens later via `critic_pass.discard_superseded_attempt` or
  `cleanup.py`'s reclaim pass. Both of those are covered above, so this
  call site itself needs no change beyond staying a status flip.

**Shipping profile.** `config.get_shipping_profile_id` (`config.py:66`) is
already a pure function of `group_type` — under v4.12 it's called once per
*candidate* (using whichever group_type the resolved GL-22b policy points
at — see the decision below), not once per group's listing. No signature
change needed, just a different call site (candidate-level publish, not
per-group publish).

**Everything else, read but not fully traced in this pass (flagged, not
answered) —** `group_mockup.py`, `group_critic_pass.py`, `digest.py` /
`group_digest.py` (the digest text presumably needs to say "this design now
offers N sizes" rather than "this listing offers N sizes" — a wording change
at minimum, possibly a data-shape change if the digest currently reads
`group_products.title` directly), `run_m1_live_test.py` (needs a new
assertion shape: one listing, not up to three, per candidate), and the test
suite (every test asserting `create_or_reuse_group_product` keys on
`group_id`, and every test asserting a rejected group's product gets
deleted, needs updating — count not taken in this pass, budget was spent on
the live-call questions per the session's stated priority order).

**Docs.** SPEC v4.12 (net-new, supersedes SPEC v4.11 section 3 stage flow
and section 4 static config), the two CLAUDE.md constraint rewrites (drafted
in the PRD below), and this plan-of-record's GL-22 row updated to point at
this findings doc and the PRD instead of "planned, not started."

---

## Task 3 — the two owner decisions, prepared with arithmetic

### GL-22b — shipping profile

Real Gelato per-unit cost, from `docs/Premium Matte Paper Poster_BE_2026-07-05.csv`
(this is the actual on-disk filename — `CLAUDE.md`'s citation
`gelato_premium_matte_poster_prices_BE_2026-07-05.csv` doesn't exist verbatim
in this checkout; flagging the mismatch rather than silently fixing
`CLAUDE.md`'s citation):

| Size | Gelato product cost | Gelato's own shipping cost | Gelato total cost | Retail (`CLAUDE.md`) |
|---|---|---|---|---|
| 5x7 | €7.78 | €5.10 | €12.88 | €19 |
| 8x12 | €7.78 | €5.86 | €13.64 | €24 |
| A3 | €12.82 | €5.10 | €17.92 | €35 |
| A2 (portrait) | €15.11 | €5.10 | €20.21 | €39 |
| A2 (landscape) | €14.50 | €5.10 | €19.60 | €39 |
| 10x24 | €14.71 | €5.86 | €20.57 | €45 |
| A1 | €17.90 | €5.55 | €23.45 | €49 |

This matches SPEC v4.11 section 4's own table (~21–44% margin), and
critically: **Gelato's real per-item shipping cost (€5.10–€5.86 across every
size in this product line) is already inside that "total cost," charged to
the seller regardless of which Etsy shipping profile is assigned.** The
Etsy `shipping_profile_id` does not change what Gelato bills the seller — it
only sets what a **buyer** is separately charged at Etsy checkout, on top of
the item price. Read live from the shop's actual shipping profiles
(`GET /v3/application/shops/{shop_id}/shipping-profiles/{id}`, 2026-08-01),
by destination:

| Profile | "Rest of world" default | EU | US |
|---|---|---|---|
| Small Posters (`287910553824`) | €12.44 | €5.86 | €6.14 |
| Large Posters (`287910565714`) | €14.55 | €7.04 | €8.97 |
| **Free shipping (`288734253315`)** | **€0** | **€0** | **€0** |

Two things this live read changes versus the brief's framing:
1. The €12.44/€14.55 numbers in `CLAUDE.md` and the plan are the **default/
   non-EU** rate, not a flat global charge — a BE-based shop's EU buyers
   (plausibly the majority) see €5.86/€7.04, a €1.18 gap, not €2.11.
2. **There is a better-fitting profile the original options list didn't
   include: `Gelato: Free shipping`, id `288734253315`, €0 to every
   destination in the shop's live profile list.** The brief's instruction
   was "check before assuming there isn't one" — checked, and there is one.

**Options, with arithmetic:**
- **Large everywhere.** 5x7 buyer's total default-region checkout cost rises
  by €2.11 (€12.44→€14.55) on a €19 item — a ~11% increase on the cheapest,
  highest-conversion-sensitivity size. *But* this is not new exposure: the
  **primary group (including 8x12, the size every design is first reviewed
  and sold at) is already on Large today**, so this doesn't introduce an
  untested buyer experience, it extends an already-live one down to 5x7.
- **Small everywhere.** A1 buyer's default-region shipping drops €2.11
  (€14.55→€12.44) — foregone revenue, not a cost problem: Gelato's real A1
  shipping cost is €5.55, so €12.44 still clears it by €6.89. The
  "under-charges A1" risk named in the brief is real only in the sense of
  **leaving money on the table** relative to Large, not in the sense of
  selling below cost.
- **Re-price 5x7 to absorb Large.** E.g. 5x7 €19→€21 keeps the *landed* cost
  to a default-region buyer roughly where Small-tier 5x7 sits today
  (€19+€12.44=€31.44 vs €21+€14.55=€35.55 — doesn't fully absorb it without
  a bigger jump; a clean absorb would need ~€21 just on the shipping delta
  alone, i.e. 5x7 → ~€21, and it still isn't a full match). Weakens the
  "entry price" positioning stated in `CLAUDE.md` for a partial fix — not
  recommended over the option below.
- **A different profile among the ~49.** No `Medium Posters` tier exists
  (confirmed live — the 49 are one-per-product-category, not tiered within
  "Posters" beyond Small/Large), but **`Gelato: Free shipping` does exist**
  and fits every size in the group without a tier trade-off at all.

**Recommendation: `Gelato: Free shipping` (`288734253315`).** It removes the
GL-22b dilemma entirely — one listing, one profile, €0 shown at checkout for
every size, no per-size winner/loser. The real cost this forgoes is the
default-region shipping *surcharge* revenue Large/Small currently collect on
top of item price (up to €14.55/order for a non-EU/US buyer) — money the
margin table in SPEC v4.11 was **never counting on** in the first place: its
~21–44% figures already net out to "item price alone must cover landed
cost" once Etsy's ~9.5%+€0.25 fee is subtracted (reconstructed from the
5x7 row: `(19×0.905 − 0.25 − 12.88) / 19 ≈ 21%`, matching the table's stated
~21% almost exactly) — i.e. the business's own numbers already assume
something close to a free-shipping economics model, so this doesn't cut into
margin the pipeline was actually planning on. It also sidesteps Q4's
"dropping a variation orphans the Gelato mapping" defect entirely for this
specific decision, since it's a single global profile with no per-size
choice to prune later. **Trade-off to flag for the owner, not decide:**
default-region and US buyers currently pay a real shipping line that (after
Q1–Q4's evidence) is pure incremental revenue over Gelato's real cost —
switching to Free Shipping forfeits that revenue on those orders
specifically (EU buyers see almost no change, €5.86–7.04 either way). Given
this is a real revenue trade-off the owner may weigh differently than "which
tier", it's presented as the recommendation with the arithmetic shown, not
a foregone conclusion.

### GL-22c — publish timing

Q2 selected the branch: **no API path exists to add a variant to an
existing product** (PUT no-ops the variant list and breaks sync; PATCH is
405; the `/variants` sub-resource is an incompatible custom-product flow;
duplicate `create-from-template` makes a second product). And Q4 killed the
third option: dropping/re-adding a size via the Etsy inventory patch orphans
the Gelato-side variant mapping with no observed self-heal.

- **(a) Publish on primary approval, patch 5x7/10x24 in later — dead.**
  Needs Q2 to have found an add-variant path. It didn't. Not buildable
  without a dashboard step per design, which defeats the automation this
  pipeline exists for.
- **(b) Create once when all three groups are decided — selected.** Costs:
  the listing doesn't exist (not even as a draft) until the last of the
  three digest decisions lands, which can be hours to days after the
  primary approval given the primary group publishes "no further review"
  today but 5x7/10x24 each go through their own independent critic-pass +
  owner Approve/Edit/Reject. **Needs a stall rule** (explicit PRD
  requirement, not decided here): what happens if the owner approves
  primary and then never acts on the 5x7/10x24 digest entries? Candidate
  options for the PRD to choose between: (i) a timeout after which the
  candidate auto-publishes primary-only sizes and treats un-decided
  secondary groups as permanently skippable-but-revisitable, (ii) no
  timeout — the candidate simply sits `pending_review` on those groups
  indefinitely, same as today's per-group model, just now blocking the
  *entire* listing's first publish rather than only that group's. (ii) is
  simpler and matches the "the review flow does not change" constraint in
  the brief, but means one slow secondary decision can hold the whole
  design off the store — worth the owner's explicit sign-off, not a default
  to assume.
- **(c) Create all six, prune rejected sizes — dead per Q4.** Confirmed
  live: pruning a size from the Etsy inventory patch does not tell Gelato
  anything, and re-adding a size creates an unrelated new Etsy `product_id`
  rather than reconnecting — an unmapped/stale Gelato variant with no
  observed API-only recovery. Struck from the plan, per the pre-committed
  fork.
