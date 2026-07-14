# Group Digest (stage 10/12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/group_digest.py` — sends the follow-up Telegram digest
entry (gallery + text/buttons) for a 5x7 or 10x24 group once it has passed its own
critic pass, logging the sent message via `group_messages`.

**Architecture:** Mirrors `pipeline/digest.py`'s primary-group digest exactly, but
scoped to `group_id` instead of `candidate_id`. Reuses two of `digest.py`'s
functions unmodified via import (`get_listing_text`, `build_digest_keyboard`) since
they're already generic on `group_id`/`candidate_id`. Four new functions:
`get_review_group`, `get_group_gallery_urls`, `build_group_digest_message_text`,
`send_group_digest`, plus the `run_group_digest_cycle` batch entrypoint.

**Tech Stack:** Python, sqlite3 (via `pipeline/db.py`), `pytest` +
`unittest.mock.patch` for the Telegram seam — same as `tests/test_digest.py`.

## Global Constraints

- Telegram digest = `sendMediaGroup` (gallery) + separate `sendMessage` (text +
  buttons), one pair per digest entry — never one combined call (CLAUDE.md hard
  constraint).
- Every outbound Telegram call targets the chat_id resolved from
  `TELEGRAM_ADMIN_CHAT_ID` (`.env`), same as `digest.py`.
- `groups.status` stays `'pending_review'` through both "mockup created, not yet
  critic-passed" and "critic-passed, awaiting digest" — a passing
  `critic_pass_attempts` row is what distinguishes the two states for selection.
- No new tables/columns. Reuses `groups`, `group_products`, `product_images`,
  `listing_texts`, `critic_pass_attempts`, `group_messages`.
- This stage never touches `candidates.status`, `groups.decision`, or the critic
  pass itself — those belong to stages 9 and 11.

---

### Task 1: `get_review_group` and `get_group_gallery_urls`

**Files:**
- Create: `pipeline/group_digest.py`
- Test: `tests/test_group_digest.py`

**Interfaces:**
- Consumes: `pipeline/db.py`'s `get_connection`/`init_db` (test fixtures only);
  schema tables `groups`, `group_products`, `product_images` (see
  `db/schema.sql`).
- Produces:
  - `get_review_group(conn, group_id: int) -> dict` — returns
    `{"candidate_id": int, "group_type": str, "price_eur": float}`. Raises
    `ValueError` if no live (`group_products.status = 'created'`) row exists for
    that group.
  - `get_group_gallery_urls(conn, group_id: int) -> list[str]` — ordered by
    `product_images.gallery_order`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_group_digest.py`:

```python
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_digest as group_digest


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-14T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_gallery(conn, candidate_id, group_type, size, *,
                           image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                           price_eur=19, group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-14T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, group_status, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_1', 'gelato_prod_1', ?, ?, ?, ?)",
        (group_id, size, price_eur, group_product_status, timestamp, timestamp),
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
    timestamp = "2026-07-14T09:10:00"
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


def _insert_critic_pass(conn, group_id, *, attempt_number=1, passed=1):
    timestamp = "2026-07-14T09:15:00"
    conn.execute(
        "INSERT INTO critic_pass_attempts (group_id, attempt_number, passed, created_at) "
        "VALUES (?, ?, ?, ?)",
        (group_id, attempt_number, passed, timestamp),
    )
    conn.commit()


def test_get_review_group_returns_candidate_type_and_price(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7", price_eur=19)

    result = group_digest.get_review_group(conn, group_id)

    assert result == {"candidate_id": candidate_id, "group_type": "5x7", "price_eur": 19}
    conn.close()


def test_get_review_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "5x7", "5x7", group_product_status="mockup_failed",
    )

    with pytest.raises(ValueError, match="group_product"):
        group_digest.get_review_group(conn, group_id)
    conn.close()


def test_get_group_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "10x24", "10x24",
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = group_digest.get_group_gallery_urls(conn, group_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_digest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.group_digest'`

- [ ] **Step 3: Write minimal implementation**

Create `pipeline/group_digest.py`:

```python
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.digest as digest
import pipeline.telegram_client as telegram_client


def get_review_group(conn, group_id: int) -> dict:
    row = conn.execute(
        """
        SELECT g.candidate_id AS candidate_id, g.group_type AS group_type, gp.price_eur AS price_eur
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live group_product for group {group_id}")
    return dict(row)


def get_group_gallery_urls(conn, group_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.image_url
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id AND gp.status = 'created'
        WHERE gp.group_id = ?
        ORDER BY pi.gallery_order
        """,
        (group_id,),
    ).fetchall()
    return [row["image_url"] for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_digest.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_digest.py tests/test_group_digest.py
git commit -m "feat: add get_review_group and get_group_gallery_urls to group_digest"
```

---

### Task 2: `build_group_digest_message_text`

**Files:**
- Modify: `pipeline/group_digest.py`
- Test: `tests/test_group_digest.py`

**Interfaces:**
- Consumes: nothing new — pure function over a `listing_text` dict shaped like
  `digest.get_listing_text`'s return value (`title`, `tags` as JSON string,
  `description`, `disclosure_text`).
- Produces: `build_group_digest_message_text(candidate_id: int, group_id: int, group_type: str, listing_text: dict, price_eur: float) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_group_digest.py`:

```python
def test_build_group_digest_message_text_includes_group_type_and_price():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "tags": _json.dumps(["botanical", "wall art"]),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
    }

    text = group_digest.build_group_digest_message_text(7, 42, "5x7", listing_text, 19)

    assert "Candidate #7" in text
    assert "5x7 group" in text
    assert "#42" in text
    assert "Monstera Line Art Botanical Print" in text
    assert "A minimalist botanical print." in text
    assert "botanical, wall art" in text
    assert "AI disclosure text." in text
    assert "19" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_group_digest.py::test_build_group_digest_message_text_includes_group_type_and_price -v`
Expected: FAIL with `AttributeError: module 'pipeline.group_digest' has no attribute 'build_group_digest_message_text'`

- [ ] **Step 3: Write minimal implementation**

Add to `pipeline/group_digest.py` (after `get_group_gallery_urls`, needs `import json` at the top):

```python
import json
```

```python
def build_group_digest_message_text(candidate_id: int, group_id: int, group_type: str,
                                     listing_text: dict, price_eur: float) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    return (
        f"Candidate #{candidate_id} — {group_type} group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"{listing_text['disclosure_text']}\n\n"
        f"Price: €{price_eur}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_group_digest.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_digest.py tests/test_group_digest.py
git commit -m "feat: add build_group_digest_message_text to group_digest"
```

---

### Task 3: `send_group_digest`

**Files:**
- Modify: `pipeline/group_digest.py`
- Test: `tests/test_group_digest.py`

**Interfaces:**
- Consumes: `get_review_group`, `get_group_gallery_urls`,
  `build_group_digest_message_text` (Task 1/2); `digest.get_listing_text(conn, candidate_id) -> dict`;
  `digest.build_digest_keyboard(group_id) -> dict`; `telegram_client.send_media_group(chat_id, photo_urls, *, bot_token=None) -> dict`;
  `telegram_client.send_message(chat_id, text, reply_markup=None, *, bot_token=None) -> dict`;
  `config.require_env(name) -> str`.
- Produces: `send_group_digest(conn, group_id: int, *, static_config=None, bot_token=None, chat_id=None, now=None) -> dict`
  returning `{"candidate_id": int, "group_id": int, "telegram_message_id": int}`.
  Inserts one row into `group_messages`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_group_digest.py`:

```python
def test_send_group_digest_sends_media_group_then_message_and_persists_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7", price_eur=19)
    _insert_listing_text(conn, candidate_id)

    calls = []

    def fake_send_media_group(chat_id, photo_urls, *, bot_token=None):
        calls.append(("media_group", chat_id, photo_urls, bot_token))
        return {"ok": True, "result": [{"message_id": 100}, {"message_id": 101}]}

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        calls.append(("message", chat_id, text, reply_markup, bot_token))
        return {"ok": True, "result": {"message_id": 202}}

    with patch("pipeline.group_digest.telegram_client.send_media_group", side_effect=fake_send_media_group), \
         patch("pipeline.group_digest.telegram_client.send_message", side_effect=fake_send_message):
        result = group_digest.send_group_digest(
            conn, group_id, bot_token="test-token", chat_id="admin-chat",
            now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert result == {
        "candidate_id": candidate_id, "group_id": group_id, "telegram_message_id": 202,
    }

    assert calls[0][0] == "media_group"
    assert calls[0][1] == "admin-chat"
    assert calls[0][2] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert calls[1][0] == "message"
    assert calls[1][1] == "admin-chat"
    assert f"Candidate #{candidate_id}" in calls[1][2]
    assert "5x7 group" in calls[1][2]
    assert calls[1][3]["inline_keyboard"][0][0]["callback_data"] == f"approve:{group_id}"

    message_row = conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchone()
    assert message_row["telegram_message_id"] == 202
    assert message_row["chat_id"] == "admin-chat"
    assert message_row["sent_at"] == "2026-07-14T09:30:00"
    conn.close()


def test_send_group_digest_uses_env_chat_id_when_not_passed(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "env-admin-chat")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "10x24", "10x24")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}) as mock_media, \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 5}}) as mock_message:
        group_digest.send_group_digest(conn, group_id, bot_token="test-token")

    assert mock_media.call_args.args[0] == "env-admin-chat"
    assert mock_message.call_args.args[0] == "env-admin-chat"
    conn.close()


def test_send_group_digest_raises_and_writes_no_row_when_listing_text_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7")  # no listing_texts row

    with patch("pipeline.group_digest.telegram_client.send_media_group") as mock_media, \
         patch("pipeline.group_digest.telegram_client.send_message") as mock_message:
        with pytest.raises(ValueError, match="listing_texts"):
            group_digest.send_group_digest(conn, group_id, bot_token="test-token", chat_id="admin-chat")

    mock_media.assert_not_called()
    mock_message.assert_not_called()
    assert conn.execute("SELECT * FROM group_messages").fetchall() == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_digest.py -k send_group_digest -v`
Expected: FAIL with `AttributeError: module 'pipeline.group_digest' has no attribute 'send_group_digest'`

- [ ] **Step 3: Write minimal implementation**

Add to `pipeline/group_digest.py`:

```python
def send_group_digest(conn, group_id: int, *, static_config: dict = None,
                       bot_token: str = None, chat_id: str = None, now=None) -> dict:
    review_group = get_review_group(conn, group_id)
    candidate_id = review_group["candidate_id"]
    group_type = review_group["group_type"]
    price_eur = review_group["price_eur"]

    photo_urls = get_group_gallery_urls(conn, group_id)
    listing_text = digest.get_listing_text(conn, candidate_id)
    chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)

    text = build_group_digest_message_text(candidate_id, group_id, group_type, listing_text, price_eur)
    reply_markup = digest.build_digest_keyboard(group_id)
    response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
    telegram_message_id = response["result"]["message_id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, telegram_message_id, chat_id, timestamp),
    )
    conn.commit()

    return {"candidate_id": candidate_id, "group_id": group_id,
            "telegram_message_id": telegram_message_id}
```

Note: `get_listing_text` raises before any `group_messages` row is written only if
it's called before the DB insert — confirm the call order above keeps
`digest.get_listing_text` ahead of both Telegram calls and the insert (it does).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_digest.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_digest.py tests/test_group_digest.py
git commit -m "feat: add send_group_digest to group_digest"
```

---

### Task 4: `run_group_digest_cycle`

**Files:**
- Modify: `pipeline/group_digest.py`
- Test: `tests/test_group_digest.py`

**Interfaces:**
- Consumes: `send_group_digest` (Task 3); schema tables `groups`, `group_products`,
  `critic_pass_attempts`, `group_messages`.
- Produces: `run_group_digest_cycle(conn, *, static_config=None, bot_token=None, chat_id=None, now=None) -> list[int]`
  — list of `group_id`s successfully digested this run.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_group_digest.py`:

```python
def _insert_ready_group(conn, niche, group_type, size, *, price_eur=19):
    candidate_id = _insert_candidate(conn, niche=niche)
    group_id, _ = _insert_group_gallery(conn, candidate_id, group_type, size, price_eur=price_eur)
    _insert_listing_text(conn, candidate_id, niche=niche)
    _insert_critic_pass(conn, group_id, passed=1)
    return candidate_id, group_id


def test_run_group_digest_cycle_processes_critic_passed_groups(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, ready_group_id = _insert_ready_group(conn, "monstera line art", "5x7", "5x7")

    not_passed_candidate_id = _insert_candidate(conn, niche="pending crop")
    not_passed_group_id, _ = _insert_group_gallery(conn, not_passed_candidate_id, "10x24", "10x24")
    _insert_listing_text(conn, not_passed_candidate_id, niche="pending crop")
    # no critic_pass_attempts row -> not yet critic-passed

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        processed_ids = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert processed_ids == [ready_group_id]
    assert not_passed_group_id not in processed_ids
    conn.close()


def test_run_group_digest_cycle_skips_groups_already_digested(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, group_id = _insert_ready_group(conn, "monstera line art", "5x7", "5x7")

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        first_run = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )
        second_run = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 10, 0, 0),
        )

    assert first_run == [group_id]
    assert second_run == []
    conn.close()


def test_run_group_digest_cycle_isolates_per_group_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, failing_group_id = _insert_ready_group(conn, "saturated term", "5x7", "5x7")
    _, succeeding_group_id = _insert_ready_group(conn, "moon phase print", "10x24", "10x24")

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        if "saturated term" in text:
            raise RuntimeError("Telegram throttled")
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message", side_effect=fake_send_message):
        processed_ids = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert processed_ids == [succeeding_group_id]
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (failing_group_id,)
    ).fetchone() is None
    conn.close()


def test_run_group_digest_cycle_ignores_primary_groups(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    primary_group_id, _ = _insert_group_gallery(conn, candidate_id, "primary", "8x12", price_eur=24)
    _insert_listing_text(conn, candidate_id)
    _insert_critic_pass(conn, primary_group_id, passed=1)

    processed_ids = group_digest.run_group_digest_cycle(
        conn, bot_token="test-token", chat_id="admin-chat",
    )

    assert processed_ids == []
    conn.close()


def test_run_group_digest_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="generating")

    processed_ids = group_digest.run_group_digest_cycle(conn, bot_token="test-token", chat_id="admin-chat")

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_digest.py -k run_group_digest_cycle -v`
Expected: FAIL with `AttributeError: module 'pipeline.group_digest' has no attribute 'run_group_digest_cycle'`

- [ ] **Step 3: Write minimal implementation**

Add to `pipeline/group_digest.py`:

```python
def run_group_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None,
                            chat_id: str = None, now=None) -> list:
    group_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT g.id
            FROM groups g
            JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
            WHERE g.group_type IN ('5x7', '10x24')
              AND g.status = 'pending_review'
              AND g.id IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
              AND g.id NOT IN (SELECT group_id FROM group_messages)
            ORDER BY g.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for group_id in group_ids:
        try:
            send_group_digest(
                conn, group_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now,
            )
        except Exception as exc:
            print(f"send_group_digest failed for group {group_id}: {exc}")
            continue
        processed_ids.append(group_id)
    return processed_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_digest.py -v`
Expected: 12 passed

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `python -m pytest -v`
Expected: all tests pass (prior stages' suites + the 12 new ones)

- [ ] **Step 6: Commit**

```bash
git add pipeline/group_digest.py tests/test_group_digest.py
git commit -m "feat: add run_group_digest_cycle batch entrypoint for stage 10/12"
```
