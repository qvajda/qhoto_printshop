# GL-19 compositor M1 acceptance — status update for planner

**Date:** 2026-07-24
**Branch:** feat/gl5-mockup-compositor
**Outcome: STOPPED at Phase 1 (offline render gate). Phase 2 (live Etsy upload) not attempted.**

## What ran

- Phase 0 (pre-flight, offline): PASS. 504/504 tests, all 4 primary/portrait
  bundles complete, master resolved.
- **Master correction**: kickoff doc's named default `db/base_artwork/31.png`
  was wrong — candidate 31 is stuck `pending_generation`, never approved.
  User redirected to candidate 39's `39.png` (approved+published primary+5x7
  groups, matches the live-test-round-1 published candidate). Flag this doc
  drift if `31.png` is referenced elsewhere as "the approved master."
- Phase 1 (offline render, no network): ran the 4 real bundles through
  `render_scenes()` via a throwaway harness (`scripts/gl19_m1_render.py`).
  Renders are deterministic and size-correct, but **failed the B+ eyeball
  bar on all 4 scenes** on closer inspection (initial pass missed it;
  user's zoom-level review caught it) — not just the anticipated steep-angle
  scene.

## Root cause: authoring, not compositor

Verified against raw bundle assets, not just composites:

1. **Aperture quads are imprecise hand-traced polygons**, not pixel-accurate
   to the photographed paper edges. Overlaying `flat_leaning_bookstack`'s
   quad on its raw `background.png` shows the quad's straight right edge
   sitting outside the real (perspective-tapered) paper edge. Same class of
   error, smaller, on all other scenes — this produces the seam/dash lines
   at frame edges.
2. **Overlay foreground occluders are not fully opaque.** Overlay alpha
   channel maxes at 187 (`flat_clips_windowlight`, clip band) and 172
   (`flat_leaning_bookstack`, book band) — never 255. Since render order is
   background → warped art → overlay, the overlay is supposed to redraw
   foreground objects (clips, book spines) opaquely on top to occlude the
   art underneath. Partial alpha there is why clips/books look "see-through."

`pipeline/mockup_render.py`'s warp + alpha-composite logic is correct given
these inputs — confirmed by the fact that every scene's mid-artwork area
(away from clips/books/frame corners) renders clean in every sample.

## Recommendation

- PR #2 (GL-5 compositor) is **not mergeable as a full pipeline yet** for
  Etsy-facing images — code is sound, but its only real asset inputs
  (aperture authoring + overlay opacity) don't meet the bar.
- Route the fix to **GL-6-proper**: re-trace aperture quads against actual
  photographed edges (perspective-aware, not straight-line approximations),
  and re-author overlay foreground occluders at full opacity.
- GL-19 (this task) is done as scoped — it was a render/verify gate, not a
  fix task; no code changes were made to the compositor or bundles.

## Not done (and why)

- Phase 2 live Etsy upload: gated on Phase-1 sample approval, which did not
  pass. No live calls made, no Gelato writes, no listing state changes.
- No merge, no rebase, no compositor/overlay edits attempted (explicitly
  out of scope for this run — "report and STOP, don't redesign").

## Artifacts left on branch

- `scripts/gl19_m1_render.py` — throwaway harness (not promoted into
  `pipeline/`), reusable once GL-6-proper lands to re-check the same 4
  scenes.
- `outputs/gl19_m1/*.png` — the 4 sample composites reviewed this session.
