import re

import pipeline.anthropic_client as anthropic_client

# R2-c (docs/2026-07-21-generation-quality-round2-plan.md): bumped whenever
# ART_BRIEF_PROMPT_TEMPLATE's text changes, so generation_attempts rows can
# be diffed round-N vs round-(N-1). No prior versioning existed for this
# template, so "v1" is the baseline, not a re-numbering of something earlier.
BRIEF_TEMPLATE_VERSION = "v1"

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
# trait study (docs/2026-07-20-s4a-failure-taxonomy.md), reworked round-2
# (docs/2026-07-21-generation-quality-round2-plan.md sec 3, R2-a) against the
# new failure taxonomy the better S4-a batch exposed:
#   1. one concrete subject in a NAMED art idiom (not generic "minimalist plant")
#   2. a density/coverage clause - the single biggest lever (4 of 5 non-good
#      baseline masters failed on low subject coverage/sparseness)
#   3. focal hierarchy (NEW, fixes FM-2) - one named primary focal subject, plus
#      a rule that any enclosed negative-space opening needs a real occupant,
#      never an abstract floating orb (the owner's own fix on masters 5/6/14)
#   4. mark boldness as a qualifier of the idiom's own medium, never a
#      replacement for it (fixes FM-3 medium drift, e.g. 7's line art
#      rendering as filled shapes)
#   5. a ground, with a backdrop shape demoted to a small-subject-only device
#      from a wide menu, never the default (fixes FM-1 backdrop-circle
#      overuse - 8 of 10 round-1 briefs used one)
#   6. 2-4 named accent colors from one consistent palette family
# Also: an optional sibling_briefs diversity nudge (fixes FM-5 batch
# monotony) and a portrait-landscape foreground-anchor stopgap (cheap half of
# FM-4 - see generate_art_brief's docstring for what's deliberately NOT done).
ART_BRIEF_PROMPT_TEMPLATE = """You are writing a visual art brief for an AI image generator (FLUX.1), for a flat 2D print-on-demand poster design. Turn this Etsy research signal into a concrete visual brief for ONE piece of artwork.

Niche/keyword: {niche}
Trend rationale: {trend_source}

Write a single positive, natural-language visual brief of at most 60 words (up to 75 words only if the focal-hierarchy field needs the room) describing ONE concrete image. Do not write a list, do not use headings - write flowing descriptive prose, the way an artist would describe a specific painting they are about to make. It MUST include, in positive language only (never phrase anything as an instruction not to do something):

1. One concrete subject rendered in a NAMED art idiom (e.g. "mid-century modern botanical", "Bauhaus", "Japanese woodblock", "vintage herbarium", "Matisse cutout" - never a generic phrase like "minimalist plant").
2. A density/coverage clause such as "dense full-frame composition" or "filling the frame edge to edge" - the subject must fill most of the frame, not float in empty space.
3. Focal hierarchy: name ONE primary focal subject and state where it sits (e.g. centered, lower third, nested in the foliage). If the composition creates an enclosed opening or channel of negative space, that opening must either hold a small secondary occupant fitted to the idiom (a butterfly, ladybug, dragonfly, single bloom, or sun/moon disc) or the composition must close over it entirely - an abstract floating shape is never the occupant.
4. Mark boldness as a qualifier of the idiom's own stated medium, never a replacement for it: a line-art idiom stays confident medium-weight lines, a filled-shape idiom stays bold filled shapes - never let boldness language turn a thin-line medium into filled shapes.
5. A ground: a warm cream, beige, or textured background. A backdrop shape is a deliberate anchoring device for a SMALL, single-motif subject only - dense full-frame compositions use none. When one is used, pick from a wide menu (arch, wash, band, sun disc behind the subject, torn-paper edge, or another era-appropriate device - not just a circle), and it must sit behind and touching the subject, never floating in leftover negative space.
6. 2 to 4 named accent colors, drawn from exactly one of these two families - neutral (sage, olive, terracotta, dusty pink) or saturated retro (burnt orange, teal, mustard, deep green) - do not mix the two families.

If the described scene reads as landscape-native (a wide vista, a horizon-driven view), name a foreground anchor subject that fills the 2:3 portrait frame instead of composing it as a wide horizontal scene.

Also apply these rules, expressed only through what you choose to write (the image model will never see this instruction, so do not mention avoidance in your output): never reference a named artist's style, never describe a recognizable character, franchise, or logo, never imply celebrity likeness, and never describe the piece as hand-painted or one-of-a-kind original - it is a print reproduction.{sibling_note}

Reply with ONLY the brief text. No preamble, no quotation marks, no markdown, no labels."""


def build_brief_prompt(candidate: dict, *, sibling_briefs: list = None) -> str:
    sibling_note = ""
    if sibling_briefs:
        sibling_note = (
            "\n\nBriefs already written earlier in this batch (for diversity only - do not "
            "repeat their palette family, backdrop device, or focal-subject type): "
            + " | ".join(sibling_briefs)
            + ". Choose a palette family, composition device, and focal-subject type distinct "
            "from all of these; across a batch both accent-color families above should appear."
        )
    return ART_BRIEF_PROMPT_TEMPLATE.format(
        niche=sanitize_niche(candidate["niche"]),
        trend_source=candidate.get("trend_source") or "no trend data available",
        sibling_note=sibling_note,
    )


def generate_art_brief(candidate: dict, *, api_key: str = None, sibling_briefs: list = None) -> str:
    """One Haiku-class Anthropic text call turning a candidate's raw research
    niche into a <=60(-75)-word positive visual brief. Pure function - does
    not touch the DB; callers persist the result to candidates.art_brief.

    `sibling_briefs` (round-2, fixes FM-5 batch monotony): the brief texts
    already written earlier in the same batch run, passed by
    generate.run_generate_cycle so the writer picks a distinct palette/
    device/focal-subject instead of herding toward the same choices. Empty/
    None for the first candidate in a batch (or any standalone call).

    Deliberately NOT done here (round-2 plan sec 3, R2-a-5 / open question 2):
    no orientation-selection logic, template plumbing, or aspect-ratio code -
    the landscape-native case only gets a brief-wording nudge (see the
    template's foreground-anchor instruction); the full landscape path is
    out of scope, deferred by owner decision."""
    prompt = build_brief_prompt(candidate, sibling_briefs=sibling_briefs)
    result = anthropic_client.complete(
        prompt, api_key=api_key, max_tokens=200, model=anthropic_client.HAIKU_MODEL
    )
    return result["text"].strip()
