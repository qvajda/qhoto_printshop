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
