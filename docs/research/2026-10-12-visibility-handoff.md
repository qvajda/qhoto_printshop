# Visibility teardown (#259) — hand-off to a desktop session — 2026-10-12

Written to be picked up cold. Branch `research/259-visibility` (local, **not
committed, not pushed**). The brief is signed off; the owner's answers are in it.

## Read first, in this order

1. `docs/research/2026-10-12-visibility-brief.md`: scope, the 11 levers,
   the pre-written resolution rules (§3), the rubric (§6). **Signed off
   2026-10-12:** keep the 7 keywords; browser = built-in (isolated, signed out).
2. `docs/data/visibility/rubric.md`: "ours" is fully coded (§1–5). §6–7
   (theirs) are empty, and that is this session's job.
3. Skill `etsy-competitor-teardown`, plus its `references/etsy-selectors.md`
   (tested SERP/listing extractors) and `references/etsy-facts.md`.

## Already resolved — do not redo

| Lever | Verdict | Count (in rubric.md) |
| --- | --- | --- |
| L-ads-cov | **NULL** | 114/132 served ≥ 1 ad impression (last 30 days) |
| L-recency | **NULL** (provisional, see findings caveat) | since 09-22: 3 viewed / 34 never (ages up to 18 d); view-rate by age 9/22/14/21 %, not monotonic |
| internal contrast basis | **organic = 15**, not 23 | 8 of the 23 viewed listings carry an ad click (35 % vs 1 % of unviewed) |

Internal signals already measured (organic 15 vs zero 109):
- Exact-tag keyword match: 73 % vs 38 % (**+35 pp**), confounded by niche and age.
- Keyword in title: +17 pp. "poster" in title: +8 pp.
- Taxonomy: 1027 on 132/132.
- Concentration: "botanical print" appears in 101/132 titles. 0 listings target
  "botanical print set of 3"; 1 tag targets "biophilic wall art".

## This session's work

1. **Our rank (L-concentration).** For each of the 7 keywords, scan SERP pages
   1–3 and record QhotoArt's best position, or "absent". Use plain
   `/search?q=<kw>` (default relevance sort; that's the one buyers get). Rule:
   brief §3.
2. **SERP layer.** Page 1 per keyword, coded via the extractor: Ad,
   Bestseller, Star Seller, price shown, free shipping, shop review count,
   digital/physical. One screenshot per SERP for first image. Rows go into
   rubric.md §6 **as each SERP is coded**, not at the end.
3. **Listing layer.** Top 3 organic (non-Ad) per keyword, 21 in all:
   category breadcrumb, attributes shown, gallery count/video, price at
   smallest/largest size, shipping and delivery estimate, shop sales/years,
   "listed on" if shown. Each row goes into §7 as it is coded.
4. **Phase 5:** verify Etsy's own help pages on search ranking factors and
   Etsy Ads auto-advertise (only third-party sources were found so far).
5. **Deliverables:** `docs/research/2026-10-xx-visibility-findings.md` (10–15
   rules, each with count, surface and structural/aesthetic tag, plus a
   corrections table) and `docs/research/2026-10-xx-visibility-decision.md`
   (VIS-LEVER per lever, readable cold). Then run the doc-link check.

## Hard rules

- **Read-only.** Never sign in to Etsy in the built-in browser, and touch no
  setting. Record locale/currency and ship-to.
- **Public repo:** counts and short pattern quotes only. **No competitor
  titles, shop names or listing ids in any file.** The owner's raw Etsy Ads
  paste (spend) stays out of the repo; only the counts above are in.
- No code, listing, tag or price change (#259 scope). New keywords are noted
  and routed, never applied.
- Python: `C:/Users/QVajd/AppData/Local/Programs/Python/Python312/python.exe`,
  never bare `python`. The DB is `db/qhoto.sqlite3`; open it read-only
  (`?mode=ro`).
- Never raise activation or history rewriting (CLAUDE.md standing decisions).

## Noted for findings, not acted on

- 2 titles in `listing_texts` contain "printable" (1 also seen live in the
  Ads table) (a digital signal on a physical poster,
  against #244 TITLE-FORMAT F2), and 13 titles use `|` separators.
- Ad delivery: about 43 impressions/day shop-wide, 1.1 % CTR, 0 orders in
  30 days. This is L-ads, a finding; budget/bid is out of scope.

## Corrections so far (carry into the findings' corrections table)

| Was | Now |
| --- | --- |
| Brief L-recency rule read "Aug listings at 14 days after creation", but snapshots start 09-22, so that isn't measurable | Rule rewritten on listings created ≥ 09-22 |
| Brief listed ads as out of scope | L-ads-cov added on owner request; resolved NULL by count |
| "Viewed = 23" | organic 15 once ad-clicked listings are separated |

## When done

Commit on `research/259-visibility` (docs only; `pipeline/` and `tests/` must
stay untouched), open a PR linking #259, and stop for the owner to read the
VIS-LEVER resolution. #259 currently carries `state:building` and `no-auto`,
and that is left as is.
