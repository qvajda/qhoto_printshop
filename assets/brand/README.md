# Qhoto Art — store visual identity (GL-10a, banner rebuilt GL-10d)

Delivered 2026-07-24. Brief: `docs/2026-07-24-gl10a-store-visual-identity-brief.md`.
Banner rebuild 2026-08-08 (GL-10d): `docs/2026-08-07-gl10b-banner-icon-decision.md`,
`docs/2026-08-08-gl10d-banner-kickoff.md`.
System of record: `Qrchard/brand_sheet.pdf`.

## Upload these

| File | Where | Spec |
| --- | --- | --- |
| `qhoto-shop-icon-500.png` | Shop Manager → shop icon | 500×500, 12 KB |
| `qhoto-shop-banner-1600x400.png` | Shop Manager → big banner | 1600×400, 346 KB |
| `qhoto-shop-banner-mini-1600x213.png` | only if you switch to the mini layout | 1600×213, 57 KB |

`.jpg` alternates are included; the PNG is smaller for the icon, but the
banner's photographic band makes the JPEG the smaller file now (106 KB vs
346 KB) — either is far under Etsy's 1 MB limit, use whichever you prefer.
Upload is manual in Shop Manager — not an API write, so nothing publishes
without you doing it.

## GL-10d — the banner now carries a product-imagery band

The big banner's lockup (badge + "Photo Art" + tagline) moved off centre to
`LOCKUP_CX = 450` (see `banner.py`) to make room for a band of three
composited mockup renders on the right, cover-cropped from
`outputs/gl19_m1/` — the deterministic, owner-reviewed pool from GL-19b, not
a new generation. Current picks: `flat_console_vase.png`,
`lifestyle_easel_shelf.png`, `lifestyle_floor_terracotta.png`, all the same
approved wildflower artwork in different hand-authored scenes. Swap the
`BAND_IMAGES` list in `banner.py` to change them; nothing generative touches
the shipped pixels, so the build stays reproducible.

**The mini banner (`qhoto-shop-banner-mini-1600x213.png`) is unchanged and
stays type-led — no band.** At 213 px tall a product band isn't legible;
this is a deliberate scope decision, not an oversight.

**The tagline (`ART · PRINTED TO ORDER`) is unchanged too.** It predates the
storefront checklist's shop tagline; they're different surfaces and the
lockup wasn't crowded enough by the band to force dropping it.

**The wordmark spelling is still "Qhoto Art"** (badge-as-Q + "hoto Art" in
Fraunces), inherited from GL-10a, not re-decided here — all *copy* uses
`QhotoArt`, but the wordmark's letterspacing question is separate and was
already settled.

### `etsy-banner.png` / `shop_icon.jpg` — retired

Both were untracked, off-system files that predated GL-10a and were never
produced by `build_final.py`. Reasons they're retired, not just superseded:
`etsy-banner.png` measured 1600×896 (1,497.5 KB) — a size matching no
documented Etsy banner format — and carried a visible garbled-text
generation artifact together with a promise mismatch (it didn't depict what
the shop actually sells). Do not resurrect them from the folder; the
current pair above is the one to upload.

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
python3 verify.py .        # 36 assertions across 20 check() call sites:
                           # dimensions+weight+no-alpha (3 x 5 files = 15),
                           # palette (5), circle-crop (3), lockup safe zone
                           # (4), imagery band (4, GL-10d), legibility (5 x
                           # 5 downscales). Count executed assertions, not
                           # call sites — the dimensions/legibility blocks
                           # each loop, so grepping `check(` undercounts.
```

Requires `cairosvg`, `numpy`, `Pillow`, and the bundled `fonts/` (Fraunces
400/500-italic/600 + Inter 400/500/600, converted from the Google Fonts woff2
originals via `@fontsource`). `cairosvg` needs a native `libcairo-2.dll` on
Windows — it isn't bundled by pip; install the GTK3 runtime (e.g.
`winget install tschoonj.GTKForWindows`) and put its `bin/` on `PATH`.

Downsampling uses 4× supersample + area-average (`Image.BOX`), not LANCZOS —
LANCZOS ringing pushed edge pixels to `#FFF6E8`, breaking the exact-palette
requirement. `verify.py` asserts this and will catch a regression. This
still governs the flat vector art (badge, ground, type); the imagery band's
product photos are cover-cropped and resized with `Image.LANCZOS` instead —
correct for photographic content, and outside what that rule protects.

**Palette and lockup safe-zone checks are region-scoped (GL-10d), not
global.** `verify.py`'s brightest/greenest-pixel and content-bbox/centroid
checks now search only `banner.LOCKUP_ZONE` — a global search breaks the
moment a photograph is in frame (a window highlight out-brightens Bone, a
botanical print out-greens Pine). `LOCKUP_ZONE`, `LOCKUP_CX`, and `BAND_ZONE`
live once in `banner.py` and are imported by `verify.py`, so the two can't
drift apart.

## Deferred (not in GL-10a)

Rest of GL-10: About text, shop sections, policies, SEO/listing copy. Also: a
full Qhoto page for the brand sheet, and any listing-image or social templates.
