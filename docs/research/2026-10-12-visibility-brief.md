# Search-visibility teardown — brief — 2026-10-12

**Status: brief only. Nothing is researched until this is signed off.**
No live-shop writes, no code changes, no sweep. Issue #259.

## 1. Problem / success criteria

On the 2026-10-10 snapshot (`listing_metrics_snapshots`), **110 of 133** published
listings have 0 views; the shop total is 52 views and 4 favourites. Titles are
the only visibility lever ever researched (#244). Nothing else that Etsy search
reads has been compared against the listings that *do* get seen: tags,
attributes, category, first image, price, shipping, reviews/shop age, ads,
recency.

**Our baseline, measured today from the DB (read-only):**

| Cut | n | viewed (>0) | views |
| --- | --- | --- | --- |
| all (joined to a candidate) | 132 | 23 | 52 |
| created 2026-08 | 42 | 10 | 34 |
| created 2026-09 | 66 | 13 | 18 |
| created 2026-10 | 24 | **0** | 0 |
| niche contains "botanical" | **65** | 14 | 37 |
| niche contains "sage"/"biophilic" | 30 | 7 | 14 |
| niche contains "line art/drawing" | 28 | 6 | 22 |
| niche contains "set"/"gallery wall" | 39 | 6 | 17 |
| niche contains "quiet luxury" | 19 | 3 | 5 |
| celestial / mid-century / abstract | 19 | **0** | 0 |

Two things already show before any browsing, and the sweep must test them, not
assume them:
- **Concentration.** 98 distinct niche strings, but half the catalogue is
  botanical and about a quarter is sage/biophilic. If those listings all match
  the same handful of queries, they compete with each other for one slot.
- **Age.** 0 of 24 October listings have a view. That could be new listings
  that haven't been indexed yet, or a sign that newer listings are worse. The
  sweep's job is to tell which.

(1 of 133 snapshot rows does not join to a candidate; it gets noted, not chased.)

**Success = 4 artefacts (the acceptance criteria in #259):**
1. `docs/data/visibility/rubric.md`: coded rows (ours and theirs) plus a counts
   table. Written during the sweep.
2. `docs/research/2026-10-xx-visibility-findings.md`: 10–15 rules, each with a
   count, a surface and a structural/aesthetic tag, plus a corrections table.
3. `docs/research/2026-10-xx-visibility-decision.md`: resolves §3, readable
   cold.
4. This brief.

## 2. Scope

**In:** the inputs Etsy search reads or shows a buyer *before the click*:
title-to-query match, tags (ours only, §6), attributes, category, first image,
price per size, shipping price/badge, shop reviews and age, Ad / Bestseller /
Star Seller badges, listing recency. Plus **where we rank** for our own
keywords.

**Out, and why:**
- Any code, listing, tag or price change. #259 is research; every finding
  lands as a proposed follow-up row.
- Titles as a formula. #244 did that (TITLE-LEN L1, TITLE-FORMAT F2). This
  sweep only re-uses title tokens as the tag proxy.
- Ads spend and ROAS as a performance study. Ads *coverage* is in (L-ads-cov,
  §3), because it may be a configuration defect rather than a market fact.
- Conversion (views to orders). With 52 views there is no conversion signal to
  read.
- Branding (banner, icon, About). GL-10b did that, and it is not a search input.

## 3. The decision this resolves

**Decision: VIS-LEVER.** Which lever(s) does the follow-up build row target?

Each lever below gets one of three outcomes:

| Outcome | Meaning | Consequence |
| --- | --- | --- |
| **GAP** | Top results share a value we lack | Becomes a proposed follow-up row with its count |
| **NULL** | We sit inside the competitor range, or competitors are split | No work. Recorded as a finding (licenses keeping what's built) |
| **N/O** | Not observable from the buyer view | Stated, with the substitute used and how much weaker the conclusion is |

Levers: L-tag/query match · L-attributes · L-category · L-first-image ·
L-price · L-shipping · L-trust (reviews/shop age/Star Seller) · L-ads ·
L-ads-cov · L-recency · L-concentration.

**L-ads-cov (owner-raised 2026-10-12): is each listing actually opted in to
Etsy Ads?** The listing editor's "Etsy Ads: Promote this listing…" toggle
appears to default to *off* on new listings. Facts checked before the sweep:
- Etsy Open API v3 has **no ads field or endpoint**. A grep of the full
  published spec (`/openapi/generated/oas/3.0.0.json`, 911 KB) finds only
  `featured_rank` and `getFeaturedListingsByShop`, which are shop-featuring and
  unrelated. So the pipeline never set the toggle (our PATCH has no field for
  it), cannot read it, and cannot fix it. Every listing carries whatever Etsy
  applied when Gelato pushed it, plus anything changed by hand.
- The shop-level "automatically advertise new listings" setting and its default
  could not be confirmed from an official Etsy help page. Only third-party
  guides and community reports turned up, including reports that the toggle
  *shows* off while ads run. To be re-verified in phase 5.
- Ads ran: about 1,317 impressions and 8 clicks around 2026-09-21 (#230). So
  *some* listings were opted in. Which ones is unknown.

Source of truth is your Etsy Ads dashboard. The API can't see it, and the
sweep doesn't sign in. Rule, written now:
- **GAP (configuration defect)** if < 80 % of published listings are opted in
  to Etsy Ads. It goes to you, not a build row: toggling is dashboard-only, and
  turning ads on spends budget, so you decide. The finding states the count,
  the shop-level auto-advertise setting, and whether opted-in listings are
  over-represented among our 23 viewed ones (≥ 20 pp = ads are what drives our
  views, which changes how every other "ours" count reads).
- **NULL** if ≥ 80 % are opted in.
- If the per-listing state can't be got, **N/O**, and every internal
  viewed-vs-unviewed contrast is flagged as possibly ads-confounded.

**Owner observation, 2026-10-12 (uncounted):** shop-level "automatically
advertise new listings" appears **on**. Drafts *show* the listing toggle off,
yet published listings are listed as "advertisement on". So the editor's
default-off toggle is a draft-state display artefact and does not show what
happens after publish. **Provisional: NULL** (coverage is not the defect).
To harden it into a count, the dashboard export is still welcome but no longer
blocking. Consequence: the internal viewed-vs-unviewed contrast is **not**
suspended. And if roughly all 133 listings are advertised yet 110 have 0
views, then ads coverage isn't the problem, and ads *delivery* (budget/bid:
about 1,317 impressions spread over about 130 listings, #230) moves to
findings as L-ads, with spend still out of scope.

**Counted, 2026-10-12, from your Etsy Ads listings table (pasted; date range
not shown):** 132 listings. The on/off icon did not survive the paste, so ad
impressions > 0 stands in for "ad on".
- **114 / 132 (86 %) served ≥ 1 ad impression**, and 18 served 0. The 18 could
  be off, or on with no delivery; the icon would tell which. **L-ads-cov:
  NULL** (≥ 80 %). Coverage is not the defect.
- 1,296 impressions and 14 clicks (1.1 % CTR) across 9 listings, 0 orders.
- **Ads join to our views:** the 9 clicked listings matched by title in
  `listing_texts`, and **8 of them are among our 23 viewed listings** (20 of
  the 52 views). The 9th has 0 views on the 2026-10-10 snapshot. So 8/23 (35 %)
  of viewed listings carry an ad click, against 1/109 (1 %) of unviewed ones.
  That is ≥ 20 pp, so per the rule above **ads drive about a third of our
  "viewed" set**.
- **Correction applied to the internal contrast:** "viewed" for every other
  lever = the **15 listings with views and no ad click** (organic only), not
  23. That leaves a thin baseline, which gets said wherever it is used.
- **Date range: last 30 days** (owner, 2026-10-12), so about 2026-09-12 to
  2026-10-12. That is about 43 impressions/day shop-wide, about 0.3 per
  listing per day. Snapshot views are lifetime (`getListing`) and ad clicks
  are 30-day, so the 8/23 join is a floor, not an exact share. #230's ~1,317
  around 09-21 used a different window and is not compared.
- Ad *delivery* (about 10 impressions per listing, 1.1 % CTR) goes to
  findings as L-ads. Budget/bid stays out of scope.

**L-ads-cov is resolved first,** before the sweep. If the 23 viewed listings
are mostly the advertised ones, the viewed/unviewed contrast measures ad
enrolment, not listing quality, and the "ranked primary" test below is
suspended for every lever.

**Default if the signal is weak or split:** NULL. No change.

**Resolution rule, written before the data exists.** A lever is **GAP** only if
both of these hold:
1. **External:** ≥ 70 % of the coded top-organic listings share a value, and
   ≤ 30 % of our listings have it (or the reverse for a value we have and they
   don't).
2. **Not explained by trust alone:** the gap still holds among top listings
   from shops with < 500 reviews. Otherwise the true lever is shop age, which
   we can't buy (→ L-trust).

A GAP is **ranked primary** if our own viewed listings (23) differ from our
unviewed listings in the same direction on the same field (internal contrast
≥ 20 percentage points). A GAP with no internal contrast stays a GAP, ranked
secondary.

**L-concentration** gets its own rule. It is GAP if, for ≥ 3 of the sampled
keywords, our listings that match the query (by title/tag tokens) number ≥ 10
**and** none of them is in the first 3 SERP pages. That means more of the same
niche adds no visibility. It is NULL if any of ours ranks inside 3 pages for a
keyword where we hold ≥ 10 listings.

**L-recency** is decided by our own snapshot history, not by competitors.
Snapshots start 2026-09-22, so it is measured on listings created on or after
that date: days from creation to first non-zero view.
- **Too early** if the October listings are younger than that median. Their
  zero is expected, so they are excluded from every other lever's "ours" count.
- **GAP** ("listings go stale, renewal matters") if view-rate *falls* with age
  across the Aug/Sep cohorts once they are older than the median.
- **NULL** otherwise.

**Anti-drift:** argued from coded fields only. A value seen on a top listing is
not a lever unless the count clears the rule. Where the top of every SERP is
owned by 1,000+ review shops, that resolves to L-trust. It is a finding, not a
mandate to copy the listing.

## 4. Constraints the research gets no vote on

- Activation, git history: per CLAUDE.md.
- Artwork is FLUX schnell, flat full-bleed; sizes are variants of one listing
  (v4.12); Gelato pushes and we patch.
- Prices are owner-set (`config/static_config.json`). A price GAP becomes a
  finding for you to weigh, not a pricing proposal on its own authority.
- Titles: #244 resolution stands.
- Listing copy is evergreen; AI disclosure stays in the description.
- Public repo: no competitor titles or shop names in any file, only counts and
  short pattern quotes.

## 5. Sampling method

**Keywords: our 7 most-held clusters, written as a buyer would search them:**

1. `botanical print`
2. `sage green wall art`
3. `botanical line art print`
4. `botanical print set of 3`
5. `quiet luxury wall art`
6. `biophilic wall art`
7. `watercolor botanical print`

**Three layers:**
- **SERP layer (cheap, wide).** Page 1 of each keyword (~48 results × 7),
  coded via the extractor: Ad, Bestseller, Star Seller, price shown, free
  shipping, shop review count, digital vs physical. One screenshot per SERP
  for the first-image field. Plus our rank: we scan pages 1–3 for QhotoArt and
  record our best position or "absent".
- **Listing layer (coded deep).** Top 3 **organic** (non-Ad) listings per
  keyword, 21 in total. From the listing page: category breadcrumb, attributes
  shown, gallery count/video, price per size, shipping/delivery estimate, shop
  sales and age, "listed on" if shown, review count.
- **Ours.** All 23 viewed listings plus 23 unviewed (random, seed fixed in the
  data file). They come from the DB and `getListing` (a read-only GET we
  already make). Coded on the same fields, plus tags and the tag-query overlap
  (which we can see for our own listings).

**Known bias:** SERPs are personalised and location-biased, and Etsy has no
"most sold" sort. Correction: browse signed out, in an isolated browser, ship-to
left at default (record it). Use the Bestseller badge as the sales signal.
Exclude Ad slots from the "top organic" set but count them separately.

## 6. The rubric

Per listing (theirs and ours):

| Field | How coded |
| --- | --- |
| query token match | share of query tokens in the title (theirs), in title+tags (ours) |
| tags | **ours only**; overlap with the query, count of 13 used |
| category | breadcrumb leaf |
| attributes | count shown; primary colour / room / subject / orientation present y/n |
| first image | flat art / framed-in-room / lifestyle / size chart / text-burned |
| gallery | image count; video y/n |
| price | at the smallest and the largest size, EUR as shown |
| shipping | free y/n; price shown; delivery estimate (days) |
| listing type | physical / digital |
| badges | Ad / Bestseller / Star Seller / Popular now |
| shop trust | shop review count, sales, years on Etsy |
| recency | "listed on" date if shown, else N/O |
| SERP position | page and slot |

**Expected NOT OBSERVABLE:** competitor tags (Etsy hides them from buyers;
the title-token surface substitutes, as in GL-10b and #244), competitor
listing-quality / CTR, and possibly competitor "listed on" (recorded per
listing as it is found).

## 7. Where findings land

| Finding type | Lands in |
| --- | --- |
| Tags / query match | `TAG_BANDS` and the tag prompt in `pipeline/compliance_draft.py` (follow-up row) |
| Attributes / category | listing PATCH in the publish stage (`updateListing` fields) (follow-up row) |
| First image | gallery order, `pipeline/group_mockup.py` and the scene library (follow-up row) |
| Price / shipping | owner decision; `config/static_config.json`, Gelato shipping profile |
| Concentration | niche selection, `candidates.niche` sourcing; ties to #243 / #134 |
| Sets | #67 (evidence only) |
| Recency / renewal | owner decision, since renewal costs listing fees |
| Ads coverage | owner, Etsy Ads dashboard (no API path, it spends budget); a runbook note for new listings if auto-advertise is off |

## 8. Out of scope / deferred

New niche keywords spotted go to the findings and then a niche-list row, never
applied directly. Description or alt-text issues spotted are noted for a
separate row. Interesting shops found mid-sweep are noted and not followed.

## 9. Open questions for sign-off

1. **Keywords**: are the 7 above right, or swap any (e.g. add `minimalist
   line art` or `celestial wall art`, where we hold 8 listings with 0 views)?
2. **Browser**: Claude in Chrome, signed out of Etsy (or a guest profile so
   your seller session doesn't personalise results), read-only. OK? Or the
   built-in browser like #244?
3. **Ads coverage: answered provisionally (§3, owner observation); an
   export would turn it into a count, not blocking.** From Shop
   Manager → Marketing → Etsy Ads, any one of:
   - (a) the per-listing table export (listing, advertising on/off,
     impressions, clicks), or
   - (b) a screenshot of the listings table filtered to "not advertised" plus
     the shop total, or
   - (c) you let me read that page in your signed-in Chrome. Read-only, no
     toggles touched. This breaks the skill's no-sign-in rule, so only on your
     explicit OK.

   Also: is the shop-level "automatically advertise new listings" setting on?
