import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.anthropic_client as anthropic_client
import pipeline.compliance_draft as compliance_draft
import pipeline.db as db


STATIC_CONFIG = {
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
}


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating"):
    timestamp = "2026-07-10T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at)
        VALUES (?, ?, 'go', ?, ?)
        """,
        (timestamp, niche, status, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id, image_types=("flat_mockup", "lifestyle"),
                             *, group_product_status="created"):
    timestamp = "2026-07-10T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(candidate_id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'tpl_1', ?, ?, ?)",
        (candidate_id, group_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, group_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, ?, '8x12', 'portrait', 'variant_8x12', 24, ?)",
        (group_product_id, group_id, timestamp),
    )
    for order, image_type in enumerate(image_types):
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, '', ?, ?)",
            (group_product_id, group_id, f"https://gelato/img{order}.jpg", order, image_type),
        )
    conn.commit()
    return group_product_id


def _insert_ready_candidate(conn, niche="monstera line art", image_types=("flat_mockup", "lifestyle")):
    candidate_id = _insert_candidate(conn, niche=niche, status="generating")
    _insert_primary_gallery(conn, candidate_id, image_types=image_types)
    return candidate_id


def test_resolve_compliance_metadata_reads_static_config_fields():
    metadata = compliance_draft.resolve_compliance_metadata(STATIC_CONFIG)

    assert metadata == {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
    }


def test_validate_listing_text_accepts_valid_input():
    compliance_draft.validate_listing_text("Botanical Wall Art Print", ["botanical", "wall art", "minimalist"])


def test_validate_listing_text_rejects_title_over_140_chars():
    long_title = "x" * 141

    with pytest.raises(ValueError, match="140"):
        compliance_draft.validate_listing_text(long_title, ["botanical"])


def test_title_up_to_full_etsy_max_length_is_valid_no_size_suffix_headroom():
    title = "x" * 140

    compliance_draft.validate_listing_text(title, ["tag1"])  # must not raise


def test_validate_listing_text_rejects_more_than_13_tags():
    too_many_tags = [f"tag{i}" for i in range(14)]

    with pytest.raises(ValueError, match="13"):
        compliance_draft.validate_listing_text("A short title", too_many_tags)


def test_validate_listing_text_rejects_tag_over_20_chars():
    long_tag = "x" * 21

    with pytest.raises(ValueError, match="20"):
        compliance_draft.validate_listing_text("A short title", [long_tag])


# GL-53, one test per drift class found in the 2026-08-10 listing_texts audit.
def test_validate_listing_text_rejects_prose_ai_disclosure_in_description():
    # Class (a), 27 of 27: the verbatim sentence the model kept writing after
    # GL-37 emptied DISCLOSURE_TEXT. It contains no 'AI generated' / 'AI art',
    # which is exactly why FORBIDDEN_WORDS' bare word-boundary 'ai' exists.
    description = (
        "This design was created using AI image generation from the seller's own "
        "prompts, then selected, edited, and prepared for print by the seller."
    )

    with pytest.raises(ValueError, match="description contains the forbidden term"):
        compliance_draft.validate_listing_text("Botanical Wall Art Print", ["botanical"], description)


def test_validate_listing_text_rejects_ai_disclosure_in_title_and_in_a_tag():
    # Class (b), 13 of 27 (the kickoff said 10; the re-run on the canonical DB says 13).
    with pytest.raises(ValueError, match="title contains the forbidden term"):
        compliance_draft.validate_listing_text(
            "Sage Branch Print | AI Generated Art | Modern Home Decor", ["botanical"], "A print."
        )

    with pytest.raises(ValueError, match="tags contains the forbidden term"):
        compliance_draft.validate_listing_text(
            "Sage Branch Print", ["botanical", "ai generated art"], "A print."
        )


def test_validate_listing_text_rejects_digital_download_wording():
    # Class (c), 25 of 27 - the serious one: it advertises a product we do not sell.
    with pytest.raises(ValueError, match="title contains the forbidden term 'Instant Digital'"):
        compliance_draft.validate_listing_text(
            "Sage Branch Wall Art | Instant Digital Download", ["botanical"], "A print."
        )

    with pytest.raises(ValueError, match="tags contains the forbidden term 'printable'"):
        compliance_draft.validate_listing_text(
            "Sage Branch Wall Art", ["printable wall art"], "A print."
        )


def test_validate_listing_text_rejects_production_partner_prose():
    # Same GL-37 decision, other half: Gelato is disclosed through
    # production_partner_ids, not in the description.
    with pytest.raises(ValueError, match="description contains the forbidden term"):
        compliance_draft.validate_listing_text(
            "Sage Branch Wall Art", ["botanical"],
            "Printed and shipped by our production partner, Gelato.",
        )


def test_validate_listing_text_accepts_clean_physical_poster_copy():
    # The false-positive guard for the bare word-boundary 'ai' rule: 'air',
    # 'detail' and 'painted' must not match, or a 200-word description would
    # loop the retry budget away.
    compliance_draft.validate_listing_text(
        "Sage Green Branch Wall Art Print | Minimalist Botanical Poster",
        ["sage green wall art", "botanical print", "nature poster"],
        "A made-to-order poster on premium matte paper. Every detail of the hand-painted "
        "branch stays crisp, and the airy neutral palette suits most rooms. Ships flat.",
    )


def test_validate_listing_text_rejects_ai_disclosure_in_an_alt_text():
    # GL-54 rider: alt texts are model output that goes live on the listing, so
    # they belong inside the guardrail same as title/tags/description.
    with pytest.raises(ValueError, match=r"alt_texts\[1\] contains the forbidden term"):
        compliance_draft.validate_listing_text(
            "Sage Branch Wall Art", ["botanical"], "A made-to-order poster.",
            ["Flat print mockup on a white background", "AI Generated art hanging in a living room"],
        )


def test_validate_listing_text_accepts_honest_mockup_alt_text_with_the_word_print():
    # Alt texts describe mockup *photographs* ("flat print mockup shot" vs a
    # lifestyle/room-context shot) - the bare word 'print' must not trip the
    # guardrail, and the shipped term list has no entry that would.
    compliance_draft.validate_listing_text(
        "Sage Branch Wall Art", ["botanical"], "A made-to-order poster.",
        ["Flat print mockup shot on a white background", "Lifestyle shot of the print in a living room"],
    )


def test_forbidden_terms_list_is_not_empty():
    # If this list is emptied, GL-37's decision is unenforced again and nothing
    # else in the suite would notice. See the comment above FORBIDDEN_TERMS.
    assert compliance_draft.FORBIDDEN_TERMS
    assert compliance_draft.FORBIDDEN_WORDS


def test_draft_prompt_does_not_hand_the_model_the_forbidden_vocabulary():
    # The template used to open with "an AI-generated botanical/minimalist wall
    # art poster print" and then ask the model not to mention AI.
    prompt = compliance_draft.build_draft_prompt(
        {"niche": "sage green branch"}, ["flat_mockup", "lifestyle"]
    )

    assert "AI-generated botanical" not in prompt
    assert "made-to-order poster" in prompt


def test_get_primary_gallery_returns_images_in_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(
        conn, image_types=("flat_mockup", "lifestyle", "lifestyle")
    )

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert [image["image_type"] for image in gallery] == ["flat_mockup", "lifestyle", "lifestyle"]
    assert [image["gallery_order"] for image in gallery] == [0, 1, 2]
    conn.close()


def test_get_primary_gallery_returns_empty_list_when_no_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert gallery == []
    conn.close()


def test_build_draft_prompt_includes_niche_and_limits():
    candidate = {"niche": "monstera line art"}

    prompt = compliance_draft.build_draft_prompt(candidate, ["flat_mockup", "lifestyle"])

    assert "monstera line art" in prompt
    assert str(compliance_draft.MAX_TITLE_LENGTH) in prompt
    assert "13" in prompt
    assert "20" in prompt
    assert "flat_mockup, lifestyle" in prompt


def test_build_draft_prompt_forbids_a_prose_disclosure(monkeypatch):
    # GL-37 (2026-08-06): the AI disclosure moved off the description entirely and
    # onto Etsy's structured "tools used" tick, which the owner sets by hand at
    # publish. The prompt must actively tell the writer NOT to add a disclosure
    # sentence - silence would let the model reintroduce one on its own, which is
    # how the old text would creep back without anyone deciding to bring it back.
    prompt = compliance_draft.build_draft_prompt({"niche": "fern study"}, ["flat_mockup"])

    assert "Do NOT include any AI-disclosure" in prompt
    assert compliance_draft.DISCLOSURE_TEXT == ""


def test_generate_draft_text_returns_parsed_draft():
    candidate = {"niche": "monstera line art"}
    fake_response = {
        "text": _json.dumps({
            "title": "Monstera Line Art Botanical Print",
            "tags": ["botanical", "wall art"],
            "description": "A minimalist botanical print.",
            "alt_texts": ["Flat mockup of monstera line art print", "Monstera print shown in a living room"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response) as mock_complete:
        draft = compliance_draft.generate_draft_text(
            candidate, ["flat_mockup", "lifestyle"], api_key="key1"
        )

    mock_complete.assert_called_once()
    assert mock_complete.call_args.kwargs["api_key"] == "key1"
    assert draft["title"] == "Monstera Line Art Botanical Print"
    assert draft["tags"] == ["botanical", "wall art"]
    assert len(draft["alt_texts"]) == 2


def test_generate_draft_text_raises_on_missing_key():
    candidate = {"niche": "monstera line art"}
    fake_response = {"text": _json.dumps({"title": "A title", "tags": [], "description": "desc"})}

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match="alt_texts"):
            compliance_draft.generate_draft_text(candidate, ["flat_mockup"], api_key="key1")


def test_generate_draft_text_raises_on_alt_text_count_mismatch():
    candidate = {"niche": "monstera line art"}
    fake_response = {
        "text": _json.dumps({
            "title": "A title", "tags": ["botanical"], "description": "desc",
            "alt_texts": ["only one alt text"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match="alt_texts"):
            compliance_draft.generate_draft_text(
                candidate, ["flat_mockup", "lifestyle"], api_key="key1"
            )


def test_write_listing_texts_inserts_row_with_json_encoded_lists(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    draft = {
        "title": "Monstera Line Art Botanical Print",
        "tags": ["botanical", "wall art"],
        "description": "A minimalist botanical print.",
        "alt_texts": ["alt one", "alt two"],
    }
    metadata = {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }

    listing_text_id = compliance_draft.write_listing_texts(
        conn, candidate_id, draft, metadata, now=datetime(2026, 7, 10, 9, 30, 0)
    )

    row = conn.execute("SELECT * FROM listing_texts WHERE id = ?", (listing_text_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["title"] == "Monstera Line Art Botanical Print"
    assert _json.loads(row["tags"]) == ["botanical", "wall art"]
    assert row["description"] == "A minimalist botanical print."
    # Retained NOT NULL column, deliberately written empty since GL-37 - see the
    # comment on DISCLOSURE_TEXT. Asserted as "" rather than against the constant
    # so this test fails loudly if a prose disclosure is ever reintroduced.
    assert row["disclosure_text"] == ""
    assert row["who_made"] == "i_did"
    assert _json.loads(row["production_partner_ids"]) == [5717252]
    assert row["taxonomy_id"] == "1027"
    assert row["shipping_profile_id"] == ""
    assert row["created_at"] == "2026-07-10T09:30:00"
    conn.close()


def test_update_gallery_alt_text_updates_rows_in_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    compliance_draft.update_gallery_alt_text(
        conn, candidate_id, ["Flat mockup alt text", "Lifestyle alt text"]
    )

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN groups g ON g.id = pi.group_id
        WHERE g.candidate_id = ? ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    assert [row["alt_text"] for row in gallery] == ["Flat mockup alt text", "Lifestyle alt text"]
    conn.close()


def test_update_gallery_alt_text_raises_on_count_mismatch(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with pytest.raises(ValueError, match="2"):
        compliance_draft.update_gallery_alt_text(conn, candidate_id, ["only one alt text"])

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN groups g ON g.id = pi.group_id
        WHERE g.candidate_id = ?
        """,
        (candidate_id,),
    ).fetchall()
    assert all(row["alt_text"] == "" for row in gallery)
    conn.close()


def _fake_draft_response(alt_text_count=2):
    return {
        "text": _json.dumps({
            "title": "Monstera Line Art Botanical Print",
            "tags": ["botanical", "wall art"],
            "description": "A minimalist botanical print.",
            "alt_texts": [f"alt text {i}" for i in range(alt_text_count)],
        })
    }


def test_build_compliance_draft_happy_path_writes_listing_text_and_alt_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        result = compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    listing_row = conn.execute(
        "SELECT * FROM listing_texts WHERE id = ?", (result["listing_text_id"],)
    ).fetchone()
    assert listing_row["candidate_id"] == candidate_id
    assert listing_row["title"] == "Monstera Line Art Botanical Print"
    assert listing_row["who_made"] == "i_did"

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN groups g ON g.id = pi.group_id
        WHERE g.candidate_id = ? ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    assert [row["alt_text"] for row in gallery] == ["alt text 0", "alt text 1"]

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "generating"
    conn.close()


def test_build_compliance_draft_marks_compliance_failed_when_claude_call_raises(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=RuntimeError("Anthropic 500")):
        with pytest.raises(RuntimeError, match="Anthropic 500"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    assert "Anthropic 500" in candidate_row["failed_reason"]

    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert listing_rows == []
    conn.close()


def test_build_compliance_draft_does_not_retry_non_value_errors(tmp_path):
    # A NoTextContentError/TruncatedResponseError (or any non-ValueError, e.g. an
    # SDK transport error) is not something "fix this and keep every other
    # requirement" feedback can address - it must fail on the first attempt, not
    # burn the 3-attempt retry budget, while still marking the candidate failed.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=anthropic_client.NoTextContentError(["tool_use"])) as mock_complete:
        with pytest.raises(anthropic_client.NoTextContentError):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    assert mock_complete.call_count == 1
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    conn.close()


def test_build_compliance_draft_marks_compliance_failed_on_validation_error(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))
    over_limit_title = "x" * (compliance_draft.MAX_TITLE_LENGTH + 1)
    fake_response = {
        "text": _json.dumps({
            "title": over_limit_title, "tags": ["botanical"], "description": "desc",
            "alt_texts": ["alt one", "alt two"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match=str(compliance_draft.MAX_TITLE_LENGTH)):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    conn.close()


def test_build_compliance_draft_retries_after_over_limit_title_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))
    over_limit_title = "x" * (compliance_draft.MAX_TITLE_LENGTH + 1)
    bad_response = {
        "text": _json.dumps({
            "title": over_limit_title, "tags": ["botanical"], "description": "desc",
            "alt_texts": ["alt one", "alt two"],
        })
    }
    good_response = _fake_draft_response(2)

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=[bad_response, good_response]) as mock_complete:
        result = compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    assert mock_complete.call_count == 2
    # the retry prompt must carry the validation failure back to Claude
    retry_prompt = mock_complete.call_args_list[1].args[0]
    assert "previous attempt failed validation" in retry_prompt
    assert str(compliance_draft.MAX_TITLE_LENGTH) in retry_prompt

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "generating"
    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(listing_rows) == 1
    conn.close()


def test_build_compliance_draft_feeds_a_forbidden_term_back_as_retry_feedback(tmp_path):
    # GL-53 wires into the retry that already existed rather than adding one:
    # validation fails -> the failure message becomes the retry feedback.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))
    bad_response = {
        "text": _json.dumps({
            "title": "Sage Branch Wall Art | Printable Download",
            "tags": ["botanical"], "description": "A print.",
            "alt_texts": ["alt one", "alt two"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=[bad_response, _fake_draft_response(2)]) as mock_complete:
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    assert mock_complete.call_count == 2
    retry_prompt = mock_complete.call_args_list[1].args[0]
    assert "previous attempt failed validation" in retry_prompt
    assert "forbidden term 'Printable'" in retry_prompt

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "generating"
    conn.close()


def test_build_compliance_draft_fails_the_candidate_when_every_attempt_carries_a_forbidden_term(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))
    bad_response = {
        "text": _json.dumps({
            "title": "Sage Branch Wall Art Print",
            "tags": ["botanical"],
            "description": "Created using AI image generation.",
            "alt_texts": ["alt one", "alt two"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=bad_response) as mock_complete:
        with pytest.raises(ValueError, match="description contains the forbidden term"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    assert mock_complete.call_count == 3
    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    assert "forbidden term" in candidate_row["failed_reason"]
    assert conn.execute(
        "SELECT COUNT(*) FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()[0] == 0
    conn.close()


def test_build_compliance_draft_marks_compliance_failed_on_alt_text_mismatch_but_keeps_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)), \
         patch("pipeline.compliance_draft.update_gallery_alt_text",
               side_effect=ValueError("alt_texts count mismatch")):
        with pytest.raises(ValueError, match="alt_texts count mismatch"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"

    # Known accepted limitation (see plan's Global Constraints): write_listing_texts already
    # committed before update_gallery_alt_text raised, so the row persists.
    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(listing_rows) == 1
    conn.close()


def test_run_compliance_draft_cycle_processes_ready_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    not_yet_mocked_id = _insert_candidate(conn, niche="pending one", status="generating")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        processed_ids = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    assert processed_ids == [ready_id]
    assert not_yet_mocked_id not in processed_ids
    conn.close()


def test_run_compliance_draft_cycle_skips_already_drafted_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        first_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )
        second_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 11, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_compliance_draft_cycle_skips_already_failed_candidates_on_next_run(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=RuntimeError("Anthropic 500")):
        # GL-53/GL-46: the stage itself fails once at the end of the loop.
        with pytest.raises(compliance_draft.ComplianceDraftCycleError):
            compliance_draft.run_compliance_draft_cycle(
                conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        second_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 11, 0, 0),
        )

    assert second_run == []  # candidate stayed 'compliance_failed', not auto-retried
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    conn.close()


def test_run_compliance_draft_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_complete(prompt, *, api_key=None, max_tokens=1024):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return _fake_draft_response(2)

    with patch("pipeline.compliance_draft.anthropic_client.complete", side_effect=fake_complete):
        # The failure is isolated (the good candidate still gets its turn) *and*
        # the stage still reports it - both halves of the GL-46 rule.
        with pytest.raises(compliance_draft.ComplianceDraftCycleError, match=f"{failing_id}: "):
            compliance_draft.run_compliance_draft_cycle(
                conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    failing_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    assert failing_row["status"] == "compliance_failed"
    succeeded_row = conn.execute(
        "SELECT COUNT(*) FROM listing_texts WHERE candidate_id = ?", (succeeding_id,)
    ).fetchone()[0]
    assert succeeded_row == 1
    conn.close()


def test_run_compliance_draft_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending")

    processed_ids = compliance_draft.run_compliance_draft_cycle(conn, static_config=STATIC_CONFIG)

    assert processed_ids == []
    conn.close()
