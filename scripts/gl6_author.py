"""GL-6 attempt-2 scene authoring tool (authoring-time only, not pipeline code).

Doctrine — docs/2026-07-24-gl6-attempt2-solution-plan.md §2: *the warped art must
never touch a photographed edge.*

  Mode I (INSET)  art quad strictly inside the photographed paper; the leftover
                  paper reads as a white margin / mat reveal. overlay = the
                  gain-map only.
  Mode O (OWN)    art quad expanded past the photographed paper; the overlay
                  restores the real photograph at alpha 255 outside a *synthetic*
                  paper edge and re-stamps the photographed occluders on top.

Either way the visible art boundary is never matched against a photographed
edge, so the annotation tolerance is ~±5px rather than ±0.5px. That is why the
`paper` quads below are hand-read off a labelled grid instead of traced: under
this doctrine precision is not what the composite depends on.

`margins` are fractions of the paper quad's own perspective space (left, top,
right, bottom); positive = inward (Mode I), negative = outward (Mode O). They
are chosen so the art quad's pixel aspect matches the master's (~0.684) —
`mockup_render` stretches the artwork onto the quad, so a mismatched quad
aspect would distort the print.

Usage:
    gl6_author.py selftest
    gl6_author.py preview [scene..]   # quad-on-background debug images
    gl6_author.py build   [scene..]   # write meta.json + overlay.png
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "assets" / "mockups" / "primary" / "portrait"
DEBUG = ROOT / "outputs" / "gl6_author"
ART_ASPECT = 6656 / 9728  # db/base_artwork/39.png

SCENES = {
    # --- flats: Mode O, the product must read full-bleed (plan §2 decision #1)
    "flat_clips_windowlight": dict(
        mode="O",
        paper=[[253, 331], [660, 333], [658, 940], [251, 936]],
        margins=(-0.027, -0.0197, -0.027, -0.0132),
        occluders=[(292, 294, 330, 378), (588, 294, 626, 378)],
        sigma=18, strength=1.0, floor=0.72,
    ),
    "flat_leaning_bookstack": dict(
        mode="O",
        paper=[[213, 219], [672, 214], [687, 911], [210, 915]],
        # asymmetric: the board leans back, so its top face is a parallelogram
        # whose back-right corner reaches ~(700,190) - past the front face's
        # (672,214). The right/top margins have to own that tab too, or it is
        # left outside the print as a stray sliver of photographed board.
        margins=(-0.036, -0.0455, -0.0655, -0.024),
        occluders=[(168, 886, 328, 962), (532, 872, 728, 962)],
        sigma=18, strength=1.0, floor=0.72,
    ),
    # --- lifestyle: Mode I, margins are styling not misrepresentation
    "lifestyle_bedroom_console": dict(
        mode="I",
        paper=[[300, 163], [657, 163], [655, 728], [301, 729]],
        margins=(0.032, 0.070, 0.032, 0.070),
        occluders=[], sigma=3, strength=0.85, floor=0.62,
    ),
    "lifestyle_sage_terracotta": dict(
        mode="I",
        paper=[[289, 266], [700, 264], [716, 986], [274, 982]],
        # side margin clears the faint inner-panel line photographed ~26px
        # inside the mat opening - the art must not land on it (doctrine §2)
        margins=(0.085, 0.1403, 0.085, 0.1403),
        occluders=[], sigma=2, strength=1.0, floor=0.55,
    ),
}

SS = 4          # polygon rasterisation supersample
EDGE_PX = 3.0   # synthetic print edge, inset far enough to bury the warp ringing
RING_PX = 8.0   # width of the photograph-restore band outside that edge


def sub_quad(paper: np.ndarray, margins) -> np.ndarray:
    """Map a sub-rectangle of the paper's own (u,v) space back to image pixels.

    Perspective-correct: uses the paper quad's homography, so on a leaning frame
    the margin stays visually even instead of shearing.
    """
    ml, mt, mr, mb = margins
    unit = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
    H = cv2.getPerspectiveTransform(unit, paper.astype(np.float32))
    box = np.array([[ml, mt], [1 - mr, mt], [1 - mr, 1 - mb], [ml, 1 - mb]], np.float32)
    return cv2.perspectiveTransform(box[None], H)[0].astype(np.float32)


def quad_aspect(q: np.ndarray) -> float:
    w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    return float(w / h)


def poly_alpha(quad: np.ndarray, size) -> np.ndarray:
    """Anti-aliased 0..1 coverage mask of `quad` at (W, H)."""
    w, h = size
    big = np.zeros((h * SS, w * SS), np.uint8)
    cv2.fillPoly(big, [np.round(quad * SS).astype(np.int32)], 255)
    return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def occluder_alpha(bg: np.ndarray, boxes, paper_a: np.ndarray) -> np.ndarray:
    """Alpha mask of props the photograph shows lying *over* the paper (clips,
    book spines). Mode O covers the whole paper, so these must be put back at
    full opacity or the art renders on top of them.

    A prop is either strongly off-white in *chroma* (brown book spines) or far
    darker than the paper (a clip's black body). Two separate tests, because
    neither alone works: plain RGB distance also fires on the paper's own
    shadowed bottom corner and punches a hole through the print, and a darkness
    threshold alone misses a clip's bright metal jaw (attempt 1's black-blob and
    see-through-prop defects respectively).
    """
    a = np.zeros(bg.shape[:2], np.float32)
    if not boxes:
        return a
    lab = cv2.cvtColor(bg, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = np.median(lab[paper_a > 0.9], axis=0)
    chroma = np.linalg.norm(lab[:, :, 1:] - ref[1:], axis=2)
    prop = (chroma > 12) | (lab[:, :, 0] < 0.75 * ref[0])
    for x0, y0, x1, y1 in boxes:
        m = prop[y0:y1, x0:x1].astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.dilate(m, np.ones((3, 3), np.uint8))
        a[y0:y1, x0:x1] = np.maximum(
            a[y0:y1, x0:x1], cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.9))
    return np.clip(a, 0, 1)


def gain_map(bg, paper_a, sigma, strength, floor) -> np.ndarray:
    """Per-pixel multiplicative relight derived from the blank insert itself, so
    the scene's real window-shadows fall across the art.

    Normalised convolution (blur the masked luminance, divide by the blurred
    mask) both smooths the insert and extrapolates the map a little past its
    edge — Mode O needs that, its quad sits outside the photographed paper.
    """
    lum = cv2.cvtColor(bg, cv2.COLOR_RGB2GRAY).astype(np.float32)
    m = (paper_a > 0.5).astype(np.float32)
    smooth = cv2.GaussianBlur(lum * m, (0, 0), sigma) / (cv2.GaussianBlur(m, (0, 0), sigma) + 1e-6)
    ref = float(np.percentile(lum[m > 0.5], 99.0))
    g = 1.0 - strength * (1.0 - np.clip(smooth / ref, 0.0, 1.0))
    return np.clip(g, floor, 1.0)


def over(dst_a, dst_c, src_a, src_c):
    """Straight-alpha 'src over dst'. a: HxW float 0..1, c: HxWx3 float."""
    a = src_a + dst_a * (1.0 - src_a)
    c = src_c * src_a[..., None] + dst_c * dst_a[..., None] * (1.0 - src_a[..., None])
    return a, c / np.maximum(a, 1e-6)[..., None]


def load_bg(scene: str) -> np.ndarray:
    return cv2.cvtColor(cv2.imread(str(BUNDLES / scene / "background.png")), cv2.COLOR_BGR2RGB)


def quads(scene: str, cfg: dict):
    paper = np.asarray(cfg["paper"], np.float32)
    return paper, sub_quad(paper, cfg["margins"])


def shrink(q: np.ndarray, px: float) -> np.ndarray:
    """Offset every edge of `q` inward by `px` pixels (negative = outward)."""
    w = np.linalg.norm(q[1] - q[0])
    h = np.linalg.norm(q[3] - q[0])
    return sub_quad(q, (px / w, px / h, px / w, px / h))


def build(scene: str, cfg: dict) -> dict:
    d = BUNDLES / scene
    bg = load_bg(scene)
    h, w = bg.shape[:2]
    paper, art_q = quads(scene, cfg)

    paper_a = poly_alpha(paper, (w, h))
    occ = occluder_alpha(bg, cfg["occluders"], paper_a)
    g = gain_map(bg, np.clip(paper_a - occ, 0, 1), cfg["sigma"], cfg["strength"], cfg["floor"])
    bgf = bg.astype(np.float32)

    # The print's visible boundary is drawn here, not left to the warp.
    # mockup_render warps with INTER_CUBIC, which rings at the artwork border: a
    # bright overshoot then a ~1px dark undershoot, composited wherever the warp
    # mask is still non-zero. Against a bright mat that reads as a dark hairline
    # around the print - a real part of attempt 1's "lines on the edges".
    # mockup_render is frozen (GL-19), so the fix is bundle-side: paint a band of
    # the real photograph back over the art's outer EDGE_PX, so the edge the
    # viewer sees is this mask, anti-aliased once, and the ringing is buried
    # under it. Same construction in both modes - only the margins differ.
    edge_a = poly_alpha(shrink(art_q, EDGE_PX), (w, h))
    ring_a = poly_alpha(shrink(art_q, -RING_PX), (w, h))

    a, c = edge_a * (1.0 - g), np.zeros((h, w, 3), np.float32)      # gain tint
    a, c = over(a, c, np.clip(ring_a - edge_a, 0, 1), bgf)          # synthetic print edge
    a, c = over(a, c, occ, bgf)                                     # props back on top

    rgba = np.dstack([np.clip(c, 0, 255), np.clip(a * 255.0, 0, 255)]).astype(np.uint8)
    cv2.imwrite(str(d / "overlay.png"), cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))

    meta = json.loads((d / "meta.json").read_text())
    meta["aperture"] = [[round(float(x), 1), round(float(y), 1)] for x, y in art_q]
    meta["overfill"] = 0.0
    (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return dict(scene=scene, mode=cfg["mode"], aspect=round(quad_aspect(art_q), 4),
                aperture=meta["aperture"])


def preview(scene: str, cfg: dict):
    DEBUG.mkdir(parents=True, exist_ok=True)
    bg = load_bg(scene)
    paper, art_q = quads(scene, cfg)
    vis = bg.copy()
    cv2.polylines(vis, [paper.astype(np.int32)], True, (0, 90, 255), 2)      # photographed paper
    cv2.polylines(vis, [art_q.astype(np.int32)], True, (0, 220, 0), 2)       # art quad
    for x0, y0, x1, y1 in cfg["occluders"]:
        cv2.rectangle(vis, (x0, y0), (x1, y1), (255, 0, 255), 1)
    cv2.imwrite(str(DEBUG / f"{scene}_quad.png"), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    print(f"{scene:28} mode={cfg['mode']} art_aspect={quad_aspect(art_q):.4f} "
          f"(master {ART_ASPECT:.4f})")


def _selftest():
    """Smallest check on the two non-obvious bits: the perspective sub-quad and
    the alpha-over combine."""
    sq = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], np.float32)
    got = sub_quad(sq, (0.1, 0.1, 0.1, 0.1))
    assert np.allclose(got, [[10, 10], [90, 10], [90, 90], [10, 90]], atol=1e-3), got
    out = sub_quad(sq, (-0.1, -0.1, -0.1, -0.1))
    assert np.allclose(out, [[-10, -10], [110, -10], [110, 110], [-10, 110]], atol=1e-3), out
    assert abs(quad_aspect(sq) - 1.0) < 1e-6
    a1, c1 = np.array([[0.4]]), np.zeros((1, 1, 3), np.float32)
    a, c = over(a1, c1, np.array([[1.0]]), np.full((1, 1, 3), 200.0, np.float32))
    assert np.allclose(a, 1.0) and np.allclose(c, 200.0), (a, c)
    a, c = over(a1, c1, np.array([[0.0]]), np.full((1, 1, 3), 200.0, np.float32))
    assert np.allclose(a, 0.4) and np.allclose(c, 0.0), (a, c)
    print("selftest OK")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    names = sys.argv[2:] or list(SCENES)
    if cmd == "selftest":
        _selftest()
    elif cmd == "preview":
        for n in names:
            preview(n, SCENES[n])
    elif cmd == "build":
        for n in names:
            print(json.dumps(build(n, SCENES[n])))
    else:
        raise SystemExit(__doc__)
