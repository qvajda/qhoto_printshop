---
source: Gelato product catalogue — Premium Matte Poster, BE pricing 2026-07-05
verified-on: 2026-07-05
verify-by: 2027-01-31
---

# The product line is unframed premium matte posters, in six sizes

Six sizes across two orientations, supplied by Gelato as unframed prints: 5x7,
8x12, A3, A2, 10x24, A1. Not a decision about product strategy — it is the set
Gelato's templates and the shop's cost basis were built on, and every price,
margin and mockup proportion in the project derives from it.

**Two things downstream depend on it directly:** `pipeline/image_crop.SIZE_INCHES`
is the one table both the printed ratios and the Gelato DPI guard read; and
mockup scenes must show an **unframed, unglazed** print, which is why the scene
prompts carry an explicit negative for mats and glazing.

**How to re-verify:** re-pull Gelato's BE price list and diff against
`gelato_premium_matte_poster_prices_BE_2026-07-05.csv`. A size disappearing from
the catalogue is the event that matters.
