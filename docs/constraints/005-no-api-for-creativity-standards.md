---
source: Etsy Open API v3 — `production_process` and `tools_used` are absent from the listing API; etsy/open-api Discussion #1630
verified-on: 2026-08-06
verify-by: 2026-11-06
---

# Etsy's two Creativity Standards questions are not settable by API

"How does your shop produce this item?" (`production_process`) and "What tools are
used to make this item?" (`tools_used`, where "an AI generator" lives) are absent
from the v3 API entirely — not on the listing, not among `taxonomy_id` 1027's 15
properties, and not settable as a shop-level default. Verified by full raw
response dumps on two live listings, not by a field-name grep.

**The operational consequence matters more than the API answer.** The only way to
set them is the web listing editor, and **the editor's sole save action is
"Activate with changes" — there is no draft-save.** Ticking the disclosure
therefore activates the listing.

**Two load-bearing halves. Do not undo either without re-reading the other.**
(1) The prose AI/production-partner disclosure has been **removed** from listing
descriptions (`compliance_draft.DISCLOSURE_TEXT` is `""`), which is only safe
because the structured tick happens at publish. (2) Programmatic draft→active
activation is **cancelled** and `etsy_client.update_listing_state` stays
`# DELIBERATELY UNWIRED` with its guard test intact. Wiring activation up while
the description carries no disclosure would publish a listing with neither.

**How to re-verify:** start from `etsy/open-api` Discussion #1630 (opened
2026-06-22). If it looks shipped, confirm with a full response dump.
