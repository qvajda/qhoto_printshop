"""Shared brief-lint validator (R2-e, docs/2026-07-21-generation-quality-round2-plan.md
section 3). Validates a BATCH of art briefs against:
  (a) the R2-a mandatory-field list, checked heuristically against the brief text.
  (b) batch-diversity rules: reject a batch where more than 2 briefs share the
      same backdrop device, or more than 2 share the same palette family.

Intended call sites (both mode A and mode B run the SAME lint - a shared
gate is the point):
  - Mode A: `generate.generate_for_candidate` runs `lint_batch` (log-only,
    via logging.warning - mode A is the autonomous cron path, a wording/
    diversity miss shouldn't abort a live batch, only surface it) on the
    cumulative sibling briefs + the newly written one, right after each
    art_brief.generate_art_brief() call and before the Replicate spend.
  - Mode B: pipeline/seed_candidates.py's seed_candidates_from_briefs calls
    `assert_batch_valid` (hard-fails, all-or-nothing insert) since that's a
    human-gated one-shot ingest, not a scheduled batch.

Reconciled at fan-in against A's final ART_BRIEF_PROMPT_TEMPLATE
(pipeline/art_brief.py): BOLDNESS_TERMS and PALETTE_FAMILIES already match
A's shipped field 4/6 wording verbatim (both agents drew the same vocabulary
from the round-2 plan doc), so no changes were needed. BACKDROP_DEVICES is
intentionally over-inclusive (covers legacy terms like "vignette"/"halo"
alongside A's new menu) - harmless, since it's only used for diversity
counting, never a mandatory-field failure.
"""

MANDATORY_FIELDS = (
    "focal-hierarchy subject",
    "backdrop-device-or-none",
    "medium-consistent boldness",
    "palette",
    "niche",
)

# Vocabulary lifted from art_brief.py's ART_BRIEF_PROMPT_TEMPLATE fields 3-5
# (current, pre-R2-a-rewrite wording) - see fan-in note above.
BOLDNESS_TERMS = ("bold filled", "confident medium-weight", "medium-weight lines")

PALETTE_FAMILIES = {
    "neutral": ("sage", "olive", "terracotta", "dusty pink"),
    "saturated_retro": ("burnt orange", "teal", "mustard", "deep green"),
}

# "Backdrop device" per FM-1: a colored circle/arch/etc anchoring the subject.
# A brief naming none of these is a valid "-or-none" brief (dense full-frame
# compositions use none per R2-a-2) - absence is not a lint error, only
# tracked for the batch-diversity rule below.
BACKDROP_DEVICES = ("circle", "arch", "wash", "band", "disc", "vignette", "halo", "torn-paper", "torn paper")

MAX_BRIEFS_SHARING_DEVICE = 2
MAX_BRIEFS_SHARING_PALETTE = 2


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


def lint_brief(brief: dict) -> list[str]:
    """Per-brief mandatory-field checks. `brief` needs at least
    {'niche': str, 'art_brief': str}; extra keys (mode B's trend_source,
    go_hold_kill_rationale) are ignored. Returns a list of error strings,
    empty if valid.

    Note: "focal-hierarchy subject" (one primary subject + its position) is
    inherently semantic, not syntactically checkable by regex/keyword - this
    only verifies the brief text is non-trivially non-empty as a floor. Real
    verification of that field needs a model call (out of scope for a sync
    lint function); the pipeline critic (critic_pass.py, criterion 4/7 per
    R2-b) is the actual enforcement point for focal-subject presence.
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
    if not any(term in text.lower() for term in BOLDNESS_TERMS):
        errors.append(f"missing mandatory field: medium-consistent boldness (expected one of {BOLDNESS_TERMS})")
    if _detect_palette_family(text) == "unknown":
        errors.append("missing mandatory field: palette (no named accent color from either palette family found)")

    return errors


def lint_batch(briefs: list[dict]) -> list[str]:
    """Per-brief mandatory-field errors + batch-diversity errors. Returns a
    flat list of human-readable error strings, empty if the whole batch is
    valid."""
    errors = []

    for i, brief in enumerate(briefs):
        for err in lint_brief(brief):
            errors.append(f"brief[{i}] ({brief.get('niche', '?')}): {err}")

    devices = [_detect_backdrop_device(b.get("art_brief") or "") for b in briefs]
    families = [_detect_palette_family(b.get("art_brief") or "") for b in briefs]

    for device in set(devices):
        if device == "none":
            continue
        count = devices.count(device)
        if count > MAX_BRIEFS_SHARING_DEVICE:
            errors.append(f"batch diversity: {count} briefs share backdrop device '{device}' (max {MAX_BRIEFS_SHARING_DEVICE})")

    for family in set(families):
        if family == "unknown":
            continue
        count = families.count(family)
        if count > MAX_BRIEFS_SHARING_PALETTE:
            errors.append(f"batch diversity: {count} briefs share palette family '{family}' (max {MAX_BRIEFS_SHARING_PALETTE})")

    return errors


def assert_batch_valid(briefs: list[dict]) -> None:
    """Raises ValueError with all lint errors joined, if any. No-op if the
    batch is clean."""
    errors = lint_batch(briefs)
    if errors:
        raise ValueError("brief batch failed lint:\n" + "\n".join(errors))
