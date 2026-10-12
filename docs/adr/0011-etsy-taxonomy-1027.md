---
status: accepted
revisit-after: 2027-02-01
---

# Etsy taxonomy 1027 (Wall Decor), not 121 (Giclée prints)

Listings use `taxonomy_id` **1027** — "Home & Living > Home Decor > Wall Decor" —
resolved from a live `getSellerTaxonomyNodes` call. Etsy has no plain
"Posters" or "Wall Art" leaf, so the choice was between this parent node and
"Art & Collectibles > Prints > Giclée" (121).

1027 was chosen because buyers shopping for a poster to hang browse Home Decor,
and because 121 implies a printmaking process this product does not use. The
alternative is worth remembering precisely because 121 *sounds* more accurate to
anyone reading the code without shopping the category.

## Amendment 2026-10-12 (#262): Wall Hangings (1029)

The listing taxonomy is now **1029** — "Home & Living > Home Decor > Wall Decor >
Wall Hangings", a child of 1027 returned by a live `getSellerTaxonomyNodes`. The
decision above (Home Decor over Giclée 121) stands; only the depth changed.

Why: 1027 is a parent node. 17/20 top-organic listings across our 7 keywords use a
deeper category (12/14 among shops < 500 reviews), Wall Hangings the most common
(6/20), and Etsy's Search Visibility help lists "category as specific as possible"
as a priority-placement requirement. We were absent from pages 1–3 on 7/7 keywords
(`docs/research/2026-10-12-visibility-findings.md` rule 1, #259). Wall Hangings' own
children (Maps, Signs, Tapestries) are not poster fits. Its Material multi and Framing
property ids are the same as on 1027, so `etsy_listing_properties` did not change.

Revert condition: the owner accepted this on condition it helps sales. If sales do
not move after the measurement window, run
`python scripts/retaxonomy_live_listings.py --to 1027 --apply` and set
`etsy_taxonomy_id` back to 1027. The filename keeps "1027" because the record is the
decision's history.
