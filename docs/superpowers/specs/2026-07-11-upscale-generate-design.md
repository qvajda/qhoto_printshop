# Upscale-in-`generate.py` — Design

**Status:** approved by Quentin 2026-07-11
**Scope:** `pipeline/generate.py` and `pipeline/replicate_client.py`. Not a new pipeline stage —
extends the existing `generate` stage (2 of 12) so `candidates.base_image_url` always holds an
upscaled, 300-DPI-capable master image instead of FLUX schnell's raw ~1MP output. One new
`candidates` column. No changes to `critic_pass.py`, `primary_mockup.py`, or CLAUDE.md's 12-stage
list.

## Problem

`replicate_client.generate_image` (pipeline/replicate_client.py:19) calls FLUX schnell with only
`{"prompt": prompt}` — no `aspect_ratio`/`megapixels`, so it gets Replicate's default output,
capped at 1 megapixel for schnell (a model ceiling, not a config choice). Separately, no
`orientation`/`aspect_ratio` is ever decided at the candidate level even though the primary
template is hardcoded portrait (`primary_mockup.py:68`).

Confirmed against real Gelato usage (not assumed): Gelato enforces a 300 DPI minimum **at
product/mockup creation** (`create_product_from_template`, the same call `primary_mockup.py`
uses to render the preview images shown in the digest) and does not auto-upscale. At 300 DPI, the
smallest size sold (8x12, the primary size) needs ~2400x3600px (~8.6MP); the largest (A1) needs
~7016x9933px (~70MP). A 1MP source is short by 1-2 orders of magnitude for every size.

`critic_pass.py` (already built, stage 5) evaluates the rendered Gelato mockup images, not the
raw FLUX output (`get_primary_group_state` reads `product_images`, populated by
`primary_mockup.py`) — so it structurally cannot run before a mockup exists, and a mockup cannot
be created below the DPI floor. There is no automated gate available before mockup creation in
the current architecture; upscale must happen before the first `primary_mockup.create_primary_mockup`
call, i.e. immediately after FLUX generation, for every (re)generation.

## Non-goals

- **No new pipeline stage.** Upscaling is a step inside `generate_for_candidate`, not a 13th
  cron-scheduled function. CLAUDE.md's stage list is unchanged.
- **No pre-upscale filtering/gating.** Every FLUX output gets upscaled, including the up-to-3
  regenerations `critic_pass.py`'s retry loop can trigger. See "Deferred" below.
- **No orientation-selection system.** The aspect-ratio fix only makes the existing hardcoded
  portrait assumption (`primary_mockup.py:68`) explicit at generation time (`aspect_ratio="2:3"`)
  — it does not add landscape candidate support or any orientation decision logic.
- **No change to `critic_pass.py`, `primary_mockup.py`, or their tests.** Both already consume
  `candidates.base_image_url` as an opaque URL; they don't need to know it's now upscaled.
- **No pinned upscale model/input schema in this doc.** Per prior guidance on this project (verify
  real third-party API shapes before locking in a client, don't guess from training data), the
  exact Replicate model slug and its current input parameters are confirmed against Replicate's
  live catalog during implementation, not specified here.

## Deferred (flagged, not built now)

Decoupling upscale from every regeneration — e.g. a cheap pre-filter on the raw FLUX output that
runs before the expensive upscale+mockup steps — is a possible future optimization if
upscale volume/cost becomes a real problem. Not building it now: it would require reworking
`critic_pass.py`'s already-shipped, already-tested design (which evaluates the final mockup
composition, not the raw image), for a saving that's bounded by the existing 3-attempt retry cap.

## 1. Function signatures

```python
# pipeline/replicate_client.py

def generate_image(prompt: str, *, api_token: str = None) -> dict:
    """Unchanged signature. Now requests aspect_ratio="2:3" (matches the portrait primary
    template) and megapixels="1" (schnell's max) instead of relying on undocumented defaults."""

def upscale_image(image_url: str, *, api_token: str = None) -> dict:
    """New. Calls a Replicate-hosted upscale model on image_url, once, targeting a resolution
    that covers the largest print size in the primary aspect-ratio group (A1) at 300 DPI. Same
    call shape as generate_image (models/{model}/predictions, api_token defaulting to
    REPLICATE_API_TOKEN). Returns {"image_url": str, "prediction_id": str}. Raises on failure —
    no silent fallback to the un-upscaled image."""
```

```python
# pipeline/generate.py

def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None, now=None) -> dict:
    """Unchanged signature and retry-overwrite behavior. Internally now: call generate_image,
    then upscale_image on its output, then a single UPDATE writing base_image_url (the upscaled
    URL), base_replicate_prediction_id, base_upscale_prediction_id, and status='generating'. If
    upscale_image raises, the UPDATE never runs - the row is left exactly as it was (still
    'pending' on first attempt), so the existing per-candidate try/except in run_generate_cycle
    and in critic_pass.run_critic_pass's retry loop retries it next cycle unchanged. No new
    error-handling code needed in either caller."""
```

**Reads:** unchanged (`candidates` row by id).
**Writes:** `candidates.base_image_url` (repointed to mean "the upscaled master", not the raw FLUX
output), `candidates.base_replicate_prediction_id` (unchanged meaning: the FLUX prediction),
`candidates.base_upscale_prediction_id` (new).

## 2. Schema change

```sql
ALTER TABLE candidates ADD COLUMN base_upscale_prediction_id TEXT;
```

Mirrors the existing `base_replicate_prediction_id` column: pure traceability, no runtime
consumer reads it. No new table — this is a per-candidate fact, same cardinality as the columns
it sits next to.

`base_image_url` keeps its existing meaning to every current reader (`primary_mockup.py`,
`critic_pass.py` transitively via `product_images`) — only what it *contains* changes, not its
name or shape. No caller-side changes required outside `generate.py` itself.

## 3. Target resolution

Master target: large enough to cover A1 (the largest primary-group size) at 300 DPI -
approximately 7016x9933px, with a small margin for crop positioning. Verified this also covers
the 5x7 and 10x24 groups' own re-crops (both need fewer pixels in both dimensions than A1 at
300 DPI), so one upscale per candidate is sufficient for every size across all three
aspect-ratio groups - consistent with "generate once, reuse for every group crop."

Exact per-size pixel/DPI requirements should ultimately be read from the resolved Gelato template
metadata (once real template IDs replace the placeholders in `config/static_config.json`) rather
than hardcoded from nominal inch/mm labels - flagged for implementation, not a design blocker.

## 4. Testing

Extend `generate.py`'s existing test coverage (mocking `replicate_client`):
- `generate_for_candidate` calls `upscale_image` with the FLUX output and stores both prediction
  ids plus the upscaled URL as `base_image_url`.
- A failing `upscale_image` leaves the candidate row unchanged (still retryable) and propagates
  the exception - covering both the direct `run_generate_cycle` path and the `critic_pass.py`
  retry-loop call path.
- `generate_image`'s request body now includes `aspect_ratio="2:3"` and `megapixels="1"`.

No new tests needed in `critic_pass.py`/`primary_mockup.py` - their contracts are unchanged.
