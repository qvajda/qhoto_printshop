import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.db as db
import pipeline.group_product as group_product
import pipeline.publish_group as publish_group
import pipeline.publish_primary_group as publish_primary_group


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png",
                       base_image_local_path=None):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url,
        base_image_local_path, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, base_image_local_path, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id, group_type, *, status="pending_review", decision=None):
    timestamp = "2026-07-13T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, decision, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, decision, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-12T09:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "AI disclosure text.",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _ensure_listing_record(conn, candidate_id, group_id, *, gelato_product_id=None,
                            status="pending"):
    """v4.12: ONE group_products row per candidate - the listing record - shared by
    every group, carrying no Gelato product until publish."""
    timestamp = "2026-07-13T10:00:00"
    row = conn.execute(
        "SELECT id FROM group_products WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if row is not None:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(candidate_id, group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'tpl_x', ?, ?, ?, ?)",
        (candidate_id, group_id, gelato_product_id, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _add_group_contribution(conn, candidate_id, group_id, size, *, price_eur=19,
                             image_urls=("https://cdn/flat.jpg", "https://cdn/life.jpg")):
    timestamp = "2026-07-13T10:00:00"
    gp_id = _ensure_listing_record(conn, candidate_id, group_id)
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, group_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, ?, ?, 'portrait', 'variant_x', ?, ?)",
        (gp_id, group_id, size, price_eur, timestamp),
    )
    for order, url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, '', ?, ?)",
            (gp_id, group_id, url, order, image_type),
        )
    conn.commit()
    return gp_id


def _static_config(*, tenx24_scenes=False):
    """The real static config, with 10x24 authored-scene-less by default so the publish
    gate has exactly one secondary group to wait on (group_mockup never creates a row
    for a group_type with no scenes, so the gate must not wait on one either)."""
    static_config = config.load_static_config()
    if tenx24_scenes:
        return static_config
    return {
        **static_config,
        "mockup_templates": {
            **static_config["mockup_templates"],
            "10x24": {"portrait": [], "landscape": []},
        },
    }


def _ready_candidate(conn, tmp_path=None):
    """Primary group approved and rendered, 5x7 group rendered and awaiting its tap.
    Approving or rejecting the 5x7 group is therefore the last decision the candidate
    is waiting on, and the gate fires."""
    candidate_id = _insert_candidate(conn)
    primary_group_id = _insert_group(
        conn, candidate_id, "primary", status="pending_review", decision="approved",
    )
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    gp_id = _add_group_contribution(conn, candidate_id, primary_group_id, "8x12", price_eur=24)
    _add_group_contribution(conn, candidate_id, group_id, "5x7")
    _insert_listing_text(conn, candidate_id)
    return {"candidate_id": candidate_id, "primary_group_id": primary_group_id,
            "group_id": group_id, "gp_id": gp_id}


# --- approve: settles one group, then the gate decides whether to publish ---

def test_handle_decision_approve_publishes_the_candidates_one_listing(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               return_value={"group_product_id": ctx["gp_id"], "gelato_product_id": "gp-1"}), \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               return_value="etsy-listing-777") as mock_patch:
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "approve",
            static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_patch.assert_called_once()
    # v4.12: patched once, for the CANDIDATE's listing record - not per group, and with
    # no group_type argument (one listing, one shipping profile).
    assert mock_patch.call_args.args[1] == ctx["gp_id"]
    assert result["action"] == "approve"
    assert result["published"] is True
    assert result["etsy_listing_id"] == "etsy-listing-777"

    group_row = conn.execute(
        "SELECT decision, status, decided_at FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()
    assert group_row["decision"] == "approved"
    assert group_row["status"] == "approved_published"
    assert group_row["decided_at"] == "2026-07-13T12:00:00"
    # The primary group publishes in the same call - it is the same listing.
    assert conn.execute(
        "SELECT status FROM groups WHERE id = ?", (ctx["primary_group_id"],)
    ).fetchone()["status"] == "approved_published"
    assert conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (ctx["candidate_id"],)
    ).fetchone()["status"] == "completed"
    conn.close()


def test_handle_decision_approve_waits_while_another_group_is_undecided(tmp_path):
    # [D1]: approving a secondary group settles that group and nothing else. The
    # candidate's listing is created ONCE, when every group has a terminal decision -
    # GL-22a Q2 proved a variant cannot be added to a product afterwards, so publishing
    # early would permanently forfeit the still-undecided group's size.
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)
    tenx24_id = _insert_group(conn, ctx["candidate_id"], "10x24", status="pending_review")
    _add_group_contribution(conn, ctx["candidate_id"], tenx24_id, "10x24", price_eur=45)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product") as mock_create, \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing") as mock_patch:
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "approve",
            static_config=_static_config(tenx24_scenes=True), dry_run=True,
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_create.assert_not_called()
    mock_patch.assert_not_called()
    assert result["published"] is False
    assert result["waiting_on"] == ["10x24"]
    # The decision is still durably recorded - the tap is never lost.
    assert conn.execute(
        "SELECT decision FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()["decision"] == "approved"
    conn.close()


def test_handle_decision_approve_marks_included_groups_publish_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               side_effect=RuntimeError("gelato down")):
        with pytest.raises(RuntimeError, match="gelato down"):
            publish_group.handle_decision(
                conn, ctx["candidate_id"], ctx["group_id"], "approve",
                static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
            )

    rows = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? ORDER BY id", (ctx["candidate_id"],)
    ).fetchall()
    assert [r["status"] for r in rows] == ["publish_failed", "publish_failed"]
    conn.close()


def test_handle_decision_approve_retries_publish_once_then_succeeds(tmp_path):
    # H1: a transient Gelato/Etsy hiccup shouldn't dead-end the candidate on one miss.
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               return_value={"group_product_id": ctx["gp_id"], "gelato_product_id": "gp-1"}), \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               side_effect=[RuntimeError("etsy hiccup"), "etsy-listing-recovered"]) as mock_patch:
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "approve",
            static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert mock_patch.call_count == 2
    assert result["etsy_listing_id"] == "etsy-listing-recovered"
    assert conn.execute(
        "SELECT status FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()["status"] == "approved_published"
    conn.close()


def test_handle_decision_approve_records_the_decision_even_when_publish_fails_twice(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               return_value={"group_product_id": ctx["gp_id"], "gelato_product_id": "gp-1"}), \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               side_effect=RuntimeError("etsy down")) as mock_patch:
        with pytest.raises(RuntimeError, match="etsy down"):
            publish_group.handle_decision(
                conn, ctx["candidate_id"], ctx["group_id"], "approve",
                static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
            )

    assert mock_patch.call_count == 2
    group_row = conn.execute(
        "SELECT decision, status FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()
    assert group_row["decision"] == "approved"  # tap consumed, decision recorded
    assert group_row["status"] == "publish_failed"
    conn.close()


# --- reject / edit: mark and exclude, delete nothing shared ---

def test_handle_decision_reject_deletes_nothing_shared(tmp_path):
    # The core v4.12 guarantee: rejecting a secondary group must leave the shared
    # product/listing and every other group's variants and images untouched. Under
    # v4.11 this deleted the Gelato product outright.
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)
    conn.execute(
        "UPDATE group_products SET gelato_product_id = 'gelato_shared' WHERE id = ?", (ctx["gp_id"],)
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               return_value={"group_product_id": ctx["gp_id"], "gelato_product_id": "gelato_shared"}), \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               return_value="etsy-listing-777"):
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "reject", "not vibing with this crop",
            static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_not_called()
    assert result["action"] == "reject"

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()
    assert group_row["decision"] == "rejected"
    assert group_row["decision_notes"] == "not vibing with this crop"
    assert group_row["status"] == "rejected"

    # The shared listing record survives, and so does the primary group's contribution.
    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (ctx["gp_id"],)).fetchone() is not None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM product_images WHERE group_id = ?", (ctx["primary_group_id"],)
    ).fetchone()["n"] == 2
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_id = ?",
        (ctx["primary_group_id"],),
    ).fetchone()["n"] == 1
    conn.close()


def test_handle_decision_reject_can_be_the_last_decision_and_publishes(tmp_path):
    # A rejection settles a group just as an approval does, so it can be what releases
    # the publish gate - the listing then carries only the sizes that passed.
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with patch("pipeline.publish_primary_group.group_product.create_candidate_gelato_product",
               return_value={"group_product_id": ctx["gp_id"], "gelato_product_id": "gp-1"}), \
         patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               return_value="etsy-listing-777"):
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "reject",
            static_config=_static_config(), dry_run=True, now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["published"] is True
    # The rejected group is excluded from the listing, not published with it.
    assert conn.execute(
        "SELECT status FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()["status"] == "rejected"
    assert conn.execute(
        "SELECT status FROM groups WHERE id = ?", (ctx["primary_group_id"],)
    ).fetchone()["status"] == "approved_published"
    conn.close()


def test_handle_decision_reject_with_no_contribution_still_marks_rejected(tmp_path):
    # A group whose render never produced anything can still be rejected.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with patch("pipeline.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "reject", static_config=_static_config(),
        )

    mock_delete.assert_not_called()
    assert result["action"] == "reject"
    assert conn.execute(
        "SELECT status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()["status"] == "rejected"
    conn.close()


def test_handle_decision_edit_drops_only_this_groups_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, ctx["group_id"], 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) "
        "VALUES (?, 202, '987654321', '2026-07-13T09:15:00')",
        (ctx["group_id"],),
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, ctx["candidate_id"], ctx["group_id"], "edit", "crop feels too tight",
            static_config=_static_config(), now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_not_called()
    assert result["action"] == "edit"

    # The shared listing record survives; only this group's gallery is cleared so the
    # re-render lands in a clean slot. Its variant rows stay - the sizes didn't change.
    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (ctx["gp_id"],)).fetchone() is not None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM product_images WHERE group_id = ?", (ctx["group_id"],)
    ).fetchone()["n"] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM product_images WHERE group_id = ?", (ctx["primary_group_id"],)
    ).fetchone()["n"] == 2
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (ctx["group_id"],)
    ).fetchall() == []
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (ctx["group_id"],)
    ).fetchall() == []

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (ctx["group_id"],)
    ).fetchone()
    assert group_row["decision"] == "edited"
    assert group_row["decision_notes"] == "crop feels too tight"
    assert group_row["status"] == "pending_review"  # left as-is, confirmed with user
    conn.close()


def test_handle_decision_edit_with_no_contribution_still_clears_attempts(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "off-center"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )

    with patch("pipeline.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(conn, candidate_id, group_id, "edit")

    mock_delete.assert_not_called()
    assert result["action"] == "edit"
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    conn.close()


def test_get_live_group_product_resolves_through_the_candidate(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)
    # The listing record was opened by the PRIMARY group, but the 5x7 group resolves it
    # too - it belongs to the candidate, not to whichever group created it.
    assert publish_group.get_live_group_product(conn, ctx["group_id"])["id"] == ctx["gp_id"]
    conn.close()


def test_get_live_group_product_raises_when_the_candidate_has_no_record(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with pytest.raises(ValueError, match="No live group_product"):
        publish_group.get_live_group_product(conn, group_id)
    conn.close()


def test_handle_decision_raises_on_unknown_action(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _ready_candidate(conn)

    with pytest.raises(ValueError, match="Unknown action"):
        publish_group.handle_decision(conn, ctx["candidate_id"], ctx["group_id"], "snooze")
    conn.close()
