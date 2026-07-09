# Compliance Draft Stage (`compliance_draft.py`) — Design

**Status:** approved by Quentin 2026-07-10
**Scope:** `pipeline/compliance_draft.py`, the fourth of 12 M1 pipeline stage modules.
Auto-fills, for the primary-size listing only: the disclosure text, the four compliance-
critical Etsy metadata fields (`who_made`/`production_partner_ids`/`taxonomy_id`/
`shipping_profile_id`), a first-pass title/tags/description validated against Etsy's format
limits, and alt text for every image `primary_mockup.py` rendered — per SPEC_v4.10.md
section 3 step 4. Consumes `primary_mockup.py`'s output (`status='generating'` candidates
with a `'created'` `group_products` row for the primary group); is itself consumed by the
not-yet-built `critic_pass.py`.

## Non-goals

- No vision/image inspection. The critic pass (SPEC section 3 step 5, future stage) is
  explicitly the vision-capable stage ("a vision-capable Claude call, distinct from the
  generation call"); compliance draft is a text-only pass. Alt text is generated from
  `image_type` (`flat_mockup` vs `lifestyle`) and the candidate's niche, not from looking at
  the rendered image.
- No critic-pass evaluation, no `candidates.status='primary_review'` transition — confirmed
  in the prior stage's design review as `critic_pass.py`'s job, not this one.
- No size-specific title suffix or per-size price. This stage's title/tags/description are
  the **shared base text** for the whole candidate; SPEC step 4 says step 7 reuses it per
  size "with only a small size-specific adjustment (a size suffix on the title, re-checked
  against the 140-character cap)" — that adjustment belongs to the future
  `publish_primary_group.py`/`publish_group.py` stages, not this one.
- No `is_supply`/`when_made`/`readiness_state_id` handling. These are fixed literals
  (`is_supply=false`, `when_made="made_to_order"`) or publish-time-only fields
  (`readiness_state_id`), not per-candidate values — `listing_texts` has no columns for
  them, and they belong on the future publish stage's `create_draft_listing` call, not
  persisted here.
- No live Etsy API calls at all. This stage only writes to local SQLite
  (`listing_texts`, `product_images.alt_text`).

## 1. Function signatures

```python
# pipeline/anthropic_client.py — new addition, alongside research_web_search
def complete(prompt: str, *, api_key: str = None, max_tokens: int = 1024) -> dict:
    """Plain single-turn completion, no tools. Same {"text", "raw"} shape as
    research_web_search but without the web_search tool."""

# pipeline/compliance_draft.py
DISCLOSURE_TEXT = "..."  # SPEC section 2's draft template, verbatim - see section 9

def resolve_compliance_metadata(static_config: dict) -> dict:
    """Pure, no I/O. Pulls who_made/production_partner_ids/taxonomy_id/shipping_profile_id
    straight from static_config's etsy_* keys. Passes blanks through as-is - see section 7."""

def validate_listing_text(title: str, tags: list[str]) -> None:
    """Pure. Raises ValueError (message names the offending field/limit) if title is over
    140 chars, tags has more than 13 entries, or any tag is over 20 chars."""

def get_primary_gallery(conn, candidate_id: int) -> list[dict]:
    """Returns the primary group's product_images rows (id, gallery_order, image_type),
    ordered by gallery_order. Helper shared by generate_draft_text's caller and
    update_gallery_alt_text."""

def build_draft_prompt(candidate: dict, image_types: list[str]) -> str:
    """Pure. Requests JSON {"title", "tags": [...], "description", "alt_texts": [...]}
    (alt_texts sized to len(image_types)) from Claude, with the 140-char/13-tag/20-char
    limits and the disclosure context spelled out in the prompt itself as a second line of
    defense on top of validate_listing_text."""

def generate_draft_text(candidate: dict, image_types: list[str], *, api_key: str = None) -> dict:
    """Calls anthropic_client.complete(build_draft_prompt(...)), json.loads the text.
    Raises ValueError if a required key is missing or len(alt_texts) != len(image_types) -
    fails loud rather than silently proceeding with partial/misaligned data."""

def write_listing_texts(conn, candidate_id: int, draft: dict, metadata: dict, *, now=None) -> int:
    """INSERTs one listing_texts row. tags and production_partner_ids are stored
    json.dumps()-encoded (see section 6). Returns the new row id."""

def update_gallery_alt_text(conn, candidate_id: int, alt_texts: list[str]) -> None:
    """UPDATEs product_images.alt_text in gallery_order, via get_primary_gallery. Raises
    ValueError on a count mismatch rather than silently leaving rows blank."""

def build_compliance_draft(conn, candidate_id: int, *, static_config: dict = None,
                            anthropic_api_key: str = None, now=None) -> dict:
    """One ready candidate -> one listing_texts row + updated alt text. See section 3 for
    the full step-by-step flow. Returns {"listing_text_id", "candidate_id"}. Does not touch
    candidates.status on success; sets status='compliance_failed' on failure (section 4)."""

def run_compliance_draft_cycle(conn, *, static_config: dict = None,
                                anthropic_api_key: str = None, now=None) -> list[int]:
    """Batch entry point (morning run, after primary_mockup). Selects every ready candidate
    (section 2's predicate) and calls build_compliance_draft on each, isolating per-candidate
    failures with the same try/except-and-continue pattern as the other *_cycle functions."""
```

**Reads from the candidate row:** `id`, `niche`, `style_theme_tags`, `trend_source`.
**Reads from `product_images`:** the primary group's gallery rows (`image_type`,
`gallery_order`), via `get_primary_gallery`.
**Writes:** one `listing_texts` row, N `product_images.alt_text` updates. Touches
`candidates.status`/`failed_reason` only on failure (section 4).

## 2. Selection predicate (`run_compliance_draft_cycle`)

```sql
SELECT c.id FROM candidates c
JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
JOIN group_products gp ON gp.group_id = g.id
WHERE c.status = 'generating'
  AND gp.status = 'created'
  AND c.id NOT IN (SELECT candidate_id FROM listing_texts)
ORDER BY c.id
```

Two different exclusion mechanisms, for two different reasons:
- **`c.status = 'generating'`** excludes anything already flipped to `'compliance_failed'`
  (section 4) — a failed draft doesn't get silently retried forever by the batch cycle,
  matching how `primary_mockup.py`'s `'mockup_failed'` rows are excluded from its own cycle.
- **`NOT IN (SELECT candidate_id FROM listing_texts)`** excludes anything already
  successfully drafted — necessary because a *successful* run leaves `candidates.status`
  unchanged at `'generating'` (this stage doesn't advance it; `critic_pass.py` does), so
  without this check a successful candidate would be redrafted every cycle.

## 3. `build_compliance_draft` step-by-step

1. Read the candidate row; raise `ValueError` if missing (same style as
   `generate_for_candidate`/`create_primary_mockup`). No DB writes have happened yet, so
   nothing needs to be marked failed on this specific error.
2. `get_primary_gallery(conn, candidate_id)` → gallery rows; derive `image_types` (ordered
   list of `'flat_mockup'`/`'lifestyle'`).
3. `resolve_compliance_metadata(static_config)` → metadata dict.
4. **From here through step 7, wrapped in try/except** (mirrors `create_primary_mockup`'s
   failure handling): on any exception, `UPDATE candidates SET status='compliance_failed',
   failed_reason=str(exc), updated_at=...`, commit, then re-raise.
5. `generate_draft_text(candidate, image_types, api_key=anthropic_api_key)` → `draft` dict
   (`title`, `tags`, `description`, `alt_texts`).
6. `validate_listing_text(draft["title"], draft["tags"])` — raises on format-limit
   violations.
7. `write_listing_texts(conn, candidate_id, draft, metadata, now=now)` → `listing_text_id`.
8. `update_gallery_alt_text(conn, candidate_id, draft["alt_texts"])`.
9. Return `{"listing_text_id": listing_text_id, "candidate_id": candidate_id}`.

Same accepted limitation as `primary_mockup.py`'s known minor finding: if step 7 commits but
step 8 then raises, the `listing_texts` row is already persisted, so the
`NOT IN (SELECT candidate_id FROM listing_texts)` predicate would treat the candidate as
"done" even though alt text wasn't fully updated — not fixed here, consistent with how that
stage's equivalent edge case was left unfixed.

## 4. Schema change: `candidates.status` gains `'compliance_failed'`

```sql
status TEXT NOT NULL CHECK(status IN (
  'pending','generating','primary_review','compliance_failed','failed','abandoned','completed'
)),
```

A distinct value from the existing `'failed'`, which is reserved for critic-pass exhaustion
(SPEC section 3 step 5 — 3 failed attempts, triggers the Gelato `DELETE` cleanup and the
Go/Hold/Kill fallback). A compliance-draft failure is a different, lighter-weight failure
mode (bad JSON from Claude, a validation-limit violation, an alt-text count mismatch) with no
Gelato cleanup or Go/Hold/Kill implications — conflating the two into one `'failed'` value
would make it impossible to tell them apart later without re-reading `failed_reason` text.

## 5. Status semantics summary

- **`candidates.status`** — stays `'generating'` on success (unchanged, same as
  `primary_mockup.py` leaves it — `critic_pass.py` is still the one that advances it to
  `'primary_review'`). Flips to `'compliance_failed'` + `failed_reason` on this stage's own
  failure (section 4) — new terminal-ish state, not auto-retried by the batch cycle.
- **`listing_texts`** — one row per candidate (not per group/size), created once by this
  stage. `publish_primary_group.py`/`publish_group.py` (future stages) read this same row
  for every size in every group, applying their own size-suffix/price adjustments on top.
- **`product_images.alt_text`** — flips from `primary_mockup.py`'s `''` placeholder to a
  real value, in place (`UPDATE`, not new rows), for every row in the primary gallery.

## 6. Serialization convention: `tags` and `production_partner_ids`

`listing_texts.tags` and `listing_texts.production_partner_ids` are both `TEXT NOT NULL` in
the schema but are naturally lists (`tags: list[str]`, `production_partner_ids: list[int]`
from `static_config["etsy_production_partner_ids"]`). No prior module has written to this
table, so this stage establishes the convention: **`json.dumps(...)`** for both, to be
`json.loads()`'d by whatever stage reads them later (`publish_primary_group.py`). Etsy's own
`createDraftListing` takes tags as a JSON array, so this round-trips cleanly into that future
call.

## 7. Static config resolution: pass blanks through, no fail-loud here

Since the prior handoff, three of the four Etsy metadata fields are resolved in
`config/static_config.json`: `etsy_taxonomy_id="1027"`, `etsy_who_made="i_did"`,
`etsy_production_partner_ids=[5717252]`. `etsy_shipping_profile_id` is still `""` and is
expected to eventually become a per-size mapping (same shape as `gelato_templates`) rather
than a single value — tracked as a separate, not-yet-done TODO in CLAUDE.md.

`resolve_compliance_metadata` does **not** fail loud on a blank/unresolved field — it passes
`static_config["etsy_shipping_profile_id"]` through as-is (currently `""`). Unlike the Gelato
template-ID placeholder policy (which fails loud specifically at the
`products:create-from-template` call boundary), this stage makes no live Etsy call at all —
the real fail-loud check belongs to the future `publish_primary_group.py` stage, which is the
one that would actually call `create_draft_listing` with a blank `shipping_profile_id`. This
keeps `compliance_draft.py` fully testable/runnable against today's still-blank config.

When `etsy_shipping_profile_id` is later restructured into a per-size dict, this function's
only change is the lookup key (`static_config["etsy_shipping_profile_id"]["8x12"]` instead of
a flat string) — no signature change.

## 8. Alt text: text-only, keyed by `image_type`

The critic pass (SPEC section 3 step 5) is explicitly the vision-capable stage in this
pipeline; nothing in step 4 asks for image inspection. `generate_draft_text` produces alt
text as part of the same single Claude call as title/tags/description, one entry per
`image_types` entry, distinguishing only `'flat_mockup'` (e.g. "flat print mockup of...") from
`'lifestyle'` (e.g. "shown in a room setting...") — not from actually looking at the rendered
image.

## 9. Disclosure text: draft wording, fine for dry-run/M1 development

`DISCLOSURE_TEXT` uses SPEC section 2's template verbatim, unchanged:

> "This design was created using AI image generation from the seller's own prompts, then
> selected, edited, and prepared for print by the seller. Printed and shipped by our
> production partner, Gelato."

Per your confirmation: acceptable for dry-run/M1 development now; the wording itself needs a
refinement pass before any real go-live milestone, tracked as a follow-up (not a blocker for
this stage's build or tests).

## 10. File / module layout

```
pipeline/
  compliance_draft.py
  anthropic_client.py     # +complete()
tests/
  test_compliance_draft.py
  test_anthropic_client.py  # +tests for complete()
```

Depends on already-merged `pipeline/anthropic_client.py` (extended with `complete`),
`pipeline/config.py`, `pipeline/db.py`. Touches `db/schema.sql` (section 4's
`candidates.status` addition — the only schema change). No changes to
`config/static_config.json` structure in this stage (the `etsy_shipping_profile_id`
per-size restructuring is a separate, not-yet-scheduled task).
