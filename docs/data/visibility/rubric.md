# Visibility teardown — coded rows (#259)

Brief: [`2026-10-12-visibility-brief.md`](../../research/2026-10-12-visibility-brief.md).
Every count in the findings must re-derive from this file.

Sources: `db/qhoto.sqlite3` read-only (`listing_metrics_snapshots`, `group_products`,
`listing_texts`, `candidates`), snapshot 2026-10-10; Etsy Ads listings table,
last 30 days, pasted by the owner 2026-10-12 (counts only, raw paste not stored).

## 1. Ours — groups

Groups exclude each other. A listing is in **ad** if it has views and appears
among the 9 ad-clicked listings (matched by `listing_texts.title`), **organic**
if it has views and no ad click, and **zero** if it has 0 views. 132 listings
join snapshot → `group_products` → `listing_texts`. 1 of the 133 snapshot rows
does not join (brief §1).

| group | n | group_product ids |
| --- | --- | --- |
| ad | 8 | 63, 93, 121, 128, 130, 139, 141, 175 |
| organic | 15 | the other viewed ids (2026-10-10 snapshot, `views > 0`) |
| zero | 109 | includes gp 60 (1 ad click, 0 views at snapshot) |

## 2. Ours — coded fields (counts)

Keyword match: **exact tag** = one of the 7 brief keywords is a whole tag;
**title** = every token of a keyword appears in the title.

| field | organic (15) | ad (8) | zero (109) | organic − zero |
| --- | --- | --- | --- | --- |
| 13 tags used | 15 | 8 | 109 | 0 pp |
| ≥ 1 keyword as exact tag | 11 (73 %) | 5 | 41 (38 %) | **+35 pp** |
| ≥ 1 keyword in title | 14 (93 %) | 8 | 83 (76 %) | +17 pp |
| "poster" in title | 9 (60 %) | 1 | 57 (52 %) | +8 pp |
| `\|` separator in title | 3 | 0 | 10 | — |
| "printable" in title | 1 | 0 | 1 | — |
| taxonomy_id | 1027 ×15 | 1027 ×8 | 1027 ×109 | one value, 132/132 |

Confound, stated where the number is: the exact-tag `botanical print` sits on
53 listings, which skew to the older botanical niches. Age and niche are not
separated from the tag effect at n = 15.

## 3. Ours — keyword coverage across the catalogue (132)

| keyword | exact tag | all tokens in title |
| --- | --- | --- |
| botanical print | 53 | **101** |
| sage green wall art | 7 | 39 |
| botanical line art print | 0 | 35 |
| botanical print set of 3 | 0 | 0 |
| quiet luxury wall art | 0 | 14 |
| biophilic wall art | 1 | 2 |
| watercolor botanical print | 0 | 9 |

## 4. Ours — recency (L-recency)

Snapshot history starts 2026-09-22.
- Listings created ≥ 2026-09-22: **3 viewed** (days to first view 3, 3, 4;
  median 3; n = 3, survivorship-biased low). **34 never viewed**, ages 1–18
  days, 24 of them older than 3 days.
- View-rate by age at 2026-10-10: < 14 d 3/31 (9 %) · 14–27 d 6/27 (22 %) ·
  28–41 d 5/34 (14 %) · 42+ d 9/41 (21 %). Age buckets use
  `group_products.created_at` and count all 133 snapshot rows, so this total is
  133, not 132.

## 5. Ours — ads (L-ads-cov / L-ads), last 30 days

- 114/132 served ≥ 1 impression; 18 served 0.
- 1,296 impressions, 14 clicks (1.1 %), clicks on 9 listings, 0 orders.
- 8 of the 9 clicked listings are in **ad** (§1).

## 6. SERP layer — theirs

Conditions: built-in browser, signed out, essential cookies only, Etsy region
**Belgium**, currency **EUR**, ship-to left at default (BE), sort "Most
relevant" (plain `/search?q=`), viewport 1400×1000, 2026-10-12. Cards are the
main result grid only (carousels excluded), deduplicated by listing id, after
scrolling the page to load every lazy card. Shop review count is the
`(n)` beside the card's star rating (shop-level). Counts in the right-hand
columns are over **organic** cards unless marked "all".

Column key: BS = Bestseller (org / all cards) · Pop = Popular now · Star = Star
Seller · DL = digital download · Free = free shipping · Sale = strikethrough
price · EU = "Ships from EU" · Tok = every query token in the title · Pst =
"poster" in title · Set = "set"/"set of" in title · Vid = card carries a video
· Shops = distinct organic shops · price min/med/max EUR as shown on the card ·
Rev med = median shop review count · <500 / ≥1k = organic cards from shops with
fewer than 500 / at least 1,000 reviews · AdFree = ad cards with free shipping.

| kw | pg | cards | ads | org | BS | Pop | Star | DL | Free | Sale | EU | Tok | Pst | Set | Vid | Shops | price min/med/max | Rev med | <500 | ≥1k | AdFree | ours |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| botanical print | 1 | 57 | 24 | 33 | 3/6 | 3 | 13 | 3 | 16 | 12 | 23 | 31 | 18 | 21 | 24 | 21 | 2.54/26.91/109.61 | 209 | 17 | 15 | 14 | absent |
| botanical print | 2 | 59 | 11 | 48 | 5/7 | 3 | 29 | 0 | 30 | 16 | 24 | 37 | 30 | 20 | 30 | 39 | 3.92/22.84/123.19 | 144 | 38 | 10 | 4 | absent |
| botanical print | 3 | 59 | 12 | 47 | 0/1 | 1 | 21 | 1 | 30 | 27 | 30 | 42 | 30 | 21 | 30 | 34 | 4.48/22.99/123.00 | 145 | 35 | 9 | 4 | absent |

## 7. Listing layer — theirs

Top 3 organic cards of page 1 per keyword (slot = position among all page-1
cards, ads included), same conditions as §6. Read from the listing page.
Shop names are replaced by `shop` in the highlights column.

Column key: cat = breadcrumb under Art & Collectibles · hl = "Highlights"
attribute lines shown to the buyer · gal = gallery slots (images + video) · 1st
= first image (room / framed / flat) · opt = size options with a price · price
= min / max EUR across sizes · sale = strikethrough shown · ship = free y/n,
ships from · deliv = delivery estimate shown on 2026-10-12 (ship-to BE) · ret
= returns · shop = rating / reviews / sales / years · listed = "Listed on" ·
fav = favourites · irev = item reviews.

| kw | slot | cat | hl | gal | 1st | opt | price | sale | ship | deliv | ret | shop | listed | fav | irev | BS/Star |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| botanical print | 5 | Prints > Giclée | Designed by shop; Vintage from the 19th century | 13+v | room | 9 | 90.87 / 133.55 | y | y, FR | Oct 19-29 | not accepted | 4.9 / 122 / 1k / 4 | 2026-10-07 | 32 | 0 | – |
| sage green wall art | 1 | 59 | 23 | 36 | 1/4 | 3 | 18 | 2 | 21 | 18 | 16 | 34 | 6 | 17 | 21 | 23 | 7.48/44.90/146.52 | 117 | 30 | 5 | 21 | absent |
| sage green wall art | 2 | 60 | 12 | 48 | 2/2 | 1 | 20 | 2 | 35 | 30 | 25 | 44 | 6 | 15 | 36 | 33 | 5.53/39.00/159.45 | 141 | 36 | 11 | 11 | absent |
| sage green wall art | 3 | 60 | 12 | 48 | 0/1 | 0 | 22 | 1 | 37 | 30 | 26 | 40 | 14 | 15 | 40 | 28 | 7.18/31.40/227.94 | 145 | 40 | 7 | 9 | absent |
| botanical line art print | 1 | 55 | 22 | 33 | 2/7 | 0 | 12 | 1 | 26 | 17 | 15 | 20 | 16 | 13 | 22 | 29 | 4.50/22.84/127.50 | 73 | 28 | 4 | 7 | absent |
| botanical line art print | 2 | 60 | 12 | 48 | 2/4 | 0 | 30 | 7 | 28 | 22 | 16 | 20 | 25 | 13 | 33 | 43 | 3.92/20.46/109.61 | 145 | 36 | 9 | 4 | absent |
| botanical line art print | 3 | 60 | 12 | 48 | 3/3 | 0 | 28 | 6 | 30 | 21 | 19 | 20 | 20 | 18 | 30 | 43 | 4.74/21.61/86.18 | 205 | 31 | 13 | 3 | absent |
| botanical print set of 3 | 1 | 56 | 23 | 33 | 3/5 | 0 | 11 | 0 | 29 | 4 | 29 | 22 | 13 | 33 | 27 | 11 | 16.00/44.90/58.45 | 145 | 30 | 2 | 8 | absent |
| botanical print set of 3 | 2 | 60 | 12 | 48 | 1/2 | 1 | 20 | 1 | 35 | 19 | 33 | 25 | 20 | 48 | 44 | 20 | 5.42/34.39/90.87 | 145 | 33 | 12 | 2 | absent |
| botanical print set of 3 | 3 | 60 | 12 | 48 | 1/2 | 0 | 20 | 1 | 24 | 15 | 26 | 30 | 19 | 48 | 40 | 25 | 10.11/34.39/92.39 | 122 | 34 | 11 | 6 | absent |
| quiet luxury wall art | 1 | 60 | 24 | 36 | 0/2 | 1 | 11 | 3 | 31 | 22 | 11 | 15 | 3 | 4 | 26 | 23 | 3.99/64.92/180.58 | 38 | 30 | 0 | 23 | absent |
| quiet luxury wall art | 2 | 60 | 12 | 48 | 0/2 | 0 | 20 | 8 | 38 | 29 | 14 | 15 | 9 | 6 | 31 | 40 | 4.71/63.86/307.97 | 28 | 43 | 1 | 12 | absent |
| quiet luxury wall art | 3 | 60 | 12 | 48 | 1/2 | 1 | 18 | 3 | 35 | 30 | 10 | 10 | 13 | 2 | 33 | 41 | 6.35/63.17/242.64 | 54 | 43 | 1 | 10 | absent |
| biophilic wall art | 1 | 55 | 22 | 33 | 1/2 | 0 | 13 | 0 | 23 | 25 | 18 | 25 | 0 | 2 | 27 | 18 | 20.33/150.00/712.50 | 69 | 30 | 0 | 20 | absent |
| biophilic wall art | 2 | 59 | 12 | 47 | 0/1 | 0 | 20 | 0 | 40 | 34 | 21 | 34 | 0 | 4 | 40 | 28 | 20.23/186.65/1397.50 | 69 | 43 | 2 | 11 | absent |
| biophilic wall art | 3 | 59 | 11 | 48 | 0/0 | 0 | 21 | 0 | 33 | 32 | 17 | 26 | 1 | 1 | 37 | 31 | 22.99/156.00/667.50 | 78 | 46 | 1 | 11 | absent |
| watercolor botanical print | 1 | 57 | 22 | 35 | 1/5 | 0 | 27 | 0 | 33 | 26 | 30 | 30 | 6 | 33 | 29 | 11 | 18.03/29.25/122.95 | 6600 | 9 | 26 | 11 | absent |
| watercolor botanical print | 2 | 60 | 12 | 48 | 1/5 | 0 | 36 | 1 | 42 | 30 | 34 | 34 | 13 | 32 | 36 | 18 | 3.92/28.50/110.67 | 6600 | 17 | 29 | 7 | absent |
| watercolor botanical print | 3 | 60 | 12 | 48 | 0/1 | 0 | 39 | 0 | 44 | 33 | 36 | 35 | 13 | 29 | 40 | 19 | 6.42/28.50/270.00 | 6600 | 15 | 32 | 4 | absent |

**Positive control (detector check), same conditions.** Query = 8 tokens of
our most-viewed listing's own title (gp 80, "Vintage" dropped, see below):
QhotoArt appears as an **Ad at slot 1** of page 1 (EUR 19.00, free shipping,
"Ships from BE", shop review count 2), and organically only at **page 3, slots
46 and 54**. So the detector finds us, and "absent" above is a real absence.
Even on a near-exact title query our organic rank is page 3.

**Query rewrite observed:** any query containing the token `vintage` was
redirected to `/search/vintage?…&vintage_rewrite=…` (3 of 3 tries; the third, `vintage botanical print`, showed "Showing botanical print in vintage" with the Vintage filter applied). With the
full title (which begins "Vintage") our listing was not on page 1, not even as
an Ad. Mechanism not verified (phase 5); recorded, not interpreted.

First image, top 8 cards per page 1 as rendered (ads included, coded from one
screenshot each; room = artwork in an interior scene, framed = framed on a
plain ground, flat = artwork alone):

| kw | room | framed | flat | note |
| --- | --- | --- | --- | --- |
| botanical print | 3 | 3 | 2 | |
| sage green wall art | 6 | 0 | 2 | |
| botanical line art print | 3 | 4 | 1 | |
| botanical print set of 3 | 5 | 3 | 0 | |
| quiet luxury wall art | 5 | 0 | 3 | product mix: oil, glass, 3D-textured, prints |
| biophilic wall art | 5 | 0 | 3 | 8/8 preserved-moss panels, not prints |
| watercolor botanical print | 4 | 3 | 1 | |
| **total (56)** | **31** | **13** | **12** | |
| botanical print | 6 | Prints > Giclée | Made by shop; Materials: Paper | 11+v | flat | 16 | 22.80 / 120.00 | y | y, PL | Oct 19-24 | accepted | 4.7 / 1.5k / 8.5k / 5 | 2026-09-30 | 4354 | 92 | – |
| botanical print | 7 | Prints > Giclée | Handpicked by shop; Vintage from the 19th century | 16+v | framed | 9 | 109.61 / 151.89 | y | y, FR | Oct 19-30 | not accepted | 4.9 / 122 / 1k / 4 | 2026-09-28 | 226 | 0 | – |
| sage green wall art | 4 | Prints > Digital Prints | Designed by shop; Materials: Paper | 15+v | room | 16 | 50.87 / 166.06 | n | y, UK | Oct 17-21 | not shown | 4.9 / 211 / 2.2k / 5 | 2026-10-09 | 653 | 7 | – |
| sage green wall art | 6 | Prints > Giclée | Designed by shop; Materials: Canvas, wood | 9+v | room | 14 | 146.63 / 252.17 | y | n, US | Oct 20-26 | accepted | 4.8 / 536 / 2.7k / 2.5 | 2026-10-10 | 2599 | 33 | BS, Star |
| sage green wall art | 7 | Home & Living > Wall Decor > Wall Hangings | Designed by shop; Materials: Paper | 9 | framed | 19 | 15.73 / 48.40 | n | n, US | Oct 15-21 | not accepted | 4.9 / 10.3k / 48.4k / 5 | 2026-10-12 | 12780 | 42 | BS, Star |
| botanical line art print | 5 | Home & Living > Wall Decor | Designed by shop; Materials: Archival paper | 9+v | room | 13 | 27.09 / 120.48 | n | y, SE | Oct 16-23 | not accepted | 4.7 / 54 / 384 / 1 | 2026-10-12 | 108 | 2 | – |
| botanical line art print | 6 | Prints > Digital Prints | Designed by shop (machine-translated) | 12 | room | 21 | 22.84 / 94.27 | n | y, DE | Oct 15-22 | not accepted | 4.8 / 29 / 296 / 9 mo | 2026-09-15 | 24 | 0 | – |
| botanical line art print | 7 | Prints > Digital Prints | Designed by shop | 13 | framed | 15 | 4.50 / 84.00 | y | y, FR | Oct 14-26 | accepted | 4.8 / 64 / 377 / 9 mo | 2026-08-25 | 215 | 1 | – (title says "digital download"; sells digital + physical options) |
| botanical print set of 3 | 4 | Home & Living > Wall Decor > Wall Hangings | Designed by shop; Materials: Archival paper, photo paper, printer paper | 9+v | room | 12 | 44.90 / 149.90 | n | y, DE | Oct 17-20 | not accepted | 4.7 / 145 / 1k / 2 | 2026-10-11 | 75 | 1 | – |
| botanical print set of 3 | 6 | Home & Living > Wall Decor > Wall Hangings | Designed by shop; Materials: Archival paper, photo paper, printer paper | 9+v | room | 12 | 44.90 / 149.90 | n | y, DE | Oct 17-22 | not accepted | 4.7 / 145 / 1k / 2 (same shop as slot 4) | 2026-10-10 | 53 | 1 | – |
| botanical print set of 3 | 7 | Home & Living > Wall Decor > Wall Decals & Murals > Murals | none shown | 6 | room | 4 | 23.99 / 38.99 | n | y, FR | Oct 19-22 | accepted | 5.0 / 2 / 33 / 1 mo | 2026-10-06 | 36 | 1 | – |
| quiet luxury wall art | 4 | Prints > Digital Prints | Designed by shop; Digital download; 1 ZIP | 9 | framed | 0 (one price) | 16.79 | y | n/a (digital) | n/a | n/a | 4.6 / 5 / 400 / 5 mo | 2026-10-11 | 61 | 0 | – (DL) |
| quiet luxury wall art | 6 | Home & Living > Wall Decor > Wall Hangings | Designed by shop; Materials: Archival paper | 8+v | room | 17 | 19.44 / 89.75 | n | y, UK | Oct 16-21 | accepted | 5.0 / 25 / 179 / 1 yr | 2026-09-14 | 34 | 0 | Star |
| quiet luxury wall art | 7 | Home & Living > Wall Decor | Designed by shop | 6 | room | 14 | 105.11 / 915.25 | y | y, BG | Oct 20-22 | not accepted | 4.7 / 461 / 2.7k / 2.5 | 2026-09-29 | 194 | 0 | – (canvas) |
| biophilic wall art | 5 | Home & Living > Wall Decor > Wall Hangings | Made by shop; Materials: Moss, olive wood | 17+v | room | 45 | 184.41 / 1191.76 | y | y, TR | Oct 17-Nov 3 | accepted | 4.8 / 95 / 283 / 1 yr | 2026-10-12 | 287 | 5 | – (moss panel) |
| biophilic wall art | 6 | Home & Living > Wall Decor > Wall Hangings | Made by shop; Materials: Metal, moss, olive wood | 10+v | not coded | 5 | 94.25 / 185.25 | y | n, ES | Oct 16-24 | accepted | 5.0 / 78 / 272 / 2 | 2026-08-16 | 129 | 5 | Star (moss panel) |
| biophilic wall art | 7 | Home & Living > Wall Decor | Materials: Moss (machine-translated) | 10+v | not coded | 10 | 469.75 / 1030.50 | y | y, PL | Oct 14-Nov 4 | not shown | 4.9 / 576 / 2.4k / 6 | 2026-08-26 | 12 | 0 | Star (moss panel) |
| watercolor botanical print | 5 | Art & Collectibles > Painting > Watercolor | Made by shop; Materials: Surface: Paper | 17+2v | room | 34 | 28.50 / 185.25 | y | y, AT | Oct 15-19 | accepted | 5.0 / 6.6k / 26.7k / 8 | 2026-10-06 | 1848 | 45 | Star |
| watercolor botanical print | 6 | Art & Collectibles > Painting > Watercolor | Materials: Surface: Paper | 13+v | room | 29 | 43.50 / 349.50 | y | y, AT | Oct 15-19 | accepted | 5.0 / 6.6k / 26.7k / 8 (same shop as slot 5) | 2026-10-10 | 2093 | 58 | Star |
| watercolor botanical print | 7 | = botanical print set of 3, slot 7 (same listing; coded once) | | | | | | | | | | | | | | |

**Ours on the same extractor (buyer view, same conditions):**

| listing | cat | hl | gal | 1st | opt | price | sale | ship | deliv | ret | shop | listed | irev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gp 80 (organic, most viewed) | Home & Living > Home Decor > Wall Decor | Designed by shop; Materials: Paper | 13, no video | flat (unframed poster on a plain wall, no room) | 6 | 19.00 / 49.00 | n | y, BE | Oct 15-20 | accepted | 5.0 / 2 / 3 / 10 mo | 2026-08-28 | 0 |
| gp 229 (zero, newest) | Home & Living > Home Decor > Wall Decor | Materials: Paper (no "Designed by" line) | 13, no video | flat (same treatment) | 6 | 19.00 / 49.00 | n | y, BE | Oct 15-26 | accepted | 5.0 / 2 / 3 / 10 mo | 2026-10-12 | 0 |
| gp 4 (zero; the 1 row with no candidate) | — | — | — | — | — | — | — | — | — | — | — | "This item is unavailable" | — |

`taxonomy_id` 1027 renders as **Home & Living > Home Decor > Wall Decor** in
the breadcrumb.

## 8. Counts (re-derived from §1–7)

**SERP, page 1, 7 keywords:** 399 cards, **160 ads (40 %)**, 239 organic.
Organic: free shipping 179 (75 %) · every query token in title 177 (74 %) ·
video 176 (74 %) · shop < 500 reviews 174 (73 %) · "Ships from EU" 142 (59 %) ·
sale price 124 (52 %) · set in title 123 (51 %) · Star Seller 105 (44 %) ·
"poster" in title 62 (26 %) · shop ≥ 1k reviews 52 (22 %) · Bestseller 11
(31 of all 399 cards) · digital 9 (4 %). Ad cards with free shipping 104/160.
Pages 1–3 (21 pages): 1,235 cards, 326 ads, 909 organic; free 660 (73 %),
< 500 reviews 664 (73 %), video 676 (74 %).

**Our rank:** absent from pages 1–3 on **7/7** keywords. Positive control: page
3 organic (slots 46, 54) on a near-exact own-title query; Ad at slot 1.

**Listing layer (20 unique listings; 14 from shops < 500 reviews):**

| field | theirs (20) | theirs, shops < 500 (14) | ours |
| --- | --- | --- | --- |
| category deeper than Wall Decor | **17** (85 %) | **12** (86 %) | **0/132** (1027 = Wall Decor) |
| first image = room (of coded) | **13/18** (72 %) | **10/13** (77 %) | **0/133** (flat_mockup at gallery_order 0 on 133/133; live 2/2) |
| video in gallery | 14 (70 %) | 9 (64 %) | 0 |
| gallery images | 6–17 | — | 13 |
| free shipping (of 19 physical) | 16 | — | yes |
| "Materials" line shown | 13 | — | yes ("Paper") |
| returns accepted / not / not shown / n.a. (digital) | 9 / 8 / 2 / 1 | — | accepted |
| "Listed on" within 30 days (≥ 09-12) | 17 | — | — |
| shop < 1 year | 4 | — | 10 months |
| Star Seller | 7 | — | no |
| Bestseller | 2 | — | no |
| "Vintage from the 19th century" | 2 | — | — (made_to_order) |

Category leaves (20): Prints > Giclée 4 · Prints > Digital Prints 4 · Wall
Decor > Wall Hangings 6 · Wall Decor (parent, = ours) 3 · Painting >
Watercolor 2 · Wall Decals & Murals > Murals 1. Of the 14 print-type
listings (moss panels, canvases and the digital-only listing removed), 13 use
a category deeper than Wall Decor.

Ours, from the DB (2026-10-12): galleries hold 1,119 `lifestyle` (room-scene)
images; 61/134 current titles contain "vintage"; listing properties set =
Material multi: Paper, Framing: Unframed (`config/static_config.json`).
