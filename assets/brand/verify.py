"""GL-10a verification: dimensions, weight, palette fidelity, safe zones."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import badge
from badge import BONE, INK, PINE, STONE

OUT = sys.argv[1] if len(sys.argv) > 1 else "final"
badge.GEOM["qhoto"] = (94.5, -0.15, 0.1625, 1.76, 1.575, 0.1815, -0.58)

SPEC = {
    "qhoto-shop-icon-500.png": (500, 500),
    "qhoto-shop-icon-500.jpg": (500, 500),
    "qhoto-shop-banner-1600x400.png": (1600, 400),
    "qhoto-shop-banner-1600x400.jpg": (1600, 400),
    "qhoto-shop-banner-mini-1600x213.png": (1600, 213),
}
fails = []


def check(ok, msg):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        fails.append(msg)


def hexof(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def near(rgb, target, tol=2):
    t = [int(target[i:i + 2], 16) for i in (1, 3, 5)]
    return all(abs(int(a) - b) <= tol for a, b in zip(rgb, t))


print("== dimensions & file size (Etsy: icon 500x500, banner 1600x400, <=1MB) ==")
for f, (w, h) in SPEC.items():
    p = os.path.join(OUT, f)
    im = Image.open(p)
    sz = os.path.getsize(p)
    check(im.size == (w, h), f"{f}: {im.size[0]}x{im.size[1]} (want {w}x{h})")
    check(sz <= 1_000_000, f"{f}: {sz:,} B (limit 1,000,000)")

print("\n== palette fidelity (exact hexes from brand_sheet.pdf) ==")
ico = np.asarray(Image.open(os.path.join(OUT, "qhoto-shop-icon-500.png")).convert("RGB"))
check(near(ico[8, 8], PINE), f"icon ground = {hexof(ico[8,8])} (want {PINE} Pine)")
# brightest pixel in the icon should be exactly Bone
bright = ico.reshape(-1, 3)[ico.reshape(-1, 3).sum(1).argmax()]
check(near(bright, BONE), f"icon badge   = {hexof(bright)} (want {BONE} Bone)")

ban = np.asarray(Image.open(os.path.join(OUT, "qhoto-shop-banner-1600x400.png")).convert("RGB"))
flat = ban.reshape(-1, 3)
check(near(flat[flat.sum(1).argmax()], BONE, 3),
      f"banner wordmark = {hexof(flat[flat.sum(1).argmax()])} (want {BONE} Bone)")
# ring hue: greenest pixel
g = flat[:, 1].astype(int) - flat[:, 0].astype(int)
check(near(flat[g.argmax()], PINE, 4),
      f"banner ring     = {hexof(flat[g.argmax()])} (want {PINE} Pine)")
corner = ban[4, 4]
check(near(corner, INK, 2), f"banner ground   = {hexof(corner)} (want {INK} Ink)")

print("\n== icon circle-crop safety (Etsy renders the icon as a circle) ==")
im = Image.open(os.path.join(OUT, "qhoto-shop-icon-500.png")).convert("RGB")
a = np.asarray(im).astype(int)
mark = (a.sum(2) > 400)                      # bone badge pixels
ys, xs = np.nonzero(mark)
r = np.hypot(xs - 249.5, ys - 249.5).max()
check(r < 250, f"badge fits inscribed circle: max radius {r:.1f}px of 250")
check(r < 225, f"badge keeps >=10% circle margin: {r:.1f}px of 225")
# nothing critical in the corners that the circle discards
corner_mark = mark[:73, :73].sum() + mark[:73, -73:].sum() + \
              mark[-73:, :73].sum() + mark[-73:, -73:].sum()
check(corner_mark == 0, f"no badge pixels in discarded corners ({corner_mark} found)")

print("\n== banner safe zone (Etsy crops/overlays the outer edges) ==")
b = np.asarray(Image.open(os.path.join(OUT, "qhoto-shop-banner-1600x400.png")).convert("RGB")).astype(int)
content = b.sum(2) > 300                     # wordmark + tagline, not the faint rows
ys, xs = np.nonzero(content)
check(xs.min() >= 200 and xs.max() <= 1400,
      f"content x-range {xs.min()}-{xs.max()} inside central 1200px (200-1400)")
check(xs.min() >= 300 and xs.max() <= 1300,
      f"content x-range {xs.min()}-{xs.max()} inside safer central 1000px (300-1300)")
cx = (xs.min() + xs.max()) / 2
check(abs(cx - 800) <= 6, f"content optically centred: midpoint {cx:.1f} (want 800)")
check(ys.min() >= 20 and ys.max() <= 380,
      f"content y-range {ys.min()}-{ys.max()} clear of top/bottom 20px")

print("\n== avatar-scale legibility (stem must survive downscale) ==")
for px in (96, 62, 40, 26, 20):
    small = np.asarray(im.resize((px, px), Image.LANCZOS).convert("RGB")).astype(int)
    m = small.sum(2) > 400
    half = m[int(px * 0.62):, :]             # lower part = the descender
    check(half.sum() >= 3,
          f"{px}px: descender survives ({half.sum()} px below 62% height)")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURE(S)"))
sys.exit(1 if fails else 0)
