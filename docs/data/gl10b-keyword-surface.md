# GL-10b — Layer 1 discovery: bestseller sweep raw data

**Written incrementally during the sweep (§12.1 discipline 1 — crash insurance).**
Locale: Etsy Belgium (EUR), which is the shop's own currency and market.
Sort used throughout: `order=highest_reviews` + `instant_download=false`.
Badge codes: `BS` = Etsy Bestseller badge · `P` = "Popular now" · `DL` = digital
download (the exclude-digital filter is **leaky** — DL rows still appear).
Ad rows are filtered out in the extractor and are not recorded.

> Sort caveat: Etsy has no "most sold" sort. `highest_reviews` is the closest
> available proxy and it skews to shop age and review-count momentum — exactly
> the bias §4 says to correct for. The Bestseller badge is the better per-listing
> signal and is recorded separately.

---

## D1 — head term "wall art print" (top reviews, digital excluded)

| Badge | Shop | Reviews | Title (truncated) |
| --- | --- | --- | --- |
| BS DL | PawtraitDesignCo | 9.5k | Pet Portrait Custom and Personalized… DIGITAL DOWNLOAD |
| — | PunoPrints | 28.9k | Custom Minimalist Digital Portrait Faceless Illustration ASAP |
| P | OccasionalMotto | 38k | Print digital photos into instant photos \| Custom instant photo prints |
| — | ThePlutonArt | 9.4k | Print your design |
| BS | TheWorldGallery | 25.4k | Custom Vinyl Lyrics Print, Personalised Music Poster… |
| BS | VerbatimARTUK | 10.7k | Personalised Metallic Foil Song Lyrics Print \| Anniversary Gift… |
| P | LittleWildStudios | 144 | Custom Toddler Mispronunciation Print \| Personalised Keepsake |
| P | Printogenic | 2.7k | Custom Canvas Print from your photo, Framed Canvas Print… |
| P | WanderingRabbitPrint | 9.2k | A4 Custom Foil Song Lyrics Art… |

**Coded observation D1-a:** of the top 9 non-ad results at the head term,
**9/9 are personalised or customer-supplied-file products.** Zero are a
fixed, pre-designed print. This is the single strongest count in the sweep so
far and it is structural, not aesthetic.

---

## D2 — "botanical line art print"

| Badge | Shop | Reviews | Title |
| --- | --- | --- | --- |
| BS | SarusWeddingTree | 650 | Up to 7 Flowers. Family Flower Bouquet Birth Month Flower Art. CUSTOM |
| — | TheWorldGallery | 25.4k | Botanical Line Art Print, Minimal Leaf Illustration, Modern Organic Poster |
| — | MotherAndSunStudioUK | 5.4k | Vintage Botanical Floral Line Art Print \| Antique Wildflower Illustration, Cosy Cottagecore |
| — | GateOfDesign | 3.8k | Framed Botanical Line Art Print **Set**: Minimalist Floral Sketch Printed Wall Art |
| BS | WoodSagePrints | 2.5k | **Set of 3** Neutral Wall Prints, Botanical Wall Prints, Bedroom Wall Prints… |
| — | LotusNurseryArt | 11.9k | Beige Botanical Line Art Print **Set**: Minimalist Floral Wall Decor |
| — | TheWorldGallery | 25.4k | Botanical Line Art Prints, Minimalist Leaf and Flower Wall Decor |
| — | WoodSagePrints | 2.5k | Neutral Wall Prints **Set of 3**, Botanical Wall Prints, Bedroom Wall Prints… |

**Coded observation D2-a:** 4 of 8 titles sell a **set**, not a single print.
**D2-b:** the recurring non-subject modifiers are **colour-family words**
(*neutral*, *beige*, *sage*) and **room words** (*bedroom*), neither of which
appears anywhere in `docs/safe_evergreen_bucket.md`.

---

## D3 — "moon phase print"

| Badge | Shop | Reviews | Title |
| --- | --- | --- | --- |
| BS | HeartoftheEarthArts | 4.5k | Lunar Calendar \| Wheel of the Year \| Moons, Seasons & Astrology |
| BS | PaperEmporiumCo | 35.6k | Custom Star Map Print: Baby Constellation Gift or Any Event |
| — | MariaRikteryteStudio | 3.5k | **2027** Mini Lunar Calendar: Stocking Filler PRE-ORDER |
| BS | OriginalLunarPhase | 3k | **2026** Lunar Phase Calendar, Moon Art Print, Choose Your Color |
| — | PaperEmporiumCo | 35.6k | Custom Moon Phase Print - The Night We Met (Any Wording) |
| — | PaperEmporiumCo | 35.6k | Fully Custom Moon Phase Print: Any Wording, Accurate Moon Phase from Date |
| — | LunaAndFernStore | 1.1k | Wolf **2026** Lunar Calendar Print |
| — | ArtMemento | 5.9k | On The Day You Were Born Custom Moon Phase Print |
| — | CreatedByZoeAU | 2k | Custom Moon Phase Print \| Personalised Celestial Poster |
| — | rendij | 2.7k | **2026** Large MOON CALENDAR in NIGHT Sky - Silkscreen Print |

**Coded observation D3-a — and it is a direct correction to
`safe_evergreen_bucket.md`.** "moon phase print" is listed there as
safe-evergreen. In the live top-10 it is occupied by two things the pipeline
cannot make: **dated calendars** (4/10 carry a year, 2026 or 2027 — seasonal by
construction, and stale the moment the year turns) and **personalised
date-derived prints** (4/10). Only the remainder is a fixed design. The *term*
is evergreen; the *ranking listings for it* are not.

---

## D4 — "mid century modern wall art"

| Badge | Shop | Reviews | Title |
| --- | --- | --- | --- |
| BS | KraftyGoose | 3.3k | 3D Printed MCM Elongated Pointed Starbursts Wall Art (not a print) |
| — | TheWorldGallery | 25.4k | Minimalist Retro Botanical Poster, Vintage Plant Wall Art, Mid Century Style Decor, **Arch** N… |
| — | BrightBlueStar | 3.7k | **Bauhaus** Print Orange Wall Art Bauhaus Poster Modern Art Minimalist Geometric Art Mid Century |
| BS | TheWorldGallery | 25.4k | Mid-Century **Japanese Bird** Art Print, Retro Blue Bird Poster, Minimalist Animal Illustration |
| — | PrintParty96 | 85 | Orange Bauhaus Print **Set**: Mid-Century Modern Wall Art |
| — | Speur | 42 | **Amber Glass** Wall Art Print — Modern Abstract Poster with Warm **Honey** Tones |

**Coded observation D4-a:** *Bauhaus* recurs twice in six results and is absent
from the bucket. **D4-b:** colour-as-keyword again (*orange*, *amber*, *honey*).

---

## D5 — "minimalist line art poster"

| Badge | Shop | Reviews | Title |
| --- | --- | --- | --- |
| — | BuBuLines | 2.2k | Custom Couple Line Art Portrait: Personalized Drawing |
| — | RosenaArtStudio | 324 | One Line Drawing \| custom couple portrait \| personalized |
| — | LumiMintDesigns | 17 | Surfer Canvas Print, Ocean Wave Wall Art, Minimalist Coastal Decor, Navy Blue Line Art |
| — | galerie61 | 3.9k | **Picasso — Elephant, Exhibition Vintage Line Art Poster** |
| — | NINETY4studio | 3k | Custom One Line Dog Portrait (Digital File) |
| — | galerie61 | 3.9k | **Picasso — The Cat, Exhibition Vintage Line Art Poster** |
| BS | EdFoxEd | 110 | Peeking Dog Wall Art, Minimalist Line Art Poster, **Terracotta Kitchen** Wall Decor, Pet Lover |
| — | LineArtPrintsDE | 11 | Poster: Minimalist Line Art Couple Illustration \| Sensual Body Line Art |

**Coded observation D5-a:** "single line drawing art" / "continuous line
illustration" are in the bucket, but the live term is owned by **custom couple
and pet portraits**. Another bucket term whose SERP the pipeline cannot compete
in. **D5-b:** the two galerie61 results are **public-domain artist exhibition
posters** — a category note, not a keyword (see the findings file; it is not a
route open to us on the Etsy IP rules).

---

## D6 — "gallery wall set prints"

| Badge | Shop | Reviews | Title |
| --- | --- | --- | --- |
| BS | KelseyMDesigns | 8.2k | **Set of 6** Construction Vehicle Art Prints, Kids Gallery Wall Set |
| BS | EverGiftCo | 461 | Soccer Poster Set, **4 Piece** Football Gallery Wall |
| — | CallaPrintShop | 174 | Sage Green and Dusty Pink Floral Gallery Wall Art **Set of 6** |
| — | SimplyExtraJordanary | 2.2k | Gallery Wall Set, Print Sets, Trendy Art Posters, **Set of 6** |
| — | PeachiPrints | 2.7k | Wild Love Pastel Animal Print **Set**: Girls Room Decor, **A5-A2** |
| — | FranHaslamDesigns | 2.1k | Greek Mythology **3 Print Bundle Set**: Mix and Match Gallery Wall Art (A5) |
| — | DIVANNO | 3k | **Neutral Gallery Wall**, William M… |

**Coded observation D6-a:** every non-frame result in this SERP is a multi-print
set, and the set size is **in the title as a number** ("Set of 6", "4 Piece",
"3 Print Bundle"). This is the basket-size lever §"Goal reframe" predicted, and
it is a **roadmap finding, not a GL-10b build** (§10 defers set merchandising).

---

## Discovered-term raw list (pre-tagging — tagging happens in the keyword delta)

Colour/tone: neutral, beige, sage green, dusty pink, terracotta, navy blue,
amber, honey, orange, pastel, black and white
Room/use: bedroom, kitchen, nursery, girls room, living room, hallway, entryway,
office, dining
Style/movement: bauhaus, japandi, cottagecore, retro, vintage, boho,
maximalist, dopamine decor, eclectic, coastal, arch
Form/merch: set of 3, set of 6, 4 piece, print bundle, mix and match,
gallery wall set, triptych, framed / unframed, A5–A2, canvas
Subject seen ranking that is absent from the bucket: japanese bird, wildflower,
elephant, sunburst/starburst, ocean wave, greek mythology

## Shop shortlist carried to the rubric (§4 sampling rule — reached by being
## behind a ranking listing, never by looking nice)

TheWorldGallery · WoodSagePrints · LotusNurseryArt · MotherAndSunStudioUK ·
GateOfDesign · galerie61 · BrightBlueStar · OriginalLunarPhase ·
SimplyExtraJordanary · DIVANNO
