import re

import pipeline.anthropic_client as anthropic_client

# The niche string is a *scene* leak vector - it can come from a hardcoded
# research.py template, an LLM's free-text trend research, or a raw Telegram
# /research topic, and any of those can carry "wall poster" / "wall art" /
# "print" as a product-container word. Stripped here, once, before the niche
# is fed into the brief-writing prompt, as belt-and-suspenders insurance on
# top of the brief-writing instructions themselves (an LLM's own filtering
# of its input isn't guaranteed the way a regex strip is). Moved here from
# generate.py in the S4-b/S4-c rework - generate.py no longer sees the raw
# niche at all, only this module's art_brief output.
SCENE_TOKENS = sorted(
    ("wall poster", "wall art", "wall décor", "wall decor", "framed poster", "poster", "print"),
    key=len, reverse=True,
)


def sanitize_niche(niche: str) -> str:
    result = niche
    for token in SCENE_TOKENS:
        result = re.sub(re.escape(token), "", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip(" -,")

# S4-b (docs/2026-07-20-remediation-plan-consolidated.md): FLUX was trained on
# descriptive natural-language captions of one concrete image, not Etsy SEO
# keywords - so before an image-generation prompt is built, one cheap Claude
# text call turns the raw research niche into a concrete visual brief. The
# hard no-go list lives HERE, not in the image prompt: a text LLM reliably
# honors "don't reference named artists" as an instruction, but FLUX has no
# negative-prompt channel, so the image model must never see negations
# (CLAUDE.md hard constraint + generate.py's positive-only scaffold).
#
# Mandatory brief fields, from the S4-a failure taxonomy + Etsy bestseller
# trait study (docs/2026-07-20-s4a-failure-taxonomy.md):
#   1. one concrete subject in a NAMED art idiom (not generic "minimalist plant")
#   2. a density/coverage clause - the single biggest lever (4 of 5 non-good
#      baseline masters failed on low subject coverage/sparseness)
#   3. mark boldness (never unqualified "line art")
#   4. a ground, optionally with a backdrop shape
#   5. 2-4 named accent colors from one consistent palette family
ART_BRIEF_PROMPT_TEMPLATE = """You are writing a visual art brief for an AI image generator (FLUX.1), for a flat 2D print-on-demand poster design. Turn this Etsy research signal into a concrete visual brief for ONE piece of artwork.

Niche/keyword: {niche}
Trend rationale: {trend_source}

Write a single positive, natural-language visual brief of at most 60 words describing ONE concrete image. Do not write a list, do not use headings - write flowing descriptive prose, the way an artist would describe a specific painting they are about to make. It MUST include, in positive language only (never phrase anything as an instruction not to do something):

1. One concrete subject rendered in a NAMED art idiom (e.g. "mid-century modern botanical", "Bauhaus", "Japanese woodblock", "vintage herbarium", "Matisse cutout" - never a generic phrase like "minimalist plant").
2. A density/coverage clause such as "dense full-frame composition" or "filling the frame edge to edge" - the subject must fill most of the frame, not float in empty space.
3. Mark boldness: "bold filled shapes" or "confident medium-weight lines" - never unqualified "line art" or "hairline strokes".
4. A ground: a warm cream, beige, or textured background, optionally anchored by a backdrop shape like a colored circle or arch.
5. 2 to 4 named accent colors, drawn from exactly one of these two families - neutral (sage, olive, terracotta, dusty pink) or saturated retro (burnt orange, teal, mustard, deep green) - do not mix the two families.

Also apply these rules, expressed only through what you choose to write (the image model will never see this instruction, so do not mention avoidance in your output): never reference a named artist's style, never describe a recognizable character, franchise, or logo, never imply celebrity likeness, and never describe the piece as hand-painted or one-of-a-kind original - it is a print reproduction.

Reply with ONLY the brief text. No preamble, no quotation marks, no markdown, no labels."""


def build_brief_prompt(candidate: dict) -> str:
    return ART_BRIEF_PROMPT_TEMPLATE.format(
        niche=sanitize_niche(candidate["niche"]),
        trend_source=candidate.get("trend_source") or "no trend data available",
    )


def generate_art_brief(candidate: dict, *, api_key: str = None) -> str:
    """One Haiku-class Anthropic text call turning a candidate's raw research
    niche into a <=60-word positive visual brief. Pure function - does not
    touch the DB; callers persist the result to candidates.art_brief."""
    prompt = build_brief_prompt(candidate)
    result = anthropic_client.complete(prompt, api_key=api_key, max_tokens=200)
    return result["text"].strip()
