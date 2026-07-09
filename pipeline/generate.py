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
