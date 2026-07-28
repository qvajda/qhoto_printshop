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
IN_DIR = ROOT / "outputs" / "gl6_keyed"
TARGET_ASPECT = 6656 / 9728        # db/base_artwork/39.png

KEY_LAB_TOL = 32                   # Lab a/b distance that still reads as the key
AREA_RANGE = (0.10, 0.60)
SOLIDITY_MIN = 0.93
ASPECT_TOL = 0.03
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


def key_mask(rgb: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Lab a/b distance to the key, which ignores the scene light baked into the
    panel's luminance - that light is the gain map, we want to keep it."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    return (np.linalg.norm(lab[:, :, 1:] - ref, axis=2) < KEY_LAB_TOL).astype(np.uint8)


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


def screen(path: Path, key_rgb) -> dict:
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
    aspect = ((e[0] + e[2]) / 2) / ((e[1] + e[3]) / 2)          # width / height
    occl = float((filled - comp).sum() / max(filled.sum(), 1))
    frontal = max(abs(e[0] - e[2]) / max(e[0], e[2]), abs(e[1] - e[3]) / max(e[1], e[3]))
    outside = float((mask & ~cv2.dilate(filled, np.ones((5, 5), np.uint8))).sum()
                    / max(filled.sum(), 1))

    # sharp: how wide the key/non-key transition actually is, in pixels of
    # perimeter. A hard painted edge crosses the key threshold within ~1-2px; a
    # soft gradient or a semi-transparent panel smears it over many more, and
    # that is a panel whose matte can never be cut cleanly.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    dist = np.linalg.norm(lab[:, :, 1:] - ref, axis=2)
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
        ("aspect", abs(aspect / TARGET_ASPECT - 1) <= ASPECT_TOL),
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
    manifest = json.loads((in_dir / "manifest.json").read_text())
    # only images this manifest actually produced - a stale PNG from an earlier
    # prompt revision must not be screened under the current run's provenance
    keys = {j["name"]: tuple(j["key_rgb"]) for j in manifest["jobs"] if j.get("path")}
    results = []
    for p in sorted(in_dir.glob("*.png")):
        if p.stem not in keys:
            continue
        results.append(screen(p, keys[p.stem]))
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
