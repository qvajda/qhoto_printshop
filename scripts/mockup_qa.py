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
SPILL_TOL = 20          # Lab a/b distance under which a pixel still reads as the key
PLATEAU_TOL = 0.05      # alpha within this of 0/1 counts as hard
SILHOUETTE_TOL = 4.0    # px of *uneven* gap between photographed and printed edge


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
    edge = (a > 0.02) & (a < 0.98) & ~_corner_mask(p)
    k = np.ones((2 * FRINGE_RADIUS + 3,) * 2, np.uint8)
    lo, hi, seen = _mask_extremes(art, a > 0.98, k)
    excess_a = np.maximum(art - (hi + FRINGE_TOL), (lo - FRINGE_TOL) - art).max(axis=2)
    bad_a = edge & seen & (excess_a > 0)
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
    """No residual key chroma anywhere in the composite. Needs the key colour;
    scenes with no key (every pre-P0 bundle) report n/a rather than a pass."""
    if key_rgb is None:
        return _finding("key-spill", True, None, "n/a - bundle declares no key colour")
    lab = cv2.cvtColor(p["comp"].astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = cv2.cvtColor(np.uint8([[key_rgb]]), cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0]
    dist = np.linalg.norm(lab[:, :, 1:] - ref[1:], axis=2)
    n = int((dist < SPILL_TOL).sum())
    return _finding("key-spill", n == 0, n, f"{n} px within {SPILL_TOL} Lab-ab of key {key_rgb}")


def d_distortion(p: dict) -> dict:
    """The print must not be stretched. Reports the cover-crop C3 would apply."""
    delta = abs(p["aspect"] / p["art_aspect"] - 1)
    return _finding("distortion", delta <= ASPECT_TOL, round(delta, 5),
                    f"quad {p['aspect']:.4f} vs art {p['art_aspect']:.4f} "
                    f"= {delta:.2%} off, cover-crop {p['crop']:.2%}")


def d_coverage(p: dict) -> dict:
    """The print area must be fully printed, and nothing may print outside it.
    Fires on attempt 2's occluder-box notches (print area showing background)
    and on Mode-O spill past the paper."""
    region = _print_region(p)
    shows_art = np.abs(p["comp"] - p["bare"]).max(axis=2) > 3
    inner = cv2.erode(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    outer = cv2.dilate(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    uncovered = int((inner & ~shows_art).sum())
    outside = int((shows_art & ~outer).sum())
    n = uncovered + outside
    return _finding("coverage", n == 0, n,
                    f"{uncovered} px of print area not printed, {outside} px of art outside it")


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
    return _finding("occluder-opacity", n == 0, n,
                    f"{n} px of flat mid-alpha ({src[plateau].mean():.2f} mean)" if n
                    else f"{int(mid.sum())} partial px, all on anti-aliased rims")


def _outward_dark_distance(gray: np.ndarray, region: np.ndarray, side: str,
                           reach=60, drop=12) -> np.ndarray:
    """Per scanline, how far outside the print edge the first clearly darker
    pixel sits - the object's own shadow, or the frame/floor it stands against.
    A print whose silhouette matches the photographed one keeps that distance
    constant along an edge; a curled or mis-traced silhouette makes it wander."""
    out = []
    rows = side in ("left", "right")
    arr = gray if rows else gray.T
    reg = region if rows else region.T
    for i in range(arr.shape[0]):
        hits = np.flatnonzero(reg[i])
        if hits.size == 0:
            continue
        if side in ("right", "bottom"):
            win = arr[i, hits[-1] + 1: hits[-1] + 1 + reach]
        else:
            win = arr[i, max(hits[0] - reach, 0): hits[0]][::-1]
        if win.size < reach // 2:
            continue
        bright = np.percentile(win, 90)
        dark = win < bright - drop
        if dark.any():                     # nothing darker in reach = no reading, not a big one
            out.append(int(np.argmax(dark)))
    return np.asarray(out, float)


def _edge_gap(region: np.ndarray, paper: np.ndarray, axis: int, far: bool):
    """Per-scanline distance between the photographed object's edge and the
    print's edge, along one side. Positive = photographed edge sticks out."""
    idx = np.arange(region.shape[axis])
    shape = [1, 1]
    shape[axis] = -1
    grid = idx.reshape(shape)
    pick = (lambda m: np.where(m.any(axis=axis), np.where(m, grid, -1).max(axis=axis), np.nan)) if far \
        else (lambda m: np.where(m.any(axis=axis), np.where(m, grid, 10 ** 6).min(axis=axis), np.nan))
    gap = pick(paper) - pick(region)
    gap = gap[np.isfinite(gap)]
    return gap if far else -gap


def d_silhouette_vs_shadow(p: dict) -> dict:
    """The photographed silhouette (paper/panel + the shadow drawn to match it)
    and the printed silhouette must disagree *evenly*. A constant margin is
    styling; a gap that varies along an edge is a curled-paper mismatch, which is
    what left a wedge of bare photographed paper under the clips scene."""
    region = _print_region(p)
    if not region.any():
        return _finding("silhouette-vs-shadow", False, None, "no print region")
    gray = cv2.cvtColor(p["bg"].astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    worst, where = 0.0, ""
    for side in ("left", "right", "top", "bottom"):
        d = _outward_dark_distance(gray, region, side)
        if d.size < 20:
            continue
        spread = float(np.percentile(d, 95) - np.percentile(d, 5))
        if spread > worst:
            worst, where = spread, f"{side} (mean {d.mean():.1f}px out)"
    return _finding("silhouette-vs-shadow", worst <= SILHOUETTE_TOL, round(worst, 2),
                    f"shadow/edge stand-off varies {worst:.1f}px along {where}" if where
                    else "no measurable edge")


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
A1 = ROOT / "assets" / "mockups" / "primary" / "portrait"    # attempt-1 bundles, still on the branch


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
        ("silhouette-vs-shadow", A2 / "flat_leaning_bookstack",
         "Mode-O quad reaching ~14px past the photographed board edge"),
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
    p = dict(comp=np.full((40, 40, 3), 210.0, np.float32))
    clean = d_key_spill(p, key)
    p["comp"][10:20, 10:20] = key
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
