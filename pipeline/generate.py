from datetime import datetime, timezone

import pipeline.replicate_client as replicate_client


NICHE_STYLE_SCAFFOLD = (
    "A minimalist botanical/nature wall art print: {niche}. Clean composition, soft "
    "muted natural color palette, print-ready poster art, no text or watermarks."
)

# Hard no-go list per SPEC_v4.10.md section 2 / CLAUDE.md - baked into generation
# prompts as best-effort steering, not a guarantee. The critic pass (future stage)
# is the authoritative compliance gate that checks the rendered image itself.
NO_GO_LIST = (
    "Do not depict any named artist's style, recognizable characters, franchises, or "
    "logos. Do not imply celebrity likeness. Do not claim or resemble hand-painted or "
    "one-of-a-kind original artwork - this is a print reproduction."
)


def build_prompt(candidate: dict, *, correction_note: str = None) -> str:
    prompt = f"{NICHE_STYLE_SCAFFOLD.format(niche=candidate['niche'])} {NO_GO_LIST}"
    if correction_note:
        prompt += f" Previous attempt was rejected for: {correction_note}. Avoid this issue in the new image."
    return prompt


def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None, now=None) -> dict:
    """Generate a base image for a candidate, then upscale it to a 300-DPI-capable master.
    Always overwrites base_image_url/base_replicate_prediction_id/base_upscale_prediction_id
    on its row (even on retry). If upscaling fails, no write happens - the row is left exactly
    as it was, so the caller's existing per-candidate retry handling picks it up again unchanged.
    `now` is only for test determinism."""
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")

    prompt = build_prompt(dict(row), correction_note=correction_note)
    generated = replicate_client.generate_image(prompt, api_token=api_token)
    upscaled = replicate_client.upscale_image(generated["image_url"], api_token=api_token)

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        """
        UPDATE candidates
        SET base_image_url = ?, base_replicate_prediction_id = ?,
            base_upscale_prediction_id = ?, status = 'generating', updated_at = ?
        WHERE id = ?
        """,
        (upscaled["image_url"], generated["prediction_id"], upscaled["prediction_id"], timestamp, candidate_id),
    )
    conn.commit()
    return {
        "image_url": upscaled["image_url"],
        "prediction_id": generated["prediction_id"],
        "upscale_prediction_id": upscaled["prediction_id"],
    }


def run_generate_cycle(conn, *, api_token: str = None, now=None) -> list[int]:
    pending_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM candidates WHERE status = 'pending' ORDER BY id"
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in pending_ids:
        try:
            generate_for_candidate(conn, candidate_id, api_token=api_token, now=now)
        except Exception as exc:
            print(f"generate_for_candidate failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
