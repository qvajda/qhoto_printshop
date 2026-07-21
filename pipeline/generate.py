from datetime import datetime, timezone

import pipeline.art_brief as art_brief
import pipeline.artwork_store as artwork_store
import pipeline.http as http
import pipeline.replicate_client as replicate_client


# S4-c(1) (docs/2026-07-20-remediation-plan-consolidated.md): positive-only,
# ~40 words. FLUX.1 has no negative-prompt channel - the old scaffold's ~10
# negated clauses ("no frame", "not sparse", "Do not depict...") were dead
# weight at best, prompt-corrupting at worst. The no-go list now lives only
# in art_brief.py's brief-writing instructions (a text LLM honors "don't
# reference named artists" reliably; the image model never sees it).
# Vocabulary is S4-a's bestseller-study wording verbatim - density/coverage
# was the single biggest lever separating good from condemned masters.
POSITIVE_SCAFFOLD = (
    "Flat 2D full-bleed artwork, one coherent centered subject, dense composition "
    "filling the frame edge to edge. Bold filled color zones with crisp clean "
    "edges, no smudging. Warm muted palette on a soft cream ground. Print-ready, "
    "no text or watermarks."
)


def build_prompt(candidate: dict, *, correction_note: str = None) -> str:
    """art_brief (the per-candidate visual brief, see art_brief.py) + the
    positive scaffold tail. S4-c(2): the correction note sits BETWEEN the
    brief and the scaffold, not appended last - if the schnell 256-token T5
    cap is ever hit, truncation eats the end of the prompt, so the critic's
    actionable retry feedback (correction_note) must not be the last thing
    in the string; the short, redundant-with-the-brief scaffold can afford
    to be there instead."""
    parts = [candidate['art_brief']]
    if correction_note:
        parts.append(f"Previous attempt was rejected for: {correction_note}. Avoid this issue in the new image.")
    parts.append(POSITIVE_SCAFFOLD)
    return " ".join(parts)


# Calibrated against the real google/t5-v1_1-xxl tokenizer offline (not a
# runtime/test dependency - transformers+sentencepiece+protobuf is a heavy,
# network-fetching one-time install, not worth carrying in requirements.txt
# for one build-time check). Measured ratios on realistic brief/scaffold/
# correction-note text ranged 1.375-1.650 tokens/word (full worst-case
# prompt: 147 words -> 226 real tokens, ratio 1.537). 1.6 is above every
# observed per-fragment ratio except the single densest fragment (1.65), so
# it will not meaningfully under-count on prose of this style.
T5_TOKEN_WORD_RATIO = 1.6


def approx_t5_tokens(text: str) -> int:
    return round(len(text.split()) * T5_TOKEN_WORD_RATIO)


def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None, now=None, no_upscale: bool = False,
                            sibling_briefs: list = None) -> dict:
    """Generate a base image for a candidate, then upscale it to a 300-DPI-capable master.
    Always overwrites base_image_url/base_replicate_prediction_id/base_upscale_prediction_id
    on its row (even on retry). If upscaling fails, no write happens - the row is left exactly
    as it was, so the caller's existing per-candidate retry handling picks it up again unchanged.
    `now` is only for test determinism.

    `no_upscale` (Step 4 validation only, docs/2026-07-20-execution-steps-1-4-kickoff.md):
    stops right after the FLUX prediction, skipping real-esrgan and the DPI gate that
    upscaling exists to satisfy - the validation batch is judging raw generation quality,
    and ESRGAN halo is a separate confounding variable (RC-E). Persists the raw FLUX
    output as the base artwork instead of the upscaled one; base_upscale_prediction_id
    stays NULL. Never used by the real pipeline path - a no-upscale row can never reach
    a real Gelato product-create (no 300-DPI master exists for it).

    `sibling_briefs` (round-2, FM-5 diversity fix): brief texts already written earlier
    in the same batch run - see run_generate_cycle. Only used when a brief is actually
    computed here (a retry with a stored art_brief never calls the writer again)."""
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")

    candidate = dict(row)
    if not candidate.get("art_brief"):
        # S4-b: one Claude text call per candidate, computed once and persisted -
        # a retry (correction_note set) reuses the same brief, it only changes
        # what FLUX is told to fix, not the underlying visual concept.
        brief_kwargs = {"sibling_briefs": sibling_briefs} if sibling_briefs else {}
        candidate["art_brief"] = art_brief.generate_art_brief(candidate, **brief_kwargs)
        conn.execute(
            "UPDATE candidates SET art_brief = ? WHERE id = ?",
            (candidate["art_brief"], candidate_id),
        )
        conn.commit()

    prompt = build_prompt(candidate, correction_note=correction_note)
    generated = replicate_client.generate_image(prompt, api_token=api_token)

    if no_upscale:
        raw = http.fetch_bytes(generated["image_url"])
        artwork = artwork_store.persist_base_artwork(candidate_id, raw)
        timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
        conn.execute(
            """
            UPDATE candidates
            SET base_image_url = ?, base_image_local_path = ?, base_image_sha256 = ?,
                base_replicate_delivery_url = ?, base_replicate_prediction_id = ?,
                base_upscale_prediction_id = NULL, status = 'generating', updated_at = ?
            WHERE id = ?
            """,
            (
                artwork["durable_url"], artwork["local_path"], artwork["sha256"],
                generated["image_url"], generated["prediction_id"],
                timestamp, candidate_id,
            ),
        )
        conn.commit()
        return {
            "image_url": artwork["durable_url"],
            "prediction_id": generated["prediction_id"],
            "upscale_prediction_id": None,
            "art_brief": candidate["art_brief"],
        }

    upscaled = replicate_client.upscale_image(generated["image_url"], api_token=api_token)

    raw = http.fetch_bytes(upscaled["image_url"])
    artwork = artwork_store.persist_base_artwork(candidate_id, raw)

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        """
        UPDATE candidates
        SET base_image_url = ?, base_image_local_path = ?, base_image_sha256 = ?,
            base_replicate_delivery_url = ?, base_replicate_prediction_id = ?,
            base_upscale_prediction_id = ?, status = 'generating', updated_at = ?
        WHERE id = ?
        """,
        (
            artwork["durable_url"], artwork["local_path"], artwork["sha256"],
            upscaled["image_url"], generated["prediction_id"], upscaled["prediction_id"],
            timestamp, candidate_id,
        ),
    )
    conn.commit()
    return {
        "image_url": artwork["durable_url"],
        "prediction_id": generated["prediction_id"],
        "upscale_prediction_id": upscaled["prediction_id"],
        "art_brief": candidate["art_brief"],
    }


def run_generate_cycle(conn, *, api_token: str = None, now=None) -> list[int]:
    """Round-2 (FM-5): threads the briefs already written earlier in this same batch
    run into each subsequent generate_for_candidate call as sibling_briefs, so the
    brief writer sees its siblings and picks a distinct palette/device/focal-subject
    instead of the whole batch herding toward the same choices."""
    pending_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM candidates WHERE status = 'pending' ORDER BY id"
        ).fetchall()
    ]
    processed_ids = []
    sibling_briefs = []
    for candidate_id in pending_ids:
        try:
            result = generate_for_candidate(
                conn, candidate_id, api_token=api_token, now=now,
                sibling_briefs=list(sibling_briefs),
            )
        except Exception as exc:
            print(f"generate_for_candidate failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
        if result.get("art_brief"):
            sibling_briefs.append(result["art_brief"])
    return processed_ids
