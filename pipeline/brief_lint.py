"""Shared brief-lint validator (R2-e, then R3-c,
docs/2026-07-21-generation-quality-round3-plan.md section 3). Validates a
BATCH of art briefs against:
  (a) the mandatory-field list, checked heuristically against the brief text
      (errors - hard-fail assert_batch_valid).
  (b) batch-diversity rules on palette family / backdrop device, scaled to
      batch size (errors).
  (c) FM-8: geometric shape-words used to describe a gap/opening (error -
      FLUX renders described negative-space geometry as literal drawn lines).
  (d) FM-9/FM-10: bottom-edge grounding on stem-native briefs, and the
      backdrop-device floor/ceiling at batch level (warnings only - these
      protect intent but a miss shouldn't hard-fail a human-curated batch).

Intended call sites (both mode A and mode B run the SAME error-level lint -
a shared gate is the point):
  - Mode A: `generate.generate_for_candidate` runs `lint_batch` (log-only,
    via logging.warning - mode A is the autonomous cron path, a wording/
    diversity miss shouldn't abort a live batch, only surface it) on the
    cumulative sibling briefs + the newly written one, right after each
    art_brief.generate_art_brief() call and before the Replicate spend.
  - Mode B: pipeline/seed_candidates.py's seed_candidates_from_briefs calls
    `assert_batch_valid` (hard-fails, all-or-nothing insert) since that's a
    human-gated one-shot ingest, not a scheduled batch. `pipeline/seed_mode_b.py`
    (R3-d CLI) also surfaces `lint_batch_warnings` in its preview, but only
    `assert_batch_valid`'s errors ever block `--commit`.

R3-c fan-in note (vocabulary built against the round-3 plan's field list,
NOT yet reconciled against Agent A's final ART_BRIEF_PROMPT_TEMPLATE v3 -
that reconciliation happens at fan-in per the plan's parallelization
section). Specifically guessed, flag for reconciliation:
  - BOLDNESS_PATTERNS below are widened proximity regexes, not lifted
    verbatim from A's shipped field 3 wording - confirm A's actual phrasing
    still matches after the rewrite.
  - STEM_NATIVE_KEYWORDS / GROUNDING_PHRASES (FM-9) and BACKDROP_DEVICES
    (FM-10, now includes "badge") are this file's own vocabulary, built from
    the plan's §2/§3 prose and docs/2026-07-21-round3-traits-delta-memo.md,
    not from A's template text directly.
  - The palette diversity-cap fraction was corrected from the plan's stated
    0.4 to 0.5 for palette (see PALETTE_CAP_FRACTION comment below) - the
    literal 0.4 cannot admit the plan's own named acceptance case (a 5/5
    split on N=10 briefs). Backdrop-device fraction (0.3) is used as
    written; it has no equivalent contradiction.
"""
import math
import re

MANDATORY_FIELDS = (
    "focal-hierarchy subject",
    "backdrop-device-or-none",
    "medium-consistent boldness",
    "palette",
    "niche",
)

# R3-c fix (a): boldness was an exact-substring match on 3 fixed phrases,
# which failed a valid brief on wording alone (round-2 false positive).
# Widened to word FAMILIES checked within a sliding word-window (order-
# agnostic, tolerant of hyphenation/plural variants and filler words in
# between) rather than one fixed phrase. Still hard-fails a brief with NO
# boldness language at all - protects intent, per the task's own "downgrade
# only if simpler" framing; widening was the simpler, less-lossy fix here.
BOLDNESS_FAMILIES = (
    {"bold", "filled"},
    {"bold", "shapes"},
    {"bold", "shape"},
    {"bold", "graphic"},
    {"bold", "forms"},
    {"bold", "form"},
    {"medium", "weight"},  # covers "medium-weight lines" and "confident medium-weight ..."
)
_BOLDNESS_WINDOW = 6


def _words(text: str) -> list:
    return re.findall(r"[a-z']+", text.lower())


def _family_in_window(words: list, family: set, window: int) -> bool:
    for i in range(len(words)):
        if family.issubset(words[i : i + window]):
            return True
    return False

PALETTE_FAMILIES = {
    "neutral": ("sage", "olive", "terracotta", "dusty pink"),
    "saturated_retro": ("burnt orange", "teal", "mustard", "deep green"),
}

# "Backdrop device" per FM-1/FM-10: a colored circle/arch/etc anchoring the
# subject. A brief naming none of these is a valid "-or-none" brief (dense
# full-frame compositions use none) - absence is not a lint error, only
# tracked for the batch-diversity rule and the FM-10 floor/ceiling check.
# "badge" added in round 3 (backdrop-device rebalance vocabulary).
BACKDROP_DEVICES = (
    "circle", "arch", "wash", "band", "disc", "vignette", "halo",
    "torn-paper", "torn paper", "badge",
)

# R3-c fix (b): fixed caps of 2 couldn't mathematically admit the batch's
# own IDEAL split (e.g. 5/5 palette on a 10-brief batch). Caps now scale
# with N. Palette fraction corrected to 0.5 (not the plan's literal 0.4,
# which yields cap=4 at N=10 and would still reject a 5/5 split) so the
# formula actually satisfies the acceptance case it's named for; device
# fraction (0.3) used as specified since no equivalent 5/5-style case
# applies to it.
PALETTE_CAP_FRACTION = 0.5
DEVICE_CAP_FRACTION = 0.3


def _diversity_cap(n: int, fraction: float) -> int:
    return max(2, math.ceil(n * fraction))


def _detect_backdrop_device(text: str) -> str:
    lowered = text.lower()
    for device in BACKDROP_DEVICES:
        if device in lowered:
            return device
    return "none"


def _detect_palette_family(text: str) -> str:
    lowered = text.lower()
    for family, terms in PALETTE_FAMILIES.items():
        if any(term in lowered for term in terms):
            return family
    return "unknown"


def _has_boldness(text: str) -> bool:
    words = _words(text)
    return any(_family_in_window(words, family, _BOLDNESS_WINDOW) for family in BOLDNESS_FAMILIES)


# FM-8: shape-words used to describe a GAP/OPENING/negative space get
# rendered by FLUX as literal drawn lines/shapes. "circle" is deliberately
# excluded - sun/moon discs are legitimate described OBJECTS, not a gap
# shape, and "circle backdrop" is valid backdrop-device vocabulary (see
# BACKDROP_DEVICES above). Only triangle/rectangle/square family words
# count, and only when they sit near a gap/opening/space word.
FM8_SHAPE_WORDS = ("triangle", "triangular", "rectangle", "rectangular", "square")
FM8_GAP_WORDS = ("gap", "opening", "space", "channel")


def _has_shape_word_for_gap(text: str) -> bool:
    words = _words(text)
    for i, word in enumerate(words):
        if word not in FM8_SHAPE_WORDS:
            continue
        window = words[max(0, i - 4) : i + 5]
        if any(gap_word in window for gap_word in FM8_GAP_WORDS):
            return True
    return False


# FM-9: stem/bouquet/herbarium-style niches need an explicit bottom-edge (or
# even-margin, for the deliberate cut-specimen-float idiom) grounding clause,
# or schnell reverts to a lopsided blank band. Warning-level: this is a
# quality nudge, not a hard mandatory field.
STEM_NATIVE_KEYWORDS = ("stem", "stems", "bouquet", "herbarium", "wildflower", "meadow")
GROUNDING_PHRASES = (
    "bottom edge", "rooted at", "running off", "run off the bottom",
    "lower edge", "even margins",
)


def _is_stem_native(niche: str, text: str) -> bool:
    lowered = f"{niche} {text}".lower()
    return any(kw in lowered for kw in STEM_NATIVE_KEYWORDS)


def _has_grounding_clause(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in GROUNDING_PHRASES)


def lint_brief(brief: dict) -> list[str]:
    """Per-brief mandatory-field + FM-8 checks (errors). `brief` needs at
    least {'niche': str, 'art_brief': str}; extra keys (mode B's
    trend_source, go_hold_kill_rationale) are ignored. Returns a list of
    error strings, empty if valid.

    Note: "focal-hierarchy subject" (one primary subject + its position) is
    inherently semantic, not syntactically checkable by regex/keyword - this
    only verifies the brief text is non-trivially non-empty as a floor. Real
    verification of that field needs a model call (out of scope for a sync
    lint function); the pipeline critic (critic_pass.py) is the actual
    enforcement point for focal-subject presence.
    """
    errors = []
    niche = (brief.get("niche") or "").strip()
    text = (brief.get("art_brief") or "").strip()

    if not niche:
        errors.append("missing mandatory field: niche")
    if not text:
        errors.append("missing mandatory field: art_brief text")
        return errors  # nothing else to check against empty text
    if len(text.split()) < 5:
        errors.append("art_brief text too short to plausibly name a focal-hierarchy subject")
    if not _has_boldness(text):
        errors.append("missing mandatory field: medium-consistent boldness (expected a bold-filled/shapes or confident-medium-weight-lines phrase family)")
    if _detect_palette_family(text) == "unknown":
        errors.append("missing mandatory field: palette (no named accent color from either palette family found)")
    if _has_shape_word_for_gap(text):
        errors.append("FM-8: geometric shape-word (triangle/rectangle/square) used to describe a gap/opening/space - describe position relative to the subject matter instead, never the shape of the surrounding emptiness")

    return errors


def lint_brief_warnings(brief: dict) -> list[str]:
    """Per-brief FM-9 warning check. Does not hard-fail assert_batch_valid."""
    warnings = []
    niche = (brief.get("niche") or "").strip()
    text = (brief.get("art_brief") or "").strip()
    if not text:
        return warnings
    if _is_stem_native(niche, text) and not _has_grounding_clause(text):
        warnings.append("FM-9: stem/bouquet/herbarium-style brief has no bottom-edge/grounding clause - schnell tends to leave a lopsided blank band without one")
    return warnings


def lint_batch(briefs: list[dict]) -> list[str]:
    """Per-brief mandatory-field/FM-8 errors + batch-diversity errors. Returns
    a flat list of human-readable error strings, empty if the whole batch is
    valid. This is the function assert_batch_valid hard-fails on."""
    errors = []

    for i, brief in enumerate(briefs):
        for err in lint_brief(brief):
            errors.append(f"brief[{i}] ({brief.get('niche', '?')}): {err}")

    n = len(briefs)
    devices = [_detect_backdrop_device(b.get("art_brief") or "") for b in briefs]
    families = [_detect_palette_family(b.get("art_brief") or "") for b in briefs]

    device_cap = _diversity_cap(n, DEVICE_CAP_FRACTION)
    for device in set(devices):
        if device == "none":
            continue
        count = devices.count(device)
        if count > device_cap:
            errors.append(f"batch diversity: {count} briefs share backdrop device '{device}' (max {device_cap})")

    palette_cap = _diversity_cap(n, PALETTE_CAP_FRACTION)
    for family in set(families):
        if family == "unknown":
            continue
        count = families.count(family)
        if count > palette_cap:
            errors.append(f"batch diversity: {count} briefs share palette family '{family}' (max {palette_cap})")

    return errors


def lint_batch_warnings(briefs: list[dict]) -> list[str]:
    """Batch-level + per-brief WARNINGS (FM-9, FM-10). Never hard-fails
    assert_batch_valid - callers (e.g. pipeline/seed_mode_b.py's preview)
    print these alongside lint_batch's errors but don't block on them."""
    warnings = []

    for i, brief in enumerate(briefs):
        for warn in lint_brief_warnings(brief):
            warnings.append(f"brief[{i}] ({brief.get('niche', '?')}): {warn}")

    n = len(briefs)
    if n >= 6:
        devices = [_detect_backdrop_device(b.get("art_brief") or "") for b in briefs]
        used = sum(1 for d in devices if d != "none")
        if used == 0:
            warnings.append(f"batch FM-10: 0/{n} briefs use a backdrop device - owner ruling: it's a good device that should appear SOMETIMES, not never")
        else:
            ceiling = math.ceil(n * 0.30)
            if used > ceiling:
                warnings.append(f"batch FM-10: {used}/{n} briefs use a backdrop device - exceeds the ~30% ceiling ({ceiling}), risks the round-1 over-use pattern")

    return warnings


def assert_batch_valid(briefs: list[dict]) -> None:
    """Raises ValueError with all lint ERRORS joined, if any. No-op if the
    batch is clean. Warnings (lint_batch_warnings) never raise here."""
    errors = lint_batch(briefs)
    if errors:
        raise ValueError("brief batch failed lint:\n" + "\n".join(errors))
