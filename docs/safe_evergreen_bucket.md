# Safe-Evergreen Bucket — POD Niche Search Terms

**Status:** v3 — approved by Quentin, 2026-08-08 (GL-43; v1 2026-07-08; v3 GL-44)
**Change log:** v2 applies the *doc-only* half of `docs/2026-08-07-gl10b-keyword-delta.md` — 9 subject-seed additions, 3 BLOCKED removals, 2 at-risk flags. v3 (GL-44) applies the deferred half: this file is now **classed**, not flat — `## Buckets` (subject seeds, unchanged content) plus three new sections below it for style modifiers, placement modifiers, and tag-safe short forms. See "Classed sections, and why" below for what each class may reach.
**Consumer:** `research.py` (search-term seed list for the safe-evergreen niche path) via `load_safe_evergreen_terms(classes=...)` — each caller requests only the classes it is allowed to see.
**Scope:** Wall art / poster-style visual designs. Does not cover apparel, mugs, jewelry, or other POD categories — extend separately if those get added to the product line.

## What counts as "safe-evergreen" here

A search term qualifies if it maps to a stable aesthetic or universal subject with roughly flat search volume year-round, rather than a meme, franchise, influencer moment, single season, or fashion-cycle trend (e.g. cottagecore, TikTok aesthetics, zodiac/astrology). Several POD niche round-ups list those trend items as "evergreen" — they aren't; they're just currently popular. That distinction is the point of this bucket: it's the set `research.py` can draw from without re-validating trend timing on every run.

## Buckets

### Botanical / nature line art
monstera line art, botanical print set, pressed flower art, fern illustration print, wildflower line drawing, eucalyptus branch art, herbarium print, vintage botanical print, antique botanical illustration, wildflower print

### Minimalist abstract / geometric
minimalist line art poster, abstract arch print, geometric shapes wall art, negative space poster

### Celestial / astronomy (not zodiac)
star chart poster, lunar cycle art, constellation line art, celestial minimalist print

### Landscape / nature photography-adjacent
mountain line art, minimalist landscape print, coastal line drawing, forest silhouette poster, desert minimalist art

### Mid-century modern abstract
mid century modern wall art, retro abstract print, mcm geometric poster, atomic age art print, bauhaus print, bauhaus poster, art deco poster

### Kitchen / botanical illustration
herb line art print, fruit illustration poster, botanical kitchen print, citrus line drawing

### Generic animal line art
minimalist animal line art, cat line drawing print, bird silhouette poster, fox line art

### World map / travel line art (non-destination-specific)
world map line art, minimalist travel print, topographic map poster

### Japanese / East Asian art
japanese wall art, ukiyo-e style print, japanese bird art

## Style modifiers

Colour-family words. Not subjects — they combine with a `## Buckets` term. Consumed by `research.py` **and** `art_brief.py`: colour is visual, so it belongs in the art brief as well as the search seed. Source: `docs/archive/2026-08-07-gl10b-keyword-delta.md` Part A1.

neutral, beige, sage green, terracotta, dusty pink, navy blue, black and white, muted earth tones, warm neutral, pastel

`sage green` and `terracotta` are closer to a 2020s palette moment than a permanent one — admitted on current occupancy, flagged for re-check (Part A1).

## Placement modifiers

Room/location words. Consumed by `research.py` and **listing copy only** — **never `art_brief.py`**. A room word is scene-word leakage: it is exactly what `sanitize_niche()` and `SCENE_TOKENS` in `pipeline/art_brief.py` exist to strip, and what made the first live run print lifestyle mockups as the artwork. Source: `docs/archive/2026-08-07-gl10b-keyword-delta.md` Part A2.

bedroom wall art, kitchen wall art, bathroom wall art, hallway art, living room wall art, entryway art, home office wall art, nursery wall art

## Tag-safe short forms

Short forms of `## Buckets` terms that are over Etsy's 20-character tag cap. Consumed by the listing-copy tag generator only — it must not invent truncations at draft time. Source: `docs/archive/2026-08-07-gl10b-keyword-delta.md` Part B3, restricted to the six over-cap terms still live in `## Buckets` (the other two flagged there, `continuous line illustration` and `single line drawing art`, were already removed below).

mid century art, minimalist landscape, geometric wall art, botanical kitchen, minimalist line art, celestial print

## Tag-safe short forms — long-form mapping (reference only, not parsed as terms)

`load_safe_evergreen_terms()` reads every non-blank, non-`###` line under a class heading as comma-separated terms (see "Careful with this section's placement" below) — this table is prose reference for a human pairing each short form above with the `## Buckets` term it stands in for, kept in its own section so it is never read as term data.

| Long form (`## Buckets`) | Short form (`## Tag-safe short forms`) |
| --- | --- |
| mid century modern wall art | mid century art |
| minimalist landscape print | minimalist landscape |
| geometric shapes wall art | geometric wall art |
| botanical kitchen print | botanical kitchen |
| minimalist line art poster | minimalist line art |
| celestial minimalist print | celestial print |

## Removed as BLOCKED (GL-43, 2026-08-08)

A third tag the bucket did not previously have. A term can pass the flat-volume test and still be useless if its SERP is owned by a product this pipeline physically cannot make. Evidence for each: `docs/2026-08-07-gl10b-keyword-delta.md` Part B.

- **`moon phase print`** — top 10 is 4 dated lunar calendars (2026/2027) and 4 personalised-from-a-date products; the category anchor is a 3-listing shop whose only section is named `2026`. An undated generated moon-phase print is not competing with those, it is invisible behind them.
- **`single line drawing art`** and **`continuous line illustration`** — "one line drawing" *is* the custom couple/pet-portrait product on Etsy; the term has been colonised by personalisation. `minimalist line art poster` and `negative space poster` survive, they return mixed results.

**At risk, kept for now, re-check at the next sweep:** `star chart poster` (adjacent to a 35.6k-review Bestseller custom star-map product) and `lunar cycle art` (a weaker form of `moon phase print`'s problem). Both are still in the Celestial bucket above — this is a flag, not a removal.

**Careful with section placement:** `load_safe_evergreen_terms()` reads every non-blank, non-`###` line between a class heading (`## Buckets`, `## Style modifiers`, `## Placement modifiers`, `## Tag-safe short forms`) and the next `##`, splitting on commas. Prose inside one of those four sections becomes term data for that class. All annotation — including the mapping table above — belongs in a section of its own, never inside one of the four.

## Classed sections, and why (GL-44, 2026-08-08)

GL-43 left the keyword delta's highest-value finding unapplied: colour-family (`neutral`, `beige`, `sage green`…) and room/placement (`bedroom wall art`, `kitchen wall art`…) are **modifiers, not subject seeds**, and the file was a flat list consumed by one function feeding both `research.py` and `art_brief.py`. A flat append would have (a) seeded `beige` as if it were a niche, and (b) sent a room word straight into the art brief — the exact class of scene-word leakage that made the first live run print lifestyle mockups *as* the artwork.

GL-44 applies it by classing the file instead: `load_safe_evergreen_terms(classes=...)` reads only the sections a caller names, and each caller names only what it is allowed to see. **Subject seeds** (`## Buckets`) reach `research.py` and `art_brief.py` — unchanged behaviour, still the default. **Style modifiers** reach `research.py` and `art_brief.py` too — colour is visual. **Placement modifiers** reach `research.py` and listing copy — **never `art_brief.py`**. **Tag-safe short forms** reach the listing-copy tag generator only, and have no consumer yet (GL-10c, #28, is that consumer — it ships asserted and unwired here, deliberately, because #28's spec forbids inventing truncations at draft time). The safety property that used to be enforced by absence is now enforced by routing — see `tests/test_research.py` for the tests that hold it.

The seasonal terms (`halloween`, `christmas wall art`, `winter art print`) are still unapplied — `EVENT_WINDOWS_2026` is code, not this file.

## Explicitly excluded

- **Zodiac / astrology** — trend-cycles with the spirituality market faster than plain celestial imagery.
- **Personalized / name-based products** — requires per-order customization, doesn't fit a static AI-asset generation model.
- **Fandom / pop culture** — copyright exposure plus genuine trend risk.
- **Holiday / seasonal decor** — not evergreen by definition.
- **Humor / slogan-driven designs** — short meme half-life, culturally inconsistent across markets.

## Sources

- [Printify — Top-selling niches on Etsy in 2026](https://printify.com/blog/top-selling-niches-on-etsy/)
- [Dynamic Mockups — 10 Evergreen Niches for Print-on-Demand](https://dynamicmockups.com/print-on-demand/evergreen-niches-for-print-on-demand/)
- [Kittl — 50+ print on demand niches for 2026](https://www.kittl.com/blogs/print-on-demand-niches-pod/)

## Open item

Confirm before extending: does the safe-evergreen bucket ever need to cover apparel/mug/decor terms, or does the product line stay wall-art-only? If it expands, humor/slogan exclusions above will need re-review — that's apparel's dominant format, not wall art's.
