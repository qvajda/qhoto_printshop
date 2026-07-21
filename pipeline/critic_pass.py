import json
from datetime import datetime, timezone
import statistics

from PIL import Image, ImageFilter, ImageStat

import pipeline.anthropic_client as anthropic_client
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.primary_mockup as primary_mockup
import pipeline.research as research


CRITERION_KEYS = tuple(f"criterion_{i}" for i in range(1, 8))
VALID_OVERALLS = ("good", "refine", "reject")

CRITIC_RUBRIC_PROMPT_TEMPLATE = (
    "You are the compliance and quality critic for an Etsy AI-generated wall art listing. "
    "Review the {image_count} gallery images above against this rubric:\n"
    "1. Hard no-go list: no named artist's style, no recognizable characters, franchises, or "
    "logos, no implied celebrity likeness, no claims of hand-painted or one-of-a-kind original "
    "artwork - this is a print reproduction.\n"
    "2. Subject presence: reject if any image is near-empty, a plain gradient, or has no clear "
    "subject at all.\n"
    "3. Subject coherence: reject nonsensical or malformed subjects (e.g. anatomically/"
    "botanically impossible hybrid forms, floating or disconnected parts).\n"
    "4. Composition: reject an off-center or cut-off subject, or large dead/empty zones, unless "
    "clearly intentional to the style.\n"
    "5. Detail quality: reject smudging, muddiness, or blurred detail at the boundaries between "
    "color zones (this is clean flat-zone art - smudging is conspicuous).\n"
    "6. Visual density: reject overly sparse line work or a composition too empty to read as "
    "finished wall art.\n"
    "7. Text match: does this draft title and description actually match what's shown in the "
    "images and fit the niche?\n\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "{flag_note}\n"
    "Reply with ONLY a JSON object, no other text, shaped exactly like this: "
    '{{"criterion_1": {{"passed": bool, "note": "..."}}, "criterion_2": {{"passed": bool, '
    '"note": "..."}}, "criterion_3": {{...}}, "criterion_4": {{...}}, "criterion_5": {{...}}, '
    '"criterion_6": {{...}}, "criterion_7": {{...}}, "overall": "good"|"refine"|"reject"}}. '
    "One entry per rubric point above (criterion_1 = rubric point 1, etc.), 'note' explains that "
    "point's verdict. 'overall' is your holistic three-tier verdict: 'good' (ready to publish), "
    "'refine' (usable but flawed - minor issues like point 5 smudging, not disqualifying), or "
    "'reject' (a hard rubric failure - do not publish)."
)


# Local sanity gate, run zero-API-cost before the vision call - two complementary
# checks, restated 2026-07-20 against the CURRENT 7 masters in db/base_artwork/ (the
# prior comment cited masters 1-3's now-overwritten fingerprints; see
# docs/2026-07-20-s4a-failure-taxonomy.md for the full study). Current calibration
# set: must-FAIL {4, 6, 7}, must-PASS {1, 2, 5}, borderline {3} (flagged to the vision
# critic, not hard-failed - it's real, structured line art that's merely sparse, not
# an empty frame). Measured (stddev / edge_ratio / cov):
#   1 .56.6/.074/.265  2 23.6/.049/.148  3 15.7/.029/.020 (borderline)
#   4  6.9/.017/.006   5 69.4/.047/.297  6  0.4/.010/.000  7  8.3/.024/.029
#
# Check A (original): BOTH variance and edge density below floor - only catches a
# truly flat/empty frame (6).
# Check B (cov, added 2026-07-20 - the S4-a headline fix): thin line art clears
# edge_ratio while covering ~1-3% of the frame (4, 7 - the old gate's blind spot).
# `cov` = fraction of grayscale pixels deviating >15 from the median gray value,
# i.e. how much of the frame is actually "not background". Used alone it would also
# hard-fail master 3 (cov .020, same ballpark as 4/7) - but 3's stddev (15.7) sits
# far clear of 4/6/7's (0.4-8.3), so check B additionally requires stddev below a
# ceiling well above the empty-frame range but well below 3's - the tie-breaker that
# keeps 3 out of the hard-fail bucket while still catching 4/6/7.
SANITY_MIN_STDDEV = 3.0
SANITY_MIN_EDGE_RATIO = 0.012
SANITY_COV_HARD_FAIL = 0.05
SANITY_COV_HARD_FAIL_STDDEV_CEILING = 12.0
SANITY_COV_FLAG_CEILING = 0.12  # below this (and not hard-failed) -> flag-to-critic, not silent pass


def compute_image_sanity_stats(local_path) -> dict:
    with Image.open(local_path) as im:
        gray = im.convert("L")
    gray.thumbnail((512, 512))  # print masters are ~6656x9728 - stats don't need full res
    stddev = ImageStat.Stat(gray).stddev[0]
    edges = gray.filter(ImageFilter.FIND_EDGES)
    hist = edges.histogram()
    total = sum(hist) or 1
    edge_ratio = sum(hist[30:]) / total  # fraction of pixels with a meaningful edge
    pixels = list(gray.getdata())
    median = statistics.median(pixels)
    cov = sum(1 for p in pixels if abs(p - median) > 15) / len(pixels)  # subject-coverage proxy
    return {"stddev": stddev, "edge_ratio": edge_ratio, "cov": cov}


def check_local_image_sanity(local_path) -> dict | None:
    """Zero-API-cost near-empty gate run before the vision call. Returns a critic-fail
    result dict if the master is near-empty (see the calibration comment above for the
    two check types), else None ("inconclusive locally - spend the vision call")."""
    if not local_path:
        return None
    try:
        stats = compute_image_sanity_stats(local_path)
    except (FileNotFoundError, OSError):
        return None  # unreadable locally -> defer to the vision critic
    empty_by_variance = (
        stats["stddev"] < SANITY_MIN_STDDEV and stats["edge_ratio"] < SANITY_MIN_EDGE_RATIO
    )
    sparse_by_coverage = (
        stats["cov"] < SANITY_COV_HARD_FAIL
        and stats["stddev"] < SANITY_COV_HARD_FAIL_STDDEV_CEILING
    )
    if empty_by_variance or sparse_by_coverage:
        return {
            "passed": False,
            "reason": (f"near-empty image: stddev {stats['stddev']:.2f} "
                       f"(min {SANITY_MIN_STDDEV}), edge ratio {stats['edge_ratio']:.4f} "
                       f"(min {SANITY_MIN_EDGE_RATIO}), coverage {stats['cov']:.4f} "
                       f"(min {SANITY_COV_HARD_FAIL})"),
            "cov": stats["cov"],
        }
    return None


def local_sanity_flag_note(stats: dict) -> str | None:
    """Borderline-but-not-hard-failed signal (S4-d two-tier gate): cov below the
    full-pass ceiling doesn't reject locally, but shouldn't silently pass through to
    the vision critic unremarked either - surfaced as an addendum in its prompt."""
    if stats["cov"] < SANITY_COV_FLAG_CEILING:
        return (f"Note: the local sanity gate flagged this design as borderline-sparse "
                f"(subject coverage {stats['cov']:.3f}, below the {SANITY_COV_FLAG_CEILING} "
                f"full-pass floor) - scrutinize rubric points 2, 4, and 6 closely.")
    return None


MASTER_SANITY_PROMPT_TEMPLATE = (
    "You are a cheap, narrow pre-filter before a full quality review. Look at this single "
    "flat artwork image ONLY and answer one question: is it empty/near-blank, malformed/"
    "garbled (rendering artifacts, incoherent shapes), or otherwise obviously unusable as "
    "print-ready wall art? Do not evaluate style, composition subtlety, or text match - a "
    "full rubric review happens later; you are only screening out the obviously broken.\n"
    "{flag_note}\n"
    "Reply with ONLY a JSON object with keys 'passed' (boolean - true unless obviously "
    "broken) and 'reason' (string), no other text."
)


def check_master_image_ai_sanity(image_source: str, *, api_key: str = None,
                                  flag_note: str = None) -> dict | None:
    """Cheap single-image vision pre-filter (S4-d two-tier gate) between the free local
    gate and the full multi-image rubric pass - screens the flat master alone for
    empty/malformed/artifact defects before spending the expensive gallery+text call.
    Returns a critic-fail result dict if rejected, else None (defer to the full rubric).

    ponytail: routes through anthropic_client.complete_with_images, which currently
    hardcodes the Sonnet model (no model override param) - so this doesn't yet get the
    "Haiku-class" cost saving the plan calls for, only the narrower single-image prompt.
    anthropic_client.py is a sibling agent's file; wire in a cheaper model at fan-in
    once it exposes one.
    """
    if not image_source:
        return None
    prompt = MASTER_SANITY_PROMPT_TEMPLATE.format(flag_note=flag_note or "")
    response = anthropic_client.complete_with_images(prompt, [image_source], api_key=api_key)
    parsed = anthropic_client.parse_json_response(response["text"])
    for key in ("passed", "reason"):
        if key not in parsed:
            raise ValueError(f"Claude master-sanity response missing required key {key!r}: {parsed!r}")
    if parsed["passed"]:
        return None
    return {"passed": False, "reason": parsed["reason"]}


def build_critic_prompt(listing_text: dict, image_count: int, *, flag_note: str = None) -> str:
    return CRITIC_RUBRIC_PROMPT_TEMPLATE.format(
        image_count=image_count,
        title=listing_text["title"],
        description=listing_text["description"],
        flag_note=flag_note or "",
    )


def _normalize_verdict(parsed: dict) -> dict:
    """Validates and flattens the per-criterion {criterion_1..7, overall} verdict shape
    (S4-d) into the dict the rest of the pipeline consumes. 'passed'/'reason' stay
    present and derived, so existing consumers (record_critic_attempt, run_critic_pass's
    retry/abandon branching, generate.py's correction_note) don't need to know about the
    richer shape - the per-criterion detail is exposed alongside for the S4-b regen-brief
    consumer via 'criteria'/'overall'."""
    missing = [key for key in CRITERION_KEYS if key not in parsed]
    if missing:
        raise ValueError(f"Claude critic response missing required key(s) {missing}: {parsed!r}")
    if parsed.get("overall") not in VALID_OVERALLS:
        raise ValueError(
            f"Claude critic response missing/invalid 'overall' (expected one of "
            f"{VALID_OVERALLS}): {parsed!r}"
        )
    criteria = {}
    for key in CRITERION_KEYS:
        entry = parsed[key]
        if not isinstance(entry, dict) or "passed" not in entry or "note" not in entry:
            raise ValueError(f"Claude critic response criterion {key!r} malformed: {entry!r}")
        criteria[key] = {"passed": bool(entry["passed"]), "note": entry["note"]}
    overall = parsed["overall"]
    failing_notes = [entry["note"] for entry in criteria.values() if not entry["passed"]]
    reason = "; ".join(failing_notes) if failing_notes else "meets rubric"
    return {
        "passed": overall != "reject",
        "reason": reason,
        "overall": overall,
        "criteria": criteria,
    }


def evaluate_critic_pass(gallery_image_urls: list, listing_text: dict, *, api_key: str = None,
                          flag_note: str = None) -> dict:
    prompt = build_critic_prompt(listing_text, len(gallery_image_urls), flag_note=flag_note)
    result = anthropic_client.complete_with_images(prompt, gallery_image_urls, api_key=api_key)
    parsed = anthropic_client.parse_json_response(result["text"])
    return _normalize_verdict(parsed)


def run_local_and_master_gate(local_path, gallery_image_urls: list, *, api_key: str = None) -> tuple:
    """Tiers 1-2 of the S4-d three-tier gate, shared by critic_pass.py (primary group,
    has a local master) and group_critic_pass.py (5x7/10x24 groups, crops of that same
    master - no group-level local file yet, so tier 1 is skipped and tier 2 runs
    against the group's own flat gallery image instead). Returns
    (fail_result_or_None, flag_note_or_None) - fail_result set means stop here (don't
    spend the full rubric call); flag_note is only meaningful when fail_result is None,
    and should be threaded into the full rubric prompt."""
    hard_fail = check_local_image_sanity(local_path)
    if hard_fail is not None:
        return hard_fail, None

    flag_note = None
    if local_path:
        try:
            flag_note = local_sanity_flag_note(compute_image_sanity_stats(local_path))
        except (FileNotFoundError, OSError):
            pass

    master_image = local_path or (gallery_image_urls[0] if gallery_image_urls else None)
    master_fail = check_master_image_ai_sanity(master_image, api_key=api_key, flag_note=flag_note)
    if master_fail is not None:
        return master_fail, None

    return None, flag_note


def get_primary_group_state(conn, candidate_id: int) -> dict:
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    group_product_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
        (group_id,),
    ).fetchone()
    if group_product_row is None:
        raise ValueError(f"No live group_products row for candidate {candidate_id}'s primary group")
    group_product_id = group_product_row["id"]

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (group_product_id,),
    ).fetchall()
    image_urls = [row["image_url"] for row in image_rows]

    listing_row = conn.execute(
        "SELECT title, tags, description FROM listing_texts WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if listing_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")

    return {
        "group_id": group_id,
        "group_product_id": group_product_id,
        "image_urls": image_urls,
        "listing_text": dict(listing_row),
    }


def record_critic_attempt(conn, group_id: int, attempt_number: int, result: dict,
                           correction_notes: str = None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    criteria = result.get("criteria")
    cursor = conn.execute(
        """
        INSERT INTO critic_pass_attempts (
            group_id, attempt_number, passed, failure_reason, correction_notes,
            overall, criteria_json, cov, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            group_id, attempt_number, 1 if result["passed"] else 0,
            None if result["passed"] else result["reason"],
            correction_notes, result.get("overall"),
            json.dumps(criteria) if criteria is not None else None,
            result.get("cov"), timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None, api_key: str = None) -> None:
    row = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")
    if row["gelato_product_id"]:
        gelato_client.delete_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
    conn.execute("DELETE FROM group_product_variants WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM group_products WHERE id = ?", (group_product_id,))
    conn.commit()


def abandon_candidate(conn, candidate_id: int, group_id: int, reason: str, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE candidates SET status = 'failed', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, candidate_id),
    )
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, group_id),
    )
    conn.commit()


def run_critic_pass(conn, candidate_id: int, *, static_config: dict = None,
                     anthropic_api_key: str = None, store_id: str = None,
                     gelato_api_key: str = None, replicate_api_token: str = None,
                     now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    max_attempt_row = conn.execute(
        "SELECT MAX(attempt_number) AS max_attempt FROM critic_pass_attempts WHERE group_id = ?",
        (group_row["id"],),
    ).fetchone()
    attempt_number = (max_attempt_row["max_attempt"] or 0) + 1

    while True:
        state = get_primary_group_state(conn, candidate_id)
        # Three-tier gate before the full rubric call: free local sanity stats -> cheap
        # single-image vision pre-filter -> full multi-image rubric. Same attempt
        # counter, same cap, across all three tiers.
        local_path = conn.execute(
            "SELECT base_image_local_path FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()["base_image_local_path"]
        result, flag_note = run_local_and_master_gate(
            local_path, state["image_urls"], api_key=anthropic_api_key
        )
        if result is None:
            result = evaluate_critic_pass(
                state["image_urls"], state["listing_text"], api_key=anthropic_api_key,
                flag_note=flag_note,
            )
        record_critic_attempt(conn, state["group_id"], attempt_number, result, now=now)

        if result["passed"]:
            timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
            conn.execute(
                "UPDATE candidates SET status = 'primary_review', updated_at = ? WHERE id = ?",
                (timestamp, candidate_id),
            )
            conn.commit()
            return {"candidate_id": candidate_id, "passed": True, "attempts": attempt_number}

        discard_superseded_attempt(
            conn, state["group_product_id"], store_id=store_id, api_key=gelato_api_key
        )

        if attempt_number >= 3:
            abandon_candidate(conn, candidate_id, state["group_id"], result["reason"], now=now)
            research.trigger_fallback_if_needed(conn, now=now)
            return {"candidate_id": candidate_id, "passed": False, "attempts": attempt_number}

        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.commit()

        try:
            generate.generate_for_candidate(
                conn, candidate_id, correction_note=result["reason"],
                api_token=replicate_api_token, now=now,
            )
            primary_mockup.create_primary_mockup(
                conn, candidate_id, static_config=static_config, store_id=store_id,
                api_key=gelato_api_key, now=now,
            )
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=static_config,
                anthropic_api_key=anthropic_api_key, now=now,
            )
        except Exception as exc:
            # A crash here (e.g. Claude returning malformed JSON) would otherwise leave the
            # candidate in whatever terminal status that stage set (e.g. compliance_failed)
            # while this group stays 'pending_review' - stuck state cleanup.py never sweeps.
            abandon_candidate(conn, candidate_id, state["group_id"], f"retry regeneration failed: {exc}", now=now)
            raise

        attempt_number += 1


def run_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                           store_id: str = None, gelato_api_key: str = None,
                           replicate_api_token: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            JOIN listing_texts lt ON lt.candidate_id = c.id
            WHERE c.status = 'generating'
              AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            run_critic_pass(
                conn, candidate_id, static_config=static_config, anthropic_api_key=anthropic_api_key,
                store_id=store_id, gelato_api_key=gelato_api_key,
                replicate_api_token=replicate_api_token, now=now,
            )
        except Exception as exc:
            print(f"run_critic_pass failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
