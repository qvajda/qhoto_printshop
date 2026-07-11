# Digest Stage (`digest.py`) — Design

**Status:** approved by Quentin 2026-07-11
**Scope:** `pipeline/digest.py`, the sixth of 12 M1 pipeline stage modules. Sends the
**primary-group** Telegram review digest per SPEC_v4.10.md section 3 step 6, for every
candidate `critic_pass.py` has moved to `candidates.status='primary_review'`. Two Telegram API
calls per candidate (`sendMediaGroup` then `sendMessage` with an Approve/Edit/Reject inline
keyboard), and persists the `sendMessage` message id to `group_messages` for later callback
routing.

## Non-goals

- No response handling. Reading `getUpdates`/callback-query payloads, checking the sender
  against the Telegram admin/allowlist ID, and driving the Approve/Edit/Reject decision is
  `publish_primary_group.py`, a separate future stage per CLAUDE.md's 12-stage list. This
  stage's job stops at successfully sending the digest and recording the message id.
- No 5x7/10x24 group digests. Those are `group_digest.py`, sent later in the evening run after
  primary-group approval (SPEC section 3 step 7), reusing this stage's callback-data scheme
  (see section 3) but not its code path.
- No schema changes. `group_messages` (`group_id`, `telegram_message_id`, `chat_id`, `sent_at`)
  already exists in `db/schema.sql`, built in anticipation of this stage. Confirmed (see
  "Resolved ambiguities" below): no `UNIQUE(group_id)` constraint added — "one digest per group"
  is a code-level invariant, not a DB-level one, consistent with how this codebase already
  treats similar single-row-per-parent assumptions (e.g. `listing_texts` has no
  `UNIQUE(candidate_id)` either; `critic_pass.py`'s design doc section 4 covers that precedent).

## 1. `digest.py` function signatures

```python
def get_primary_gallery_urls(conn, candidate_id: int) -> list[str]:
    """Ordered (gallery_order asc) image_urls for the candidate's primary group_product:
    flat mockup first, then lifestyle/room-context images. Raises ValueError if the candidate
    has no primary group or no live group_product."""

def get_primary_group(conn, candidate_id: int) -> dict:
    """Reads the candidate's primary groups.id and its live group_products.price_eur (the
    8x12 row). Returns {"group_id": int, "price_eur": float}. Raises ValueError if missing."""

def get_listing_text(conn, candidate_id: int) -> dict:
    """Reads the candidate's listing_texts row (title, tags, description, disclosure_text).
    Raises ValueError if missing - digest.py should never run ahead of compliance_draft.py's
    output, but fails loud rather than sending a blank message if it somehow does."""

def build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict,
                               price_eur: float) -> str:
    """Pure. Formats candidate_id + group_id (so multiple digest entries in one batch are
    identifiable), title, description, tags, disclosure_text, and price_eur into the
    sendMessage body."""

def build_digest_keyboard(group_id: int) -> dict:
    """Pure. Returns the Telegram reply_markup dict: one row, three buttons (Approve/Edit/
    Reject), callback_data f"{action}:{group_id}" for action in ("approve","edit","reject")."""

def send_primary_digest(conn, candidate_id: int, *, static_config: dict = None,
                         bot_token: str = None, chat_id: str = None, now=None) -> dict:
    """One candidate -> sendMediaGroup, then sendMessage, then persist the group_messages row.
    See section 3 for the full step-by-step flow. Returns {"candidate_id", "group_id",
    "telegram_message_id"}."""

def run_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None,
                      chat_id: str = None, now=None) -> list[int]:
    """Batch entry point (morning run, after critic_pass). Selects every candidate awaiting its
    primary digest (section 2's predicate) and calls send_primary_digest on each, isolating
    per-candidate failures with the same try/except-and-continue pattern as the other *_cycle
    functions."""
```

`static_config` is accepted for signature consistency with the other `*_cycle` stages even
though this stage doesn't currently read anything from it — no static config value is needed to
build a digest message. `chat_id` defaults to `config.require_env("TELEGRAM_ADMIN_CHAT_ID")`
when not passed, matching how `bot_token` already defaults inside `telegram_client.py`'s own
functions.

**Reads from `groups`/`group_products`/`product_images`/`listing_texts`:** the primary group's
id, price, live gallery, and draft text.
**Writes:** one `group_messages` row per successfully sent digest. No other table is touched —
this stage doesn't change `candidates.status` or `groups.status`; those only move once a
decision comes back (a future stage's job).

## Selection predicate (`run_digest_cycle`)

```sql
SELECT DISTINCT c.id FROM candidates c
JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
WHERE c.status = 'primary_review'
  AND g.id NOT IN (SELECT group_id FROM group_messages)
ORDER BY c.id
```

`c.status = 'primary_review'` is set only by `critic_pass.py` on a pass. The `group_messages`
anti-join is what makes a digest send-once: a row only exists there after `sendMessage`
succeeds (section 3), so a candidate whose digest already went out is excluded from future
cycles, and a candidate whose `sendMediaGroup` succeeded but whose `sendMessage` then failed is
correctly still selected next cycle (see "Resolved ambiguities," duplicate-gallery case).

## 2. `send_primary_digest` step-by-step

1. `get_primary_group(conn, candidate_id)` → `group_id`, `price_eur`.
2. `get_primary_gallery_urls(conn, candidate_id)` → ordered `photo_urls`.
3. `get_listing_text(conn, candidate_id)` → `listing_text`.
4. `chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")`.
5. `telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)`.
6. `text = build_digest_message_text(candidate_id, group_id, listing_text, price_eur)`.
7. `reply_markup = build_digest_keyboard(group_id)`.
8. `response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)`.
9. `INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)`
   using `response["result"]["message_id"]` and the current timestamp. Commit.
10. Return `{"candidate_id", "group_id", "telegram_message_id"}`.

**On any exception (steps 1-3, or either Telegram call):** propagate. `run_digest_cycle`
isolates it per candidate, same as every other `*_cycle` function. No partial-state cleanup is
attempted (see "Resolved ambiguities," duplicate-gallery case) — the candidate stays selectable
next cycle because no `group_messages` row was written.

## 3. Message payloads

**`sendMediaGroup`** — reuses `telegram_client.send_media_group` unchanged:
```python
telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)
# -> {"chat_id": ..., "media": [{"type": "photo", "media": url}, ...]}
```

**`sendMessage`** — text plus a 3-button inline keyboard, built by this stage:
```python
text = (
    f"Candidate #{candidate_id} — Primary group (#{group_id})\n\n"
    f"{listing_text['title']}\n\n"
    f"{listing_text['description']}\n\n"
    f"Tags: {', '.join(json.loads(listing_text['tags']))}\n\n"
    f"{listing_text['disclosure_text']}\n\n"
    f"Price: €{price_eur}"
)
reply_markup = {
    "inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve:{group_id}"},
        {"text": "✏️ Edit",    "callback_data": f"edit:{group_id}"},
        {"text": "❌ Reject",  "callback_data": f"reject:{group_id}"},
    ]]
}
telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
```

`callback_data` carries only `group_id` — `groups.candidate_id` and `groups.group_type` are
both derivable from it via one lookup, so this exact encoding is reused unchanged by the future
`group_digest.py` for 5x7/10x24 buttons, keeping the eventual callback handler in
`publish_primary_group.py`/`publish_group.py` group-agnostic (confirmed).

## Resolved ambiguities (from design review)

1. **Digest text content:** confirmed — include `candidate_id` and `group_id` in the message
   text (not just title/description/tags/disclosure/price), so multiple digest entries landing
   in one batch run are identifiable at a glance.
2. **`callback_data` scheme:** confirmed as proposed — `f"{action}:{group_id}"` for
   `action in ("approve", "edit", "reject")`.
3. **Partial-send failure (`sendMediaGroup` succeeds, `sendMessage` fails):** confirmed
   acceptable to leave as-is. No `group_messages` row is written, so the next `run_digest_cycle`
   re-selects the candidate and **re-sends a duplicate gallery** before retrying `sendMessage`.
   No dedup/cleanup logic added for this — consistent with other stages already accepting
   redone partial work on retry (e.g. `critic_pass.py` overwriting `listing_texts`).
4. **`group_messages` uniqueness:** confirmed code-level invariant only, no
   `UNIQUE(group_id)` schema constraint added. `send_primary_digest` is only ever reached for a
   candidate once per the selection predicate's anti-join, so the constraint would be
   belt-and-suspenders, not load-bearing — same posture already taken for `listing_texts`.

## 4. File / module layout

```
pipeline/
  digest.py
tests/
  test_digest.py
```

Depends on already-merged `pipeline/telegram_client.py` (`send_media_group`, `send_message`),
`pipeline/config.py` (`require_env`), `pipeline/db.py`. No `db/schema.sql` changes, no
`config/static_config.json` changes, no new `telegram_client.py` functions — `send_media_group`
and `send_message` already accept everything this stage needs.
