# Prompt — prototype mockup generator

Paste into a fresh Claude session with image generation. It builds a
3-phase prototype: extract style → generate/select scenes → emit a
self-hosted asset bundle (background + overlay + aperture JSON) per size
ratio and orientation, ready for the Pillow/homography compositor.

---

You are helping me prototype a **poster mockup generator** for a print-on-demand
shop. I'll give you a few example mockup images (interior/lifestyle scenes with a
framed or unframed poster on a wall). Work in three phases and **stop for my input
between each**.

**Phase 1 — Style extraction.**
Study my example images and write a compact "style DNA": scene type, wall/surface,
lighting direction and warmth, palette, props, camera angle and distance, framing
(framed vs unframed, mat, frame colour/material), and mood. Keep it to a tight spec
I can reuse as a generation seed. Show it to me and wait for confirmation before
generating anything.

**Phase 2 — Scene variations.**
From that style DNA, generate **8–12 new empty-frame scene variations** in the same
style — different rooms/angles/props but visibly one cohesive set. Critical rules
for every scene:
- The poster area must be an **empty rectangular aperture filled flat solid magenta
  (#FF00FF)**, so the placement region is unambiguous — no artwork inside it yet.
- Straight-on and gentle-angle scenes both welcome; label each scene "flat" (near
  straight-on) or "lifestyle" (angled/contextual).
- Render at high resolution (long edge ≥ 2400 px).
Present them as a labelled grid. I'll reply with the scene numbers I want to keep.

**Phase 3 — Size/orientation set + self-hosted asset bundles.**
For each scene I select, produce the full matrix below — same scene, aperture
re-shaped to each target ratio, in both orientations (skip landscape where a scene
clearly can't support it, and tell me which you skipped and why):

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
  magenta quad.
- `preview.png` — a flattened composite with a placeholder poster in the aperture,
  so I can eyeball fit without running the pipeline.

Name each bundle folder `<scene>_<ratioKey>_<orientation>/`.

Deliverables: the style DNA, the selected scenes, and a folder of asset bundles
(background + overlay + meta + preview per variant) plus a top-level manifest
listing every bundle — ready to drop into the pipeline's
`assets/mockups/<group>/<orientation>/` and render with Pillow.

Constraints: original scenes only — do not imitate a specific photographer or brand.
Target 10 scenes per set (3 flat + 7 lifestyle); 5x7 gets its own dedicated set.
Ask me before deviating from those.
