"""GL-6 attempt-3 scene authoring tool (authoring-time only, not pipeline code).

Replaces `scripts/gl6_author.py`, whose four hand-read paper quads, four margin
tuples and four occluder-box lists are the thing that failed twice and the thing
that cannot reach ~26 bundles. **There are no per-scene constants in this file.**
Every number a bundle needs is derived from its own image:

    extract   key matte (Lab distance to the key measured off the image, not
              assumed) -> anti-aliased matte with the occluders already as holes
              -> background with the key neutralised (chroma dropped, luminance
              kept, so partial-alpha edges blend into paper rather than green)
              -> gain map -> quad = the matte's corner quad expanded on its short
              axis to the master's aspect
    verify    scripts/mockup_qa.py - nothing reaches the owner unless it passes
    build     writes background.png, matte.png, overlay.png, meta.json and
              scene.json (model, prompt, seed, key colour, quad, aspect delta,
              crop %)

The overlay carries the gain map and nothing else: no repaint band, no stamped-
back occluders. The matte handles both, per pixel (GL-21 C2).

    scene_author.py extract <image.png> <scene_name> [--tag flat|lifestyle]
    scene_author.py verify  <scene_name>
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mockup_qa                                    # noqa: E402
import scene_screen as ss                           # noqa: E402
import pipeline.mockup_render as mr                 # noqa: E402

BUNDLES = ROOT / "assets" / "mockups" / "primary" / "portrait"
MASTER_ASPECT = 6656 / 9728                         # db/base_artwork/39.png

MATTE_LO, MATTE_HI = 0.6, 1.0                       # x KEY_LAB_TOL: the anti-aliased rim
GAIN_SIGMA, GAIN_STRENGTH, GAIN_FLOOR = 12.0, 0.9, 0.55


def soft_matte(rgb: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """0..1 coverage: 1 deep in the key, 0 outside it, anti-aliased across the
    photograph's own edge gradient - so the matte inherits the real edge softness
    instead of a drawn one. Occluders need no special case: a clip jaw is simply
    not the key, so it is already a hole."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    dist = np.linalg.norm(lab[:, :, 1:] - ref, axis=2)
    lo, hi = MATTE_LO * ss.KEY_LAB_TOL, MATTE_HI * ss.KEY_LAB_TOL
    a = np.clip((hi - dist) / (hi - lo), 0.0, 1.0)
    keep = ss.panel(ss.key_mask(rgb, ref))[0]       # largest key region only
    if keep is None:
        raise SystemExit("no key region found - is this a keyed scene?")
    near = cv2.dilate(keep, np.ones((7, 7), np.uint8)).astype(bool)
    return np.where(near, a, 0.0).astype(np.float32)


def neutralise(rgb: np.ndarray, ref: np.ndarray, matte: np.ndarray) -> np.ndarray:
    """Drop the key's chroma wherever it reaches - inside the panel and in the
    spill ring around it - and keep every bit of luminance. The panel becomes the
    blank paper the scene was always meant to show, still carrying the scene's
    own light, and a partial-alpha edge pixel now blends art into paper."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    dist = np.linalg.norm(lab[:, :, 1:] - ref, axis=2)
    # Full removal well past the key threshold, feathering only after that. A
    # narrow despill leaves a rim of half-neutralised green exactly where the
    # matte is partial, and that rim reads as a green outline around the print -
    # caught on the P0 probe's full-frame check, invisible in the metrics.
    spill = np.clip((2.5 * ss.KEY_LAB_TOL - dist) / ss.KEY_LAB_TOL, 0.0, 1.0)
    w = np.maximum(matte, spill)[:, :, None]
    lab[:, :, 1:] = lab[:, :, 1:] * (1 - w) + 128.0 * w
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)


def gain_map(bg: np.ndarray, matte: np.ndarray) -> np.ndarray:
    """Per-pixel multiplicative relight taken from the panel itself, so the
    scene's real shadows fall across the print. Normalised convolution (blur the
    masked luminance, divide by the blurred mask) both smooths it and extends it
    a little past the panel edge. Kept from attempt 2 - this part worked."""
    lum = cv2.cvtColor(bg, cv2.COLOR_RGB2GRAY).astype(np.float32)
    m = (matte > 0.5).astype(np.float32)
    smooth = (cv2.GaussianBlur(lum * m, (0, 0), GAIN_SIGMA)
              / (cv2.GaussianBlur(m, (0, 0), GAIN_SIGMA) + 1e-6))
    ref = float(np.percentile(lum[m > 0.5], 99.0))
    g = 1.0 - GAIN_STRENGTH * (1.0 - np.clip(smooth / ref, 0.0, 1.0))
    return np.clip(g, GAIN_FLOOR, 1.0)


def quad_for(matte: np.ndarray) -> np.ndarray:
    """The matte's own corner quad, expanded on its short axis until it matches
    the master's aspect. The art is projected onto this; what is *seen* is the
    matte, so the expansion only guarantees coverage under the anti-aliased rim -
    it can never show as a border, which is what `overfill` used to be for."""
    box, _ = ss._quad((matte > 0.5).astype(np.uint8))
    e = [float(np.linalg.norm(box[i] - box[(i + 1) % 4])) for i in range(4)]
    aspect = ((e[0] + e[2]) / 2) / ((e[1] + e[3]) / 2)
    unit = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
    H = cv2.getPerspectiveTransform(unit, box.astype(np.float32))
    if aspect < MASTER_ASPECT:                       # too narrow: widen
        m = (MASTER_ASPECT / aspect - 1) / 2
        sub = np.array([[-m, 0], [1 + m, 0], [1 + m, 1], [-m, 1]], np.float32)
    else:                                            # too wide: heighten
        m = (aspect / MASTER_ASPECT - 1) / 2
        sub = np.array([[0, -m], [1, -m], [1, 1 + m], [0, 1 + m]], np.float32)
    return cv2.perspectiveTransform(sub[None], H)[0].astype(np.float32)


def extract(image_path: Path, scene: str, tag: str, provenance: dict) -> dict:
    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    h, w = rgb.shape[:2]
    ref = ss.key_ref(rgb, provenance.get("key_rgb", (0, 177, 64)))
    matte = soft_matte(rgb, ref)
    bg = neutralise(rgb, ref, matte)
    g = gain_map(bg, matte)
    quad = quad_for(matte)

    d = BUNDLES / scene
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bg).save(d / "background.png")
    Image.fromarray((matte * 255).round().astype(np.uint8)).save(d / "matte.png")
    # overlay = the gain map alone: black at (1-g) alpha. No repaint band, no
    # re-stamped props - both of those are the matte's job now.
    overlay = np.dstack([np.zeros((h, w, 3), np.uint8),
                         ((1.0 - g) * 255).round().clip(0, 255).astype(np.uint8)])
    Image.fromarray(overlay, "RGBA").save(d / "overlay.png")

    aspect = mr.quad_aspect(quad)
    _, crop = mr.cover_crop_to_aspect(Image.open(mockup_qa.MASTER).convert("RGB"),
                                      aspect, max_crop=1.0)
    (d / "meta.json").write_text(json.dumps({
        "scene": scene, "group_type": "primary", "orientation": "portrait",
        "aperture": [[round(float(x), 1), round(float(y), 1)] for x, y in quad],
        "size": [w, h], "tag": tag, "overfill": 0.0,
    }, indent=2) + "\n")
    (d / "scene.json").write_text(json.dumps({
        **provenance, "scene": scene, "source_image": str(image_path),
        "key_lab_ab": [round(float(x), 2) for x in ref],
        "quad_aspect": round(aspect, 4),
        "aspect_delta": round(aspect / MASTER_ASPECT - 1, 4),
        "cover_crop": round(crop, 4),
        "matte_coverage": round(float((matte > 0.5).mean()), 4),
    }, indent=2) + "\n")
    return dict(scene=scene, aspect=round(aspect, 4), crop=round(crop, 4), dir=str(d))


def _provenance_for(image_path: Path) -> dict:
    """Carry the generation manifest's model/prompt/seed/key into scene.json, so
    a bundle can always be traced back to the call that made it."""
    mani = image_path.parent / "manifest.json"
    if not mani.exists():
        return {}
    m = json.loads(mani.read_text())
    job = next((j for j in m["jobs"] if j.get("path") and Path(j["path"]).name == image_path.name), {})
    return {k: job.get(k) for k in ("prompt", "seed", "key", "key_rgb")} | {
        "model": m["model"], "licence": m["licence"],
        "aspect_ratio": m["aspect_ratio"], "megapixels": m["megapixels"]}


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "verify"
    if cmd == "extract":
        image_path, scene = Path(argv[2]), argv[3]
        tag = argv[argv.index("--tag") + 1] if "--tag" in argv else (
            "flat" if scene.startswith("flat") else "lifestyle")
        print(json.dumps(extract(image_path, scene, tag, _provenance_for(image_path)), indent=2))
        return 0
    if cmd == "verify":
        art = Image.open(mockup_qa.MASTER).convert("RGB")
        ok = True
        for scene in argv[2:] or [d.name for d in sorted(BUNDLES.iterdir()) if d.is_dir()]:
            r = mockup_qa.check(BUNDLES / scene, art)
            ok &= r["passed"]
            print(f"\n{scene}  [{'PASS' if r['passed'] else 'FAIL'}]")
            for f in r["findings"]:
                print(f"  {'ok  ' if f['passed'] else 'FAIL'} {f['name']:20} {f['detail']}")
            print(f"  -> {mockup_qa.contact_sheet(r, mockup_qa.SHEET_DIR / f'{scene}.png')}")
        return 0 if ok else 1
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
