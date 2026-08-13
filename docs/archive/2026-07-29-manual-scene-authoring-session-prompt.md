# Session kickoff — manual scene authoring (Nano Banana + intake harness) — 2026-07-29

Ready-to-paste prompt for a **Claude Code session** from the `qhoto_printshop`
repo root, on `feat/gl6-p4-scene-library`.

Owner-in-the-loop throughout — this session writes prompts *with* you and builds
the intake harness. It generates no images itself; you do that by hand in the
Nano Banana UI and drop the results in `assets/mockups/inflow/`.

Predecessors: `docs/2026-07-29-p4b-scene-generation-pivot.md` (the decision and
the evidence), `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` (plan
of record), attempt-3 findings §8–§10.

---

## PROMPT — paste from here down

You are continuing GL-6 on the Etsy AI POD pipeline. P0–P4a shipped four
primary/portrait bundles; P4b is scaling the library. Scene generation has just
moved off FLUX schnell to **Nano Banana Pro, hand-run by me**, and this session
has two jobs: write the scene prompts with me, and build the intake harness that
takes one hand-generated image to an authored, gated bundle.

**Do not generate any images. Do not call Replicate, Etsy or Gelato.**

### Read first

1. `docs/2026-07-29-p4b-scene-generation-pivot.md` — the decision, the P4b1
   numbers, and the two rules §3.2 draws out.
2. `assets/mockups/inflow/README.md` — the folder contract.
3. `CLAUDE.md`, the two mockup constraint blocks and the new scene-generation one.
4. `scripts/scene_screen.py`, `scripts/scene_author.py`, `scripts/mockup_qa.py`,
   `pipeline/image_crop.py`.

### Standing rules (unchanged)

- **Never work around a compositor or authoring defect in the assets.** If the
  composite is wrong, fix the tool and add a test. If a constraint blocks the
  correct fix, stop and flag it.
- **Zero per-scene constants in source.** Everything derived, everything recorded
  in `scene.json`.
- **`overlay.png` may only paint where the print is.**
- Review order: full-frame gestalt, **bare scene beside the composite**, then
  corners, then edge strips. No sign-off from crops alone. One commit per scene.

---

## Task 1 — the intake harness, `scripts/scene_intake.py`

One command takes one inflow image all the way and tells me plainly whether it
is usable:

```bash
python scripts/scene_intake.py assets/mockups/inflow/primary/lifestyle_bench_fern.png
```

It should, in order: resolve `--group`/`--orientation` from the file's inflow
folder and its sidecar; run the screen; run `scene_author.py extract`; run the
eight-detector gate; write the contact sheet **and a bare-scene-vs-composite
pair**; print one verdict block with every metric, its limit, and pass/fail.

Requirements:

- **Stop at the first hard failure and say which stage.** A screen `aspect`
  failure means regenerate — don't author it and waste my review.
- **`--dry-run` writes nothing outside `outputs/`.** I want to see the verdict
  before a bundle lands in `assets/`.
- **Refuse to run without a provenance sidecar**, and copy its fields into
  `scene.json`. A hand-made image has no batch manifest behind it; if the
  sidecar isn't enforced the provenance is simply lost.
- **Add a key-collision check the screen currently cannot do.** §3.2 of the
  pivot doc: a fern frond within `KEY_LAB_TOL` of an emerald panel was swallowed
  by the mask, `occluders` reported 0.0, and the art would have printed over a
  leaf that is visibly in front of the poster. Detect near-key colour *adjacent
  to or intruding on* the panel boundary and warn loudly. Demonstrate it against
  `/tmp`-style evidence or a synthetic case — a check that cannot see a known
  defect is not a check (`mockup_qa.py demo`'s own standard).
- Tests alongside, in the existing style. The suite is at 567; don't weaken it.

## Task 2 — write the scene prompts with me, interactively

Do **not** hand me a finished list. Work through it one scene at a time, show me
the prompt, take my edits. Target, against a library of 4 primary + 2 unauthored
5x7:

- primary/portrait: **+1 flat, +5 lifestyle**
- 5x7: +8 · 10x24: +10 (after primary proves the loop)

What the pivot doc establishes about prompting this model, to build on rather
than rediscover:

- **Aspect comes from the geometry card, never from prose.** Attempt 1 asked for
  "A1 format" and rendered 0.7572. Pass
  `assets/mockups/geometry_cards/geometry_card_<group>_*.png` as a reference and
  say the poster's proportions match it exactly.
- **Negation works** on this model and inverts on schnell. Use it.
- **Do not ask for raking light across the panel.** schnell's `COMMON` tail did,
  and a shadowed key desaturates out of key tolerance. Light the room; light the
  panel flatly and evenly.
- **The key colour must appear nowhere else in the scene.** Emerald + foliage is
  a collision — keep plants clear of the panel, or key that scene magenta.
- **Vary `area` deliberately.** Both Nano Banana scenes so far are ~0.12, near
  the 0.10 floor; shipped bundles run 0.22–0.44. A gallery of ten wide
  establishing shots makes the artwork a postage stamp in Etsy's grid.
- **Vary `occluders` deliberately.** Both are 0.0 — a bare rectangle on a bare
  wall. Prompt one or two scenes with something genuinely in front of the print;
  that is what the matte primitive buys and what makes `flat_leaning_bookstack`
  read as a photograph.
- Sources at ~2000–2400 px on the long side.

For each scene give me: the prompt verbatim, which card to attach, the key
colour and why, and the `area`/`occluders` intent. Then I generate it.

## Task 3 — the end-to-end proof

I will generate **one** image against the first prompt and drop it in
`assets/mockups/inflow/primary/`. Run the harness on it and walk me through the
verdict: screen, gate, contact sheet, bare-vs-composite. If it authors clean,
commit that scene and the harness together and we scale. If it doesn't, tell me
whether the defect is the prompt, the tool, or the scene — and fix the tool if
that's the answer.

## Housekeeping, same session

- `scripts/scene_generate.py`'s docstring still says schnell is "the only image
  model this project may use". It now contradicts `CLAUDE.md`. The file is
  already modified in the working tree — fix it there.
- Copy the four shipped scenes' source images into `inflow/primary/` with
  sidecars. `outputs/gl6_*` and `outputs/attempt1_*photo.png` are git-ignored,
  so `flat_leaning_bookstack` is currently one `git clean` from being
  unreproducible — against the §8.4 pure-function property.
- The two uncommitted 5x7 bundles under `assets/mockups/5x7/` need a decision:
  commit or drop.

Ask before you build if anything here is ambiguous. Show me the harness design
before you write it.
