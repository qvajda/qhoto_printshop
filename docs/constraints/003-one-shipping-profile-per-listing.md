---
source: Etsy Open API v3 — a listing carries exactly one shipping_profile_id
verified-on: 2026-08-01
verify-by: 2027-02-01
---

# One Etsy listing gets exactly one shipping profile

A listing has a single `shipping_profile_id`. It cannot vary by variant. This is
an API shape, not a choice.

**What it forced:** under one-listing-per-artwork the profile is resolved once
per **candidate**, not per aspect-ratio group. The previous Small/Large split by
group became unrepresentable the moment sizes shared a listing.

Currently `288734253315` — "Gelato: Free shipping", €0 to every destination,
confirmed live via `GET /v3/application/shops/{shop_id}/shipping-profiles`.

**Retail prices are unaffected.** Gelato's per-item shipping (€5.10–€5.86) is
billed to the seller whichever profile is set and is already inside the cost
basis; all six sizes clear cost at 21–44%.

**How to re-verify:** re-list the shop's shipping profiles and confirm the id
still exists and still shows €0 at checkout.
