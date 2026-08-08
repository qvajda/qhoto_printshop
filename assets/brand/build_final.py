"""GL-10a — build the final Qhoto Art shop icon, banner and reusable badge SVG.

Locked decisions (2026-07-24):
  D1 accent  : Pine #23402F — sampled from the Qhoto badge on brand_sheet.pdf p2
  D2 wordmark: "Qhoto Art"  (badge = Q, then "hoto Art")
  D3 source  : redrawn as SVG — brand_sheet.pdf is raster (300 dpi JPEG), there
               is no vector badge to extract
  Letterform : the badge is a Q masquerading as a P ("Photo" -> "Qhoto"), so the
               tail becomes a lowercase-p stem at the LEFT of the bowl. Geometry
               is the midpoint of candidates p-e and p-stem-lean.
  Icon       : bone badge on a Pine ground — pine-on-Ink measures 1.6:1 and the
               stem disappears below 40px, which would make the mark read as O.
  Banner     : sheet's wordmark colourway — pine ring + bone handle on Ink.
"""
import os

import badge
from badge import BONE, INK, PINE, STONE
import banner

OUT = os.environ.get("GL10A_OUT", ".")

# midpoint of p-e (90.0,-0.35,0.175,1.82,1.63,0.193,-0.64)
#         and p-stem-lean (99.0, 0.05,0.150,1.70,1.52,0.170,-0.52)
badge.GEOM["qhoto"] = (94.5, -0.15, 0.1625, 1.76, 1.575, 0.1815, -0.58)
G = "qhoto"


def build():
    os.makedirs(OUT, exist_ok=True)
    p = lambda n: os.path.join(OUT, n)

    # 1. shop icon — 500x500, bone badge on Pine ground
    banner.icon(p("qhoto-shop-icon-500.png"), size=500, geom=G,
                ring=BONE, handle=BONE, ground=PINE, fill=0.70)

    # 2. big banner — 1600x400, product-imagery band (GL-10d)
    banner.banner(p("qhoto-shop-banner-1600x400.png"), W=1600, H=400, geom=G,
                  ring=PINE, handle=BONE, base_frac=0.485, tag_frac=0.660,
                  lockup_cx=banner.LOCKUP_CX, band_images=banner.BAND_IMAGES)

    # 3. mini banner — 1600x213 (optional layout)
    banner.banner(p("qhoto-shop-banner-mini-1600x213.png"), W=1600, H=213, geom=G,
                  ring=PINE, handle=BONE, cap_frac=0.30, base_frac=0.545,
                  tag_frac=0.775)

    # 4. reusable badge SVGs
    open(p("qhoto-badge-icon.svg"), "w").write(
        badge.badge_svg(500, geom=G, ring=BONE, handle=BONE, ground=PINE, fill=0.70))
    open(p("qhoto-badge-wordmark.svg"), "w").write(
        badge.badge_svg(500, geom=G, ring=PINE, handle=BONE, ground=None, fill=0.86))

    # 5. JPEG alternates (Etsy accepts either; PNG is smaller for flat art)
    from PIL import Image
    for src, dst in [("qhoto-shop-icon-500.png", "qhoto-shop-icon-500.jpg"),
                     ("qhoto-shop-banner-1600x400.png",
                      "qhoto-shop-banner-1600x400.jpg")]:
        Image.open(p(src)).convert("RGB").save(p(dst), quality=92, optimize=True,
                                               subsampling=0)


if __name__ == "__main__":
    build()
    for f in sorted(os.listdir(OUT)):
        if f.startswith("qhoto-"):
            print(f"{f:42s} {os.path.getsize(os.path.join(OUT, f)):>9,d} B")
