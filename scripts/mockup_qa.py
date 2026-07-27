"""GL-21 automated mockup defect gate (docs/2026-07-26-gl6-attempt3-production-
readiness-plan.md §3.4). Authoring-time only, not pipeline code.

Six detectors, each aimed at a defect that shipped past a human review:

  fringe              the artwork border must blend between art and background -
                      no dark hairline (pre-C1 BORDER_CONSTANT), no bright band
                      (attempt 2's bundle-side repaint)
  key-spill           no residual key chroma left anywhere in the composite
  distortion          quad aspect vs artwork aspect, and the cover-crop it costs
  coverage            print area fully covered, no visible art outside it
                      (attempt 2's occluder-box notches, Mode-O floor spill)
  occluder-opacity    holes are 0 or 1 apart from anti-aliasing (attempt 1's
                      alpha-172 see-through clips and book spines)
  silhouette-vs-shadow  the photographed object's silhouette and the print's
                      silhouette must not disagree *unevenly* - a constant
                      margin is styling, a bowing gap is a curled-paper mismatch

`demo` re-runs every detector against a bundle that is known to carry its
defect: a detector that cannot see a known defect is not a detector.

Usage:
    mockup_qa.py check <bundle_dir> [<bundle_dir>...] [--art PATH]
    mockup_qa.py sheet <bundle_dir> [<bundle_dir>...] [--art PATH] [--out DIR]
    mockup_qa.py demo
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pipeline.mockup_render as mr  # noqa: E402

MASTER = ROOT / "db" / "base_artwork" / "39.png"      # candidate 39, the approved master
SHEET_DIR = ROOT / "outputs" / "mockup_qa"

FRINGE_RADIUS = 10      # px either side of the art boundary that counts as "the edge"
FRINGE_TOL = 24         # 0-255. A supersampled edge downsampled by INTER_AREA can
                        # legitimately land ~20 outside its interior's local range;
                        # the defect class this guards (BORDER_CONSTANT) is ~120.
ASPECT_TOL = 0.01       # |quad aspect / art aspect - 1|
MATTE_CROP_TOL = 0.08   # how much of the print a matte may hide. A frame rebate
                        # really does cover a few mm; sage's 0.59 mat opening
                        # against a 0.684 master hid 18%, which is defect (d).
SPILL_TOL = 32          # Lab a/b distance under which a pixel still reads as the key.
                        # Must match the extractor's own key tolerance: at 20 this
                        # test passed a composite with a visible green rim, because
                        # the rim's residue sat between the two thresholds.
SPILL_PROJ_MAX = 8.0    # Lab units of key-direction chroma tolerated on the print's
                        # own edge band - above this it reads as a coloured hairline
SPILL_BAND_BUDGET = 0.001  # x the band's own size: an occluder's real colour shows at
                        # the rim of its hole, and that is scene content, not residue
PLATEAU_TOL = 0.05      # alpha within this of 0/1 counts as hard
PLATEAU_BUDGET = 0.01   # x the matte's perimeter: a matte derived from a photograph's
                        # own edge gradient leaves a few soft px on it. Attempt 1's
                        # alpha-172 stamps are ~10x this and nowhere near an edge.
EDGE_MIN = 20.0         # Sobel magnitude that counts as a real photographic edge
FLOATING_MAX = 0.10     # fraction of the print boundary allowed to sit on no edge at
                        # all (corners, occluder junctions). Derived mattes measure
                        # 0.00-0.03; every hand-drawn quad from attempts 1-2, 0.74-1.00.
COVERAGE_TOL = 0.0005   # fraction of the print area allowed to read as un-printed:
                        # an anti-aliased rim always leaves a few px indistinguishable
                        # from the background. Attempt 2's occluder notches were 5.1%.


# --------------------------------------------------------------------------- parts

def _parts(bundle: mr.SceneBundle, art: Image.Image) -> dict:
    """Re-derive every layer render_scene builds, without C3's hard limit - QA
    has to be able to measure a bundle that the compositor would refuse."""
    quad = mr._overfill_quad(bundle.aperture, bundle.overfill)
    aspect = mr.quad_aspect(quad)
    cropped, crop = mr.cover_crop_to_aspect(art, aspect, max_crop=1.0)
    rgba = np.array(mr._warp_into_quad(cropped, bundle.size, quad)).astype(np.float32)
    raw_a = rgba[:, :, 3] / 255.0
    if bundle.matte is not None:
        rgba[:, :, 3] *= bundle.matte
    warped = Image.fromarray(rgba.round().clip(0, 255).astype(np.uint8), "RGBA")
    bg = bundle.background.copy()
    comp = Image.alpha_composite(Image.alpha_composite(bg, warped), bundle.overlay)
    bare = Image.alpha_composite(bg.copy(), bundle.overlay)
    return dict(
        quad=quad, aspect=aspect, crop=crop, art_aspect=art.size[0] / art.size[1],
        art_a=rgba[:, :, 3] / 255.0, raw_a=raw_a, art_rgb=rgba[:, :, :3],
        comp=np.asarray(comp.convert("RGB"), np.float32),
        bare=np.asarray(bare.convert("RGB"), np.float32),
        bg=np.asarray(bundle.background.convert("RGB"), np.float32),
        size=bundle.size, matte=bundle.matte, overlay_a=np.asarray(
            bundle.overlay.convert("RGBA"), np.float32)[:, :, 3] / 255.0,
    )


def _poly_a(quad: np.ndarray, size, ss=4) -> np.ndarray:
    w, h = size
    big = np.zeros((h * ss, w * ss), np.uint8)
    cv2.fillPoly(big, [np.round(quad * ss).astype(np.int32)], 255)
    return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _print_region(p: dict) -> np.ndarray:
    """Where the print is *supposed* to be visible: the matte if the bundle has
    one, otherwise the art quad (which is all a pre-matte bundle declares)."""
    m = p["matte"] if p["matte"] is not None else _poly_a(p["quad"], p["size"])
    return m > 0.5


def _min_cluster(mask: np.ndarray, min_area=3) -> np.ndarray:
    """Drop connected components smaller than `min_area`."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[lab]


def _corner_mask(p: dict, r=FRINGE_RADIUS) -> np.ndarray:
    """The four quad corners, where "the range this edge's own interior spans"
    is ill-defined (two edges meet and the local window straddles both)."""
    m = np.zeros(p["art_a"].shape, np.uint8)
    for x, y in p["quad"]:
        cv2.circle(m, (int(round(x)), int(round(y))), r, 1, -1)
    return m.astype(bool)


def _finding(name, passed, metric, detail):
    return dict(name=name, passed=bool(passed), metric=metric, detail=detail)


# --------------------------------------------------------------------------- detectors

def _mask_extremes(img: np.ndarray, mask: np.ndarray, k: np.ndarray):
    """Local min/max of `img` over `k`, sampling only where `mask` is set."""
    m3 = np.repeat(mask[:, :, None].astype(np.float32), img.shape[2], axis=2)
    lo = cv2.erode(np.where(m3 > 0, img, 255.0), k)
    hi = cv2.dilate(np.where(m3 > 0, img, 0.0), k)
    seen = cv2.dilate(mask.astype(np.uint8), k).astype(bool)
    return lo, hi, seen


def d_fringe(p: dict) -> dict:
    """Two things at every partial-coverage border pixel:

    (a) the warped *art* colour there must still be the artwork's own colour -
        i.e. within the range its fully-covered neighbours span. This is the C1
        test: BORDER_CONSTANT=0 drags the border toward black, so the operand is
        already wrong before any compositing happens, and a test on the
        composite alone can never see it (a blend toward a black operand still
        lies "between" that operand and the background).
    (b) the composite must land between that art colour and the background -
        the blend itself must not overshoot.
    """
    a, comp, art, bg = p["art_a"], p["comp"], p["art_rgb"], p["bg"]
    raw = p["raw_a"]
    corner = _corner_mask(p)
    # (a) is about the *warp* border only. A matte rim also produces partial
    # alpha, but it cannot alter the art's colour - it only decides how much of
    # it shows - so including it just flags any matte edge that happens to cross
    # a high-contrast part of the artwork.
    edge_a = (raw > 0.02) & (raw < 0.98) & ~corner
    edge_b = (a > 0.02) & (a < 0.98) & ~corner
    k = np.ones((2 * FRINGE_RADIUS + 3,) * 2, np.uint8)
    lo, hi, seen = _mask_extremes(art, raw > 0.98, k)
    excess_a = np.maximum(art - (hi + FRINGE_TOL), (lo - FRINGE_TOL) - art).max(axis=2)
    bad_a = edge_a & seen & (excess_a > 0)
    edge = edge_b
    clear = p["overlay_a"] < 0.02                       # the overlay is allowed to repaint
    blend_lo, blend_hi = np.minimum(art, bg), np.maximum(art, bg)
    excess_b = np.maximum(comp - (blend_hi + FRINGE_TOL), (blend_lo - FRINGE_TOL) - comp).max(axis=2)
    bad_b = edge & clear & (excess_b > 0)
    # a real hairline is a continuous ring; a lone pixel is resampling noise
    bad_a, bad_b = _min_cluster(bad_a), _min_cluster(bad_b)
    n = int(bad_a.sum()) + int(bad_b.sum())
    worst = max(excess_a[bad_a].max() if bad_a.any() else 0,
                excess_b[bad_b].max() if bad_b.any() else 0)
    return _finding("fringe", n == 0, n,
                    f"{int(bad_a.sum())} border px whose art colour is off its own edge, "
                    f"{int(bad_b.sum())} px whose blend overshoots (max {worst:.0f}/255)" if n else
                    f"{int(edge.sum())} border px clean")


def d_key_spill(p: dict, key_rgb) -> dict:
    """No residual key chroma anywhere in the composite, and no key-direction
    *tint* on the print's own edge - which is the form the defect actually takes.
    A fixed distance-to-key test passes a visible green line, because the line
    sits 40-80 Lab units away: it is a partial tint, not the key itself."""
    if key_rgb is None:
        return _finding("key-spill", True, None, "n/a - bundle declares no key colour")
    lab = cv2.cvtColor(p["comp"].astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = cv2.cvtColor(np.uint8([[key_rgb]]), cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0, 1:]
    n = int((np.linalg.norm(lab[:, :, 1:] - ref, axis=2) < SPILL_TOL).sum())
    # measured on the *background*, not the composite: the master's own green
    # stems project onto an emerald key just as hard as residue does, and they
    # are the artwork, not spill. The background under the print is meant to be
    # blank paper, so any key-direction chroma there is residue by construction.
    bg_lab = cv2.cvtColor(p["bg"].astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    u = (ref - 128.0) / (np.linalg.norm(ref - 128.0) + 1e-6)
    proj = (bg_lab[:, :, 1:] - 128.0) @ u
    region = _print_region(p).astype(np.uint8)
    band = (cv2.dilate(region, np.ones((9, 9), np.uint8))
            - cv2.erode(region, np.ones((9, 9), np.uint8))).astype(bool)
    tinted = int((band & (proj > SPILL_PROJ_MAX)).sum())
    budget = int(SPILL_BAND_BUDGET * max(band.sum(), 1))
    return _finding("key-spill", n == 0 and tinted <= budget, n + tinted,
                    f"{n} px within {SPILL_TOL} Lab-ab of key {key_rgb}, "
                    f"{tinted} px of key-direction tint on the print edge (budget {budget})")


def d_distortion(p: dict) -> dict:
    """The print must not be stretched, and the matte must not hide so much of it
    that the buyer is shown a different crop than the one they receive.

    A frame's rebate really does cover a few mm of a print, so a small matte crop
    is physical, not dishonest. Sage's 0.59 mat opening against a 0.684 master
    was 18% - that is a differently-shaped opening, and it is defect (d)."""
    delta = abs(p["aspect"] / p["art_aspect"] - 1)
    region = _print_region(p)
    detail = (f"quad {p['aspect']:.4f} vs art {p['art_aspect']:.4f} "
              f"= {delta:.2%} off, cover-crop {p['crop']:.2%}")
    hidden = 0.0
    if region.any():
        box, _ = _region_quad(region)
        e = [float(np.linalg.norm(box[i] - box[(i + 1) % 4])) for i in range(4)]
        if min(e) > 4:
            m_aspect = ((e[0] + e[2]) / 2) / ((e[1] + e[3]) / 2)
            hidden = 1 - min(m_aspect, p["aspect"]) / max(m_aspect, p["aspect"])
            detail += f", matte {m_aspect:.4f} hides {hidden:.1%} of the print"
    return _finding("distortion", delta <= ASPECT_TOL and hidden <= MATTE_CROP_TOL,
                    round(delta, 5), detail)


def _region_quad(region: np.ndarray):
    """Corner quad of a mask, TL TR BR BL (its own extremes, so perspective and
    curl survive - the same derivation scene_author uses)."""
    cnt = max(cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    q = cnt.reshape(-1, 2).astype(np.float32)
    s, d = q.sum(1), q[:, 0] - q[:, 1]
    return np.stack([q[s.argmin()], q[d.argmax()], q[s.argmax()], q[d.argmin()]]), cnt


def d_coverage(p: dict) -> dict:
    """The print area must be fully printed, and nothing may print outside it.
    Fires on attempt 2's occluder-box notches (print area showing background)
    and on Mode-O spill past the paper."""
    # Measured from alpha, not from "does the composite differ from the bare
    # scene": on a white-walled scene the artwork's own pale background is
    # pixel-identical to the blank paper it prints onto, and a difference test
    # calls thousands of correctly-printed px unprinted (3101 on bedroom_console).
    region = _print_region(p)
    inner = cv2.erode(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    outer = cv2.dilate(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    uncovered = int((inner & ((p["raw_a"] < 0.5) | (p["overlay_a"] > 0.5))).sum())
    outside = int(((p["art_a"] > 0.5) & ~outer).sum())
    n = uncovered + outside
    budget = int(COVERAGE_TOL * max(region.sum(), 1))
    return _finding("coverage", n <= budget, n,
                    f"{uncovered} px of print area not printed, {outside} px of art outside it "
                    f"(budget {budget})")


def d_occluder_opacity(p: dict) -> dict:
    """Holes must be hard: 0 or 1 apart from the anti-aliased rim. A plateau of
    mid alpha is attempt 1's see-through clip (alpha 172) - it reads as a ghost.

    Matte-only by construction: in a pre-matte bundle the same channel also
    carries the gain map, and no threshold cleanly separates a smooth relight
    field from a badly-stamped prop. That ambiguity is exactly what the matte
    primitive removes."""
    if p["matte"] is None:
        return _finding("occluder-opacity", True, None, "n/a - pre-matte bundle, no matte to check")
    src = p["matte"]
    mid = (src > PLATEAU_TOL) & (src < 1 - PLATEAU_TOL)
    k = np.ones((5, 5), np.uint8)
    near0 = cv2.dilate((src <= PLATEAU_TOL).astype(np.uint8), k).astype(bool)
    near1 = cv2.dilate((src >= 1 - PLATEAU_TOL).astype(np.uint8), k).astype(bool)
    plateau = mid & ~(near0 & near1)          # partial, but not on a 0<->1 rim
    n = int(plateau.sum())
    perim = sum(cv2.arcLength(c, True) for c in
                cv2.findContours((src > 0.5).astype(np.uint8),
                                 cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0])
    budget = int(PLATEAU_BUDGET * perim)
    return _finding("occluder-opacity", n <= budget, n,
                    f"{n} px of flat mid-alpha ({src[plateau].mean():.2f} mean, budget {budget})" if n
                    else f"{int(mid.sum())} partial px, all on anti-aliased rims")


def d_silhouette_vs_shadow(p: dict) -> dict:
    """The print's silhouette must lie on the photographed object's own edge.

    Under the matte primitive this is the sharp form of "silhouette vs shadow".
    A matte derived from the image - a key boundary, or GrabCut snapped to the
    board - sits on a real photographic edge by construction, and the shadow
    FLUX drew belongs to that same silhouette. A boundary running through flat,
    edgeless pixels means the region was *drawn*, not derived: attempt 2's clips
    quad crossing blank curled paper (defect (a)), its bookstack quad running out
    onto the floor, and its bedroom_console quad sitting in the middle of a flat
    mat. Measured as the fraction of the print boundary with no gradient within
    2px; derived bundles score 0.00-0.03, every hand-drawn one 0.74-1.00.
    """
    region = _print_region(p).astype(np.uint8)
    if not region.any():
        return _finding("silhouette-vs-shadow", False, None, "no print region")
    boundary = (region - cv2.erode(region, np.ones((3, 3), np.uint8))).astype(bool)
    gray = cv2.cvtColor(p["bg"].astype(np.uint8), cv2.COLOR_RGB2GRAY)
    grad = np.hypot(cv2.Sobel(gray, cv2.CV_32F, 1, 0, 3), cv2.Sobel(gray, cv2.CV_32F, 0, 1, 3))
    grad = cv2.dilate(grad, np.ones((5, 5), np.uint8))          # strongest edge within 2px
    floating = float((grad[boundary] < EDGE_MIN).mean())
    return _finding("silhouette-vs-shadow", floating <= FLOATING_MAX, round(floating, 3),
                    f"{floating:.1%} of the print boundary sits on no photographic edge "
                    f"(limit {FLOATING_MAX:.0%})")


DETECTORS = ["fringe", "key-spill", "distortion", "coverage",
             "occluder-opacity", "silhouette-vs-shadow"]


def check(bundle_dir: Path, art: Image.Image) -> dict:
    bundle_dir = Path(bundle_dir)
    bundle = mr.load_bundle(bundle_dir)
    p = _parts(bundle, art)
    prov = bundle_dir / "scene.json"
    key = json.loads(prov.read_text()).get("key_rgb") if prov.exists() else None
    findings = [d_fringe(p), d_key_spill(p, key), d_distortion(p), d_coverage(p),
                d_occluder_opacity(p), d_silhouette_vs_shadow(p)]
    return dict(scene=bundle.scene, dir=str(bundle_dir), findings=findings,
                passed=all(f["passed"] for f in findings), parts=p)


# --------------------------------------------------------------------------- contact sheet

def contact_sheet(result: dict, out_path: Path, scale=3, crop=110, strip=26):
    """Full frame + the four print corners at `scale` + a 1-px strip lifted off
    each print edge. The owner reviews this, never a bare crop (attempt-1 lesson:
    crops alone signed off four bad scenes)."""
    comp = Image.fromarray(result["parts"]["comp"].astype(np.uint8))
    quad = result["parts"]["quad"]
    W = max(comp.width, 4 * crop * scale + 5 * 8)
    corners = [comp.crop(_box(pt, crop, comp.size)).resize((crop * scale,) * 2, Image.NEAREST)
               for pt in quad]
    strips = [_edge_strip(comp, quad, i, W - 16, strip) for i in range(4)]
    H = comp.height + 30 + crop * scale + 24 + len(strips) * (strip + 18) + 40
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    sheet.paste(comp, ((W - comp.width) // 2, 8))
    y = comp.height + 16
    dr.text((8, y), f"{result['scene']} - {'PASS' if result['passed'] else 'FAIL'}", (240, 240, 240))
    y += 14
    for i, c in enumerate(corners):
        sheet.paste(c, (8 + i * (crop * scale + 8), y))
    dr.text((8, y + crop * scale + 4), "print corners @%dx (TL TR BR BL)" % scale, (200, 200, 200))
    y += crop * scale + 20
    for name, s in zip(("top", "right", "bottom", "left"), strips):
        sheet.paste(s, (8, y))
        dr.text((8, y + strip + 2), f"1px strip along {name} edge", (200, 200, 200))
        y += strip + 18
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def _box(pt, crop, size):
    x, y = int(pt[0]), int(pt[1])
    h = crop // 2
    x = min(max(x, h), size[0] - h - 1)
    y = min(max(y, h), size[1] - h - 1)
    return (x - h, y - h, x - h + crop, y - h + crop)


def _edge_strip(comp: Image.Image, quad, i, width, height):
    """Sample the composite along print edge `i` (TL->TR->BR->BL) one pixel wide
    and stretch it vertically - a dark hairline or a bright band shows up as a
    stripe here even when it is invisible at 1:1."""
    a, b = quad[i], quad[(i + 1) % 4]
    n = width
    xs = np.linspace(a[0], b[0], n).round().astype(int).clip(0, comp.width - 1)
    ys = np.linspace(a[1], b[1], n).round().astype(int).clip(0, comp.height - 1)
    line = np.asarray(comp)[ys, xs]                      # (n,3)
    return Image.fromarray(np.repeat(line[None, :, :], height, axis=0))


# --------------------------------------------------------------------------- demo

A2 = ROOT / "outputs" / "attempt2_reference" / "bundles"     # attempt-2 bundles, kept as reference
A1 = ROOT / "outputs" / "attempt1_reference"                 # attempt-1 bundles, preserved
# Both corpora are copies on purpose: P3 rewrites the live bundles, and a demo
# that points at them would quietly start measuring the fixed scene instead of
# the defect it claims to reproduce.


def _report(name, fired, where, why, detail):
    print(f"  {'FIRED ' if fired else 'SILENT'} {name:20} {where:26} {detail}")
    print(f"  {'':27} known defect: {why}")
    return fired


def _run(name, bundle_dir, art):
    return next(f for f in check(bundle_dir, art)["findings"] if f["name"] == name)


def demo():
    """Every detector against a bundle (or a matte) known to carry its defect."""
    art = Image.open(MASTER).convert("RGB")
    ok = True

    # fringe: the defect is in the compositor, not in any bundle - so put it back.
    scene = A2 / "lifestyle_sage_terracotta" if A2.exists() else A1 / "flat_clips_windowlight"
    orig = cv2.warpPerspective
    cv2.warpPerspective = (lambda src, M, dsize, flags=0, borderMode=None, **kw:
                           orig(src, M, dsize, flags=flags))          # pre-C1 BORDER_CONSTANT
    try:
        broken = _run("fringe", scene, art)
    finally:
        cv2.warpPerspective = orig
    fixed = _run("fringe", scene, art)
    ok &= _report("fringe", not broken["passed"] and fixed["passed"], scene.name,
                  "pre-C1 warpPerspective bled BORDER_CONSTANT=black into the art border",
                  f"C1 reverted: {broken['detail']} | C1 on: {fixed['detail']}")

    for name, bundle_dir, why in (
        ("distortion", A1 / "lifestyle_sage_terracotta",
         "hand-read quad at aspect 0.561 against a 0.684 master"),
        ("coverage", A2 / "flat_leaning_bookstack",
         "two axis-aligned occluder boxes punched out of the print, plus the "
         "3px band of photograph attempt 2 repainted over the print's own edge"),
        ("silhouette-vs-shadow", A2 / "flat_clips_windowlight",
         "art quad expanded past a curled sheet, so the print's straight edge ran "
         "across blank paper while the photographed shadow followed the curl"),
    ):
        if not bundle_dir.exists():
            print(f"  SKIP   {name:20} {bundle_dir} missing")
            continue
        f = _run(name, bundle_dir, art)
        ok &= _report(name, not f["passed"], bundle_dir.name, why, f["detail"])

    ok &= _occluder_demo(art)
    ok &= _spill_demo()
    return ok


def _occluder_demo(art):
    """attempt-1's alpha-172 clips, expressed in the new primitive: its overlay's
    prop stamps become matte holes, and they land at a flat 0.33 instead of 0."""
    import shutil
    import tempfile
    src = A1 / "flat_clips_windowlight"
    tmp = Path(tempfile.mkdtemp()) / "bundle"
    shutil.copytree(src, tmp)
    ov = np.asarray(Image.open(src / "overlay.png").convert("RGBA"), np.float32)[:, :, 3] / 255.0
    stamp = ov > 0.35                       # this bundle's gain map stays under 0.28
    matte = np.where(stamp, 1.0 - ov, 1.0)
    Image.fromarray((matte * 255).round().astype(np.uint8)).save(tmp / "matte.png")
    f = _run("occluder-opacity", tmp, art)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return _report("occluder-opacity", not f["passed"], "clips overlay -> matte",
                   "attempt 1 stamped the clips back at alpha ~172, not 255", f["detail"])


def _spill_demo():
    key = (0, 190, 120)
    matte = np.zeros((60, 60), np.float32)
    matte[15:45, 15:45] = 1.0
    p = dict(comp=np.full((60, 60, 3), 210.0, np.float32),
             bg=np.full((60, 60, 3), 210.0, np.float32), matte=matte)
    clean = d_key_spill(p, key)
    p["bg"][12:15, 15:45] = key          # residue along the print's top edge
    dirty = d_key_spill(p, key)
    return _report("key-spill", clean["passed"] and not dirty["passed"], "(synthetic)",
                   "100px of emerald key left in a composite - no keyed bundle "
                   "exists until P0 generates one", dirty["detail"])


# --------------------------------------------------------------------------- cli

def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    args = argv[2:]
    if cmd == "demo":
        raise SystemExit(0 if demo() else 1)
    art_path = MASTER
    if "--art" in args:
        i = args.index("--art")
        art_path = Path(args[i + 1])
        del args[i:i + 2]
    out = SHEET_DIR
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i:i + 2]
    dirs = [Path(a) for a in args] or [ROOT / "assets" / "mockups" / "primary" / "portrait" / d.name
                                       for d in (ROOT / "assets" / "mockups" / "primary" / "portrait").iterdir()
                                       if d.is_dir()]
    art = Image.open(art_path).convert("RGB")
    all_ok = True
    for d in dirs:
        r = check(d, art)
        all_ok &= r["passed"]
        print(f"\n{r['scene']}  [{'PASS' if r['passed'] else 'FAIL'}]")
        for f in r["findings"]:
            print(f"  {'ok  ' if f['passed'] else 'FAIL'} {f['name']:20} {f['detail']}")
        if cmd == "sheet":
            print(f"  -> {contact_sheet(r, out / f'{r['scene']}.png')}")
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main(sys.argv)
