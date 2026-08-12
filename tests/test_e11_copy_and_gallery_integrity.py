"""E11 (GL-68 / GL-69 / GL-70 / GL-72) - assertions in code, not sentences in prompts.

The GL-53 lesson and its two recurrences are the reason this file exists: every
decision below has a test that fails if the decision is quietly undone, and each
test asserts the call that is actually made rather than a mock of whichever call
the code happens to pick (four tests passed against E10c's broken reconcile
endpoint for exactly that reason).
"""
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest
from PIL import Image

import pipeline.compliance_draft as compliance_draft
import pipeline.critic_pass as critic_pass
import pipeline.db as db
import pipeline.etsy_client as etsy_client
import pipeline.group_product as group_product


def _conn(tmp_path):
    conn = db.get_connection(tmp_path / "e11.sqlite3")
    db.init_db(conn)
    return conn


def _draft_response(alt_count=2):
    return {"text": _json.dumps({
        "title": "Monstera Line Art Botanical Print",
        "tags": ["botanical"],
        "description": "A minimalist botanical print, shipped to you.",
        "alt_texts": [f"alt {i}" for i in range(alt_count)],
    })}


def _candidate(conn, *, status="generating", artwork_path=None, art_brief=None,
               niche="monstera line art", failed_reason=None):
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, "
        "base_image_local_path, art_brief, failed_reason, updated_at) "
        "VALUES ('2026-08-12T09:00:00', ?, 'go', ?, ?, ?, ?, '2026-08-12T09:00:00')",
        (niche, status, artwork_path, art_brief, failed_reason),
    )
    conn.commit()
    return cursor.lastrowid


def _primary_gallery(conn, candidate_id, image_types=("flat_mockup", "lifestyle"), *,
                      alt_text="", group_type="primary", group_product_id=None):
    group_id = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, decision, status, created_at, updated_at) "
        "VALUES (?, ?, 'approved', 'pending_review', '2026-08-12T09:00:00', '2026-08-12T09:00:00')",
        (candidate_id, group_type),
    ).lastrowid
    if group_product_id is None:
        group_product_id = conn.execute(
            "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, "
            "gelato_product_id, etsy_listing_id, status, created_at, updated_at) "
            "VALUES (?, ?, 'tpl', 'gelato_1', '4554354628', 'created', "
            "'2026-08-12T09:00:00', '2026-08-12T09:00:00')",
            (candidate_id, group_id),
        ).lastrowid
    for order, image_type in enumerate(image_types):
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, "
            "gallery_order, image_type) VALUES (?, ?, ?, ?, ?, ?)",
            (group_product_id, group_id, f"https://cdn/{group_id}-{order}.png", alt_text,
             order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _listing_text(conn, candidate_id, title="Monstera Line Art Botanical Print"):
    conn.execute(
        "INSERT INTO listing_texts (candidate_id, title, tags, description, disclosure_text, "
        "who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at) "
        "VALUES (?, ?, ?, 'A print.', '', 'i_did', ?, '1027', '', '2026-08-12T09:00:00')",
        (candidate_id, title, _json.dumps(["botanical"]), _json.dumps([5717252])),
    )
    conn.commit()


# --------------------------------------------------------------- GL-68


def test_draft_prompt_carries_the_art_brief():
    candidate = {"niche": "monstera line art",
                 "art_brief": "a single monstera leaf, bold filled shapes, sage green"}

    prompt = compliance_draft.build_draft_prompt(candidate, ["flat_mockup"])

    assert "a single monstera leaf, bold filled shapes, sage green" in prompt


def test_draft_prompt_sanitises_the_art_brief_too():
    # A pre-GL-55 brief was written FROM the unstripped niche, so it carries the event
    # wording the niche no longer does (candidates 77/78/79).
    candidate = {"niche": "botanical", "art_brief": "a diwali lamp among leaves"}

    prompt = compliance_draft.build_draft_prompt(candidate, ["flat_mockup"])

    # The template itself names Diwali (in the list of words the copy must not use), so
    # assert on the brief line, not on the whole prompt.
    brief_line = next(line for line in prompt.split("\n") if line.startswith("Art brief"))
    assert "diwali" not in brief_line.lower()
    assert "lamp among leaves" in brief_line


def test_draft_prompt_tells_the_model_the_artwork_wins_over_the_brief():
    prompt = compliance_draft.build_draft_prompt(
        {"niche": "botanical", "art_brief": "b"}, ["flat_mockup"])

    assert "THE ARTWORK WINS" in prompt


def test_generate_draft_text_sends_the_artwork_to_the_image_carrying_call(tmp_path):
    artwork = tmp_path / "master.png"
    Image.new("RGB", (40, 60), (200, 180, 120)).save(artwork)
    candidate = {"niche": "monstera line art", "art_brief": "a leaf",
                 "base_image_local_path": str(artwork)}

    with patch("pipeline.compliance_draft.anthropic_client.complete_with_images",
               return_value=_draft_response(1)) as with_images, \
         patch("pipeline.compliance_draft.anthropic_client.complete") as plain:
        compliance_draft.generate_draft_text(candidate, ["flat_mockup"], api_key="k")

    # The whole of GL-68: the drafting call is the one that carries the image.
    plain.assert_not_called()
    with_images.assert_called_once()
    assert with_images.call_args.args[1] == [str(artwork)]


def test_generate_draft_text_falls_back_when_the_master_is_missing():
    candidate = {"niche": "monstera line art", "base_image_local_path": "/nope/gone.png"}

    with patch("pipeline.compliance_draft.anthropic_client.complete_with_images") as with_images, \
         patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_draft_response(1)) as plain:
        compliance_draft.generate_draft_text(candidate, ["flat_mockup"], api_key="k")

    with_images.assert_not_called()
    plain.assert_called_once()


# --------------------------------------------------------------- GL-70


def test_correction_note_reaches_the_drafting_call(tmp_path):
    conn = _conn(tmp_path)
    candidate_id = _candidate(conn)
    _primary_gallery(conn, candidate_id)

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_draft_response()) as plain:
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=_STATIC_CONFIG, anthropic_api_key="k",
            correction_note="Severe mismatch: the copy promises a line-drawn leaf, "
                            "the images show a red cardinal.",
        )

    prompt = plain.call_args.args[0]
    assert "red cardinal" in prompt
    conn.close()


def test_copy_only_never_grades_the_artwork(tmp_path):
    conn = _conn(tmp_path)
    artwork = tmp_path / "master.png"
    Image.new("RGB", (40, 60), (10, 90, 40)).save(artwork)
    candidate_id = _candidate(conn, artwork_path=str(artwork))
    _primary_gallery(conn, candidate_id)
    _listing_text(conn, candidate_id)

    with patch("pipeline.critic_pass.run_local_and_master_gate") as gate, \
         patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value={"text": _json.dumps({"passed": True, "reason": "matches"})}):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=_STATIC_CONFIG, anthropic_api_key="k",
            copy_only=True, now=datetime(2026, 8, 12, 9, 0, 0),
        )

    assert result["passed"] is True
    gate.assert_not_called()
    conn.close()


def test_copy_only_hands_back_and_never_abandons(tmp_path):
    conn = _conn(tmp_path)
    candidate_id = _candidate(conn)
    group_id, _ = _primary_gallery(conn, candidate_id)
    _listing_text(conn, candidate_id)

    rejection = {"text": _json.dumps({"passed": False, "reason": "copy names a leaf, art is a bird"})}
    with patch("pipeline.critic_pass.abandon_candidate") as abandon, \
         patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=rejection), \
         patch("pipeline.compliance_draft.anthropic_client.complete", return_value=_draft_response()):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=_STATIC_CONFIG, anthropic_api_key="k",
            copy_only=True, now=datetime(2026, 8, 12, 9, 0, 0),
        )

    abandon.assert_not_called()
    assert result["handed_back"] is True
    candidate = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    # Handed back to the owner, not destroyed: the digest cycle picks 'primary_review'
    # rows up, and the last draft is still on the row for the owner to look at.
    assert candidate["status"] == "primary_review"
    assert candidate["failed_reason"] is None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()["n"] == 1
    group = conn.execute("SELECT status, failed_reason FROM groups WHERE id = ?",
                         (group_id,)).fetchone()
    assert group["status"] != "failed_abandoned"
    assert "handed back" in group["failed_reason"]
    conn.close()


def test_correction_notes_are_persisted_on_every_attempt_after_the_first(tmp_path):
    conn = _conn(tmp_path)
    candidate_id = _candidate(conn)
    group_id, _ = _primary_gallery(conn, candidate_id)
    _listing_text(conn, candidate_id)

    rejection = {"text": _json.dumps({"passed": False, "reason": "copy/art mismatch: bird vs leaf"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=rejection), \
         patch("pipeline.compliance_draft.anthropic_client.complete", return_value=_draft_response()):
        critic_pass.run_critic_pass(
            conn, candidate_id, static_config=_STATIC_CONFIG, anthropic_api_key="k",
            copy_only=True, now=datetime(2026, 8, 12, 9, 0, 0),
        )

    notes = [row["correction_notes"] for row in conn.execute(
        "SELECT correction_notes FROM critic_pass_attempts WHERE group_id = ? "
        "ORDER BY attempt_number", (group_id,)
    ).fetchall()]
    assert notes[0] is None
    assert all(note and "mismatch" in note for note in notes[1:])
    conn.close()


# --------------------------------------------------------------- GL-72


def test_a_passing_critic_clears_a_stale_failed_reason(tmp_path):
    conn = _conn(tmp_path)
    candidate_id = _candidate(
        conn, failed_reason="gl46_generate_failed (attempt 1/3): Anthropic response "
                            "truncated at max_tokens=200; raise the cap")
    _primary_gallery(conn, candidate_id)
    _listing_text(conn, candidate_id)

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value={"text": _json.dumps({"passed": True, "reason": "matches"})}):
        critic_pass.run_critic_pass(
            conn, candidate_id, static_config=_STATIC_CONFIG, anthropic_api_key="k",
            copy_only=True, now=datetime(2026, 8, 12, 9, 0, 0),
        )

    row = conn.execute("SELECT status, failed_reason FROM candidates WHERE id = ?",
                       (candidate_id,)).fetchone()
    assert row["status"] == "primary_review"
    assert row["failed_reason"] is None
    conn.close()


# --------------------------------------------------------------- GL-69


def test_upload_listing_image_sends_alt_text_as_a_multipart_field():
    sent = {}

    def fake_send(request):
        sent["body"] = request.data
        return {"listing_image_id": 1}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send), \
         patch("pipeline.etsy_client._call_with_refresh",
               side_effect=lambda build, token: fake_send(build("t"))):
        etsy_client.upload_listing_image(
            "shop", "listing", b"png-bytes", rank=1, alt_text="Flat mockup of a leaf print",
            api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    body = sent["body"]
    assert b'name="alt_text"' in body
    assert b"Flat mockup of a leaf print" in body


def test_fallback_alt_text_names_what_the_photograph_shows():
    flat = compliance_draft.fallback_alt_text("Monstera Print", "flat_mockup")
    lifestyle = compliance_draft.fallback_alt_text("Monstera Print", "lifestyle")

    assert flat != lifestyle
    assert "Monstera Print" in flat
    assert len(compliance_draft.fallback_alt_text("x" * 400, "lifestyle")) <= 250
    # It is listing copy like any other: it must clear the GL-53/GL-55 guardrails.
    compliance_draft.validate_listing_text("Monstera Print", [], "", [flat, lifestyle])


def test_gallery_upload_ships_alt_text_and_backfills_secondary_groups(tmp_path):
    conn = _conn(tmp_path)
    candidate_id = _candidate(conn)
    _, group_product_id = _primary_gallery(conn, candidate_id, alt_text="Flat mockup of a leaf")
    # The 5x7 group shares the candidate's listing record and was never given alt text.
    _primary_gallery(conn, candidate_id, ("flat_mockup",), group_type="5x7",
                     group_product_id=group_product_id)
    _listing_text(conn, candidate_id)
    listing_text = dict(conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)).fetchone())

    uploaded = []

    def fake_upload(shop_id, listing_id, image_bytes, *, rank=None, alt_text=None, **kwargs):
        uploaded.append((rank, alt_text))
        return {"listing_image_id": f"img{rank}"}

    with patch("pipeline.group_product.etsy_client.upload_listing_image", side_effect=fake_upload), \
         patch("pipeline.group_product.etsy_client.get_listing_images", return_value={"results": []}), \
         patch("pipeline.group_product.etsy_client.update_listing", return_value={}), \
         patch("pipeline.group_product.etsy_client.update_listing_inventory", return_value={}), \
         patch("pipeline.group_product.http.fetch_bytes", return_value=b"bytes"):
        group_product.patch_etsy_listing(
            conn, group_product_id, listing_text, _STATIC_CONFIG, shop_id="shop",
            dry_run=False, now="2026-08-12T09:00:00",
        )

    assert uploaded, "no image was uploaded"
    assert all(alt_text for _, alt_text in uploaded), uploaded
    # The derived alt text is written back, so a live read-back is checked against
    # something the DB actually holds.
    assert all(row["alt_text"] for row in conn.execute(
        "SELECT alt_text FROM product_images WHERE group_product_id = ?", (group_product_id,)
    ).fetchall())
    conn.close()


_STATIC_CONFIG = {
    "etsy_taxonomy_id": 1027,
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_shop_section_id": 59380312,
    "etsy_shipping_profile_id": "288734253315",
    "prices_eur": {"5x7": 19, "8x12": 24, "A3": 35, "A2": 39, "10x24": 45, "A1": 49},
    "gelato_templates": {},
    "mockup_templates": {},
}
