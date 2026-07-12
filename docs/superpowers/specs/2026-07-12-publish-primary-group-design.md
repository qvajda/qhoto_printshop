# Publish primary group — design (pipeline stage 7/12)

Date: 2026-07-12
Spec basis: SPEC_v4.10.md section 3 steps 6–7, section 4; CLAUDE.md hard constraints.

## 1. Purpose

`pipeline/publish_primary_group.py` is the hourly-poll stage that reads a human's
Approve/Edit/Reject decision on `digest.py`'s primary-group Telegram message and acts on it.
On approval, it publishes the primary aspect-ratio group (8x12″ + A3 + A2 + A1) — the four
sizes sharing the ISO A-series ratio — with no further per-size review, per SPEC_v4.10.md D6.

## 2. Scope

**Owns:** the hourly `getUpdates` poll, admin-allowlist enforcement on inbound callbacks,
recording the decision, and — on approval — creating/publishing all four primary-group
`group_products` rows as Gelato products + Etsy listings.

**Does not own:** triggering the 5x7/10x24 group fan-out (`group_mockup.py` /
`group_critic_pass.py` / `group_digest.py`). CLAUDE.md lists these as separate named
pipeline stages, matching the one-module-per-stage convention already used for
research/generate/primary-mockup/compliance-draft/critic-pass. A future evening-batch
orchestrator (not part of this stage) is responsible for calling them next once it sees a
candidate with `groups.status = 'approved_published'` on its primary group. This stage's job
ends once the primary group is published or the decision is rejected/edited.

**Does not own (deferred):** capturing free-text correction notes for the Edit action.
Telegram digests currently only send three buttons — no reply-message flow exists. Edit
records `decision = 'edited'`, `decision_notes = NULL`, and regenerates the primary size with
no correction note. A follow-up stage can add real note capture later.

## 3. Telegram callback resolution (verified against Bot API, not assumed)

Confirmed against Telegram's `CallbackQuery` object (Bot API docs, cross-checked via
python-telegram-bot's reference, which mirrors the raw API 1:1):

- `callback_query.id` — token required by `answerCallbackQuery`.
- `callback_query.from.id` — sender's numeric Telegram user ID. **This is checked against
  `TELEGRAM_ADMIN_CHAT_ID`** before anything is treated as a real decision, per CLAUDE.md.
- `callback_query.data` — our own string, exactly what `digest.py` set:
  `f"{action}:{group_id}"` (`build_digest_keyboard`). Parsed directly — no extra API call
  needed to resolve `group_id`.
- `callback_query.message.message_id` / `callback_query.message.chat.id` — the original
  `sendMessage` this button was attached to.

`group_id → candidate_id` is a single join via `groups.candidate_id`. As an integrity guard
(not strictly required for routing, but cheap and catches stale/replayed callbacks),
`message.message_id` + `message.chat.id` are cross-checked against the `group_messages` row
for that `group_id` before the decision is accepted.

Every inbound update — callback or not, admin or not — is logged to `telegram_events_log`
(`accepted = 0` and no `action_taken` for anything discarded), per CLAUDE.md's two-job
requirement for the allowlist ID.

**New gap found and included in this design:** nothing currently persists Telegram's
`update_id` between hourly polls, so `get_updates` would reprocess old updates indefinitely.
This stage adds a single-row `telegram_offset` table (`id INTEGER PRIMARY KEY CHECK (id = 1)`,
`last_update_id INTEGER NOT NULL`) read before polling and written after, so `offset` on the
next `get_updates` call is `last_update_id + 1`.

## 4. Function signatures

```python
# pipeline/publish_primary_group.py

def resolve_callback(update: dict) -> dict | None:
    """Parse a getUpdates entry. Returns None if it isn't a callback_query.
    Otherwise {telegram_user_id, callback_query_id, action, group_id, message_id, chat_id}."""

def is_admin(telegram_user_id, admin_chat_id) -> bool: ...

def log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken, *, now=None) -> int: ...

def record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None:
    """Writes groups.decision / decision_notes / decided_at."""

def build_size_listing_data(listing_text: dict, metadata: dict, size: str, price_eur: float) -> dict:
    """Size-suffixed title (re-validated via compliance_draft.validate_listing_text against the
    140-char cap), shared description/tags/disclosure, per-size price, shared static metadata."""

def publish_group_product(conn, group_product_row, candidate, listing_text, *, static_config,
                           store_id=None, gelato_api_key=None, shop_id=None,
                           etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                           now=None) -> dict:
    """One size end to end: create the Gelato product if group_product_row doesn't already have
    one (8x12 already does; A3/A2/A1 don't), fetch its gallery, download each image's bytes,
    etsy_client.upload_listing_image per image, etsy_client.create_draft_listing,
    etsy_client.update_listing_state(..., state='active'), write gelato_product_id/
    etsy_listing_id/status back to group_products. Retries the whole sequence once on any
    exception; on a second failure, sets status='publish_failed' and re-raises to the caller,
    which continues with the remaining sizes."""

def publish_primary_group(conn, candidate_id, *, static_config=None, ...) -> dict:
    """8x12 first, then A3/A2/A1. Continues past per-size failures. Returns {size: status}.
    Sets groups.status = 'approved_published' once at least one size published; if all four
    fail, leaves the group in a state a future digest can surface (no digest authored here)."""

def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, ...) -> dict:
    """approve -> record_decision + publish_primary_group.
       edit    -> record_decision(decision_notes=None) + generate.generate_for_candidate(...)
                  + primary_mockup.create_primary_mockup(...) + compliance_draft.build_compliance_draft(...)
                  (same direct-call chain critic_pass.py already uses internally).
       reject  -> record_decision + groups.status='rejected' + candidates status update,
                  logged the same way as a critic-pass failure (full record kept)."""

def process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None, ...) -> dict | None:
    """Allowlist check -> log -> answerCallbackQuery -> handle_decision. Discards + logs
    (accepted=0) anything from a non-admin sender or a callback that fails the group_messages
    integrity check, without acting on it."""

def run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None,
                                     static_config=None, ...) -> list:
    """Hourly-poll entrypoint: reads telegram_offset, calls get_updates(offset=...),
    process_update per entry, advances telegram_offset, returns processed results."""
```

This mirrors the existing per-item-function + cycle-function shape used by
`critic_pass.py`/`primary_mockup.py`/`compliance_draft.py`.

## 5. Publish sequence (the 4 primary-group sizes)

1. **8x12** — Gelato product already exists (`primary_mockup.py`, `status='created'`). Fetch
   each gallery image's bytes, upload to Etsy, `create_draft_listing` (base title, no suffix),
   `update_listing_state(..., 'active')`, write `etsy_listing_id`, `status='published'`.
2. **A3 / A2 / A1** — each needs its own fresh `gelato_client.create_product_from_template`
   call (own template, own `gelato_product_id`, same `candidate.base_image_url`, portrait
   orientation — same call shape `primary_mockup.py` already uses), then the same
   upload→draft→activate sequence, with a size-suffixed title re-checked against the 140-char
   cap via `build_size_listing_data`.
3. All four share `disclosure_text`, `who_made`/`production_partner_ids`/`taxonomy_id`,
   `shipping_profile_id` (from `listing_texts`, already resolved by `compliance_draft.py`).
4. Operational failure (Gelato or Etsy call throws) on any size: retry that size's whole
   sequence once; if it still fails, that size alone becomes `publish_failed`, the others are
   unaffected, and the failure is surfaced in a future digest (not authored by this stage).

## 6. New client-layer additions required

- **`etsy_client.update_listing_state(shop_id, listing_id, state, *, api_key=None,
  api_secret=None, access_token=None, dry_run=None) -> dict`** — `PATCH
  /v3/application/shops/{shop_id}/listings/{listing_id}` with body `{"state": state}`.
  Verified live against Etsy's OpenAPI 3.0 spec and developer docs (not assumed): this is the
  only way to move a listing from `draft` to `active` — there is no separate publish-specific
  endpoint — and it requires the listing to already have at least one image uploaded, which is
  why image upload happens before this call in the sequence above. Requires the `listings_w`
  OAuth scope on `ETSY_ACCESS_TOKEN`.
- **`http.fetch_bytes(url) -> bytes`** — `http.send()` currently only parses JSON bodies;
  downloading a Gelato preview/gallery image for re-upload to Etsy needs raw bytes.

## 7. Known gaps flagged, deliberately out of scope for this stage

- **`etsy_section_id`** — required by the spec on every listing (CLAUDE.md, SPEC_v4.10.md
  section 1/3), not present in `static_config.json` or CLAUDE.md's static-config list. Your
  manual test log already has a real value (`shop_section_id: 49030934`). Left unresolved by
  your choice — same class of blocker as `etsy_shipping_profile_id`'s per-size mapping TODO
  already in CLAUDE.md. Both block a real (non-dry-run) publish call for this stage; neither
  blocks building/testing it against dry-run/mocked clients.
- **Edit-note text capture** — deferred per section 2 above.
- **5x7/10x24 fan-out trigger** — deferred per section 2 above; this stage's contract is
  simply to leave `groups.status = 'approved_published'` behind for the next stage to find.

## 8. Error handling summary

- Non-admin sender: discarded, logged (`accepted=0`), never acted on.
- Callback whose `message_id`/`chat_id` don't match its `group_messages` row: discarded,
  logged, never acted on.
- Per-size Gelato/Etsy operational failure: retry once, then isolate the failure to that size.
- Reject/critic-style abandonment: full record kept (trend source, listing text, decision),
  same convention as `critic_pass.py`'s `abandon_candidate`.

## 9. Testing approach

TDD per project convention, mocking `telegram_client`/`gelato_client`/`etsy_client`/`http` at
their existing seams (same style as `digest.py`'s and `critic_pass.py`'s test suites):
callback parsing against real-shaped `getUpdates` fixtures, allowlist rejection, the
integrity-check mismatch case, per-size retry-then-isolate behavior, and the edit/reject
decision-recording paths. `dry_run` threads through exactly like `gelato_client`/`etsy_client`
already support, so the full cycle is testable without live calls.
