# Qhoto Art — store visual identity (GL-10a)

Delivered 2026-07-24. Brief: `docs/2026-07-24-gl10a-store-visual-identity-brief.md`.
System of record: `Qrchard/brand_sheet.pdf`.

## Upload these

| File | Where | Spec |
| --- | --- | --- |
| `qhoto-shop-icon-500.png` | Shop Manager → shop icon | 500×500, 12 KB |
| `qhoto-shop-banner-1600x400.png` | Shop Manager → big banner | 1600×400, 101 KB |
| `qhoto-shop-banner-mini-1600x213.png` | only if you switch to the mini layout | 1600×213, 57 KB |

`.jpg` alternates are included; the PNGs are smaller *and* lossless here, so
prefer them. Both are far under Etsy's 1 MB limit. Upload is manual in Shop
Manager — not an API write, so nothing publishes without you doing it.

## Locked decisions

**D1 — Qhoto accent: Pine `#23402F`.** Not invented: sampled directly from the
Qhoto badge already drawn on `brand_sheet.pdf` p2. The sheet had the green, it
just never labelled it. (Sampling the same way reads Qrchard's ring as
`#5A1A23` against its documented `#5C1A24`, so the method is accurate to ~1%.)
**Add this to the brand sheet as Qhoto's official accent.**

**D2 — wordmark: "Qhoto Art"** — badge as the Q, then "hoto Art" in Fraunces.

**D3 — badge source: redrawn as SVG.** Vector extraction was impossible:
`brand_sheet.pdf` is raster throughout (four 300 dpi JPEGs, no embedded fonts
or paths). Geometry was instead *measured* off the p1 ICON ONLY lockup rendered
at 400 dpi, normalised to ring outer radius = 1.0 — see the docstring in
`badge.py` for every measured value.

**Letterform — the reason the tail changed.** Qrchard is a Q masquerading as an
**O** ("Orchard"). Qhoto is a Q masquerading as a **P** ("Photo"). That is a
different job, so the tail cannot simply be rotated:

- Tail at 6 o'clock (as the sheet draws Qhoto) reads as an **exclamation mark**
  — bowl plus centred stem plus dot. Fails at every size.
- Tail rotated to 112° or 135° reads as a Q with its tail on the wrong side.
- Tail moved to the **left of the bowl** as a descending stem reads as a
  lowercase **p** — which is the intended illusion, and still a Q on inspection.

Final geometry is the midpoint of two candidates (`p-e` and `p-stem-lean`):
lean 94.5°, stem top −0.15, half-width 0.1625, apex 1.76, dot 1.575 r 0.1815,
offset 0.58R left. Blade width and dot size stay in Qrchard's measured family.

**Colourway — differs by application, exactly as the sheet does.**
The sheet uses accent-ring/bone-handle for the *wordmark* and
bone-ring/accent-handle for the *icon-only* lockup. Same split here:

- **Banner wordmark** — Pine ring + Bone handle on Ink.
- **Icon** — Bone badge on a **Pine ground**.

The icon ground is the one deliberate departure from the sheet, and it was
forced by measurement. Pine on Ink is **1.6:1** contrast; below 40 px the stem
vanishes and the mark reads as an **O** — the worst possible failure, since O is
precisely what Qrchard's badge means. Putting the accent in the ground gives
**8.7:1**, keeps a dark saturated field, and makes the green the thing that
registers in an Etsy grid. Note this weakness is inherited, not introduced: the
sheet's own Qrchard icon-only lockup is oxblood-on-Ink at **1.45:1**. It has
simply never been tested at avatar size. Worth fixing for Qrchard too.

## Rebuilding

```
python3 build_final.py     # writes all deliverables (GL10A_OUT=<dir>)
python3 verify.py .        # 27 assertions: dimensions, weight, exact hexes,
                           # circle-crop safety, banner safe zone, legibility
```

Requires `cairosvg`, `numpy`, `Pillow`, and the bundled `fonts/` (Fraunces
400/500-italic/600 + Inter 400/500/600, converted from the Google Fonts woff2
originals via `@fontsource`).

Downsampling uses 4× supersample + area-average (`Image.BOX`), not LANCZOS —
LANCZOS ringing pushed edge pixels to `#FFF6E8`, breaking the exact-palette
requirement. `verify.py` asserts this and will catch a regression.

## Deferred (not in GL-10a)

Rest of GL-10: About text, shop sections, policies, SEO/listing copy. Also: a
full Qhoto page for the brand sheet, and any listing-image or social templates.
