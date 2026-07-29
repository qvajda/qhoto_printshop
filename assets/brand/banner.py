"""Qhoto Art — Etsy shop banner (1600x400) and mini banner (1600x213).

Echoes the Qrchard banner application on brand_sheet.pdf p2: Ink ground with a
soft warm centre lift, low-opacity "orchard row" verticals rising from the
bottom edge, badge-as-Q wordmark in Fraunces centred, letterspaced Inter caps
tagline in Stone below. Rendered at 3x and downsampled.
"""
import io
import math
import random

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from badge import badge_group, extent, INK, CHARCOAL, BONE, STONE, PINE, GEOM

SS = 4  # supersample factor
FONTS = "fonts/"


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
           cap_frac=0.21, base_frac=0.50, tag_frac=0.665):
    w, h = W * SS, H * SS
    im = _ground(w, h)

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
    x0 = (w - total) / 2

    im.paste(bim, (round(x0 + R - bcx), round(ring_cy - bcy)), bim)
    d.text((x0 + 2 * R + gap, baseline), word, font=f, fill=BONE, anchor="ls")

    tf = _font("inter-latin-500-normal.ttf", int(h * 0.055))
    _tracked(d, (w / 2, h * tag_frac), tagline, tf, STONE, tracking=h * 0.055 * 0.34)

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
