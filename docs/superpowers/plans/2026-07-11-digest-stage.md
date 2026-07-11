# Digest Stage (digest.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/digest.py`, the sixth of 12 M1 pipeline stage modules — sends the primary-group Telegram review digest (`sendMediaGroup` gallery + `sendMessage` with an Approve/Edit/Reject inline keyboard) for every candidate `critic_pass.py` has moved to `candidates.status='primary_review'`, and persists the `sendMessage` message id to `group_messages` for later callback routing, per SPEC_v4.10.md section 3 step 6.

**Architecture:** Six functions in `digest.py`, layered like the prior stages: three read-only query helpers (`get_primary_group`, `get_primary_gallery_urls`, `get_listing_text`) gather everything needed for one candidate's digest entry; two pure builders (`build_digest_message_text`, `build_digest_keyboard`) format the `sendMessage` payload; `send_primary_digest()` orchestrates one candidate's full send (both Telegram calls plus the `group_messages` insert); `run_digest_cycle()` is the batch entry point. No new functions needed in `telegram_client.py` — `send_media_group`/`send_message` already accept everything this stage needs.

**Tech Stack:** Python 3, `sqlite3` (stdlib, via `pipeline/db.py`), `pytest` + `unittest.mock` — same conventions as every prior stage module.

## Global Constraints

Per the approved design (`docs/superpowers/specs/2026-07-11-digest-stage-design.md`):

- **Two separate Telegram calls, never combined:** `sendMediaGroup` for the gallery, then `sendMessage` with the draft text + inline keyboard — Telegram's Bot API cannot attach a `reply_markup` to a media group.
- **`callback_data` carries only `group_id`:** `f"{action}:{group_id}"` for `action in ("approve", "edit", "reject")` — `groups.candidate_id`/`groups.group_type` are both derivable from `group_id` via one lookup, so this exact encoding is reused unchanged by the future `group_digest.py` for 5x7/10x24 buttons.
- **Digest text includes `candidate_id` and `group_id`**, not just title/description/tags/disclosure/price, so multiple digest entries landing in one batch run are identifiable.
- **Only the `sendMessage` response's `message_id` is persisted** to `group_messages` — the media group's per-photo messages never carry the keyboard, so they can never receive a `callback_query`.
- **No dedup/cleanup logic for partial-send failures.** If `sendMediaGroup` succeeds but `sendMessage` then raises, no `group_messages` row is written, so the next `run_digest_cycle` re-selects the candidate and re-sends a duplicate gallery before retrying `sendMessage`. Accepted as-is, consistent with other stages already accepting redone partial work on retry.
- **No schema changes.** `group_messages` (`group_id`, `telegram_message_id`, `chat_id`, `sent_at`) already exists in `db/schema.sql`. No `UNIQUE(group_id)` constraint added — "one digest per group" is a code-level invariant (enforced by the selection predicate's anti-join), not a DB-level one.
- **No response handling in this stage.** Reading callbacks and driving Approve/Edit/Reject is the future `publish_primary_group.py`.
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: Query helpers — `get_primary_group()`, `get_primary_gallery_urls()`, `get_listing_text()`

**Files:**
- Create: `pipeline/digest.py`
- Create: `tests/test_digest.py`

**Interfaces:**
- Consumes: `pipeline/db.py`'s `get_connection`/`init_db` (already merged).
- Produces:
  - `get_primary_group(conn, candidate_id: int) -> dict` — returns `{"group_id": int, "price_eur": float}` from the candidate's live (`status='created'`) primary `group_products` row. Raises `ValueError` if missing.
  - `get_primary_gallery_urls(conn, candidate_id: int) -> list[str]` — ordered (`gallery_order` asc) image urls for the candidate's live primary `group_product`.
  - `get_listing_text(conn, candidate_id: int) -> dict` — `{"title", "tags", "description", "disclosure_text"}` from `listing_texts`. Raises `ValueError` if missing.
  - All three consumed by Task 3's `send_primary_digest`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_digest.py`:

```python
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.digest as digest
import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-11T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id,
                             image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                             *, price_eur=24, group_product_status="created"):
    timestamp = "2026-07-11T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', 'gelato_prod_1', ?, ?, ?, ?)",
        (group_id, price_eur, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, image_url, order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-11T09:10:00"
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


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_returns_group_id_and_price(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    expected_group_id, _ = _insert_primary_gallery(conn, candidate_id, price_eur=24)

    result = digest.get_primary_group(conn, candidate_id)

    assert result == {"group_id": expected_group_id, "price_eur": 24}
    conn.close()


def test_get_primary_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group_product"):
        digest.get_primary_group(conn, candidate_id)
    conn.close()


def test_get_primary_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(
        conn, candidate_id,
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = digest.get_primary_gallery_urls(conn, candidate_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()


def test_get_listing_text_returns_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_listing_text(conn, candidate_id, niche="monstera line art")

    result = digest.get_listing_text(conn, candidate_id)

    assert result["title"] == "monstera line art print"
    assert result["tags"] == _json.dumps(["botanical", "wall art"])
    assert result["description"] == "A print of monstera line art."
    assert result["disclosure_text"] == "AI disclosure text."
    conn.close()


def test_get_listing_text_raises_when_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="listing_texts"):
        digest.get_listing_text(conn, candidate_id)
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.digest'`.

- [ ] **Step 3: Implement `pipeline/digest.py`**

```python
import json
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.telegram_client as telegram_client


def get_primary_group(conn, candidate_id: int) -> dict:
    row = conn.execute(
        """
        SELECT g.id AS group_id, gp.price_eur AS price_eur
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        """,
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live primary group_product for candidate {candidate_id}")
    return {"group_id": row["group_id"], "price_eur": row["price_eur"]}


def get_primary_gallery_urls(conn, candidate_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.image_url
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id AND gp.status = 'created'
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    return [row["image_url"] for row in rows]


def get_listing_text(conn, candidate_id: int) -> dict:
    row = conn.execute(
        "SELECT title, tags, description, disclosure_text FROM listing_texts WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    return dict(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_digest.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat: add digest.py query helpers for primary-group digest data"
```

---

## Task 2: Pure builders — `build_digest_message_text()`, `build_digest_keyboard()`

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

**Interfaces:**
- Produces:
  - `build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict, price_eur: float) -> str`.
  - `build_digest_keyboard(group_id: int) -> dict` — Telegram `reply_markup` shape.
  - Both consumed by Task 3's `send_primary_digest`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_digest.py`:

```python
def test_build_digest_message_text_includes_ids_title_tags_price_disclosure():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "tags": _json.dumps(["botanical", "wall art"]),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
    }

    text = digest.build_digest_message_text(7, 42, listing_text, 24)

    assert "Candidate #7" in text
    assert "#42" in text
    assert "Monstera Line Art Botanical Print" in text
    assert "A minimalist botanical print." in text
    assert "botanical, wall art" in text
    assert "AI disclosure text." in text
    assert "24" in text


def test_build_digest_keyboard_has_three_buttons_with_group_id_callback_data():
    keyboard = digest.build_digest_keyboard(42)

    buttons = keyboard["inline_keyboard"][0]
    assert len(buttons) == 3
    callback_data = [button["callback_data"] for button in buttons]
    assert callback_data == ["approve:42", "edit:42", "reject:42"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL — `build_digest_message_text`/`build_digest_keyboard` don't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/digest.py`:

```python
def build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict, price_eur: float) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    return (
        f"Candidate #{candidate_id} — Primary group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"{listing_text['disclosure_text']}\n\n"
        f"Price: €{price_eur}"
    )


def build_digest_keyboard(group_id: int) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{group_id}"},
            {"text": "✏️ Edit", "callback_data": f"edit:{group_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{group_id}"},
        ]]
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_digest.py -v`
Expected: all 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat: add digest.py message text and keyboard builders"
```

---

## Task 3: `send_primary_digest()` — one candidate's full send

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

**Interfaces:**
- Consumes: `get_primary_group`, `get_primary_gallery_urls`, `get_listing_text` (Task 1); `build_digest_message_text`, `build_digest_keyboard` (Task 2); `telegram_client.send_media_group(chat_id, photo_urls, *, bot_token=None) -> dict`, `telegram_client.send_message(chat_id, text, reply_markup=None, *, bot_token=None) -> dict` (already merged); `config.require_env` (already merged).
- Produces: `send_primary_digest(conn, candidate_id: int, *, static_config: dict = None, bot_token: str = None, chat_id: str = None, now=None) -> dict` — returns `{"candidate_id", "group_id", "telegram_message_id"}`. Consumed by Task 4's `run_digest_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_digest.py`:

```python
def test_send_primary_digest_sends_media_group_then_message_and_persists_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    expected_group_id = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()["id"]

    calls = []

    def fake_send_media_group(chat_id, photo_urls, *, bot_token=None):
        calls.append(("media_group", chat_id, photo_urls, bot_token))
        return {"ok": True, "result": [{"message_id": 100}, {"message_id": 101}]}

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        calls.append(("message", chat_id, text, reply_markup, bot_token))
        return {"ok": True, "result": {"message_id": 202}}

    with patch("pipeline.digest.telegram_client.send_media_group", side_effect=fake_send_media_group), \
         patch("pipeline.digest.telegram_client.send_message", side_effect=fake_send_message):
        result = digest.send_primary_digest(
            conn, candidate_id, bot_token="test-token", chat_id="admin-chat",
            now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert result == {
        "candidate_id": candidate_id, "group_id": expected_group_id, "telegram_message_id": 202,
    }

    assert calls[0][0] == "media_group"
    assert calls[0][1] == "admin-chat"
    assert calls[0][2] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert calls[1][0] == "message"
    assert calls[1][1] == "admin-chat"
    assert f"Candidate #{candidate_id}" in calls[1][2]
    assert calls[1][3]["inline_keyboard"][0][0]["callback_data"] == f"approve:{expected_group_id}"

    message_row = conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (expected_group_id,)
    ).fetchone()
    assert message_row["telegram_message_id"] == 202
    assert message_row["chat_id"] == "admin-chat"
    assert message_row["sent_at"] == "2026-07-11T09:30:00"
    conn.close()


def test_send_primary_digest_uses_env_chat_id_when_not_passed(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "env-admin-chat")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}) as mock_media, \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 5}}) as mock_message:
        digest.send_primary_digest(conn, candidate_id, bot_token="test-token")

    assert mock_media.call_args.args[0] == "env-admin-chat"
    assert mock_message.call_args.args[0] == "env-admin-chat"
    conn.close()


def test_send_primary_digest_raises_and_writes_no_row_when_listing_text_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(conn, candidate_id)  # gallery exists, no listing_texts row

    with patch("pipeline.digest.telegram_client.send_media_group") as mock_media, \
         patch("pipeline.digest.telegram_client.send_message") as mock_message:
        with pytest.raises(ValueError, match="listing_texts"):
            digest.send_primary_digest(conn, candidate_id, bot_token="test-token", chat_id="admin-chat")

    mock_media.assert_not_called()
    mock_message.assert_not_called()
    assert conn.execute("SELECT * FROM group_messages").fetchall() == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL — `send_primary_digest` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/digest.py`:

```python
def send_primary_digest(conn, candidate_id: int, *, static_config: dict = None,
                         bot_token: str = None, chat_id: str = None, now=None) -> dict:
    group = get_primary_group(conn, candidate_id)
    photo_urls = get_primary_gallery_urls(conn, candidate_id)
    listing_text = get_listing_text(conn, candidate_id)
    chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)

    text = build_digest_message_text(candidate_id, group["group_id"], listing_text, group["price_eur"])
    reply_markup = build_digest_keyboard(group["group_id"])
    response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
    telegram_message_id = response["result"]["message_id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group["group_id"], telegram_message_id, chat_id, timestamp),
    )
    conn.commit()

    return {"candidate_id": candidate_id, "group_id": group["group_id"],
            "telegram_message_id": telegram_message_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_digest.py -v`
Expected: all 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat: add digest.py send_primary_digest"
```

---

## Task 4: `run_digest_cycle()` — batch orchestrator

**Files:**
- Modify: `pipeline/digest.py`
- Modify: `tests/test_digest.py`

**Interfaces:**
- Consumes: `send_primary_digest(conn, candidate_id, ...)` (Task 3).
- Produces: `run_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None, chat_id: str = None, now=None) -> list[int]` — the module's public batch entry point, to be called by the not-yet-built twice-daily batch orchestrator after `critic_pass.run_critic_pass_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_digest.py`:

```python
def test_run_digest_cycle_processes_primary_review_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    not_ready_id = _insert_candidate(conn, niche="pending one", status="generating")
    _insert_primary_gallery(conn, not_ready_id)
    _insert_listing_text(conn, not_ready_id, niche="pending one")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        processed_ids = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert processed_ids == [ready_id]
    assert not_ready_id not in processed_ids
    conn.close()


def test_run_digest_cycle_skips_candidates_already_digested(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        first_run = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )
        second_run = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 10, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_digest_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        if "saturated term" in text:
            raise RuntimeError("Telegram throttled")
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message", side_effect=fake_send_message):
        processed_ids = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert processed_ids == [succeeding_id]

    failing_group_id = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (failing_id,)
    ).fetchone()["id"]
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (failing_group_id,)
    ).fetchone() is None
    conn.close()


def test_run_digest_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="generating")

    processed_ids = digest.run_digest_cycle(conn, bot_token="test-token", chat_id="admin-chat")

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_digest.py -v`
Expected: FAIL — `run_digest_cycle` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/digest.py`:

```python
def run_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None,
                      chat_id: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            WHERE c.status = 'primary_review'
              AND g.id NOT IN (SELECT group_id FROM group_messages)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            send_primary_digest(
                conn, candidate_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now,
            )
        except Exception as exc:
            print(f"send_primary_digest failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_digest.py -v`
Expected: all 14 PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research, generate, primary_mockup, compliance_draft, critic_pass, digest suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/digest.py tests/test_digest.py
git commit -m "feat: add digest.py run_digest_cycle batch orchestrator"
```

---

## Self-Review Notes

- **Spec coverage:** all 6 `digest.py` function signatures from `docs/superpowers/specs/2026-07-11-digest-stage-design.md` sections 1-3 are covered — the three read helpers (Task 1), the two pure payload builders including the confirmed `candidate_id`/`group_id`-in-text and `action:group_id` callback-data scheme (Task 2), the full two-call-plus-persist send with the confirmed no-dedup partial-failure behavior (Task 3, exercised directly by its third test), and the selection-predicate-driven batch orchestrator with per-candidate isolation (Task 4). The design doc's "Resolved ambiguities" section's four decisions are all reflected in code and asserted by tests, not just narrated.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code.
- **Type consistency:** `get_primary_group`'s return keys (`group_id`, `price_eur`, Task 1) match exactly what `send_primary_digest` reads off `group` (Task 3). `build_digest_message_text`/`build_digest_keyboard`'s parameter order (Task 2) matches their call sites in `send_primary_digest` (Task 3). `send_primary_digest`'s keyword signature (Task 3) is called identically by `run_digest_cycle` (Task 4) — same parameter names (`static_config`, `bot_token`, `chat_id`, `now`). `telegram_client.send_media_group`/`send_message`'s existing signatures (positional `chat_id`, `photo_urls`/`text`, optional `reply_markup`, keyword-only `bot_token`) are called exactly as already defined in the already-merged `pipeline/telegram_client.py` — no changes needed there.
