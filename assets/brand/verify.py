"""GL-10a verification: dimensions, weight, palette fidelity, safe zones."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import badge
from badge import BONE, INK, PINE, STONE
import banner
from banner import LOCKUP_ZONE, LOCKUP_CX, BAND_ZONE

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
    # Etsy renders transparency as black; the imagery band (RGBA mockup
    # sources, RGBA badge PNGs) is exactly the path that could leak an
    # alpha channel through an unmasked paste() or an un-flattened save.
    check(im.mode == "RGB", f"{f}: mode {im.mode} (want RGB, no alpha)")

print("\n== palette fidelity (exact hexes from brand_sheet.pdf) ==")
ico = np.asarray(Image.open(os.path.join(OUT, "qhoto-shop-icon-500.png")).convert("RGB"))
check(near(ico[8, 8], PINE), f"icon ground = {hexof(ico[8,8])} (want {PINE} Pine)")
# brightest pixel in the icon should be exactly Bone
bright = ico.reshape(-1, 3)[ico.reshape(-1, 3).sum(1).argmax()]
check(near(bright, BONE), f"icon badge   = {hexof(bright)} (want {BONE} Bone)")

ban = np.asarray(Image.open(os.path.join(OUT, "qhoto-shop-banner-1600x400.png")).convert("RGB"))
lx0, ly0, lx1, ly1 = LOCKUP_ZONE
# GL-10d: the imagery band puts a photograph in frame, so a *global* extrema
# search is the wrong instrument (a window/wall highlight out-brightens Bone,
# a botanical print out-greens Pine). Scope both searches to the lockup zone,
# where only the wordmark/tagline/badge live.
lock_flat = ban[ly0:ly1, lx0:lx1].reshape(-1, 3)
check(near(lock_flat[lock_flat.sum(1).argmax()], BONE, 3),
      f"banner wordmark = {hexof(lock_flat[lock_flat.sum(1).argmax()])} (want {BONE} Bone)")
# ring hue: greenest pixel, within the lockup zone
g = lock_flat[:, 1].astype(int) - lock_flat[:, 0].astype(int)
check(near(lock_flat[g.argmax()], PINE, 4),
      f"banner ring     = {hexof(lock_flat[g.argmax()])} (want {PINE} Pine)")
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
bx0, by0, bx1, by1 = BAND_ZONE

# GL-10d: the content mask (b.sum(2) > 300) catches every mid-tone pixel of
# the imagery band too, so its bbox/centroid must be scoped to the lockup
# zone — not the whole banner — or the band swamps the check immediately.
lock = b[ly0:ly1, lx0:lx1]
content = lock.sum(2) > 300                  # wordmark + tagline, not the faint rows
ys, xs = np.nonzero(content)                 # local coords, offset by (lx0, ly0)
lw, lh = lx1 - lx0, ly1 - ly0
check(xs.min() >= 40 and xs.max() <= lw - 40,
      f"lockup content x-range {xs.min()}-{xs.max()} inside {lw}px lockup zone, 40px margin")
check(xs.min() >= 100 and xs.max() <= lw - 100,
      f"lockup content x-range {xs.min()}-{xs.max()} inside safer 100px margin")
cx = lx0 + (xs.min() + xs.max()) / 2
check(abs(cx - LOCKUP_CX) <= 6,
      f"lockup content optically centred: midpoint {cx:.1f} (want {LOCKUP_CX})")
check(ys.min() >= 20 and ys.max() <= lh - 20,
      f"lockup content y-range {ys.min()}-{ys.max()} clear of top/bottom 20px of the zone")

print("\n== imagery band (GL-10d — composited mockup renders) ==")
band = b[by0:by1, bx0:bx1]
band_mask = band.sum(2) > 300
coverage = band_mask.sum() / band_mask.size
check(coverage >= 0.3, f"band populated: {coverage:.0%} of the band zone is content (want >=30%)")

gap_mask = b[:, lx1:bx0].sum(2) > 300         # buffer strip between the two zones
check(gap_mask.sum() == 0,
      f"band does not intrude on the lockup zone: {gap_mask.sum()} content px in the buffer")

full_mask = b.sum(2) > 300
full_mask[:, lx0:lx1] = False                 # exclude the lockup zone itself
ys2, xs2 = np.nonzero(full_mask)
check(xs2.min() >= bx0 - 2 and xs2.max() <= bx1 + 2,
      f"band content x-range {xs2.min()}-{xs2.max()} lands inside band zone ({bx0}-{bx1})")
check(ys2.min() >= by0 - 2 and ys2.max() <= by1 + 2,
      f"band content y-range {ys2.min()}-{ys2.max()} lands inside band zone ({by0}-{by1})")
# corner-is-Ink is already asserted above ("banner ground") — the band sits
# entirely inside BAND_ZONE, nowhere near [4, 4], so that check still covers it.

print("\n== avatar-scale legibility (stem must survive downscale) ==")
for px in (96, 62, 40, 26, 20):
    small = np.asarray(im.resize((px, px), Image.LANCZOS).convert("RGB")).astype(int)
    m = small.sum(2) > 400
    half = m[int(px * 0.62):, :]             # lower part = the descender
    check(half.sum() >= 3,
          f"{px}px: descender survives ({half.sum()} px below 62% height)")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURE(S)"))
sys.exit(1 if fails else 0)
