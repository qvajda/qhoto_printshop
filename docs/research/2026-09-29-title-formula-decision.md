# Title formula decision — TITLE-LEN / TITLE-FORMAT — 2026-09-29

**Written to be picked up cold.** Evidence: `2026-09-29-title-clarity-findings.md`
(rules R1–R14) and `docs/data/title-clarity/rubric.md`. Status: **resolved by
pre-agreed rules, awaiting owner ratification before any build.**

## Context in three lines

Etsy's dashboard suggests a shorter title for all 91 of our pipeline listings,
and 8 of 10 sampled suggestions wrongly append "(Digital Download)". A sweep of
~440 first-page listings across 10 searches, plus 10 bestseller shops, tested
whether bestsellers use shorter or clearer titles than ours.

## TITLE-LEN → **L1 keep** (the default)

Bestseller titles are longer than ours (18 vs 15 words), and length doesn't
differ between badged and unbadged listings. Keep `MAX_TITLE_WORDS = 15`,
`MAX_TITLE_LENGTH = 140`, `MIN/MAX_TITLE_CLAUSES = 4/5`. **Dismiss Etsy's
shortening suggestions.** Don't accept them either: they add a false
"(Digital Download)".

## TITLE-FORMAT → **F2 format term**

Both clauses of the pre-written rule fire: 6/10 shops put "poster" in ≥ 10/12
titles, and digital listings sit in 9/10 of the same SERPs.

### What to build (one shop issue, one PR)

All in `pipeline/compliance_draft.py` + `tests/`:

1. **Object noun.** Change `PREFERRED_MEDIUM_TERMS` and the TITLE FORMULA prompt
   so the **first clause names the object as a poster**, e.g. "Vintage
   Eucalyptus Herbarium Poster" or "… Poster Print". "art print" / "wall art"
   stay allowed in later clauses. Evidence: R4, R5.
2. **Digital-word ban, in code.** Titles must not contain
   `printable|download|digital|instant`. Add it to the title banned pattern, next
   to the brand and size terms (`_TITLE_BANNED_PATTERN`), with a test. Per
   GL-53, a prompt instruction alone doesn't count. Evidence: R6, R7.
3. **Assertion for (1).** Add a check that the first clause contains `poster`,
   so it isn't only a prompt preference (same GL-53 reasoning). If the owner
   prefers "poster anywhere in title" over "first clause", loosen it there.
4. **Spec note.** Amend the GL-10b listing-copy spec §5 reference (now in
   `docs/archive/2026-08-07-gl10b-listing-copy-spec.md`; its live descendant
   is in `docs/SPEC_v4.11.md` §2.2/§5) to record that the "prefer art print
   over poster" preference was overturned by a count, with a link to R4.

Not in scope: re-weighting tags, changing the caps, adding a "(Matte Paper)"
suffix. That suffix is a minority pattern (14 % organic); keep it as a fallback
if the re-measure below fails.

### Rolling out to the 91 live listings

Redraft through the existing text-only path (`📝 Redo copy only`, never
regenerates artwork). This is a live-listing text change, so it follows the
normal approval flow. It's a separate step after the PR merges, not part of it.

### Acceptance / re-measure

- Unit: the prompt names poster; the banned-term test rejects "Printable Wall
  Art"; the first-clause assertion rejects a title with no "poster".
- Live, ≥ 2 weeks after the redraft: re-read Etsy's title suggestions on ~10
  redrafted listings. **Success = fewer than 8/10 append "(Digital Download)"**
  (baseline 8/10). If it's still ≥ 8/10, R9's caveat held (Etsy's guess isn't
  driven by the noun), so try the "(Matte Paper)"-style physical term next.

## Immediate hand-fix (owner, Shop Manager — no code)

Listing **4549960823** has "Minimalist **Printable** Wall Art" in the title of a
physical poster. Replace "Printable" (e.g. "Minimalist Botanical Wall Art").
The URL slug stays as it is (frozen at first publish); only the title changes.

## What would reopen this

- TITLE-LEN: a future sweep where badged titles are measurably shorter than
  unbadged ones in the same SERPs.
- TITLE-FORMAT: the re-measure above coming back ≥ 8/10 "(Digital Download)"
  after the redraft.
