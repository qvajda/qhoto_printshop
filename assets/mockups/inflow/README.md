# Scene inflow — hand-generated mockup source images

Drop hand-generated keyed scene images here. `scripts/scene_author.py extract`
turns one of these into a bundle under `assets/mockups/<group>/<orientation>/`.

```
assets/mockups/inflow/
  primary/     # printed 0.6667 (8x12) - 0.7071 (A3/A2/A1)
  5x7/         # printed 0.7143
  10x24/       # printed 0.4167
```

## Why here and not `outputs/`

Every bundle's `scene.json` records a `source_image`, and §8.4 of the attempt-3
findings established that bundles are a *pure function of source image + tool* —
a defect found in the tool costs one `extract` per scene to re-issue, not a
re-authoring session. That property only holds while the sources survive.

`outputs/gl6_*` and `outputs/attempt1_*photo.png` are **git-ignored**, so
`flat_leaning_bookstack`'s source is one `git clean` away from being gone and
that bundle would become unreproducible. `assets/` is tracked. Sources live here
from now on.

Keep files at **~2000–2400 px on the long side**. A 4800 px source renders a
supersampled warp four scenes deep, twice daily; 2400 px still leaves ~600×860
of print area, which is more than an Etsy gallery image needs.

## Naming

```
<tag>_<descriptor>.png          e.g. lifestyle_bench_fern.png
<tag>_<descriptor>.json         the provenance sidecar, same stem
```

`<tag>` is `flat` or `lifestyle`, matching the existing library
(`flat_clips_windowlight`, `lifestyle_shelf_books`, …) — the tag drives gallery
order, flat scenes first.

## The sidecar is not optional

A hand-generated image has no batch `manifest.json` behind it, so nothing else
records where it came from. `scene.json` carries provenance forward only if the
sidecar is there to be copied. See `_TEMPLATE.json`.

## Before authoring

```bash
python scripts/scene_screen.py assets/mockups/inflow/primary --group primary
```

The screen is a **ranker, not the gate** — it derives the aspect exactly as the
author does (§10.2), so a screen pass means the aspect will survive `extract`,
but the eight-detector gate and the full-frame review still decide. Two things
the screen provably cannot see:

- **A prop whose colour is close to the key.** A yellow-green fern frond against
  an emerald panel sits inside `KEY_LAB_TOL`, so the mask swallows it, the panel
  still reads as a solid rectangle, and `occluders` reports 0.0 — while the art
  would print straight over a leaf that is visibly *in front* of the poster.
  Standing rule: **emerald and green foliage don't mix.** Keep plants clear of
  the panel, or key that scene in magenta.
- **Anything outside the print.** That is `scene-fidelity`'s job at the gate, and
  it only exists because a full-frame review of a *composite* missed a wash over
  two thirds of the frame (§8.2). Review the bare scene next to the composite.
