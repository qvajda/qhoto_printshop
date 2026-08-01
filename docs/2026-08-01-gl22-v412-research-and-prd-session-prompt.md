# Session kickoff — GL-22a research → findings → v4.12 PRD (2026-08-01)

Ready-to-paste prompt for a **Claude Code session** from the `qhoto_printshop`
repo root. Branch off `master` (GL-23 is merged; master carries the wired
10 + 1 + 2 gallery).

**Owner authorisations granted for this session, 2026-08-01:**
one or two **throwaway live Gelato products** may be created and must be
deleted; the session goes **research → findings → PRD and stops before any
implementation**.

Plan of record: `docs/2026-07-22-go-live-plan-of-attack.md` — GL-22, GL-22a/b/c/d.
Predecessors: `docs/SPEC_v4.11.md` (the shape being replaced), `CLAUDE.md`
(the two hard constraints this change rewrites).

---

## PROMPT — paste from here down

You are running **GL-22a**, the research gate in front of GL-22 ("v4.12 — one
Etsy listing per artwork"), and then writing the **v4.12 PRD** off what you
measure. Read `docs/2026-07-22-go-live-plan-of-attack.md` Part 1 §"New scope"
and the GL-22* rows in Part 2 first — they are your brief, and they already
contain the audit, so do not re-derive it.

**The change, in one paragraph.** Today a design publishes as three Etsy
listings, one per aspect-ratio group (v4.11: "one listing per group, sizes are
variants"). The target is **one listing per artwork** — all six sizes as
variants of a single Gelato product and a single Etsy listing, with the gallery
composed of the primary mockups always, plus the 5x7 mockups if that crop
passed its review, plus the 10x24 mockups if that one did. A design still
offers 4, 5 or 6 sizes depending on which crops passed; it just offers them in
one place. **The review flow does not change** — three digest entries, three
Approve/Edit/Reject decisions, exactly as spec section 3 steps 6–7 describes.
Only the product/listing shape underneath changes.

### Read first, in this order

1. `docs/2026-07-22-go-live-plan-of-attack.md` — Part 1 §"New scope", Part 2
   GL-22/22a/22b/22c/22d, Part 3 §"Why GL-22 goes before the live re-test".
2. `CLAUDE.md` — the constraint blocks. **Two of them are made wrong by this
   change** ("One Etsy listing per aspect-ratio group" and "abandon that group
   only … DELETE that group's Gelato product(s)"), plus the per-group shipping
   profile paragraph. Rewriting them is part of the PRD's deliverable; flag any
   third one you find rather than editing silently.
3. `docs/SPEC_v4.11.md` sections 3 (the stage flow) and 4 (static config, the
   price table).
4. `pipeline/group_product.py` — `create_or_reuse_group_product` and
   `patch_etsy_listing` are where most of this lands.
5. `pipeline/gelato_client.py` `create_product_from_template`,
   `pipeline/etsy_client.py` `update_listing` / `update_listing_inventory` /
   `upload_listing_image`, `pipeline/config.py`, `db/schema.sql`.

### Standing rules

- **No implementation.** No pipeline code, no schema change, no migration
  script, no test edits. The deliverables are two documents.
- **Live calls are scoped and reversible.** You may create at most **two**
  Gelato products from the real portrait template, and you must delete them.
  Write the intended cleanup — product IDs, listing IDs, the delete calls —
  into the findings doc *as you create each artefact*, not afterwards. Never
  activate an Etsy listing: Gelato pushes with
  `isVisibleInTheOnlineStore: false`, drafts are free, activation costs $0.20
  and makes it buyer-visible. If a run leaves anything you cannot delete
  programmatically, say so in bold in the findings and name the manual step.
- **Measure, don't infer.** Every answer below carries the HTTP status, the
  request body and the response field you read it from. "Presumably" is not an
  answer; "unobserved within the window I gave it" is.
- **Flag constraints, don't route around them.** If a question cannot be
  answered inside the authorisation above, stop and say what call would answer
  it, rather than substituting a weaker experiment and reporting it as the
  answer.
- Comments and docs in this repo explain *why*, with the measurement that
  justified the number. Match that voice.

---

## Task 1 — the four questions

Answer in this order; Q1 can make Q2 cheaper and may delete a manual step from
the plan entirely.

**Q1 — Does a shared `image_placeholder_name` force a shared image?**
The config gives all six portrait sizes one `template_id`
(`23444c3a-c0ab-4a82-b6f7-44fb03a6607d`), distinct `template_variant_id`s, and
the *same* `image_placeholder_name`. The API takes `fileUrl` per variant, so it
is not obvious that two variants sharing a placeholder name must share an
image.
*Method:* one live `products:create-from-template` with exactly two variants —
8x12 portrait (`a55fef92-c197-4ac1-b4e5-e0a41a805011`) and 5x7 portrait
(`91514a4b-202a-4a1d-b487-aee90c57e960`) — carrying two **visibly different**
durable URLs. Use the approved master (candidate 39) for one and its **5x7
cover-crop** for the other: that is the real use case, and the difference in
framing is obvious at a glance. Both must be R2-hosted http(s);
`gelato_client` refuses `replicate.delivery` and non-http paths by design.
Then `GET` the product and read the per-variant previews, and read the pushed
Etsy draft's variation images.
*Answered when:* you can state "the two variants carry different artwork" or
"they collapse to one image", with the preview URLs and a downloaded pair.
**If they differ, say so prominently — GL-22d (the owner's Gelato template
edit) is then unnecessary work and should be struck from the plan.**

**Q2 — Is there any API path to add a variant to an existing store product?**
This is the load-bearing unknown: the owner's preferred publish flow
(publish on primary approval, patch 5x7/10x24 in later) needs it. Gelato's own
support article describes adding a variation as a **dashboard** action
("Edit Design" → pick sizes → Publish) or an Etsy-side edit followed by
"Sync products".
*Method:* first the reference — look for `PUT`/`PATCH` on
`/v1/stores/{storeId}/products/{productId}` or any variants sub-resource in
the ecommerce API docs. Then empirically, against Q1's product: attempt the
most plausible update call and record the status and body verbatim; and
attempt a second `create-from-template` naming the same title to confirm
whether it duplicates rather than updates (the GL-9 live run suggests it
duplicates — that is why the create path is idempotent through one helper).
*Answered when:* either a working endpoint with a body that added a variant,
or "no API path — dashboard only", each with the HTTP evidence.
**This answer selects the GL-22c branch. The fork is pre-committed in the plan
— apply it, do not re-open it.**

**Q3 — Does Gelato re-push and overwrite our Etsy patch?**
v4.11 is "Gelato pushes, we patch". If Gelato re-syncs after any later product
change, our title/description/tags/prices could be silently reverted — and
under v4.12, later product changes are exactly what the design depends on.
*Method:* once Q1's product has synced to Etsy, patch the draft listing's
title/tags/description; then cause a Gelato-side change (a title edit, or
whatever Q2 found) and re-read the Etsy listing after a stated interval.
*Answered when:* "our fields survive" / "field X is overwritten after event Y"
/ "no sync observed within N minutes" — the third is a legitimate answer, and
must be reported as unobserved rather than as safety.

**Q4 — What happens to the Gelato↔Etsy mapping when we drop a variation?**
The second fallback in GL-22c creates all six variants and prunes the rejected
sizes from the Etsy inventory patch. Its risk is an unmapped Gelato variant.
*Method:* on Q1's synced draft, call `update_listing_inventory` with only one
of the two sizes; read the variant's connection state on the Gelato side; then
re-add the size and check whether it reconnects on sync or needs a manual
connect.
*Answered when:* the state transitions are written down, including whether
re-adding is self-healing. If it needs a human, the second fallback is dead —
say so.

**Cleanup, before you report anything:** delete every Gelato product created,
confirm the corresponding Etsy drafts are gone (or name the manual deletion),
and list every ID touched. A findings doc that reports four answers and leaves
an orphan is a failed run.

---

## Task 2 — the impact map (offline, no calls)

Enumerate what v4.12 actually touches, file by file, so the PRD's plan is
sized rather than guessed. The audit in the plan of record gives you the
starting set; verify each one and add what it missed.

- **Schema.** `groups` stays the review unit. `group_products` →
  `group_product_variants` / `product_images` / `listing_metrics_snapshots`
  currently hang off one product **per group**; under v4.12 the product/listing
  is **per candidate**. Say concretely: which tables move, what the migration
  does to the rows already in `db/qhoto.sqlite3` from the GL-9 live run (four
  real Etsy drafts exist), and what the backfill/rollback is. Note that
  `listing_texts` is **already candidate-level** — title/tags/description do
  not vary per group today, which removes a whole class of work — and that its
  vestigial `shipping_profile_id` column becomes meaningful again under one
  listing.
- **Create path.** `create_or_reuse_group_product` passes one `image_url` to
  every variant; v4.12 needs the primary sizes on the master and the 5x7 /
  10x24 sizes on their own cover-crops in **one** call. The idempotent
  create-or-reuse helper stays the single route — say how reuse keys change
  when the key is a candidate, not a group.
- **Gallery assembly.** Images now come from up to three groups into one
  listing, in rank order, growing across reviews. **Etsy's cap is 20 photos**
  (raised from 10 in Aug 2025) — 10 + 1 + 2 = 13 today, but the build must
  **assert** it rather than assume, and the API is documented as fussy about
  `rank` near the cap. Say what happens on re-upload/append: does
  `patch_etsy_listing` re-upload the whole gallery or only the delta?
- **Abandon / reject / cleanup.** `critic_pass.discard_superseded_attempt`,
  `publish_group.handle_decision`'s reject and edit branches, and `cleanup.py`
  all delete or reclaim a group's Gelato product. With one shared product,
  abandoning 5x7 must delete **nothing**. Name every call site.
- **Shipping profile.** `config.get_shipping_profile_id` is per-group-type by
  construction; under one listing it resolves once per candidate. Depends on
  GL-22b.
- **Everything else it touches:** `group_mockup.py`, `group_critic_pass.py`,
  `digest.py` / `group_digest.py` (the digest text says which sizes a listing
  offers), `run_m1_live_test.py`, and the test suite.
- **Docs:** SPEC v4.12, the CLAUDE.md constraint rewrites, and the plan of
  record's GL-22 row.

---

## Task 3 — prepare the two owner decisions

Do not decide these. Prepare them so they can be decided on numbers.

**GL-22b — shipping profile.** One listing, one profile. Today: 5x7 → Small
(`287910553824`, €12.44), primary + 10x24 → Large (`287910565714`, €14.55).
Compute the **actual margin per size** under each option using
`gelato_premium_matte_poster_prices_BE_2026-07-05.csv` and the final EUR retail
prices in `CLAUDE.md` (5x7 €19 · 8x12 €24 · A3 €35 · A2 €39 · 10x24 €45 ·
A1 €49). Options: Large everywhere (5x7 loses €2.11); Small everywhere (**do
not** — it under-charges A1, quantify by how much); re-price 5x7 to absorb it
(say to what, and what that does to the entry price point); or a better fit
among the ~49 Gelato-created profiles (check before assuming there isn't one).
Recommend one, with the arithmetic visible.

**GL-22c — publish timing.** Q2 selects the branch. State which one it
selected and what it costs, in one short paragraph each: (a) publish on primary
approval and patch later; (b) create once when all three groups are decided —
including a **stall rule** for a decision that never arrives, which the PRD
must specify; (c) create all six and prune rejected sizes Etsy-side, only if
Q4 says the mapping self-heals.

---

## Task 4 — the PRD

`docs/2026-08-01-v412-single-listing-prd.md`, per CLAUDE.md §2: **problem,
success criteria, scope (in/out), constraints, plan, open questions.** Plus,
because this one touches a live store and existing data:

- **Migration and rollback** — what happens to the four existing published
  rows, and how to get back if the first live publish under v4.12 goes wrong.
- **The live-test delta** — what GL-13 must now cover that Round 1 did not
  (one listing carrying 4/5/6 variants, a gallery that grew across two
  reviews, a rejected secondary group that deletes nothing).
- **Phasing** — what can land behind the existing dry-run flags before any
  live write.
- **The CLAUDE.md constraint rewrites**, drafted as exact replacement text for
  owner review.

**Done means:** a findings doc with four measured answers and a clean-up
ledger; an impact map that names files and call sites; two decisions prepared
with arithmetic; and a PRD ending in an explicit **"awaiting owner sign-off —
no implementation until approved"**. Commit both docs; do not open a PR to
master and do not write code.

If Q2 comes back "dashboard only", **do not treat that as a blocker** — apply
the pre-committed fallback, note the manual-step alternative for completeness,
and write the PRD for the fallback shape. The plan's whole point is that this
costs a decision, not a schedule slip.
