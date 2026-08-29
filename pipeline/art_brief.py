import re

import pipeline.anthropic_client as anthropic_client
import pipeline.brief_lint as brief_lint

# R2-c (docs/2026-07-21-generation-quality-round2-plan.md): bumped whenever
# ART_BRIEF_PROMPT_TEMPLATE's text changes, so generation_attempts rows can
# be diffed round-N vs round-(N-1). No prior versioning existed for this
# template, so "v1" is the baseline, not a re-numbering of something earlier.
# R3-a (docs/2026-07-21-generation-quality-round3-plan.md sec 3): bumped to
# "v2" for the round-3 template rewrite (occupant conditionality, integration
# vocabulary, negative-space wording hygiene, bottom-edge grounding,
# backdrop-device rebalance, conditional density/sparse idiom).
# GL-63 (#90): bumped to "v3" - the closing instruction now permits one
# trailing `OCCUPANT:` declaration line, so a reply written under v2 has a
# different expected shape than one written under v3.
# GL-10c/1 (#207): bumped to "v4" - two more trailing declaration lines
# (COLOUR, IDIOM) so dominant_colour/named_idiom can be threaded to draft
# time (spec 2026-08-07-gl10b-listing-copy-spec.md §1.3 option B) without
# parsing them back out of the brief prose.
BRIEF_TEMPLATE_VERSION = "v4"

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
# (docs/2026-07-21-generation-quality-round2-plan.md sec 3, R2-a), then
# reworked again round-3 (docs/2026-07-21-generation-quality-round3-plan.md
# sec 2/3, R3-a) against the failure taxonomy round 2's batch exposed
# (FM-7..FM-13 - secondary-subject integration, not "is there one"):
#   1. one concrete subject, named FIRST, in a NAMED art idiom (not generic
#      "minimalist plant") - subject-first ordering, see research note below.
#   2. a CONDITIONAL density clause (fixes FM-13): dense full-frame OR one
#      large dominant subject holding generous, intentional empty space - a
#      legitimate sparse idiom, not just the dense mode. Invalid combination:
#      a small subject adrift in a mostly empty frame.
#   3. focal hierarchy + occupant conditionality (fixes FM-11) + integration
#      vocabulary (fixes FM-7) + negative-space wording hygiene (fixes FM-8):
#      name the primary subject's scale in positive terms, err bigger; a
#      secondary occupant is only used when a genuine enclosed opening exists
#      AND an occupant improves it - "closes over it" / "no secondary
#      subject" are equally valid choices, never "always add a creature".
#      When used: physical-contact verbs bind it to the subject (never
#      spatial prepositions), anatomically-complete/symmetric wording, a
#      dynamic pose (in flight, mid-crawl) when it has no natural perch, and
#      its position is described relative to surrounding SUBJECT MATTER
#      (stems, fronds, blooms) - never the shape of the space around it
#      (round 2's "opening/channel" wording became drawn geometry in the
#      render, e.g. a literal triangle/rectangle outline).
#   4. mark boldness as a qualifier of the idiom's own medium, never a
#      replacement for it (fixes FM-3 medium drift, e.g. 7's line art
#      rendering as filled shapes) - unchanged from round 2.
#   5. a ground, with a backdrop device rebalanced (fixes FM-10) from
#      round-2's "small-subject-only" demotion (which, combined with
#      mandatory density, drove it to 0/10 use) to a positive menu device
#      appropriate behind a large dominant subject too - still not the
#      default, still not forbidden, deliberately used for SOME designs.
#   6. edge contact (fixes FM-9): stem/bouquet/herbarium subjects state how
#      the composition meets the lower frame edge, or more generally where
#      it touches the frame's edges - schnell reverts to a floating cut
#      specimen with margins unless told otherwise.
#   7. 2-4 named accent colors from one consistent palette family.
# Also: sibling_briefs diversity nudge (fixes FM-5 batch monotony), now with
# a backdrop-device FLOOR as well as a cap (fixes FM-10 at the batch level -
# round 2's cap-only nudge was one of three converging causes of extinction),
# and the round-2 portrait-landscape foreground-anchor stopgap (unchanged).
#
# Prompt-craft research (2026-07-21, web pass, sources in the R3-a task
# report): (1) FLUX weights early tokens more heavily - the subject named
# first in the prompt gets stronger attention than one buried after
# background/style clauses, confirming the seed hypothesis "subject first
# with explicit scale". (2) T5 wants natural-language sentences, not
# comma-separated tag lists, and very long prompts (200+ words) get
# internally summarized/compressed - small secondary-object detail is
# exactly what drops first, which is why field 3 below asks for one
# concrete contact clause rather than several stacked descriptors. (3)
# FLUX/schnell prompt-craft guides converge on "1-2 style anchors, more
# dilutes adherence" and schnell's 4-step distillation is tuned for exactly
# that step count (more steps ~ no better, sometimes worse) - both support
# "fewer stacked constraints beat more" at generation time. No source
# directly benchmarked contact-verb vs. preposition phrasing for FLUX
# specifically; the field-3 rule below is this plan's best inference from
# (1)+(2) (concrete action/contact language reads as one grounded scene
# clause, not a compressible spatial relation) rather than a confirmed
# finding - flagged as such, not overclaimed.
ART_BRIEF_PROMPT_TEMPLATE = """You are writing a visual art brief for an AI image generator (FLUX.1), for a flat 2D print-on-demand poster design. Turn this Etsy research signal into a concrete visual brief for ONE piece of artwork.

Niche/keyword: {niche}
Trend rationale: {trend_source}

Write a single positive, natural-language visual brief of at most 60 words (up to 75 words only if the focal-hierarchy field needs the room) describing ONE concrete image. Do not write a list, do not use headings - write flowing descriptive prose, the way an artist would describe a specific painting they are about to make, naming the primary subject in the opening words. It MUST include, in positive language only (never phrase anything as an instruction not to do something):

1. One concrete subject, named FIRST, rendered in a NAMED art idiom (e.g. "mid-century modern botanical", "Bauhaus", "Japanese woodblock", "vintage herbarium", "Matisse cutout" - never a generic phrase like "minimalist plant").
2. A density clause: EITHER a dense full-frame composition filling the frame edge to edge, OR one large dominant subject that fills most of the frame while holding generous, intentional empty space around it - a deliberate sparse idiom, not a flaw. Never describe a small subject adrift in a mostly empty frame.
3. Focal hierarchy: name the primary focal subject's scale in positive terms (e.g. "large enough to read across a room", "spanning a third of the frame width" - when in doubt, go bigger) and where it sits (centered, lower third, nested in the foliage). If the composition has a genuine enclosed opening in the primary subject, a small secondary occupant fitted to the idiom (a butterfly, ladybug, dragonfly, bird, single bloom, or sun/moon disc) is one valid, deliberate choice - use it ONLY when it genuinely improves the composition. When used, describe it touching the surrounding subject matter in physical-contact language (e.g. "six legs gripping the stem", "wings brushing the leaf edge"), with both wings or limbs spread symmetrically and anatomically complete; if it has no natural perch, give it a dynamic pose (in flight, mid-glide, mid-crawl) instead of a static perched one. Describe its position relative to the surrounding stems, fronds, or blooms only - never the shape or geometry of the opening itself (never call it a triangle, rectangle, square, or circle of space). Equally valid, and just as deliberate a choice: the composition closes over the opening entirely, or the subject has no secondary occupant at all.
4. Mark boldness as a qualifier of the idiom's own stated medium, never a replacement for it: a line-art idiom stays confident medium-weight lines, a filled-shape idiom stays bold filled shapes - never let boldness language turn a thin-line medium into filled shapes.
5. A ground: a warm cream, beige, or textured background. A backdrop device (an arch, wash, band, sun disc, torn-paper edge, or another era-appropriate device - not just a circle) sitting behind and touching the primary subject is a deliberate design choice for SOME designs - appropriate behind a large dominant subject as well as a small single-motif one, not the default and not forbidden. When used, it must sit behind and touch the subject, never float in leftover negative space.
6. Edge contact: for stem, bouquet, or herbarium-style subjects, state how the composition meets the lower frame edge (e.g. "stems running off the bottom edge of the frame") - more generally, name where the composition touches the frame's edges rather than leaving unstated margins.
7. 2 to 4 named accent colors, drawn from exactly one of these two families - neutral (sage, olive, terracotta, dusty pink) or saturated retro (burnt orange, teal, mustard, deep green) - do not mix the two families.

If the described scene reads as landscape-native (a wide vista, a horizon-driven view), name a foreground anchor subject that fills the 2:3 portrait frame instead of composing it as a wide horizontal scene.

Also apply these rules, expressed only through what you choose to write (the image model will never see this instruction, so do not mention avoidance in your output): never reference a named artist's style, never describe a recognizable character, franchise, or logo, never imply celebrity likeness, and never describe the piece as hand-painted or one-of-a-kind original - it is a print reproduction.{sibling_note}

Reply with ONLY the brief text. No preamble, no quotation marks, no markdown, no labels. After the brief text, on their own trailing lines (any order), declare: whether it uses a secondary occupant, write exactly "OCCUPANT: yes" if it does, or "OCCUPANT: none" if it does not; the single dominant colour word from the palette above, as "COLOUR: <word>"; and the named art idiom from rule 1, as "IDIOM: <name>"."""


# R3-a (FM-10, docs/2026-07-21-generation-quality-round3-plan.md sec 3):
# round 2's sibling note only capped backdrop-device repetition ("do not
# repeat their ... backdrop device") - one of three converging causes that
# drove backdrop-device use from 8/10 to 0/10. This adds a FLOOR alongside
# the cap, using brief_lint's own BACKDROP_DEVICES vocabulary so the batch-
# level nudge and the batch-level lint agree on what counts as one.
_SIBLING_BACKDROP_CAP = 2


def _sibling_backdrop_device_count(sibling_briefs: list) -> int:
    return sum(
        1 for text in sibling_briefs
        if any(device in text.lower() for device in brief_lint.BACKDROP_DEVICES)
    )


def build_brief_prompt(candidate: dict, *, sibling_briefs: list = None) -> str:
    sibling_note = ""
    if sibling_briefs:
        backdrop_count = _sibling_backdrop_device_count(sibling_briefs)
        if backdrop_count == 0:
            backdrop_guidance = (
                " None of the earlier briefs in this batch used a backdrop device - "
                "strongly consider one here."
            )
        elif backdrop_count >= _SIBLING_BACKDROP_CAP:
            backdrop_guidance = (
                " Two or more earlier briefs in this batch already used a backdrop "
                "device - use none here."
            )
        else:
            backdrop_guidance = ""
        sibling_note = (
            "\n\nBriefs already written earlier in this batch (for diversity only - do not "
            "repeat their palette family, backdrop device, or focal-subject type): "
            + " | ".join(sibling_briefs)
            + ". Choose a palette family, composition device, and focal-subject type distinct "
            "from all of these; across a batch both accent-color families above should appear."
            + backdrop_guidance
        )
    return ART_BRIEF_PROMPT_TEMPLATE.format(
        niche=sanitize_niche(candidate["niche"]),
        trend_source=candidate.get("trend_source") or "no trend data available",
        sibling_note=sibling_note,
    )


# GL-63 (#90): the model declares occupant-use on its own trailing line
# rather than the brief prose being scanned for a hardcoded creature-noun
# vocabulary (rejected by the owner, 2026-08-14 comment on issue #90 - a
# vocabulary list drifts with phrasing and re-introduces the exact subject
# naming this row exists to avoid). "yes"/"none" is an allowlist, not a
# noun - anything else (including a missing line) is undeclared so a typo
# can't silently disable the batch-level cap in brief_lint.
#
# GL-10c/1 (#207): generalised to peel any of a known set of trailing
# `KEY: value` lines, order-independent, instead of one occupant-only
# regex - COLOUR/IDIOM need the same "reply degrades gracefully" tolerance
# split_occupant_declaration already has. The key set is fixed (not fully
# generic) so an unrelated prose line ending in "Something: like this" is
# never mistaken for a declaration.
_KNOWN_DECLARATION_KEYS = ("occupant", "colour", "idiom")
_DECLARATION_LINE_RE = re.compile(
    r"^\s*(" + "|".join(_KNOWN_DECLARATION_KEYS) + r")\s*:\s*(.*)$", re.IGNORECASE
)


def split_trailing_declarations(raw: str) -> tuple:
    """Peels every trailing `KEY: value` declaration line off the end of a
    model reply (KEY one of _KNOWN_DECLARATION_KEYS, any order), returning
    (prose, {key_lower: value}). Stops at the first trailing line that
    isn't a declaration, so prose is never eaten past that point."""
    lines = raw.rstrip().split("\n")
    declarations = {}
    while lines:
        match = _DECLARATION_LINE_RE.match(lines[-1].strip())
        if not match:
            break
        key, value = match.group(1).lower(), match.group(2).strip()
        declarations[key] = value
        lines.pop()
    return "\n".join(lines).strip(), declarations


def split_occupant_declaration(raw: str) -> tuple:
    """Splits a model reply into (prose, occupant), where occupant is one of
    "yes", "none", or "undeclared". Tolerates a reply with no trailing
    OCCUPANT line (returns the whole reply, "undeclared") so a model that
    ignores the instruction degrades to pre-GL-63 behaviour instead of
    corrupting the brief. Thin wrapper over split_trailing_declarations so
    this function's existing callers/tests stay unchanged."""
    prose, declarations = split_trailing_declarations(raw)
    value = declarations.get("occupant")
    if value is None:
        return raw.strip(), "undeclared"
    occupant = value.lower() if value.lower() in ("yes", "none") else "undeclared"
    return prose, occupant


def generate_art_brief(candidate: dict, *, api_key: str = None, sibling_briefs: list = None) -> dict:
    """One Haiku-class Anthropic text call turning a candidate's raw research
    niche into a <=60(-75)-word positive visual brief. Pure function - does
    not touch the DB; callers persist the result to candidates.art_brief
    (dominant_colour/named_idiom too, GL-10c/1 #207).
    Returns {"art_brief": str, "occupant": "yes"|"none"|"undeclared",
    "dominant_colour": str|None, "named_idiom": str|None} - all three
    declarations are parsed off the reply's trailing lines and never appear
    in the returned art_brief prose. colour/idiom are free text, not an
    allowlist like occupant: an absent or empty declaration degrades to
    None rather than a guessed value.

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
        # GL-60: 200 was sized for the <=60(-75)-word brief alone and left no headroom -
        # candidate 81 hit TruncatedResponseError live and burned a retry. 75 words is
        # ~110 tokens; 600 covers the long tail without licensing a rambling brief (the
        # word cap is enforced by the prompt and brief_lint, not by max_tokens).
        prompt, api_key=api_key, max_tokens=600, model=anthropic_client.HAIKU_MODEL
    )
    prose, declarations = split_trailing_declarations(result["text"].strip())
    occupant_value = declarations.get("occupant")
    occupant = (
        occupant_value.lower() if occupant_value and occupant_value.lower() in ("yes", "none")
        else "undeclared"
    )
    return {
        "art_brief": prose,
        "occupant": occupant,
        "dominant_colour": declarations.get("colour") or None,
        "named_idiom": declarations.get("idiom") or None,
    }
