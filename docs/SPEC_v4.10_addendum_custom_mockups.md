# SPEC v4.10 — Addendum A: Custom mockup pipeline

Status: **proposed, needs sign-off** (touches Etsy via API + >30 min work →
PRD threshold per CLAUDE.md §2). Fold into the next SPEC minor bump once
approved; log the decision in `docs/CHANGELOG.md`.

Supersedes the mockup-source behaviour in SPEC v4.10 §3 step 3 (primary
mockup) and the equivalent in `group_mockup` (stage 8). Everything else in
those steps — ordering, `image_type` tagging, critic pass over the gallery,
Telegram digest — is unchanged.

---

## 1. Problem

Today the gallery comes from Gelato: `products:create-from-template` returns
Gelato's own flat mockup + lifestyle/room-context images, and the pipeline
just orders and stores them (`product_images`, `image_type` in
`flat_mockup` / `lifestyle`). The output is inconsistent scene-to-scene and
off-brand, and we don't control the scene set. We want **one fixed set of
~10 hand-crafted mockups**, identical scene composition on every design, as
the storefront imagery.

## 2. Decision

**Decouple storefront imagery from Gelato, completely.** Gelato is reduced
to print file + fulfilment; it no longer supplies the Etsy gallery, and we
keep **no** Gelato mockup as a fallback (decision, Q4). The pipeline renders
the already-approved artwork into a fixed library of mockup scene templates
and uploads the results to Etsy directly via `uploadListingImage`.
If a custom render fails, the path is `mockup_failed` → retry, never a
silent fall-back to a Gelato image.

- Rendering engine: **self-hosted compositor** (Pillow + a perspective warp
  via `numpy`/OpenCV homography), running in-process. No third-party render
  API, no per-render cost, no vendor in the cron loop. Reason it fits: our
  scenes are a *fixed* set authored once, and flat poster-on-wall art is the
  easy compositing case — a homography plus a baked shadow/highlight overlay
  gets ~90% of the realism. See §6/§7 for why this beats the hosted option
  **for this specific project**, and the escape hatch if it doesn't.
- Each scene template is an **asset bundle**, not a PSD: `background.png`
  (scene behind the poster) + `overlay.png` (shadows/highlights/foreground,
  alpha, composited on top) + `aperture` (four corner coords of the poster
  region). Rendering = warp artwork to the aperture quad, paste over
  background, composite overlay on top.
- Template library is **static config**, resolved once, never discovered at
  runtime (consistent with the Gelato template-ID / static-config rule).
- Etsy allows **20 images/listing** (since Aug 2025); we use ~10. Upload is
  one image per request with a `rank`; keep the existing ordering contract:
  straight-on/flat mockup(s) first (`image_type='flat_mockup'`), then
  lifestyle/room-context (`image_type='lifestyle'`).

The base artwork is still **image-generated exactly once** — every mockup,
every size, every group reuses that same base image. Unchanged invariant.

## 3. Aspect-ratio families (the key wrinkle)

A single mockup set cannot serve all sizes: the poster aperture in each scene
must match the artwork's aspect ratio or the print gets cropped/stretched.
Our six sizes collapse into **three ratios × two orientations**:

| Family | Sizes | Ratio (portrait) | Notes |
|---|---|---|---|
| ISO / primary | 8x12, A3, A2, A1 | ~1:1.414 (0.707) | the primary group; one render scales to all four |
| 5x7 | 5x7 | 5:7 (0.714) | **own dedicated set** (decision, Q1) — not reused from ISO |
| Panoramic | 10x24 | 5:12 (0.417) | genuinely different; own scenes |

So the template registry is keyed by **(group_type, orientation)**, matching
the existing `aspect_ratio_groups` / `get_group_type_for_size()` split — the
same three-group structure already used for shipping and review. **Three
distinct scene sets** (ISO, 5x7, panoramic), each × orientation, **10 scenes
per set: 3 flat/straight-on + 7 lifestyle** (decision, Q2). Etsy's 20-image
ceiling leaves headroom.

## 4. Config

Scene assets live in the repo (e.g. `assets/mockups/<group_type>/<orientation>/<scene>/`,
each holding `background.png`, `overlay.png`, `meta.json` with the aperture
corners + `flat`/`lifestyle` tag). `config/static_config.json` gets a
`mockup_templates` block that just lists scene IDs in render order, keyed to
match `aspect_ratio_groups`:

```jsonc
"mockup_templates": {
  "primary": { "portrait": ["<scene_id>", ...], "landscape": [...] },
  "5x7":     { "portrait": [...], "landscape": [...] },
  "10x24":   { "portrait": [...], "landscape": [...] }
}
```

- Expose `config.get_mockup_templates(group_type, orientation) -> list[str]`
  (ordered scene IDs; the compositor resolves each to its asset bundle on
  disk). No render-API key needed — nothing external to authenticate.
- **Placeholder policy (mirror the Gelato-template rule):** scene slots may
  start as placeholder IDs; build/test freely against them, but if a
  still-placeholder ID (no asset bundle on disk) reaches a real (non-mocked)
  render call, it must **fail loudly** with a clear error — never silently
  skip or upload a Gelato-default image instead.

## 5. Pipeline changes

- **`primary_mockup` (stage 3):** after the Gelato product is created for
  the primary size, *do not* fetch Gelato's gallery for the storefront.
  Instead render the approved artwork into
  `get_mockup_templates("primary", orientation)` via the self-hosted
  compositor, write the resulting image refs into `product_images` with the existing
  ordering + `image_type` tagging (**3 `flat_mockup` first, then 7
  `lifestyle`**). On any render failure, set `status='mockup_failed'`
  (existing status, existing semantics) — no Gelato fallback.
  Note: Gelato's create-from-template still runs (we need the product for
  fulfilment) but its returned gallery is discarded; a follow-up
  optimisation may relax the Gelato "mockups ready" poll to a "product
  created" poll since we no longer consume those images — verify before
  changing the poll.
- **`group_mockup` (stage 8):** same, keyed by the group under review
  (`5x7` / `10x24`), using that group's re-crop of the same base artwork.
- **New module `pipeline/mockup_render.py`** (self-hosted compositor,
  independently testable, one job — given one artwork image + an ordered list
  of scene IDs, warp/composite each and return ordered rendered images).
  Pure-function core (artwork + scene bundle → PNG), trivial to unit-test
  against a checked-in fixture scene. Keeps the one-module-per-stage
  convention. Renders are written to wherever the Etsy upload step reads from
  (local file or the same store used for Gelato galleries today).
- **Etsy publish (stages 7 / 11):** upload the stored mockup URLs via
  `uploadListingImage` in rank order. No per-variant shipping change here —
  shipping profile mapping is resolved separately (Addendum B / group-level
  Small vs Large).
- **Critic pass (stages 5 / 9):** unchanged mechanically — it already grades
  every gallery image. It now grades our custom scenes, which is desirable
  (catches a bad artwork/scene composite before it reaches the digest).

## 6. Engine choice — why self-hosted (Q3 elaborated)

Decision: **self-host the compositor.** Rationale specific to this project:

- **Scenes are fixed and authored once.** The only real cost of self-hosting
  is one-time: build the warp+overlay compositor, and author a
  shadow/highlight overlay per scene. That's amortised over unlimited future
  designs — the opposite of a shop that spins up new templates constantly
  (which is where a hosted renderer earns its keep).
- **Posters are the easy compositing case.** Flat rectangular art on a wall,
  straight-on or gentle angle — a homography plus one multiply/overlay layer
  is convincing. This is far more forgiving than wrinkled apparel or curved
  mugs.
- **No vendor in the cron loop.** Zero marginal cost, but more importantly no
  API rate limits, no mid-batch downtime, no watermark/credit-tier gotchas,
  fully deterministic and offline. In an automated twice-daily pipeline that
  reliability is worth more than the dollars.
- **Cost of the hosted option, for reference:** Dynamic Mockups bills credits
  (1 API render = 1 credit, ~$0.051, clean only on paid). Our volume ≈ 30
  renders/design on a clean pass (~$1.53), up to ~90 on full retries — cheap
  in absolute terms (~$180–$1,530/yr depending on throughput). The point
  isn't that it's expensive; it's that we get equal-or-better fit here for $0
  and no external dependency.

**`psd-tools` caveat (why we don't just "use psd-tools"):** psd-tools is a
PSD *reader/parser*, not a Photoshop-grade renderer — it can't do
smart-object replace-warp-and-re-render. "Self-hosted" therefore means we
write the compositor (Pillow + homography + baked overlay); psd-tools is not
in the path at all. That's why our scene format is a flat asset bundle
(background + overlay + aperture), not a PSD.

**Escape hatch:** if the compositor's realism on angled lifestyle scenes
proves a time sink, the swap to **Dynamic Mockups** is cheap and localised —
only `mockup_render.py` and the asset format change; the pipeline, config
shape, ordering, and critic pass are untouched. Reassess after the first
real scene set is composited and eyeballed.

## 7. Alternatives considered (rejected)

- **Dynamic Mockups (hosted API)** — fastest path to photoreal angled
  scenes with no compositor to build; rejected as the *default* only because
  self-host fits this fixed-scene, cost-sensitive project better. Kept as the
  documented escape hatch (§6).
- **Gelato Mockup Studio custom mockups** — UI-oriented, coupled to Gelato's
  publish flow; awkward for a headless pipeline that owns Etsy images.
- **Curate/reorder Gelato's default gallery** — lowest effort, fails the
  "well-crafted, always the same set" bar.

## 8. Resolved decisions

1. **Q1 — 5x7:** own dedicated scene set, not reused from ISO. ✅
2. **Q2 — set size/split:** 10 scenes per set, **3 flat + 7 lifestyle**,
   flat ranked first. ✅
3. **Q3 — engine:** **self-hosted compositor** (Pillow + homography + baked
   overlays); Dynamic Mockups kept as escape hatch only. ✅ (see §6)
4. **Q4 — Gelato fallback:** dropped entirely — custom mockups only,
   `mockup_failed` + retry is the sole failure path. ✅
