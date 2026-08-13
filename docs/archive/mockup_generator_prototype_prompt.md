# Prompt — prototype mockup generator

Paste into the **code agent** (it has the Replicate skills installed:
`find-models`, `compare-models`, `run-models`, `prompt-images`). It builds a
3-phase prototype: extract style → generate/select scenes **via Replicate** →
emit a self-hosted asset bundle (background + overlay + aperture JSON) per size
ratio and orientation, ready for the Pillow/homography compositor.

---

You are helping me prototype a **poster mockup generator** for a print-on-demand
shop. I'll give you a few example mockup images (interior/lifestyle scenes with a
framed or unframed poster on a wall). Work in three phases and **stop for my input
between each**.

**Image generation runs through Replicate**, using the installed skills — do not
use any other image backend:
- `find-models` + `compare-models` to pick a photorealistic interior/scene model.
- **License guardrail (hard):** these scenes become commercial Etsy listing assets,
  so only pick models whose licence permits **commercial use**. FLUX.1 [schnell]
  (Apache-2.0) is the known-good default in this stack; **FLUX.1 [dev] is
  non-commercial → do not use it.** If you propose a non-FLUX-schnell model, state
  its licence and flag it to me before running.
- `prompt-images` to turn the style DNA into effective prompts.
- `run-models` to batch-generate concurrently, poll, and pull the outputs.
Tell me which model you chose and why before Phase 2 generation.

**Phase 1 — Style extraction.**
Study my example images and write a compact "style DNA": scene type, wall/surface,
lighting direction and warmth, palette, props, camera angle and distance, framing
(framed vs unframed, mat, frame colour/material), and mood. Keep it to a tight spec
I can reuse as a generation seed. Show it to me and wait for confirmation before
generating anything.

**Phase 2 — Scene variations (via Replicate).**
Using the chosen Replicate model (`run-models`, prompts built with `prompt-images`),
generate **8–12 new empty-frame scene variations** in the same style — different
rooms/angles/props but visibly one cohesive set. Rules for every scene:
- Render the poster as an **empty framed picture with a plain, evenly-lit blank white
  insert** — no artwork. (Diffusion models won't emit a clean #FF00FF fill reliably,
  so we detect/mark the blank quad afterwards rather than prompting for magenta.)
- **Stage the poster at the set's apparent scale:** ISO set → large / statement piece
  (A1–A2 feel); 5x7 set → small / intimate (shelf, desk, gallery cluster); panoramic
  set → wide statement (above a sofa/bed). Keep it believable, not cartoonishly huge.
- Straight-on and gentle-angle scenes both welcome; label each "flat" (near
  straight-on) or "lifestyle" (angled/contextual).
- Request the largest dimensions the model supports (long edge ≥ 2400 px if
  available; otherwise upscale via a Replicate upscaler using `run-models`).
- **Record the `seed` and exact prompt for every kept scene** — Phase 3 reuses them.
- Run the batch **concurrently** via `run-models`, then present the outputs as a
  labelled grid. I'll reply with the scene numbers I want to keep.

**Phase 3 — Size/orientation set + self-hosted asset bundles.**
For each scene I select, produce the full matrix below — the **same scene**, poster
aperture re-shaped to each target ratio, in both orientations (skip landscape where a
scene clearly can't support it, and tell me which you skipped and why). To keep the
scene identical across ratios, **reuse the recorded Replicate model + seed + prompt**
and vary only the output dimensions (or outpaint/extend the canvas); don't free-
generate a fresh scene per ratio.

| Ratio key | Aspect (portrait W:H) | Covers |
|---|---|---|
| iso    | 1 : 1.414 | 8x12, A3, A2, A1 |
| p5x7   | 5 : 7     | 5x7 (its own dedicated set) |
| pano   | 5 : 12    | 10x24 panoramic |

Orientations: `portrait` and `landscape` (swap W:H).

The renderer is self-hosted (Pillow + a homography warp) — **not** Photoshop and
**not** a PSD-based tool — so package each variant as a flat **asset bundle**, not a
PSD. Since image generation produces flat rasters, do the packaging with a **script
you write and run**. Per variant, emit:
- `background.png` — the scene with the poster region empty (fill it neutral; the
  compositor pastes artwork over it).
- `overlay.png` — a transparent-alpha layer holding everything that should sit *on
  top* of the poster: cast shadows, highlights/glare, and any foreground object
  (plant, frame edge). This is what sells the realism; derive it from the scene's
  lighting. If a scene has no foreground occlusion, it's just the shadow/highlight
  gradient on transparent.
- `meta.json` — `{ "scene": "...", "ratio": "iso|p5x7|pano", "orientation":
  "portrait|landscape", "aperture": [[x,y],[x,y],[x,y],[x,y]] (TL,TR,BR,BL, px),
  "size": [w,h], "tag": "flat|lifestyle" }`. Detect the aperture corners from the
  blank white poster region (frame's inner edge); show me the detected quad over the
  scene so I can correct it before you commit the bundle.
- `preview.png` — a flattened composite with a placeholder poster in the aperture,
  so I can eyeball fit without running the pipeline.

Name each bundle folder `<scene>_<ratioKey>_<orientation>/`.

Deliverables: the style DNA, the selected scenes, and a folder of asset bundles
(background + overlay + meta + preview per variant) plus a top-level manifest
listing every bundle — ready to drop into the pipeline's
`assets/mockups/<group>/<orientation>/` and render with Pillow.

Constraints: original scenes only — do not imitate a specific photographer or brand.
Target 10 scenes per set (3 flat + 7 lifestyle); ISO, 5x7, and panoramic are three
separate sets, each staged at its own apparent scale (above). For the ISO set,
include **one size/scale-reference image** (poster-vs-furniture or a dimensions
graphic) so the small variants aren't misrepresented — this may be an 11th image.
Ask me before deviating from those.
