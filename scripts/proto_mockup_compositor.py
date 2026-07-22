"""
THROWAWAY SPIKE — GL-6 mockup prototype, Phase 3.

Minimal Pillow-only homography compositor to prove the mockup concept out on
a handful of scenes. This is NOT the production compositor (that's GL-5,
`pipeline/mockup_render.py`). Do not import this from pipeline code, do not
extend it — if the concept is approved, GL-5 gets built properly (better
quad detection, hand-authored overlays, OpenCV homography).

What it does, per scene:
  1. Auto-detects the blank poster aperture by flood-filling from the image
     center (the scenes were generated with a plain white poster insert).
  2. Warps the real approved artwork into that quad via a hand-solved
     perspective transform (PIL has no cv2 dependency here — 8-coefficient
     homography solved with numpy, applied via Image.transform(PERSPECTIVE)).
  3. Derives a shadow/highlight overlay from the *original* blank-poster
     lighting (the diffusion model already rendered a lighting gradient
     across the "blank white" insert — reusing it as a multiply/screen layer
     is the spike's shortcut for "baked overlay authoring", which GL-5 would
     do by hand per scene).
  4. Writes an Addendum-compatible bundle: background.png, overlay.png,
     meta.json, preview.png.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(REPO_ROOT, "scratch_mockup_proto", "phase2_raw")
DEBUG_DIR = os.path.join(REPO_ROOT, "scratch_mockup_proto", "phase3_debug")
BUNDLE_ROOT = os.path.join(REPO_ROOT, "assets", "mockups", "primary", "portrait")
ARTWORK_PATH = os.path.join(REPO_ROOT, "db", "base_artwork", "31.png")

SCENES = [
    "flat_clips_windowlight",
    "flat_leaning_bookstack",
    "lifestyle_sage_terracotta",
    "lifestyle_bedroom_console",
]
FLAT_TAG = {"flat_clips_windowlight": "flat", "flat_leaning_bookstack": "flat"}

# Flood-fill auto-detect (detect_aperture_quad below) turned out unreliable on
# these renders: the "blank poster" fill and the wall paint are both
# near-white and only ~6-15 units apart in RGB, well inside normal
# color-similarity flood-fill tolerance, so it leaks into the wall. Hand-read
# corners instead for this spike; this is exactly the "show the quad, owner
# corrects it" step the addendum expects to be manual/approximate.
MANUAL_QUADS = {
    "flat_clips_windowlight": [(252, 332), (662, 340), (660, 930), (254, 920)],
    "flat_leaning_bookstack": [(214, 214), (700, 216), (708, 948), (206, 950)],
    "lifestyle_sage_terracotta": [(302, 268), (700, 245), (715, 930), (338, 968)],
    "lifestyle_bedroom_console": [(295, 150), (655, 150), (655, 720), (295, 720)],
}


def detect_aperture_quad(scene_img: Image.Image, thresh=35):
    """Flood-fill from center to find the blank poster region; return its
    4 extreme corners (TL, TR, BR, BL) as a cheap quad approximation."""
    w, h = scene_img.size
    flood = scene_img.convert("RGB").copy()
    ImageDraw.floodfill(flood, (w // 2, h // 2), (255, 0, 255), thresh=thresh)
    arr = np.array(flood)
    mask = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)
    ys, xs = np.nonzero(mask)
    if len(xs) < 100:
        raise RuntimeError("flood fill found no usable aperture region")
    s = xs.astype(int) + ys.astype(int)
    d = xs.astype(int) - ys.astype(int)
    tl = (int(xs[s.argmin()]), int(ys[s.argmin()]))
    br = (int(xs[s.argmax()]), int(ys[s.argmax()]))
    tr = (int(xs[d.argmax()]), int(ys[d.argmax()]))
    bl = (int(xs[d.argmin()]), int(ys[d.argmin()]))
    return [tl, tr, br, bl], mask


def find_coeffs(source_corners, dest_corners):
    """Solve the 8 perspective coefficients PIL needs for
    Image.transform(size, Image.PERSPECTIVE, coeffs): maps each OUTPUT
    (dest) corner back to the corresponding SOURCE corner."""
    matrix = []
    for (xa, ya), (xb, yb) in zip(source_corners, dest_corners):
        matrix.append([xb, yb, 1, 0, 0, 0, -xa * xb, -xa * yb])
        matrix.append([0, 0, 0, xb, yb, 1, -ya * xb, -ya * yb])
    A = np.array(matrix, dtype=float)
    B = np.array(source_corners, dtype=float).reshape(8)
    return np.linalg.solve(A, B)


def warp_artwork_into_quad(artwork: Image.Image, canvas_size, quad):
    wa, ha = artwork.size
    source_corners = [(0, 0), (wa, 0), (wa, ha), (0, ha)]
    coeffs = find_coeffs(source_corners, quad)
    warped_rgb = artwork.convert("RGB").transform(
        canvas_size, Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC
    )
    alpha = Image.new("L", canvas_size, 0)
    ImageDraw.Draw(alpha).polygon(quad, fill=255)
    warped = warped_rgb.convert("RGBA")
    warped.putalpha(alpha)
    return warped


def derive_overlay(scene_img: Image.Image, mask: np.ndarray, quad):
    """Shortcut overlay: reuse the lighting gradient the diffusion model
    already rendered onto the blank poster insert, as a shadow/highlight
    layer confined to (a slightly inset) aperture region."""
    arr = np.array(scene_img.convert("RGB")).astype(float)
    lum = arr.mean(axis=2)
    ref = float(np.percentile(lum[mask], 95)) or 255.0
    factor = lum / ref

    h, w = lum.shape
    overlay = np.zeros((h, w, 4), dtype=np.uint8)

    shadow = np.clip(1.0 - factor, 0, 1)  # 0..1, higher = darker
    shadow_alpha = np.clip(shadow * 190, 0, 190).astype(np.uint8)
    overlay[..., 0] = 20
    overlay[..., 1] = 18
    overlay[..., 2] = 15
    overlay[..., 3] = shadow_alpha

    highlight = np.clip(factor - 1.03, 0, 0.4)  # glare/warm glow above reference white
    highlight_alpha = np.clip(highlight * 400, 0, 160).astype(np.uint8)
    hl_mask = highlight_alpha > overlay[..., 3]
    overlay[hl_mask, 0] = np.clip(arr[hl_mask, 0], 0, 255).astype(np.uint8)
    overlay[hl_mask, 1] = np.clip(arr[hl_mask, 1], 0, 255).astype(np.uint8)
    overlay[hl_mask, 2] = np.clip(arr[hl_mask, 2], 0, 255).astype(np.uint8)
    overlay[hl_mask, 3] = highlight_alpha[hl_mask]

    overlay_img = Image.fromarray(overlay, "RGBA")

    aperture_mask_img = Image.new("L", scene_img.size, 0)
    ImageDraw.Draw(aperture_mask_img).polygon(quad, fill=255)
    inset = aperture_mask_img.filter(ImageFilter.MinFilter(9))  # feather ~4px in
    feathered = inset.filter(ImageFilter.GaussianBlur(3))

    r, g, b, a = overlay_img.split()
    a = Image.composite(a, Image.new("L", a.size, 0), feathered)
    overlay_img = Image.merge("RGBA", (r, g, b, a))
    return overlay_img


def draw_quad_debug(scene_img: Image.Image, quad):
    dbg = scene_img.convert("RGB").copy()
    draw = ImageDraw.Draw(dbg)
    draw.polygon(quad, outline=(255, 0, 0), width=4)
    for i, (x, y) in enumerate(quad):
        draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(0, 255, 0))
        draw.text((x + 10, y - 10), f"{i}", fill=(255, 0, 0))
    return dbg


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    artwork = Image.open(ARTWORK_PATH).convert("RGB")

    for scene_id in SCENES:
        scene_path = os.path.join(RAW_DIR, f"{scene_id}.png")
        scene_img = Image.open(scene_path).convert("RGB")

        quad = MANUAL_QUADS[scene_id]
        mask_img = Image.new("L", scene_img.size, 0)
        ImageDraw.Draw(mask_img).polygon(quad, fill=255)
        mask = np.array(mask_img) > 0

        debug_img = draw_quad_debug(scene_img, quad)
        debug_img.save(os.path.join(DEBUG_DIR, f"{scene_id}_quad.png"))

        warped = warp_artwork_into_quad(artwork, scene_img.size, quad)
        overlay = derive_overlay(scene_img, mask, quad)

        composite = scene_img.convert("RGBA")
        composite = Image.alpha_composite(composite, warped)
        composite = Image.alpha_composite(composite, overlay)

        bundle_dir = os.path.join(BUNDLE_ROOT, scene_id)
        os.makedirs(bundle_dir, exist_ok=True)
        scene_img.save(os.path.join(bundle_dir, "background.png"))
        overlay.save(os.path.join(bundle_dir, "overlay.png"))
        composite.convert("RGB").save(os.path.join(bundle_dir, "preview.png"))
        meta = {
            "scene": scene_id,
            "group_type": "primary",
            "orientation": "portrait",
            "aperture": [list(p) for p in quad],
            "size": list(scene_img.size),
            "tag": FLAT_TAG.get(scene_id, "lifestyle"),
        }
        with open(os.path.join(bundle_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        print(f"{scene_id}: quad={quad} -> {bundle_dir}")

    print("done")


if __name__ == "__main__":
    sys.exit(main())
