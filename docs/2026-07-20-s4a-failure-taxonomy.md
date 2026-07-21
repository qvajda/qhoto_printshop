# S4-a — Failure taxonomy & bestseller trait study (2026-07-20)

Executes and refines S4-a from `docs/2026-07-19-post-test-remediation-plan.md`
(Finding 4). Scope changed vs. the original S4-a spec: images 1–3 in
`db/base_artwork/` are **new designs generated over the original run-#1
masters 1–3**, with owner grades — so the sample is now a quality *gradient*
(1 good, 2 refine, 3 borderline, 4–7 condemned), not 7 binary failures.
This is better for calibration and this doc treats it that way. Extended, per
owner request, with an Etsy bestseller trait study (learn what *good* looks
like, not only what bad looks like — observed traits only, no competitor
imagery copied or stored).

Method notes: local stats computed with the exact
`critic_pass.compute_image_sanity_stats` logic plus two extra metrics
(`ncol` = distinct colors at 256px thumbnail; `cov` = fraction of grayscale
pixels deviating >15 from the median — a subject-coverage proxy). Rubric
assessment done per-criterion by a vision model (Claude) against the 7-point
`CRITIC_RUBRIC_PROMPT_TEMPLATE`; the pipeline's own critic was NOT re-run
live (deferred to the Claude Code session, after Finding 3's error-handling
fixes, so results aren't poisoned by the empty-response bug). Bestseller
study done via live Etsy browsing (etsy.com, BE locale, 2026-07-20) using the
`is_best_seller=true` search filter — every listing observed carried Etsy's
actual Bestseller badge.

---

## 1. Scorecard — the 7 masters

Owner verdicts are the ground truth. Rubric points: 1 no-go / 2 subject
presence / 3 coherence / 4 composition / 5 detail quality (smudging) /
6 visual density / 7 text match (n/a here — no listing text in scope).

| # | Niche (from DB / memory) | Owner verdict | stddev | edge | ncol | cov | Local gate | Rubric failures (vision assessment) |
|---|--------------------------|---------------|-------:|-----:|-----:|----:|-----------|-------------------------------------|
| 1 | mid-century modern botanical, bold filled foliage, dense full-frame, warm muted palette | **Good** | 56.6 | .074 | 8398 | .265 | pass | none — dense centered bouquet, clean flat zones, warm palette |
| 2 | retro travel poster line art (live test 2; rendered as bird line art on peach circle) | **Refine** — good idea, some smudging, fairly sparse | 23.6 | .049 | 2686 | .148 | pass | 5 (minor wobble/smudge in fine linework), 6 borderline (single-weight thin lines, large empty margins outside the circle) |
| 3 | art deco geometric line art (live test 3; rendered as single-stem botanical) | **Borderline** reject/refine — too sparse, lines too thin, but aesthetically pleasing; better line art than 4 | 15.7 | .029 | 1061 | .020 | pass | 6 (very sparse — one stem, hairline strokes, one small filled leaf), 4 borderline (large dead zones) |
| 4 | wildflower line drawing | **Reject** — far too empty; should be prevented | 6.9 | .017 | 387 | .006 | **pass (gate miss)** | 2 (borderline no-subject), 4 (two tiny grass tufts pinned to bottom corners, 99% empty), 6 |
| 5 | (minimalist landscape family) | **Best of the lot** — refine; smudging around finer details | 69.4 | .047 | 3494 | .297 | pass | 5 (soft/mushy edges on fine branch tips and grass blades — check RC-E ESRGAN halo at 100% before blaming FLUX) |
| 6 | (unknown) | **Reject** — empty cream gradient; should be prevented | 0.4 | .010 | 31 | .000 | **FAIL — correct** | 2 (hard fail) |
| 7 | (unknown) | **Reject** — completely off-center, predominantly empty, nonsensical subject (half-chair half-animal + palm trunk) | 8.3 | .024 | 1169 | .029 | **pass (gate miss)** | 2, 3 (hard fail — chair/animal hybrid), 4 (subject crammed bottom-left, ~90% empty), 6 |

### Failure taxonomy (counts over the 5 non-good designs)

- **Too sparse / low subject coverage:** 4 of 5 (2, 3, 4, 7) — the dominant
  failure mode by far.
- **Empty canvas:** 1 (6) — only case the current local gate catches.
- **Malformed/nonsensical subject:** 1 (7).
- **Off-center composition / dead zones:** 2 (4, 7).
- **Smudging / soft detail:** 2 (2, 5) — the *refine*-tier defect; never the
  sole reason for rejection.
- Scene leak: 0 — the H5 "prevent" fix (`36a57bd`) appears to be holding.

### Key quantitative finding — `cov` separates the set perfectly

Subject coverage (`cov`): good/refine designs score **.148–.297**; sparse or
empty rejects score **.000–.029**; borderline 3 sits at .020 (owner-graded
borderline, metric-graded reject — consistent). A clean gap of ~5x exists
between .029 and .148. The current gate (stddev<3 AND edge<0.012) only
catches truly empty frames: **4 and 7 pass it while being owner-condemned
"should be prevented" failures.** Thin line art produces enough local edge
signal to clear `edge_ratio` while covering almost nothing — a structural
blind spot that `cov` closes. Recommendation in §3.

### Calibration-set staleness (action required)

`critic_pass.py:39-45` documents the sanity thresholds as calibrated on
"masters 2/6 must FAIL, 1/5 must PASS" — but master 2 (and 1, 3) have been
**overwritten by new designs**. Old master 2's fingerprint (stddev 0.18,
edge .0096) no longer exists on disk; only 6 still matches its comment. The
labeled set must be restated against current files: must-FAIL {6, 4, 7},
must-PASS {1, 5, 2}, borderline {3} — which the current thresholds do NOT
satisfy (4, 7 pass). See §3.

### Natural-experiment evidence for RC-A (prompt quality)

Candidate 1's stored niche is already a full visual description
("mid-century modern botanical poster, bold filled abstract foliage and
leaves, dense full-frame composition, warm muted palette") — and it produced
the only owner-good design. Candidates 2/3 got shorter, keyword-style niches
and landed in refine/borderline. n=3, but the direction exactly matches
RC-A/S4-b's prediction: descriptive prompts → dense, coherent output;
keyword prompts → sparse output. The S4-b art-brief stage is doing manually
what candidate 1's niche did by accident.

---

## 2. Etsy bestseller trait study (observed 2026-07-20, BE locale)

Searches run with the Bestseller-badge filter across the pipeline's niche
families: botanical line art print, mid century modern botanical print, art
deco geometric wall art, minimalist landscape poster, wildflower print,
retro travel poster. Traits recorded from badge-carrying listings only
(shops in the 200–25k review range). No competitor images were saved;
observations are attribute-level.

### Traits shared by bestsellers (ranked by consistency)

1. **High subject coverage — even in "minimalist" niches.** Bestselling
   artwork fills most of the frame: full wildflower meadows edge-to-edge,
   dense Matisse-style filled foliage, Bauhaus grids covering the canvas,
   full landscape scenes. Genuinely sparse single-motif whitespace posters
   are almost absent from badge results. Where a single small subject
   appears, it is anchored by a background shape (see 4).
2. **Bold, confident marks.** Filled color shapes or medium-weight lines.
   Hairline single-weight line art essentially never carries a badge alone —
   when fine line art sells, it's bundled in sets of 2–3 and/or paired with
   watercolor washes or colored backdrop shapes.
3. **Warm, muted, non-white grounds.** Cream/beige/textured-paper
   backgrounds dominate; pure white grounds are rare. Two palette families
   recur: (a) neutral ground + 2–4 muted accents (sage, olive, terracotta,
   dusty pink); (b) saturated retro (burnt orange, teal, mustard, deep
   green) for MCM/Bauhaus.
4. **Backdrop shapes anchor small subjects.** Colored circles, arches, or
   washes behind the subject — exactly design 2's peach-circle device. That
   instinct is bestseller-aligned; design 2 failed on execution (line
   weight, smudge), not concept.
5. **Style specificity beats generic minimalism.** Badges cluster on
   identifiable idioms: vintage herbarium charts, Bauhaus exhibition
   posters, Japanese woodblock landscapes, Matisse-cutout florals — not
   "minimalist plant".
6. **Sets of 2/3/6 dominate line-art niches.** Merchandising structure, not
   an art-generation trait — relevant to Finding 1's future revisit, out of
   scope here.
7. **Typography is core in some niches.** MCM/Bauhaus (exhibition headers)
   and especially retro travel posters (city names are the product) — the
   pipeline's hard no-text constraint makes these niches structurally
   disadvantaged. Retro travel in particular should be deprioritized in
   research/Go-Hold-Kill until that constraint is ever revisited: a
   text-free "retro travel poster" cannot match what the niche's buyers are
   demonstrably buying. (Consistent with live-test 2 drifting to a bird —
   the niche keyword itself fights the constraint.)

### Gap analysis — our failures vs. bestseller traits

| Bestseller trait | Our set |
|---|---|
| High coverage (trait 1) | The #1 failure mode: 2/3/4/7 all sparse. Design 1 (cov .265) is the only one matching, and it's the only owner-good design. |
| Bold marks (trait 2) | 3 and 4 are hairline-weight; 2 is thin. 1 and 5 (filled shapes/silhouettes) are the two best-rated. |
| Warm non-white ground (trait 3) | Mostly followed (cream grounds) — not a failure driver. |
| Backdrop shape (trait 4) | Design 2 already does this; keep and execute better. |
| Style specificity (trait 5) | Candidate 1's niche names an idiom; the weaker niches were generic. Feeds S4-b brief instructions. |

Bottom line: the bestseller study independently converges on the same two
levers as the failure taxonomy — **coverage/density and mark boldness** —
and both are prompt-controllable (RC-A/RC-B), which strengthens the case
that S4-b + S4-c(1-2) should precede any model upgrade (S4-c-3).

---

## 3. Recommendations (feed-forward into S4-b / S4-c / S4-d)

### Into S4-b (art-brief instructions — the big lever)

Require every brief to specify, in positive natural language: one concrete
subject in a named art idiom (trait 5); a density/coverage clause ("dense
full-frame composition", "filling the frame edge to edge"); mark boldness
("bold filled shapes" / "confident medium-weight lines" — never unqualified
"line art"); a ground ("warm cream background", optionally a backdrop
shape per trait 4); and 2–4 named accent colors from palette family (a) or
(b) (trait 3). Candidate 1's niche string is a working prototype of the
target output format.

### Into S4-c(1) (positive scaffold)

Scaffold vocabulary drawn from the trait list: "flat 2D full-bleed
artwork", "one coherent centered subject", "dense composition filling the
frame", "bold filled color zones with crisp clean edges", "warm muted
palette on a soft cream ground". Coverage/density language is the piece the
current scaffold lacks entirely.

### Into S4-d (gates) — concrete, data-backed changes

1. **Add `cov` (subject-coverage) to the local sanity gate.** Measured gap:
   condemned sparse/empty ≤ .029, owner-acceptable ≥ .148. Proposed:
   hard-fail below **0.05** (catches 4, 6, 7 for free, no vision call),
   flag-to-critic between **0.05–0.12** (catches 3-type borderlines).
   Keep the existing stddev/edge test too — `cov` alone wouldn't
   catch a full-canvas gradient; together they're complementary.
2. **Restate the calibration set** against the current (partly overwritten)
   files: must-FAIL {4, 6, 7}, must-PASS {1, 2, 5}, borderline {3}. Update
   the `critic_pass.py:39-45` comment — it currently cites fingerprints of
   deleted images.
3. **Rubric point 6 wording is vindicated, not over-strict** — every
   owner-condemned design a human would call "too sparse" is one the rubric
   would also fail. The S4-d(2) concern (false-fails on intentional
   minimalism) shows no evidence in this set; hold off softening points 4/6
   until live telemetry shows false-fails. (Reverses the plan doc's prior
   about softening being likely needed.)
4. **Smudging (point 5) is the refine-tier defect** (2, 5) and interacts
   with RC-E: inspect 2/5 at 100% pre- vs post-ESRGAN before attributing
   to FLUX. If the halo appears at upscale, the fix is upscaler config,
   not prompts.

### Verdict vocabulary

The owner's three-tier grading (good / refine / reject) is finer than the
critic's binary `passed`. When S4-d(1) restructures critic output
per-criterion, adopt the same three tiers so owner grades and critic
verdicts stay comparable over time.

### Baseline / regression set

The 7 current masters + owner grades in §1 are the frozen baseline for
measuring S4-b/S4-c: regenerate against the same niches after the prompt
rework and blind-compare. Success = new batch's owner grades strictly
dominate §1's distribution (≥ the 1-good-2-refine-4-reject baseline).

---

## 4. Execution-order note

Nothing here changes the remediation plan's ordering (#3 error handling →
S4-b/c → S4-d). This doc completes step 2 (S4-a) of that sequence; the
executing Claude Code session should treat §3 as S4-a's output artifact and
implement against it. The one addition: re-run the *pipeline* critic on
these 7 masters once Finding 3's fixes land, and diff its per-criterion
verdicts against §1's vision assessment — that closes the "gates unproven
live" gap at zero design cost.

