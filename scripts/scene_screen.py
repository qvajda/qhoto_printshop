"""GL-6 attempt-3 P0: machine-checked screen for keyed scene candidates.

Replaces the prose generation criteria (plan §3.2). Nine checks, all derived
from the key mask - no hand-reading, and the same key extraction P2's
`scene_author.py extract` will use:

  area          key covers a plausible fraction of the frame
  single        one connected key region, not confetti
  solidity      the region is a panel, not a splash
  aspect        opening within 3% of the group's target (0.684 for primary)
  occluders     holes (clips, spines) cover <= 15% of the panel
  sharp         the key edge is a hard edge, not a soft gradient
  no-outside    no key colour anywhere outside the panel (spill)
  frontal       opposite edges of the panel are within 4% of each other
  no-nested     no second straight line inside the opening (sage's defect (d))

    scene_screen.py [outputs/gl6_keyed] [--sheet]
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
IN_DIR = ROOT / "outputs" / "gl6_keyed"

KEY_LAB_TOL = 32                   # Lab a/b distance that still reads as the key
AREA_RANGE = (0.10, 0.60)
SOLIDITY_MIN = 0.93
ASPECT_TOL = 0.02                  # matches the compositor's MAX_COVER_CROP: no point
                                   # showing the owner a panel C3 will refuse later
OCCLUDER_MAX = 0.15
SHARP_MAX = 3.0                    # px of key/non-key transition per px of perimeter
OUTSIDE_MAX = 0.002                # key px outside the panel, as a fraction of the panel
FRONTAL_TOL = 0.06                 # opposite-edge length ratio; a homography maps any
                                   # quad exactly, so mild perspective is fine - this only
                                   # rejects the steep scenes deferred to v1.1
NESTED_MAX = 0.004                 # fraction of interior px sitting on a straight edge


def key_ref(rgb: np.ndarray, hint_rgb) -> np.ndarray:
    """The key's actual Lab a/b, measured off the image.

    The prompt asks for "vivid magenta"; FLUX paints some hot pink of its own
    choosing, tens of Lab units from (255,0,255). Keying against the requested
    colour therefore finds nothing and reports a perfectly good panel as empty.
    So: take the largest strongly-chromatic region and use *its* median a/b,
    falling back to the requested colour when the image has no such region.
    scene_author's extract needs exactly this, for the same reason."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    hint = cv2.cvtColor(np.uint8([[hint_rgb]]), cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0, 1:]
    strong = (np.linalg.norm(lab[:, :, 1:] - 128.0, axis=2) > 40).astype(np.uint8)
    n, comp, stats, _ = cv2.connectedComponentsWithStats(strong, 8)
    if n < 2:
        return hint
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[biggest, cv2.CC_STAT_AREA] < 0.02 * rgb.shape[0] * rgb.shape[1]:
        return hint
    return np.median(lab[:, :, 1:][comp == biggest], axis=0)


LOCUS_BIN = 2.0                    # L units per knot. Fine enough to follow the roll-off
                                   # (lifestyle_console_vase's key moves 20 Lab units of
                                   # chroma between L 40 and L 62), coarse enough that a
                                   # knot is a median over thousands of px, not noise.
LOCUS_MIN_BIN = 64                 # px before a lightness bin is trusted as a knot: below
                                   # this a bin is the panel's own speckle, and one bad knot
                                   # bends the locus for every pixel that interpolates
                                   # through it.
KEY_FRAC = 0.5                     # the tolerance at a given lightness, as a fraction of
                                   # the key's own chroma there. Below 1 by construction, so
                                   # a *neutral* pixel (chroma 0, deviation = the locus's own
                                   # magnitude) can never be classified as key at any
                                   # lightness - that is the property the fixed 32-unit
                                   # tolerance did not have, and the reason a deeply shadowed
                                   # neutral was the naive division's failure mode. 0.5 leaves
                                   # the bright end unchanged from the old absolute test
                                   # (0.5 x the corpus's 62-88 unit keys is >= 31 against
                                   # KEY_LAB_TOL's 32) so the shipped bundles do not move.
NOISE_FLOOR_K = 4.0                # x the panel's own measured scatter about the locus: the
                                   # graceful-degradation floor §2 asks for. Where the key is
                                   # so dark that KEY_FRAC x chroma falls under the image's
                                   # own noise, widen back to the noise instead of punching
                                   # speckle holes in the matte. The corpus measures sigma
                                   # 0.4-1.4, so this floor only engages below L ~ 6.


def _fit_locus(L: np.ndarray, ab: np.ndarray):
    """The key's chroma locus: median a/b per lightness bin, as knots (L, a, b).

    This is the model plan §2 asks for, and it is fitted per image from the
    panel's own pixels - there is no per-scene constant here, only the panel's
    own measurement of what its key looks like under its own light."""
    if L.size == 0:
        return np.zeros((0, 3), np.float32)
    idx = np.clip((L / LOCUS_BIN).astype(int), 0, int(100 / LOCUS_BIN))
    counts = np.bincount(idx, minlength=int(100 / LOCUS_BIN) + 1)
    # The contiguous run of populated bins around the panel's modal lightness,
    # not every populated bin. A gap in the middle is lightness the panel never
    # exhibited, and `np.interp` would happily draw a straight line across it -
    # inventing a locus for illumination that was never observed. An isolated
    # far bin is worse than no knot at all: it bends the curve for every pixel
    # that interpolates through it.
    top = int(counts.argmax())
    lo = hi = top
    while lo > 0 and counts[lo - 1] >= LOCUS_MIN_BIN:
        lo -= 1
    while hi + 1 < len(counts) and counts[hi + 1] >= LOCUS_MIN_BIN:
        hi += 1
    knots = [[float(np.median(L[s])), *np.median(ab[s], axis=0)]
             for b in range(lo, hi + 1) for s in [idx == b] if s.sum() >= LOCUS_MIN_BIN]
    if not knots:                                        # too small/flat to bin - one knot
        knots = [[float(np.median(L)), *np.median(ab, axis=0)]]
    return np.asarray(knots, np.float32)


def _locus_at(L: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """The locus's a/b at each pixel's lightness.

    Held constant outside the lightness range the panel actually exhibits, not
    extrapolated along the end slope. Extrapolating downward off the bright end
    says "the key keeps desaturating as it gets lighter", which is true of a
    highlight and equally true of the matte's own anti-aliased rim blending into
    a pale wall - and the rim is the far commoner pixel. Constant is the
    honest reading: outside what was observed, assume the nearest thing that was.
    (Consequence, stated rather than hidden: a *blown* highlight desaturates past
    the top knot and is not recovered - see the plan's criterion 4.)"""
    if len(knots) == 1:
        return np.broadcast_to(knots[0, 1:], L.shape + (2,))
    return np.stack([np.interp(L, knots[:, 0], knots[:, 1 + i]) for i in range(2)], axis=-1)


def key_model(rgb: np.ndarray, hint_rgb) -> dict:
    """Fit the key's chroma model: where the key sits in Lab under *this* image's
    own range of illumination, and how tight that fit is.

    Replaces "Lab a/b distance to a fixed reference", which measured the wrong
    thing (GL-21 P4a, 2026-07-29). Dropping L from the distance does not make the
    measurement lightness-invariant: a surface's a/b themselves collapse toward
    neutral as it darkens, so a shadowed key - still 100% key - drifts away from
    the reference and lands in the matte's anti-aliased ramp as half-transparent
    print. Measured on lifestyle_studio_held: 847 px of a hand's grip shadow at
    alpha 0.61, distances 20-31 against a ramp whose lower edge is 19.2, while a
    genuine prop (her finger) sits at 76. The two are not close; the fixed
    reference simply could not tell them apart.

    Rescaling each pixel's chroma to the key's own lightness was tried and is a
    dead end: it amplifies chroma noise wherever L is small and took
    flat_clips_windowlight from 0 to 30 339 px of mid-alpha. So: fit the locus,
    do not divide by L. The panel's key traces a curve through (L, a, b) - the
    corpus measures it as tight as +-2 units of chroma per lightness bin - and
    membership becomes deviation from that curve, at a tolerance that shrinks
    with the key's own chroma so a neutral is never swallowed (see KEY_FRAC).

    Seeded from the old absolute test and refitted once against its own result:
    the seed already spans the shadow (those pixels measure 19-32, i.e. inside
    KEY_LAB_TOL - it was the *ramp*, not the mask, that they fell out of), and
    the second pass lets the fit reach the lightness bins the first one only
    just missed."""
    ref = key_ref(rgb, hint_rgb)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0] * (100.0 / 255.0)
    ab = lab[:, :, 1:] - 128.0
    seed = panel((np.linalg.norm(ab - (np.asarray(ref, np.float32) - 128.0), axis=2)
                  < KEY_LAB_TOL).astype(np.uint8))[0]
    model = dict(ref=[float(v) for v in ref],
                 knots=[[float(v) for v in (50.0, *(np.asarray(ref, np.float32) - 128.0))]],
                 sigma=0.0)
    if seed is None:
        return model                                     # no key region: screen() reports it
    # Fitted off the region's *interior*, never its rim: an anti-aliased edge
    # pixel is a blend of key and background, so it sits off the locus by
    # construction, and at a lightness the panel itself may not otherwise reach
    # it would be the only contributor to a bin - a knot made entirely of
    # background.
    sel = cv2.erode(seed, np.ones((5, 5), np.uint8)).astype(bool)
    if not sel.any():
        sel = seed.astype(bool)
    for _ in range(2):
        knots = _fit_locus(L[sel], ab[sel])
        resid = np.linalg.norm(ab[sel] - _locus_at(L[sel], knots), axis=1)
        model = dict(ref=[float(v) for v in ref],
                     knots=[[round(float(v), 2) for v in k] for k in knots],
                     sigma=round(float(1.4826 * np.median(resid)), 3))
        nxt = panel((key_deviation(rgb, model) < 1.0).astype(np.uint8))[0]
        if nxt is None:
            break
        sel = cv2.erode(nxt, np.ones((5, 5), np.uint8)).astype(bool)
        if not sel.any():
            break
    return model


def key_deviation(rgb: np.ndarray, model: dict) -> np.ndarray:
    """How far each pixel is from being the key surface, in units of the key's
    own tolerance at that pixel's lightness. 1.0 is the boundary, so every
    threshold this repo already carries as a multiple of KEY_LAB_TOL keeps its
    meaning as a multiple of 1.0.

    A shadowed key lies *on* the locus at low L and reads ~0. A prop lies off it
    whatever its L. A neutral reads >= 1/KEY_FRAC by construction."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0] * (100.0 / 255.0)
    knots = np.asarray(model["knots"], np.float32)
    locus = _locus_at(L, knots)
    dev = np.linalg.norm(lab[:, :, 1:] - 128.0 - locus, axis=2)
    tol = np.clip(KEY_FRAC * np.linalg.norm(locus, axis=2),
                  NOISE_FLOOR_K * model["sigma"], KEY_LAB_TOL)
    return dev / np.maximum(tol, 1e-6)


def key_mask(rgb: np.ndarray, model: dict) -> np.ndarray:
    return (key_deviation(rgb, model) < 1.0).astype(np.uint8)


def panel(mask: np.ndarray):
    """Largest key component + the same region with its holes filled. The holes
    are the occluders: a clip jaw or a book spine is simply not the key."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n < 2:
        return None, None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (lab == biggest).astype(np.uint8)
    filled = comp.copy()
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(filled, cnts, -1, 1, cv2.FILLED)
    return comp, filled


def _quad(filled):
    """Corner quad of the key region, TL TR BR BL.

    Not minAreaRect: a rotated rect has equal opposite edges by construction, so
    it can never show perspective, and it would square off a curled sheet whose
    curl we specifically want to keep.

    Not the contour's x+y / x-y extremes either, which is what this used to be.
    Those pick the true corners only while the panel's edges stay roughly axis
    aligned. On a panel whose bottom edge tilts - every leaning scene - x-y is
    minimised by a point part-way along the *bottom* edge rather than by the
    bottom-left corner, and the resulting quad is skewed and oversized. On
    lifestyle_shelf_books it put the corner 38px off, which `quad_for`'s
    containment step then had to swallow by widening the whole quad 5%, which
    the aspect step amplified to 13% of the design hidden behind the matte
    (GL-21 P3.5/F2). Polygon-approximate the contour to exactly four vertices
    instead, and keep the extremes only to order them and as a fallback."""
    cnt = max(cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
              key=cv2.contourArea)
    p = cnt.reshape(-1, 2).astype(np.float32)
    peri = cv2.arcLength(cnt, True)
    for eps in np.arange(0.005, 0.15, 0.002):
        approx = cv2.approxPolyDP(cnt, eps * peri, True)
        if len(approx) == 4:
            p = approx.reshape(4, 2).astype(np.float32)
            break
    s, d = p.sum(1), p[:, 0] - p[:, 1]
    quad = np.stack([p[s.argmin()], p[d.argmax()], p[s.argmax()], p[d.argmin()]])
    return quad, cnt


CONTAM_MIN_AREA_FRAC = 0.0001      # a contamination cluster must cover at least this
                                   # fraction of the panel's own area to count - scale-
                                   # aware because this repo carries no per-scene
                                   # constants. Calibrated against the real defect (pivot
                                   # doc §3.2): a fern frond measured 244px (protrusion
                                   # band) + 78px (intrusion band) against a ~2M px panel,
                                   # 0.012% and 0.004% respectively - both an order of
                                   # magnitude above this floor, while a single stray
                                   # anti-aliased pixel is not.
CONTAM_RIM_PX = 2                  # the panel's own edge sits just outside the hard key
                                   # mask by construction, and just inside/outside the
                                   # quad's own boundary - both are expected to read as
                                   # midband and must not fire. This is the ~2px the
                                   # brief allows past each measurement before it counts.


def _clusters(mask: np.ndarray, min_area: int):
    """Connected components of `mask` at or above `min_area`, as (kept-mask, bboxes)."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    ids = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    kept = np.isin(lab, ids) if ids else np.zeros(mask.shape, bool)
    boxes = [tuple(int(v) for v in stats[i, :4]) for i in ids]
    return kept, boxes


def key_contamination(rgb: np.ndarray, model: dict) -> dict:
    """A prop whose colour sits near the key (pivot doc §3.2's fern frond): close
    enough that the hard key mask swallows it, the panel still reads as a solid
    rectangle, and `screen`'s `occluders` metric reports 0.0 - while `extract`
    would put the prop *inside* the print area, and the art would print straight
    over something visibly in front of the poster.

    Two measurements the screen's own mask-solidity check provably cannot make,
    because solidity only ever looks at the panel's *largest* component and
    fills its holes - both blind spots this exists to cover:

      protrusion  key-classified pixels OUTSIDE the panel's own quad, past a
                  ~2px rim. A prop swallowed into the mask makes it bulge past
                  the panel's own straight sides; that bulge is the signature.
      intrusion   pixels at 1x-2.5x the key deviation INSIDE the quad, excluding
                  the panel's own ~2px anti-aliased rim (which lands in that
                  band by construction and is the false positive this must not
                  fire on) - the feathered mid-alpha pixels that become an
                  occluder-opacity failure at the gate (budget ~41px on a scene
                  this size; 568px killed the P4a clips candidate).

    Returns pixel counts plus a bbox per surviving cluster, so a WARN reads like
    the pivot doc's own sentence ("244 px ... at x 2946-2994, y 1849-1858")."""
    mask = key_mask(rgb, model)
    comp, filled = panel(mask)
    if comp is None:
        return dict(protrusion=0, intrusion=0, clusters=[])
    quad, _ = _quad(filled)
    h, w = mask.shape
    quad_fill = np.zeros((h, w), np.uint8)
    cv2.fillPoly(quad_fill, [np.round(quad).astype(np.int32)], 1)
    rim = np.ones((2 * CONTAM_RIM_PX + 1,) * 2, np.uint8)
    min_area = max(4, int(CONTAM_MIN_AREA_FRAC * filled.sum()))

    outside_quad = cv2.dilate(quad_fill, rim) == 0
    protrusion, p_boxes = _clusters((mask > 0) & outside_quad, min_area)

    dev = key_deviation(rgb, model)
    midband = (dev >= 1.0) & (dev < 2.5)
    panel_rim = cv2.dilate(comp, rim).astype(bool) & ~comp.astype(bool)
    inside_quad = quad_fill.astype(bool)
    intrusion, i_boxes = _clusters(midband & inside_quad & ~panel_rim, min_area)

    return dict(protrusion=int(protrusion.sum()), intrusion=int(intrusion.sum()),
                clusters=[dict(kind="protrusion", bbox=b) for b in p_boxes] +
                         [dict(kind="intrusion", bbox=b) for b in i_boxes])


def aspect_gap(aspect: float, group_type: str) -> float:
    """Distance from a panel's aspect to the range its group is *printed* at -
    the same measure C3 applies at render time, so the screen never promotes a
    scene the compositor will refuse. Zero anywhere inside the range."""
    from pipeline.mockup_render import print_mismatch
    return print_mismatch(aspect, group_type)[0]


def screen(path: Path, key_rgb, group_type="primary") -> dict:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    h, w = rgb.shape[:2]
    model = key_model(rgb, key_rgb)
    mask = key_mask(rgb, model)
    comp, filled = panel(mask)
    if comp is None:
        return dict(name=path.stem, passed=False, fail=["area"], metrics={"area": 0.0},
                    path=str(path))

    box, cnt = _quad(filled)
    area = filled.sum() / (h * w)
    n_comp = cv2.connectedComponentsWithStats(mask, 8)[2]
    big = int((n_comp[1:, cv2.CC_STAT_AREA] > 0.02 * filled.sum()).sum())
    hull = cv2.contourArea(cv2.convexHull(cnt))
    solidity = float(filled.sum() / hull) if hull else 0.0
    e = [float(np.linalg.norm(box[i] - box[(i + 1) % 4])) for i in range(4)]
    if min(e) < 4:                                   # degenerate region, not a panel
        return dict(name=path.stem, passed=False, fail=["area"],
                    metrics={"area": round(area, 3)}, path=str(path))
    # The aspect that matters is the one scene_author will *derive*, and that
    # means deriving it the same way: from the anti-aliased matte, not from this
    # hard key mask, and through quad_for's containment and rim margin. Measuring
    # anything else promotes scenes the gate then rejects - the hard mask read
    # clipsheet_v2_s44 at 0.7074 and the author derived 0.7276, 2.8% off the
    # printed range and a C3 failure. Imported here, not at module scope:
    # scene_author imports this module.
    from scene_author import quad_for, soft_matte
    derived = quad_for(soft_matte(rgb, model))
    e = [float(np.linalg.norm(derived[i] - derived[(i + 1) % 4])) for i in range(4)]
    aspect = ((e[0] + e[2]) / 2) / ((e[1] + e[3]) / 2)          # width / height
    e = [float(np.linalg.norm(box[i] - box[(i + 1) % 4])) for i in range(4)]   # frontal: the panel's own
    occl = float((filled - comp).sum() / max(filled.sum(), 1))
    frontal = max(abs(e[0] - e[2]) / max(e[0], e[2]), abs(e[1] - e[3]) / max(e[1], e[3]))
    outside = float((mask & ~cv2.dilate(filled, np.ones((5, 5), np.uint8))).sum()
                    / max(filled.sum(), 1))

    # sharp: how wide the key/non-key transition actually is, in pixels of
    # perimeter. A hard painted edge crosses the key threshold within ~1-2px; a
    # soft gradient or a semi-transparent panel smears it over many more, and
    # that is a panel whose matte can never be cut cleanly.
    dev = key_deviation(rgb, model)                  # the matte's own measure
    k9 = np.ones((9, 9), np.uint8)
    near = (cv2.dilate(comp, k9) - cv2.erode(comp, k9)).astype(bool)   # boundary ring only
    transition = ((dev > 0.5) & (dev < 1.5) & near).sum()
    perimeter = float(cv2.arcLength(cnt, True))
    sharp = float(transition / max(perimeter, 1))

    # no-nested: a mat line, bevel or second frame inside the opening shows up as
    # a long straight edge in the panel's own interior
    inner = cv2.erode(comp, np.ones((15, 15), np.uint8)).astype(bool)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120) > 0
    nested = float((edges & inner).sum() / max(inner.sum(), 1))

    m = dict(area=round(area, 3), components=big, solidity=round(solidity, 3),
             aspect=round(aspect, 4), occluders=round(occl, 3), sharp=round(sharp, 3),
             outside=round(outside, 4), frontal=round(frontal, 3), nested=round(nested, 4))
    fails = [n for n, ok in (
        ("area", AREA_RANGE[0] <= area <= AREA_RANGE[1]),
        ("single", big == 1),
        ("solidity", solidity >= SOLIDITY_MIN),
        ("aspect", aspect_gap(aspect, group_type) <= ASPECT_TOL),
        ("occluders", occl <= OCCLUDER_MAX),
        ("sharp", sharp <= SHARP_MAX),
        ("no-outside", outside <= OUTSIDE_MAX),
        ("frontal", frontal <= FRONTAL_TOL),
        ("no-nested", nested <= NESTED_MAX),
    ) if not ok]
    return dict(name=path.stem, passed=not fails, fail=fails, metrics=m,
                quad=[[round(float(x), 1), round(float(y), 1)] for x, y in box], path=str(path))


def sheet(results, out_path, cols=6, tile=220):
    """Labelled contact sheet, survivors first - the only thing the owner reads."""
    rows = (len(results) + cols - 1) // cols
    sh = Image.new("RGB", (cols * tile, rows * (tile + 34) + 8), (18, 18, 18))
    dr = ImageDraw.Draw(sh)
    for i, r in enumerate(results):
        x, y = (i % cols) * tile, (i // cols) * (tile + 34) + 4
        im = Image.open(r["path"]).convert("RGB")
        im.thumbnail((tile - 8, tile - 8))
        sh.paste(im, (x + 4, y))
        colour = (120, 230, 140) if r["passed"] else (230, 130, 120)
        dr.text((x + 4, y + tile - 2), r["name"][:34], colour)
        dr.text((x + 4, y + tile + 9), "PASS" if r["passed"] else ",".join(r["fail"])[:34], colour)
        dr.text((x + 4, y + tile + 20),
                f"a{r['metrics'].get('aspect', 0):.3f} occ{r['metrics'].get('occluders', 0):.2f} "
                f"sol{r['metrics'].get('solidity', 0):.2f}", (160, 160, 160))
    sh.save(out_path)
    return out_path


def main(argv):
    in_dir = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else IN_DIR
    group_type = argv[argv.index("--group") + 1] if "--group" in argv else "primary"
    manifest = json.loads((in_dir / "manifest.json").read_text())
    # only images this manifest actually produced - a stale PNG from an earlier
    # prompt revision must not be screened under the current run's provenance
    keys = {j["name"]: tuple(j["key_rgb"]) for j in manifest["jobs"] if j.get("path")}
    results = []
    for p in sorted(in_dir.glob("*.png")):
        if p.stem not in keys:
            continue
        results.append(screen(p, keys[p.stem], group_type))
    results.sort(key=lambda r: (not r["passed"], len(r["fail"]), r["name"]))
    for r in results:
        print(f"  {'PASS' if r['passed'] else 'fail'} {r['name']:34} "
              f"{'' if r['passed'] else ','.join(r['fail']):28} {r['metrics']}")
    ok = [r for r in results if r["passed"]]
    by_type = sorted({r["name"].split("_")[0] for r in ok})
    print(f"\n{len(ok)}/{len(results)} pass; scene types with a clean key: "
          f"{', '.join(by_type) if by_type else 'none'} ({len(by_type)}/4)")
    (in_dir / "screen.json").write_text(json.dumps(results, indent=2) + "\n")
    if "--sheet" in argv:
        print(f"sheet -> {sheet(results, in_dir / 'contact_sheet.png')}")
    return 0 if len(by_type) >= 2 else 1        # P0 gate: >= 2 of 4 scene types


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
