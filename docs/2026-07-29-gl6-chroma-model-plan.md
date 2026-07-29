# GL-6 — the chroma model for keyed mattes (plan, session prompt, and where P4b was parked)

Written 2026-07-29 on `feat/gl6-p4-scene-library`, at the point where scene
authoring stopped being blocked by prompting and started being blocked by the
extractor. Amends nothing; adds the one capability
`docs/2026-07-29-p4b-scene-generation-pivot.md` §4 turns out to depend on.

Three parts:

1. **The problem and the plan** — what to build, what it must satisfy, and the
   corpus it is measured against.
2. **The session prompt** — a self-contained brief to fire in a fresh session.
3. **Resuming P4b afterwards** — what is done, what is next, and the prompting
   rules this session paid for.

---

# Part 1 — the problem

## 1.1 Owner directive (2026-07-29)

> Being able to handle shadows and highlights is essential for the mockups.
> That is expected from the buyers that the mockups show "golden hour"
> scenarios and realistic shadows — not just a set of conveniently "no shadows
> at all and perfect flat lighting" scenes.

This overrides the GL-21 decision recorded in `scene_screen.key_distance`'s
docstring ("reject the scene, keep the screen honest"). That decision was
correct when the defect had cost exactly one candidate scene. It has now
blocked an entire scene *class*, and the class is the one that makes a mockup
look like a photograph.

## 1.2 What the extractor does today

`scene_screen.key_distance` measures, per pixel, the Euclidean distance from
the key's reference colour in Lab **a/b only** — luminance deliberately
ignored, because the scene's light falling across the panel is the gain map
and we want to keep it.

`scene_author.soft_matte` turns that distance into coverage with a linear ramp
between `MATTE_LO * KEY_LAB_TOL` and `MATTE_HI * KEY_LAB_TOL`, currently
`0.6 * 32 = 19.2` to `32`.

The assumption underneath: **a pixel's chroma distance from the key is a
measure of how much of it is key.** That assumption is false in shadow and in
highlight. Dropping L from the *distance* does not make the measurement
lightness-invariant, because a surface's a/b themselves collapse toward
neutral as it darkens or blows out. A shadowed emerald panel is still 100 %
emerald panel; its a/b have simply moved.

## 1.3 The evidence, measured this session

Both scenes are Nano Banana Pro, hand-run, screened 9/9 or near it, and both
died on the same mechanism.

**`lifestyle_console_vase`** — a stoneware vase casts its shadow onto the
poster's lower-left face:

```
FAIL gate occluder-opacity   5532 px of flat mid-alpha (0.87 mean, budget 43)
largest cluster              5134 px at x857-1020 y1329-1396, alpha 0.87
panel quad                   x752-1647 y149-1395
```

**`lifestyle_studio_held`** — a woman holds the poster; her fingers shade the
sheet where they grip it. Screen 9/9, `aspect` 0.7024 *inside* the printed
range, gate 7/8:

```
FAIL gate occluder-opacity   847 px of flat mid-alpha (0.61 mean, budget 49)
largest cluster              707 px at x1618-1679 y737-824, alpha 0.62
cluster mean RGB             (9, 76, 28)          <- poster in shadow
panel interior mean RGB      (32, 166, 84)
cluster key distance         min 19.9  median 23.7  max 31.3
current ramp                 19.2 .. 32.0         <- the cluster sits inside it
a genuine prop, for scale    finger core, distance 75.9, matte 0.00
```

That last pair of lines is the whole diagnosis in two numbers. The shadowed
**panel** measures 20–31. A real **prop** measures 76. They are not close, and
yet the shadowed panel is the one being called half-transparent, because the
ramp's lower edge was placed at 19.2 to catch anti-aliasing.

Symmetrically, and not yet measured because no such scene has been generated:
a **specular highlight** or a blown-out golden-hour hotspot desaturates toward
white and will drift the same way, out of the top of the key rather than the
bottom.

## 1.4 The prior attempt, and why it is not simply repeatable

Recorded in `key_distance`'s docstring (GL-21 P4a): rescaling each pixel's
chroma to the key's own lightness was tried. It fixes the shadow bands and it
**amplifies chroma noise wherever L is small** — it took
`flat_clips_windowlight` from 0 to 30 339 px of mid-alpha. The conclusion
recorded there is the starting point for this work, not an obstacle to it:

> The right fix is a chroma model, not a division.

Read that docstring before writing any code. The naive division is a known
dead end; re-deriving it costs a day.

## 1.5 The ramp band-aid, measured and rejected

For the record, so it is not rediscovered as a fresh idea. Narrowing the ramp
(`MATTE_LO` 0.6 → 0.85, i.e. lower edge 19.2 → 27.2) was swept across the
corpus:

| MATTE_LO | clips | framed_wall_plant | shelf_books | studio_held (occ-op px) |
|---|---|---|---|---|
| 0.60 | PASS | PASS | PASS | FAIL 847 |
| 0.75 | PASS | PASS | **FAIL distortion** | FAIL 148 |
| 0.85 | PASS | PASS | PASS | **PASS 10** |
| 0.90 | PASS | PASS | PASS | PASS 1 |

Quad aspect movement on the committed bundles at 0.85: clips +0.0015,
framed_wall_plant −0.0007, shelf_books −0.0014; matte coverage +0.0005 each.

It works, and it is still the wrong fix, for three reasons:

1. It buys shadow tolerance by making the matte's edge harder everywhere,
   which is a cost paid on every scene to fix a defect that occurs on some.
2. It cannot help a highlight at all — a blown-out hotspot moves *away* from
   the key in the same direction a prop does.
3. It converts §3.2's near-key prop (the fern) from a gate-visible defect
   (mid-alpha, caught by `occluder-opacity`) into a gate-invisible one (fully
   printed over a leaf). Only `scene_screen.key_contamination`, added this
   session, would see it.

If the chroma model turns out to be genuinely intractable, 0.85 is the
documented fallback — but it is a fallback, not the goal.

## 2 What to build

A replacement for "distance from a fixed reference in a/b" that answers the
question the matte actually needs answered: **is this pixel the key surface
under some illumination, or is it a different material?**

Direction, not prescription — the session doing this work owns the design:

- The key surface under varying light traces a **locus** through Lab, not a
  point. Its hue direction stays roughly constant while its chroma magnitude
  falls toward neutral at both ends of the lightness range (shadow and
  highlight/specular). A model of that locus can be **fitted per image from
  the panel's own confident pixels** — which is what keeps this repo's
  no-per-scene-constants rule intact: nothing is hardcoded, everything is
  derived from the image and recorded in `scene.json`.
- Membership then becomes deviation from that locus, measured in units of the
  fit's own spread, rather than absolute distance from one point. A shadowed
  panel pixel lies *on* the locus at low L. A prop lies off it, whatever its L.
- Noise is the known failure mode (§1.4). Whatever the model, its confidence
  must degrade gracefully where the signal is genuinely weak instead of
  amplifying it. Consider requiring agreement between hue direction and
  chroma magnitude rather than trusting either alone at low L.
- A hard-won bonus if the model is good: §3.2's fern is a *different hue
  direction* at full chroma, so a locus-based test should reject it where a
  distance-based test swallowed it. Do not design for this, but measure it.

## 3 Acceptance criteria

Hard, all of them, measured with the tools already in the repo.

1. **No regression on the shipped library.** `flat_clips_windowlight`,
   `lifestyle_framed_wall_plant`, `lifestyle_shelf_books` re-author (`scene_author.py
   reauthor`) and still pass `mockup_qa.py check` 8/8. Quad aspect must move by
   less than 0.002 on each; report the deltas. `flat_leaning_bookstack` is
   seeded, not keyed, and must be byte-identical — if it changes, the change
   leaked into the wrong path.
2. **`lifestyle_studio_held` passes 8/8**, with the finger-shadow region fully
   opaque (`occluder-opacity` at or near 0, not merely under budget), and her
   fingers themselves still cut clean holes.
3. **`lifestyle_console_vase` passes 8/8**, same standard for the vase shadow.
4. **A highlight case.** No scene in the corpus has one yet. Either construct a
   synthetic panel with a specular/blown hotspot and prove the matte stays
   solid across it, or state plainly that highlight handling is unverified —
   do not claim it silently.
5. **Props still separate.** `flat_clips_windowlight`'s clip jaws and
   `lifestyle_studio_held`'s fingers remain holes at alpha 0, not soft patches.
6. **`mockup_qa.py demo` still fires every detector.** A model that makes the
   gate blind is worse than the defect.
7. **Full suite green** (584 at the time of writing) with new tests covering
   the model itself: a synthetic keyed panel with a shadow gradient across it
   must matte solid; the same panel with a genuine prop must matte a hole; a
   near-key prop must not be silently swallowed.
8. **Zero per-scene constants.** Every parameter derived per image or justified
   in a comment by the defect it guards, and the fit's own parameters recorded
   in each bundle's `scene.json` so a bundle stays a pure function of source +
   tool.

## 4 The corpus, on disk

All sources are tracked under `assets/mockups/inflow/` as of this session —
`outputs/gl6_*` and `outputs/attempt1_*photo.png` are git-ignored, so nothing
in `outputs/` may be relied on.

| file | what it is for |
|---|---|
| `inflow/primary/lifestyle_studio_held.png` | the finger-shadow case, criterion 2. Screen 9/9, gate 7/8 today |
| `inflow/primary/lifestyle_console_vase.png` | the vase-shadow case, criterion 3. Screen 9/9, gate 7/8 today |
| `inflow/primary/flat_clips_windowlight.png` | shipped bundle, no-regression + real props |
| `inflow/primary/lifestyle_shelf_books.png` | shipped bundle. NB: fails `scene_screen`'s `frontal` at 0.087 today while passing the gate 8/8 — re-author it via `scene_author.py reauthor`, not via intake |
| `inflow/primary/lifestyle_framed_wall_plant.png` | shipped bundle, no-regression |
| `inflow/primary/flat_leaning_bookstack.png` | seeded photograph — the must-not-change control |
| `inflow/primary/lifestyle_sideboard_leaning.png` | **not** a chroma case. Fails the screen for an unrelated reason, see §6 |
| `inflow/5x7/*.png` | two undecided 5x7 sources, out of scope |

Run one scene end to end with:

```bash
python scripts/scene_intake.py assets/mockups/inflow/primary/lifestyle_studio_held.png --dry-run
```

`--dry-run` authors into `outputs/scene_intake/<scene>/` and writes nothing
under `assets/`.

## 5 Non-goals

- **Magenta keying.** Still viable (pivot doc §3.2) and untouched by this work.
- **The 5x7 and 10x24 groups.** Blocked behind primary, unchanged.
- **`scene_generate.py`.** Superseded; do not revive it.
- **Any pipeline, Etsy or Gelato code.** This is authoring-time only.

## 6 Deferred, and deliberately separate: occluded-corner extrapolation

Found this session on `lifestyle_sideboard_leaning`, unrelated to chroma, and
recorded here because it is the next thing to block a scene class.

A cup and two books rest against the poster's bottom-left corner. The props
sever that corner from the panel, so:

```
FAIL stage 2 screen: ['no-outside', 'frontal']
outside 0.0033 (limit 0.002)   frontal 0.128 (limit 0.06)
severed fragments: 1958 px + 1300 px at x772-822 y1312-1410
fitted quad: TL(783,277) TR(1627,277) BR(1638,1450) BL(773,1300)
edges: T 844  R 1173  B 878  L 1023
```

The bottom-left corner snaps up to y1300 while the right side runs to y1450 —
that 150 px *is* the entire `frontal` failure, and the severed fragment is
counted as key spill. Top vs bottom edge differ by 3.9 %, so the real keystone
is fine. `scene_screen._quad` derives corners from the visible mask, and a
corner behind a prop cannot be recovered that way.

The fix is to fit lines to the four edges and intersect them, recovering an
occluded corner by extrapolation. It touches quad derivation for every bundle,
so it wants its own session and its own no-regression pass. Until then,
compose props across the *middle* of an edge, never at a corner —
`lifestyle_studio_held` does exactly this and its quad is clean.

## 7 Outcome (2026-07-29, same day)

Built and shipped on `feat/gl6-p4-scene-library`. All eight criteria met; the
`MATTE_LO = 0.85` fallback of §1.5 was **not** used and `MATTE_LO` is still 0.6.

**What it is.** `scene_screen.key_model` fits the key's locus through
(L, a, b) — median a/b per 2-unit lightness bin, over the contiguous run of
populated bins around the panel's mode, seeded from the old absolute test and
refitted once against its own result. `key_deviation` returns distance from
that curve divided by a tolerance `clip(KEY_FRAC · chroma(L), NOISE_FLOOR_K · σ,
KEY_LAB_TOL)`. `KEY_FRAC = 0.5 < 1` is the load-bearing half: a neutral's
deviation *is* the locus's own magnitude, so a dark neutral can never be
swallowed at any lightness — which is precisely what §1.4's division got wrong
in the other direction. 1.0 is the boundary, so `MATTE_LO/HI`, the
contamination midband and the screen's `sharp` band all keep their meanings.
`key_distance` is gone; the locus is held **constant** outside the observed
lightness range, not extrapolated along the end slope (see `_locus_at`).

| criterion | result |
|---|---|
| 1 no regression | 4/4 gate 8/8. Aspect Δ: clips +0.0000, framed_wall_plant −0.0001, shelf_books −0.0019, all inside 0.002. `flat_leaning_bookstack`'s three layers byte-identical; its `scene.json` gains `"key_locus": null` only |
| 2 `lifestyle_studio_held` | 8/8. `occluder-opacity` 847 px @ 0.61 → **3 px** @ 0.22; fingers 97.8 % at alpha < 0.05 |
| 3 `lifestyle_console_vase` | 8/8. `occluder-opacity` 5532 px @ 0.87 → **0** |
| 4 highlight | **Verified synthetically, with a stated boundary.** A hotspot washing the key 80 % of the way to white (chroma 76 → 19 Lab units) mattes fully solid. A *fully clipped* white pixel carries no chroma and is not recovered — pinned by `test_fully_blown_highlight_is_not_recovered` so a later "fix" is examined rather than trusted. No corpus scene exercises it |
| 5 props | clips jaws 93.6 %, studio_held fingers 97.8 % at alpha < 0.05; the remainder is the anti-aliased rim |
| 6 `mockup_qa.py demo` | all 8 fire |
| 7 suite | 595 pass (584 + 11 in `tests/test_chroma_model.py`) |
| 8 no per-scene constants | every parameter fitted per image or commented with the defect and measurement it guards; knots + σ recorded in `scene.json.key_locus` |

**One gate change, and it is not a workaround.** `d_occluder_opacity` measured
"on a rim" within 2 px of both a 0 and a 1. A corner rim is a *wedge*, and a
wedge's tip is further from both plateaus than its sides — `lifestyle_shelf_books`'
shadowed bottom-left corner measured 5 px deep, 21 px against a budget of 20.
Reach is now 3 px (`PLATEAU_RIM_PX`). Attempt 1's alpha-172 stamps measure 296 px
at every reach from 2 to 5 px, so the defect class is untouched.

**Not fixed, and measured to be sure.** §3.2's near-key fern is *not* separated
by the locus: RGB (60,200,30) reads deviation 0.67 against a boundary of 1.0, so
the mask still takes it. The locus does not help because the fern's problem was
never lightness. `key_contamination` remains the detector that owns it, and
`test_near_key_prop_is_not_silently_swallowed` holds it to firing with a shadow
gradient in the frame.

**Landed after the model, same session.** `lifestyle_studio_held` (0.7023) and
`lifestyle_console_vase` (0.7184) are committed bundles — the primary library
is **6**, and §3.2's table is that much shorter. §3.4's open question 1 is
closed: every bundle's `source_image` now points at `assets/mockups/inflow/`,
`_provenance_for` reads a per-image sidecar as well as a batch manifest, and
the fields that lived only in the git-ignored manifest (seed, licence,
aspect_ratio, megapixels) are backfilled into the four sidecars. Doing that
surfaced a defect worth its own note: **`reauthor` used to re-derive
provenance from the sidecar**, which on a raw Replicate export dropped
`key_rgb` and switched `d_key_spill` off — a gate detector turned off by a
re-author, on a bundle still reporting PASS. `reauthor` now carries the
bundle's own recorded provenance and is idempotent for every sidecar shape.

**Still open:** §6's occluded-corner extrapolation, untouched. §3.4's open
question 2 (intake hard-stops on any screen failure, and the screen is
stricter than the gate) has not bitten a second time yet.

## 8 The re-screen backlog — do this before generating anything new

The model changed the key mask, and `screen`'s `sharp`, `area`, `solidity` and
`no-outside` all read that mask. Every scene rejected by the *old* screen was
therefore judged by a measurement that no longer exists, and the batches under
`outputs/gl6_*` are a corpus of ~160 already-paid-for images. Re-screen them
before spending a cent on new generation.

**Measured this session, on a read-only diff against each batch's recorded
`screen.json`:**

- **`sharp` collapses.** It was the second-commonest rejection after `aspect`,
  and it was largely measuring the shadow: typical moves are 3.4 → 1.9,
  4.8 → 1.8, 5.7 → 1.5, 6.4 → 2.3 against a limit of 3.0. That is the defect
  this plan removed, showing up in the screen rather than the gate.
- **Three confirmed new passes** without touching anything else:
  `gl6_keyed/framed_v3_emerald_s11` (sharp 3.408 → 1.923),
  `gl6_keyed/shelf_v3_emerald_s22` (sharp 3.701 → 1.083, aspect 0.7385 →
  0.6967), `gl6_p4a/clipsheet_v2_emerald_s44` (aspect 0.7276 → 0.7000).
  Several more sit one check away.
- **`no-outside` newly fires on ~14 scenes**, and this is the part to look at
  hard rather than celebrate. The model's mask reaches further into shadow, so
  key-coloured *bounce* on a wall beside the panel now classifies as key. It is
  either the detector finally seeing real spill, or the mask over-reaching past
  the panel — decide which by looking, on at least three of them, before
  trusting any verdict from this pass.
- **`gl6_p4b1` is a wash: 0 newly passing at primary.** Its 61 images fail on
  `aspect`, which is a schnell limitation no extractor fixes (pivot doc §1.1).
  Don't spend time there.

**Method.** `scene_screen.py <dir> --group <g>` **overwrites that batch's
`screen.json`**, and those directories are git-ignored, so the old verdicts are
destroyed on first run and exist nowhere else. Copy each `screen.json` aside
first. A scene that now passes is copied into `assets/mockups/inflow/<group>/`
with a sidecar (`_TEMPLATE.json`) and authored by `scene_intake.py` — never
authored straight out of `outputs/`.

**The two uncommitted 5x7 bundles, re-authored under the model and measured:**
`lifestyle_small_bookstack` passes 8/8 at aspect 0.7285. `lifestyle_small_kitchenshelf`
trades one failure for another — `occluder-opacity` 164 px @ 0.74 is gone, and
`distortion` now fails at 2.26 % outside the printed range (quad 0.7308 vs
0.7143). Aspect is not fixable by authoring, so that one is a regenerate, not a
re-author. Both are still untracked, awaiting an owner verdict.

---

# Part 2 — the session prompt

Fire this in a fresh session on `feat/gl6-p4-scene-library` (or a branch off
it). It is self-contained.

> You are fixing the keyed-matte extractor in the Etsy AI POD pipeline so that
> mockup scenes with real shadows and highlights can be authored. This is
> authoring-time work only: do not touch `pipeline/generate.py`, do not call
> Replicate, Etsy or Gelato, do not generate any images.
>
> **Read first, in this order:**
> - `docs/2026-07-29-gl6-chroma-model-plan.md` — the plan, the measured
>   evidence, the acceptance criteria and the corpus. Part 1 is your brief.
> - `scripts/scene_screen.py`, especially `key_distance`'s docstring, which
>   records the failed naive attempt and names the fix you are building.
> - `scripts/scene_author.py`, especially `soft_matte`, `neutralise` and
>   `quad_for`.
> - `scripts/mockup_qa.py` — the eight detectors that decide whether you are
>   done, and `demo()`, which must still fire every one of them afterwards.
> - `scripts/scene_intake.py` — one command takes one source image to a gated
>   bundle; use `--dry-run` throughout so nothing lands in `assets/`.
> - `CLAUDE.md`'s mockup constraint blocks.
>
> **The problem, in one line:** the matte decides coverage from a pixel's Lab
> a/b distance to a fixed key reference, so a shadowed key — which is still
> 100 % key — drifts into the anti-aliasing ramp and prints half-transparent.
> Measured: 5532 px at alpha 0.87 on a vase's shadow, 847 px at alpha 0.61 on
> a hand's grip shadow, while a genuine prop sits at distance 76 against the
> shadow's 20–31. Build the chroma model that separates illumination from
> material. Plan §2 gives direction; the design is yours.
>
> **Standing rules that govern this work:**
> - Never work around a compositor or authoring defect from the asset side. If
>   a tool is wrong, fix the tool and add a test. If a constraint blocks the
>   correct fix, stop and flag it rather than routing around it.
> - Zero per-scene constants. Everything derived per image, everything
>   recorded in `scene.json`; a bundle is a pure function of source + tool.
> - Comments in this repo explain *why* — which defect a number guards
>   against, with its measurement. Match that voice; read `soft_matte` and
>   `d_matte_hidden` before writing any.
> - A check that cannot see a known defect is not a check (`mockup_qa.demo`'s
>   own standard).
> - Review order for anything visual: full-frame gestalt, bare scene beside the
>   composite, then corners, then edge strips. Never sign off from crops alone.
>
> **Done means** every one of the eight acceptance criteria in plan §3, each
> reported with its measurement — including the ones that are awkward, such as
> the quad-aspect deltas on the three re-authored bundles and whether the
> highlight case is verified or merely untested. If the chroma model cannot
> meet them, say so plainly and report what it *did* achieve against the
> `MATTE_LO = 0.85` fallback in plan §1.5, rather than quietly shipping the
> fallback as the fix.
>
> Commit per logical unit, and do not merge or open a PR without the owner.

---

# Part 3 — resuming P4b afterwards

## 3.1 State at the park

Committed this session:

- `scripts/scene_intake.py` — the intake harness. One image → sidecar check →
  screen → key-collision warning → `extract` → eight-detector gate → contact
  sheet + bare-vs-composite pair → one verdict block. `--dry-run` writes
  nothing outside `outputs/`. Accepts either our `_TEMPLATE.json` sidecar or a
  raw Replicate prediction export (the owner's actual artefact).
- `scene_screen.key_contamination` — the §3.2 blind spot: near-key props
  swallowed by the mask. Warns, does not block (owner decision). It has
  already fired correctly twice: 568 px on the clips scene's jaws, 14 278 px
  on `lifestyle_studio_held`'s fingers, where it predicted the gate failure
  from the source image before authoring.
- `scene_author.bundles/extract` take an output root, so intake can stage.
- Every bundle source is now tracked under `assets/mockups/inflow/`.
- `scene_generate.py`'s docstring no longer claims schnell is the only model
  this project may use.

Not done, blocked on the chroma model: **no new scene has been committed.**
The library is still 4 primary bundles.

## 3.2 The library targets, unchanged

| group | have | target | gap |
|---|---|---|---|
| primary/portrait | 4 | 3 flat + 7 lifestyle | +1 flat, +5 lifestyle |
| 5x7 | 2 uncommitted, undecided | 10 | +8 |
| 10x24 | 0 | 10 | +10 |

Two scenes are generated and waiting for the chroma model to author cleanly:
`lifestyle_studio_held` (the strongest of the three — screen 9/9, aspect
*inside* the printed range, real finger occluders) and `lifestyle_console_vase`.

## 3.3 What prompting Nano Banana Pro actually taught us today

Everything here is paid for with a real generation; it belongs in the next
prompt, not in a rediscovery.

- **Attach the geometry card, always.** Three scenes, three aspects: 0.7182,
  0.7189, 0.7024. The card gets you close; adding *"it is a portrait rectangle
  clearly taller than it is wide"* is what took the third one inside the
  printed range. The first two cost a 4.7 % cover-crop each.
- **Vague, evocative instruction works on this model.** The owner's
  one-line addition — *"The image should evoke a homely feeling"* — did more
  for the scene than a clause specifying the props. The first scene was
  sterile because it was over-specified. Give the model room.
- **Negation works — use two, not ten.** `"The bright green should not be
  reflected to any nearby surfaces"` produced `outside` 0.0 on every scene.
  The six-clause "no mat, no glazing, no glass…" tail inherited from schnell is
  superfluous here and was dropped with no ill effect.
- **Props must be geometrically forced to overlap, not asked to.** Scene 1 put
  a vase "in front of the poster's lower edge" on a table and the model simply
  hung the poster higher: occluders 0.0. Scene 3 put the poster in someone's
  hands and the overlap was unavoidable.
- **Props across the middle of an edge, never at a corner** — until §6's
  extrapolation fix lands.
- **`occluders` reads 0.0 for edge overlaps by design.** It counts enclosed
  holes. Edge overlap shows up at the gate as `matte-hidden`'s "occluded by
  props" figure instead. Do not chase the screen metric.
- **Ask for ~2000–2400 px on the long side.** Replicate's `2K` at 4:3 gives
  2400×1792 exactly.
- **The key colour must appear nowhere else.** A painter's studio was
  successfully kept green-free by naming the palette ("warm ochres, umbers and
  earthy reds, no green paint anywhere"). If a scene genuinely needs foliage
  or green paint, key it magenta instead of fighting the prompt.
- **Do not ask for a flat-lit panel any more.** That clause was a workaround
  for the defect this plan removes, and it is what made scene 1 sterile.
  Once the chroma model lands, ask for the golden-hour light the buyer expects.

## 3.4 Two open questions for the owner, neither urgent

1. **The four shipped bundles' `scene.json` still points `source_image` at
   git-ignored `outputs/`.** The pixels are safe in `inflow/` now, the pointer
   is not; `reauthor` still resolves against `outputs/`. Repointing them is a
   four-line change plus a re-author that should be byte-identical — but it
   rewrites four committed bundles, so it was left alone.
2. **`scene_intake` hard-stops on any screen failure, and the screen is
   stricter than the gate.** `lifestyle_shelf_books` — committed, 8/8 at the
   gate — fails the screen's `frontal` at 0.087. If that bites a second time,
   make non-`aspect` screen failures overridable rather than loosening the
   screen.
