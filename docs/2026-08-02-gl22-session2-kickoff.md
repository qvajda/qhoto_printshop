# GL-22 session 2 — coding kickoff (v4.12, the publish path)

**Tool: Claude Code, in-repo, test-driven.** Session 2 of 2.
Session 1 landed (`6df9ba5`, `ed660c1`, `b0560df`, `4c878b3`). This session
carries the change the split exists to isolate.

> **Read §1 before anything else.** Session 1 found that the thing this
> session was scoped to modify is welded to something else, and left the
> secondary path deliberately broken. That is the starting state, not a bug
> to be surprised by.

---

## 0. Read these first, in this order

1. `docs/2026-08-01-v412-single-listing-prd.md` — the PRD and its
   `[D1]`/`[D2]`/`[D3]` decisions.
2. `docs/2026-08-01-gl22-session1-kickoff.md` and session 1's log entry in
   `docs/2026-07-22-go-live-plan-of-attack.md` Part 4 — what was built, and
   the shared-product collision as it was actually resolved.
3. `docs/2026-08-01-gl22a-findings.md` — Q2 (no API path adds a variant
   post-create) is the constraint everything below is shaped by.
4. `CLAUDE.md` — three constraints get rewritten **in this session** (§5).
5. `pipeline/group_product.py` in full. It is the centre of this session.

---

## 1. The starting state — a weld, and a deliberate breakage

**`create_or_reuse_group_product` does two unrelated jobs.** It creates the
Gelato product *and* renders the local compositor mockups that the review
gallery is made of (`group_product.py:411–415` — `mockup_render.render_scene`
→ `artwork_store.persist_mockup_render` → `product_images`).

Under v4.12 those two jobs have **incompatible timing**:

- Review mockups must exist **before** any group is decided — they *are*
  what the owner reviews.
- The Gelato product can only be created **once, after every group is
  decided**, with all validated sizes in one call ([D1], forced by Q2).

So the weld has to be cut. This is not a preference; no ordering satisfies
both jobs while they live in one function.

**What session 1 left behind, deliberately.** With the reuse key moved to
`candidate_id`, `group_mockup` for 5x7/10x24 resolves the candidate's
*primary* product, mismatches the size set, and hits session 1's new
`SharedProductVariantError` guard. **The secondary path is intentionally
broken between the two sessions.** Dry-run-only ground, nothing live runs —
but it is real, not latent, and un-breaking it is job one here.

**The cheap fix is dead, checked.** "Pass the candidate's full size set at
mockup time" cannot work: when 5x7 renders its mockups, 10x24 has not been
decided yet, so the final size set is unknown at that moment.

**The silent-wipe risk the PRD flagged is now concrete.**
`group_product.py:433` and `critic_pass.py:446` both run
`DELETE FROM product_images WHERE group_product_id = ?`. With one product per
candidate, 5x7 rendering its mockups **deletes the primary's gallery**. Seven
call sites read `product_images` by `group_product_id`
(`compliance_draft.py:62`, `critic_pass.py:394,446`, `digest.py:34`,
`group_critic_pass.py:28`, `group_digest.py:36`, `group_product.py:433,483`,
`cleanup.py:106`).

**Owner decision, 2026-08-01 — `group_id` scopes, the FK stays.**
`product_images` keeps **both** `group_product_id` (the listing it will
publish into) and `group_id` (the group that rendered it, added in session
1). Deletes and rebuilds gain `AND group_id = ?`. **Do not** make
`group_product_id` nullable and **do not** rename `group_products` — both
were considered and rejected: the first forces a SQLite table rebuild, which
breaks the additive-migration guarantee the whole rollback story rests on;
the second is a repo-wide diff landing on top of this session's riskiest
change.

> **Naming, so it stops misleading.** After session 1, `group_products` is
> **not** "the Gelato product row" — it is the candidate's listing record,
> and `gelato_product_id` is one nullable column on it. Say this in SPEC
> v4.12 (§5) rather than leaving the next reader to work it out.

---

## 2. What this session builds

### A. Cut the weld *(do this first — everything else depends on it)*

Split `create_or_reuse_group_product` into two functions with two timings:

1. **`render_group_mockups(conn, group_id, …)`** — ensures the candidate's
   `group_products` row exists (`status='pending'`, `gelato_product_id
   NULL`), renders that group's scenes, writes its `product_images` scoped
   to `group_id`, and records that group's `group_product_variants` rows.
   **No Gelato call.** Called by `primary_mockup.py` and `group_mockup.py`.
2. **`create_candidate_gelato_product(conn, candidate_id, …)`** — the single
   `create-from-template` call, at publish time, carrying every validated
   size as a variant with its own group's `fileUrl`. Fills in
   `gelato_product_id`, flips the row to `created`. Called by the publish
   path only.

Things that must move with the Gelato half, not the render half:
`poll_until_ready`, `resolve_etsy_listing_id`, the `mockup_failed`-with-a-
product-id re-poll path, and the orphan-delete-before-retry idempotency.
Session 1's `SharedProductVariantError` guard **stays** — the mockup path
should simply stop reaching it.

**One judgement call, flagged not decided: the DPI guard.**
`_assert_print_dpi` currently fires before any DB write in the create path.
It guards that the master is large enough to print each size — a *print*
concern, not a Gelato one. **Recommendation: move it to the render path**, so
a too-small master fails before the owner spends a review on it rather than
after. If moving it turns out to break the "fails fast without orphaning a
row" property it was written for, **stop and flag it** rather than picking
one property over the other.

`group_products.status` needs **no new value**: `pending` already means "row
exists, no Gelato product yet", and `mockup_failed` now accurately means the
local render failed.

### B. Gallery assembly, scoped

- Every `product_images` delete/rebuild gains `AND group_id = ?`. **A scoped
  delete is the whole point of this session** — an unscoped one silently
  destroys another group's reviewed gallery, and nothing downstream would
  notice until a buyer saw the listing.
- Assemble the candidate's gallery in rank order across the groups whose
  decision is `approved`/`edited`, skipping `rejected`, `failed_abandoned`
  and `stalled_skipped`.
- **Assert `len(images) <= 20`**, do not assume it. Today's set is 10 + 1 + 2
  = 13; the assert is for when the library grows.
- **The PRD's open question is answered — record it and act on it.**
  `patch_etsy_listing`'s loop (`group_product.py:482–494`) uploads **every**
  image row unconditionally on every call: a **full re-upload, no delta, no
  dedup**. Under [D1] it is called once per candidate, so the append-across-
  reviews concern the PRD raised **dissolves**. What does *not* dissolve is
  **retry safety**: a second call after a partial failure duplicates the
  whole gallery on the listing. Make it idempotent, and test that.

### C. Abandon / reject / cleanup — stop deleting a shared product

Three call sites, per the PRD's impact map:

- `critic_pass.discard_superseded_attempt` (`critic_pass.py:437`) — currently
  deletes the Gelato product, the variants, the images and the
  `group_products` row outright. Under v4.12 it must scope to the group and
  **never** delete a shared row.
- `cleanup.py`'s two Gelato-product-deleting queries — whole-candidate
  teardown stays whole-candidate; a single group's failure must not reach
  them.
- `publish_group.py`'s reject branch — the findings doc confirmed **no change
  needed**. Verify that still holds after A, and say so; don't assume it.

Net rule: **abandoning a group marks it and excludes it. It deletes
nothing.**

### D. Shipping profile collapse `[D3]`

`config/static_config.json`'s `etsy_shipping_profile_id` goes from a
per-group-type dict to the single value `"288734253315"`.
`config.get_shipping_profile_id()` loses its `group_type` argument;
`patch_etsy_listing` stops passing one. `get_group_type_for_size()` **stays**
— it has other callers. **Retail prices are unchanged** — do not touch them.

### E. The stall predicate `[D2]`

- `stalled_skipped` added to the `groups.status` CHECK.
- `GROUP_REVIEW_STALL_DAYS = 14` in `pipeline/config` — a named constant, not
  a literal in the gate.
- The publish gate's "have all groups reached a terminal decision?" check
  gains "…or has an undecided group's `groups.updated_at` aged past the
  window?", marking that group `stalled_skipped`.
- **No stage, no `reminder_sent_at`, no `CLAUDE.md` stage-list edit** — the
  reminder is deferred to GL-31.
- It will not *fire* until GL-7 evaluates the gate on a cadence. Test it by
  lowering the constant, never by waiting.

### F. Digest / mockup / critic pass

`group_mockup.py`, `group_critic_pass.py`, `digest.py`, `group_digest.py` —
wording and data shapes for one listing instead of three. The PRD flagged the
extent as untraced; trace it now and report the actual diff size. **The
three-digest-entry review flow does not change** — that is a standing
constraint, not an implementation detail.

### G. Tests, spec, constraints

- `run_m1_live_test.py` + suite updated for one-listing-per-candidate.
- **SPEC v4.12**, superseding SPEC v4.11 §§3–4.
- The three `CLAUDE.md` rewrites, verbatim from the PRD's rewrite block.

---

## 3. Two approved destructive actions

Both owner-approved 2026-08-01. **Do these deliberately, not as cleanup
noise.**

1. **Delete the two GL-22a research drafts in Shop Manager.** First real use
   of session 1's `delete_listing`; the `listings_d` re-auth is done. Log
   both listing IDs before and after. **Irreversible, on a live external
   account** — confirm via `GET` what you are about to delete before you
   delete it, per the PRD's own rollback advice.
2. **Drop `stash@{0}` and `stash@{1}`** — the redundant recovery stashes from
   the incident; contents confirmed restored to the working tree.
   **`stash@{2}` is older (`feat/gl21-matte-compositor`) and is NOT approved
   for deletion — leave it alone.**

Nothing else destructive is approved. Anything that turns up wanting a
delete gets flagged, not done.

---

## 4. How to run this session — subagents, and a hard denylist

### The incident this rule comes from

In session 1 a subagent ran `git stash` to "compare against a clean
checkout" and **wiped the working tree** — its own work, the parallel
agent's, the owner's in-flight edits, and uncommitted documentation.
Recovered in full, but only because the stashes happened to survive. A file
allowlist did not prevent it, because the destructive command **took no file
arguments**.

### Command denylist — applies to every subagent, no exceptions

A subagent may **not** run, under any justification:

- `git stash` (any form), `git checkout -- .`, `git restore`, `git reset
  --hard`, `git clean`
- `git rebase`, `git merge`, `git cherry-pick`, `git revert`, force-push
- `git branch -D`, `git stash drop/clear`, any history rewrite
- `rm -rf`, or any bulk delete outside its own scratch directory
- any `*_LIVE_MODE` env var set to true; any real Gelato/Etsy write

**Subagents may read git state freely** (`git status`, `git diff`, `git log`,
`git show`) — reading was never the problem. If a subagent believes it needs
a write-side git operation, it **reports and stops**. The main thread runs
it, if at all.

**Also brief each subagent with:** its section of this kickoff verbatim, the
relevant `CLAUDE.md` constraints, an explicit file allowlist, and this
denylist. The allowlist and the denylist are complementary — session 1
proved the allowlist alone is not sufficient.

### The split

| Leg | Where | Why |
|---|---|---|
| **D** shipping collapse | **Sonnet subagent** | Mechanical: one config value, one signature, one call site. |
| **E** stall predicate | **Sonnet subagent** | Fully specified above: one CHECK value, one constant, one clause. |
| **G** test-suite sweep for mechanical renames | **Sonnet subagent** | Only after A–C are settled. |
| **Review pass, per commit** | **Sonnet subagent** | Reads the diff against §6's DoD, reports, does not edit. |
| **A** weld cut | **Main thread** | Two timings, four behaviours that must survive the move, one flagged judgement call. |
| **B** gallery assembly | **Main thread** | The silent-wipe risk. This is why the session exists. |
| **C** abandon/cleanup | **Main thread** | Deletion semantics against a shared row — same risk class as B. |
| **F** digest pass | **Main thread** | Extent unknown until traced. |

**Parallelism:** D and E touch disjoint files and can run alongside A. B
depends on A. C depends on A. Do not parallelise anything with B.

**Never delegated:** the decision to deviate from this kickoff. A subagent
that finds the spec wrong reports back; it does not improvise
(`CLAUDE.md` §3 — flag contradictions, don't route around them).

---

## 5. Definition of done

- [ ] **The secondary path works again** — `group_mockup` for 5x7/10x24
      renders mockups without touching Gelato and without hitting
      `SharedProductVariantError`. This is the first thing to get green.
- [ ] Render and Gelato-create are separate functions with separate timings;
      the four preserved behaviours (re-poll, orphan delete, idempotent
      create, DPI guard) each still covered by a test.
- [ ] **A test that fails on today's code**: rendering 5x7's mockups leaves
      primary's `product_images` rows untouched. Without this test the
      session's main risk is unproven.
- [ ] One Gelato product per candidate, created once at publish, carrying
      only validated sizes, each with its own group's `fileUrl`.
- [ ] `len(images) <= 20` asserted, not assumed.
- [ ] `patch_etsy_listing` is idempotent — a second call does not duplicate
      the gallery. Tested.
- [ ] Rejecting/abandoning a secondary group deletes **nothing**; the shared
      row and every other group's variants and images survive. Tested.
- [ ] Shipping resolves once per candidate to `288734253315`; prices
      unchanged.
- [ ] Stall predicate present, constant-driven, tested by lowering the
      constant.
- [ ] SPEC v4.12 written; the three `CLAUDE.md` rewrites applied verbatim
      from the PRD. **If a fourth constraint is wrong, flag it — do not edit
      it silently.**
- [ ] Full suite green.
- [ ] **Zero live calls except the two approved draft deletions.**
- [ ] Session log appended to the plan-of-attack's Part 4.

---

## 6. Scope check — this may want to be two PRs

§2 A–C is one coherent, risky change. §2 D–G is a set of independent,
mostly-mechanical ones. If the session runs long, **split at that line and
ship A–C first** — do not let the shipping-profile collapse sit unmerged
behind the gallery rework, and do not rush the gallery rework to land
everything at once. Say which shape you took in the session log.

---

## 7. What GL-13 inherits

The live re-test proves what this session can only assert in dry-run: one
listing carrying 4/5/6 variants across its lifecycle, a gallery that grew
across two reviews, and a rejected secondary group that deleted nothing.
Anything this session could not prove offline belongs in GL-13's delta —
list it explicitly in the session log rather than leaving GL-13 to rederive
it.
