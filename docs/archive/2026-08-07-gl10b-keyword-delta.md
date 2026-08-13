# GL-10b keyword delta — proposed, not applied

**Artefact 5 of 5.** Terms discovered by the Layer 1 bestseller sweep
(`docs/data/gl10b-keyword-surface.md`), each tagged trend-or-evergreen before
it can reach the bucket, per brief §4.

> ⚠️ **Nothing here is applied.** `docs/safe_evergreen_bucket.md` is
> `research.py`'s live input and carries an owner-approval note in its header;
> `EVENT_WINDOWS_2026` in `pipeline/research.py` is code. Changing either
> changes what the pipeline makes. **This file is a proposal for a separate
> owner decision** (brief §10).

## The test being applied

`safe_evergreen_bucket.md`'s own, verbatim: a term qualifies if it *"maps to a
stable aesthetic or universal subject with roughly flat search volume
year-round, rather than a meme, franchise, influencer moment, single season, or
fashion-cycle trend."*

**And one addition this sweep forces.** The bucket was validated on *terms*.
It was never validated against **who ranks for them**. A term can pass the
flat-volume test and still be useless if its SERP is owned by a product the
pipeline cannot make. That is a **third tag**, and it is new:

| Tag | Meaning |
| --- | --- |
| **EVERGREEN** | passes the flat-volume test → propose for the bucket |
| **TREND/SEASONAL** | fails it → propose for `collect_event_lookahead()`'s windows |
| **BLOCKED** | may pass the volume test, but its SERP is owned by personalisation or dated product → **the pipeline cannot compete regardless**, so it belongs in neither list |

---

## Part A — proposed **additions** to `safe_evergreen_bucket.md`

### A1. New bucket: **Colour-family modifiers** — EVERGREEN

Not subjects. **Modifiers** that combine with an existing bucket term, and the
single largest gap the sweep found (findings R3).

```
neutral, beige, sage green, terracotta, dusty pink, navy blue,
black and white, muted earth tones, warm neutral, pastel
```

**Evidence.** `Beige Botanical Line Art Print Set` (LotusNurseryArt, 11.9k
reviews) · `Set of 3 **Neutral** Wall Prints… Botanical` (WoodSagePrints,
**Bestseller badge**) · `**Terracotta** Kitchen Wall Decor` (EdFoxEd,
**Bestseller badge**) · `Sage Green and Dusty Pink Floral Gallery Wall`
(CallaPrintShop) · `**Amber** Glass… Warm **Honey** Tones` (Speur). 6 of 10
shops carry a colour-led section or colour-led titles.

**Why evergreen.** These are interior-decor colour vocabulary, not a fashion
cycle — "neutral" and "black and white" have been decor language for decades.
**One caveat and it is a real one: `sage green` and `terracotta` are closer to a
2020s palette moment than to a permanent one.** They are proposed as evergreen
on the strength of current occupancy, and flagged for re-check rather than
asserted as permanent.

**Implementation note.** These are modifiers, not seed terms — a colour word
alone ("beige") is not a niche. The value is in *combination*, which means it is
as much a change to how `art_brief.py` and the title formula consume the bucket
as it is a change to the bucket. See Part D.

### A2. New bucket: **Room / placement modifiers** — EVERGREEN

```
bedroom wall art, kitchen wall art, bathroom wall art, hallway art,
living room wall art, entryway art, home office wall art, nursery wall art
```

**Evidence.** Room sections in 6 of 10 shops (WoodSagePrints, DIVANNO,
BrightBlueStar, SimplyExtraJordanary, MotherAndSunStudioUK, LotusNurseryArt).
In titles: `…Bedroom Wall Prints…` (WoodSagePrints, Bestseller) ·
`…Wall Decoration for Kitchen & Dining, Bedroom, Living Room, Hallway,
Entryway, Office…` (AshleyPercivalPrints, 2.6k reviews, "Popular now").

**Why evergreen.** Rooms do not go out of fashion. This is buyer-intent
vocabulary of the most stable kind available.

**Caution — this is where scene-word leakage will happen.** `sanitize_niche()`
and `SCENE_TOKENS` exist precisely to strip words like these out of artwork
prompts, and they are right to. **Room modifiers belong in the listing
title/tags, never in the art brief.** If they are added to the bucket, the
bucket becomes a source for two different consumers with different rules, and
Part D says how to keep that safe.

### A3. Additions to the existing **Mid-century modern abstract** bucket — EVERGREEN

```
bauhaus print, bauhaus poster, art deco poster
```

**Evidence.** *Bauhaus* appears twice in six results for `mid century modern
wall art` (BrightBlueStar, PrintParty96) and is absent from the bucket.
`Art Deco Posters` is a 57-listing section at DIVANNO.

**Why evergreen.** Named historical design movements with a century of
continuous revival. As stable as "mid century modern" already in the bucket.

### A4. Additions to the existing **Botanical / nature line art** bucket — EVERGREEN

```
vintage botanical print, antique botanical illustration, wildflower print
```

**Evidence.** `Vintage Botanical Wall Art Set of 3… Wildflower Botanical
Poster Trio` (TheWorldGallery) · `Vintage Botanical Floral Line Art Print |
Antique Wildflower Illustration` (MotherAndSunStudioUK, 5.4k reviews). The
bucket has `herbarium print` and `pressed flower art` but not the
*vintage/antique* register that the ranking listings actually use.

### A5. New bucket: **Japanese / East Asian art** — EVERGREEN, with a caveat

```
japanese wall art, ukiyo-e style print, japanese bird art
```

**`japandi` is deliberately not in that list** — it is a 2020s interiors
coinage and is tagged TREND in Part C. (An earlier draft had it in both places;
it cannot be in both.)

**Evidence.** `Japanese and Oriental` is TheWorldGallery's **1,205-listing**
section; `Japanese Prints` is DIVANNO's **101-listing** section;
`Mid-Century **Japanese Bird** Art Print` carries a **Bestseller badge** at
TheWorldGallery; `Japandi` appears in a paid-ad title (NorthCanvasAtelier).

**The caveat, and it is the reason this is proposed rather than recommended.**
Both large occupants sell **reproductions of specific public-domain works**
(Hokusai's wave, Utamaro). A generated "japanese wall art" is competing on
aesthetic against listings competing on a named artwork. `japandi` is also
plausibly a 2020s interiors coinage rather than an evergreen — **it is tagged
TREND below, not here.**

---

## Part B — proposed **removals / rewordings** in `safe_evergreen_bucket.md`

### B1. `moon phase print` — **BLOCKED. Propose removal.**

**Evidence** (findings R2). Top 10 for the term: **4 titles carry a year**
(2026 or 2027 lunar calendars), **4 are personalised** (custom moon phase from a
date). The category anchor, `OriginalLunarPhase`, is a **3-listing shop with
22,508 sales over 13 years whose only section is named `2026`**.

**Why it fails the bucket's own test.** The *term* has flat year-round volume.
The *listings that win it* are dated products that are worthless in January.
A generated undated moon-phase print is not competing with them; it is invisible
behind them.

**Proposed:** remove from the *Celestial* bucket. `lunar cycle art` has the same
problem to a lesser degree and should be re-checked. **`star chart poster` is
also at risk** — the `Custom Star Map Print` from PaperEmporiumCo (35.6k
reviews, Bestseller) is a personalisation product occupying adjacent space.
`constellation line art`, `celestial minimalist print` and `moon phase` as a
*visual style* inside a broader design are unaffected.

### B2. `single line drawing art` and `continuous line illustration` — **BLOCKED. Propose removal.**

**Evidence** (findings R1, D5). Top 8 for `minimalist line art poster`:
**4 are custom couple or pet portraits** (BuBuLines, RosenaArtStudio,
NINETY4studio, and the category's shape generally). "One line drawing" *is*
the personalised-portrait product on Etsy — the term has been colonised.

**Proposed:** remove both. `minimalist line art poster` itself survives (it
returns mixed results), as does `negative space poster`.

### B3. Five bucket terms **cannot be tags** — a length problem, not a relevance one

Etsy caps tags at **20 characters** (findings R14). Over the cap:

| Term | Chars |
| --- | --- |
| `continuous line illustration` | 28 |
| `mid century modern wall art` | 27 |
| `minimalist landscape print` | 26 |
| `geometric shapes wall art` | 25 |
| `single line drawing art` | 23 |
| `botanical kitchen print` | 23 |
| `minimalist line art poster` | 26 |
| `celestial minimalist print` | 26 |

**Proposed:** not a removal — these are still good *research* seeds and good
*title* tokens. But the bucket should **record a short tag-safe form beside each
long term** (`mid century modern wall art` → tag `mid century art`, 15), because
the listing-copy generator (artefact 3) needs one and should not be inventing
truncations at draft time. This is a **schema change to the bucket file**, and
it is the largest single piece of work in this proposal.

---

## Part C — proposed additions to `collect_event_lookahead()`

`EVENT_WINDOWS_2026` currently holds five windows (`fall_cozy_aesthetic`,
`holiday_peak`, `diwali`, `black_friday_cyber_monday`, `engagement_season`) and
every one of them emits the **same** hardcoded niche string:
`f"botanical/minimalist nature illustration - {window['name']}"`. The seasonal
path therefore has windows but **no seasonal subject vocabulary**. These terms
are the first candidates for one.

| Term | Tag | Evidence | Suggested window |
| --- | --- | --- | --- |
| `halloween wall art`, `vintage halloween` | TREND/SEASONAL | `Vintage Halloween` = 44-listing section (DIVANNO); `FALL HALLOWEEN Wall Art` = 42 (GateOfDesign) | new `halloween`, ~1 Sep – 25 Oct; overlaps `fall_cozy_aesthetic` |
| `christmas wall art`, `winter art print` | TREND/SEASONAL | `CHRISTMAS Vintage Art` 64 + `CHRISTMAS Minimal Art` 61 (GateOfDesign); `Winter Art` 40 (DIVANNO); `Christmas` 18 (DIVANNO) | existing `holiday_peak` |
| `cottagecore`, `boho`, `japandi`, `dopamine decor`, `maximalist` | TREND | Present across SERPs, and **`safe_evergreen_bucket.md`'s own exclusions already name cottagecore as a trend**. `dopamine decor` and `maximalist` are unambiguously current-cycle | no window — **aesthetic trends, not calendar events.** They need a *third* mechanism the pipeline does not have (see below) |
| `2026 calendar`, `lunar calendar` | TREND/SEASONAL | B1 | new `new_year_calendar`, ~1 Oct – 31 Dec. **Only viable if the pipeline can make dated designs, which it currently cannot** — file, don't build |

> **A gap worth naming.** Two of the four rows above are not calendar events at
> all — `cottagecore`, `boho`, `japandi`, `dopamine decor` are **aesthetic
> trends with multi-year arcs and no fixed dates**. `collect_event_lookahead()`
> is date-windowed and cannot express them; the evergreen bucket excludes them
> by definition. They currently fall through both. The LLM search classifier
> (`TRENDING_NOW_PROMPT`) is the only path that could catch them, and its prompt
> is hardcoded to *"nature, botanical, minimalist landscape wall art"* — so it
> would not surface `bauhaus` or `dopamine decor` either. **This is a finding
> about `research.py`'s shape, filed here rather than fixed.**

---

## Part D — the implementation problem this delta creates

Parts A1 and A2 add **modifiers**, not subjects, and the existing bucket is a
flat list of subject seeds consumed by one function
(`load_safe_evergreen_terms()`). Dropping `bedroom wall art` into that list
would send a **room word straight into `art_brief.py`** — where
`sanitize_niche()` and `SCENE_TOKENS` would strip it, correctly, and where
CLAUDE.md's hard constraint about scene words makes leaking it a real defect
(it is what made the first live run print lifestyle mockups as the artwork).

**So this delta cannot be applied as a flat append.** It needs the bucket to
distinguish:

| Class | Consumed by | Example |
| --- | --- | --- |
| **Subject seeds** | `research.py` **and** `art_brief.py` | `monstera line art`, `bauhaus print` |
| **Style modifiers** | `research.py` and `art_brief.py` | `vintage`, `neutral`, `black and white` |
| **Placement modifiers** | `research.py` and the **listing copy only** — **never `art_brief.py`** | `bedroom wall art`, `kitchen wall art` |
| **Tag-safe short forms** | the listing-copy tag generator only | `mid century art` |

That is a schema change to `safe_evergreen_bucket.md` plus a consumer change in
`research.py`. **It is code, it is not GL-10b, and it is the natural third
member of the post-launch item that already holds GL-10c and multi-section
routing** — all three touch the same generation/publish path and all three are
cheaper once there are live listings.

---

## Summary of what is being proposed

| | Count |
| --- | --- |
| New terms proposed as EVERGREEN | **27** across 5 buckets (2 new buckets, 3 extensions) — counted: A1 10, A2 8, A3 3, A4 3, A5 3 |
| Existing terms proposed for **removal** (BLOCKED) | 3 — `moon phase print`, `single line drawing art`, `continuous line illustration` |
| Existing terms flagged **at risk**, re-check | 2 — `star chart poster`, `lunar cycle art` |
| Existing terms needing a **tag-safe short form** | 8 |
| New seasonal windows proposed | 2 — `halloween`, `new_year_calendar` (the latter blocked on dated-design capability) |
| Terms that fall through every existing mechanism | 5 — `cottagecore`, `boho`, `japandi`, `dopamine decor`, `maximalist` |
| **Applied** | **0** |

**Method limitation, stated because it bounds every row above.** Etsy does not
expose competitors' tags to buyers (findings M1). Every term here was inferred
from **title tokens and section names**, not from anyone's actual tag list. That
biases the delta toward terms competitors were willing to spend title characters
on — which is a reasonable proxy for what they believe converts, and a poor one
for the long-tail they hide in tags.
