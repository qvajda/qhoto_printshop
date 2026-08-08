"""Qhoto Art — Etsy shop banner (1600x400) and mini banner (1600x213).

Echoes the Qrchard banner application on brand_sheet.pdf p2: Ink ground with a
soft warm centre lift, low-opacity "orchard row" verticals rising from the
bottom edge, badge-as-Q wordmark in Fraunces centred, letterspaced Inter caps
tagline in Stone below. Rendered at 3x and downsampled.
"""
import io
import math
import os
import random

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from badge import badge_group, extent, INK, CHARCOAL, BONE, STONE, PINE, GEOM

SS = 4  # supersample factor
FONTS = "fonts/"

# GL-10d — big-banner-only zones (1600x400 final-res coords), shared with
# verify.py so the two never drift apart. mini banner (213px tall) is
# type-led only and does not use these.
LOCKUP_ZONE = (40, 20, 860, 380)     # x0, y0, x1, y1 — badge/wordmark/tagline
LOCKUP_CX = 450                      # lockup's own optical centre
BAND_ZONE = (900, 40, 1560, 360)     # x0, y0, x1, y1 — product imagery band
GL19_M1_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs", "gl19_m1")
BAND_IMAGES = [os.path.join(GL19_M1_DIR, n) for n in (
    "flat_console_vase.png", "lifestyle_easel_shelf.png",
    "lifestyle_floor_terracotta.png")]


def _font(name, px):
    return ImageFont.truetype(FONTS + name, px)


def _tracked(draw, xy, text, font, fill, tracking, anchor_centre=True):
    """Draw text with manual letterspacing; returns total advance width."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = xy[0] - total / 2 if anchor_centre else xy[0]
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=font, fill=fill)
        x += w + tracking
    return total


def _ground(W, H, seed=7, rows=True):
    """Ink ground + warm centre lift + orchard-row verticals.

    The lift is computed in float and dithered before quantising, otherwise an
    8-bit ramp this shallow (9 levels over 2000px) shows visible contour bands.
    """
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.5, H * 0.40
    dist = np.hypot((xx - cx) / (W * 0.55), (yy - cy) / (H * 0.95))
    t = np.clip(1.0 - dist, 0.0, 1.0)
    lift = 10.0 * (t * t * (3 - 2 * t))
    rng = np.random.default_rng(seed)
    lift = lift + rng.uniform(-0.5, 0.5, lift.shape)
    base = np.array([0x15, 0x12, 0x0D], np.float32)
    a = np.clip(base[None, None, :] + lift[..., None], 0, 255).astype(np.uint8)
    im = Image.fromarray(a, "RGB")

    if rows:
        d = ImageDraw.Draw(im, "RGBA")
        rnd = random.Random(seed)
        step = W / 17.0
        x = step * 0.35
        while x < W:
            hgt = H * rnd.uniform(0.22, 0.58)
            alpha = int(255 * rnd.uniform(0.10, 0.22))
            d.line([(x, H), (x, H - hgt)], fill=(0x8F, 0x86, 0x76, alpha),
                   width=max(1, round(0.75 * SS)))
            x += step * rnd.uniform(0.75, 1.3)
    return im


def _cover_crop(im, tw, th):
    """Cover-crop `im` to the tw:th aspect (centred), then resize to it."""
    sw, sh = im.size
    if sw / sh > tw / th:
        nw = round(sh * tw / th)
        x0 = (sw - nw) // 2
        im = im.crop((x0, 0, x0 + nw, sh))
    else:
        nh = round(sw * th / tw)
        y0 = (sh - nh) // 2
        im = im.crop((0, y0, sw, y0 + nh))
    return im.resize((tw, th), Image.LANCZOS)   # photo content: LANCZOS is fine here


def _band(im, SS, rect, image_paths, gap=16, mat=2):
    """Paste cover-cropped product photos into `rect` (final-res coords)."""
    x0, y0, x1, y1 = [v * SS for v in rect]
    bw, bh = x1 - x0, y1 - y0
    n = len(image_paths)
    g = gap * SS
    tw = (bw - (n + 1) * g) // n
    d = ImageDraw.Draw(im)
    x = x0 + g
    for path in image_paths:
        tile = _cover_crop(Image.open(path).convert("RGB"), tw, bh)
        im.paste(tile, (round(x), round(y0)))
        m = mat * SS
        d.rectangle([x - m / 2, y0 - m / 2, x + tw + m / 2, y0 + bh + m / 2],
                    outline=STONE, width=m)
        x += tw + g


def _badge_img(R, geom, ring, handle):
    """Transparent PNG of the badge, plus the offset of the ring centre."""
    (mx, my), rneed = extent(geom)
    pad = R * (rneed + 0.15)
    size = int(2 * pad)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
           + badge_group(R, pad - mx * R, pad - my * R, geom, ring, handle) + "</svg>")
    im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert("RGBA")
    return im, (pad - mx * R, pad - my * R)


def banner(path, W=1600, H=400, geom="diagonal", ring=PINE, handle=BONE,
           word="hoto Art", tagline="ART · PRINTED TO ORDER",
           cap_frac=0.21, base_frac=0.50, tag_frac=0.665,
           lockup_cx=None, band_images=None, band_rect=BAND_ZONE):
    w, h = W * SS, H * SS
    im = _ground(w, h)

    cx = (lockup_cx if lockup_cx is not None else W / 2) * SS

    cap = h * cap_frac                      # cap height of the wordmark
    fsize = int(cap / 0.70)                 # Fraunces cap height ~0.70 em
    f = _font("fraunces-latin-400-normal.ttf", fsize)
    d = ImageDraw.Draw(im)
    baseline = h * base_frac

    # Badge stands in for the Q: ring diameter ~= cap height, ring top on the
    # cap line, so its centre sits half a cap height above the baseline.
    R = cap * 0.52
    ring_cy = baseline - cap * 0.5
    bim, (bcx, bcy) = _badge_img(R, geom, ring, handle)
    gap = cap * 0.07
    tw = d.textlength(word, font=f)
    total = 2 * R + gap + tw
    x0 = cx - total / 2

    im.paste(bim, (round(x0 + R - bcx), round(ring_cy - bcy)), bim)
    d.text((x0 + 2 * R + gap, baseline), word, font=f, fill=BONE, anchor="ls")

    tf = _font("inter-latin-500-normal.ttf", int(h * 0.055))
    _tracked(d, (cx, h * tag_frac), tagline, tf, STONE, tracking=h * 0.055 * 0.34)

    if band_images:
        _band(im, SS, band_rect, band_images)

    out = im.resize((W, H), Image.BOX)   # area average: no ringing overshoot
    out.save(path, quality=94, optimize=True)
    return out


def icon(path, size=500, geom="diagonal", ring=PINE, handle=BONE,
         ground=INK, fill=0.72):
    s = size * SS
    im = Image.new("RGB", (s, s), ground)
    (mx, my), rneed = extent(geom)
    R = (s / 2.0) * fill / rneed
    bim, (bcx, bcy) = _badge_img(R, geom, ring, handle)
    im.paste(bim, (int(s / 2 - mx * R - bcx), int(s / 2 - my * R - bcy)), bim)
    out = im.resize((size, size), Image.BOX)   # area average: no ringing overshoot
    out.save(path, quality=95, optimize=True)
    return out
