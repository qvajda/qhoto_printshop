# Design Generation Stage (`generate.py`) — Design

**Status:** approved by Quentin 2026-07-09
**Scope:** `pipeline/generate.py`, the second of 12 M1 pipeline stage modules. One
Replicate (FLUX.1 [schnell]) image-generation call per candidate, writing the result
back onto the `candidates` row. Consumes `research.py`'s output (`status='pending'`
rows); is itself consumed by the not-yet-built `primary_mockup.py` and, later,
`critic_pass.py`'s regenerate-on-fail loop.

## Non-goals

- No Gelato mockup creation (`primary_mockup.py`'s job).
- No compliance-draft text generation or critic-pass rubric evaluation.
- No group-level (5x7/10x24) crop/recomposition — those stages reuse the base image
  this module produces and never call Replicate themselves, which is how CLAUDE.md's
  "a design is only ever image-generated once" constraint is actually enforced (by
  those later stages simply never invoking this module again once a candidate's
  primary group is approved).

## 1. Function signatures

```python
def build_prompt(candidate: dict, *, correction_note: str = None) -> str:
    """Pure prompt-construction, no I/O. Exposed separately so tests can assert on
    prompt content without mocking Replicate."""

def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None) -> dict:
    """Reads one candidate row, calls replicate_client.generate_image() once (always a
    fresh call - see section 2), writes base_image_url/base_replicate_prediction_id/
    status back, returns {"image_url": ..., "prediction_id": ...}."""

def run_generate_cycle(conn, *, api_token=None) -> list[int]:
    """Batch entry point for the twice-daily morning run: selects every
    status='pending' candidate and calls generate_for_candidate() on each. Returns the
    list of candidate IDs processed."""
```

**Reads from the candidate row:** `id`, `niche`, `style_theme_tags` (currently always
NULL - see section 4).
**Writes back:** `base_image_url`, `base_replicate_prediction_id`, `status`
(`'pending'` → `'generating'`), `updated_at`.

`run_generate_cycle` processes **every** pending candidate from the cycle, not just
one — the spec's digest step explicitly repeats "once per candidate in the batch," and
there's no persisted candidate score to rank by (deliberate — see
`project-candidate-scoring-in-memory-only` memory). A batch with multiple Go
candidates (e.g. several trending-now keywords clearing the demand threshold) is
expected to generate multiple designs in one cycle.

## 2. Consuming research.py's output / the future critic-pass retry hook

`generate_for_candidate` only ever operates on `status='pending'` rows (Go
candidates); Hold/Kill candidates are `'abandoned'` and untouched by this module.

Per SPEC_v4.10.md section 3 step 5, the primary-group critic-pass retry loop
("design generation → primary-size mockup → compliance draft → critic pass,
repeated" up to 3 times) really does call design generation again each attempt — this
is distinct from CLAUDE.md's "image-generated once" constraint, which is about
*group-level* crop retries (5x7/10x24, step 7) reusing an *already-approved* base
image. Concretely:

- `generate_for_candidate` always makes a fresh Replicate call and **overwrites**
  `base_image_url`/`base_replicate_prediction_id` on the candidate row — no per-attempt
  image history is kept here (attempt history/failure reasons live in
  `critic_pass_attempts`, keyed to the primary `groups` row, once that stage exists).
- The future `critic_pass.py` retry loop calls
  `generate_for_candidate(conn, candidate_id, correction_note=<prior failure_reason>)`
  directly, up to 3 times — bypassing `run_generate_cycle`, which only ever runs the
  first attempt for a fresh batch.
- Once the primary group is human-approved, nothing calls `generate_for_candidate` for
  that candidate again.

## 3. Prompt construction & no-go list enforcement

`build_prompt` combines a fixed niche/style scaffold, the candidate's `niche`, and the
SPEC section 2 hard no-go list, baked in as explicit negative instructions inside the
single prompt string — `replicate_client.generate_image` takes only `{"prompt": ...}`,
there's no separate negative-prompt field:

```
A minimalist botanical/nature wall art print: {niche}. Clean composition, soft muted
natural color palette, print-ready poster art, no text or watermarks.
Do not depict any named artist's style, recognizable characters, franchises, or logos.
Do not imply celebrity likeness. Do not claim or resemble hand-painted or one-of-a-kind
original artwork - this is a print reproduction.
[if correction_note given: Previous attempt was rejected for: {correction_note}.
Avoid this issue in the new image.]
```

**Enforcement split:** this stage's no-go language is best-effort prompt steering
only — generative models don't reliably obey negative instructions. The critic pass
(future stage, vision-capable Claude call) is the authoritative compliance gate,
inspecting the rendered image and forcing a regenerate on violation. Both layers are
required per CLAUDE.md ("baked into generation prompts, not just review") — neither
alone is sufficient.

## 4. Decisions from review (2026-07-09)

- **Orientation — portrait only for M1.** The base image is always generated
  portrait-oriented; there is no per-candidate orientation choice yet, and no
  `candidates.orientation` column. **Flagged as a deferred feature, not solved here:**
  a future revision may need to pick portrait vs. landscape per design (e.g. by niche
  or an explicit signal), which would need a schema addition at that time. Noting it
  here so it isn't silently lost, per CLAUDE.md's placeholder-policy spirit.
- **Status transition — combined check, no new status value.** `generate_for_candidate`
  sets `status='generating'` (no new enum value added to `db/schema.sql`).
  `primary_mockup.py` (next stage, not built yet) is expected to select on
  `status='generating' AND base_image_url IS NOT NULL` to mean "image ready, not yet
  mocked up."
- **`rationale` (research.py's raw-candidate field) — left out.** It's already not
  persisted anywhere on `candidates` (no column exists), and `build_prompt` doesn't
  need it — niche + the fixed style/no-go scaffold is enough for M1. Not adding a
  schema column for it now.
- **`style_theme_tags` — deferred, not populated by this stage.** The column stays
  NULL through `generate.py`; prompts use a hardcoded style descriptor set instead of
  reading this column. **Flagged for a later stage** (most likely compliance-draft,
  which generates alt text/description and might want richer style tags) to decide
  whether/how to populate it — not solved here.

## 5. File / module layout

```
pipeline/
  generate.py
tests/
  test_generate.py
```

Depends on already-merged `pipeline/replicate_client.py` (`generate_image`),
`pipeline/db.py` (connection/schema), `pipeline/config.py` (env/static config
plumbing, not actually needed here since Replicate has no static per-size config).
No changes to `db/schema.sql`, `config/static_config.json`, or `.env.example`.
