# GL-4 findings — mockup compositor approach (library-first) — 2026-07-22

Research output for the go/no-go on *how* to build `pipeline/mockup_render.py`
(GL-5). Companion GL-5 implementation plan:
`docs/2026-07-22-gl5-compositor-implementation-plan.md`. Feeds
`docs/SPEC_v4.10_addendum_custom_mockups.md` §5–§6 and the GL-2 decision
(mockups ship pre-launch, near-frontal for v1.0; angled → v1.1).

Inputs used: the four committed prototype bundles on
`proto/mockup-scene-prototype`
(`assets/mockups/primary/portrait/<scene>/{background,overlay,meta}`), the
approved master `db/base_artwork/31.png`, the prototype findings
(`docs/2026-07-22-mockup-prototype-findings.md`), and a throwaway spike
described in "Spike" below. No competitor imagery was saved into the repo;
spike outputs live outside it.

---

## TL;DR

The prototype's failures were **detection failures, not warp failures**. The
Addendum already annotates the aperture at authoring time in `meta.json`, so
**runtime corner-detection is not needed at all** — the job collapses to
"warp the master into a known quad + alpha-composite a pre-baked overlay."
Once you stop detecting, the only remaining defects (the two "seams" in the
prototype) are edge-quality artefacts with a known, cheap fix: an
**anti-aliased warp (supersampled) + a small over-fill of the quad + the
frame edge carried in `overlay.png`**.

Recommendation: **self-host on OpenCV** (`cv2.getPerspectiveTransform` +
`cv2.warpPerspective`, supersampled soft-alpha mask), keep the existing
asset-bundle format unchanged, and treat **v1.0 near-frontal and v1.1 angled
as the same code path** — v1.1 needs better *authoring* precision, not a
different compositor. Dynamic Mockups stays the documented escape hatch but
is a poor structural fit here (PSD re-authoring, 24-hour render-link expiry,
a vendor in the twice-daily cron) and should only be reached for if
hand-authoring overlays for steep scenes genuinely stalls.

---

## Q1 — Detection vs. annotation (the reframe): **confirmed.**

The reframe holds, and strongly. The prototype's own post-mortem
(`docs/2026-07-22-mockup-prototype-findings.md`) shows every hard failure was
in *finding* the aperture: flood-fill from centre leaked into the wall
because the rendered "blank white" insert and the wall paint sit only ~6–15
RGB units apart, so corners had to be hand-read, and mis-read corners — not
the homography — produced the seams. The Addendum design removes that entire
failure class by construction: the four corners are authored into
`meta.json` (`aperture: [[TL],[TR],[BR],[BL]]`) and the compositor just reads
them.

Does the annotated aperture need any **runtime refinement**? No. Refinement
(snapping corners to a detected edge) would re-introduce the exact
detection step we just deleted, and on these low-contrast inserts it would be
*less* reliable than the human-verified authoring annotation. The correct
place for corner precision is the **authoring tool** (draw/adjust the quad by
hand, once per scene, with the quad overlaid for visual confirmation — the
"show the quad, owner corrects it" loop the Addendum already anticipates).
Runtime stays a pure, deterministic function of `(artwork, bundle)`.

One consequence worth stating: because detection is gone, **the quality bar
moves entirely onto warp + composite edge quality**. That is where the two
prototype "seams" actually came from, and the spike below shows they are a
2-line fix, not a research problem.

## Q2 — Warp + composite libraries

All four candidates below do a mathematically correct planar homography
(4-point perspective) — none is "wrong." The differences are edge
anti-aliasing, speed, and dependency weight.

- **OpenCV** (`opencv-python-headless`) — `getPerspectiveTransform(src, dst)`
  then `warpPerspective(...)`. Warp a solid white mask through the *same*
  transform to get the alpha; render at 2× and downscale with `INTER_AREA`
  for a clean anti-aliased aperture edge. Fast (C++), the industry-standard
  homography path. **License: Apache-2.0** (OpenCV core since 4.5.0; the
  `opencv-python` packaging layer is MIT). Commercial-safe. **Recommended.**
- **Pillow** `Image.transform(size, Image.PERSPECTIVE, coeffs)` — already in
  the repo. A real homography (8 coefficients solved with numpy, as the
  prototype did). Correct, zero new deps. Its weakness is the alpha edge: a
  raw `ImageDraw.polygon` mask is not anti-aliased, giving the staircase seen
  in the spike's Pillow output. Fixable by supersampling the whole
  warp+mask, but at that point you've re-implemented what OpenCV gives for
  free. **License: MIT-CMU / HPND.** Commercial-safe. **Viable zero-new-dep
  fallback.**
- **scikit-image** `ProjectiveTransform` + `warp` — also a correct
  homography, NumPy-native, nice API. But it's a heavier scientific
  dependency (pulls scipy, networkx, etc.) for no edge-quality win over
  OpenCV, and it's slower. **License: BSD-3-Clause.** Commercial-safe. Not
  worth its weight here.
- **NumPy** — transitive under all of the above for array work. **License:
  BSD-3-Clause.** Commercial-safe.

Clean edges without the prototype's artefacts come from **how you build the
alpha**, not which library warps: (a) supersample so the diagonal aperture
edge is anti-aliased, and (b) over-fill the quad by ~1.5–2% so the warped art
bleeds *under* the frame/mat rather than stopping a pixel short and exposing
the background. OpenCV makes both trivial; Pillow can do (a) with extra code.

## Q3 — Foreground occlusion: **pre-baked `overlay.png` is enough.**

Yes — a pre-baked foreground alpha in `overlay.png`, authored once per scene,
fully handles "a plant leaf crosses the poster corner" with **no runtime
segmentation**. The compositing order is the whole trick: `background.png`
(scene behind the poster) → warped artwork (clipped to the aperture) →
`overlay.png` (shadows/highlights *and* any foreground object that should sit
in front of the print). Anything the overlay draws on top — a frame edge, a
leaf, a shelf lip — occludes the artwork for free. Since the scenes are a
fixed, authored set, the occluding pixels are known at authoring time;
per-render masking would be pure waste. This also means the **frame/mat inner
edge belongs in the overlay**, which is what lets the over-fill trick hide
seams cleanly (the art bleeds under an edge the overlay redraws on top).

Practical authoring note: the prototype dropped `lifestyle_nook_monstera`
because a monstera leaf occluded ~40% of the aperture. That is a *staging*
limit, not a compositor limit — keep foreground objects clipping <~15% of the
aperture (a corner, an edge), which the overlay handles convincingly; reserve
heavy occlusion for scenes where it's a deliberate, hand-authored effect.

## Q4 — Shadow/highlight realism: **baked overlay, cheapest path wins.**

For near-frontal, a **baked multiply/screen overlay authored per scene** is
both the cheapest and the most convincing option, and it's already the
Addendum's format. Two ingredients read as "a real print on a wall": a soft
contact/drop shadow along the top and hinge-side edges (a dark, low-alpha
multiply band, feathered ~6–12px), and a gentle directional light gradient
across the print matching the scene's light (a screen/além-white layer, very
low alpha). The prototype derived these automatically from the lighting FLUX
had already baked onto the blank insert — a legitimate shortcut that proves
the concept; GL-5 should let the author refine them by hand per scene (or
keep the auto-derived version when it already looks right).

Procedural relighting (estimating a normal map, ray-marching soft shadows,
etc.) is not worth it here: it adds real complexity and dependencies to beat
a hand-tuned 2-layer overlay that a fixed scene only needs authored **once**.
Skip it.

## Q5 — Purpose-built mockup tooling (OSS + hosted)

**OSS.** No open-source project is a drop-in for this job; the useful
"library" is the OpenCV/Pillow primitive, not a framework.

- **`automated_mockups`** (pip `mockup-generator`, **MIT**, Pillow + numpy +
  scikit-image + OpenCV; ~66★, lightly maintained). Closest in spirit:
  detects a coloured placeholder box, then places the design with
  fit/fill/stretch + rotation. Two disqualifiers for us: (1) it detects the
  placeholder by colour — the *exact* approach that failed in the prototype
  on low-contrast inserts — and (2) it does bounding-box + rotation
  placement, **not a true 4-corner perspective homography**, so it can't do
  leaning/angled scenes, and it has no baked-overlay occlusion/shadow layer.
  Worth reading for its batch/CLI shape; not worth adopting. Its dependency
  list is a useful confirmation that OpenCV+Pillow+numpy is the standard
  stack for this.
- **`Raj-Srikar/Custom-Mockup-Generator`** (**MIT**) — JS + Photopea, driven
  by PSD smart objects and luminosity masks. Not Python, needs PSD authoring
  and the Photopea API in the loop. Wrong shape for a headless, offline cron.
- Broader GitHub `mockup-generator` topic is dominated by apparel/PSD or
  hosted-SaaS wrappers; nothing does "warp into an annotated quad + baked
  overlay" better than ~40 lines of OpenCV.

**Hosted mockup APIs** (compared head-to-head per the Addendum's escape-hatch
requirement; pricing verified 2026-07):

- **Dynamic Mockups** — the sanctioned escape hatch. Render API, 1 render =
  1 credit; Pro is **$15/mo billed annually = 3,600 credits/yr** with top-ups
  at **$0.051/credit**; free tier watermarks API renders (unusable for
  commercial output), clean only on paid. Rate limit 300 calls/min.
  **Critical operational catch: rendered image links are retained only 24
  hours** — the cron must download-and-persist every render immediately.
  Templates are **PSD smart-object** based, so adopting it means
  **re-authoring every scene as a PSD** (a format change from our bundle) and
  hosting each design asset at a URL or uploading it as a binary. Realism on
  angled wall-art is excellent out of the box. Not an OSS licence — a SaaS
  subscription whose ToS permits commercial use of outputs on paid plans
  (their entire customer base is POD sellers).
- **Placid** — credit model, 1 image = 1 credit; template-driven (their own
  editor), REST API. Same structural costs as any hosted option (vendor in
  the cron, credit accounting, template re-authoring in their format).
  Comparable in fit to Dynamic Mockups, weaker wall-art library.
- **Others (Mockuuups, Mediamodifier, Placeit)** — same category, same
  vendor-in-cron and format-lock-in costs; none preferable to Dynamic
  Mockups for this use case.

**Cost at ~30 renders/design.** A clean pass is ~30 renders (~$1.53 at
$0.051), up to ~90 on full retries (~$4.59); annualised this is roughly
$180–$1,530/yr depending on throughput — cheap in dollars. The real cost of
the hosted path is **structural, not monetary**: a vendor in a twice-daily
autonomous cron (rate limits, downtime, credit-tier and watermark gotchas,
the 24h link expiry), plus a one-time PSD re-authoring of the whole scene
library and an asset-format change. For a **fixed** scene set the self-host
build cost is one-time and then $0/forever with no external dependency —
which is exactly why the Addendum (§6) prefers it.

## Q6 — Recommendation (v1.0 near-frontal, v1.1 angled)

**v1.0 near-frontal (ships pre-launch): self-host on OpenCV.**
`cv2.getPerspectiveTransform` + `cv2.warpPerspective` at 2× supersample for
an anti-aliased aperture alpha; composite `background → warped art (over-fill
~1.5–2%) → overlay.png`; no runtime detection (read `meta.json` aperture);
foreground occlusion + shadow/highlight from the baked `overlay.png`. This is
the spike's winning path and it produced a production-clean near-frontal
composite on the first pass. Keep the asset-bundle format exactly as-is. Add
one dependency: `opencv-python-headless`.

- *Zero-new-dependency alternative*, if you'd rather not add OpenCV: the
  Pillow path already in the repo, made clean by supersampling the warp and
  the polygon mask. It works for pure-frontal but costs ~30–40 extra lines
  and is slower; OpenCV earns its weight the moment v1.1 angled scenes need
  reliably clean diagonal edges. Recommendation is OpenCV.

**v1.1 angled (fast-follow): the same compositor, better authoring — not a
new engine.** The homography already handles perspective; the spike warped
the steep `lifestyle_sage_terracotta` scene cleanly once the quad was
over-filled and the frame edge lived in the overlay. What steep scenes
actually need is **accurate corner annotation** (an authoring-tool concern)
and a per-scene over-fill amount + a foreground frame edge in the overlay —
all authoring, all one-time. So v1.0 does **not** get over-engineered for
angles: it's the identical `warp_into_quad` function; v1.1 is a scene-library
and authoring-precision expansion, not a code rewrite.

**Dynamic Mockups: escape hatch only, and a narrow one.** Reach for it solely
if hand-authoring convincing overlays for many steep scenes proves a real
time-sink during GL-6-proper. Even then the clean fallback is a **hybrid**
(self-host frontal scenes, Dynamic Mockups only for the handful of hardest
angled ones) — but weigh that against its PSD re-authoring, 24h link expiry,
and vendor-in-cron cost before adopting. For a fixed scene set it is
structurally the worse fit despite trivial dollar cost.

---

## Comparison table

| Approach | Realism (near-frontal) | Realism (angled) | Build effort | License | Deps added | Vendor in cron? | Cost @ ~30 renders/design |
|---|---|---|---|---|---|---|---|
| **OpenCV warp + baked overlay** (recommended) | Excellent (spike: clean 1st pass) | Good once quad is accurate (spike: clean after over-fill) | Low — ~40-line pure fn | Apache-2.0 / MIT wrapper | `opencv-python-headless` (+numpy) | No | $0 |
| Pillow warp + supersampled mask | Good (needs AA mask code) | OK; more edge-tuning | Low-med — +30–40 lines vs OpenCV | MIT-CMU/HPND | none (in repo) | No | $0 |
| scikit-image ProjectiveTransform | Good | Good | Med — heavier API | BSD-3-Clause | scikit-image (+scipy) | No | $0 |
| `automated_mockups` (pip) | OK (bbox+rotation, colour detect) | Poor (no true homography) | Low to call, but wrong primitives | MIT | opencv+skimage+pillow | No | $0 |
| Dynamic Mockups (hosted) | Excellent | Excellent | Low code, high re-authoring (PSD) | SaaS ToS (commercial OK, paid) | swap `mockup_render.py` + PSD assets | **Yes** | ~$1.53 clean / ~$4.59 w/ retries |
| Placid (hosted) | Good | Good | Low code, template re-authoring | SaaS ToS | swap + their templates | **Yes** | ~1 credit/render |

Realism ratings for the self-host rows are grounded in the spike (below); the
hosted rows are from vendor capability, not a saved render (no competitor
imagery kept per the repo rule).

## Spike (throwaway — not committed to the repo)

Ran one disposable script against the real inputs to settle Q1/Q2 with pixels
rather than argument. Using the **annotated `meta.json` aperture only (no
detection)**, warped `db/base_artwork/31.png` into two real prototype scenes —
`flat_clips_windowlight` (near-frontal) and `lifestyle_sage_terracotta`
(steep/leaning) — via three variants:

- **A — Pillow `Image.transform(PERSPECTIVE)` + hard polygon alpha** (the
  prototype's method). Near-frontal: clean. Steep scene: visible **staircase
  aliasing** along the top edge and a **thin dark gap line** down the
  hinge-side edge — i.e. the two "seams" the prototype reported, reproduced.
- **B — OpenCV `warpPerspective`, 2× supersample, warped-white-mask alpha,
  exact quad.** Aliasing gone (soft AA edge). A faint gap line remained where
  the annotated quad sat a hair inside the frame opening.
- **B+ — same as B, quad over-filled 1.5% from centroid.** Both seams
  **eliminated**: the art bleeds under the frame edge, no staircase, reads as
  a print sitting in the frame.

Near-frontal `flat_clips_windowlight` under B was **production-clean on the
first pass** — clips overlay on top, natural drop shadow, tight edges.
Conclusion: the seams were detection/aliasing/gap artefacts, not homography
error; supersampled OpenCV + a small over-fill + frame-in-overlay closes
them. The spike is throwaway; GL-5 is the real build.

## Open items for GL-5 / authoring

- Decide the over-fill amount: a global default (~1.5–2%) vs. a per-scene
  `overfill` field in `meta.json` for steep scenes. Recommend a global
  default now, add the optional per-scene override only if a scene needs it.
- Confirm `overlay.png` for framed scenes includes the frame/mat inner edge
  as opaque foreground (required for the over-fill trick). The prototype's
  auto-derived overlays are lighting-only; GL-6-proper authoring must add the
  frame edge.
- `opencv-python-headless` vs `opencv-python`: use **headless** (no GUI/X11
  deps, smaller, correct for a server/cron). Prebuilt manylinux wheels, no
  native build, no GPU — the only real cost is ~40MB wheel size. Acceptable.

---

## Sources

- [Dynamic Mockups pricing](https://dynamicmockups.com/pricing/) ·
  [Dynamic Mockups API FAQ](https://docs.dynamicmockups.com/getting-started/frequently-asked-questions)
  (credits, 300/min rate limit, 24h render-link retention, watermark policy)
- [Placid pricing](https://placid.app/pricing)
- [automated_mockups (pip mockup-generator, MIT)](https://github.com/CTDave001/automated_mockups)
- [Raj-Srikar/Custom-Mockup-Generator (MIT, Photopea/PSD)](https://github.com/Raj-Srikar/Custom-Mockup-Generator)
- Local: `docs/SPEC_v4.10_addendum_custom_mockups.md`,
  `docs/2026-07-22-mockup-prototype-findings.md`,
  `assets/mockups/primary/portrait/*` (on `proto/mockup-scene-prototype`)
