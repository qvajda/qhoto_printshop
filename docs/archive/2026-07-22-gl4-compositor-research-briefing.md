# GL-4 research briefing — mockup compositor approach (library-first) — 2026-07-22

A human-in-the-loop research session (Cowork / Claude in Chrome, with an
optional short local code spike). **Output = a recommendation + a GL-5
implementation plan**, not production code. Feeds the go/no-go on *how* to build
`pipeline/mockup_render.py`.

Context: the GL-6 prototype proved the **scenes** are high quality, but its
throwaway compositor failed on **every** axis — corner/aperture detection,
filling the blank canvas cleanly, cleaning up its own artefacts, and handling a
foreground object partially occluding the poster. Owner's steer: **find an
existing library / OSS project** for poster-into-scene compositing rather than
re-implement Pillow + homography from scratch. GL-2 is already decided (mockups
go pre-launch, near-frontal for v1.0; angled → v1.1).

## The reframe to test first (highest-value question)

The prototype did **runtime blank-quad detection** and that's where much of the
failure lived. But SPEC v4.10 Addendum A's design **annotates the aperture in
`meta.json` at authoring time** (four corner coords per scene). If the aperture
is known from the bundle, **runtime detection may be unnecessary entirely** —
the job collapses to "warp artwork into a known quad + composite a baked
overlay." So the first thing to determine:

> Does author-time aperture annotation + a solid warp/overlay step remove most
> of the prototype's failures, making runtime corner-detection a non-problem?

If yes, the library search narrows to "robust perspective warp + alpha
compositing + shadow/occlusion via a pre-baked overlay" — a much easier target
than "detect + warp + relight."

## Constraints any recommendation must satisfy (from CLAUDE.md + Addendum A)

- **Commercial-use license** on any dependency (this outputs commercial Etsy
  assets). State each candidate's license explicitly. FLUX.1 [schnell] /
  Apache-2.0 is the house standard for the *scene generation*; that's already
  done — this is about the *compositing* step.
- **Fits the runtime shape:** the pipeline is discrete scheduled functions, no
  persistent service. Addendum §6 prefers an **in-process, offline,
  deterministic** compositor (no vendor in the cron loop, zero marginal cost).
  **Dynamic Mockups** (hosted API, ~$0.051/render) is the *sanctioned escape
  hatch* (Addendum §7) if self-host realism is a time-sink — evaluate it head to
  head, don't dismiss it.
- **Asset-bundle format is fixed:** `background.png` + `overlay.png` (alpha,
  composited on top for shadows/highlights/foreground occlusion) + `aperture`
  quad + tag, keyed by `(group_type, orientation)`. A recommendation that needs
  a different asset format must justify the change.
- **Dependency weight:** the project leans zero-/few-dependency (Pillow + numpy
  already in; a hand-rolled SigV4 signer rather than boto3). OpenCV is
  acceptable if it earns its place; flag heavy/GPU/native-build deps as a cost.
- **Scope split:** v1.0 = near-frontal scenes (small/no perspective); v1.1 =
  angled/leaning. The recommendation should say what each phase needs, so v1.0
  isn't over-engineered for angles it won't ship.

## Questions to answer

1. **Detection vs. annotation:** confirm/deny the reframe above. If author-time
   apertures suffice, does the aperture need any runtime refinement at all?
2. **Warp + composite libraries:** what existing Python OSS does perspective
   warp of an image into a quad + clean alpha compositing well? (e.g. OpenCV
   `getPerspectiveTransform`/`warpPerspective`, Pillow `transform(QUAD)`,
   scikit-image `ProjectiveTransform`, `homography`-focused libs.) Which give
   clean edges without the prototype's artefacts?
3. **Foreground occlusion:** the realism-maker. Is a **pre-baked `overlay.png`
   with a foreground alpha mask** (authored once per scene) enough to handle "a
   plant leaf crosses the poster corner," avoiding any runtime segmentation? Or
   is a per-render mask/segmentation step needed (heavier)?
4. **Shadow/highlight realism:** baked overlay (multiply/screen layer authored
   per scene) vs. anything procedural. What's the cheapest path to "reads as a
   real print on a wall" for near-frontal?
5. **Purpose-built mockup tooling:** any OSS "smart mockup / product-image
   compositor" projects on GitHub worth adopting or lifting from? Note license +
   maintenance state. Explicitly compare against **Dynamic Mockups** and
   **Placid/other hosted mockup APIs** on fit, cost at ~30 renders/design,
   license, and vendor-in-cron cost.
6. **Recommendation:** self-host-on-library vs. Dynamic Mockups (escape hatch)
   vs. thin hand-rolled homography — for **v1.0 near-frontal** and **v1.1
   angled** separately. Name the specific library/approach.

## Method

- Survey first (web / GitHub). Then, if useful, a **short local code spike** on
  the real inputs: take one authored near-frontal scene bundle from the GL-6
  prototype + one approved master (`db/base_artwork/`), and warp+composite via
  the top 1–2 candidate approaches. Eyeball against the prototype's output and
  the Gelato-default baseline. Keep any spike code throwaway and clearly marked
  — the production build is GL-5.
- Respect the repo's no-competitor-imagery rule (same as
  `docs/deep-research-briefing-template.md`): don't save others' mockup images
  into the repo.

## Output (deliverables)

1. `docs/2026-07-22-compositor-approach-findings.md`: answers to Q1–Q6, the
   detection-vs-annotation verdict, a comparison table (approach × realism ×
   effort × license × deps × vendor-in-cron × cost), and a **clear
   recommendation** for v1.0 and v1.1.
2. A **GL-5 implementation plan**: the chosen library/approach, the
   `mockup_render.py` module shape (pure-function core: artwork + scene bundle →
   ordered PNGs), any `meta.json`/asset-format tweak, the `mockup_templates`
   config block + `get_mockup_templates()`, and the `primary_mockup`/
   `group_mockup` rewiring + Etsy `uploadListingImage` ordering — enough to hand
   straight to a Claude Code session.

---

## Session prompt (paste into Cowork / Claude in Chrome)

> You are researching how to build a **poster-into-scene mockup compositor** for
> a print-on-demand pipeline. Read `docs/SPEC_v4.10_addendum_custom_mockups.md`
> and this briefing first. The scenes (photorealistic interiors with an empty
> framed poster region) are already generated and high-quality; the aperture
> corners are annotated per scene at authoring time in `meta.json`. Your job is
> to recommend **how to warp the artwork into that aperture and composite
> shadows/highlights/foreground occlusion realistically**, preferring an
> existing library/OSS over a hand-rolled implementation.
>
> First settle the key question: given author-time aperture annotation, is
> runtime corner-detection needed at all, or does the job reduce to warp +
> alpha-composite a pre-baked overlay? Then survey Python libraries for
> perspective warp + clean compositing, and OSS/hosted mockup tools (compare
> explicitly against Dynamic Mockups and other hosted mockup APIs on fit, cost
> at ~30 renders/design, license, and having-a-vendor-in-the-cron-loop cost).
> Every dependency must permit **commercial use** — state each license. Keep the
> asset-bundle format (background + overlay + aperture quad) unless you justify a
> change. Split the recommendation into **v1.0 near-frontal** (ships pre-launch)
> and **v1.1 angled** (fast-follow).
>
> If useful, run a short throwaway spike: warp one approved master into one real
> annotated near-frontal scene via your top 1–2 approaches and compare to the
> Gelato-default baseline. Don't save competitor mockup images into the repo.
>
> Deliver `docs/2026-07-22-compositor-approach-findings.md` (Q1–Q6 + comparison
> table + recommendation) and a GL-5 implementation plan detailed enough to hand
> to a Claude Code session.
