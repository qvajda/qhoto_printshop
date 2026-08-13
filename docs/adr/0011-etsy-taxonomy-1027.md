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
