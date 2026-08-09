# GL-10b — Layer 1 rubric, filled

**Written one row at a time, the moment each shop is coded** (§12.1 discipline 1).
Terse structured rows only — narrative goes in the findings file, once, at the end.
Visual rows judged at true display size, never zoomed (§4).

## Rubric corrections, recorded before the rows

Two fields in §4's rubric turned out not to be codeable as written. Flagged
rather than fudged (CLAUDE.md §3):

1. **"Tags" is not observable.** Etsy no longer exposes listing tags to buyers —
   not in the rendered page, not in the HTML, not in a meta tag (checked on a
   live listing: `"tags":` blob absent, `meta[name=keywords]` absent). The row is
   coded **NOT OBSERVABLE** everywhere, and the **title-token surface is used as
   the proxy** throughout. This weakens artefact 5 slightly — the keyword delta
   is built from title tokens and SERP occupancy rather than from competitors'
   actual tag lists — and that limitation belongs in the findings file.
2. **"Sales count" is shop-level only.** Etsy gives a shop total, never a
   per-listing one. Per-listing demand is proxied by the Bestseller badge and
   review count, as in the discovery file.

## Spec correction discovered mid-sweep (feeds Layer 2 / §7.0 obs. 4)

> **⚠️ THIS NOTE IS WRONG AND IS KEPT ON PURPOSE. See §L2-1 below for the
> correction.** `isbl_1680x420` is Etsy's CDN *render* size; the upload spec is
> still 1600 × 400. Left in place because §7.0 obs. 4 asked the sweep not to
> assume either the old spec or the live file was right, and the audit trail of
> getting that wrong and then checking is the point.

TheWorldGallery's banner asset is served at **`isbl_1680x420`** — i.e. Etsy's
current big-banner spec is **1680 × 420 (4:1)**, not the 1600 × 400 recorded in
the GL-10a brief §3. Same 4:1 ratio, different pixel dimensions. To be confirmed
against Etsy's own help pages in Layer 2 before it is treated as settled, but it
is first-party evidence from a live shop and it means **the GL-10a assets are
under-sized for the current spec**, independently of any D-A decision.

---

## S1 — TheWorldGallery

| Field | Coding |
| --- | --- |
| Scale | **195,865 sales** · 13,368 listings · 6 yrs (since 2020) · 25.4k reviews, 4.8 · 31,511 admirers · London UK |
| First gallery image | flat art, full-bleed, no frame, no room — the print itself. Text burned in on *some* listings (the "ANY POSTER FRAMED / SIZES A1 A2 A3 A4" featured items are size-chart-as-first-image), but not on the botanical set |
| Gallery composition | **14 images** on the coded listing. Order: flat art → in-room styling → detail/paper shot → size chart |
| Title pattern | **4 comma-separated clauses, 138 chars, subject front-loaded, no brand name, no pipes or dashes.** Coded example: `Vintage Botanical Wall Art Set of 3, Cottagecore Floral Prints, Wildflower Botanical Poster Trio, Soft Earthy Nature Art for Home Decor` → [style+subject+form+qty] / [aesthetic+subject+form] / [subject+form synonym] / [tone + use] |
| Tags | NOT OBSERVABLE (see correction 1) |
| Description skeleton | **4 blocks, ~90 words of prose.** (1) benefit-led opening naming subject + tone; (2) aesthetic/interior-context sentence ("Perfect for a cottagecore interior"); (3) **room-placement sentence** ("Ideal for bedrooms, hallways, or cozy living spaces"); (4) POSTAGE/packaging block. Materials sit in Etsy's structured Highlights field, not in prose. **No AI disclosure** (not an AI shop) |
| Price ladder | 13 size variants across **three measurement systems** (A-series, cm, inches). A4×3 €33.96 → A1×3 €95.99 = **2.83× spread**. Postage €9.58 charged separately, not free |
| Sections | **15 sections, subject-based**, and three of them are **set-size sections**: `Sets of 2` (66), `SETS OF 3` (1369), `Gallery Walls & Big Sets` (84). Others: Food and Drink, Cats, Japanese and Oriental, Cultural Art, Custom & Personalised, Other Art (8284), Monet, Van Gogh, William Morris, Other Famous Art, Kids & Nursery, FRAMED POSTERS |
| Series behaviour | **Yes, and it is a primary merchandising axis** — 1,369 listings in the set-of-3 section alone; sets sold as single listings with a qty-in-title |
| About | **~80 words.** Answers: what we sell ("An eclectic mix of classic & modern wall art"), why we do it, and a promise of continuous new work. Plus named shop members with roles (Alex — Designer/Customer Service/Owner; Jria — Dispatcher) |
| Announcement | Present but inert — "Welcome! Contact us if you wish to inquire about custom sizes." Last updated Apr 2025 |
| Reviews | not coded this pass |
| **Banner treatment** | **Photographic, imagery-led, 100 % imagery / 0 % type.** A classical picture-gallery interior, warm/light ground, deep perspective. **Shop name not repeated. No tagline. No promo text.** Served at `isbl_1680x420` |
| **Banner + icon coherence** | **Weak-to-none as a system, strong as a theme.** Banner is a photograph; icon is a flat cream-ground wordmark badge. They share only the "old master gallery" idea, no shared mark, palette or type |
| **Icon treatment** | **Mark-in-ground**, cream/off-white square. Discobolus statue silhouette above a three-line `THE / WORLD / GALLERY` wordmark. At true avatar size (74 px rendered) **the wordmark is unreadable** — it reads as a dark blob on cream. Same failure class as the live QhotoArt icon |
| **Shop-name-in-search** | icon reads as a cream tile with a smudge; the *name* does all the work |

---

## S2 — WoodSagePrints

| Field | Coding |
| --- | --- |
| Scale | **17,346 sales** · 819 listings · 5 yrs · 2.5k reviews, 4.9 · 1,537 admirers · Eastbourne UK |
| First gallery image | **framed-in-room lifestyle, 4/4 featured items.** Warm neutral interiors, oak frames, styled props. No burned-in text on the art itself |
| Gallery composition | not fully coded (shop-level pass) |
| Title pattern | from SERP: `Set of 3 Neutral Wall Prints, Botanical Wall Prints, Bedroom Wall Prints, Botanical Art, B…` — **comma-stacked, near-repetitive**, leads with set qty, repeats "Wall Prints" three times, carries a **room word** and a **colour-family word** |
| Tags | NOT OBSERVABLE |
| Description skeleton | not coded (shop-level pass) |
| Price ladder | not coded (shop-level pass) |
| Sections | **18 sections, mixed axes** — room (Kitchen Wall Art 31, Bathroom Quotes 5), subject (Botanical Floral Prints 131, William Morris 12), style (Abstract & Minimalist 247, BOHO WALL ART 17), occasion (Wedding Signs 16, Personalised Christmas 4), and **tone** (Funny Swear word Quotes 28, Self Love Quotes 18). No section is called "Posters" or "Prints" alone |
| Series behaviour | yes — set-of-3 is the lead SERP product |
| About | not coded |
| Reviews | not coded |
| **Banner treatment** | **Hybrid: lifestyle photography + type lockup + promo panels.** Left third = styled living room with three framed prints; centre = `WELCOME TO / WOOD SAGE / Prints` (serif caps + script); right = a single framed product shot. **Ground light** (sage/beige/cream). Roughly **60 % imagery / 40 % type**. **Shop name repeated. Promo text present** — a translucent panel reading `SAME DAY DESPATCH / FREE SHIPPING`. **It is a carousel** (dot indicators) |
| **Banner + icon coherence** | **Strong.** Same serif-caps + script wordmark, same sage ground, in both |
| **Icon treatment** | **Mark-on-ground**, circular, sage. **Wordmark only, no symbol.** At true avatar size (74 px) `WOOD SAGE Prints` is **unreadable** — a grey disc with texture |
| **Shop-name-in-search** | icon contributes nothing legible; recognisable only as "the sage circle" |

---

## S3 — LotusNurseryArt

| Field | Coding |
| --- | --- |
| Scale | **59,910 sales** · 7,820 listings · **11 yrs** · 11.9k reviews, 4.8 · 10,133 admirers · California US |
| First gallery image | **framed-in-room lifestyle with set-of-3 shown together**, 2/2 featured. Props (teepee, knitted giraffe) — heavily styled to the nursery buyer |
| Title pattern | from SERP: `Beige Botanical Line Art Print Set: Minimalist Floral Wall Decor` — **colon-separated two-part**: [colour + subject + form + Set] : [style + subject + use]. Shorter than TheWorldGallery's |
| Tags | NOT OBSERVABLE |
| Sections | **20 sections, and the taxonomy is the *room*, then the theme within it** — GENDER NEUTRAL NURSERY 1579, NURSERY DECOR GIRL 1818, NURSERY DECOR BOY 910, then ADVENTURE / RAINBOW / BUTTERFLY / ANIMAL / SPACE / FLORAL / NAUTICAL / BOHO NURSERY. Plus **two build-your-own sections: `CREATE YOUR SET` (17) and `CREATE CANVAS SET` (13)**, and `MIX & MATCH` (17) |
| Series behaviour | **Yes, and productised** — "create your set" is its own section, i.e. the set is a purchasable configurator, not just a bundle listing |
| Price ladder | "On sale" section contains **7,820 of 7,820 listings** — the entire shop is permanently discounted |
| **Banner treatment** | **Photographic lifestyle + right-hand type block.** Nursery scene with a set of 3 framed prints; type reads `CUSTOM DESIGNS FOR YOUR ROOMS - MIX&MATCH` / `NURSERY WALL ART` / *`Art for little dreamers`* (script) / `CELEBRATING 11 YEARS AT ETSY`. **Ground light**, warm blush/taupe. ~65 % imagery / 35 % type. **Shop name NOT repeated** — the banner leads with the *category* ("NURSERY WALL ART"), not the brand. **Tagline present. Longevity as a trust signal.** Carousel (4 dots) |
| **Banner + icon coherence** | **Weak.** Banner is photographic and typographic; icon is a flat cartoon bear head. Shared only in subject register (nursery/childlike) |
| **Icon treatment** | **Mark-on-ground**, pale lilac square, **symbol only, no wordmark** — a bear face. **The only icon in the sample so far that is legible at 74 px**, and it is legible precisely because it is one high-contrast symbol with no type |
| **Shop-name-in-search** | reads cleanly — a recognisable bear |

---

## S4 — MotherAndSunStudioUK

| Field | Coding |
| --- | --- |
| Scale | **31,961 sales** · 1,276 listings · 6 yrs · 5.4k reviews, 4.8 · 6,934 admirers · UK. Carries Etsy's **Star Seller** badge (the purple mark by the shop name) |
| First gallery image | **flat art, full-bleed, no frame, no room — 4/4 featured items.** The print itself, edge to edge. Same treatment QhotoArt's pipeline produces |
| Title pattern | from SERP: `Vintage Botanical Floral Line Art Print \| Antique Wildflower Illustration, Cosy Cottagecore` — **pipe as the primary separator, commas inside clauses**. Mixed separators |
| Tags | NOT OBSERVABLE |
| Sections | **17 sections, style-and-era-led** — RETRO/MIDCENTURY 146, CLASSIC/HERITAGE/VINTAGE 42, MATISSE 143, DISCO 30, RETRO MASCOT 66, COWBOY 21, MYSTICAL 91, 1980s 4 — plus room (KITCHEN 163, BEDROOM 41, BATHROOM 14) and tone (HANDWRITTEN QUOTES 40, FUN PHRASES 136). A catch-all **`MISC PRINTS` (203)** exists |
| Series behaviour | implied by the banner offer (buy 3+), not by set listings |
| Price ladder | entire shop "On sale" (1,276 of 1,276) — same permanent-discount pattern as S3 |
| **Banner treatment** | **Promo-led — the loudest in the sample.** Left half is a hand-lettered `30% OFF WHEN YOU BUY 3 OR MORE PRINTS` on a pink candy-stripe ground, with `FREE WORLDWIDE DELIVERY + NO HIDDEN USA TAXES` above it; right half is three lifestyle product shots. **Ground light/bright.** ~50 % imagery / 50 % type, and **the type is all offer, no brand** — the shop name appears nowhere in it. Carousel |
| **Banner + icon coherence** | **Moderate** — both use the pink ground and hand-lettered style |
| **Icon treatment** | **Mark-on-ground**, pink square, **hand-lettered wordmark `mother sun`** with a small sun device. At 74 px the lettering is **illegible**; the pink square is the recognisable part |
| **Shop-name-in-search** | reads as "the pink one" |

---

## S5 — galerie61 — *the outlier, and the most important row in the sample*

| Field | Coding |
| --- | --- |
| Scale | **23,230 sales** · **98 listings** · 5 yrs · 3.9k reviews, 4.8 · 3,431 admirers · Bristol UK |
| **Sales per listing** | **237** — against TheWorldGallery's 14.7, WoodSagePrints' 21, LotusNurseryArt's 7.7, MotherAndSunStudioUK's 25, BrightBlueStar's 35. **An order of magnitude above the sample, on the smallest catalogue in it** |
| First gallery image | **framed print leaning on a floor against a plain wall, 4/4 featured** — identical staging every listing, one repeated scene. Video badge on every card |
| Title pattern | `Picasso - Dog, Exhibition Vintage Line Art Poster, L'éléphant Minimalist Line Drawing…` — **[artist] - [subject], [category], [style]**. Dash after the artist name, commas after |
| Tags | NOT OBSERVABLE |
| Price ladder | **flat €14.75 across all four featured listings, FREE delivery.** The only shop in the sample leading with free delivery rather than a discount |
| Sections | **5 sections, all subject/artist**: Exhibition Prints 14, Picasso 24, William Morris 19, Japanese Art 15, Matisse 26. **No room sections, no tone sections, no catch-all** |
| Series behaviour | implicit — the artist sections *are* the series |
| **Banner treatment** | **Type-led, and the only one in the sample.** A pure white ground, no imagery at all, carrying one fine-line wordmark `galerie` `Sixty` `One` in a hairline serif inside a thin rule box. **No tagline. No promo text. No product.** ~0 % imagery / 100 % type, and the type occupies maybe 25 % of the width — the rest is white space. Not served from the `isbl` banner path |
| **Banner + icon coherence** | **The strongest in the sample.** Banner wordmark and icon monogram are the same hairline-serif system; icon inverts it (light on dark) |
| **Icon treatment** | **Mark-in-ground**, mid-grey square, **white `g61` monogram, no wordmark.** **Legible at 74 px** |
| **Shop-name-in-search** | reads cleanly as a monogram; the grey/white pairing survives the size |

> **Why this row matters to D-A.** galerie61 is the sample's counter-example to
> "the Etsy mean is bright and shouty": a restrained, type-led, high-white-space
> brand with the highest sales-per-listing in the sample by a factor of ~7. It
> does *not* prove register drives sales — the catalogue is public-domain
> artist reproductions, which is a demand story, not a branding one, and the
> confound must be stated (§2.4). But it is a **count**, and it is the one data
> point that argues a calm storefront is not a handicap.

---

## S6 — BrightBlueStar

| Field | Coding |
| --- | --- |
| Scale | **22,790 sales** · 656 listings · 9 yrs · 3.7k reviews, 4.9 · 3,996 admirers · Bath UK. **35 sales/listing** |
| First gallery image | **framed-in-room lifestyle, 4/4 featured** — hands holding a frame, frames on shelves, styled interiors |
| Title pattern | from SERP: `Bauhaus Print Orange Wall Art Bauhaus Poster Modern Art Minimalist Geometric Art Mid Century` — **no separators at all**, a keyword run-on. The least readable pattern in the sample |
| Tags | NOT OBSERVABLE |
| Sections | **18 sections, style-led with room sections beneath** — Fantasy 57, Surreal 36, Mid Century Decor 73, Patent Prints 17, Vintage Designs 140, Fine Art Photography 48, Coastal 42, Abstract Minimalist 30, Retro Home 28, plus Bathroom 49 / Kitchen 36, plus **`Gallery Wall Sets` (1)** and **`Instant Download Art` (21)** |
| Price ladder | entire shop "On sale" (656/656) — third instance of the permanent-discount pattern |
| **Banner treatment** | **Four-panel grid: 3 lifestyle photographs + 1 type panel.** Type panel carries `BRIGHT BLUE STAR` (serif caps) + tagline *"A collection of quirky and classic images to enhance your home"* + the star mark. **Ground light** (white/cream). **75 % imagery / 25 % type. Shop name repeated. Tagline present. No promo text** |
| **Banner + icon coherence** | **Strong** — the star mark and the blue are carried into the icon |
| **Icon treatment** | **Mark-on-ground**, white square, **blue star symbol above a small `BRIGHT BLUE STAR` wordmark.** The **star is legible at 74 px**; the wordmark under it is not. A hybrid: the symbol survives, the type does not |
| **Shop-name-in-search** | reads as a blue star — works |

---

## S7 — DIVANNO

| Field | Coding |
| --- | --- |
| Scale | **17,408 sales** · 1,081 listings · 4 yrs · 3k reviews, 4.8 · 2,617 admirers · London UK. **16 sales/listing** |
| First gallery image | **framed print, single, styled against a plain wall, 4/4 featured.** Consistent staging |
| Title pattern | from SERP: `Neutral Gallery Wall, William M…` — comma-stacked, colour word first |
| Sections | **19 sections, purely subject/era**: Abstract 82, Japanese 101, Beach 23, Botanical 56, Line Art 20, Impressionist 33, **Museum Prints 176**, Animal 78, Middle Eastern 8, William Morris 45, Vintage Posters 98, Academia 63, Kitchen 24, **Gallery Sets 14**, Winter 40, Art Deco 57, Vintage Halloween 44, Modern Art 100, Christmas 18 |
| **Banner treatment** | **Product still-life photography, no type at all.** A shelf of framed prints (Hokusai wave, William Morris, Monet, Rousseau) propped among pampas grass and wooden objects. **Ground light**, warm neutral. **100 % imagery / 0 % type. No shop name, no tagline, no promo** |
| **Banner + icon coherence** | **None** — banner is a photograph, icon is a white type tile |
| **Icon treatment** | **Mark-on-ground**, white square, **`DIVANNO` wordmark + a smaller line beneath.** At 74 px **illegible** — a white square with grey scratches |
| **Shop-name-in-search** | contributes nothing; reads as blank white |

---

## S8 — OriginalLunarPhase — *the second outlier, and it is a warning*

| Field | Coding |
| --- | --- |
| Scale | **22,508 sales** · **3 listings** · **13 yrs** · 3k reviews, **5.0** · 1,491 admirers · New Hampshire US. **≈7,500 sales per listing** |
| First gallery image | **product photography of the actual printed posters** — a fan of the physical calendars laid on grass. Not a render, not a room. The most "this is a real object" first image in the sample |
| Sections | **one section, and it is a year: `2026` (3 items)** |
| Series behaviour | none — one product, colour variants |
| Price ladder | single product, colour choice |
| **Banner treatment** | **Product photography, no type.** The printed posters themselves, fanned out on grass, edge to edge. **Ground light** (green grass, pale posters). **100 % imagery / 0 % type. No name, no tagline, no promo** |
| **Banner + icon coherence** | moderate — both are photographs of the same product |
| **Icon treatment** | **Photographic**, a moon on a dark ground. **Legible at 74 px** — it is one high-contrast circular subject |
| **Shop-name-in-search** | reads as a moon; works |

> **Why this row is a warning, not a model.** It is the strongest
> sales-per-listing figure available and it comes from a **dated product**
> (a 2026 lunar calendar) sold by a 13-year-old shop with a 5.0 rating. It
> confirms D3-a — the "moon phase print" term is owned by dated calendars — and
> it is **not a strategy QhotoArt can copy**: the pipeline makes undated
> designs, and the moat here is 13 years of reviews on one SKU.

---

## S9 — SimplyExtraJordanary

| Field | Coding |
| --- | --- |
| Scale | **20,925 sales** · 393 listings · 8 yrs · 2.2k reviews, 4.9 · 8,019 admirers · Preston UK. **Star Seller.** 53 sales/listing |
| First gallery image | **framed print in a styled room, 4/4 featured** |
| Sections | **16 sections, mixed** — mostly room/subject (KITCHEN 65, NURSERY & KIDS 122, FOOD & DRINK 87, QUOTES 45, PLACES 10, BATHROOM 1, BEDROOM 2, SKIING 6), plus **`SAVE ON BUNDLES` (28)** and — notable for us — **`HORIZONTAL PRINTS` (11)**, a section defined by *orientation* |
| Price ladder | entire shop on sale (393/393) |
| **Banner treatment** | **Lifestyle product photography, no type.** Five framed prints on a sunlit ledge. **Ground light**, warm cream. **100 % imagery / 0 % type. No name, no tagline, no promo** |
| **Banner + icon coherence** | weak — banner photographic, icon a flat olive type tile |
| **Icon treatment** | **Mark-on-ground**, olive square, **three-line `SIMPLY / EXTRA / JORDANARY` wordmark.** At 74 px **illegible** |
| **Shop-name-in-search** | reads as "the olive square" |

---

## S10 — GateOfDesign — *the closest structural analogue to QhotoArt*

| Field | Coding |
| --- | --- |
| Scale | **46,859 sales** · 686 listings · 5 yrs · 3.8k reviews, 4.9 · 9,548 admirers · Europe. **Star Seller.** 68 sales/listing |
| First gallery image | **framed gallery-wall arrangement in a styled room, 2/2 featured** |
| Title pattern | from SERP: `Framed Botanical Line Art Print Set: Minimalist Floral Sketch Printed Wall Art` — colon-separated, **leads with the product form ("Framed")** |
| **Sections** | **12 sections, and the naming convention is the finding.** Six of them carry an **ALL-CAPS qualifier prefix + descriptor**: `PRINTED Gallery Sets` 35, `PRINTED Single Prints` 132, `PRINTING Service` 2, `VINTAGE Gallery Sets` 135, `VINTAGE Single Prints` 119, `VINTAGE Square Wall Art` 20. The rest are style/season: ECLECTIC 64, BOHO NEUTRAL 12, FALL HALLOWEEN 42, CHRISTMAS Vintage 64, CHRISTMAS Minimal 61. **The primary split is fulfilment/form (printed-and-shipped vs digital vintage), not subject** — structurally identical to QhotoArt's framed-photography vs generated-prints split |
| Series behaviour | **yes, and it is the second axis of the section taxonomy** — "Gallery Sets" vs "Single Prints" repeated under each qualifier |
| Price ladder | 460 of 686 on sale |
| **Banner treatment** | **Hybrid, and the most complete lockup in the sample.** Left third: styled room with a 6-print gallery wall. Centre: `PRINTABLE & SHIPPED WALL ART` (serif caps) over *`Curated Designs for a Cozy Home`* (tagline), then a large script wordmark `Gate of Design` + `STUDIO`. Right third: a floating gallery-wall arrangement. Bottom centre: **`SALE UP TO 75% OFF`**. **Ground light**, warm grey/cream. ~65 % imagery / 35 % type. **Name repeated. Tagline present. Promo present** |
| **Banner + icon coherence** | **Strong** — the same script wordmark, inverted (black circle) in the icon |
| **Icon treatment** | **Mark-in-ground**, black circle, **script `Gate of Design` wordmark + small caps `STUDIO`.** At 74 px **illegible** — a black disc with a white squiggle |
| **Shop-name-in-search** | reads as "the black circle" |

---

# Coded counts — the input to D-A (§2.4 requires counts, not impressions)

n = 10 shops, all reached by being behind a ranking listing.

| Variable | Count |
| --- | --- |
| **Banner ground light** | **10 / 10** |
| Banner ground dark | **0 / 10** |
| Banner treatment: imagery-only, no type | 4 / 10 (TheWorldGallery, DIVANNO, OriginalLunarPhase, SimplyExtraJordanary) |
| Banner treatment: hybrid imagery + type | 5 / 10 (WoodSage, LotusNursery, MotherAndSun, BrightBlueStar, GateOfDesign) |
| **Banner treatment: type-led, no imagery** | **1 / 10 (galerie61)** |
| Banner contains a product-grid or framed-print imagery | 8 / 10 |
| Shop name repeated in the banner | 4 / 10 |
| Tagline present in the banner | 4 / 10 |
| **Promo / discount text in the banner** | **3 / 10** (MotherAndSun 30 %, GateOfDesign 75 %, WoodSage free-shipping/despatch) |
| Entire catalogue permanently "On sale" | **5 / 10** |
| **Icon legible at true avatar size (74 px)** | **4 / 10** |
| — of which **symbol-led** (no wordmark, or a dominant symbol) | **4 / 4** |
| **Icon illegible at 74 px** | **6 / 10** |
| — of which **wordmark-led** | **6 / 6** |
| First gallery image: framed / in-room / lifestyle | **8 / 10** |
| First gallery image: flat art, no frame | 2 / 10 (TheWorldGallery, MotherAndSunStudioUK) |
| Sections named with a subject axis | 9 / 10 |
| Sections including a **set/bundle** axis | 6 / 10 |
| Sections including a **room** axis | 6 / 10 |
| **Shops using the bare word "Posters" as a section name** | **0 / 10** |
| Median section count | 17 |
| Sales per listing — range | 7.7 (LotusNursery) → 7,500 (OriginalLunarPhase); median ≈ 30 |

---

# Layer 2 — Etsy primary sources, verified 2026-08-06/07

All from `help.etsy.com` articles, read in-browser. No SEO-blog material.

## L2-1 — Banner specs. **The GL-10a spec was right; my mid-sweep note was wrong.**

Source: *Requirements and Best Practices for Images in Your Etsy Shop*
(`help.etsy.com/hc/en-gb/articles/115015663347`).

| Asset | Minimum | Recommended |
| --- | --- | --- |
| Big shop banner | 1200 × 300 | **1600 × 400** |
| Mini shop banner | 1200 × 160 | **1600 × 213** |
| Carousel banner | — | 1200 × 300 |
| Collage banner | 600×300 (2 img) / 400×300 (3) / 300×300 (4) | — |
| Logo | — | **500 × 500** |
| Profile photo | — | 400 × 400 |
| Order receipt banner | 760 × 100 | — |

**Correction to my own note earlier in this file:** the `isbl_1680x420` filename
on competitor shops is **Etsy's CDN render size, not the upload spec.** The
recommended big-banner size is still **1600 × 400** and the logo is still
**500 × 500** — i.e. **GL-10a's assets are correctly specified** and §7.0
observation 4's doubt about the *spec* is resolved in GL-10a's favour.

**But observation 4's other half stands, and is now sourced:** the same article
states *"Images larger than 1MB in file size may not finish uploading."* The
live banner is **1.53 MB**, and **1600 × 896** matches no documented format.

**New and material — the panelled banners are a paid feature.** The article
states plainly that **carousel and collage banners are only available to sellers
subscribed to Etsy Plus.** Five of the ten sampled shops run a panelled or
carousel banner. **QhotoArt on the free tier has exactly one option: a single
static 1600 × 400 big banner.** Any recommendation that assumes a multi-panel
layout is a recommendation to buy Etsy Plus, and must say so.

**File-type trap:** *"transparent .png files are not supported. If a file
contains transparency, the transparent parts of the image will appear black on
Etsy."* Anything `build_final.py` emits must be flattened. Worth a `verify.py`
assertion.

## L2-2 — Shop sections. §3.1's open questions, answered.

Source: *How to Create and Manage Shop Sections*
(`help.etsy.com/hc/en-gb/articles/360000345048`).

- **Section names: up to 24 characters.** The brief's figure is confirmed.
- **Up to 20 custom sections** plus the default "All items".
- **A listing can be in only one section** — which is exactly why multi-section
  routing is code and correctly deferred (§10).
- Empty sections don't render publicly.
- **Renaming is free.** The section URL is `?section_id=<numeric>` — observed on
  every sampled shop — so **a rename does not change the URL.** §3.1's
  "get it right now while there's no traffic to lose" concern is unfounded;
  the name can be changed later at zero cost. It should still be got right, but
  it is no longer a one-way door.

## L2-3 — A copy surface the brief does not have on its list: **the shop tagline**

Source: *SEO for Shop and Listing Pages* (`…/115015663987`).

> "Your tagline appears under your shop name on your shop homepage. It can be up
> to **55 characters**. Use your tagline to briefly describe your shop and the
> items you sell."

QhotoArt has none. It is a **55-character, indexed, shop-level surface** and it
costs one paste. **Added to the storefront checklist as a sixth artefact item.**
The same article names the four shop-page SEO elements as **tagline, About,
images/video, and policies** — three of which are GL-10b deliverables and the
fourth (About images/video, up to 5 images + 1 video) is unbuilt.

## L2-4 — Listing title rules, and **a consequence for the v4.11 Gelato architecture**

Source: same article.

- "Consider using **less than 15 words**."
- "Search engines only show the **first 50 to 60 characters**… include the most
  important traits upfront, like your item's colours, material, and size."
- **"Your listing's URL is based on the title you enter when you first publish
  the listing. Once it's published, the URL won't change again, even if [the
  title changes]."**

> ⚠️ **This is a genuine, previously unrecorded consequence of "Gelato pushes,
> we patch" (CLAUDE.md).** Gelato creates the Etsy listing with *Gelato's*
> auto-generated title; the pipeline then PATCHes the real title via
> `updateListing`. Per Etsy's own documentation **the URL slug is frozen at
> Gelato's title and our patched title never reaches it.** Every QhotoArt
> listing will therefore carry a URL that does not match its title. This is a
> Google-SEO cost, not an Etsy-search one, and it is **not a GL-10b fix** — it
> belongs with GL-29/GL-11 as an architecture note. Flagged, not solved.

## L2-5 — Tags: 13 per listing, **20 characters each**

Source: *How to Use Tags to Get Found in Search* (`…/360000336307`).

- Up to **13 tags**, each up to **20 characters**, letters/numbers/spaces plus
  `'` and `-` (not as the first character).
- "Tags are helpful when there's no matching attribute and are great for
  aspirational or buyer-minded search terms (e.g. 'gift for her')."
- "Use a **diverse array** of tags."

> **The 20-character cap is a hard design constraint on the tag strategy** and it
> disqualifies a lot of the discovered surface: `minimalist landscape print`
> (26), `mid century modern wall art` (27), `continuous line illustration` (28)
> **cannot be tags at all.** The listing-copy spec must generate tags against a
> length budget, not just a relevance one.


