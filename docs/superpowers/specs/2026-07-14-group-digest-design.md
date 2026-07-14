# Group digest — design (pipeline stage 10/12)

Date: 2026-07-14
Spec basis: SPEC_v4.10.md section 3 step 7 (follow-up digest entry for 5x7/10x24
groups) and step 6 (digest mechanism); CLAUDE.md hard constraints (sendMediaGroup +
separate sendMessage pair, up to three digest entries per design).
Prior art: pipeline/digest.py (stage 6, same mechanism at the primary-group level —
this stage's message/keyboard pattern must match it); docs/superpowers/specs/
2026-07-13-group-critic-pass-design.md (stage 9, what this stage consumes).

## 1. Purpose

`pipeline/group_digest.py` sends the follow-up Telegram digest entry for a 5x7 or
10x24 group once it has passed its own critic pass (stage 9): `sendMediaGroup`
(gallery) + separate `sendMessage` (text + Approve/Edit/Reject buttons), scoped to
that one group rather than the primary's four-size text. Logs the sent message via
`group_messages`, same as stage 6 does for the primary group.

## 2. Scope

**Owns:** selecting groups ready for their follow-up entry, building and sending
that entry, logging it to `group_messages`.

**Does not own:** the critic pass itself (stage 9, done), reading the admin's
decision (`publish_group.py`, stage 11), or the primary group's own digest
(`digest.py`, stage 6, separate module/data path).

## 3. Reuse

Imports `pipeline.digest` and reuses two functions as-is, unmodified:
- `digest.get_listing_text(conn, candidate_id)` — already generic, no primary-only
  assumption.
- `digest.build_digest_keyboard(group_id)` — already keyed by `group_id`, not
  candidate_id, so the callback_data format (`approve:{group_id}` etc.) is identical
  for primary and non-primary groups. `publish_group.py` (stage 11) can reuse
  `publish_primary_group.py`'s existing callback-parsing logic (`resolve_callback`,
  `is_admin`) unchanged.

## 4. Function signatures

```python
# pipeline/group_digest.py

def get_review_group(conn, group_id: int) -> dict:
    """Joins groups + group_products (status='created') on group_id. Returns
    candidate_id, group_type, price_eur. Raises ValueError if no live
    group_products row exists (mirrors digest.get_primary_group)."""

def get_group_gallery_urls(conn, group_id: int) -> list:
    """product_images for the group's live (status='created') group_products row,
    ordered by gallery_order. Mirrors digest.get_primary_gallery_urls, scoped by
    group_id instead of candidate_id + group_type='primary'."""

def build_group_digest_message_text(candidate_id, group_id, group_type, listing_text, price_eur) -> str:
    """Same shape as digest.build_digest_message_text: header line reads
    'Candidate #{id} — {group_type} group (#{group_id})' instead of 'Primary
    group', single price (this group's own), no size suffix logic — that only
    matters for the real Etsy listing title built at publish time
    (publish_group.py, stage 11), not for this preview message."""

def send_group_digest(conn, group_id: int, *, static_config=None, bot_token=None,
                       chat_id=None, now=None) -> dict:
    """get_review_group -> get_group_gallery_urls -> digest.get_listing_text ->
    sendMediaGroup -> build_group_digest_message_text -> digest.build_digest_keyboard
    -> sendMessage -> INSERT group_messages. Same call order/shape as
    digest.send_primary_digest."""

def run_group_digest_cycle(conn, *, static_config=None, bot_token=None,
                            chat_id=None, now=None) -> list:
    """Selects group_ids where group_type IN ('5x7','10x24'), groups.status=
    'pending_review', that group's live group_products.status='created', a passing
    row exists in critic_pass_attempts (passed=1), and no group_messages row yet
    for that group. Calls send_group_digest per group_id, catches+logs exceptions,
    continues past one group's failure."""
```

## 5. Selection query

```sql
SELECT DISTINCT g.id
FROM groups g
JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
WHERE g.group_type IN ('5x7', '10x24')
  AND g.status = 'pending_review'
  AND g.id IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
  AND g.id NOT IN (SELECT group_id FROM group_messages)
ORDER BY g.id
```

`groups.status` stays `'pending_review'` through both "mockup created, not yet
critic-passed" and "critic-passed, awaiting digest" (per stage 9's design, a pass
doesn't flip group status). The `critic_pass_attempts` passed=1 check is what
distinguishes the two — same reasoning stage 9 itself uses for its own selection
query.

## 6. Data model

No new tables/columns. Reuses `groups`, `group_products`, `product_images`,
`listing_texts`, `critic_pass_attempts`, `group_messages` — all already generic on
`group_id`.

## 7. Error handling summary

- `run_group_digest_cycle` catches and logs exceptions per group_id, continuing to
  process the rest — same pattern as `digest.run_digest_cycle`.
- `get_review_group`/`get_group_gallery_urls` raise `ValueError` on missing rows,
  which propagates up to the per-group catch in the cycle function (never crashes
  the whole cycle).

## 8. Testing approach

TDD, mocking `telegram_client` at its existing seam (same style as `digest.py`'s
suite): `get_review_group` happy path + missing-row error, `get_group_gallery_urls`
ordering, `build_group_digest_message_text` content/format, `send_group_digest`
happy path (asserts `sendMediaGroup` then `sendMessage` called in order, and
`group_messages` row inserted), `run_group_digest_cycle`'s selection query (only
picks up critic-passed `pending_review` groups without an existing message, skips
groups still awaiting critic pass, skips already-messaged groups, continues past one
group's exception).
