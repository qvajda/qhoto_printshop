# GL-22 session 1 — coding kickoff (v4.12, foundations)

**Tool: Claude Code, in-repo, test-driven.** Not Cowork — this is a schema
migration plus a client rework, all of it exercised against the test suite.

**Status of the work above this session:** GL-22a research ✅, GL-22b ✅,
GL-22c ✅, GL-22d ✅ struck. The PRD
(`docs/2026-08-01-v412-single-listing-prd.md`) is **signed off**. This is the
first of two build sessions.

---

## 0. Read these first, in this order

1. `docs/2026-08-01-v412-single-listing-prd.md` — the PRD, including the
   `[D1]`/`[D2]`/`[D3]` decision block at the top. **Scope is what the PRD
   says; this kickoff only carves session 1 out of it.**
2. `docs/2026-08-01-gl22a-findings.md` — the measured answers. Sections Q1,
   Q2 and Q4 are load-bearing for this session; the "Task 2 — impact map"
   section names the call sites.
3. `CLAUDE.md` — the hard constraints. Three of them are wrong under v4.12
   and their replacement text is already drafted in the PRD. **Do not apply
   those rewrites in this session** (see §4).
4. `db/schema.sql`, `pipeline/group_product.py`, `pipeline/etsy_client.py`.

---

## 1. What this session builds

Three workstreams, in this order. Each is independently committable; commit
after each passes its tests (repo convention).

### A. `etsy_client.py` — two fixes, unrelated to each other

**A1. The `update_listing_inventory` float-price bug.** Found live during
GL-22a Q4. `pipeline/etsy_client.py:185`. The function normalises
`offering["price"]` to a float **only for products whose size matched the
caller's `size_to_price` map**; every unmatched product is passed through
with Etsy's read shape, where `price` is an object (`{amount, divisor,
currency_code}`), and Etsy rejects the write with
`HTTP 400: Expected float value for 'price' (got array)`.

- Today this never fires because every caller passes the full size set. It
  will fire the first time anyone patches a subset. **v4.12 does not need
  it** (the second GL-22c fallback that would have is dead) — fix it anyway;
  it is a landmine directly under the next thing that touches this function.
- Fix: normalise `price` for **every** product in the outgoing body, not
  only matched ones. An unmatched product keeps its existing price value,
  converted to the float shape Etsy's write API expects.
- **Keep the existing `missing` guard intact.** Raising rather than silently
  dropping a size's price is the correct behaviour and is not what's broken
  here.
- Test: a listing inventory containing a size the caller did not price →
  the outgoing body has a float `price` on every offering, and the priced
  sizes still get their new prices.

**A2. A new `delete_listing`.** GL-22a needed to clean up two research
drafts and could not — there is no `delete_listing` in the client and the
current token has no `listings_d` scope.

- Same shape as the other write functions: `dry_run` defaulting to
  `not config.is_live_mode("ETSY")`, dry-run returning a synthetic response
  with no network call.
- `DELETE /v3/application/listings/{listing_id}`.
- **This is a destructive operation on an external account (CLAUDE.md §4).**
  Log loudly with the listing ID on every real call. Do **not** wire it into
  any pipeline stage in this session — it exists as a recovery tool, called
  by hand.

> **Manual prerequisite, owner action, do before or during the session:**
> re-authorise the Etsy OAuth token with the `listings_d` scope added. Same
> PKCE flow as the 2026-07-17 scope change (`etsy_oauth_authorize.py` →
> `etsy_oauth_exchange.py`). **A2 can be written and unit-tested without
> it** — dry-run needs no token — so this does not block the session; it
> blocks only the first real delete.

### B. The schema migration — additive, no row rewritten

Per the PRD's Migration and rollback section. Three nullable columns:

| Table | New column | Meaning |
|---|---|---|
| `group_products` | `candidate_id INTEGER REFERENCES candidates(id)` | the product now belongs to the candidate, not the group |
| `group_product_variants` | `group_id INTEGER REFERENCES groups(id)` | which group contributed this size |
| `product_images` | `group_id INTEGER REFERENCES groups(id)` | which group contributed this image — **this is what makes session 2's scoped gallery rebuild possible at all** |

- Update `db/schema.sql` **and** ship a `migrate_*.py` following the
  existing convention (`migrate_generation_attempts_table.py` is the model):
  module docstring stating what and why, idempotent, safe to run repeatedly,
  `DEFAULT_DB_PATH` pointing at `db/qhoto.sqlite3`.
- **Do not backfill.** The five real GL-9 rows under candidate 39 (ids
  9–13; id 10 `published` with real Etsy listing `4542159277`, id 12
  `created` with no listing id resolved) keep `candidate_id NULL` and stay
  on the old code path. A `candidate_id IS NOT NULL` gate distinguishes new
  rows from old ones — new code must never assume the new shape on a row
  that predates the migration.
- `group_products` currently has `group_id NOT NULL`. **Leave it that way**
  for now: a v4.12 row still records which group first created the product,
  and dropping a NOT NULL in SQLite means a table rebuild, which is exactly
  the non-additive change the rollback story depends on avoiding. If this
  turns out to be wrong when session 2 writes the gallery code, raise it —
  don't rebuild the table on your own initiative.
- **Rollback is "stop calling the new path", not a down-migration.** Say so
  in the migration script's docstring.

### C. `create_or_reuse_group_product` — candidate-keyed, per-group images

`pipeline/group_product.py:165`. Callers today:
`pipeline/primary_mockup.py:48`, `pipeline/group_mockup.py:63`,
`pipeline/publish_primary_group.py:84`.

The two changes:

1. **Reuse key moves from `group_id` to `candidate_id`.** Both reuse
   lookups (the `status IN ('created','published')` one and the
   `status IN ('mockup_failed','publish_failed')` one) key on the candidate.
2. **Per-variant image resolution.** GL-22a Q1 proved that two variants
   sharing one `image_placeholder_name` accept independently-submitted
   `fileUrl`s in a single `create-from-template` call. So the create body
   carries **each size's own group's crop**, resolved per variant, in one
   call. Today `group_product.py` passes one `image_url` to every variant.

**Three behaviours in the existing function that must survive intact** —
each was written against a real failure and none of them is superseded:

- **The `mockup_failed`-with-a-product-id reuse path.** A create that
  succeeded but whose readiness poll timed out is *not* stale; deleting and
  recreating restarts the same slow clock and churns a real Gelato product.
  Read the comment at `group_product.py:200` before touching this.
- **The orphan delete on a genuinely stale row** (`publish_failed`, or a
  `mockup_failed` that never returned a product id). The live run duplicated
  products because a create succeeded, the poll timed out and the retry
  re-created — idempotency here is a hard constraint, not a nicety.
- **The DPI guard before any DB write**, so a too-small master fails fast
  without orphaning a `group_products` row.

**The sizes-changed branch needs care.** Today, when the requested size set
differs from the stored one, the function deletes the Gelato product and
recreates. Under `[D1]` the size set is settled *before* the first create
(all groups are decided first), so that branch should become **much rarer**
— but the existing trigger, `primary_mockup.py`'s 8x12-only row expanding to
the 4-size fan-out on approval, still exists and still needs it.
**Do not delete this branch. Do not extend it to delete a product that other
groups' variants already depend on** — that is precisely the shared-product
delete v4.12 forbids. If the two requirements collide in a way this kickoff
hasn't anticipated, **stop and flag it** rather than picking one.

---

## 2. Explicitly out of scope — session 2 owns these

Touching any of them in this session is scope creep; if a change here seems
to force one, stop and say so.

- **Gallery assembly across groups**, the ≤20-image assertion, the scoped
  clear/rebuild, and the unanswered `patch_etsy_listing` full-vs-delta
  upload question. This is session 2's whole point and its sharpest risk.
- **Abandon/reject/cleanup** — `critic_pass.discard_superseded_attempt`,
  `cleanup.py`'s two product-deleting queries, `publish_group.py`'s reject
  branch.
- **The shipping-profile collapse** to a single `288734253315`
  (`config/static_config.json`'s per-group-type dict,
  `pipeline/config.get_shipping_profile_id`).
- **The stall rule** `[D2]` — `stalled_skipped` in the `groups.status`
  CHECK, `GROUP_REVIEW_STALL_DAYS = 14`, and the extra clause in the publish
  gate. (Note: an earlier draft made this a `stall_sweep` stage with a
  `reminder_sent_at` column. **Both are struck** — the reminder is deferred
  post-go-live as GL-31, which reduces the rule to a predicate. Do not add
  either in this session's migration.)
- **`group_mockup.py` / `group_critic_pass.py` / `digest.py` wording and
  data shapes.**
- **SPEC v4.12** and the **CLAUDE.md rewrites**.
- **`run_m1_live_test.py`** end-to-end assertions (unit tests here, yes;
  the live-test harness, no).

---

## 3. Definition of done

- [ ] A1 fixed with a test that fails on the old code.
- [ ] A2 written, dry-run-aware, unit-tested, unwired, loud on real calls.
- [ ] `db/schema.sql` updated **and** an idempotent `migrate_*.py` shipped;
      running it twice against a copy of the real DB is a no-op the second
      time and leaves the five GL-9 rows byte-identical.
- [ ] `create_or_reuse_group_product` keyed on `candidate_id`, resolving a
      per-variant image, with the three preserved behaviours still covered
      by their existing tests (**existing tests adapted, not deleted** — if
      a test now asserts the wrong thing, rewrite the assertion and say why
      in the commit; deleting it loses the failure it was written against).
- [ ] New tests: one product reused across two groups of the same candidate;
      two variants in one create body carrying different `fileUrl`s; a
      pre-migration row (`candidate_id NULL`) still resolving under the old
      path.
- [ ] Full suite green (597+ on master as of GL-23).
- [ ] **Zero live calls.** Everything in this session is provable in
      dry-run. If something seems to need a live call, it belongs to
      session 2 or to GL-13 — flag it, don't make the call.
- [ ] A short session log appended to `docs/2026-07-22-go-live-plan-of-attack.md`
      Part 4, in the style of the existing entries: what was found, what
      was decided in-flight, what the next session inherits.

---

## 4. Constraints this session must respect

- **CLAUDE.md's three wrong constraints stay wrong until session 2.** Their
  replacement text is drafted in the PRD. Rewriting them now would leave
  `CLAUDE.md` describing a shape the code does not yet have, which is worse
  than describing one it no longer has — at least the second is obviously
  stale. **If you find a fourth constraint this change makes wrong, flag it;
  do not edit it silently** (the PRD's audit found three and explicitly
  flagged that absence rather than declaring the audit complete).
- **Never call Gelato or Etsy against real endpoints without an explicit
  go-ahead** (repo convention). Dry-run and the `*_LIVE_MODE` gates cover
  everything here.
- **Artwork generation is untouched.** Replicate + FLUX.1 [schnell] only;
  this session sees already-generated, already-cropped images and nothing
  upstream of them.
- **Commit after each workstream passes its tests.**

---

## 5. How to run this session — subagents, model-matched

Owner direction (2026-08-01): **use subagents, and use Sonnet where the
complexity allows.** The split below follows the same risk gradient that
split the two sessions in the first place.

**The tell for whether something is a subagent's job:** if this kickoff
already states exactly what the code must do, delegate it. If this kickoff
says "if these two requirements collide, stop and flag it", it needs
judgement about the project's history and stays on the main thread.

| Leg | Where it runs | Why |
|---|---|---|
| **A1** inventory float-price fix | **Sonnet subagent** | Cause is diagnosed, fix is stated, test is stated. No history to weigh. |
| **A2** `delete_listing` | **Sonnet subagent** | A new function following an existing shape in the same file. |
| **B** schema migration | **Sonnet subagent** | Three nullable columns, an idempotent script, an existing script to model it on. |
| **C** `create_or_reuse_group_product` | **Main thread** | Three preserved behaviours, each written against a real live-run failure, plus a sizes-changed branch this kickoff explicitly says may collide with the shared-product rule. Judgement, not transcription. |
| **Review pass** | **Sonnet subagent, per commit** | Reads the diff against §3's DoD and reports; does not edit. |

**Parallelism.** A (A1 + A2, same file — one subagent doing both, sequential
within itself) and B (schema + migration script) touch **disjoint files** and
can run in parallel. **C depends on B** — it queries `candidate_id` — so C
starts after B lands. Do not parallelise C with anything.

**Briefing a subagent.** Each one gets: its section of this kickoff verbatim,
the relevant `CLAUDE.md` constraints, and the file paths it may touch —
**plus an explicit instruction that it may not touch files outside that
list**. A subagent that "helpfully" adjusts the gallery code has done the
damage session 2 exists to avoid.

**What does not get delegated, ever:** the decision to deviate from this
kickoff. A subagent that finds the spec wrong reports back; it does not
improvise. Same rule as `CLAUDE.md` §3 — flag contradictions, don't route
around them.

---

## 6. What session 2 inherits

Stated so it can be checked rather than rediscovered: a candidate-keyed
product with a `group_id` recorded on every variant and every image, an
`etsy_client` whose inventory patch survives a partial size set, and a
`delete_listing` to recover with. Session 2's gallery work depends on
`product_images.group_id` existing — if B lands differently from the table
above, session 2's kickoff needs updating before it starts.
