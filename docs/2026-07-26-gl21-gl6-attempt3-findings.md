# GL-21 + GL-6 attempt 3 — findings (2026-07-26/27)

Branch `feat/gl21-matte-compositor`, cut from `feat/gl5-mockup-compositor`.
Executes `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` phases
P0–P3. Attempt 2's `feat/gl6-scene-library` was reference only; nothing was
cherry-picked from it but ideas.

**Recommendation: PR #2 is mergeable once the four bundles below are
owner-approved.** Detail in §7.

> **Superseded in part by §8 (independent review, 2026-07-28).** The four
> bundles §5 declares QA-green shipped a defect that repainted ~700 k px of
> *photograph* per scene. Fixed; re-authored; the gate now has a seventh
> detector. §7's recommendation stands only as amended in §8.

---

## 1. P1 — the compositor (GL-21)

`pipeline/mockup_render.py` was unfrozen (owner-approved) and given three
additive changes. The freeze is lifted in `CLAUDE.md` and in
`docs/SPEC_v4.10_addendum_custom_mockups.md` §2, and replaced by a standing
rule: **no bundle-side workaround for a compositor defect — fix the compositor
and cover it with a test.**

| | change | effect |
|---|---|---|
| **C1** | `borderMode=BORDER_REPLICATE` on the colour warp only | removes the black contamination; mask warp keeps `BORDER_CONSTANT` |
| **C2** | optional per-pixel `matte.png`, multiplied into the warped art's alpha | the new primitive; absent file ⇒ pre-GL-21 behaviour byte-for-byte |
| **C3** | render-time cover-crop guard, fail loud past 2 % | no silent stretch of a print a buyer pays for |

### C1, measured in isolation

New compositor vs. the attempt-2 renders, with C3 neutralised and no matte, so
the border mode is the only variable:

| scene | changed px | inside the artwork-border band | outside it | max Δ |
|---|---|---|---|---|
| flat_clips_windowlight | 1261 | 1261 | **0** | 65 |
| flat_leaning_bookstack | 1627 | 1627 | **0** | 65 |
| lifestyle_bedroom_console | 947 | 947 | **0** | 65 |
| lifestyle_sage_terracotta | 1420 | 1420 | **0** | 65 |

Every changed pixel is on the artwork border. (The plan's ~120/255 figure was
measured on the warp output; in the composite the contaminated art is blended
with the background at partial alpha, so the visible delta is smaller.)

### C3's consequence, and what it cost

The four pre-attempt-3 bundles carried quads from 0.561 to 0.693 against a 0.684
master — up to 18 % stretch. C3 refuses all of them, so 12 gallery-rendering
tests moved onto aspect-correct stub bundles (`tests/conftest.py`,
`stub_mockup_bundles`) rather than riding on production assets mid-rework, and
one new test asserts the real bundles now fail loud. That test flips back to
asserting a successful render now that P3 has re-authored them.

Suite: 504 → **517 green** (13 new).

---

## 2. P1 — the QA gate (`scripts/mockup_qa.py`)

Six detectors plus a contact-sheet generator. `mockup_qa.py demo` runs each one
against a bundle known to carry its defect and exits non-zero if any goes
silent — *a detector that cannot see a known defect is not a detector.*

| detector | demonstrated against | reading |
|---|---|---|
| fringe | C1 reverted in-process on a real bundle | 695 border px wrong, max 226/255; with C1 on, clean |
| distortion | attempt-1 `lifestyle_sage_terracotta` | quad 0.5610 vs 0.6842 = 18.01 % off |
| coverage | attempt-2 `flat_leaning_bookstack` | 14 534 px of print area not printed |
| occluder-opacity | attempt-1 clips overlay expressed as a matte | 296 px of flat mid-alpha (budget 41) |
| silhouette-vs-shadow | attempt-2 `flat_clips_windowlight` | 94.2 % of the print boundary on no photographic edge |
| key-spill | synthetic (no keyed bundle existed before P0) | 100 px of residual key |

Both defect corpora are **copies** (`outputs/attempt2_reference/`,
`outputs/attempt1_reference/`), git-ignored but kept on disk: the demo first
read the live asset dirs, and as P3 rewrote them the occluder case quietly began
measuring the fixed scene instead of the defect it claimed to reproduce.

### Detectors that were wrong first

Three of the six failed their own honesty check and were rebuilt:

- **fringe** originally compared each edge pixel to its spatial neighbours. That
  cannot see C1 at all: a blend toward a black *operand* still lies between that
  operand and the background. It now checks the warped art's own colour against
  the range its fully-covered neighbours span, keyed off the **raw warp alpha** —
  a matte rim changes how much art shows, never its colour.
- **occluder-opacity** was reading the overlay on pre-matte bundles, where the
  gain map lives in the same channel and no threshold separates a smooth relight
  field from a badly-stamped prop. It is matte-only now; that ambiguity is
  exactly what the matte primitive removes.
- **silhouette-vs-shadow** measured stand-off variation to the nearest dark
  pixel and fired on both *correct* bundles — with a matte the print silhouette
  *is* the photographed silhouette, so an uneven margin is styling. Reformulated:
  the print boundary must lie on a real photographic edge, because a derived
  matte can only ever sit on one. Derived bundles score 0.0–2.6 %; every
  hand-drawn quad from attempts 1–2 scores 73.8–100 %.

Two more gaps were found by running the gate on real output rather than on
fixtures:

- **distortion** only looked at the quad, so a matte narrower than the print
  could silently crop it — defect (d) in general form. It now also measures how
  much of the print the matte hides: a frame rebate covering a few mm is
  physical (bedroom_console hides 7.3 %), sage's 0.59 opening hid 18 % and is not.
- **coverage** inferred "printed" from a difference against the bare scene,
  which is blind wherever the artwork's pale background matches the blank paper
  it prints onto — 3101 correctly-printed px called unprinted on bedroom_console.
  It is measured from alpha now, which is colour-independent.

---

## 3. P0 — keyed generation (go)

FLUX.1 **[schnell]** on Replicate, Apache-2.0 weights, never `[dev]`.
`aspect_ratio 3:4 @ 1 megapixel` → 896×1152, matching the bundle size.
Paced at 11 s for the granted-credit 6 requests/minute cap.

| batch | prompts | delivered | cost |
|---|---|---|---|
| P0 main | 4 scene types × 3 variants × 2 keys × 2 seeds = 48 | 37 (11 lost to Replicate 404/500/timeout) | $0.14 |
| framed re-fire (aspect language) | 3 variants × 1 key × 4 seeds = 12 | 10 | $0.04 |
| shelf re-fire (square-edge language) | 3 variants × 1 key × 4 seeds = 12 | see §5 | $0.04 |

**Gate: ≥ 2 of 4 scene types must yield a clean key. Result: 3 of 4** — clips,
leaning, shelf. Every `framed` candidate failed, in both batches.

Findings worth carrying into P4:

- **Prompts must be positive-only.** The first draft leaned on "no texture, no
  mat, no inner border" — the exact anti-pattern `pipeline/generate.py` S4-c(1)
  already records (FLUX has no negative channel; "no mat" is as likely to summon
  one). Rewritten affirmatively before the batch that produced the survivors.
- **The key colour must be measured off the image, not assumed.** FLUX paints
  "vivid magenta" as a hot pink tens of Lab units from (255,0,255); keying
  against the requested colour reported every magenta panel as empty. This was a
  measurement bug, not a magenta verdict — magenta is still unevaluated as a
  scene colour. Emerald left **zero** measurable spill on every survivor,
  including scenes with plants, so magenta may simply be unnecessary.
- **Aspect is the dominant screen failure.** FLUX does not reliably hit 0.684;
  survivors land within 1 %, the rest run 0.70–0.99. Naming the proportion
  ("a tall 2:3 rectangle, three units high for every two wide") moved framed
  openings from 0.70–0.90 to 0.62–0.87 but still produced no survivor.
- **"Panel" summons a mounted board.** FLUX renders a thick panel with rounded
  corners and paints the key on its inset face, which composites as a print
  mounted on an oversized white slab. "A single thin sheet of poster paper with
  sharp square corners" is the fix.
- **Framed scenes are the hard case.** Their key edge is soft (glass sheen), so
  the derived matte carries thousands of px of mid-alpha and the print would
  render semi-transparent. Both framed candidates that passed on aspect failed
  `occluder-opacity` by 250×. A framed scene needs either a no-glass prompt or
  the seeded path on a photo.

---

## 4. P2 — the authoring tool (`scripts/scene_author.py`)

Replaces `scripts/gl6_author.py`. **Zero per-scene constants in source** — the
requirement that makes P4's ~26 bundles reachable, and the thing attempt 2 got
wrong with four hand-read quads, four margin tuples and four occluder-box lists.

- `extract` — key matte (key measured off the image) → occluders are simply
  holes → anti-aliased matte → background with the key neutralised (chroma
  dropped, luminance kept, so partial-alpha edges blend into paper not green) →
  gain map → quad = the matte's corner quad, pushed out in its own perspective
  space until it contains the whole matte, then expanded on the short axis to
  the master's aspect.
- `extract --seeded` — Plan B for a photo with no key: a coarse owner polygon
  seeds GrabCut, which refines it against the image. Built even though P0 went,
  and used for two of the four P3 scenes.
- `verify` — runs the QA gate and writes the contact sheet.
- `build` is folded into `extract`: splitting them would need an intermediate
  on-disk representation for no gain.

Carried over from attempt 2 unchanged in substance: the **chroma-OR-darkness**
prop test (neither alone works — RGB distance punches a hole through the paper's
own shadowed corner, darkness alone misses a clip's bright metal jaw) and the
**normalised-convolution gain map**.

Four derivation defects the gate caught on real output, all fixed generically:

| defect | cause | fix |
|---|---|---|
| board's top lip unprinted (4439 px) | corner quad chords across a bowed edge | quad pushed out until it contains the matte |
| bright 2 px sliver down the print's right edge | GrabCut settles a couple of px inside the object | grow the matte's **outer** boundary only, holes preserved, so a book's own edge is never printed over |
| see-through patches at 0.35 alpha | GrabCut's 1 px slivers, feathered | open + close before feathering (248 px → 12) |
| green rim outlining the print | despill too narrow: half-neutralised key exactly where the matte is partial | full removal out to 2.5× the key tolerance, feathering after |

The green rim is the one to remember: **the metrics passed it.** It was caught
on the full-frame contact sheet, and it was invisible to `key-spill` because
that test's tolerance was tighter than the extractor's own key tolerance, so the
residue sat between the two thresholds. The two are tied together now.

---

## 5. P3 — the four primary/portrait scenes

One commit per scene, each after its own full-frame pass. All four QA-green, all
four within 0.01 % of the master's aspect.

| scene | before | after | mode | quad | commit |
|---|---|---|---|---|---|
| `flat_clips_windowlight` | attempt-1 photo, quad 0.6929, curled paper vs. a straight print | keyed FLUX scene, clips are matte holes, shadow belongs to the real silhouette | keyed | 0.6841 | `384ea43`, despill fix in `a5dfde7` |
| `flat_leaning_bookstack` | attempt-1 photo, quad 0.6730; attempt 2's square notches | same photo, GrabCut matte, books are real occluders | seeded | 0.6842 | `74c409d` |
| `lifestyle_bedroom_console` | attempt-1 photo, quad 0.6316, art floating inset in the mat | same photo, print fills the frame opening | seeded | 0.6842 | `9036020` |
| `lifestyle_sage_terracotta` → **`lifestyle_shelf_books`** | 0.59 mat opening + a nested panel line | **replaced**: keyed FLUX shelf scene | keyed | 0.6842 | `a5dfde7` |

Sage was replaced, not re-authored: a 0.59 opening against a 0.684 master hides
18 % of the print. The rename carried through `mockup_templates`, the asset
manifest, the GL-19 harness and the config test; scene order (2 flat, then 2
lifestyle) is unchanged.

Two candidates were rejected before it, both on full-frame review after passing
or nearly passing the metrics:

- **framed** — every candidate in both batches. A frame's glass sheen makes the
  key edge soft, so the derived matte carries thousands of px of mid-alpha and
  the print renders semi-transparent. The two that hit aspect failed
  `occluder-opacity` by 250×.
- **`shelf_v3_emerald_s11`** — QA 6/6, but the full frame shows the print
  mounted on an oversized rounded white backing slab.

### What full-frame review caught that the metrics did not

Three defects, all invisible to the gate as it stood, all fixed generically:

1. **A green rim outlining the print** (P0 probe). The despill was too narrow;
   `key-spill`'s tolerance was tighter than the extractor's own key tolerance, so
   the residue sat between the two thresholds.
2. **A bright 2 px sliver down the print's right edge** (seeded bookstack).
   GrabCut settles a couple of px inside the object.
3. **A green hairline at the print's edge** (shelf, and the already-committed
   clips scene). The background was neutralised *weighted by the matte*, so a
   partial-matte pixel kept ~half its key chroma.

The pattern is consistent across all three attempts: **the metrics catch
geometry, the eye catches colour at the seam.** The gate now measures both, but
the full-frame check stays mandatory.

### GL-19 harness

```
flat_clips_windowlight     size=(896,1152) sha256=e5fd4a131cde
flat_leaning_bookstack     size=(896,1152) sha256=118215fa7185
lifestyle_bedroom_console  size=(896,1152) sha256=4ea202e33d2b
lifestyle_shelf_books      size=(896,1152) sha256=459b7ba5db42

4/4 scenes rendered, deterministic, size-checked OK.
```

The harness now renders what it can and names what is blocked, rather than
aborting on the first failure — GL-6 re-authored the bundles one at a time.

---

## 6. Provenance

Every bundle carries `scene.json`: model, licence, prompt, seed, key colour
(requested and measured), mode (keyed/seeded), seed polygon where used, derived
quad aspect, aspect delta, cover-crop percentage and matte coverage. Generation
manifests with prediction ids live beside the images under
`outputs/gl6_keyed*/manifest.json`.

---

## 7. Recommendation on PR #2

**Merge, once the four contact sheets are owner-approved.** Everything PR #2 was
gated on is now closed:

- the compositor defect GL-19 surfaced is fixed at source and covered by a test
  (C1), not worked around in the assets;
- all four primary/portrait bundles pass an automated six-detector gate and a
  full-frame review, and are within 0.01 % of the master's aspect;
- the GL-19 harness runs 4/4, deterministic and size-checked;
- 517/517, up from 504, with no test weakened — the one placeholder that
  asserted the real bundles fail loud has flipped back to asserting a successful
  render;
- the pipeline contract (`load_bundle` / `render_scene` / bundle-on-disk) and
  `pipeline/group_product.py` are unchanged, and no Etsy or Gelato call was made.

Two things the owner should decide before or alongside the merge:

1. **The backing-slab look.** FLUX renders a keyed print as a sheet mounted on a
   slightly larger board. On `flat_clips_windowlight` it reads as paper; on
   `lifestyle_shelf_books` it reads as a white mount. Acceptable as a product
   shot, but it is a scene-selection choice, not a defect, and P4 can prompt it
   away now that the cause is known.
2. **`lifestyle_shelf_books` sits next to `lifestyle_bedroom_console`** in the
   gallery. Both are interiors; the set has no framed-on-a-wall lifestyle scene
   any more, because framed scenes cannot currently be keyed. P4 should solve
   that with a seeded framed photo rather than another keyed attempt.

### Carried into P4

- Keyed generation is the default path; `--seeded` earns its place (two of the
  four shipped scenes use it, including the one photo the owner accepted).
- Prompt language that works: positive-only, "a single thin sheet of poster paper
  with sharp square corners", "a tall 2:3 rectangle, three units high for every
  two wide". Language that does not: "panel" (summons a mounted board), any
  negation, any framed opening with glass.
- Expect roughly 1 usable scene per 6 generated after the screen, and budget the
  same again for scenes the full-frame check rejects. At $0.003/image that is
  noise; the cost is review time, not credits.
- The screen is a **ranker**, not the gate. Two of the four shipped scenes failed
  it on a marginal check (`frontal` 0.065 vs. a 0.06 limit; `sharp` on a soft
  edge) and passed the real gate cleanly once extracted.

---

## 8. Independent review pass (2026-07-28)

A review of this session, run against the branch as committed at `8532825`.
Everything §1–§6 claims about the compositor reproduced exactly: 517/517 green,
`mockup_qa.py check` 4/4 PASS, `mockup_qa.py demo` 6/6 FIRED exit 0,
`gl19_m1_render.py` 4/4 with the four sha256 prefixes §5 records. The GL-21
compositor work needed no change.

The bundles did.

### 8.1 The defect: the overlay was repainting the whole photograph

`scene_author.py` wrote `overlay.png` as `black at alpha (1 - gain_map)`, over
the **full frame**. `gain_map` is a normalised convolution — `blur(lum·m) /
blur(m)` — so away from the panel the numerator vanishes, `g` clamps to
`GAIN_FLOOR = 0.55`, and the overlay carries a flat alpha of
`(1 - 0.55) · 255 = 115` across every pixel the print does not cover.

Measured outside the print matte, on the four shipped bundles:

| scene | mean overlay alpha | mean colour delta | px changed |
|---|---|---|---|
| flat_clips_windowlight | 102.2 | 86.8 | 727 093 |
| flat_leaning_bookstack | 100.6 | 83.6 | 668 729 |
| lifestyle_bedroom_console | 109.1 | 67.1 | 724 487 |
| lifestyle_shelf_books | 107.7 | 94.2 | 775 336 |

Roughly 65–75 % of each frame, at a quarter to a third of full range. Visibly:
every cream sunlit wall rendered grey, the warm bedroom rendered murky, and a
rounded-rectangle halo glowed around every print.

Two things this explains, which §5 and §7 attribute elsewhere:

- The "**backing-slab look**" of §7.1 is mostly this halo. It is on all four
  scenes, including the two *seeded* ones whose `background.png` is an unchanged
  attempt-1 photograph — so it cannot be a FLUX prompting artefact, and it is not
  a scene-selection choice. A residual real slab does exist on the keyed scenes;
  it is much smaller than the composites suggested.
- It is a **regression introduced by this session**. The same bundle's attempt-1
  overlay measures alpha mean 3.5 over 32 % of the frame; attempt 3's measures
  71.3 over 99.7 %.

### 8.2 Why the gate did not see it

All six detectors measure the print: its border, its key residue, its aspect,
its coverage, its holes, its silhouette. The bundle owns three layers and the
gate only ever looked at one of them. 6/6 green while two thirds of the frame
was wrong.

`§5`'s own conclusion — *"the metrics catch geometry, the eye catches colour at
the seam"* — held, and then the full-frame check that was supposed to catch the
rest was performed on the composite alone. Against the composite the wash is
plausible: it looks like the scene's own lighting. It is only obvious against
`background.png`. **A full-frame review of a composite is not a review of the
bundle; the bare scene has to be in the frame next to it.**

### 8.3 The fixes

**(1) `scene_author.py` — mask the gain map by the matte.**

```python
overlay = np.dstack([np.zeros((h, w, 3), np.uint8),
                     ((1.0 - g) * matte * 255).round().clip(0, 255).astype(np.uint8)])
```

The gain map only ever relights pixels the art covers, so outside the matte it
has nothing to do. One term, at the source, not in the assets — the standing
rule applied to the authoring tool as well as to the compositor.

**(2) `mockup_qa.py` — a seventh detector, `scene-fidelity`.**

Outside the print (dilated 5 px for the anti-aliased rim and a few px of contact
shadow), the bare composite must equal `background.png` within `SCENE_TOL = 4`,
budget `SCENE_BUDGET = 0.001` of the outside area. Measured against the
background, so it also catches any future repaint band, stamped prop or vignette
— not just this one. Its `demo` case puts the defect back on a live bundle by
unmasking the overlay: **766 362 px against a 766 px budget**, a 1000× margin.

### 8.4 Re-authoring, and what it proves

All four bundles were re-derived by re-running `scene_author.py extract` from
the sources `scene.json` records — the two FLUX scenes from
`outputs/gl6_keyed*/`, the two seeded ones from their attempt-1 photographs plus
the recorded seed polygon.

**`background.png`, `matte.png`, `meta.json` and `scene.json` came back
byte-identical on all four; only `overlay.png` changed.** That is the P2 design
goal — zero per-scene constants — demonstrated rather than asserted: the
bundles are a pure function of their source image plus the tool, and a defect
found in the tool costs one command per scene to re-issue, not a re-authoring
session.

After:

```
flat_clips_windowlight     size=(896,1152) sha256=aac4dad68e13
flat_leaning_bookstack     size=(896,1152) sha256=10f224b6430e
lifestyle_bedroom_console  size=(896,1152) sha256=fd7c742e84f6
lifestyle_shelf_books      size=(896,1152) sha256=455652e23689

4/4 scenes rendered, deterministic, size-checked OK.
```

Gate 7/7 PASS on all four (`scene-fidelity` reads **0 px** repainted, max 0/255,
on every scene — the mask is exact, not merely within budget). `demo` 7/7 FIRED,
exit 0. Suite unchanged at 517 green: the fix is authoring-time, and
`pipeline/mockup_render.py` was not touched.

Full-frame and zoom review, both, on all four re-renders: walls are the
photograph's own colour again, no halo, corners and 1-px edge strips clean, no
green residue on either keyed scene.

### 8.5 Two other findings from the same pass

- **Scope leak into PR #2.** `a5dfde7` (the shelf-scene commit) also carries
  `scripts/qops_phase0.py` and `scripts/qops_phase1.py` — 617 lines of
  ways-of-working tooling with nothing to do with GL-21 or GL-6 — and `b17ad23`
  rewrites `docs/2026-07-22-go-live-plan-of-attack.md` (+272 lines). Neither
  belongs in a mockup-compositor PR. Strip both before opening it.
- **`MASTER_ASPECT = 6656 / 9728` is a sample's pixel ratio standing in for a
  product constant** (`scene_author.py:43`, taken from `db/base_artwork/39.png`).
  Every portrait master on disk measures 0.6842, so it holds today, and
  non-primary groups skip mockups entirely (`group_product.py:347`), so the
  5x7/10x24 crops cannot reach it. But a master at any other ratio trips C3's
  2 % guard and fails the whole candidate loud. Worth deriving from the
  generator's configured aspect rather than from one file, whenever P4 touches
  this.

### 8.6 Amended recommendation

The §7 gate list is otherwise intact and now reads:

- the compositor defect GL-19 surfaced is fixed at source and covered by a test;
- the *authoring* defect this review surfaced is fixed at source and covered by
  a detector with a demonstrated 1000× margin;
- all four bundles pass a **seven**-detector gate, a full-frame review **against
  the bare scene**, and a zoom review, and are within 0.01 % of the master's
  aspect;
- harness 4/4, deterministic and size-checked; 517/517; the pipeline contract
  and `pipeline/group_product.py` unchanged; no Etsy or Gelato call made.

**Merge once the four re-rendered scenes are owner-approved**, with the two
scope-leak files stripped from the branch. The open questions §7 raises — the
residual backing slab on the keyed scenes, and the set having no framed-on-wall
lifestyle scene — are unchanged and still P4's.

---

## 9. P3.5 — pre-merge fixes (2026-07-28)

Three items were scoped (F1 parse floor, F2 a matte-hidden detector, F3
re-author `lifestyle_bedroom_console`). F2 turned out to describe one instance
of a wider defect, so this section records what was actually found and changed.

### 9.1 F1 — the gate did not parse below 3.12

`scripts/mockup_qa.py:562` nested same-quote f-strings (PEP 701). On 3.10/3.11
the whole module was a `SyntaxError`, so the authoring gate did not fail a check
— it failed to load. An undeclared floor is what let that ship, and an untracked
`scripts/_mockup_qa_py310.py` (a hand-edited copy of the same file) is what the
previous session used to work around it.

- line fixed, the duplicate copy deleted;
- `pyproject.toml` declares `requires-python = ">=3.10"`;
- `tests/test_scripts_smoke.py` imports every script and, separately, checks
  every `scripts/` and `pipeline/` module for constructs the *declared floor*
  cannot parse. That second check reads the token stream directly:
  `ast.parse(..., feature_version=(3, 10))` accepts PEP 701 (verified), and
  `compile` uses the running grammar, so neither can see this class on 3.12.

### 9.2 F2 — the matte hid print on a path nothing measured

`d_matte_hidden`, eighth detector, enforced at the same 2 % as C3, no
exceptions. Trim and occlusion are separated by shape rather than by filling
holes: the loss is measured in the quad's own rectified frame as a low quantile
of the per-row and per-column inset, so a band running the length of an edge
counts and a prop clipping a few rows does not. (A median does not work — the
bookstack's two book piles occlude the print's bottom corners across more than
half the columns and read as a 2.7 % bottom trim.)

Running it exposed two upstream bugs, both fixed at source rather than in the
bundles:

1. **`scene_screen._quad` mis-picked corners on any tilted panel.** It used the
   contour's `x+y` / `x-y` extremes, which find the true corners only while the
   edges stay roughly axis-aligned. On a panel whose bottom edge tilts — every
   leaning scene — `x-y` is minimised part-way along the *bottom* edge, not at
   the bottom-left corner. On `lifestyle_shelf_books` that put the corner 38 px
   out. Replaced with a polygon approximation to exactly four vertices, keeping
   the extremes only to order them and as a fallback.
2. **`scene_author.quad_for` expanded the quad to the master's aspect.** The art
   then filled a quad the matte was narrower than, and the matte trimmed the
   difference straight back off the design — the same loss C3 measures, taken on
   a path C3 does not watch. Combined with (1) it reached **13.3 % of the design
   on `lifestyle_shelf_books`, 6.2 % on `flat_leaning_bookstack`, 7.0 % on
   `lifestyle_bedroom_console`** — none of it visible on the current master,
   where the lost strips land on blank margin. The expansion is gone; what
   remains is a containment step (quantile, not min/max, so one stray pixel
   cannot drag an edge and take the aspect with it) plus a 1 px rim margin.
   `MASTER_ASPECT` is deleted with it, closing §8.5.

### 9.3 The C3 reference — owner decision, 2026-07-28

With the quads derived honestly, the panels' real aspects are 0.6869, 0.6661,
0.6425 and 0.7087 against a 0.6842 master, and C3 — which measured its 2 %
against the master — rejected three of the four. That reading was wrong, not the
panels:

> the primary group is **printed** at 0.6667 (8x12) and 0.7071 (A3/A2/A1), with
> the master's 0.6842 between them. A panel at 0.6661 is 0.08 % off the actual
> 8x12 print — it shows the buyer exactly what ships. No single aspect can be
> within 2 % of both ends, so a master-relative rule rejects the master itself.

C3 now measures the gap to the group's **printed ratio range**: inside it, zero;
outside, the distance to the nearer end, still capped at 2 %. Both the panel and
the artwork are checked, so a master at a genuinely wrong shape still fails loud
(the case §8.5 raised). `pipeline/image_crop` gained `SIZE_INCHES` (moved from
`group_product`, so the DPI guard and the ratio guard read one table),
`size_ratio` (A-series is exactly 1:√2 — the rounded inch conversions put
A1/A2/A3 at three different ratios) and `printed_ratio_range`.

### 9.4 F3 — `lifestyle_bedroom_console` is unfixable and is dropped

It is a **framed** scene: the photographed opening measures 0.639, and no
re-seed changes the shape of a frame in a photograph. At 3.6 % outside the
printed range it fails C3 and is removed from `mockup_templates`. It was also
the set's only framed-on-wall scene, which makes the P4a framed spike
load-bearing rather than exploratory. Owner approved firing it (2026-07-28).

Also relevant to P4a: all 18 framed candidates already on disk
(`outputs/gl6_keyed/framed_*`, `outputs/gl6_keyed_framed/`) fail
`scene_screen.py`, most on `sharp` (a soft key edge, 2.3–4.8 against a 3.0
limit) or `aspect`. The spike needs new prompt work, not re-screening.

### 9.5 State

```
gate      3/4 PASS (8 detectors); lifestyle_bedroom_console FAIL distortion
demo      8/8 FIRED, exit 0
suite     567 passed
harness   3/4 rendered, deterministic, size-checked
          flat_clips_windowlight     sha256=4a0a932b364d
          flat_leaning_bookstack     sha256=1a9940260ae9
          lifestyle_shelf_books      sha256=31c141a30e45
          lifestyle_bedroom_console  BLOCKED (3.6% outside the printed range)
```

The primary set is **2 flat + 1 lifestyle**. P4b's target of 3 flat + 7
lifestyle is therefore +9 for this group, not +6.

---

## 10. P4a — framed keyed spike (2026-07-29)

**Go/no-go: GO.** Both keyed successes to date were bare sheets; framed is
where attempt 2 died. Three batches, FLUX.1 [schnell], emerald only (magenta has
failed `aspect` on nearly every candidate in every batch to date), 60 images,
$0.17.

| batch | content | screened |
|---|---|---|
| `gl6_p4a` | framed rewrite ×3, clipsheet ×2, shelfsheet ×2, 4 seeds | 1/28 |
| `gl6_p4a2` | framed v1 × 16 fresh seeds | 2/14 |
| `gl6_p4a3` | shelfsheet ×2 × 8 fresh seeds | 0/13 |

(5 images lost to Replicate 404/timeout across the three runs.)

### 10.1 The framed `sharp` failures were glazing

All 18 pre-P4a framed candidates failed the screen, 9 of them on `sharp` at
2.3–4.8 against a 3.0 limit. A soft key edge *inside a frame* is glass: FLUX
renders glazing unasked, and glazing lays a reflection gradient and a bevel
shadow across the exact boundary the matte has to cut. The rewritten prompt
names and forbids the glass, forbids the mount and the mat, and dimensions the
opening ("20cm wide by 30cm tall") instead of describing its ratio, which FLUX
had been ignoring.

The residual aspect scatter is **sampling, not prompting** — the dimensions are
ignored too — so batch 2 bought seeds on the one variant whose edge and
frontality were already clean (`sharp` 2.98, `frontal` 0.002).
`framed_v1_emerald_s66` passed all eight detectors: distortion 0.6641 (0.38 %
outside the printed range), matte-hidden 1.17 % trimmed / 0.00 % occluded,
everything else 0 px. Full-frame plus both rebate corners at 4×: the art meets
the frame's inner edge directly, no mat line, no hairline, the wall keeps its
own colour. Shipped as `lifestyle_framed_wall_plant`.

### 10.2 The screen was measuring something the gate does not

Twice in this phase a candidate passed the screen and failed the gate on
aspect. The screen measured the **hard key mask's** corner quad; the author
derives from the **anti-aliased matte** through `quad_for`'s containment and rim
margin. Not the same number: `clipsheet_v2_s44` screened 0.7074 and authored
0.7276 — 2.8 % outside the printed range, a C3 failure. `scene_screen` now calls
`soft_matte` and `quad_for` directly, so screen and gate agree to 4 decimal
places, and it takes `--group` for the secondary batches.

### 10.3 Thin-sheet: half landed, and one extractor limitation found

- **clips** — 1 candidate survived the corrected screen and then failed the gate
  on `occluder-opacity`: 568 px of alpha 0.54 along the two clip jaws.
- **shelf** — **0 of 21** across both batches, every one on `aspect` (0.64–1.14)
  plus `frontal` on a third. FLUX will not hold a portrait sheet standing on
  furniture; it widens the sheet or swings the camera. `lifestyle_shelf_books`
  stays as authored, and its residual slab look is a scene-selection matter for
  P4b, not something this prompt family fixes.

The clip band is the **extractor**, not the scene — the clip's edge is sharp to
1 px in the photograph. A deeply shadowed key desaturates, so its Lab a/b drifts
away from the key and lands in the matte's ramp. Rescaling each pixel's chroma
to the key's own lightness fixes those bands and *was tried*: it also amplifies
chroma noise wherever L is small and took `flat_clips_windowlight` from 0 to
30 339 px of mid-alpha. Reverted. The right fix is a chroma model, not a
division, and it is not worth one candidate scene — the limitation is recorded
on `scene_screen.key_distance`, and `occluder-opacity` keeps catching it.

### 10.4 State

```
library   flat_clips_windowlight  flat_leaning_bookstack
          lifestyle_shelf_books   lifestyle_framed_wall_plant
gate      4/4 PASS (8 detectors)      suite  567 passed
harness   4/4 deterministic, size-checked
          4a0a932b364d  1a9940260ae9  31c141a30e45  d82026d0cb4c
```

2 flat + 2 lifestyle. **P4b is +1 flat and +5 lifestyle for primary, then 10
each for 5x7 and 10x24.** `scene_author` now takes `--group`/`--orientation` and
records both, so the secondary groups need no further tool work.

Prompt do/don't, updated by this phase:

- **do** forbid glazing, mounts and mats explicitly in any framed prompt;
- **do** buy seeds rather than rewrite a prompt when only `aspect` is failing —
  it is a lottery FLUX plays regardless of the words;
- **don't** ask for a sheet standing upright on furniture (0/21);
- **don't** trust a screen metric that is not computed the way the author
  computes it.
