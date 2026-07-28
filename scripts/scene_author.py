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

    scene_author.py extract  <image.png> <scene_name> [--tag flat|lifestyle]
    scene_author.py reauthor [<scene_name>...]     # re-derive from scene.json
    scene_author.py verify   [<scene_name>...]
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
RIM_PX = 1.0                                        # quad margin past the matte, so the
                                                    # matte's anti-aliased rim sits on
                                                    # fully-covered art

MATTE_LO, MATTE_HI = 0.6, 1.0                       # x KEY_LAB_TOL: the anti-aliased rim
DESPILL_CAP = 4.0                                   # Lab units of key-direction chroma
                                                    # allowed to survive anywhere. Tighter
                                                    # values chase a +-6 G-R difference inside
                                                    # a shadow, which is inside the scene's own
                                                    # palette variation (its wall measures +4.3).
DESPILL_MAX_CHROMA = 20.0                           # above this a pixel is a real colour,
                                                    # not a tinted neutral - leave it alone
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


def _fill(mask: np.ndarray) -> np.ndarray:
    """`mask` with its enclosed holes filled."""
    out = mask.copy()
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(out, cnts, -1, 1, cv2.FILLED)
    return out


def _holes(mask: np.ndarray) -> np.ndarray:
    return (_fill(mask) & ~mask.astype(bool)).astype(bool)


def _prop_mask(rgb: np.ndarray, core: np.ndarray) -> np.ndarray:
    """Props lying over the print area - book spines, clip jaws, a plant leaf.

    Two separate tests, chroma OR darkness, carried over from attempt 2 because
    neither alone works: plain RGB distance also fires on the paper's own shadowed
    corner and punches a hole through the print, and a darkness threshold alone
    misses a clip's bright metal jaw. (attempt 1's black-blob and see-through-prop
    defects, respectively.)"""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = np.median(lab[core], axis=0)
    chroma = np.linalg.norm(lab[:, :, 1:] - ref[1:], axis=2)
    raw = ((chroma > 12) | (lab[:, :, 0] < 0.75 * ref[0])).astype(np.uint8)
    # open first: a few speckled pixels would otherwise become single-pixel holes
    # in the matte, which read as flat mid-alpha once anti-aliased (QA's
    # occluder-opacity test, 123 px on the seeded bookstack)
    return cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)


def seeded_matte(rgb: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Plan B, for a scene with no key: a coarse owner polygon used as a GrabCut
    seed and refined against the image itself. The polygon only has to be within
    several px - the photograph decides the actual edge, which is the whole point
    (attempts 1 and 2 both failed trying to hand-trace it to sub-pixel)."""
    h, w = rgb.shape[:2]
    inside = np.zeros((h, w), np.uint8)
    cv2.fillPoly(inside, [np.round(poly).astype(np.int32)], 1)
    k = np.ones((25, 25), np.uint8)
    core = cv2.erode(inside, np.ones((45, 45), np.uint8)).astype(bool)
    if not core.any():
        raise SystemExit("seed polygon too small to sample the print area from")
    props = _prop_mask(rgb, core)
    m = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    m[inside.astype(bool)] = cv2.GC_PR_FGD
    # a prop inside the seed must never become sure-foreground, or GrabCut learns
    # the book's colour as paper and the hole closes over the print
    m[(cv2.erode(inside, k) > 0) & ~props] = cv2.GC_FGD
    m[cv2.dilate(inside, k) == 0] = cv2.GC_BGD
    cv2.grabCut(rgb[:, :, ::-1].copy(), m, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 5, cv2.GC_INIT_WITH_MASK)
    fg = (((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)) & ~props).astype(np.uint8)
    # GrabCut leaves 1px slivers along an uncertain edge; feathered, they peak at
    # ~0.35 and read as a see-through patch of print (QA's occluder-opacity test).
    fg = cv2.morphologyEx(cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)),
                          cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # GrabCut settles a couple of px *inside* the object, which leaves a bright
    # sliver of bare board along the print's edge - the "lines on the edges" class
    # that was rejected twice. Grow the outer boundary to close it, but only the
    # outer one: dilating the holes too would print over a book's own edge.
    holes = _holes(fg)
    fg = (cv2.dilate(_fill(fg), np.ones((5, 5), np.uint8)) & ~holes).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:                                        # one print area, not confetti
        fg = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    return np.clip(cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 0.8), 0, 1)


def neutralise(rgb: np.ndarray, ref: np.ndarray, matte: np.ndarray) -> np.ndarray:
    """Drop the key's chroma wherever it reaches - inside the panel and in the
    spill ring around it - and keep every bit of luminance. The panel becomes the
    blank paper the scene was always meant to show, still carrying the scene's
    own light, and a partial-alpha edge pixel now blends art into paper."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    dist = np.linalg.norm(lab[:, :, 1:] - ref, axis=2)
    # Inside the panel: drop the chroma outright, keep every bit of luminance.
    spill = np.clip((2.5 * ss.KEY_LAB_TOL - dist) / ss.KEY_LAB_TOL, 0.0, 1.0)
    # Weighting by the matte itself was the bug behind the green hairline: at a
    # partial-matte pixel the background kept ~half its key chroma, and the art
    # composited over it at that same partial alpha, so the residue showed
    # through as a tinted line. The background has no reason to keep key chroma
    # anywhere the key reaches - it is meant to be blank paper - so neutralise
    # the matte's whole footprint, not a fraction of it. Luminance is untouched.
    w = np.maximum((matte > 0.02).astype(np.float32), spill)[:, :, None]
    lab[:, :, 1:] = lab[:, :, 1:] * (1 - w) + 128.0 * w

    # Around it: a directional despill. A distance threshold cannot catch a tint
    # that is only *slightly* toward the key - the panel's edge against a bright
    # prop lands 40-80 Lab units away and still reads as a green line (seen at 3x
    # on the shelf scene, and invisible to a fixed-distance spill test). Project
    # onto the key's own chroma direction and cap the positive part, so wood and
    # books are untouched. Confined to a ring so a real plant elsewhere in the
    # scene keeps its greens.
    k = ref - 128.0
    u = k / (np.linalg.norm(k) + 1e-6)
    ab = lab[:, :, 1:] - 128.0
    proj = ab @ u
    # Applied to the whole frame, not a ring: the key bounces light onto whatever
    # the panel is mounted on, and that cast covers far more than a few px (the
    # shelf scene's backing board read G-R +13 at 15px out and further). Confined
    # instead to *low-chroma* pixels - a tinted white board is spill, a green
    # leaf at full saturation is scene content and keeps its colour.
    chroma = np.linalg.norm(ab, axis=2)
    # Close to the panel, spill dominates whatever the pixel's own chroma is -
    # the sheet's cast shadow is both saturated and entirely bounce light. Far
    # from it, only near-neutral surfaces can be assumed tinted rather than
    # coloured, or a plant across the room loses its greens.
    near = cv2.dilate((matte > 0.02).astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
    spillable = (near | (chroma < DESPILL_MAX_CHROMA)) & (proj > DESPILL_CAP)
    excess = np.where(spillable, proj - DESPILL_CAP, 0.0)
    lab[:, :, 1:] = ab - excess[:, :, None] * u + 128.0
    return cv2.cvtColor(lab.clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


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
    """The matte's own corner quad, expanded just far enough to cover it.

    It used to also be expanded on its short axis until it matched the master's
    aspect, which was wrong in the way that is hardest to see: the art then
    filled a quad the matte was narrower than, and the matte trimmed the
    difference straight back off the design. That is not free - it is the same
    loss C3's cover-crop makes, taken silently on a path C3 does not watch, and
    it cost up to 13% of the design (GL-21 P3.5/F2). The aspect policy has one
    owner, and it is C3: leave the quad on the panel's real proportions, and let
    the compositor cover-crop the artwork onto it or fail loud past 2%.

    What remains is the coverage guarantee: push the edges out until every matte
    pixel is inside, plus one pixel so the matte's anti-aliased rim lands on
    fully-covered art rather than on the warp's own partial-alpha edge."""
    box, _ = ss._quad((matte > 0.5).astype(np.uint8))
    unit = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
    H = cv2.getPerspectiveTransform(unit, box.astype(np.float32))

    # The corner quad is a chord across every bowed edge, so a board with a
    # slightly curved top leaves an unprinted lip under it. Push each edge out in
    # the quad's *own* space until the whole matte is inside - measured, not
    # padded. (Caught by the QA coverage test on the seeded bookstack: 4439 px.)
    ys, xs = np.nonzero(matte > 0.5)
    uv = cv2.perspectiveTransform(
        np.stack([xs, ys], 1)[None].astype(np.float32), np.linalg.inv(H))[0]
    # A quantile, not the outright min/max: a single stray matte pixel - a spur of
    # contact shadow, a corner the shelf lip cuts off - would otherwise push a
    # whole edge out and take the quad's aspect with it (bookstack's bottom moved
    # 3%). Left outside instead, where the QA coverage test counts it against the
    # same budget this quantile is set from.
    q = mockup_qa.COVERAGE_TOL / 4                    # one share per edge
    lo, hi = np.quantile(uv, q, axis=0), np.quantile(uv, 1 - q, axis=0)
    e = [float(np.linalg.norm(box[i] - box[(i + 1) % 4])) for i in range(4)]
    pad = np.array([RIM_PX / ((e[0] + e[2]) / 2), RIM_PX / ((e[1] + e[3]) / 2)], np.float32)
    lo, hi = np.minimum(lo, 0) - pad, np.maximum(hi, 1) + pad
    cover = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]], np.float32)
    return cv2.perspectiveTransform(cover[None], H)[0].astype(np.float32)


def extract(image_path: Path, scene: str, tag: str, provenance: dict,
            seed_poly: np.ndarray = None) -> dict:
    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    h, w = rgb.shape[:2]
    if seed_poly is not None:
        matte, bg, ref = seeded_matte(rgb, seed_poly), rgb, None
    else:
        ref = ss.key_ref(rgb, provenance.get("key_rgb", (0, 177, 64)))
        matte = soft_matte(rgb, ref)
        bg = neutralise(rgb, ref, matte)          # keyed only: there is no key to remove
    g = gain_map(bg, matte)                       # from a seeded photo the paper is already blank
    quad = quad_for(matte)

    d = BUNDLES / scene
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bg).save(d / "background.png")
    Image.fromarray((matte * 255).round().astype(np.uint8)).save(d / "matte.png")
    # overlay = the gain map alone: black at (1-g) alpha. No repaint band, no
    # re-stamped props - both of those are the matte's job now.
    #
    # Masked by the matte, and that mask is not cosmetic. `gain_map` is a
    # normalised convolution: far from the panel the numerator vanishes, so g
    # clamps to GAIN_FLOOR and an unmasked overlay is a *full-frame* black wash
    # at alpha (1-GAIN_FLOOR) = 115/255. It repainted ~700k px of photograph per
    # scene, greyed every wall and drew a rounded halo around every print, and
    # the gate could not see it because all six detectors looked at the print.
    # The gain map only ever relights pixels the art covers, so outside the
    # matte it has nothing to do. (Caught by the GL-21 review; d_scene_fidelity.)
    overlay = np.dstack([np.zeros((h, w, 3), np.uint8),
                         ((1.0 - g) * matte * 255).round().clip(0, 255).astype(np.uint8)])
    Image.fromarray(overlay, "RGBA").save(d / "overlay.png")

    aspect = mr.quad_aspect(quad)
    # Measured off the master itself rather than from a hardcoded ratio - a
    # per-scene-constant-free tool has no business carrying one sample's pixel
    # dimensions as a product constant (GL-21 review §8.5).
    master = Image.open(mockup_qa.MASTER).convert("RGB")
    master_aspect = master.size[0] / master.size[1]
    _, crop = mr.cover_crop_to_aspect(master, aspect, max_crop=1.0)
    (d / "meta.json").write_text(json.dumps({
        "scene": scene, "group_type": "primary", "orientation": "portrait",
        "aperture": [[round(float(x), 1), round(float(y), 1)] for x, y in quad],
        "size": [w, h], "tag": tag, "overfill": 0.0,
    }, indent=2) + "\n")
    (d / "scene.json").write_text(json.dumps({
        **provenance, "scene": scene, "source_image": str(image_path),
        "mode": "seeded" if seed_poly is not None else "keyed",
        "seed_polygon": None if seed_poly is None else
                        [[round(float(x), 1), round(float(y), 1)] for x, y in seed_poly],
        "key_lab_ab": None if ref is None else [round(float(x), 2) for x in ref],
        "quad_aspect": round(aspect, 4),
        "aspect_delta": round(aspect / master_aspect - 1, 4),
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
        poly = None
        if "--seeded" in argv:
            # coarse owner polygon: 4 "x,y" points, or a bundle dir to lift an
            # existing hand-read aperture from. Several px of error is expected.
            src = argv[argv.index("--seeded") + 1]
            if Path(src).is_dir():
                poly = np.asarray(json.loads((Path(src) / "meta.json").read_text())["aperture"],
                                  np.float32)
            else:
                poly = np.asarray([[float(v) for v in p.split(",")]
                                   for p in src.split(";")], np.float32)
        print(json.dumps(extract(image_path, scene, tag,
                                 _provenance_for(image_path), poly), indent=2))
        return 0
    if cmd == "reauthor":
        # Re-derive bundles from what scene.json already records. A bundle is a
        # pure function of its source image plus this tool, so a fix in the tool
        # costs one command, not an authoring session - proved in the GL-21
        # review, where re-running extract reproduced all four byte-identical
        # except the one layer that had been wrong.
        for scene in argv[2:] or [d.name for d in sorted(BUNDLES.iterdir()) if d.is_dir()]:
            d = BUNDLES / scene
            sj = json.loads((d / "scene.json").read_text())
            src = ROOT / Path(sj["source_image"].replace("\\", "/"))
            poly = None if sj.get("seed_polygon") is None else np.asarray(sj["seed_polygon"],
                                                                         np.float32)
            print(json.dumps(extract(src, scene, json.loads((d / "meta.json").read_text())["tag"],
                                     _provenance_for(src), poly)))
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
