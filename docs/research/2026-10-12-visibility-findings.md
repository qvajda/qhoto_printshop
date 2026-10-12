# Search-visibility teardown — findings — 2026-10-12

Issue #259. Brief: [`2026-10-12-visibility-brief.md`](2026-10-12-visibility-brief.md).
Data: [`docs/data/visibility/rubric.md`](../data/visibility/rubric.md) (every count
below re-derives from it). Decision: [`2026-10-12-visibility-decision.md`](2026-10-12-visibility-decision.md).

**Conditions.** Built-in browser, signed out, essential cookies only, Etsy
region Belgium, EUR, ship-to default (BE), "Most relevant" sort, 2026-10-12.
7 keywords × SERP pages 1–3 (21 pages, 1,235 cards) and 20 unique top-organic
listings (21 slots; one listing ranked top-3 on two keywords). Our side: the
DB (snapshot 2026-10-10) and 2 of our listings read through the same
extractor. Nothing was written to the shop.

**Scope reminders.** No competitor titles, shop names or listing ids are in
this repo. Prices are owner-set. Ads budget/bid is out of scope.

## Headline

We are **absent from pages 1–3 on 7 of 7 keywords**, and even a query made of
our own most-viewed listing's title finds it organically only on **page 3**.
The page-1 competitors are mostly **small shops** (73 % under 500 reviews), so
shop age is not what keeps us out. Two inputs separate us cleanly from what
ranks, and both are inputs Etsy names itself: the **category** (132/132 of ours
sit on a parent node, while 17/20 top listings use a deeper leaf) and the **first
image** (all of ours lead with a flat mockup, while 13/18 top listings lead with a
room scene). A third is a query-side trap: Etsy rewrites any "vintage" query
to the Vintage category, and 61/134 of our titles spend a token on it.

## Rules

Tag: **S** = structural (what search can match, what the platform permits),
**A** = aesthetic (taste; it feeds the engagement ranking factor).

| # | Rule | Evidence (count) | Surface | Tag |
| --- | --- | --- | --- | --- |
| 1 | **Use a category deeper than Wall Decor.** (L-category: **GAP**, secondary) | 17/20 top-organic listings use a category below Wall Decor (Wall Hangings 6, Giclée 4, Digital Prints 4, Watercolor 2, Murals 1). It is 12/14 among shops with < 500 reviews, and 13/14 among print-type listings only. Ours: 132/132 on `taxonomy_id` 1027, which renders as Home & Living > Home Decor > Wall Decor, the parent of Wall Hangings. Etsy's own Search Visibility help page lists "the listing's category is as specific as possible" among the requirements for priority placement | `config/static_config.json` `etsy_taxonomy_id`; amend `docs/adr/0011-etsy-taxonomy-1027.md` | S |
| 2 | **Lead the gallery with a room scene.** (L-first-image: **GAP**, secondary, marginal) | 13/18 coded top-organic first images show the art in a room (10/13 among shops < 500). Ours: `flat_mockup` at `gallery_order` 0 on 133/133 (2/2 confirmed live). Our galleries already hold 1,119 `lifestyle` images. **Sensitivity:** recoding one room as framed drops it to 12/18 = 67 %, under the 70 % bar. Across all page-1 cards (ads included) room leads in 31/56 (55 %) | gallery order, `pipeline/group_mockup.py` | A |
| 3 | **Treat "vintage" as a blocked token.** | Any query containing `vintage` is rewritten to `/search/vintage` ("Showing botanical print in vintage", Vintage filter applied) in 3 of 3 tries. 61/134 of our titles contain "vintage". Ours are `made_to_order`, so they cannot be in that result set, and must not be. 2/20 top-organic competitors carry "Vintage from the 19th century" on reproduction prints. Not verified: whether Etsy also discounts the token on non-vintage queries | title/tag prompt, `pipeline/compliance_draft.py` (with the #244 title rules) | S |
| 4 | **More of the same niche adds no visibility.** (L-concentration: **GAP** by rule) | Keywords where we hold ≥ 10 title matches: botanical print 101, sage green wall art 39, botanical line art print 35, quiet luxury wall art 14. All 4 are absent from pages 1–3. **Confound, same breath:** the positive control shows we rank on page 3 even for our own title, so the absence is ranking-wide and not only self-competition. Etsy's disclosure names *frequency capping* (limits on the same shop at the top for a keyword), which is the mechanism that would make concentration cost slots | niche sourcing, `candidates.niche`; #243 / #134 | S |
| 5 | **Query match is not the gap.** (L-tag/query: **NULL**) | 177/239 (74 %) page-1 organic titles carry every query token. Ours: 105/132 (80 %) carry every token of ≥ 1 keyword. The internal +35 pp exact-tag contrast (organic 15 vs zero 109) stands, but it is confounded by niche and age (rubric §2) | `TAG_BANDS`, `pipeline/compliance_draft.py`: no change | S |
| 6 | **Trust does not gate page 1.** (L-trust: **NULL**) | 174/239 (73 %) page-1 organic cards come from shops with < 500 reviews; 14/20 top-3 listings do too. A shop with 2 reviews, 1 month old, placed top-3 on 2 keywords. Ours: 2 reviews, 3 sales, 10 months. **Exception:** `watercolor botanical print`. There the median shop has 6,600 reviews, 26/35 organic cards come from ≥ 1k shops, and two of its top 3 are from one shop | none | S |
| 7 | **Shipping is already competitive.** (L-shipping: **NULL**) | Free shipping on 179/239 (75 %) of page-1 organic and 16/19 physical top listings. Ours: free, ships from BE, estimate Oct 15–20 (theirs Oct 14–Nov 4). Etsy's disclosure ranks on shipping price and favours local shops "in certain markets" | Gelato shipping profile: no change | S |
| 8 | **Price is not the gap.** (L-price: **NULL**) | Our smallest size is EUR 19.00. The page-1 organic median by keyword runs 22.84–64.92 for print keywords (150 for biophilic). Top-3 print listings start at 4.50–109.61. We sit at the low end, inside the range | owner, `config/static_config.json`: no change | S |
| 9 | **Visible attributes match; hidden ones can't be compared.** (L-attributes: **NULL** visible / **N/O** hidden) | "Materials" is shown on 13/20 top listings and on ours ("Paper"). Colour, room and subject attributes are not shown to buyers. Etsy says query matching scans attributes "(e.g. color)", and we set 2 properties (Material: Paper, Framing: Unframed). Substitute: none. The conclusion is weaker and is stated as N/O | listing properties, `pipeline/group_product.py` (follow-up: read which properties the chosen category offers) | S |
| 10 | **Video is one listing short of a gap.** (gallery: **NULL**) | 176/239 (74 %) page-1 organic cards carry a video, as do 14/20 top listings, but only 9/14 (64 %) among shops < 500, which fails the trust test by one listing. Ours: 0 videos, 13 images (theirs 6–17) | gallery: no change; revisit if a later sweep moves it | A |
| 11 | **Ads take 40 % of page 1.** (L-ads: finding, owner) | 160/399 page-1 cards are ads, typically the whole first row. Our ad reached slot 1 on a near-exact query. Delivery is about 43 impressions/day shop-wide (rubric §5) | owner, Etsy Ads dashboard; budget/bid out of scope | S |
| 12 | **Two of the seven keywords are poor fits.** | `biophilic wall art` is preserved-moss panels: 0/33 page-1 organic titles say "poster", the median price is EUR 150, and 8/8 of the first row are moss. **BLOCKED** for posters. `quiet luxury wall art` is a mixed product (oil, glass, 3D, canvas): 3/36 "poster", median EUR 64.92, 0 shops ≥ 1k. Weak fit, **not** blocked | niche list (#243); proposed, not applied | S |
| 13 | **Sets own the set query.** | `botanical print set of 3`: 33/33 page-1 organic titles are sets, from only 11 shops; across 7 keywords 123/239 (51 %) of organic titles say "set". We list 0 sets | #67 (evidence only) | S |
| 14 | **Top listings are freshly (re)listed.** (L-recency: **NULL**, provisional) | 17/20 top listings show "Listed on" within 30 days. That includes 4/4 old-id listings (with 33–92 item reviews) showing Sep 30–Oct 10 dates, so the field tracks renewal, not creation. Etsy: a new listing gets "a small, temporary boost", and a renewal "a similar, though smaller" one. Our own snapshot history shows no decay with age (rubric §4), and that is the rule the brief set. Not verified: whether an edit resets "Listed on" | owner (renewal costs fees) | S |
| 15 | **Ads coverage is fine.** (L-ads-cov: **NULL**) | 114/132 served ≥ 1 ad impression in 30 days (rubric §5) | none | S |

### Noted, not acted on

- gp 4 (the one snapshot row with no candidate) shows "This item is
  unavailable" to buyers. Checking the other 132 by fetch returned HTTP 403 (a
  bot wall), so their availability was not counted. 2 of 2 sampled were live.
- gp 229 shows no "Designed by" line in Highlights, while gp 80 does. Cause
  unknown; low weight.
- 2 titles say "printable" and 13 use `|`. That is the #244 TITLE-FORMAT F2
  territory, carried from the hand-off.
- **Owner-side instrument worth one look:** Shop Manager → *Search visibility*
  page. Per Etsy it flags, per listing, an insufficiently specific category,
  primary-photo issues and shop completeness. It is the direct read on rules 1
  and 2 and can't be seen signed out.

## Platform facts verified (phase 5, primary sources)

| Fact | Source |
| --- | --- |
| Query matching scans titles, attributes (e.g. color), categories and tags. Ranking factors: relevancy, listing engagement, recency (new = temporary boost, renewal = smaller boost), listing and shop quality (shop photo, enough high-quality images, return policy), customer service, shipping, translation/location (local shops prioritised in some markets), frequency capping, context-specific ranking. Etsy states no fee buys organic rank | Etsy, *Search, Advertisement & Recommendation Ranking Disclosures* (Terms of Use annex), last updated 2025-10-16: `etsy.com/legal/policy/search-advertisement-ranking-disclosures/899478564529` |
| Priority-placement requirements: ≥ 1 image; primary photo high-resolution (≥ 2000 px advised), a single image of the finished product (no collage), clear and well lit; **category as specific as possible**; a return policy (even "No returns"). Shop: logo. Plus customer-service minimums. Seller-side *Search visibility* page and a Listings filter show per-listing issues | Etsy Help, *How to Use the Etsy Search Visibility Page*: `help.etsy.com/hc/en-gb/articles/25869947521175` |
| "By default, all your current listings are advertised when you start an Etsy Ads campaign." Whether **new** listings are added automatically is **not** stated there, so it is still unconfirmed from a primary source | Etsy Help, *How to Set Up and Manage an Etsy Ads Campaign*: `help.etsy.com/hc/en-gb/articles/360033701174` |
| Ads: second-price auction with auto-bidding against the daily budget; bids can factor in search relevancy and listing quality | Ranking Disclosures (above) |

## Corrections

| Was | Now |
| --- | --- |
| Brief L-recency rule read "Aug listings at 14 days after creation", but snapshots start 09-22 | Rule rewritten on listings created ≥ 09-22 (hand-off) |
| Brief listed ads as out of scope | L-ads-cov added on owner request; resolved NULL by count (hand-off) |
| "Viewed = 23" | organic 15 once ad-clicked listings are separated (hand-off) |
| Skill's SERP extractor returned no review counts on signed-out Etsy Belgium | The count sits in a `review-count-text` attribute on a web component; extractor fixed before any row was written |
| First SERP capture had 15 cards | The grid lazy-loads; every page is now scrolled first (55–60 cards per page) |
| Shop age read "2.5 years" as 5, and missed "9 months" | Regex fixed; all listing rows re-read and the values in §7 are the corrected ones |
| Brief §3 "ranked primary" via internal contrast for category and first image | Not computable: ours hold one value on 132/132 and 133/133, so there is no internal contrast. Both are ranked **secondary** by construction, not by evidence against them |
| Brief §6 treats "listed on" as recency | It tracks renewal (old ids with dozens of reviews show October dates), so it is read as a renewal signal |
| Brief keyword list treated all 7 as poster keywords | `biophilic wall art` is BLOCKED (moss panels); `quiet luxury wall art` is a weak fit |
| Brief assumed our availability is uniform | gp 4 is unavailable; the other 132 could not be checked in bulk (403) |

## Verification pass

- Every count above was re-derived from rubric §6–8 by script (SERP rows) and by
  hand (listing rows, recounted once: returns split corrected from 9/9/2 to
  9/8/2 + 1 n/a).
- No competitor title, shop name or listing id is in any committed file (grep
  for listing paths, 10-digit ids and the shop names seen: none).
- Nothing was written to the shop. No sign-in. The only browser action beyond
  reading was declining non-essential cookies.
- Activation and history-rewrite decisions are not touched.
