# Critic Pass Stage (`critic_pass.py`) — Design

**Status:** approved by Quentin 2026-07-10
**Scope:** `pipeline/critic_pass.py`, the fifth of 12 M1 pipeline stage modules. A vision-
capable Claude call reviewing the **primary group's** rendered gallery images plus the draft
title/tags/description against a fixed rubric, per SPEC_v4.10.md section 3 step 5. Consumes
`compliance_draft.py`'s output (`status='generating'` candidates with a `listing_texts` row);
owns the regenerate-retry loop across `generate.py` → `primary_mockup.py` → `compliance_draft.py`
→ itself (up to 3 attempts); on pass, sets `candidates.status='primary_review'` (the trigger
point for the not-yet-built digest stage); on exhaustion, abandons the candidate with Gelato
cleanup and a Go/Hold/Kill fallback.

## Non-goals

- No group-level (5x7/10x24) critic pass — that's `group_critic_pass.py`, a separate future
  stage per CLAUDE.md's 12-stage list, reusing this stage's rubric but scoped to a different
  group and triggered only after primary-group approval (SPEC section 3 step 7).
- No Telegram digest. Setting `candidates.status='primary_review'` on pass is this stage's
  entire contribution to that hand-off — confirmed deferred here in both `primary_mockup.py`'s
  and `compliance_draft.py`'s design reviews.
- No live Etsy calls, no publish logic.
- No schema changes. `candidates.status` already has `'primary_review'`/`'failed'`,
  `groups.status` already has `'failed_abandoned'`, `group_products.status` already has
  `'deleted'`, and `critic_pass_attempts` (group_id, attempt_number 1-3, passed, failure_reason,
  correction_notes, `UNIQUE(group_id, attempt_number)`) already exists in `db/schema.sql`,
  built in anticipation of this stage.

## 1. Vision call: `anthropic_client.complete_with_images`

Verified live against Anthropic's current API docs (not guessed): an `image` content block
with `source: {"type": "url", "url": "..."}` is a real, documented source type alongside
base64/`file_id` — Gelato's hosted preview/gallery URLs can be passed directly, no
fetch-and-base64 step needed. Anthropic's own guidance is images-before-text in the content
array.

```python
# pipeline/anthropic_client.py — new addition, alongside complete()/research_web_search()
def complete_with_images(prompt: str, image_urls: list[str], *, api_key: str = None,
                          max_tokens: int = 1024) -> dict:
    """Vision-capable single-turn completion. Content = one {"type":"image","source":
    {"type":"url","url":...}} block per image_urls entry (in order), followed by one
    {"type":"text","text":prompt} block. Same {"text","raw"} return shape as complete()/
    research_web_search()."""
```

## 2. `critic_pass.py` function signatures

```python
CRITIC_RUBRIC_PROMPT_TEMPLATE = "..."  # no-go list + image-quality checks + text/image/niche match

def get_primary_group_state(conn, candidate_id: int) -> dict:
    """Reads the candidate's primary group_id, its current (single, live) group_product_id,
    that group_product's gallery image_urls (ordered by gallery_order), and the candidate's
    listing_texts row. Raises ValueError if any piece is missing."""

def build_critic_prompt(listing_text: dict, image_count: int) -> str:
    """Pure. Rubric: hard no-go-list compliance across all gallery images (named styles,
    characters/logos, implied hand-painted/celebrity claims), basic image-quality checks
    (artifacts, watermark-like elements, off-center/cut-off composition) per image, and
    whether the draft title/description actually match the images and niche. Requests JSON
    {"passed": bool, "reason": str} - pass/fail plus reason, not a tunable score."""

def evaluate_critic_pass(gallery_image_urls: list, listing_text: dict, *,
                          api_key: str = None) -> dict:
    """Calls anthropic_client.complete_with_images(build_critic_prompt(...), gallery_image_urls,
    api_key=api_key), json.loads(result["text"]). Raises ValueError if "passed"/"reason" keys
    are missing - fails loud rather than silently treating a malformed response as a pass."""

def record_critic_attempt(conn, group_id: int, attempt_number: int, result: dict,
                           correction_notes: str = None, *, now=None) -> int:
    """INSERTs one critic_pass_attempts row (group_id, attempt_number, passed, failure_reason,
    correction_notes, created_at). Returns the new row id."""

def discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None,
                                api_key: str = None) -> None:
    """gelato_client.delete_product() on that group_products row's gelato_product_id, then
    physically DELETEs the group_products row and its product_images children from SQLite.
    See section 4 for why this must be a real delete, not a status flag."""

def abandon_candidate(conn, candidate_id: int, group_id: int, reason: str, *, now=None) -> None:
    """UPDATE candidates SET status='failed', failed_reason=reason, updated_at=...; UPDATE
    groups SET status='failed_abandoned', failed_reason=reason, updated_at=... WHERE id=group_id.
    Commits both in one transaction."""

def run_critic_pass(conn, candidate_id: int, *, static_config: dict = None,
                     anthropic_api_key: str = None, store_id: str = None,
                     gelato_api_key: str = None, replicate_api_token: str = None,
                     now=None) -> dict:
    """One ready candidate -> up to 3 evaluate/regenerate loops. See section 3 for the full
    step-by-step flow. Returns {"candidate_id", "passed": bool, "attempts": int}."""

def run_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                           store_id: str = None, gelato_api_key: str = None,
                           replicate_api_token: str = None, now=None) -> list[int]:
    """Batch entry point (morning run, after compliance_draft). Selects every ready candidate
    (section 2's predicate) and calls run_critic_pass on each, isolating per-candidate failures
    with the same try/except-and-continue pattern as the other *_cycle functions."""
```

**Reads from the candidate row:** `id`, `niche`, `base_image_url`.
**Reads from `groups`/`group_products`/`product_images`/`listing_texts`:** the primary group's
current gallery and draft text, via `get_primary_group_state`.
**Writes:** `critic_pass_attempts` rows (one per attempt), `candidates.status`/`failed_reason`,
`groups.status`/`failed_reason` on final outcome. Deletes and re-creates `group_products`/
`product_images`/`listing_texts` rows on retry (via the other stages' own functions plus
`discard_superseded_attempt`'s cleanup).

## Selection predicate (`run_critic_pass_cycle`)

```sql
SELECT DISTINCT c.id FROM candidates c
JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
JOIN listing_texts lt ON lt.candidate_id = c.id
WHERE c.status = 'generating'
  AND g.id NOT IN (
    SELECT group_id FROM critic_pass_attempts WHERE passed = 1
  )
ORDER BY c.id
```

`c.status = 'generating'` excludes anything already `'primary_review'` (passed) or `'failed'`
(exhausted) or `'compliance_failed'` (upstream problem, not this stage's concern). The
`critic_pass_attempts` anti-join is a belt-and-suspenders check — in normal flow a pass
immediately flips `candidates.status`, but it protects against re-running the batch cycle
mid-way through a partially-completed manual run.

## 3. `run_critic_pass` step-by-step (the retry loop)

1. `get_primary_group_state(conn, candidate_id)` → `group_id`, `group_product_id`, gallery
   `image_urls`, `listing_text`. Raise `ValueError` if the candidate or any piece is missing.
2. `attempt_number = 1`.
3. `evaluate_critic_pass(image_urls, listing_text, api_key=anthropic_api_key)` → `result`
   (`{"passed", "reason"}`).
4. `record_critic_attempt(conn, group_id, attempt_number, result, ...)`.
5. **Pass:** `UPDATE candidates SET status='primary_review', updated_at=...`. Return
   `{"candidate_id", "passed": True, "attempts": attempt_number}`.
6. **Fail, `attempt_number < 3`:**
   a. `discard_superseded_attempt(conn, group_product_id, ...)` — delete this attempt's Gelato
      product + its SQLite rows (section 4).
   b. `conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))`
      (section 4).
   c. `generate.generate_for_candidate(conn, candidate_id, correction_note=result["reason"],
      api_token=replicate_api_token, now=now)` → new base image, overwriting
      `base_image_url`/`base_replicate_prediction_id` (per that function's existing,
      retry-safe design).
   d. `primary_mockup.create_primary_mockup(conn, candidate_id, static_config=static_config,
      store_id=store_id, api_key=gelato_api_key, now=now)` → new `group_products`/
      `product_images` rows (`get_or_create_primary_group` finds the same `group_id`, per its
      existing idempotent design).
   e. `compliance_draft.build_compliance_draft(conn, candidate_id, static_config=static_config,
      anthropic_api_key=anthropic_api_key, now=now)` → new `listing_texts` row.
   f. `attempt_number += 1`; re-fetch gallery/draft text via `get_primary_group_state`; go to
      step 3.
7. **Fail, `attempt_number == 3`:**
   a. `discard_superseded_attempt` on this (final) attempt's product too.
   b. `abandon_candidate(conn, candidate_id, group_id, result["reason"], now=now)`.
   c. `research.trigger_fallback_if_needed(conn, now=now)` (section 5).
   d. Return `{"candidate_id", "passed": False, "attempts": 3}`.

**On any exception from steps 6c/6d/6e (an operational failure in a retry attempt, not a
critic-pass rubric fail):** propagate the exception — `run_critic_pass_cycle` isolates it per
candidate, same as the other `*_cycle` functions. The candidate is left at `status='generating'`
mid-retry; a subsequent manual/batch run can pick it back up, since the selection predicate only
excludes candidates with a recorded pass.

## 4. Two bugs found while tracing this through already-merged code

Neither is hypothetical — both are real defects in the current implementation that only
manifest once a second attempt exists, which nothing before this stage ever created.

**`compliance_draft.get_primary_gallery` has no `group_products.status` filter or "latest"
concept.** Its join (`product_images` → `group_products` → `groups WHERE group_type='primary'`)
returns every row for the group, unfiltered. If a superseded attempt's `group_products`/
`product_images` rows are left in place when a new attempt starts, this query mixes images
from both attempts. **Fix:** `discard_superseded_attempt` physically `DELETE`s the superseded
`group_products` row and its `product_images` children from SQLite (not just a status flag),
so only one live `group_products` row per group ever exists at a time — `get_primary_gallery`
needs no changes. This also naturally satisfies SPEC section 3 step 5's "delete the Gelato
product created during each failed attempt": one delete per attempt, as it's superseded,
rather than a batch sweep saved for final abandonment.

**`compliance_draft.write_listing_texts` always `INSERT`s; `listing_texts` has no
`UNIQUE(candidate_id)`.** A second `build_compliance_draft` call on retry would leave two rows
for one candidate, breaking that module's own stated "one row per candidate" invariant.
**Fix:** `run_critic_pass` deletes the stale `listing_texts` row (step 6b) before re-drafting,
rather than patching the already-merged, tested `compliance_draft.py`.

Per-attempt history is still fully preserved where the spec actually requires it —
`critic_pass_attempts.failure_reason`/`correction_notes`, one row per attempt, kept forever.
Image/text rows don't need to survive their own supersession, consistent with
`generate_for_candidate` already overwriting `base_image_url` on every retry today (no image
generation history is kept anywhere either, so this isn't a new loss of information).

## 5. Go/Hold/Kill fallback: `research.trigger_fallback_if_needed`

No existing function returns "the next-highest-scored candidate" — [[project_candidate_scoring_in_memory_only]]
means nothing is persisted to re-rank against later, and `_insert_candidate` is private to
`research.py`. The schema also has no `batch_id`/cycle-grouping concept — candidates are rows
with only `created_at`, so "the pool that cycle" can't be queried precisely as SPEC section 3
step 1 describes it.

Other Go candidates from the same research cycle are already processed independently and in
parallel by `run_generate_cycle`/`run_primary_mockup_cycle`/etc. (each candidate row is handled
on its own, isolated try/except — none of them "wait" on this candidate's outcome). A fallback
is therefore only actually needed when abandonment would leave **zero** other live candidates
for the rest of the pipeline to work on this run.

```python
# pipeline/research.py — new addition
def trigger_fallback_if_needed(conn, *, now=None) -> int | None:
    """If any other candidate is currently non-terminal (status NOT IN ('failed','abandoned',
    'completed')), no-op and return None - that candidate is already being processed
    independently. Otherwise, insert one safe-evergreen candidate (via
    pick_safe_evergreen_fallback + classify + the same insert path _insert_candidate uses) and
    return its new candidate id."""
```

Confirmed reading (per your approval): "any other non-terminal candidate, system-wide" stands
in for "the pool that cycle" given there's no batch grouping to scope it more tightly. Adding a
`batch_id` column to precisely scope this was considered and explicitly rejected as scope creep
beyond this stage.

## 6. Status semantics summary

- **`candidates.status`** — stays `'generating'` throughout the retry loop (mid-attempt state
  is not distinguished at this granularity, matching every prior stage's convention). Flips to
  `'primary_review'` on pass (new value only this stage sets), or `'failed'` + `failed_reason`
  on 3-attempt exhaustion.
- **`groups.status`** — stays `'pending_review'` (set by `primary_mockup.py`) through every
  attempt, since there's no finer-grained enum value for "critic pass in progress." Flips to
  `'failed_abandoned'` + `failed_reason` on exhaustion only. A pass leaves it at
  `'pending_review'` — genuinely still true, since human review (the digest, a future stage)
  hasn't happened yet.
- **`group_products.status`**/**`product_images`**/**`listing_texts`** — the superseded
  attempt's rows are deleted outright on each retry (section 4); only one live set exists per
  group at any time, spanning the whole `create_primary_mockup` → `build_compliance_draft` →
  `evaluate_critic_pass` cycle for that attempt.
- **`critic_pass_attempts`** — one row per attempt (1-3), permanent, never deleted — the actual
  attempt-history record the spec asks for.

## 7. File / module layout

```
pipeline/
  critic_pass.py
  anthropic_client.py     # +complete_with_images()
  research.py             # +trigger_fallback_if_needed()
tests/
  test_critic_pass.py
  test_anthropic_client.py     # +tests for complete_with_images()
  test_research.py             # +tests for trigger_fallback_if_needed()
```

Depends on already-merged `pipeline/generate.py` (`generate_for_candidate`),
`pipeline/primary_mockup.py` (`create_primary_mockup`), `pipeline/compliance_draft.py`
(`build_compliance_draft`), `pipeline/gelato_client.py` (`delete_product`),
`pipeline/anthropic_client.py`, `pipeline/config.py`, `pipeline/db.py`. No `db/schema.sql`
changes (section, "Non-goals"). No `config/static_config.json` changes.

Note: this makes `critic_pass.py` a direct caller of three sibling stage modules, more coupled
than any prior stage — a deliberate choice (confirmed), since SPEC section 3 step 5 spells the
retry sequence explicitly ("generate → primary_mockup → compliance_draft → critic_pass,
repeated") and no separate orchestrator stage exists in CLAUDE.md's 12-stage list to own it.
