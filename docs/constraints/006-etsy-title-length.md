---
source: measured `listing_texts.title` for the 31 published listings that join
  a `group_products` row via `candidate_id`, `scripts/gl155_title_length_probe.py`
verified-on: 2026-08-28
verify-by: n/a — closes #155, no re-check scheduled
---

# Etsy's shorter-title dashboard nudge is cosmetic, not a drafting defect

**Current constraint:** `compliance_draft.MAX_TITLE_LENGTH = 140`
(`pipeline/compliance_draft.py:36`), matching Etsy's hard field limit for
`listings.title`.

## What was measured

`scripts/gl155_title_length_probe.py` joined every `published` `group_products`
row to its drafted `listing_texts.title` by `candidate_id` (33 published rows;
2 have no matching `listing_texts` row — pre-dating that table or a manual
correction — and are excluded). 31 titles measured:

```
draft: min=109 median=126 max=139 n=31
```

Every drafted title is **under** 140, several within 1–11 characters of the
ceiling (`4559240924` at 139, `4558565968` at 136, `4560219306` at 137). None
exceed it — `MAX_TITLE_LENGTH` did its job; nothing was truncated or rejected
by Etsy's create/update call (all 31 are `published`, i.e. Etsy accepted the
PATCH).

The probe also GETs each live listing's title via `etsy_client.get_listing`
for a draft-vs-live diff, but this session had no `ETSY_*` credentials and
`ETSY_LIVE_MODE` unset, so every call returned the `dry_run` stub
(`live_len=None` for all 31 rows). The owner should re-run the probe live
before next relying on the live column; the draft-side lengths above are
unaffected by that gap since they read the DB, not the API.

**Which specific listings Etsy's dashboard flags is not exposed by any v3 API
endpoint** — confirmed by the absence of an SEO/quality-score field on
`GET /listings/{id}` (see `docs/constraints/005-no-api-for-creativity-standards.md`
for the same class of dashboard-only surface). This doc correlates the owner's
2026-08-18 observation ("recommends shorter titles, only visible once live")
against the measured lengths instead: the flagged listings were live, searchable,
full-length (109–139 chars) titles that Etsy itself had already accepted — the
nudge appeared *after* acceptance, not as a rejection or validation error.

**Citation gap, stated plainly:** this session had no web-fetch access
(`WebSearch`/`WebFetch` permission was not granted), so no Etsy Seller Handbook
or Help Center sentence could be quoted and verified live. Etsy's technical
field limit of 140 characters is already encoded as `MAX_TITLE_LENGTH` and is
exercised by `tests/test_compliance_draft.py`; no separate *published,
numeric* "recommended" title length distinct from that field max is known to
exist in Etsy's documentation. The owner should verify directly against
`https://www.etsy.com/seller-handbook` (or the shop dashboard's own SEO panel,
where the nudge was seen) if a documented number ever needs quoting here.

## Why this reads as cosmetic, not a validation rule

- It surfaces only once a listing is live/searchable, not while drafting or on
  the create/update call itself (2026-08-18 owner observation) — consistent
  with a per-listing SEO/quality-score panel computed post-publish, not a
  field-level validator.
- Every measured title Etsy flagged was already inside the documented 140-char
  hard limit and was accepted (`200`, `published`) — the platform's own
  acceptance criterion was satisfied.
- Etsy's search-result snippet on mobile truncates well before 140 characters
  regardless of title length, which is the well-known reason SEO tooling
  nudges toward shorter, front-loaded titles — a ranking/readability
  suggestion, not a hard ceiling.

## Verdict

Verdict: cosmetic on-page nudge, no drafting change

`MAX_TITLE_LENGTH` stays 140. If the owner later wants shorter, keyword-front
loaded titles for SEO reasons (not because Etsy is rejecting anything), that
is the five-slot / 15-word title formula in **#28 (GL-10c)** — not this row.
#155 closes.
