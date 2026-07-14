# Prompt — prototype mockup generator

Paste into a fresh Claude session with image generation. It builds a
3-phase prototype: extract style → generate/select scenes → emit PSD
smart-object templates per size ratio and orientation.

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

**Phase 3 — Size/orientation set + PSD templates.**
For each scene I select, produce the full matrix below — same scene, aperture
re-shaped to each target ratio, in both orientations (skip landscape where a scene
clearly can't support it, and tell me which you skipped and why):

| Ratio key | Aspect (portrait W:H) | Covers |
|---|---|---|
| iso    | 1 : 1.414 | 8x12, A3, A2, A1 (and 5x7 — ~1% off, reuse unless I say otherwise) |
| p5x7   | 5 : 7     | 5x7 only, if I ask for a dedicated set |
| pano   | 5 : 12    | 10x24 panoramic |

Orientations: `portrait` and `landscape` (swap W:H).

Then package each variant as a **layered PSD mockup template** with:
- a background raster layer (the scene),
- a **smart-object layer named exactly `Design`**, transformed (warped to the four
  magenta-aperture corners) so my artwork drops straight in,
- the magenta fill removed/hidden behind the smart object.

Since image generation produces flat rasters, not layered PSDs, do the packaging
with a **script you write and run**: detect the magenta quad's four corner
coordinates in each render, then assemble the PSD via `psd-tools` (or an equivalent
you justify). For each variant output: the final PSD, a flattened PNG preview, and
the detected corner coordinates. Name files
`mockup_<scene>_<ratioKey>_<orientation>.psd`.

Deliverables: the style DNA, the selected scenes, and a folder of PSD smart-object
templates + PNG previews + a manifest (scene, ratio, orientation, corner coords,
flat/lifestyle tag) ready to load into a Dynamic Mockups-style renderer.

Constraints: original scenes only — do not imitate a specific photographer or brand.
Ask me before assuming scene count, the flat-vs-lifestyle split, or whether 5x7 gets
its own set.
