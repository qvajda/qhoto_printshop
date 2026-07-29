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


def key_distance(rgb: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Lab a/b distance to the key, which ignores the scene light baked into the
    panel's luminance - that light is the gain map, we want to keep it.

    Known limitation, measured but not fixed (GL-21 P4a, 2026-07-29): a deeply
    *shadowed* key desaturates, so a prop's contact shadow drifts away from the
    key and lands in the matte's anti-aliased ramp - a band of half-transparent
    print along that prop. It cost `clipsheet_v1_s44` 568 px at alpha 0.54
    against a sharp 1px clip edge in the photograph itself, and QA's
    occluder-opacity test catches it. Rescaling each pixel's chroma to the key's
    own lightness fixes those bands and was tried: it also amplifies chroma
    noise wherever L is small, and took flat_clips_windowlight from 0 to 30 339
    px of mid-alpha. The right fix is a chroma model, not a division, and it is
    not worth one candidate scene - reject the scene, keep the screen honest."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    return np.linalg.norm(lab[:, :, 1:] - ref, axis=2)


def key_mask(rgb: np.ndarray, ref: np.ndarray) -> np.ndarray:
    return (key_distance(rgb, ref) < KEY_LAB_TOL).astype(np.uint8)


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


def key_contamination(rgb: np.ndarray, ref: np.ndarray) -> dict:
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
      intrusion   pixels at 1x-2.5x the key tolerance INSIDE the quad, excluding
                  the panel's own ~2px anti-aliased rim (which lands in that
                  band by construction and is the false positive this must not
                  fire on) - the feathered mid-alpha pixels that become an
                  occluder-opacity failure at the gate (budget ~41px on a scene
                  this size; 568px killed the P4a clips candidate).

    Returns pixel counts plus a bbox per surviving cluster, so a WARN reads like
    the pivot doc's own sentence ("244 px ... at x 2946-2994, y 1849-1858")."""
    mask = key_mask(rgb, ref)
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

    dist = key_distance(rgb, ref)
    midband = (dist >= KEY_LAB_TOL) & (dist < 2.5 * KEY_LAB_TOL)
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
    ref = key_ref(rgb, key_rgb)
    mask = key_mask(rgb, ref)
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
    derived = quad_for(soft_matte(rgb, ref))
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
    dist = key_distance(rgb, ref)                    # the matte's own measure
    k9 = np.ones((9, 9), np.uint8)
    near = (cv2.dilate(comp, k9) - cv2.erode(comp, k9)).astype(bool)   # boundary ring only
    transition = ((dist > 0.5 * KEY_LAB_TOL) & (dist < 1.5 * KEY_LAB_TOL) & near).sum()
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
