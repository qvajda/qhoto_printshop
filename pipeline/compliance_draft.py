import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pipeline.anthropic_client as anthropic_client
import pipeline.artwork_store as artwork_store
import pipeline.config as config


# DISCLOSURE_TEXT removed 2026-08-06 (owner decision, GL-37). Both facts it
# carried are disclosed structurally on the listing, not in prose:
#   - AI generation -> the "What tools are used to make this item?" ->
#     "an AI generator" tick, which is NOT API-settable (GL-37: absent from the
#     listing, from taxonomy 1027's properties, and from any shop-level default;
#     tracked upstream as etsy/open-api Discussion #1630). The owner sets it by
#     hand in the web listing editor as part of the draft->publish action.
#   - Gelato -> production_partner_ids, set on the listing patch and verified
#     present live (GL-34).
# THE PRECONDITION THIS RESTS ON: every listing is published by hand through
# the editor, where the tick and the publish are the same save action. If a
# listing is ever activated programmatically instead (the parked GL-29), it
# would carry neither the structured tick nor this text - so re-read this
# comment before wiring any automated activation.
# The listing_texts.disclosure_text column is retained (NOT NULL) and written
# empty rather than migrated away: dropping it means a table rebuild, and it
# costs nothing to leave.
# WHAT KEEPS THIS DECISION TRUE: check_forbidden_terms below, called from
# validate_listing_text. Emptying this constant removed *our* sentence and
# nothing else - the model went on writing its own for two more days (GL-53:
# 27 of 27 drafts, including ones written after this comment was added). A
# prompt instruction is a preference; the check is the control.
DISCLOSURE_TEXT = ""

MAX_TAGS = 13
MAX_TAG_LENGTH = 20
MAX_TITLE_LENGTH = 140

DRAFT_TEXT_PROMPT_TEMPLATE = (
    "The image above IS the artwork this listing sells. Look at it and describe what is "
    "actually there - its subject, medium, palette and mood. Where the artwork and the "
    "niche/brief below disagree, THE ARTWORK WINS: the buyer receives the artwork, not "
    "the brief. (GL-68: copy written from the niche alone described a minimalist line "
    "leaf over an image of a red cardinal, and the critic rejected it three times.)\n"
    "Art brief the artwork was generated from, as intent only: {art_brief}\n"
    "{colour_line}{idiom_line}\n"
    "You are writing an Etsy listing draft for a botanical/minimalist wall art poster "
    "print, niche: {niche}. THE PRODUCT: a physical, made-to-order poster, printed on "
    "premium matte paper and shipped to the buyer. It is NOT a digital file, NOT a "
    "printable, NOT a download, and nothing is printed at home - never describe it as "
    "any of those, in the title, in a tag, or in the description. "
    "This listing must comply with Etsy's format limits: the title must be at most "
    "{max_title_length} characters, and there must be at most 13 tags and each tag at "
    "most 20 characters. Do NOT include any AI-disclosure or production-partner "
    "sentence anywhere - both are disclosed through Etsy's own structured listing "
    "fields, not in prose. The copy must be EVERGREEN: the listing stays up all year, "
    "so never name a holiday, festival, sale event or dated season (no Christmas, "
    "Diwali, Black Friday, New Year, 'for the holidays'). Describing the artwork's own "
    "mood or palette as autumnal or wintry is fine; naming a date is not.\n\n"
    "The product gallery (mockup photographs of this same artwork, not shown to you) has "
    "{image_count} images in this order: {image_types}. Write one "
    "short, descriptive alt text per image, in the same order, distinguishing a flat print "
    "mockup shot from a lifestyle/room-context shot.\n\n"
    "Reply with ONLY a JSON object with keys 'title' (string), 'tags' (list of strings), "
    "'description' (string), and 'alt_texts' (list of strings, same length and order as the "
    "gallery), no other text."
)


def resolve_compliance_metadata(static_config: dict) -> dict:
    # shipping_profile_id is NOT resolved here: v4.12 [D3] resolves it once per candidate
    # at publish time (config.get_shipping_profile_id), so there's nothing per-candidate
    # worth freezing into listing_texts at draft time.
    return {
        "who_made": static_config["etsy_who_made"],
        "production_partner_ids": static_config["etsy_production_partner_ids"],
        "taxonomy_id": static_config["etsy_taxonomy_id"],
    }


# GL-53. THIS LIST IS THE MECHANISM THAT KEEPS GL-37's DECISION TRUE (see the
# DISCLOSURE_TEXT comment above): if it is emptied, that decision is unenforced
# again and nothing anywhere will say so. Two classes, one list:
#
#   AI provenance - GL-37 put this in Etsy's structured "tools used" tick, set
#       by hand at publish. Prose repeats it in the one place we said it would
#       not be, and a tag spends one of thirteen search slots on it.
#   Digital-product wording - worse than drift: it advertises a product the
#       shop does not sell. Every size is a physical made-to-order Gelato
#       poster (when_made 'made_to_order', is_supply false). 25 of 27 drafts
#       said 'printable' or 'Instant Digital Download'.
#
# ONE LIST FOR ALL THREE FIELDS, deliberately, and the judgement call is the
# bare-'AI' one. The actual shipped sentence is "created using AI image
# generation" - it contains none of 'ai generated', 'ai-generated' or 'ai art',
# so a substring list alone misses the 27-of-27 defect it was written for. Hence
# FORBIDDEN_WORDS: word-boundary 'ai', case-insensitive. In English art copy a
# standalone "ai" token is always the acronym ('air', 'detail', 'paint' don't
# match a \bai\b), so the false-positive risk that argued for a narrower
# description list does not actually exist, and a narrower list would have let
# the defect through. The digital terms are safe on a description for the same
# reason they are needed there: an honest description of a shipped poster has no
# use for the word 'printable'. Over-matching costs one regeneration; under-
# matching costs a hand-repaired title at publish time, or a buyer complaint.
FORBIDDEN_TERMS = (
    "ai generated", "ai-generated", "ai art", "artificial intelligence",
    "midjourney", "dall-e", "stable diffusion", "generated with ai",
    "production partner", "gelato",
    "printable", "digital download", "instant download", "instant digital",
    "digital file", "pdf download", "jpg download", "svg", "print at home",
)
FORBIDDEN_WORDS = ("ai",)
_FORBIDDEN_PATTERN = re.compile(
    "|".join([re.escape(term) for term in FORBIDDEN_TERMS]
             + [rf"\b{re.escape(word)}\b" for word in FORBIDDEN_WORDS]),
    re.IGNORECASE,
)


# GL-55. THE DECISION THIS ENFORCES (owner, 2026-08-10, PRD
# docs/2026-08-10-gl55-gl56-prd.md §6.1 option (a)): listing copy is EVERGREEN. A
# seasonal niche - from any origin, whether a GL-47 gap, a bug, or the frozen
# pre-GL-47 backlog that surfaced this - must not put a dated event into the copy.
# Four E9 candidates reached the owner's queue saying "for the holidays", "Black
# Friday Cyber Monday Sale", "Welcome to the new year" over artwork that was fine.
#
# THE PRINCIPLE, which matters more than the entries (§6.2, owner-chosen):
#   BLOCKED - anything tied to a calendar date or a named festival / retail moment.
#       The listing outlives the date; copy that names one is stale the week after.
#   ALLOWED - atmospheric words for a season of nature ('autumnal', 'wintry',
#       'summer light'). A design's SUBJECT may legitimately be autumnal without
#       its COPY being seasonal, so those are deliberately absent below.
# That line is why 'new year' is here and 'winter' is not.
#
# Two halves, one list, and it is used at BOTH ends: the niche is sanitised with it
# before the prompt ever sees it (sanitize_niche), and the model's output is checked
# with it after (check_seasonal_terms). The prompt half alone is exactly the failure
# GL-53 already had once - an instruction in a prompt is a preference, not a control.
# The list will have gaps; the claim is that it fails loud when it matches and is one
# line to extend when it misses.
SEASONAL_TERMS = (
    "black friday", "cyber monday", "boxing day", "prime day", "singles day",
    "christmas", "xmas", "yuletide", "noel", "advent", "santa",
    "hanukkah", "chanukah", "diwali", "deepavali", "eid", "ramadan", "lunar new year",
    "thanksgiving", "halloween", "easter", "st patrick", "mardi gras",
    "valentine", "mother's day", "mothers day", "father's day", "fathers day",
    "new year", "new years", "newyear", "nye",
    "holiday", "holidays", "festive", "seasonal sale",
    "engagement season", "wedding season", "back to school", "graduation season",
)
_SEASONAL_PATTERN = re.compile(
    "|".join(re.escape(term) for term in SEASONAL_TERMS), re.IGNORECASE
)

# What the prompt gets when sanitising leaves nothing usable (e.g. niche
# 'holiday_peak' -> 'peak' -> meaningless). Better a generic-but-true descriptor than
# a niche word the copy should never echo.
NEUTRAL_NICHE = "botanical minimalist wall art"


def sanitize_niche(niche: str) -> str:
    """Strips event/season vocabulary out of a raw niche before it reaches the prompt.

    Niches arrive slug-shaped ('black_friday_cyber_monday', 'new_year_refresh'), so
    underscores become spaces first or the phrases never match.
    """
    cleaned = _SEASONAL_PATTERN.sub(" ", (niche or "").replace("_", " ").replace("-", " "))
    cleaned = " ".join(cleaned.split())
    return cleaned if len(cleaned) >= 3 else NEUTRAL_NICHE


def check_seasonal_terms(title: str, tags: list, description: str, alt_texts: list = None) -> None:
    """Rejects a draft naming a dated event or festival (GL-55). See SEASONAL_TERMS.

    Raises rather than scrubbing, same reasoning as check_forbidden_terms: a draft that
    reached for the event came out of a wrong framing, and the message is written to be
    usable verbatim as retry feedback.
    """
    fields = [("title", title), ("tags", ", ".join(tags)), ("description", description)]
    for index, alt_text in enumerate(alt_texts or []):
        fields.append((f"alt_texts[{index}]", alt_text))
    for field, value in fields:
        match = _SEASONAL_PATTERN.search(value or "")
        if match:
            raise ValueError(
                f"{field} contains the seasonal term {match.group(0)!r}: this listing stays "
                f"up all year, so the copy must be evergreen and must never name a dated "
                f"event, festival or retail moment. Rewrite the {field} describing the "
                f"artwork itself - its subject, style, colours and the room it suits."
            )


def check_forbidden_terms(title: str, tags: list, description: str, alt_texts: list = None) -> None:
    """Rejects a draft carrying AI-provenance or digital-product wording (GL-53).

    Raises rather than sanitising: a draft that used the word came out of a wrong
    framing, so a scrubbed title is worse copy than a regenerated one. The message
    is written to be usable verbatim as retry feedback.

    GL-54 rider: alt_texts are model output too, and they go live on the listing
    as image alt text - TRUE ONLY SINCE GL-69 (2026-08-12): when this sentence was
    written the upload call had no alt_text field at all, so every listing shipped
    alt_text='' and this docstring asserted a behaviour that did not exist. That is
    how the gap survived the review that added this validation. The consumer is now
    etsy_client.upload_listing_image's alt_text field, via group_product's upload
    loop - they're listing copy, not internal notes, so they belong
    inside the guardrail same as title/tags/description. alt_texts describe mockup
    *photographs* ("flat print mockup shot" vs a lifestyle/room-context shot), so
    the word 'print' alone is expected and legitimate there - checked against the
    shipped FORBIDDEN_TERMS/FORBIDDEN_WORDS list, which has no bare 'print' entry
    (only phrases like 'printable', 'print at home'), so that word is never a false
    positive here.
    """
    fields = [("title", title), ("tags", ", ".join(tags)), ("description", description)]
    for index, alt_text in enumerate(alt_texts or []):
        fields.append((f"alt_texts[{index}]", alt_text))
    for field, value in fields:
        match = _FORBIDDEN_PATTERN.search(value or "")
        if match:
            raise ValueError(
                f"{field} contains the forbidden term {match.group(0)!r}: this listing is a "
                f"physical made-to-order poster and its AI provenance and production partner "
                f"are disclosed in Etsy's structured fields, never in the copy. Rewrite the "
                f"{field} without that term or any wording that means the same thing."
            )


def validate_listing_text(title: str, tags: list, description: str = "", alt_texts: list = None, *,
                           max_title_length: int = MAX_TITLE_LENGTH) -> None:
    if len(title) > max_title_length:
        raise ValueError(
            f"title is {len(title)} chars, exceeds the {max_title_length}-char limit: {title!r}"
        )
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags exceeds Etsy's {MAX_TAGS}-tag limit: {tags!r}")
    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(
                f"tag {tag!r} is {len(tag)} chars, exceeds Etsy's {MAX_TAG_LENGTH}-char limit"
            )
    check_forbidden_terms(title, tags, description, alt_texts)
    check_seasonal_terms(title, tags, description, alt_texts)


def get_primary_gallery(conn, candidate_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.id, pi.gallery_order, pi.image_type
        FROM product_images pi
        JOIN groups g ON g.id = pi.group_id
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def build_draft_prompt(candidate: dict, image_types: list) -> str:
    # GL-55: the raw niche never reaches the model - see SEASONAL_TERMS. The art brief
    # goes through the same sanitiser: it was written FROM the niche, so a pre-GL-55
    # brief carries the event wording the niche no longer does (candidates 77/78/79).
    #
    # GL-10c/1 (#207): dominant_colour/named_idiom are candidate columns computed at
    # generate time (art_brief.generate_art_brief), NOT parsed back out of the brief
    # prose above (spec §1.3 option A, rejected as fragile). Either can be absent
    # (pre-migration rows, a reply that skipped the declaration) - the slot is then
    # dropped from the prompt entirely, never filled with a guessed colour word.
    dominant_colour = candidate.get("dominant_colour")
    named_idiom = candidate.get("named_idiom")
    colour_line = f"Dominant colour: {sanitize_niche(dominant_colour)}\n" if dominant_colour else ""
    idiom_line = f"Named art idiom: {sanitize_niche(named_idiom)}\n" if named_idiom else ""
    return DRAFT_TEXT_PROMPT_TEMPLATE.format(
        niche=sanitize_niche(candidate["niche"]),
        art_brief=sanitize_niche(candidate.get("art_brief") or ""),
        colour_line=colour_line,
        idiom_line=idiom_line,
        image_count=len(image_types),
        image_types=", ".join(image_types),
        max_title_length=MAX_TITLE_LENGTH,
    )


def generate_draft_text(candidate: dict, image_types: list, *, api_key: str = None,
                         retry_feedback: str = None) -> dict:
    """GL-68: the drafter sees the artwork. `candidates.base_image_local_path` is the
    same file the critic's local gate grades, and `_image_content_block` already takes a
    local path, so this is a call swap - not new plumbing. Without an image the copy is
    invented from a four-word niche, and the critic (which does get the images) rejects
    a mismatch the drafter cannot see, let alone fix."""
    prompt = build_draft_prompt(candidate, image_types)
    if retry_feedback:
        prompt += f"\n\n{retry_feedback}"
    artwork_path = artwork_store.resolve_artefact_path(candidate.get("base_image_local_path"))
    if artwork_path and not Path(artwork_path).exists():
        # Blind drafting is the GL-68 defect itself, so it is never the silent default:
        # a missing master means the copy is written from the brief alone and that has
        # to be visible in the log when the critic later rejects the mismatch.
        print(f"[compliance_draft] artwork {artwork_path!r} is missing; drafting without it")
        artwork_path = None
    if artwork_path:
        result = anthropic_client.complete_with_images(
            prompt, [artwork_path], api_key=api_key, max_tokens=2048,
        )
    else:
        result = anthropic_client.complete(prompt, api_key=api_key, max_tokens=2048)
    draft = anthropic_client.parse_json_response(result["text"])
    for key in ("title", "tags", "description", "alt_texts"):
        if key not in draft:
            raise ValueError(f"Claude draft response missing required key {key!r}: {draft!r}")
    if len(draft["alt_texts"]) != len(image_types):
        raise ValueError(
            f"Claude draft response has {len(draft['alt_texts'])} alt_texts, "
            f"expected {len(image_types)} to match the gallery: {draft!r}"
        )
    return draft


def write_listing_texts(conn, candidate_id: int, draft: dict, metadata: dict, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, draft["title"], json.dumps(draft["tags"]), draft["description"], DISCLOSURE_TEXT,
            metadata["who_made"], json.dumps(metadata["production_partner_ids"]),
            metadata["taxonomy_id"], "", timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_gallery_alt_text(conn, candidate_id: int, alt_texts: list) -> None:
    gallery = get_primary_gallery(conn, candidate_id)
    if len(alt_texts) != len(gallery):
        raise ValueError(
            f"{len(alt_texts)} alt_texts provided but candidate {candidate_id}'s primary "
            f"gallery has {len(gallery)} images"
        )
    for image, alt_text in zip(gallery, alt_texts):
        conn.execute(
            "UPDATE product_images SET alt_text = ? WHERE id = ?",
            (alt_text, image["id"]),
        )
    conn.commit()


# GL-69 half two: the secondary-group path (5x7 / 10x24) renders mockups but never
# generates alt text for them - `update_gallery_alt_text` covers the primary gallery
# only - so those rows reach the upload loop holding the '' placeholder
# `create_group_product` inserted. Derived from the listing title rather than drafted by
# a model: alt text on a mockup photograph only has to say what the photograph shows,
# and one extra Anthropic call per secondary group buys nothing. Etsy caps alt text at
# 250 chars; the title is already capped at 140.
ALT_TEXT_SUFFIXES = {
    "flat_mockup": "flat print mockup",
    "lifestyle": "print shown in a room setting",
}
ETSY_MAX_ALT_TEXT_LENGTH = 250


def fallback_alt_text(title: str, image_type: str) -> str:
    suffix = ALT_TEXT_SUFFIXES.get(image_type, "product photograph")
    return f"{title} - {suffix}"[:ETSY_MAX_ALT_TEXT_LENGTH]


def build_compliance_draft(conn, candidate_id: int, *, static_config: dict = None,
                            anthropic_api_key: str = None, correction_note: str = None,
                            now=None) -> dict:
    """GL-70: `correction_note` is the critic's own reason for rejecting the previous
    draft. `generate_draft_text` already took `retry_feedback`; the gap was purely that
    this function had no parameter to forward, so three critic retries were three
    identical blind draws (all 12 critic_pass_attempts rows E10b wrote had
    correction_notes NULL). Affects the normal path too, not just copy_only - there it
    was merely masked, because the regeneration call does receive the note."""
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    gallery = get_primary_gallery(conn, candidate_id)
    image_types = [image["image_type"] for image in gallery]
    metadata = resolve_compliance_metadata(static_config)

    try:
        # LLMs don't reliably obey character-count instructions on the first try, so
        # retry with the validation failure fed back as feedback before giving up (cap
        # 3, same retry budget as critic_pass). Only catch ValueError in *this inner
        # retry loop* (missing/invalid draft fields, Etsy limit violations, and
        # anthropic_client.MalformedJSONError - which subclasses ValueError): those are
        # real model-output problems worth feeding back as correction text. Anything
        # else (e.g. anthropic_client.NoTextContentError/TruncatedResponseError, or the
        # SDK's own transport errors) is not something a "fix this and keep every other
        # requirement" message can meaningfully address, so it isn't retried here - it
        # falls through to the outer except below, which still marks the candidate
        # failed (bookkeeping), just without wasting the retry budget on it.
        feedback = (
            f"The previous listing draft for this artwork was rejected by the quality "
            f"critic: {correction_note}. Write a new draft that fixes that, describing "
            f"the artwork you can see."
        ) if correction_note else None
        draft = None
        last_value_error = None
        for attempt in range(3):
            try:
                draft = generate_draft_text(candidate, image_types, api_key=anthropic_api_key,
                                             retry_feedback=feedback)
                validate_listing_text(draft["title"], draft["tags"], draft["description"], draft["alt_texts"])
                last_value_error = None
                break
            except ValueError as exc:
                last_value_error = exc
                feedback = f"Your previous attempt failed validation: {exc}. Fix this and keep every other requirement."
        if last_value_error is not None:
            raise last_value_error

        listing_text_id = write_listing_texts(conn, candidate_id, draft, metadata, now=now)
        update_gallery_alt_text(conn, candidate_id, draft["alt_texts"])
    except Exception as exc:
        conn.execute(
            "UPDATE candidates SET status = 'compliance_failed', failed_reason = ?, updated_at = ? WHERE id = ?",
            (str(exc), timestamp, candidate_id),
        )
        conn.commit()
        raise

    return {"listing_text_id": listing_text_id, "candidate_id": candidate_id}


class ComplianceDraftCycleError(RuntimeError):
    """Raised once at the end of run_compliance_draft_cycle if any candidate failed."""


def run_compliance_draft_cycle(conn, *, static_config: dict = None,
                                anthropic_api_key: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            WHERE c.status = 'generating'
              AND EXISTS (SELECT 1 FROM product_images pi WHERE pi.group_id = g.id)
              AND c.id NOT IN (SELECT candidate_id FROM listing_texts)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    # GL-53 found the second instance of GL-46's shape here (CLAUDE.md: a
    # swallowed per-item exception must always leave a state change behind).
    # Half of it was already right - build_compliance_draft marks the row
    # 'compliance_failed' with a reason - but the `continue` meant the stage
    # returned success, so run_batch's _run_stage never fired its Telegram
    # notification. Finish the loop so one bad candidate does not strand the
    # rest, then raise once with every failure named. No re-queue: a
    # 'compliance_failed' row is terminal here (an existing test pins that),
    # and the retry budget lives inside build_compliance_draft's 3 attempts.
    processed_ids = []
    failures = []
    for candidate_id in candidate_ids:
        try:
            build_compliance_draft(
                conn, candidate_id, static_config=static_config,
                anthropic_api_key=anthropic_api_key, now=now,
            )
        except Exception as exc:
            print(f"build_compliance_draft failed for candidate {candidate_id}: {exc}")
            failures.append(f"{candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)

    if failures:
        raise ComplianceDraftCycleError(
            f"{len(failures)} of {len(candidate_ids)} candidate(s) failed compliance draft - "
            + "; ".join(failures)
        )
    return processed_ids
