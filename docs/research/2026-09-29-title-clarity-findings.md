# Listing-title clarity teardown — findings — 2026-09-29

Brief: `2026-09-29-title-clarity-brief.md`. Raw data: `docs/data/title-clarity/`.
Decision handoff: `2026-09-29-title-formula-decision.md`.

**Trigger.** Etsy's Shop Manager suggests a shorter title for every one of our
listings (91 flagged). The owner supplied 10 current-vs-suggested pairs.

**Bottom line.**
1. **Length is not the problem.** Bestselling physical-print titles are
   *longer* than ours (median 18 words vs 15), and length doesn't differ
   between badged and unbadged listings. **TITLE-LEN resolves to L1: keep.**
2. **What the title calls the object is the problem.** Competitors call it a
   **"Poster"** (53 % of bestseller titles, 6 of 10 coded shops in ≥ 10 of 12
   titles). Our formula steers away from that word (29 %) and leads with "art
   print" (56 % vs 7 %). Digital sellers label themselves in the title (89 %).
   Etsy's own model reads our titles as digital downloads (8 of 10).
   **TITLE-FORMAT resolves to F2: add a format term.** Both clauses of the rule
   fire.

---

## Rules

Types: **S** = structural (search, platform, what we can make), **A** =
aesthetic.

### R1 — Bestseller titles are longer than ours, not shorter. [S, null for change]
**(a)** Median words / chars: bestseller physical 18 / 119 (n=55), organic
physical 18 / 120.5 (n=256), **ours 15 / 104** (n=91). 0 of 10 coded shops have
a median ≤ 8 words (lowest: 9). 24 of 55 bestseller titles run to 19+ words.
**(b)** `MAX_TITLE_WORDS`, `MAX_TITLE_CLAUSES` in `pipeline/compliance_draft.py`.
Unchanged.
**Confound:** TheWorldGallery (201k sales) has a shop-page median of 9 words,
but its first 12 listings include frame add-ons, and its own badged listing is
131 chars.

### R2 — Length doesn't track the Bestseller badge. [S, null]
**(a)** Badged vs unbadged organic physical, within the same SERPs: 119 vs 120
chars, 18 vs 18 words, 3 vs 4 clauses, 3 vs 3 product nouns.
**(b)** None. This null result is what licenses keeping the current caps.
Etsy's "shorter is clearer" suggestion is not backed by what sells.

### R3 — Etsy's "< 15 words" advice is real, and we already follow it. [S]
**(a)** Re-verified verbatim on *How to Create a Listing* (2026-09-29):
*"Consider using less than 15 words… Clearly state what the item is… Avoid
repetition."* 69 % of competitor titles ignore the word advice; ours comply.
**(b)** Keep `MAX_TITLE_WORDS = 15`. Don't lengthen to match competitors: R2
says length is no lever, and the platform advice points the other way.

### R4 — "Poster" is the market's word for this object; our formula avoids it. [S]
**(a)** "poster" appears in 53 % of bestseller physical titles, 55 % of organic
physical titles, and **29 % of ours** (91 comma titles). Shop layer: 6 of 10
shops use it in ≥ 10 of their 12 titles (TheWorldGallery, HazeAndJuniper,
GotTheme, MetropolitanArtCo, VintageArtQuarter, Homivia). Our preference for
"art print"/"wall art" comes from the GL-10b listing-copy spec §5, which argued
from a planned section name (`Unframed Art Prints`) and an uncounted "dominant
vocabulary". GL-10b counted section names ("0/10 shops use a bare 'Posters'
section"), not title nouns. **This contradicts GL-10b. Flagged, not silently
overridden.**
**(b)** `PREFERRED_MEDIUM_TERMS` and the TITLE FORMULA prompt text in
`compliance_draft.py`.

### R5 — We lead with "art print"; the market leads with poster/print/wall art. [S]
**(a)** First product noun is "art print" in 51 of 91 of ours (56 %), vs 4 of 55
bestsellers (7 %) and 25 of 256 organic (10 %). Bestsellers lead with poster
(29 %), print (22 %), wall art (18 %). Etsy's suggestions mostly shorten "art
print" to "Print".
**(b)** Same prompt clause as R4.

### R6 — Digital sellers label themselves; physical sellers rely on "poster" plus the absence of "digital". [S]
**(a)** 89 % of digital-listing titles carry digital/download/printable, vs 0 %
of competitor physical organic titles. Strict physical words (framed, canvas,
matte, paper, physical…) show up in only 14 % of organic and 13 % of bestseller
physical titles, but in **51 % of ads**, mostly framed/canvas products.
**Confound:** 55 % of *digital* titles also say "poster", so "poster" alone is
not proof of a physical product. The convention is poster **and** no digital
word.
**(b)** Title prompt and a new code assertion (R7).

### R7 — One of our physical listings says "Printable". [S, defect]
**(a)** Listing 4549960823 (legacy, pre-GL-10c):
`…Minimalist Printable Wall Art…`. It's a physical poster listing carrying the
single most digital word there is. 1 of 108.
**(b)** Hand-fix the title in Shop Manager (checklist). Then per the GL-53 rule
(*a prompt instruction is a preference, not a control*), add
`printable|download|digital|instant` to the title's banned-term assertion in
`compliance_draft.py`, so the pipeline can't produce it again.

### R8 — Buyers do see digital and physical mixed together. [S]
**(a)** Digital listings appear in **9 of 10** SERPs (all but the vintage-category rewrite) despite physical-heavy
queries: 37 of 439 organic cards overall (8 %), up to 12 of 44 (27 %) on
"vintage poster". So the title has to tell them apart. This is the second
clause of the TITLE-FORMAT rule, and it fires.
**(b)** Decision doc.

### R9 — Etsy's model reads our titles as digital downloads. [S, partly NOT OBSERVABLE]
**(a)** 8 of 10 suggestions append `(Digital Download)`. The listing itself
looks physical to a buyer (4584119793: `Materials: Paper`, a delivery estimate,
no download marker). The suggestion tool seems to reason from the title text.
**Caveat that weakens R4:** that same listing's title already ends in
"Botanical Study Poster", and Etsy still guessed digital. So adding "poster" is
the *market* convention; it's not shown to change *Etsy's* guess. Why Etsy
guesses digital is NOT OBSERVABLE from the buyer side.
**(b)** Decision doc. Re-measure after the change (acceptance criterion there).

### R10 — Our formula fills to the cap every time. [A]
**(a)** 54 of 91 of our titles are *exactly* 15 words, and the 10 pairs are all
14–15. Competitors spread out (bestsellers: 9 at ≤ 10 words, 24 at 19+). What
Etsy cuts from our pairs is mostly the trailing room/decor clause
("naturalist wall decor", "Botanical Home Decor"), i.e. filler written to hit
the cap.
**(b)** Prompt wording: "at most 15 words", not a target. Optional. Counts
alone don't mandate it (R2).

### R11 — Stacking product nouns is normal; Etsy's "avoid repetition" isn't what the market does. [A, null]
**(a)** Median product nouns: ours 3, bestsellers 3. ≥ 4 nouns: ours 24 of 91
(26 %), bestsellers 24 of 55 (44 %).
**(b)** No change to `MAX_WORD_REPEATS`. Don't cap product nouns; nothing in
the counts supports it.

### R12 — Commas-only is fine. [A, null]
**(a)** Commas are the majority separator in bestsellers (35/55) and organic
(140/256). Pipes 13 % / 15 %.
**(b)** `TITLE_BANNED_SEPARATORS` unchanged.

### R13 — Gift and set framing: seen in the market, blocked for us. [S, BLOCKED]
**(a)** "gift" in 20 % of bestseller titles; set/bundle in 7 % of bestseller
and 24 % of organic titles. Ours 0 %. Etsy's help says include recipients or
occasions only if essential. Sets need multi-artwork listings (v4.12: one
artwork per listing; GL-10b R4 already deferred sets).
**(b)** None. Recorded so it isn't rediscovered.

### R14 — Our listing pages already say "paper"; the title is the weak link. [S]
**(a)** Ours, like 9 of 10 bestseller listings checked, shows a paper material
in Highlights (#239's Material fix is live). The title is the only surface
where we differ from the convention.
**(b)** None beyond R4/R7.

---

## Decision resolution (rules written in the brief before any data)

**TITLE-LEN → L1 keep.**
- L3 needed ≥ 7/10 shops with median ≤ 8 words: **0/10**. Fails.
- L2 needed ours ≥ 1.4× bestseller median words (15 vs 18 = **0.83×**), or ≥ 6/10
  shops with the product noun in the first 40 chars where we mostly don't (ours
  91 % vs bestsellers 91 %). Fails.
- Badged vs unbadged length: no difference (R2). Resolves to the default.

**TITLE-FORMAT → F2 format term.**
- Clause 1: ≥ 5 of 10 physical-selling shops use a physical-format term (poster
  counts, per the brief's rubric) in their titles. **6/10** use "poster" in
  ≥ 10/12 titles (7 if you count Knopfmaedchen's "original", which isn't
  comparable). Fires.
- Clause 2: digital and physical mixed in the same SERPs: **9/10**. Fires.
- **Which term** isn't in the rule. The counts point to "Poster" (R4) plus a
  ban on digital words (R6/R7). A strict physical suffix like "(Matte Paper)"
  is a minority pattern in organic titles (14 %). See the decision doc.

## Out-of-scope observations (routed, not built)

- Our description opens with artwork prose, and a "printed and shipped" line
  isn't in the first ~300 chars. It's a description surface, so it gets its own
  issue if wanted.
- Keyword surface: nothing new beyond GL-10b; not re-run.

## Verification pass

- Every group count re-derived by one JS classifier from the stored rows, with
  the same function for ours and theirs.
- SERP titles are full titles: 10/10 matched the listing `h1` exactly.
- Etsy's 140-char / < 15-word guidance re-verified verbatim at the source,
  2026-09-29.
- No competitor title copied into the repo. Pattern quotes only.
- Nothing written to the live shop. Every browser action was a signed-out GET.

### Errors found and fixed during the sweep

| What was wrong | What it is now |
| --- | --- |
| First SERP pass ran the extractor before lazy-loaded cards rendered: 12 cards per search instead of ~60 | Re-ran every search with scroll-to-load. All counts use the ~60-card pass |
| "vintage herbarium print" was rewritten by Etsy into the Vintage category and its rows were labelled "vintage poster", overwriting that search's data | Relabelled, and re-ran "vintage poster". Both vintage-category searches excluded from length stats as non-competitors |
| My "formula titles" filter (comma-only) also caught ~23 pre-GL-10c titles over 15 words | Renamed to "ours, comma titles" (n=91). Medians are unchanged (15 words) because 54 sit at exactly 15 |
| The extractor's strict `phys` flag excluded "poster", but the brief's rubric counts poster as a physical term | Poster counted separately. The F-rule applied as the brief wrote it, and the confound (55 % of digital titles also say poster) stated in R6 |
| Brief said "91 of 91 live listings"; the shop shows 113 items, and 108 were scraped (incl. 4 framed photography, 13 legacy separators) | The 91 comma titles line up with the dashboard's 91. Both figures reported |
| First draft said digital listings appeared in 10/10 SERPs; "vintage herbarium print" had 0 | Corrected to 9/10 on re-derivation |
| One badged-listing check (VintageArtQuarter) didn't capture the material line | Reported as 9/10, not 10/10 |
