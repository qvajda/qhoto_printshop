# Safe-Evergreen Bucket — POD Niche Search Terms

**Status:** v2 — approved by Quentin, 2026-08-08 (GL-43; v1 2026-07-08)
**Change log:** v2 applies the *doc-only* half of `docs/2026-08-07-gl10b-keyword-delta.md` — 9 subject-seed additions, 3 BLOCKED removals, 2 at-risk flags. The delta's modifier buckets (colour, room/placement) and tag-safe short forms are **deliberately not here** — see "Deferred, and why" below.
**Consumer:** `research.py` (search-term seed list for the safe-evergreen niche path)
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

## Removed as BLOCKED (GL-43, 2026-08-08)

A third tag the bucket did not previously have. A term can pass the flat-volume test and still be useless if its SERP is owned by a product this pipeline physically cannot make. Evidence for each: `docs/2026-08-07-gl10b-keyword-delta.md` Part B.

- **`moon phase print`** — top 10 is 4 dated lunar calendars (2026/2027) and 4 personalised-from-a-date products; the category anchor is a 3-listing shop whose only section is named `2026`. An undated generated moon-phase print is not competing with those, it is invisible behind them.
- **`single line drawing art`** and **`continuous line illustration`** — "one line drawing" *is* the custom couple/pet-portrait product on Etsy; the term has been colonised by personalisation. `minimalist line art poster` and `negative space poster` survive, they return mixed results.

**At risk, kept for now, re-check at the next sweep:** `star chart poster` (adjacent to a 35.6k-review Bestseller custom star-map product) and `lunar cycle art` (a weaker form of `moon phase print`'s problem). Both are still in the Celestial bucket above — this is a flag, not a removal.

**Careful with this section's placement:** `load_safe_evergreen_terms()` reads every non-blank, non-`###` line between `## Buckets` and the next `##`, splitting on commas. Prose inside `## Buckets` becomes search terms. All annotation belongs below that boundary, as here.

## Deferred, and why (GL-43, 2026-08-08)

The keyword delta's **highest-value finding is not applied here, deliberately.** Its two new buckets — colour-family (`neutral`, `beige`, `sage green`…) and room/placement (`bedroom wall art`, `kitchen wall art`…) — are **modifiers, not subject seeds**, and this file is a flat list consumed by one function that feeds both `research.py` and `art_brief.py`. A flat append would (a) seed `beige` as if it were a niche, and (b) send a room word straight into the art brief — the exact class of scene-word leakage that made the first live run print lifestyle mockups *as* the artwork.

Applying them requires a class distinction in this file (subject seed / style modifier / placement modifier / tag-safe short form) plus a consumer change, so that placement modifiers reach the listing copy and **never** `art_brief.py`. Also deferred with it: tag-safe short forms for the 8 bucket terms over Etsy's 20-character tag cap (`mid century modern wall art` → `mid century art`), which the listing-copy generator needs and must not invent at draft time.

That work is **GL-44**, post-launch, next to GL-10c. The seasonal terms (`halloween`, `christmas wall art`, `winter art print`) are also unapplied — `EVENT_WINDOWS_2026` is code, not this file.

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
