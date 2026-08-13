# GL-10d — banner rebuild coding session kickoff (2026-08-08)

**Session type:** Claude Code, one sitting, `assets/brand/` only.
**Decision document (the *what*):** `docs/2026-08-07-gl10b-banner-icon-decision.md`.
**This file (the *how*):** what is already on disk, what will break, what must
not move.

**Why this file exists.** The decision document is deliberately self-contained
and it is correct — but it was written from a competitor sweep, not from the
code. It does not know what `assets/brand/` already contains, and it does not
know that three of `verify.py`'s existing assertions are **structurally
incompatible** with putting a photograph on the banner. Both facts change the
shape of the session. Read the decision document for *why*; read this for
*where*.

---

## 1. The one-paragraph version

GL-10a's banner already renders at 1600 × 400, on the right ground, in the
right palette, under 1 MB. **You are not rebuilding it.** You are adding a band
of product imagery composited from already-approved mockup renders, moving the
type lockup to accommodate it, and — the part that carries the actual risk —
**re-parameterising `verify.py` so it still proves something, with more
assertions at the end than it had at the start.** The icon is not touched at
all.

---

## 2. Read first, in this order

1. `docs/2026-08-07-gl10b-banner-icon-decision.md` §4.2 (what changes and what
   does not), §4.3 (target values), §7 (definition of done).
2. `assets/brand/README.md` — the locked GL-10a decisions and the rebuild
   commands. **Note the last section: LANCZOS was rejected for a measured
   reason.** Downsampling is 4× supersample + `Image.BOX` area-average, because
   LANCZOS ringing pushed edge pixels to `#FFF6E8` and broke the exact-palette
   assertions. Do not "improve" the resampling.
3. `assets/brand/verify.py` in full. It is the spec.
4. `assets/brand/banner.py` — `banner()` and `_ground()`.
5. `assets/brand/build_final.py` — the five build steps.

Do **not** read the wider go-live plan for this. It is 160 KB and nothing in it
changes what you build here.

---

## 3. Ground truth on disk — this is narrower than "rebuild the banner"

`assets/brand/` already contains, all currently passing:

| File | State |
| --- | --- |
| `qhoto-shop-banner-1600x400.png` | **already the correct size**, 101 KB, Ink ground, Pine ring + Bone wordmark |
| `qhoto-shop-banner-1600x400.jpg` | JPEG alternate, quality 92, `subsampling=0` |
| `qhoto-shop-banner-mini-1600x213.png` | mini layout, 57 KB |
| `qhoto-shop-icon-500.png` | **500 × 500, 12 KB — finished. Do not touch it.** |
| `qhoto-badge-icon.svg`, `qhoto-badge-wordmark.svg` | reusable vector |

**The two files to be retired are the odd ones out:** `etsy-banner.png`
(1600 × 896, 1,497.5 KB — measured, confirmed) and `shop_icon.jpg`. Both are
untracked, both are the *live* pair, and neither is produced by
`build_final.py`. They are off-system artefacts that predate GL-10a.

**Consequence:** the deliverable is a change to `banner.banner()` plus new
assertions in `verify.py`. It is not a new pipeline, a new module, or a new
asset directory.

---

## 4. The change, precisely

### 4.1 What moves

`banner.banner()` currently composes one centred lockup: badge-as-Q + "hoto
Art" in Fraunces on the baseline at `base_frac`, tagline
`ART · PRINTED TO ORDER` in Stone letterspaced at `tag_frac`, over `_ground()`'s
Ink field with its warm centre lift and orchard-row verticals.

**Add a product-imagery band.** Composition is yours to choose against the
actual lockup, but the constraints are fixed:

- The band carries **composited mockup renders of real QhotoArt prints in the
  existing hand-authored scenes** — see §5 for the eligible pool.
- The Ink ground stays the field. The band sits **on** it; it does not become a
  full-bleed photograph. The corner pixel `ban[4, 4]` must remain Ink — there
  is an assertion on exactly that, and it should stay.
- The lockup stays legible and stays inside the safe zone. It may move off
  optical centre; that is the point, and it is what forces §6.

### 4.2 What must not move

Every one of these has a passing assertion behind it. Changing any of them is
out of scope for this session and needs the owner:

- Ink ground, Pine `#23402F`, Bone, Stone, Charcoal.
- Fraunces + Inter, and the bundled `fonts/`.
- `badge.GEOM["qhoto"] = (94.5, -0.15, 0.1625, 1.76, 1.575, 0.1815, -0.58)`.
- The icon, in every respect — file, ground, fill fraction, colourway.
- `SS = 4` supersample and `Image.BOX` downsampling.

---

## 5. Where the imagery comes from

**`outputs/gl19_m1/` — 13 rendered composites, deterministic, size-checked,
owner-reviewed and approved during GL-19b.** That is the eligible pool, and it
is eligible *because* it was reviewed, not because it is convenient. Named
scenes include `flat_clips_windowlight`, `flat_console_vase`,
`lifestyle_sofa_goldenhour`, `lifestyle_reading_nook`,
`lifestyle_floor_terracotta`, `lifestyle_easel_shelf`.

The bundles themselves live in `assets/mockups/primary/portrait/`, and
`pipeline/mockup_render.py` can re-render any of them if you need a different
crop or a different artwork in the frame.

**Two rules on the imagery, both from the decision document:**

1. **Composited, never generated.** Nano Banana Pro is **role C** — concept
   exploration only, nothing generated ships. A generative model cannot hold an
   exact palette value, cannot reproduce a measured mark, and cannot be
   regenerated identically later. Everything in the band must be reproducible
   by re-running the build.
2. **The band must depict what the shop actually sells** — botanical,
   minimalist, celestial, mid-century. This is the root fix for the live
   banner's promise mismatch, so a scene showing figurative portrait work would
   reintroduce the defect being removed.

---

## 6. ⚠️ The verifier problem — the sharp part of this session

`verify.py`'s palette assertions are written as **global extrema over the whole
image**. That is a valid instrument for flat vector art and an invalid one the
moment a photograph is in frame. Three assertions will break, and they will
break *misleadingly* — as a palette failure, when the actual cause is a
photographic highlight:

| Line | Assertion | Why the band breaks it |
| --- | --- | --- |
| 56 | brightest pixel in the banner **is Bone** (`flat.sum(1).argmax()`) | any specular highlight — a window, a white wall, paper stock — will out-brighten Bone `#E7E0D1`, which is not a bright colour |
| 60 | greenest pixel **is Pine** (`argmax` of G−R) | a botanical print or a plant in a styled scene will out-green Pine `#23402F` |
| 80 | content mask `b.sum(2) > 300`, then x-range 200–1400, x-range 300–1300, midpoint 800 ± 6, y-range 20–380 | the mask was written to catch "wordmark + tagline, not the faint rows". Every mid-tone pixel of the band satisfies it, so the content bbox becomes the whole band and the centroid check fails immediately |

**The correct fix is to scope each assertion to a region, not to relax its
tolerance and not to delete it.** Define the lockup zone and the imagery band
as explicit rectangles in the module, then:

- assert Bone is the brightest pixel **within the lockup zone**;
- assert Pine is the greenest pixel **within the lockup zone**;
- assert the content-mask bbox and centroid **within the lockup zone**, against
  that zone's own centre rather than 800;
- and add the band's own assertions — that it lands where it is supposed to,
  that it does not intrude into the lockup zone, that the corner is still Ink.

**This is why the definition of done is stated as a count.** A session that
loosens three tolerances and adds one new check has *lost* the verifier while
appearing to satisfy the brief. GL-10b flagged this in its own words: *losing
the verifier is the actual risk of this change.*

### 6.1 The new assertion: no alpha channel

Etsy renders transparency as black. Nothing currently catches it, and
**the imagery band is exactly the path that introduces it** — the mockup
composites and `_badge_img()` are RGBA, so a `paste()` without a mask, or a
save from an un-flattened composite, produces an alpha channel that no existing
check will see. Assert `im.mode == "RGB"` (or that no alpha band exists) on
every file in `SPEC`.

### 6.2 The one that already exists

**The `< 1 MB` check is already at `verify.py` line 45.** GL-10b's first draft
proposed adding it and had to correct itself. Do not add a second one; do
confirm the new banner still passes it, since a photographic band will push the
PNG well past 101 KB. If PNG goes over, the JPEG alternate at quality 92 is the
intended escape hatch — `build_final.py` already emits one.

---

## 7. Open sub-decisions — surface these, do not silently resolve them

1. **The wordmark string.** Three spellings exist: the registered shop is
   `QhotoArt`, GL-10a's wordmark sets **"Qhoto Art"**, the retired live icon
   read "Qhoto-Art". **All copy uses `QhotoArt`** — that is settled and already
   applied in the storefront checklist. Whether the *wordmark* sets it as one
   word, two, or hyphenated is a design question to be decided against the
   actual lockup. GL-10a chose "Qhoto Art" for the letterspacing. Flagged so it
   is not inherited by accident.
2. **The mini banner.** `qhoto-shop-banner-mini-1600x213.png` is built and
   verified. Does it get a band too, or stay type-led? At 213 px tall a product
   band is probably not viable. **Recommendation: leave it unchanged**, and say
   so in the README rather than leaving a reader to wonder whether it was
   forgotten.
3. **The tagline.** `ART · PRINTED TO ORDER` predates the shop tagline chosen
   in the storefront checklist (`AI-made botanical & minimalist art prints,
   unframed`). They are different surfaces and need not match — but if the band
   crowds the lockup, the tagline is the first thing to consider dropping, and
   that is a decision, not a layout tweak.

---

## 8. Definition of done

- [ ] New banner emitted by `python3 build_final.py`: **1600 × 400, no alpha,
      < 1 MB**, imagery band composited from `outputs/gl19_m1/` renders.
- [ ] `python3 verify.py .` green, with **more assertions than it started
      with**. Existing palette/geometry/dimension/circle-crop/legibility checks
      intact; safe-zone and palette checks **re-parameterised to regions**, not
      relaxed; new no-alpha check added.

      ⚠️ **Count executed assertions, not `check(` call sites.** There are
      **15 call sites** but **27 executed assertions**, because two of them sit
      in loops: the dimensions block runs 2 checks over 5 files (10), and the
      legibility block runs 1 check over 5 downscales (5). Palette 5,
      circle-crop 3, safe zone 4. 10+5+3+4+5 = 27, which is the number the
      README quotes. A session that greps for `check(`, finds 15, and concludes
      the README is stale will then "restore" a count that was never lost —
      and can delete real assertions while believing it added some.
- [ ] Icon untouched, still passing, still 12 KB.
- [ ] `assets/brand/README.md` updated: the new banner's composition, the
      re-parameterised assertions and the new count, **and a short record that
      `etsy-banner.png` / `shop_icon.jpg` are retired and why** — promise
      mismatch, a visible garbled-text generation artifact, 1,497.5 KB, and
      1600 × 896 matching no documented Etsy format. Written down so they
      cannot be resurrected by someone who finds them in the folder.
- [ ] Commit. Owner uploads both files manually in Shop Manager — **not an API
      write**, so nothing goes live without him.

---

## 9. Constraints on the session itself

- **Stay inside `assets/brand/`.** Reading from `outputs/gl19_m1/` and
  `assets/mockups/` is fine; writing outside `assets/brand/` is not.
- **Do not touch `pipeline/`.** As of 2026-08-08 the repo has two live trees —
  master and `worktree-gl7-cron-orchestrator`, which is mid-soak (GL-38). This
  session is safe to run *only* because `assets/brand/` is disjoint from
  everything the soak executes. That property is the whole reason it can go
  before the merge; do not spend it.
- **Do not run anything from the main checkout that touches the DB or
  Telegram.** One bot token, one `getUpdates` cursor, two trees. Nothing in
  this session needs either.
- **`cairosvg`, `numpy`, `Pillow`** and the bundled `fonts/` are the
  dependencies. No new ones.

---

## 10. What this session is not

Not the icon (done). Not the storefront copy (owner-manual, GL-10). Not the
listing-copy template (GL-10c, post-launch). Not a move away from Qrchard's
system — **D-A resolved to A1 and was ratified 2026-08-07**; palette, type,
badge geometry and every `verify.py` constant are settled. If the composition
seems to want a different colourway, that is a signal to change the composition,
not the brand.
