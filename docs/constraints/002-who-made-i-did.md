---
source: Etsy Open API v3 — createDraftListing / updateListing `who_made` enum
verified-on: 2026-08-06
verify-by: 2026-11-06
---

# `who_made: "i_did"` is the only value the Etsy API offers

The `who_made` enum has exactly three raw values — `i_did`, `someone_else`,
`collective`. There is no fourth value and no separate AI-disclosure field.
Etsy's "Designed by a seller / made with an AI generator" label is the **display
name** for `i_did`, not a distinct settable value.

Nothing was decided here: this is the shape of somebody else's API. Must be paired
with `is_supply: false` and `when_made: "made_to_order"`.

**How to re-verify:** a full raw `GET /listings/{id}` dump on a live listing —
**a field-name grep is not sufficient** and has produced a wrong answer before.
Start from `etsy/open-api` Discussion #1630 rather than re-deriving.
