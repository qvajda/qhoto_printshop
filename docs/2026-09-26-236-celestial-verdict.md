# Celestial / astronomy niche — verdict (#236)

**Date:** 2026-09-26. **Author:** research sortie for #236.

**Session limitation:** this sortie ran with no `ETSY_API_KEY`/`ETSY_API_SECRET`
in the environment (`etsy_client.find_all_listings_active` raised
`MissingConfigError` on the first probe call). A fresh SERP re-check of `star
chart poster` / `lunar cycle art` — the two terms flagged "at risk, re-check at
next sweep" in `docs/safe_evergreen_bucket.md` since GL-43 — could not be run
this session. The verdicts below use the DB candidate outcomes (live GO/kill/
reject decisions, not stale) plus the existing archived SERP evidence
(`docs/archive/2026-08-07-gl10b-keyword-delta.md`, `docs/data/gl10b-keyword-surface.md`).
A live re-check is still owed; it does not change the verdict for the three
terms below that have direct DB evidence (moon phase, and star chart's own
GO/reject/brief evidence), only for `lunar cycle art` and `celestial minimalist
print`, where the call is made on producibility + analogy, not a fresh count.

## DB outcomes (from #236's own evidence table, `candidates`)

| id | niche | trend_source | outcome |
|---|---|---|---|
| 517 | star chart poster | event_lookahead:new_year_refresh | hold / abandoned |
| 520 | minimalist moon phase astronomy poster | trending_now | GO, primary group **rejected** (text) |
| 526 | moon phase minimalist wall art | trending_now | **kill**, demand_ratio 0.0012 < 0.002 threshold, listing_count 2819 |
| 531 | constellation line art | event_lookahead:new_year_refresh | hold / abandoned (unrelated: event window, not a demand or text rejection) |
| 533 | moon phase wall art print | trending_now | GO, primary group **rejected** (text) |
| 540 | vintage celestial star map poster | trending_now | GO, primary group **rejected** (text) |

Candidate 540's own `art_brief` asks for "constellation names and magnitude
markers" and a "decorative cartouche and title block" — the brief itself
specifies labelled text/data FLUX schnell cannot render legibly, so the
rejection is not a generation-quality miss, it is the brief working as
written.

## Verdict per sub-niche

| Sub-niche | Verdict | Evidence |
|---|---|---|
| moon phase (moon phase print / minimalist moon phase astronomy poster / moon phase wall art print / moon phase minimalist wall art) | **remove** | 3 of 3 `trending_now` GOs (520, 526→killed pre-GO, 533) never survived: two rejected for garbled text at primary-group review, one killed on demand_ratio 0.0012 (listing_count 2819). Already "Removed as BLOCKED" as the literal string `moon phase print`, but 520/526/533 are all paraphrases that never matched that string — see enforcement gap below. |
| lunar cycle art | **remove** | Never independently demand-checked this session (no API key). Kept "at risk" since GL-43/GL-44 (`docs/archive/2026-08-07-gl10b-keyword-delta.md` line 150: "same problem to a lesser degree"). It is the same phase-sequence subject as moon phase (520/526/533) under a different name — same producibility risk (a "cycle" implies a labelled sequence) and the same demand anchor (`OriginalLunarPhase`, `docs/data/gl10b-keyword-surface.md`). No new evidence exists to un-flag it; a term that's been "re-check at next sweep" for 7 weeks with 3/3 sibling-subject rejections in between is a removal, not a continued flag. |
| star chart poster | **remove** | Candidate 517 never reached demand check (event_lookahead source, abandoned on window close, not itself evidence). But the genre is structurally the same failure as 540 (vintage celestial star map poster, GO → primary rejected for text) — "star chart" *is* a labelled-coordinate genre by definition, same as 540's cartouche/magnitude-marker brief. Demand side: `docs/data/gl10b-keyword-surface.md` line 63 — SERP anchored by `PaperEmporiumCo`'s 35.6k-review Bestseller `Custom Star Map Print`, a personalisation product this pipeline cannot compete with (same shape as the moon-phase-calendar anchor). Two independent reasons (producibility + demand), no reason found to keep. |
| constellation line art | **keep as is** | Candidate 531 abandoned only because its `event_lookahead` window closed — not a text rejection, not a demand kill. "Line art" is a stylistic treatment (connected dots/lines), not a labelled chart: it does not require star names, magnitude markers, or coordinates to read as the subject, so it doesn't inherit 540's/517's producibility failure. Not on GL-43/GL-44's "at risk" list. No DB evidence against it. Live SERP re-check still owed (session had no API key) but nothing here changes the call. |
| celestial minimalist print | **keep as is** | No candidate in the DB evidence table used this niche at all — zero rejections, zero kills. It names a decorative motif (sun/moon/star shapes), not a chart or calendar, so it is text-free by construction the same way `constellation line art` is. Never flagged at risk by GL-43/GL-44. No evidence found to remove it. |

## Producibility summary

The failure is genre-specific, not celestial-wide: **chart/calendar/phase-sequence
genres** (moon phase, star chart) inherently ask for labelled text, numerals, or
a dated sequence — FLUX schnell cannot render legible glyphs, so the brief sets
up a defect the critic then (correctly) rejects at the cost of a wasted
generation + review cycle. **Motif genres** (constellation line art, celestial
minimalist print) name a visual pattern, not a labelled instrument, and carry
no such requirement — nothing in the DB evidence shows them failing this way.

## Enforcement gap

`pipeline/research.py`'s `collect_trending_now` → `_build_demand_checked_candidate`
has no filter against `docs/safe_evergreen_bucket.md`'s "Removed as BLOCKED"
section at all — `trending_now` free-texts a keyword from Claude's web search
and only demand-checks it (`find_all_listings_active` + the ratio/threshold in
`_classify_demand`), never against the blocklist. That is why 520/526/533 (all
`trending_now`) reintroduced the moon-phase subject three times after GL-43
"removed" `moon phase print` in the doc only — a paraphrase (`minimalist moon
phase astronomy poster`, `moon phase wall art print`, `moon phase minimalist
wall art`) never matches the literal blocked string. Filed as a follow-up
`type:code` issue (see below): a BLOCKED-term filter read from
`docs/safe_evergreen_bucket.md`'s `## Removed as BLOCKED` section, applied to
`trending_now` (and `collect_on_demand`) output before the demand check, on
substring/fuzzy match against the subject words (`moon phase`, `star chart`,
`lunar cycle`) rather than exact keyword equality — so a reworded keyword
cannot evade it the way 520/526/533 did.

No `keep with fix` sub-niche this session, so no `art_brief.py` / `brief_lint.py`
/ `critic_pass.py` change is required by this verdict. Note for the record:
`critic_pass.py`'s hard no-go list (~L52-57) rejects a *maker's mark*
(signature/seal/cartouche used as a false hand-made claim) but has no separate
rule for garbled/illegible *chart* labels used as chart labels (star names,
magnitude markers) — a different defect class from the same underlying FLUX
text limitation. Not filed as a follow-up here since removing the two
chart/calendar genres removes the only DB-evidenced source of it; worth
revisiting only if a future niche reintroduces labelled-text requirements.

## Follow-up issue

- `type:code`, `state:triage`: BLOCKED-term filter for `trending_now`/
  `collect_on_demand` output in `pipeline/research.py`, sourced from
  `docs/safe_evergreen_bucket.md`'s `## Removed as BLOCKED` section, matched by
  subject substring rather than exact string. Filed as a native sub-issue of
  #236.
