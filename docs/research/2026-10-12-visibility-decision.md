# VIS-LEVER — decision — 2026-10-12

Issue #259. Written to be read cold. The rule this resolves was fixed before any
data existed: brief §3, [`2026-10-12-visibility-brief.md`](2026-10-12-visibility-brief.md).
Evidence: [`2026-10-12-visibility-findings.md`](2026-10-12-visibility-findings.md)
and [`docs/data/visibility/rubric.md`](../data/visibility/rubric.md).

## The question

132 live listings, 109 with zero views. Which visibility lever(s) should the
follow-up build row target?

## The rule (brief §3, restated)

A lever is **GAP** only if (1) ≥ 70 % of the coded top-organic listings share a
value and ≤ 30 % of ours have it, and (2) that still holds among top listings
from shops with < 500 reviews. A GAP is **primary** if our own viewed
listings differ from our unviewed ones in the same direction by ≥ 20 pp, and
**secondary** otherwise. **NULL** = we sit inside the range or the signal is
split (the default). **N/O** = not observable from the buyer view.
L-concentration and L-recency have their own rules (brief §3).

## Resolution

| Lever | Outcome | Theirs (top organic) | Under-500 test | Ours | Rank |
| --- | --- | --- | --- | --- | --- |
| **L-category** | **GAP** | 17/20 deeper than Wall Decor (85 %) | 12/14 (86 %) ✓ | 0/132 | secondary (ours is one value on 132/132, so no internal contrast exists) |
| L-first-image | **dropped by owner** (was GAP, marginal) | room first 13/18 (72 %) | 10/13 (77 %) ✓ | **unknown**: DB says flat on 133/133, but the owner reordered many galleries by hand on Etsy (2/2 sampled live were flat) | no sales effect seen from those reorders; not pursued |
| **L-concentration** | **GAP** (own rule) | — | — | ≥ 10 title matches on 4 keywords; absent from pages 1–3 on all 4 | — (confounded: we're page 3 even on our own title) |
| L-tag/query match | NULL | 74 % carry every query token | — | 80 % | internal +35 pp exact-tag, but confounded |
| L-trust | NULL | 73 % of page-1 organic from < 500-review shops | — | 2 reviews | exception: `watercolor botanical print` |
| L-shipping | NULL | 75 % free | — | free, ships from BE | — |
| L-price | NULL | medians 22.84–64.92 | — | from 19.00 (low end, inside range) | — |
| L-attributes | NULL visible / N/O hidden | Materials 13/20 | — | Materials shown | colour etc. not observable |
| L-ads | finding → owner | 40 % of page-1 cards are ads | — | ~43 impressions/day | budget out of scope |
| L-ads-cov | NULL | — | — | 114/132 served | — |
| L-recency | NULL (provisional) | 17/20 "listed on" ≤ 30 days | — | no decay in own history | owner (renewal costs fees) |
| (gallery video) | NULL | 14/20 (70 %) | 9/14 (64 %) ✗ | 0 | fails test by one listing |

No GAP is ranked primary. That is not because evidence ran against it: on
L-category every one of our listings holds the same value, so there is nothing
to contrast internally.

## Owner review, 2026-10-12

- **First image: dropped.** The owner has already reordered many galleries by
  hand for a nicer thumbnail. That made no visible difference (0 sales either
  way), and it also means the DB's `gallery_order` does not show the live
  first image, so "ours 0/133" was wrong (see findings, corrections).
- **Category change: accepted in principle, on the condition that it helps
  sales.** So it ships as a measured change, not a settled fix (row 1 below).
- **Search visibility page: checked by the owner. It flags titles only**
  (being handled in #258), with **no category flag**. Etsy's own tool
  therefore does not confirm L-category. It stays GAP by count, but its
  primary-source support is weaker than the findings first stated.
- All other findings accepted.

## Recommended follow-up rows, in order

Each is a **proposal**. None is applied, and each needs its own sortie and the
owner's go-ahead, because changes to live listings are live writes.

1. **Category (L-category), as a measured change.** Etsy's help page names a
   specific category as a priority-placement requirement, but the shop's
   Search visibility page does not flag ours (owner, 2026-10-12). So the
   change must earn its keep by measurement.
   - Build: resolve the leaf under Wall Decor (Wall Hangings is the one 6/20 top
     listings use, and it keeps ADR-0011's Home Decor reasoning) via
     `getSellerTaxonomyNodes`. Set it in `config/static_config.json`, then check
     which listing properties that leaf offers (rule 9). Amend
     `docs/adr/0011-etsy-taxonomy-1027.md` rather than overriding it.
     Re-PATCHing the 132 live listings is its own step.
   - Measure: re-run the 7-keyword rank scan 14 days after (the brief's
     scan, same conditions), plus views and orders from the snapshots. The
     owner's condition is sales; with near-zero baseline traffic, views and
     rank are the earlier readable signal. If neither moves, revert is cheap
     (one config value plus a PATCH).
2. **"vintage" token (finding 3).** Drop "vintage" from title generation
   (`pipeline/compliance_draft.py`), keep "vintage-style"/"antique-style" only if
   a later check shows those aren't rewritten too. Route through the #244 title
   rules owner. Never set `when_made` to a vintage value: the prints are new.
3. **Concentration (L-concentration).** Goes to niche sourcing (#243 / #134):
   stop adding to botanical/sage until something in those clusters ranks inside
   3 pages. Drop `biophilic wall art` as a target keyword (BLOCKED, moss panels).

**Owner-only, no build row:** Etsy Ads budget (40 % of page 1 is ads, about 43
impressions/day for us); renewal policy (top listings are freshly (re)listed,
own data shows no decay); sets (#67 evidence: 33/33 on the set query).

## What would change this

- (Resolved 2026-10-12: the Search visibility page shows no category flag,
  so #1 runs as a measured change rather than a confirmed fix.)
- A second sweep from another region/ship-to that puts us inside 3 pages
  would turn L-concentration NULL.
- Rank scan after #1 ships with no movement on any keyword: revert #1. The
  remaining explanation is then engagement (clicks, favourites), and the first
  image becomes worth reopening, despite the owner's drop.
