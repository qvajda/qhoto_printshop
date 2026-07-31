# Coding-session kickoff — GL-21 (compositor) + GL-6 attempt 3 (scenes) — 2026-07-26

Ready-to-paste prompt for a **Claude Code session** started from the
`qhoto_printshop` repo root. Needs the Replicate skills (`find-models`,
`run-models`, `prompt-images`) for P0/P3 generation. Owner-in-the-loop between
phases — **not** an unattended batch.

Plan of record: `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md`
(decisions §7 approved). This prompt covers **P0–P3 only** — the PR-#2 unblock.
P4 (the ~26-bundle library scale-out) is a separate session.

---

## PROMPT — paste from here down

You are implementing **GL-21 + GL-6 attempt 3** for the Etsy AI POD pipeline:
fix the mockup compositor, then re-author the four primary/portrait scene
bundles on top of it. Two previous attempts at the *asset* half failed. Read why
before you touch anything — the failure mode is subtle and repeatable.

### Read first, in this order

1. `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` — **the plan of
   record.** §1 (the compositor bug + the honesty failure), §2 (mechanism of all
   four defects), §3 (the three changes), §5 (phases/gates), §7 (approved
   decisions). Everything below is its execution.
2. `CLAUDE.md` (root + repo) — hard constraints. Especially: Replicate + **FLUX.1
   [schnell] only** (never `[dev]`); generated *artwork* stays flat full-bleed;
   no Etsy/Gelato writes.
3. `docs/2026-07-22-go-live-plan-of-attack.md` — rows **GL-21**, **GL-6**, GL-5,
   GL-19, and **Part 4 (cont.) Sessions F + G** (the attempt-2 post-mortem).
4. `pipeline/mockup_render.py` (88 lines — **no longer frozen**),
   `scripts/gl6_author.py` (attempt-2 tool, to be replaced),
   `scripts/gl19_m1_render.py` (the acceptance harness — keep working).
5. `docs/2026-07-24-gl6-attempt2-solution-plan.md` §2 — the *doctrine* is still
   right ("the art must never have to meet a photographed edge"); only its
   primitives were wrong. Do not re-litigate the doctrine.

### The one rule that overrides convenience

**Never work around a compositor defect in the assets.** Attempt 2 measured a
real border bug, was told `mockup_render.py` was frozen, and repainted the
photograph over every print's outer 3 px instead — trading a dark hairline for a
bright one across all four bundles. If the composite is wrong, fix the code and
add a test. If a constraint blocks the correct fix, **stop and flag it to the
owner**; do not route around it.

### Base branch

Branch off **`feat/gl5-mockup-compositor`** (inherits `mockup_render.py`, the 4
bundles, the config accessor, PR #2's test suite) as
**`feat/gl21-matte-compositor`**. Attempt 2's `feat/gl6-scene-library`
(`30124f1..00ac765`) is **reference only** — do not build on it; cherry-pick
nothing but ideas. Keep its `outputs/gl19_m1/*.png` renders around as the
"before" side of the comparison.

### Ground truth you can rely on (already verified, do not re-derive)

- `cv2.warpPerspective` defaults to `borderMode=BORDER_CONSTANT` value 0. Under
  `INTER_CUBIC` that contaminates every partial-coverage border pixel toward
  black: **710–1479 px per scene, mean error ~120/255, max 250.**
  `BORDER_REPLICATE` on the **colour** warp removes it exactly. The **mask** warp
  must stay `BORDER_CONSTANT` (replicating an all-255 mask fills the frame).
- Master is `db/base_artwork/39.png`, 6656×9728, aspect **0.684**. **Never
  `31.png`** (candidate 31 is stuck `pending_generation`).
- Attempt-2 quads ranged 0.63–0.70 → up to 5 % silent non-uniform stretch.
- `lifestyle_sage_terracotta`'s mat has a photographed inner panel line ~16 px
  inside the opening (L 179 vs. 250 at row 500); its opening aspect is 0.59.
- Occluder detection needs **chroma OR darkness as two separate tests** — RGB
  distance alone punches a hole through the paper's own shadowed corner;
  darkness alone misses a clip's bright metal jaw.

---

## P1 — Compositor (GL-21). Do this first. No assets touched.

Three additive changes to `pipeline/mockup_render.py`:

- **C1** — `borderMode=cv2.BORDER_REPLICATE` on the colour `warpPerspective`
  only.
- **C2** — optional `matte.png` in the bundle dir (single-channel or alpha, same
  size as `background.png`). `load_bundle` loads it if present; `render_scene`
  multiplies the warped art's alpha by it. **Absent file ⇒ current behaviour
  byte-for-byte** — assert this in a test against an existing bundle.
- **C3** — aspect guard at render time: compare the artwork's aspect to the
  quad's, **cover-crop the artwork** (centre crop, no stretch) to match, and
  raise `MockupRenderError` if the required crop exceeds **2 %**. Report the crop
  fraction so the authoring tool can record it.

`overfill` stays in the schema for compatibility; with a matte the quad is
derived to circumscribe the matte at the master's aspect, so bundles author
`0.0`. Document `overfill` as deprecated-for-matte-bundles in the docstring.

Then `scripts/mockup_qa.py` — the automated defect gate, six detectors, each of
which **must reproduce a known defect on the current attempt-2 bundles** before
you trust it (a detector that can't see a known defect isn't a detector):

1. **fringe** — every partial-alpha border pixel's composite value lies between
   its art and background neighbours. Must fire on attempt-2 sage.
2. **key-spill** — no residual key chroma anywhere in the composite.
3. **distortion** — |quad aspect ÷ art aspect − 1| ≤ 1 %; report crop %. Must
   fire on the old 0.63/0.70 quads.
4. **coverage** — no art outside the matte; no matte pixel left uncovered. Must
   fire on the bookstack notches.
5. **occluder-opacity** — matte holes are 0 or 1 apart from anti-aliasing. Must
   fire on attempt-1's α-172 overlays if you still have them.
6. **silhouette-vs-shadow** — flag where the photographed shadow's silhouette and
   the matte disagree beyond tolerance. Must fire on attempt-2 clips.

Plus a **contact-sheet generator**: per scene, one PNG with the full frame, four
corners at 3×, and a 1-px edge strip along each border.

**P1 gate:** existing 504 green + ~8 new tests green; `render_scene` on the four
current bundles differs from `outputs/gl19_m1/` **only** by the C1 border fix
(diff the deltas and show they're confined to border pixels); all six detectors
demonstrated firing on a known defect. Also update `CLAUDE.md` + the Addendum to
record that the compositor is unfrozen and why. **Stop, report, wait.**

---

## P0 — Keyed-generation spike (go/no-go). Owner approves the batch before it fires.

Generate FLUX.1 [schnell] scenes whose print area is a **solid flat key-colour
panel** instead of blank white paper. Three prompt variants × four scene types
(hanging-with-clips flat, leaning-board flat, framed lifestyle, shelf/console
lifestyle). State the model + licence, show the owner the prompt set and the
per-batch cost, get approval, then fire.

Why keyed: the matte becomes exact and automatic including curl and every
overlapping prop; the drop shadow FLUX renders belongs to the *actual* silhouette
the art will occupy, so the clips-scene defect cannot recur; and FLUX still
renders the scene's light *onto* the panel, which is exactly what the gain-map
extractor wants. Note that the 2026-07-23 brief said *not* to prompt for a keyed
insert — that instruction is deliberately reversed (plan §3.2).

Test both emerald and magenta keys; magenta risks spill on warm woods, green on
foliage. Then run the machine-checked screen: key area fraction in range · single
connected key component · solidity ≥ threshold · opening aspect within 3 % of the
group's target · occluder coverage ≤ 15 % · sharp key edge · no key colour
outside the panel · near-frontal (opposite-edge length ratio) · **no nested
mat/panel line inside the opening**.

Take **one** survivor end-to-end (extract → matte → render through P1's
compositor → QA → contact sheet).

**P0 gate:** ≥ 2 of the 4 scene types yield a clean key ⇒ **go**. Otherwise
**no-go ⇒ fall back to Plan B** (`--seeded` mattes on existing photos, plan
§3.3); P1's compositor work and the QA harness are unaffected either way. Show
the owner the screen results as a labelled contact sheet. **Stop, report, wait.**

---

## P2 — Authoring tool. Replaces `scripts/gl6_author.py`.

`scripts/scene_author.py`, with **zero per-scene constants in source** — this is
the requirement that makes P4's ~26 bundles possible and it is not negotiable.
Attempt 2 hard-coded four quads, four margin tuples and four occluder box lists;
that is the thing that failed.

- `extract <scene>` — key matte (Lab distance + despill) → hole-filled occluder
  mask → anti-aliased matte → `background.png` with the key region **neutralised**
  (chroma removed, luminance kept, so partial-alpha edges blend into paper, not
  green) → gain map (**keep attempt 2's `gain_map()` — it works**) → quad = min-area
  quad of the matte, expanded on the short axis to the master's aspect.
- `extract --seeded <scene>` — Plan B: matte from a coarse owner polygon used as a
  GrabCut/flood **seed**, refined against the image. Build this even if P0 goes;
  it is how any photo the owner loves gets kept.
- `verify <scene>` — runs `mockup_qa.py`; nothing reaches the owner unless it
  passes.
- `build <scene>` — writes `background.png`, `matte.png`, `overlay.png` (gain
  only — no repaint band, no stamped-back occluders; the matte handles both),
  `meta.json`, and `scene.json` provenance: model, prompt, seed, key colour,
  derived quad, aspect delta, crop %.

Carry over attempt 2's two real findings: the chroma-**OR**-darkness occluder test,
and the normalised-convolution gain map.

**P2 gate:** tool runs end-to-end on the P0 survivor and on one `--seeded`
scene; QA green; provenance written. **Stop, report, wait.**

---

## P3 — The four primary/portrait scenes. This is the PR-#2 unblock.

| scene | action |
|---|---|
| `lifestyle_bedroom_console` | **keep the photo**, rebuild the bundle (matte, no repaint band) |
| `flat_leaning_bookstack` | try `--seeded` on the existing photo first (~30 min); regenerate keyed if it fails QA |
| `flat_clips_windowlight` | **regenerate keyed** — curled silhouette + matched shadow are unobtainable from the current white-on-white photo |
| `lifestyle_sage_terracotta` | **regenerate keyed** — 0.59 opening aspect and a nested panel line; pre-approved for regeneration |

For each: author via `scene_author.py`, pass `mockup_qa.py`, then
`scripts/gl19_m1_render.py` with master `39.png`. **Review order is
non-negotiable** (attempt-1 lesson): **full-frame gestalt first**, then the
corner montages, then a final full-frame contact sheet. No sign-off from crops.
**One commit per scene, only after its full-frame pass.**

**P3 gate:** 4/4 at the B+ bar with QA green ⇒ GL-19 harness re-run clean ⇒
**PR #2 mergeable.** Write `docs/2026-07-26-gl21-gl6-attempt3-findings.md`:
per-scene before/after, the C1 delta measurement, QA detector results, seeds +
prompts + licence for anything generated, and an explicit **PR-#2 merge
recommendation**. Then stop for owner review.

### Explicitly out of scope here

- **P4 library scale-out** (primary +6, 5x7 ×10, 10x24 ×10 — target confirmed at
  3 flat + 7 lifestyle per group). Separate session, after P3 signs off.
- **Landscape** orientation → GL-18. **Steep/angled** lifestyle scenes → v1.1
  (author-and-shelve at most; keep out of `mockup_templates`).
- Any Etsy/Gelato call, the Gelato readiness-poll change (GL-20), Round 2 itself
  (GL-13). `pipeline/group_product.py` and the bundle-on-disk contract stay
  unchanged.
- `config/static_config.json` `mockup_templates` / `assets/mockups/manifest.json`
  rewiring beyond what the existing 4 scenes already need — that's P5.

### Definition of done

C1–C3 shipped with tests and the freeze lifted in the docs; `mockup_qa.py`'s six
detectors each demonstrated against a known defect; `scene_author.py` deriving
every number from the image with zero per-scene constants; the four primary
bundles passing QA **and** owner full-frame review; the GL-19 harness clean;
findings doc written with the PR-#2 recommendation. No live writes. FLUX.1
[schnell] only. Seeds and prompts recorded.
