# GL-21 + GL-6 attempt 3 — findings (2026-07-26/27)

Branch `feat/gl21-matte-compositor`, cut from `feat/gl5-mockup-compositor`.
Executes `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` phases
P0–P3. Attempt 2's `feat/gl6-scene-library` was reference only; nothing was
cherry-picked from it but ideas.

**Recommendation: PR #2 is mergeable once the four bundles below are
owner-approved.** Detail in §7.

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
