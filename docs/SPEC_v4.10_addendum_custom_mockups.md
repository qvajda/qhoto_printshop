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

**Decouple storefront imagery from Gelato.** Gelato keeps producing the
print file and fulfilling; it no longer supplies the Etsy gallery. The
pipeline renders the already-approved artwork into a fixed library of
PSD smart-object mockup templates and uploads the results to Etsy directly
via `uploadListingImage`.

- Rendering engine: **Dynamic Mockups API** (PSD templates whose artwork
  layer is a smart object named `Design`; sub-second render, batch). Reason
  it fits: API-first, headless, matches the discrete-cron / one-function-
  per-stage architecture — no UI step in the loop.
- Template library is **static config**, resolved once, never discovered at
  runtime (consistent with the Gelato template-ID / static-config rule).
- Etsy allows **20 images/listing** (since Aug 2025); we use ~10. Upload is
  one image per request with a `rank`; keep the existing ordering contract:
  straight-on/flat mockup(s) first (`image_type='flat_mockup'`), then
  lifestyle/room-context (`image_type='lifestyle'`).

The base artwork is still **image-generated exactly once** — every mockup,
every size, every group reuses that same base image. Unchanged invariant.

## 3. Aspect-ratio families (the key wrinkle)

A single mockup set cannot serve all sizes: the poster aperture in each PSD
must match the artwork's aspect ratio or the print gets cropped/stretched.
Our six sizes collapse into **three ratios × two orientations**:

| Family | Sizes | Ratio (portrait) | Notes |
|---|---|---|---|
| ISO / primary | 8x12, A3, A2, A1 | ~1:1.414 (0.707) | the primary group; one render scales to all four |
| 5x7 | 5x7 | 5:7 (0.714) | ~1% off ISO — **may share the ISO template** with a minor aperture tweak, confirm visually |
| Panoramic | 10x24 | 5:12 (0.417) | genuinely different; needs its own scenes |

So the template registry is keyed by **(group_type, orientation)**, matching
the existing `aspect_ratio_groups` / `get_group_type_for_size()` split — the
same three-group structure already used for shipping and review. ~10 scenes
per (family × orientation); ISO and 5x7 may reuse one physical PSD set.

## 4. Config

Add to `config/static_config.json` a `mockup_templates` block, keyed to
match `aspect_ratio_groups`:

```jsonc
"mockup_templates": {
  "primary": { "portrait": ["<psd_or_dm_template_id>", ...], "landscape": [...] },
  "5x7":     { "portrait": [...], "landscape": [...] },
  "10x24":   { "portrait": [...], "landscape": [...] }
}
```

- Expose `config.get_mockup_templates(group_type, orientation) -> list[str]`
  and `config.get_mockup_engine_key()` (Dynamic Mockups API key from `.env`,
  same handling as the Gelato/Etsy/Telegram credentials — never in a
  committed file).
- **Placeholder policy (mirror the Gelato-template rule):** template slots
  may start as placeholder strings; build/test freely against them, but if a
  still-placeholder template ID reaches a real (non-mocked) render call, it
  must **fail loudly** with a clear error — never silently skip or upload a
  Gelato-default image instead.

## 5. Pipeline changes

- **`primary_mockup` (stage 3):** after the Gelato product is created for
  the primary size, *do not* fetch Gelato's gallery for the storefront.
  Instead render the approved artwork into
  `get_mockup_templates("primary", orientation)` via the Dynamic Mockups
  client, write the resulting URLs into `product_images` with the existing
  ordering + `image_type` tagging. On any render failure, set
  `status='mockup_failed'` (existing status, existing semantics).
- **`group_mockup` (stage 8):** same, keyed by the group under review
  (`5x7` / `10x24`), using that group's re-crop of the same base artwork.
- **New module `pipeline/mockup_render.py`** (thin Dynamic Mockups client,
  independently testable, one job — render N templates from one artwork URL,
  return ordered image URLs). Keeps the one-module-per-stage convention.
- **Etsy publish (stages 7 / 11):** upload the stored mockup URLs via
  `uploadListingImage` in rank order. No per-variant shipping change here —
  shipping profile mapping is resolved separately (Addendum B / group-level
  Small vs Large).
- **Critic pass (stages 5 / 9):** unchanged mechanically — it already grades
  every gallery image. It now grades our custom scenes, which is desirable
  (catches a bad artwork/scene composite before it reaches the digest).

## 6. Alternatives considered (rejected)

- **Gelato Mockup Studio custom mockups** — you can upload your own scenes,
  but it's UI-oriented and coupled to Gelato's publish flow; awkward for a
  headless cron pipeline that owns Etsy images directly.
- **Self-hosted compositing** (Pillow / ImageMagick / node-canvas, or
  headless Photoshop scripting) — zero per-render cost, full control, fine
  for flat straight-on frames; but we'd build the perspective/lighting
  ourselves and it looks worse on angled lifestyle shots. Keep as fallback
  if Dynamic Mockups cost becomes material.
- **Curate/reorder Gelato's default gallery** — lowest effort, fails the
  "well-crafted, always the same set" bar.

## 7. Open questions (need answers before build)

1. Do we render 5x7 on its own PSD set or reuse the ISO set with an aperture
   tweak? (visual check on one design decides it)
2. Exactly how many scenes in the fixed set, and the flat-vs-lifestyle split
   / order (e.g. 3 straight-on + 7 lifestyle)?
3. Dynamic Mockups plan/pricing at our expected render volume vs self-hosted
   fallback — worth a quick cost check before committing the dependency.
4. Do we keep any Gelato-generated image at all (e.g. as a fallback if a
   custom render fails), or is `mockup_failed` + retry the only path?
