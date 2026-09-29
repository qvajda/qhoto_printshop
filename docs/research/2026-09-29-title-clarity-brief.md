# Listing-title clarity teardown — brief — 2026-09-29

**Status: brief only. Nothing is researched until this is signed off.**
No live-shop writes, no code changes, no sweep.

## 1. Problem / success criteria

Etsy's Shop Manager flags **91 of 91 live listings** with "Make your titles even
clearer to buyers" and offers a shortened title for each one. Our titles come
from the GL-10b/GL-10c formula (`pipeline/compliance_draft.py`: 4–5 comma
clauses, ≤15 words, ≤140 chars, subject first, no size, no brand). That formula
was built from the 2026-08-07 teardown, which coded *keyword surface*, not
*title length or clarity*. What we don't know: whether bestselling competitors'
titles really are shorter/plainer than ours, or whether Etsy is just nudging
every shop the same way.

**Success = 3 artefacts:**
1. `docs/research/2026-09-29-title-clarity-findings.md` — coded title rubric +
   10–15 rules with counts.
2. `docs/research/2026-09-29-title-formula-decision.md` — resolves §3, written
   so a later session can pick it up cold.
3. `docs/data/title-clarity-rubric.md` — raw rows, written during the sweep.

### 1.1 What Etsy's suggestions show (10 pairs from the owner, measured)

| | median chars | median words | median clauses |
| --- | --- | --- | --- |
| Ours | 101.5 | **15** (range 14–15) | 4 |
| Etsy suggestion | 82.5 | 11 (10–12) | 2 |
| …without the `(…)` suffix | 66.5 | 9.5 (8–11) | 2 |

Patterns (counts are out of 10):
- Our titles sit at the 15-word cap every time. The formula fills up to the cap.
- Etsy puts the subject, style and product noun into **one leading clause**
  ("Vintage Eucalyptus Herbarium Print"), keeps the colour, and cuts stacked
  product nouns (art print + wall decor + poster in the same title).
- **9/10 add a format suffix**: 8 × `(Digital Download)` (wrong, since these
  are physical posters) and 1 × `(Matte Paper)`. Etsy's model cannot tell from
  our title what object is being sold. That is a structural clarity gap,
  separate from length.

## 2. Scope

**In:** listing **titles** only — length, structure, clause order, what the
first ~40 chars say, modifier load.

**Out, and why:**
- Tags, descriptions, alt text — separate surfaces, not what Etsy flagged.
- Keyword discovery / niche list changes — GL-10b did that; any new term
  spotted gets noted, not acted on.
- Rewriting the 91 live titles — that's the follow-up issue this feeds, not
  this session.
- Listing URL slugs — frozen to Gelato's title (GL-10b R13); title changes
  can't reach them.

## 3. The decision this resolves

**Decision: TITLE-LEN** — does the title formula change?

| Level | Meaning | Consequence |
| --- | --- | --- |
| **L1 keep** | Formula unchanged; dismiss Etsy's suggestion | No work. The dashboard nag stays |
| **L2 tighten** | Keep clause structure, lower caps (e.g. fewer clauses/words, product noun inside first ~40 chars) | Edit constants + prompt in `compliance_draft.py`, tests; re-draft 91 titles via `📝 Redo copy only` path (text only, no artwork) |
| **L3 plain** | Adopt Etsy-style short title: subject + style + product type, modifiers moved to tags/attributes | Formula rewrite (`MIN/MAX_TITLE_CLAUSES`, prompt), tag bands re-weighted to carry dropped modifiers, 91 re-drafts |

**Default if the signal is weak or split:** L1.

**Resolution rule, written before the data exists:**
- Measure the median word count and char count of bestseller titles vs ours.
- **L3** if ≥ 7 of 10 sampled shops have a median title ≤ 8 words **and**
  Bestseller-badged titles are not longer than unbadged ones in the same SERPs.
- **L2** if our median is ≥ 1.4× the bestseller median in words, or ≥ 6 of 10
  shops put the product noun (print/poster/wall art) in the first 40 chars and
  we mostly don't — but the L3 condition fails.
- **L1** otherwise, including if badged vs unbadged length shows no difference
  *and* our lengths sit inside the competitor range.

**Decision: TITLE-FORMAT** — does the title say it's a physical object?

| Level | Meaning | Consequence |
| --- | --- | --- |
| **F1 none** | As now | No work; Etsy keeps guessing "digital" |
| **F2 format term** | A physical-format word in the title (e.g. "Poster", "Matte Paper Print", "Physical Print") | One prompt clause + one assertion in `compliance_draft.py` |

**Default:** F1. **Rule:** F2 if ≥ 5 of the 10 coded shops that sell *physical*
prints put a physical-format term in the title, **or** if the SERP layer shows
physical and digital listings mixed in the same results (meaning buyers have to
tell them apart from the title).

**Anti-drift:** argued from coded fields only. "Etsy suggested it" is not
evidence by itself — Etsy's suggestion tool fires on 91/91, so it's a
platform-wide nudge until counts say otherwise. A null result (length doesn't
track the badge) resolves to L1.

## 4. Constraints the research gets no vote on

- 140-char Etsy cap; no size in title (sizes are variants, v4.12); no shop
  name; no dated/seasonal terms; commas-only separators; evergreen copy.
- AI disclosure stays in description (GL-53 / Creativity Standards).
- `📝 Redo copy only` never regenerates artwork.

## 5. Sampling method

Start from what sells, then walk back to shops. Discovery searches:

- `wall art print`, `abstract wall art`, `botanical print`, `minimalist poster`,
  `vintage poster`, `boho wall art`, `japanese art print`, `landscape print`
- Plus 2 terms from our strongest niches, picked from our own shop page.

**Two layers:**
- **SERP layer (cheap, wide):** first page of each search, every title
  measured via the extractor — gives the length distribution and
  badged-vs-unbadged comparison (~300+ titles).
- **Shop layer (coded):** 10 shops behind Bestseller-badged listings, top 3
  listings each → 30 coded titles.

**Our baseline:** our 91 titles (from DB or our shop page) coded on the same
fields, plus the Etsy suggestion for ~10 of them (see §9).

**Known bias:** `order=highest_reviews` favours old shops; SERPs are
personalised/location-biased. Correction: use the Bestseller badge as the
sales signal, compare badged vs unbadged *within the same SERP*, and browse
signed-out.

## 6. The rubric (per title)

| Field | How coded |
| --- | --- |
| chars | measured |
| words | measured |
| clauses / separator | count; `,` `\|` `-` `:` none |
| first-40-chars content | subject / style / product noun / gift / other |
| product noun present + position | print, poster, wall art, art print, canvas; char offset |
| modifier count | room, colour, style, gift, audience terms |
| redundant tokens | any word ≥ 3× or synonym stacking (poster print wall art) |
| size / "set of N" in title | y/n |
| gift framing | y/n |
| product-noun count | how many of print / poster / wall art / decor appear |
| format signal | physical term (poster, matte, framed, canvas, physical) / digital term (download, printable, instant) / none |
| listing type | physical / digital, from the listing page |
| Bestseller badge | y/n |
| reviews (shop), price | as shown |
| clarity read | can a buyer tell *what object* it is from the first 40 chars? y/n |

**NOT OBSERVABLE:** conversion or click-through by title; Etsy's suggested
titles for *competitors*. Substitute: badge + SERP position.

## 7. Where findings land

| Finding type | Lands in |
| --- | --- |
| Length / clause caps | `pipeline/compliance_draft.py` constants + `tests/` |
| Clause order / product noun | `build_draft_prompt` TITLE FORMULA text |
| Dropped modifiers → tags | `TAG_BANDS` in `compliance_draft.py` |
| Spec wording | `docs/SPEC_v4.11.md` §2.2/§5 (listing copy) |
| Re-draft of 91 live titles | new shop issue, not this session |

## 8. Out of scope / deferred

New keywords → note in findings, route to a niche-list issue. Description/tag
issues spotted → note, separate issue.

## 9. Open questions for sign-off

1. **Etsy's suggested titles** — can you paste ~10 current-vs-suggested pairs
   (or a screenshot)? They show *what* Etsy wants cut, which sharpens the
   rubric. Not blocking.
2. Browser: built-in app browser (isolated, not signed in to Etsy, so SERPs
   aren't personalised to our shop), read-only. OK?
