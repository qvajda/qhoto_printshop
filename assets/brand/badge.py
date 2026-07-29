"""Qrchard/Qhoto badge — parametric reconstruction.

Geometry measured from brand_sheet.pdf page 1 "ICON ONLY" lockup rendered at
400 dpi (the PDF is raster: 300 dpi JPEGs, no vector paths to extract).
All units normalised to ring outer radius = 1.0, origin = ring centre.

Measured (Qrchard, oxblood handle):
  stroke / R      = 0.1414
  wedge vertex A  = (-0.0218, +0.2056)
  wedge vertex B  = (-0.2109, +0.5838)
  wedge apex      = (+1.4145, +1.0645)   -> 1.770 along axis
  dot centre      = (+1.2371, +1.0722)   -> 1.637 along axis, r = 0.1929
  handle axis     = 40.91 deg below horizontal
Measured (Qhoto as drawn on page 2 sibling row, low-res source):
  back edge 0.221 along axis, half-width 0.289, tip 1.20, dot 1.325 r 0.162
"""
import math

INK      = "#15120D"
CHARCOAL = "#211C16"
OXBLOOD  = "#5C1A24"
BONE     = "#E7E0D1"
STONE    = "#8F8676"
PINE     = "#23402F"   # D1 — sampled from the sheet's Qhoto badge

STROKE = 0.1414

# (axis_deg, back_u, half_w, apex_u, dot_u, dot_r, offset)
# `offset` shifts the handle sideways off the ring centre, in R units, positive
# = to the right of the axis direction. A P's stem sits at the LEFT of the bowl
# and descends past it, so the Qhoto tail needs a negative offset on a near-
# vertical axis — a centred vertical stem reads as an exclamation mark instead.
QR = (0.171, 0.211, 1.830, 1.637, 0.1929)   # measured Qrchard blade metrics
GEOM = {
    # --- reference ---
    "diagonal":        (40.91, *QR, 0.0),       # Qrchard, unmodified
    "vertical-sheet":  (90.0, 0.221, 0.289, 1.330, 1.325, 0.1620, 0.0),
    "vertical-qrchard": (90.0, *QR, 0.0),
    # --- P candidates ---
    "p-diag-left":     (135.0, *QR, 0.0),       # radial tail to lower-left
    "p-lean-left":     (112.0, *QR, 0.0),
    "p-stem":          (90.0, 0.05, 0.150, 1.70, 1.52, 0.1700, -0.52),
    "p-stem-tight":    (90.0, 0.05, 0.150, 1.70, 1.52, 0.1700, -0.64),
    "p-stem-lean":     (99.0, 0.05, 0.150, 1.70, 1.52, 0.1700, -0.52),
}


def _axis(geom):
    ang, back_u, half_w, apex_u, dot_u, dot_r, off = GEOM[geom]
    t = math.radians(ang)
    ux, uy = math.cos(t), math.sin(t)
    vx, vy = uy, -ux          # +v is to the right of the axis direction
    return (ux, uy), (vx, vy), (back_u, half_w, apex_u, dot_u, dot_r, off)


def extent(geom):
    """(bbox centre, r_needed) in R units: centre of the whole assembly's bbox
    and the radius of the smallest circle on that centre containing it. Used to
    fit the badge inside Etsy's circular crop."""
    (ux, uy), (vx, vy), (back_u, half_w, apex_u, dot_u, dot_r, off) = _axis(geom)
    dx, dy = dot_u * ux + off * vx, dot_u * uy + off * vy
    ax, ay = apex_u * ux + off * vx, apex_u * uy + off * vy
    x0 = min(-1.0, dx - dot_r, ax); x1 = max(1.0, dx + dot_r, ax)
    y0 = min(-1.0, dy - dot_r, ay); y1 = max(1.0, dy + dot_r, ay)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    pts = [(-1, -my), (1, -my), (-mx, -1), (-mx, 1),
           (dx - mx, dy - my + dot_r), (dx - mx, dy - my - dot_r),
           (dx - mx + dot_r, dy - my), (dx - mx - dot_r, dy - my),
           (ax - mx, ay - my)]
    r = max(math.hypot(*p) for p in pts)
    return (mx, my), r


def badge_svg(size, geom="p-stem", ring=PINE, handle=BONE,
              ground=None, fill=0.76, cx=None, cy=None, R=None):
    """Badge centred by its own bounding box and scaled so the assembly fits
    within `fill` of the frame's inscribed circle (Etsy crops icons round)."""
    (mx, my), rneed = extent(geom)
    if R is None:
        R = (size / 2.0) * fill / rneed
    cx = size / 2.0 - mx * R if cx is None else cx
    cy = size / 2.0 - my * R if cy is None else cy
    (ux, uy), (vx, vy), (back_u, half_w, apex_u, dot_u, dot_r, off) = _axis(geom)

    def P(u, v):
        v = v + off
        return (cx + (u * ux + v * vx) * R, cy + (u * uy + v * vy) * R)

    a = P(back_u, -half_w)
    b = P(back_u, +half_w)
    apex = P(apex_u, 0)
    dot = P(dot_u, 0)

    parts = []
    if ground:
        parts.append(f'<rect width="{size}" height="{size}" fill="{ground}"/>')
    parts.append(
        f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{R*(1-STROKE/2):.3f}" '
        f'fill="none" stroke="{ring}" stroke-width="{R*STROKE:.3f}"/>')
    parts.append(
        f'<path d="M {a[0]:.3f} {a[1]:.3f} L {b[0]:.3f} {b[1]:.3f} '
        f'L {apex[0]:.3f} {apex[1]:.3f} Z" fill="{handle}"/>')
    parts.append(
        f'<circle cx="{dot[0]:.3f}" cy="{dot[1]:.3f}" r="{R*dot_r:.3f}" '
        f'fill="{handle}"/>')
    body = "\n  ".join(parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
            f'height="{size}" viewBox="0 0 {size} {size}">\n  {body}\n</svg>')


def badge_group(R, cx, cy, geom="p-stem", ring=PINE, handle=BONE):
    """Badge as a bare <g> at arbitrary position/size, for lockups."""
    (ux, uy), (vx, vy), (back_u, half_w, apex_u, dot_u, dot_r, off) = _axis(geom)

    def P(u, v):
        v = v + off
        return (cx + (u * ux + v * vx) * R, cy + (u * uy + v * vy) * R)

    a, b, apex, dot = P(back_u, -half_w), P(back_u, half_w), P(apex_u, 0), P(dot_u, 0)
    return (f'<g>'
            f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{R*(1-STROKE/2):.3f}" '
            f'fill="none" stroke="{ring}" stroke-width="{R*STROKE:.3f}"/>'
            f'<path d="M {a[0]:.3f} {a[1]:.3f} L {b[0]:.3f} {b[1]:.3f} '
            f'L {apex[0]:.3f} {apex[1]:.3f} Z" fill="{handle}"/>'
            f'<circle cx="{dot[0]:.3f}" cy="{dot[1]:.3f}" r="{R*dot_r:.3f}" '
            f'fill="{handle}"/></g>')
