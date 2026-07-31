"""GL-21 automated mockup defect gate (docs/2026-07-26-gl6-attempt3-production-
readiness-plan.md §3.4). Authoring-time only, not pipeline code.

Eight detectors, each aimed at a defect that shipped past a human review:

  fringe              the artwork border must blend between art and background -
                      no dark hairline (pre-C1 BORDER_CONSTANT), no bright band
                      (attempt 2's bundle-side repaint)
  key-spill           no residual key chroma left anywhere in the composite
  distortion          quad aspect vs artwork aspect, and the cover-crop it costs
  matte-hidden        the other path that loses print: art scaled into the quad
                      and then trimmed by the matte. Same 2% budget as C3, and
                      invisible to a human reviewer by construction
  coverage            print area fully covered, no visible art outside it
                      (attempt 2's occluder-box notches, Mode-O floor spill)
  occluder-opacity    holes are 0 or 1 apart from anti-aliasing (attempt 1's
                      alpha-172 see-through clips and book spines)
  silhouette-vs-shadow  the photographed object's silhouette and the print's
                      silhouette must not disagree *unevenly* - a constant
                      margin is styling, a bowing gap is a curled-paper mismatch
  scene-fidelity      outside the print, the composite must still be the
                      photograph. The other six all look at the print, and P3
                      shipped four bundles whose overlay repainted ~700k px of
                      *scene* per frame at 6/6 green

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
MATTE_HIDDEN_TOL = 0.02  # F2: the same budget C3 enforces on the cover-crop, on
                        # the other path that loses print. No exceptions (owner,
                        # 2026-07-26) - a panel whose proportions do not match
                        # the product gets re-authored, not exempted.
SPILL_TOL = 32          # Lab a/b distance under which a pixel still reads as the key.
                        # Must match the extractor's own key tolerance: at 20 this
                        # test passed a composite with a visible green rim, because
                        # the rim's residue sat between the two thresholds.
SPILL_PROJ_MAX = 8.0    # Lab units of key-direction chroma tolerated on the print's
                        # own edge band - above this it reads as a coloured hairline
SPILL_BAND_BUDGET = 0.001  # x the band's own size: an occluder's real colour shows at
                        # the rim of its hole, and that is scene content, not residue
PLATEAU_TOL = 0.05      # alpha within this of 0/1 counts as hard
PLATEAU_RIM_PX = 3      # how far a mid-alpha px may be from both a 0 and a 1 and still
                        # count as sitting on a rim - see d_occluder_opacity
PLATEAU_BUDGET = 0.01   # x the matte's perimeter: a matte derived from a photograph's
                        # own edge gradient leaves a few soft px on it. Attempt 1's
                        # alpha-172 stamps are ~10x this and nowhere near an edge.
EDGE_MIN = 20.0         # Sobel magnitude that counts as a real photographic edge
FLOATING_MAX = 0.10     # fraction of the print boundary allowed to sit on no edge at
                        # all (corners, occluder junctions). Derived mattes measure
                        # 0.00-0.03; every hand-drawn quad from attempts 1-2, 0.74-1.00.
SCENE_TOL = 4           # 0-255 per-channel drift allowed outside the print. The
                        # overlay is a rounding-free alpha composite over the
                        # background, so a legitimate zero-alpha pixel drifts by 0.
SCENE_BUDGET = 0.001    # x the outside-print area: the gain map is allowed to
                        # feather a few px past the matte for contact shadow.
                        # The defect this guards was 65% of the frame.
COVERAGE_TOL = 0.0005   # fraction of the print area allowed to read as un-printed:
                        # an anti-aliased rim always leaves a few px indistinguishable
                        # from the background. Attempt 2's occluder notches were 5.1%.
JITTER_TOL = 0.08       # p90 of |alpha_i - alpha_(i+1)| between adjacent boundary-
                        # crossing samples along one straight print edge. A real
                        # photographic edge (or this repo's own occluder rims) varies
                        # smoothly row to row; soft_matte's un-blurred ramp did not -
                        # measured 0.108-0.879 across the keyed corpus before GL-21 P4b2's
                        # fix, all under 0.04 after it.


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
        group_type=bundle.group_type,
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

    Measured against the ratios the group is printed at, not against the
    master's: the primary group prints at 0.667 and 0.707 with the master's
    0.684 between them, so a panel at 0.667 shows exactly the 8x12 the buyer
    receives and is not a distortion at all. C3 enforces the same comparison.

    How much the *matte* then hides is a separate loss on a separate path, and
    d_matte_hidden owns it."""
    gap, nearest = mr.print_mismatch(p["aspect"], p["group_type"])
    where = ("inside the printed range" if gap == 0 else
             f"{gap:.2%} outside it, nearest printed ratio {nearest:.4f}")
    return _finding("distortion", gap <= mr.MAX_COVER_CROP, round(gap, 5),
                    f"quad {p['aspect']:.4f} {where} (limit {mr.MAX_COVER_CROP:.0%}); "
                    f"master {p['art_aspect']:.4f}, cover-crop {p['crop']:.2%}")


def _rectified(mask: np.ndarray, quad: np.ndarray, n=256) -> np.ndarray:
    """`mask` resampled into the quad's own frame, n x n. In this frame the
    design is a unit square, so a loss measured here is a loss of design
    regardless of the scene's perspective."""
    dst = np.float32([[0, 0], [n, 0], [n, n], [0, n]])
    H = cv2.getPerspectiveTransform(dst, quad.astype(np.float32))
    return cv2.warpPerspective(mask.astype(np.float32), H, (n, n),
                               flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP) > 0.5


def _band(vis: np.ndarray) -> tuple[float, float]:
    """How far the visible region is inset from the left and right of the frame,
    as fractions of its width.

    A low quantile of the per-row inset, not the median: a trim is the inset
    that is there on *every* row, so the least-obstructed rows measure it, while
    a prop only ever adds to it. The median is not enough - the bookstack's two
    book piles occlude the print's bottom corners across more than half the
    columns, and a median reads their 8px as a 2.7% bottom trim. A quantile
    rather than the outright minimum so one ragged row cannot report 0."""
    n = vis.shape[1]
    rows = [np.flatnonzero(r) for r in vis]
    rows = [r for r in rows if r.size]
    if not rows:
        return 0.5, 0.5
    lo = float(np.quantile([r[0] for r in rows], 0.1)) / n
    hi = float(np.quantile([n - 1 - r[-1] for r in rows], 0.1)) / n
    return lo, hi


def d_matte_hidden(p: dict) -> dict:
    """How much of the design never reaches the buyer's eye.

    C3 gates one of the two ways print is lost - the cover-crop that fits the
    artwork to the quad's aspect - at 2%. The matte hides print on the *other*
    path, independently of it, and until this detector it was only reported.
    The art is scaled into the quad, then whatever the matte does not pass is
    gone. Measured on lifestyle_bedroom_console: quad 393x574 at aspect 0.6842,
    which passes C3 cleanly, against a 367x574 matte at 0.639 - 6.6% of the
    design's width gone (14px left, 17px right, full-width on 568 of 574 rows).
    A flat symmetric side trim, not prop occlusion.

    Invisible twice over, which is the point of measuring it. On the current
    master those strips land on blank margin; and a reviewer has nothing to
    compare a missing strip *to*, so no amount of full-frame review finds it.
    Bundles are permanent and artwork is not: the next design with a border, a
    signature, or stems running to the edge loses 6.6% of its width in that
    scene, on every listing that uses it.

    Trim vs occlusion. Only the trim is enforced: a prop genuinely in front of
    the print is scene content, and is budgeted upstream by scene_screen's 15%
    occluder check. The two are separated by *shape*, not by filling holes - a
    corner clipped by a shelf edge is an occlusion but is not an enclosed hole,
    and a panel whose bottom edge bows is neither. A trim is a band that runs
    the length of an edge, so it is measured as the median inset per row and
    per column in the quad's own rectified frame; a prop affects a minority of
    rows and drops out of the median, a mismatched panel affects all of them.

    Enforced at C3's 2%, with no exceptions (owner decision 2026-07-26): a
    scene whose panel proportions do not match the product is re-authored, not
    exempted."""
    if p["matte"] is None:
        return _finding("matte-hidden", True, None, "n/a - pre-matte bundle, nothing to hide it")
    vis = _rectified(p["matte"] > 0.5, p["quad"])
    left, right = _band(vis)
    top, bottom = _band(vis.T)
    trimmed = 1 - (1 - left - right) * (1 - top - bottom)
    occluded = max(0.0, (1 - float(vis.mean())) - trimmed)
    return _finding("matte-hidden", trimmed <= MATTE_HIDDEN_TOL, round(trimmed, 4),
                    f"{trimmed:.2%} of the design trimmed off by the matte "
                    f"(L{left:.1%} R{right:.1%} T{top:.1%} B{bottom:.1%}, "
                    f"limit {MATTE_HIDDEN_TOL:.0%}), {occluded:.2%} occluded by props")


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
    # "On a rim" is measured within PLATEAU_RIM_PX, not 2px as it used to be. A
    # straight anti-aliased rim is 1-2px wide, but a *corner* rim is a wedge, and
    # the tip of a wedge is further from both plateaus than its sides are: on
    # lifestyle_shelf_books' shadowed bottom-left corner, where the panel fades
    # into the shelf's own shadow, the wedge measures 5px deep and 21 px of it
    # read as a plateau against a budget of 20. That is a soft edge in the
    # photograph, correctly ramped, failed on its geometry rather than its alpha.
    # 3px still leaves the defect class untouched: attempt 1's alpha-172 clip
    # stamps measure 296 px at every reach from 2px to 5px, because a stamped
    # prop is wide, not a rim (see _occluder_demo).
    k = np.ones((2 * PLATEAU_RIM_PX + 1,) * 2, np.uint8)
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


def d_scene_fidelity(p: dict) -> dict:
    """Outside the print, the composite must still be the photograph.

    The bundle owns three layers and only one of them is the print; the other
    six detectors all measure the print, so nothing stopped an overlay from
    repainting the scene. P3's did: `gain_map` is a normalised convolution whose
    numerator vanishes away from the panel, so g clamped to its floor and the
    overlay carried a full-frame black wash at alpha 115/255 - grey walls, a
    rounded halo round every print, ~700k px per scene - through a 6/6 green
    gate. Measured against the bare background, so it catches any future repaint
    band, stamped prop or vignette, not just this one."""
    outside = ~cv2.dilate(_print_region(p).astype(np.uint8),
                          np.ones((5, 5), np.uint8)).astype(bool)
    delta = np.abs(p["bare"] - p["bg"]).max(axis=2)
    n = int((outside & (delta > SCENE_TOL)).sum())
    budget = int(SCENE_BUDGET * max(outside.sum(), 1))
    return _finding("scene-fidelity", n <= budget, n,
                    f"{n} px of scene repainted outside the print "
                    f"(max {delta[outside].max():.0f}/255, budget {budget})")


def _edge_crossings(matte: np.ndarray, a, b, walk=8) -> list:
    """The alpha of the first partial pixel (>0.02) encountered scanning
    inward from quad corner `a` toward `b`, one sample per row if the edge
    runs closer to vertical or per column if closer to horizontal - the exact
    quantity a reviewer's eye lands on scanning the print's own border, and
    what the owner's manual measurement sampled by hand."""
    h, w = matte.shape
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    vertical = abs(b[1] - a[1]) > abs(b[0] - a[0])
    lo, hi = sorted((a[1], b[1]) if vertical else (a[0], b[0]))
    out = []
    for c in range(int(np.ceil(lo)) + 3, int(np.floor(hi)) - 3):    # corners excluded
        along = (a[1], b[1]) if vertical else (a[0], b[0])
        cross = (a[0], b[0]) if vertical else (a[1], b[1])
        frac = (c - along[0]) / (along[1] - along[0]) if along[1] != along[0] else 0.0
        edge = cross[0] + frac * (cross[1] - cross[0])
        val = None
        for sign in (1, -1):
            for k in range(-2, walk):
                x, y = (int(round(edge)) + sign * k, c) if vertical else (c, int(round(edge)) + sign * k)
                if not (0 <= x < w and 0 <= y < h):
                    continue
                v = matte[y, x]
                if v > 0.02:
                    val = float(v)
                    break
            if val is not None:
                break
        out.append(val)
    return out


def d_edge_alpha_jitter(p: dict) -> dict:
    """The print's four edges are straight by construction (the quad IS that
    edge), so the boundary alpha sampled along one should vary smoothly as a
    function of position, not row to row at random. soft_matte's chroma ramp
    could collapse to a single partial pixel per row when the source edge was
    sharper than the ramp's own width, and that pixel's alpha was then a raw,
    uncorrelated chroma sample - the "black dotted line" / "stairs" the owner
    saw on lifestyle_console_pampas, lifestyle_studio_held and
    lifestyle_framed_wall_plant (2026-07-30). Measured as the 90th-percentile
    jump between adjacent boundary-crossing samples along each edge (corners
    excluded, a genuine occluder crossing the edge reads solidly 0 or 1 rather
    than jittering and so contributes no crossing sample there); worst edge
    wins. See JITTER_TOL for the calibration against the keyed corpus."""
    if p["matte"] is None:
        return _finding("edge-alpha-jitter", True, None, "n/a - pre-matte bundle, no matte edge to measure")
    quad = p["quad"]
    worst, worst_edge = 0.0, None
    for i in range(4):
        vals = [v for v in _edge_crossings(p["matte"], quad[i], quad[(i + 1) % 4]) if v is not None]
        if len(vals) < 20:
            continue
        jit = float(np.percentile(np.abs(np.diff(vals)), 90))
        if jit > worst:
            worst, worst_edge = jit, i
    return _finding("edge-alpha-jitter", worst <= JITTER_TOL, round(worst, 3),
                    f"edge {worst_edge}: p90 row-to-row alpha jump {worst:.2f} "
                    f"(limit {JITTER_TOL:.2f})" if worst_edge is not None else
                    "no edge had enough boundary crossings to measure")


DETECTORS = ["fringe", "key-spill", "distortion", "matte-hidden", "coverage",
             "occluder-opacity", "silhouette-vs-shadow", "scene-fidelity",
             "edge-alpha-jitter"]


def _waive(findings: list, waivers: dict) -> list:
    """An owner may accept a named detector's failure on one bundle, and the
    only honest way to record that is on the bundle: `gate_waivers` in
    scene.json, detector name -> the reason, carried in from the source's own
    sidecar so a re-author keeps it.

    A waived finding still runs, still reports its measurement, and says so in
    every sheet and verdict - what changes is only whether it blocks. This is
    not a way to quieten a detector: switching one off across the corpus is a
    change to the detector, made once with a measurement behind it. Waiving one
    is a statement about one photograph, which is why the reason is required
    text and lives next to the pixels it excuses."""
    out = []
    for f in findings:
        why = waivers.get(f["name"])
        if f["passed"] or not why:
            out.append(f)
            continue
        out.append({**f, "passed": True, "waived": True,
                    "detail": f"WAIVED ({why}) - measured: {f['detail']}"})
    return out


def check(bundle_dir: Path, art: Image.Image) -> dict:
    bundle_dir = Path(bundle_dir)
    bundle = mr.load_bundle(bundle_dir)
    p = _parts(bundle, art)
    prov = bundle_dir / "scene.json"
    scene_json = json.loads(prov.read_text()) if prov.exists() else {}
    key = scene_json.get("key_rgb")
    findings = _waive([d_fringe(p), d_key_spill(p, key), d_distortion(p), d_matte_hidden(p),
                       d_coverage(p), d_occluder_opacity(p), d_silhouette_vs_shadow(p),
                       d_scene_fidelity(p), d_edge_alpha_jitter(p)],
                      scene_json.get("gate_waivers") or {})
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
A3 = ROOT / "outputs" / "attempt3_reference"                 # P3's bundles, before P3.5 re-authored them
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
        ("matte-hidden", A3 / "lifestyle_bedroom_console",
         "the scene's framed opening is 0.639 against a 0.684 master, so the "
         "quad was widened to the master's aspect - passing C3 - and the matte "
         "then trimmed 6.6% of the design's width straight back off again"),
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
    ok &= _scene_fidelity_demo(art)
    ok &= _edge_jitter_demo(art)
    return ok


def _edge_jitter_demo(art):
    """The pre-fix lifestyle_console_pampas bundle, snapshotted before GL-21
    P4b2 added soft_matte's edge blur - the live bundle is now the fixed one,
    so the defect only still exists in this copy (same convention as A1/A2/A3:
    a reference corpus of a bundle caught with its defect in place)."""
    ref = A3 / "lifestyle_console_pampas"
    if not ref.exists():
        print(f"  SKIP   edge-alpha-jitter    {ref} missing")
        return True
    broken = _run("edge-alpha-jitter", ref, art)
    live = ROOT / "assets" / "mockups" / "primary" / "portrait" / "lifestyle_console_pampas"
    fixed = _run("edge-alpha-jitter", live, art)
    return _report("edge-alpha-jitter", not broken["passed"] and fixed["passed"],
                   "lifestyle_console_pampas", "soft_matte's un-blurred chroma ramp put a "
                   "single noisy pixel on the edge, alpha 0.34/0.84/0.78/1.00/0.95/0.48 "
                   "row to row (owner report, 2026-07-30)",
                   f"pre-fix: {broken['detail']} | post-fix: {fixed['detail']}")


def _scene_fidelity_demo(art):
    """P3's own defect, put back on a live bundle: `gain_map`'s normalised
    convolution clamps to GAIN_FLOOR=0.55 away from the panel, so the overlay
    shipped as a full-frame black wash at alpha 115/255 outside the matte."""
    import shutil
    import tempfile
    src = ROOT / "assets" / "mockups" / "primary" / "portrait" / "flat_clips_windowlight"
    tmp = Path(tempfile.mkdtemp()) / "bundle"
    shutil.copytree(src, tmp)
    clean = _run("scene-fidelity", tmp, art)
    ov = np.array(Image.open(src / "overlay.png").convert("RGBA"))
    matte = np.asarray(Image.open(src / "matte.png").convert("L"))
    ov[:, :, 3] = np.where(matte > 128, ov[:, :, 3], 115)      # (1-GAIN_FLOOR)*255
    Image.fromarray(ov, "RGBA").save(tmp / "overlay.png")
    dirty = _run("scene-fidelity", tmp, art)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return _report("scene-fidelity", clean["passed"] and not dirty["passed"],
                   "clips overlay unmasked",
                   "the gain map written full-frame instead of matte-masked - a "
                   "black wash over the whole photograph that 6/6 detectors missed",
                   dirty["detail"])


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
            # not f"...{f'{r['scene']}.png'}": nesting the same quote inside an
            # f-string is PEP 701, i.e. 3.12+, and this gate has to parse on the
            # declared floor (pyproject.toml requires-python). It did not, so on
            # 3.10/3.11 the whole file was a SyntaxError and the gate never ran.
            print(f"  -> {contact_sheet(r, out / (r['scene'] + '.png'))}")
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main(sys.argv)
