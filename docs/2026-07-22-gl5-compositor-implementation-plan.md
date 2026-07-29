# GL-5 implementation plan — `pipeline/mockup_render.py` (self-hosted compositor)

Hand-off plan for a Claude Code session. Findings/decision:
`docs/2026-07-22-compositor-approach-findings.md`. Design of record:
`docs/SPEC_v4.10_addendum_custom_mockups.md` (Addendum A). This plan is the
production build of the compositor; the `proto/mockup-scene-prototype`
compositor (`scripts/proto_mockup_compositor.py`) is throwaway — read it for
reference, do not promote it.

> **CLAUDE.md gate.** This touches an external system (Etsy image upload) and
> is >30 min → PRD threshold. This document is the PRD; get sign-off before
> building. Do **not** call Etsy `uploadListingImage` or Gelato create against
> real endpoints during dev without explicit go-ahead — use dry-run/fixtures
> (per repo Conventions).

## 1. Problem / success criteria

Build a pure, offline, deterministic compositor that renders an approved
master into the fixed library of scene bundles and returns ordered images for
the Etsy gallery, replacing Gelato's default gallery (Addendum §2, §5).

Success:
1. `render_scene(artwork, bundle) -> PIL.Image` is a pure function: same
   inputs → identical bytes, no network, no global state.
2. Near-frontal scenes composite with no visible seam/staircase (the spike's
   B+ quality bar).
3. Placeholder scene IDs (no bundle on disk) **fail loudly** — never silently
   skip or fall back to a Gelato image (Addendum §4, §5).
4. `primary_mockup` (stage 3) and `group_mockup` (stage 8) consume it and
   write `product_images` with the existing ordering + `image_type` tags
   (3 `flat_mockup` first, then `lifestyle`); render failure →
   `status='mockup_failed'`, no Gelato fallback.
5. Unit-testable against the checked-in fixture bundle with no external calls.

Scope in: the compositor module, config accessor, the two stage rewirings,
Etsy upload ordering. Scope out (do NOT build here): the full scene library
(GL-6-proper), authoring tooling, the 5x7/10x24/landscape bundles beyond
what's needed for a fixture, the Gelato "product created" poll relaxation
(Addendum §5 notes it as a *separate* follow-up — verify before touching).

## 2. Dependency decision

Add **`opencv-python-headless`** to `requirements.txt` (pin a current 4.x,
e.g. `opencv-python-headless==4.11.0.86`; use the version resolved at build
time). Rationale + license (Apache-2.0) in the findings doc Q2/Q6. Also add
**`numpy`** explicitly to `requirements.txt` — it's used at runtime by the
compositor and is currently undeclared (only Pillow is pinned). Headless
(not `opencv-python`) because there's no display in the cron; smaller wheel,
no X11.

If sign-off rejects the new dependency, the documented fallback is the
Pillow-only supersampled path (findings Q6); this plan assumes OpenCV.

## 3. Asset-bundle format — unchanged, one optional additive field

Keep the Addendum §4 bundle exactly: `background.png`, `overlay.png`,
`meta.json`. `meta.json` stays:

```jsonc
{
  "scene": "flat_clips_windowlight",
  "group_type": "primary",          // matches aspect_ratio_groups
  "orientation": "portrait",         // portrait | landscape
  "aperture": [[x,y],[x,y],[x,y],[x,y]],  // TL, TR, BR, BL, pixels in background.png
  "size": [w, h],                   // background.png dimensions
  "tag": "flat"                     // flat | lifestyle
}
```

Optional **additive** field, defaulted so existing bundles keep working:
`"overfill": 0.018` (fraction; default `DEFAULT_OVERFILL = 0.018` if absent).
Do not otherwise change the format (findings: over-fill + frame-edge-in-overlay
is what kills seams). Document in the module + Addendum that for framed
scenes `overlay.png` MUST carry the frame/mat inner edge as opaque foreground
(so the over-filled art bleeds under it).

## 4. Module shape — `pipeline/mockup_render.py`

Pure-function core, one job (Addendum §5). No I/O in the core; a thin loader
resolves bundles from disk.

```python
"""Self-hosted mockup compositor (GL-5). Pure, offline, deterministic.
Warp an approved master into an annotated scene aperture and composite a
pre-baked overlay. No runtime aperture detection (apertures are authored in
meta.json). See docs/2026-07-22-compositor-approach-findings.md."""

from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import cv2
from PIL import Image

DEFAULT_OVERFILL = 0.018      # fraction of quad size, pushed out from centroid
SUPERSAMPLE = 2               # anti-alias factor for the warp + alpha

class MockupRenderError(RuntimeError):
    """Raised on any unrecoverable render problem (missing bundle, bad quad,
    placeholder ID with no assets). Callers map this to status='mockup_failed'."""

@dataclass(frozen=True)
class SceneBundle:
    scene: str
    group_type: str
    orientation: str
    aperture: np.ndarray      # (4,2) float32, TL TR BR BL
    size: tuple[int, int]
    tag: str                  # 'flat' | 'lifestyle'
    background: Image.Image   # RGBA
    overlay: Image.Image      # RGBA
    overfill: float

def load_bundle(bundle_dir: str | Path) -> SceneBundle:
    """Resolve a scene bundle from disk. Missing dir/files/keys ->
    MockupRenderError (this is the placeholder 'fail loud' path)."""
    d = Path(bundle_dir)
    meta_p, bg_p, ov_p = d / "meta.json", d / "background.png", d / "overlay.png"
    if not (meta_p.exists() and bg_p.exists() and ov_p.exists()):
        raise MockupRenderError(f"incomplete/placeholder bundle: {d}")
    meta = json.loads(meta_p.read_text())
    quad = np.asarray(meta["aperture"], dtype=np.float32)
    if quad.shape != (4, 2):
        raise MockupRenderError(f"bad aperture in {meta_p}: {quad.shape}")
    return SceneBundle(
        scene=meta["scene"], group_type=meta["group_type"],
        orientation=meta["orientation"], aperture=quad,
        size=tuple(meta["size"]), tag=meta["tag"],
        background=Image.open(bg_p).convert("RGBA"),
        overlay=Image.open(ov_p).convert("RGBA"),
        overfill=float(meta.get("overfill", DEFAULT_OVERFILL)),
    )

def _overfill_quad(quad: np.ndarray, frac: float) -> np.ndarray:
    c = quad.mean(axis=0)
    return (c + (quad - c) * (1.0 + frac)).astype(np.float32)

def _warp_into_quad(artwork: Image.Image, size, quad, ss=SUPERSAMPLE) -> Image.Image:
    """Homography warp of artwork onto quad, supersampled, with an
    anti-aliased alpha from the warped white mask. Returns RGBA at `size`."""
    W, H = size
    bgr = np.array(artwork.convert("RGB"))[:, :, ::-1]
    ha, wa = bgr.shape[:2]
    src = np.array([[0, 0], [wa, 0], [wa, ha], [0, ha]], np.float32)
    dst = (quad * ss).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(bgr, M, (W * ss, H * ss), flags=cv2.INTER_CUBIC)
    mask = cv2.warpPerspective(np.full((ha, wa), 255, np.uint8), M,
                               (W * ss, H * ss), flags=cv2.INTER_LINEAR)
    warped = cv2.resize(warped, (W, H), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_AREA)
    return Image.fromarray(np.dstack([warped[:, :, ::-1], mask]), "RGBA")

def render_scene(artwork: Image.Image, bundle: SceneBundle) -> Image.Image:
    """PURE core: artwork + bundle -> flattened RGB composite.
    Order: background -> warped art (over-filled) -> overlay (shadows/
    highlights/foreground/frame-edge)."""
    quad = _overfill_quad(bundle.aperture, bundle.overfill)
    warped = _warp_into_quad(artwork, bundle.size, quad)
    out = bundle.background.copy()
    out = Image.alpha_composite(out, warped)
    out = Image.alpha_composite(out, bundle.overlay)
    return out.convert("RGB")

def render_scenes(artwork_path, scene_dirs) -> list[Image.Image]:
    """Given a master image path + an ordered list of bundle dirs, return
    ordered composites. Any bundle failure raises MockupRenderError (caller
    -> mockup_failed). Order is preserved = Etsy rank order."""
    art = Image.open(artwork_path).convert("RGB")
    return [render_scene(art, load_bundle(d)) for d in scene_dirs]
```

Notes:
- No aperture detection anywhere (Q1). The old flood-fill/`detect_aperture_quad`
  from the prototype is deliberately gone.
- Keep `render_scene` free of file I/O so it unit-tests against an in-memory
  fixture. `load_bundle` / `render_scenes` are the I/O seam.
- Determinism: fixed `SUPERSAMPLE`, no randomness, no time — same bytes every
  run (success criterion 1; makes the golden-image test stable).

## 5. Config — `mockup_templates` block + accessor

Per Addendum §4. Add to `config/static_config.json`:

```jsonc
"mockup_templates": {
  "primary": { "portrait": ["flat_clips_windowlight", "flat_leaning_bookstack", "..."],
               "landscape": [] },
  "5x7":     { "portrait": [], "landscape": [] },
  "10x24":   { "portrait": [], "landscape": [] }
}
```

Order in the list == render/rank order; keep the ordering contract (flat/
straight-on `image_type='flat_mockup'` first, then `lifestyle`) — encode it by
listing the 3 flat scene IDs before the 7 lifestyle ones (Addendum §2, §5).

In `pipeline/config.py` add, mirroring the existing static-config accessors
(`get_group_type_for_size`, `get_shipping_profile_id`):

```python
def get_mockup_templates(group_type: str, orientation: str) -> list[str]:
    """Ordered scene IDs for (group_type, orientation). Resolved once from
    static config; never discovered at runtime (same rule as Gelato IDs)."""
```

Add a resolver from scene ID → bundle dir:
`assets/mockups/<group_type>/<orientation>/<scene_id>/`. A scene ID present in
config with **no** bundle dir on disk is the placeholder case → let
`load_bundle` raise `MockupRenderError` (fail loud). Do not pre-filter it
away.

## 6. Pipeline rewiring

**`pipeline/primary_mockup.py` (stage 3).** After the Gelato product for the
primary size is created, stop consuming Gelato's gallery for the storefront.
Instead:
1. `orientation` from the artwork/group; `scene_ids =
   config.get_mockup_templates("primary", orientation)`.
2. `images = mockup_render.render_scenes(master_path, [bundle_dir(s) for s in scene_ids])`.
3. Persist each rendered PNG where the Etsy upload step reads from (same store
   used for Gelato galleries today — local file or R2), and write
   `product_images` rows with existing ordering + `image_type` (`flat_mockup`
   for the first 3, `lifestyle` after), matching current schema.
4. On any `MockupRenderError`: `status='mockup_failed'` (existing status/
   semantics), no Gelato fallback (Addendum §2, §5).
5. Gelato create-from-template still runs for fulfilment; its returned gallery
   is discarded. Do **not** change the Gelato "mockups ready" poll here — the
   Addendum flags that as a separate, verify-first follow-up.

**`pipeline/group_mockup.py` (stage 8).** Same, keyed by the group under
review (`5x7` / `10x24`) and that group's re-crop of the base artwork; use
that group's `get_mockup_templates(group_type, orientation)`.

**Etsy publish (stages 7 / 11).** Upload stored mockup refs via
`uploadListingImage` in list/rank order (flat first, then lifestyle). No
shipping change here (resolved separately, per-group). Keep the existing
1-image-per-request + `rank` contract (Addendum §5).

**Critic pass (stages 5 / 9).** Unchanged — it now grades our custom
composites, which is desired (catches a bad composite before the digest).

## 7. Tests

- `tests/test_mockup_render.py`:
  - `render_scene` golden test against a checked-in fixture bundle (reuse one
    prototype bundle, e.g. `flat_clips_windowlight`) + a small fixture
    artwork; assert output size == `meta.size` and compare to a committed
    golden PNG (allow a tiny per-pixel tolerance for libjpeg/opencv version
    drift, or assert on a downscaled hash).
  - `load_bundle` raises `MockupRenderError` on: missing dir, missing
    `overlay.png`, malformed aperture (not 4×2). This is the placeholder
    fail-loud contract.
  - `render_scenes` preserves order.
  - Determinism: two `render_scene` calls produce identical bytes.
  - Purity: no network/file access inside `render_scene` (pass in-memory
    `Image`s).
- Reuse the `proto/mockup-scene-prototype` bundles as fixtures (copy one into
  `tests/fixtures/mockups/...`; keep the fixture small).
- Commit after the module + its test pass (repo convention: commit after each
  stage passes its manual M1 test). Don't hold the whole suite hostage to
  unrelated branches.

## 8. Build order (for the Claude Code session)

1. Branch off `master` (bring the approved bundles over from
   `proto/mockup-scene-prototype` into `assets/mockups/...`, or land them via
   GL-6-proper first — confirm with owner which bundles are canonical).
2. Add deps (`opencv-python-headless`, `numpy`) to `requirements.txt`.
3. Write `pipeline/mockup_render.py` (§4) + `tests/test_mockup_render.py`
   (§7). Green.
4. Add `mockup_templates` config + `get_mockup_templates()` + bundle-dir
   resolver (§5). Test the placeholder fail-loud path.
5. Rewire `primary_mockup` (§6); test with a dry-run/fixture, no real Etsy/
   Gelato writes.
6. Rewire `group_mockup` (§6); same.
7. Wire Etsy `uploadListingImage` ordering (§6) behind the existing dry-run
   flag; only go live on explicit owner go-ahead.
8. Manual M1: render the real approved master into the real primary/portrait
   bundles, eyeball vs. the spike bar; then (with go-ahead) one guarded live
   upload.

## 9. Risks / watch-items

- **Frame-edge in overlay:** the over-fill trick needs framed scenes'
  `overlay.png` to include the opaque frame/mat inner edge. Prototype overlays
  are lighting-only — GL-6-proper authoring must add it, or over-fill will
  spill visibly onto the mat. Track as an authoring acceptance criterion.
- **Steep-angle scenes (v1.1):** same code path, but corner-annotation
  precision matters more. If hand-authoring convincing overlays for many steep
  scenes stalls, the sanctioned fallback is Dynamic Mockups for those scenes
  only (hybrid) — see findings Q6; weigh its 24h-link/PSD/vendor-in-cron cost
  first.
- **opencv wheel size (~40MB):** fine for the runtime, but confirm it fits the
  scheduled-function deploy image size budget before merging.
- **Determinism across opencv/libjpeg versions:** pin the versions; make the
  golden test tolerant to avoid false failures on minor bumps.
