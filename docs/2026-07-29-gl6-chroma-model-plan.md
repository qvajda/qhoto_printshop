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
