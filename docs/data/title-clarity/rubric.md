# Title-clarity teardown — coded data — 2026-09-29

Scraped signed-out in the built-in browser, Etsy **Belgium** locale, default
relevance sort (no `order=` param), no `instant_download` filter so digital
listings stay visible and tagged. Competitor titles are **not** stored in this
public repo — only coded numbers and short pattern quotes. Our own titles are
in `ours.txt`.

Classifier (one JS function, same code for ours and theirs):
- words = whitespace split; chars = `length`; clauses = split on `,` `|` ` - ` ` – ` ` — ` `: `
- product nouns (`nn`) = non-overlapping matches of
  `wall art|wall decor|home decor|art print|print|poster|decor|canvas|painting|artwork|wall hanging`
- `dig` = digital|download|printable|instant|downloadable
- `phys` (strict) = framed|unframed|canvas|matte|paper|physical|shipped|giclee|made to order|original|handmade
- `poster` counted separately (the brief's rubric counts it as a physical term; see findings R6)
- `n40` = first product noun starts before char 40

## 1. SERP layer — 10 searches, first page, scroll-loaded

| Search | organic cards | of which digital (DL) |
| --- | --- | --- |
| wall art print | 57 | 6 |
| abstract wall art | 38 | 3 |
| botanical print | 35 | 4 |
| minimalist poster | 61 | 5 |
| boho wall art | 37 | 1 |
| japanese art print | 44 | 1 |
| landscape print | 38 | 3 |
| sage green botanical print | 34 | 2 |
| vintage poster ¹ | 44 | 12 |
| vintage herbarium print ¹ | 51 | 0 |

¹ Etsy rewrites any query starting with "vintage" into its **Vintage category**
(`/search/vintage?...`, items 20+ years old). These are not competitors, so both
are **excluded from every length statistic** below and reported separately.

### Groups (deduplicated by listing id)

| Group | n | med chars | med words | med clauses | med product nouns | ≤ 8 words | ≥ 14 words | noun in first 40 | `dig` | `phys` | `poster` | set/bundle | gift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Ours, all** | 108 | 105.5 | 15 | 4 | 3 | 0 % | 96 % | 93 % | 1 % | 6 % | 39 % | 0 % | 0 % |
| **Ours, comma titles** ² | 91 | 104 | 15 | 4 | 3 | 0 % | 97 % | 91 % | 0 % | 2 % | 29 % | 0 % | 0 % |
| Competitor physical, organic | 256 | 120.5 | 18 | 4 | 3 | 5 % | 69 % | 89 % | 0 % | 14 % | 55 % | 24 % | 14 % |
| — Bestseller-badged | 55 | 119 | 18 | 3 | 3 | 5 % | 67 % | 91 % | 0 % | 13 % | 53 % | 7 % | 20 % |
| — not badged, organic | 216 | 120 | 18 | 4 | 3 | 6 % | 69 % | 89 % | 0 % | 15 % | 53 % | 27 % | 13 % |
| Competitor physical, ads | 118 | 99.5 | 15 | 3 | 3 | 3 % | 61 % | 92 % | 1 % | 51 % | 18 % | 15 % | 8 % |
| Competitor digital (DL) | 38 | 112.5 | 16.5 | 4 | 2 | 0 % | 68 % | 79 % | **89 %** | 0 % | 55 % | 45 % | 3 % |
| Vintage category (excluded) | 110 | 104 | 15.5 | 3 | 1 | 5 % | 70 % | 47 % | 0 % | 43 % | 34 % | 26 % | 6 % |

² Comma-only titles; excludes 13 legacy pipe/dash titles and 4 framed
photography listings. Includes ~23 pre-GL-10c comma titles over 15 words.

### Word-count distribution

| Bucket | Ours (91) | Bestseller (55) | Organic (256) |
| --- | --- | --- | --- |
| ≤ 10 | 0 | 9 | 33 |
| 11–14 | 14 | 13 | 54 |
| exactly 15 | **54** | 2 | 12 |
| 16–18 | 15 | 7 | 31 |
| 19+ | 8 | 24 | 126 |

### Product nouns per title

| nn | 0 | 1 | 2 | 3 | 4 | 5 | 6+ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ours (91) | 0 | 4 | 31 | 32 | 20 | 4 | 0 |
| Bestseller (55) | 2 | 5 | 9 | 15 | 15 | 5 | 4 |

### First product noun in the title

| Noun | Ours (91) | Bestseller (55) | Organic (256) |
| --- | --- | --- | --- |
| art print | **51 (56 %)** | 4 (7 %) | 25 (10 %) |
| print | 15 | 12 | 73 |
| wall art | 14 | 10 | 75 |
| poster | 11 (12 %) | **16 (29 %)** | 55 (21 %) |
| other / none | 0 | 13 | 28 |

### Separators

Ours: commas only, 91/91. Bestseller: commas 35, pipes 7, colon 4, none 3,
dash+comma 2, other 4. Organic: commas 140/256, pipes 39, none 18, colon 17.

## 2. Shop layer — 10 shops behind Bestseller-badged physical listings

Picked by order of Bestseller-listing count across the 8 non-vintage SERPs
(ties broken by how many searches the shop showed up in). 12 shop-page titles per shop, plus the badged listing's page.

| Shop | sales | med words | med chars | med nouns | `poster` /12 | `phys` /12 | `dig` /12 | separators | BS listing: chars, physical? | Comparable? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TheWorldGallery | 201.2k | 9 | 58 | 2 | **10** | 2 | 1 | `,` | 131, yes | yes — shop page includes frame add-on listings, so short median |
| HazeAndJuniper | 7.5k | 19.5 | 125 | 4 | **11** | 0 | 0 | mixed `- – ,` | 136, yes | yes |
| GotTheme | 37.1k | 21 | 135.5 | 5.5 | **11** | 0 | 0 | `,` | 135, yes | yes (PD reproductions, sets) |
| MetropolitanArtCo | 1.4k | 11 | 80.5 | 3 | **11** | 0 | 0 | `,` | 136, yes | yes |
| VintageArtQuarter | 13.9k | 21.5 | 132 | 4.5 | **12** | 0 | 0 | `– ,` | 132, yes | yes |
| Knopfmaedchen | 925 | 9 | 51.5 | 1 | 0 | 10 ("original") | 0 | `-` | 60, yes | **no** — hand-carved original lino cuts |
| SomaPrintsArt | 4.7k | 14 | 83.5 | 3 | 0 | 0 | 0 | `— ,` | 88, yes | yes — closest niche to ours (retro floral, burnt orange/teal) |
| Homivia | 280 | 17.5 | 118.5 | 3 | 11 | 0 | **8** | `,` | 133, sells both | mixed digital/physical shop |
| TheOdysseyGallery | 219 | 14 | 86.5 | 0 | 0 | 0 | 0 | `\| ,` | 83, yes | **no** — signed vintage lithographs |
| nishartgallery | 17.4k | 12.5 | 81 | 2 | 0 | 5 ("framed") | 0 | `,` | 89, yes | yes (framed vintage reproductions) |

- For all 10 badged listings, the SERP card title matched the listing's `h1`
  character for character. SERP titles are full titles, not truncated.
- 9 of 10 badged listings show a paper material in Highlights (the 160-char
  capture didn't reach it on the VintageArtQuarter listing). So does ours
  (listing 4584119793 checked: `Materials: Paper`, delivery estimate, no
  digital-download marker).

## 3. Etsy's suggested titles (10 pairs, owner-supplied)

See brief §1.1. Ours median 15 words / 101.5 chars / 4 clauses. Suggestions
median 11 words / 82.5 chars / 2 clauses. 9 of 10 add a format suffix: 8 ×
`(Digital Download)` (wrong) and 1 × `(Matte Paper)`.
