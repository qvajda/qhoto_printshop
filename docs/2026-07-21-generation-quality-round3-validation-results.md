# Round-3 validation results (2026-07-21)

10-candidate batch, base artwork only, no upscale. 5 mode-A (v3 writer,
reusing round-2's 5 Refine niches 16/20/22/23/24 for direct comparison) + 5
mode-B (owner's parallel Cowork deep-research briefs, `docs/round3_mode_b_briefs.json`,
loaded via `pipeline.seed_mode_b --commit`). Blind-graded (labels A-J,
mode hidden), mapping revealed after grading.

## Result: PASS (8 good / 2 refine / 0 reject)

| Label | Candidate | Mode | Niche | Grade | Owner note |
|---|---|---|---|---|---|
| A | 29 | A | Japanese woodblock, cherry blossom branch | Refine | detached branch breaks logical integrity |
| B | 33 | B | mid-century modern desert landscape | Good | small refine: separate the foreground bush from same-color floor |
| C | 31 | B | mid-century modern single bloom | Good | — |
| D | 27 | A | wildflower, single stem (lupine) | Good | could be thicker/more exaggerated to fill the page |
| E | 25 | A | mid-century modern, abstract leaf composition | Good | — |
| F | 30 | B | art deco botanical moth | Good | — |
| G | 28 | A | vintage herbarium, fern + ladybug | Refine | fern not bushy enough, canvas feels half-empty; ladybug looks stamped on top, not integrated |
| H | 26 | A | minimalist landscape, coastal cliffs (sea stack) | Good | — |
| I | 34 | B | cut-paper foliage collage, bird in flight | Good | — |
| J | 32 | B | cottagecore wildflower meadow | Good | stems could be thicker, more density overall |

**Mode split:** Mode A 3 good / 2 refine (25,26,27 good; 28,29 refine).
Mode B 5 good / 0 refine (all five: 30,31,32,33,34).

## Gate check vs plan §4 pass criteria

- ≥ 6 good: **8/10 — PASS**
- 0 reject: **PASS**
- Each round-3 integration defect class in ≤ 1 design:
  - contactless/mis-scaled secondary subject: 1 (candidate 28's ladybug
    "stamped on top, not integrated") — **PASS**
  - drawn containment geometry: 0 — **PASS**
  - bottom-edge blank band: 0 (not raised by owner this batch) — **PASS**
- Backdrop-device usage in 1-4 of 10: candidate 31 (arch), candidate 33
  (sun disc behind peak) = **2/10 — PASS**

**Overall: GO.**

## New defect signal (not one of the three round-3 classes, carry to round 4)

Candidate 29's "detached branch breaking logical integrity" — a botanical
coherence defect distinct from FM-7/8/9 (not a secondary-occupant
integration issue, not drawn geometry, not an edge-grounding miss). One
occurrence. Worth a criterion-3 wording note next round if it recurs.

## Round-4 backlog (owner refine notes, not blocking, not actioned this round)

1. Candidate 29 (cherry blossom): a branch structurally disconnects from
   the main branch — botanical-coherence defect, distinct from named FM
   classes.
2. Candidate 33 (desert mesa): foreground bush rendered in the same color
   as the ground plane, reads as merged/ambiguous silhouette against the
   floor.
3. Candidate 27 (lupine): owner wants the single-stem subject rendered
   thicker/larger to fill more of the frame — a scale-emphasis note, not a
   defect (still graded Good).
4. Candidate 28 (fern + ladybug): two compounding issues — (a) the fern
   itself under-fills the frame (owner: "canvas feels half-empty," subject
   could be bushier/larger), (b) the ladybug reads as pasted on rather than
   gripping the frond — a live example of FM-7(b) contactless integration
   surviving the v3 template's own contact-language field.
5. Candidate 32 (wildflower meadow): owner wants thicker stems and overall
   higher density even though bottom-edge grounding (FM-9) is already
   working correctly in this design.

Common thread across 3/5 notes (27, 28, 32): even where the v3 template's
density/scale wording produced a passing composition, the owner's instinct
keeps landing on "make the dominant element bigger/thicker/denser" — a
possible signal that the v3 "large enough to read across a room" /
"spanning a third of the frame width" scale language could go a step
further for round 4 (push the floor up, not just state a floor).

## Environment note

Generation batch: 9/10 succeeded on first pass; candidate 26 hit a
transient Replicate "No adapter found for model" error (not a 429, not the
granted-credit backpressure pattern round 2 saw) - immediate single retry
succeeded. Not a code defect, no action needed.
