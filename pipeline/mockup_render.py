"""Self-hosted mockup compositor (GL-5, hardened by GL-21). Pure, offline,
deterministic. Warp an approved master into an annotated scene aperture and
composite a pre-baked overlay. No runtime aperture detection (apertures are
authored in meta.json). See docs/2026-07-22-compositor-approach-findings.md.

GL-21 (docs/2026-07-26-gl6-attempt3-production-readiness-plan.md §3.1) lifted
the GL-19 freeze on this module and added three things:

  C1  the colour warp uses BORDER_REPLICATE. cv2.warpPerspective defaults to
      BORDER_CONSTANT=0 (black), which INTER_CUBIC then blends into every
      partial-coverage border pixel - measured at 710-1479 px per scene,
      ~120/255 mean error. The *mask* warp must stay BORDER_CONSTANT:
      replicating an all-255 mask would fill the whole frame.
  C2  an optional per-pixel `matte.png` in the bundle. The quad decides where
      the art is *projected*; the matte decides what is *visible*, per pixel,
      anti-aliased. It replaces the quad-as-silhouette, the occluder boxes and
      the bundle-side repaint bands of attempt 2. Absent file => byte-identical
      to pre-GL-21 behaviour.
  C3  a render-time aspect guard: the artwork is centre cover-cropped to the
      quad's aspect (never stretched, never letterboxed) and anything past
      MAX_COVER_CROP fails loud. Attempt 2 shipped quads from 0.56 to 0.69
      against a 0.684 master - up to 18% silent non-uniform stretch of a print
      a buyer pays for.

`overfill` predates the matte and is **deprecated for matte bundles**: with a
matte, the quad is authored as the min-area quad of the matte expanded on the
short axis to the master's aspect, so coverage is guaranteed and the matte
trims the anti-aliased edge. Matte bundles author `overfill: 0.0`; the field
stays in the schema for the pre-matte bundles.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import cv2
from PIL import Image

DEFAULT_OVERFILL = 0.018      # fraction of quad size, pushed out from centroid
SUPERSAMPLE = 2               # anti-alias factor for the warp + alpha
MAX_COVER_CROP = 0.02         # C3: max linear fraction of the master we may crop

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
    matte: np.ndarray | None = None   # (H,W) float32 0..1, or None (C2)

def _load_matte(path: Path, size: tuple[int, int]) -> np.ndarray:
    """matte.png -> (H,W) float32 coverage in 0..1. Accepts a single-channel
    image or anything with an alpha channel (the alpha wins)."""
    img = Image.open(path)
    img = img.getchannel("A") if "A" in img.getbands() else img.convert("L")
    if img.size != size:
        raise MockupRenderError(f"matte {path} is {img.size}, bundle is {size}")
    return np.asarray(img, dtype=np.float32) / 255.0

def load_bundle(bundle_dir: str | Path) -> SceneBundle:
    """Resolve a scene bundle from disk. Missing dir/files/keys ->
    MockupRenderError (this is the placeholder 'fail loud' path).
    `matte.png` is optional; absent means pre-GL-21 behaviour."""
    d = Path(bundle_dir)
    meta_p, bg_p, ov_p = d / "meta.json", d / "background.png", d / "overlay.png"
    if not (meta_p.exists() and bg_p.exists() and ov_p.exists()):
        raise MockupRenderError(f"incomplete/placeholder bundle: {d}")
    meta = json.loads(meta_p.read_text())
    quad = np.asarray(meta["aperture"], dtype=np.float32)
    if quad.shape != (4, 2):
        raise MockupRenderError(f"bad aperture in {meta_p}: {quad.shape}")
    size = tuple(meta["size"])
    matte_p = d / "matte.png"
    return SceneBundle(
        scene=meta["scene"], group_type=meta["group_type"],
        orientation=meta["orientation"], aperture=quad,
        size=size, tag=meta["tag"],
        background=Image.open(bg_p).convert("RGBA"),
        overlay=Image.open(ov_p).convert("RGBA"),
        overfill=float(meta.get("overfill", DEFAULT_OVERFILL)),
        matte=_load_matte(matte_p, size) if matte_p.exists() else None,
    )

def quad_aspect(quad: np.ndarray) -> float:
    """Width/height of a (4,2) TL TR BR BL quad, averaging opposite edges."""
    w = (np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2
    h = (np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2
    return float(w / h)

def cover_crop_to_aspect(artwork: Image.Image, target_aspect: float,
                         max_crop: float = MAX_COVER_CROP) -> tuple[Image.Image, float]:
    """C3. Centre cover-crop `artwork` to `target_aspect`, never stretch, never
    letterbox. Returns (cropped, crop_fraction) where crop_fraction is the
    linear fraction of the cropped axis that was discarded - the authoring tool
    records it in scene.json. Raises MockupRenderError past `max_crop` rather
    than silently distorting the print."""
    w, h = artwork.size
    art_aspect = w / h
    crop = 1.0 - min(art_aspect, target_aspect) / max(art_aspect, target_aspect)
    if crop > max_crop:
        raise MockupRenderError(
            f"aperture aspect {target_aspect:.4f} vs artwork {art_aspect:.4f} needs a "
            f"{crop:.1%} cover-crop, over the {max_crop:.1%} limit - re-author the quad"
        )
    if art_aspect > target_aspect:
        nw = round(h * target_aspect)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:
        nh = round(w / target_aspect)
        box = (0, (h - nh) // 2, w, (h - nh) // 2 + nh)
    return artwork.crop(box), crop

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
    # C1: BORDER_REPLICATE on the colour warp only - BORDER_CONSTANT=0 (the
    # default) is black, and INTER_CUBIC drags every border pixel toward it.
    # The mask warp keeps the default: replicating 255 would fill the frame.
    warped = cv2.warpPerspective(bgr, M, (W * ss, H * ss), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
    mask = cv2.warpPerspective(np.full((ha, wa), 255, np.uint8), M,
                               (W * ss, H * ss), flags=cv2.INTER_LINEAR)
    warped = cv2.resize(warped, (W, H), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_AREA)
    return Image.fromarray(np.dstack([warped[:, :, ::-1], mask]), "RGBA")

def render_scene(artwork: Image.Image, bundle: SceneBundle) -> Image.Image:
    """PURE core: artwork + bundle -> flattened RGB composite.
    Order: background -> warped art (cover-cropped, matted) -> overlay
    (shadows/highlights/foreground/frame-edge)."""
    quad = _overfill_quad(bundle.aperture, bundle.overfill)
    art, _crop = cover_crop_to_aspect(artwork, quad_aspect(quad))
    warped = _warp_into_quad(art, bundle.size, quad)
    if bundle.matte is not None:
        rgba = np.array(warped)
        rgba[:, :, 3] = np.rint(rgba[:, :, 3] * bundle.matte).clip(0, 255).astype(np.uint8)
        warped = Image.fromarray(rgba, "RGBA")
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
