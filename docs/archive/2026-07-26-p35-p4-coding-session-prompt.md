# Coding-session kickoff — P3.5 (pre-merge fixes) + P4 (library scale-out) — 2026-07-26

Ready-to-paste prompt for a **Claude Code session** from the `qhoto_printshop`
repo root. Needs the Replicate skills (`find-models`, `run-models`,
`prompt-images`). Owner-in-the-loop for scene selection — **not** an unattended
batch.

Predecessors: `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` (plan
of record), `docs/2026-07-26-gl21-gl6-attempt3-coding-session-prompt.md`
(P0–P3, delivered), and the attempt-3 findings doc §8.

**P0–P3 are done and owner-accepted.** Gate 7/7 × 4, harness 4/4 deterministic
(`aac4dad6 / 10f224b6 / fd7c742e / 455652e2`), 517/517 tests. This session does
the small pre-merge fix list, merges PR #2, then scales the library.

---

## PROMPT — paste from here down

You are continuing GL-21 / GL-6 attempt 3 on the Etsy AI POD pipeline. The
compositor and the four primary/portrait bundles are built and accepted. Your
job: close three pre-merge gaps, land PR #2, then author the rest of the scene
library.

### Read first

1. `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md` — plan of record,
   especially §3 (the three changes) and §7 (approved decisions).
2. The attempt-3 findings doc §8 — what P0–P3 actually shipped, the two open
   items, and why the gate was blind to one of them.
3. `docs/2026-07-22-go-live-plan-of-attack.md` rows **GL-21**, **GL-6**, GL-5,
   GL-13, GL-18 + Part 4 (cont.) Sessions F/G/H.
4. `scripts/mockup_qa.py`, `scripts/scene_author.py`, `scripts/scene_generate.py`,
   `scripts/scene_screen.py`, `pipeline/mockup_render.py`.

### Standing rules (unchanged, non-negotiable)

- **Never work around a compositor defect in the assets.** If the composite is
  wrong, fix the compositor and add a test. If a constraint blocks the correct
  fix, stop and flag it.
- **`overlay.png` may only paint where the print is** (contract line added in
  P3 — an unmasked overlay is a full-frame wash).
- **Zero per-scene constants in source.** Everything derived, everything
  recorded in `scene.json`.
- Replicate + **FLUX.1 [schnell]** only. No Etsy/Gelato writes. Master is
  `db/base_artwork/39.png` (never `31.png`).
- Review order: **full-frame gestalt first**, then corners, then the edge strips.
  No sign-off from crops. One commit per scene after its full-frame pass.

---

## P3.5 — Pre-merge fixes. Three items, all small. Blocks the merge.

**F1 — `scripts/mockup_qa.py` doesn't parse below Python 3.12.** Line 562 nests
same-quote f-strings (PEP 701): `f"... {contact_sheet(r, out / f'{r['scene']}.png')}"`.
On Python 3.10 this is a hard `SyntaxError` — the gate does not run at all. The
repo declares no Python floor. Fix the line, then **declare the floor
explicitly** (`requires-python` / CI matrix) and add a smoke test that imports
every script in `scripts/`, so this class of breakage can't recur silently. P4
hands ~26 bundles to this gate; it has to run everywhere.

**F2 — the 2 % crop policy isn't enforced on the path that actually hides print.**
C3 gates *quad-vs-art* aspect. The **matte** hides print independently and is
only reported. Measured on `lifestyle_bedroom_console`: quad 393×574 at aspect
0.6842 (passes C3 cleanly), matte 367×574 at 0.639 → the art is scaled to the
quad then trimmed to the matte, so **6.6 % of the design width never appears**
(14 px left, 17 px right, 568 of 574 rows full-width — a flat symmetric side
trim, not prop occlusion).

Add a **matte-hidden-print detector** to the gate and enforce it at the same
**2 %** budget as C3, **with no exceptions** (owner decision, 2026-07-26).
Distinguish *hidden* (art scaled into the quad, then clipped by the matte) from
*occluded* (a prop genuinely in front) — but note the decision is no-exceptions,
so an occlusion carve-out is **not** in scope; a scene whose panel proportions
don't match the product must be re-authored, not exempted.

Rationale to keep in the docstring: this is invisible on the current master
(the lost strips land on blank margin) and invisible to manual review by
construction. It matters because bundles are permanent and artwork is not — a
future design with a border, signature, or stems running to the edge loses 6.6 %
of its width in that scene. This is precisely the defect class the QA suite
exists to catch.

**F3 — re-author `lifestyle_bedroom_console` to pass F2.** Re-seed against a
panel region whose proportions match the product, or regenerate the scene keyed
if seeding can't get under 2 %. Then re-run the full gate and
`scripts/gl19_m1_render.py`; hashes will change — record the new ones.

**P3.5 gate:** gate green on all four bundles *including* the new detector;
517/517 + new tests green; scripts import-smoke passes on the declared floor.
Then **merge PR #2** (`feat/gl21-matte-compositor` → master) per the owner's
merge-first decision, so P4's bundles land on master rather than a stacked
branch. **Stop, report, wait for the merge go-ahead.**

---

## P4a — Framed-scene keyed spike. Go/no-go. Do this before any large batch.

No keyed **framed-on-wall** scene has ever been produced. Both keyed successes so
far are bare sheets (hanging rail, leaning shelf) — the easy cases. Framed is
where attempt 2 died: `lifestyle_sage_terracotta`'s nested mat line and 0.59
opening aspect. P4's target is 7 lifestyle slots per group, which wants framed
scenes, so prove the branch before committing the batch.

Also fold in the **backing-slab fix** (owner decision): the two existing keyed
scenes read as a thick mounted board rather than a thin unframed sheet, which
oversells an unframed-poster product. Adjust the keyed prompt to force a thin
sheet / true frame rebate, and validate on this spike.

Batch: ~3 prompt variants × framed-on-wall, plus the thin-sheet variant of the
two existing keyed scene types. Owner approves the prompt set and cost before it
fires. Run `scene_screen.py`, including the **no nested mat/panel line inside the
opening** check and **opening aspect within 3 % of the group's target**.

**P4a gate:** at least one framed keyed scene passes the full gate end-to-end.
- **Go** ⇒ framed scenes are keyed in P4b.
- **No-go** ⇒ framed slots fall back to `--seeded` mattes on non-keyed framed
  generations, with the scope cost known up front rather than discovered
  mid-batch. Either way P4b proceeds.
If the thin-sheet prompt lands, **re-do `flat_clips_windowlight` and
`lifestyle_shelf_books`** with it. **Stop, show contact sheets, wait.**

---

## P4b — Library scale-out. Target: 3 flat + 7 lifestyle per group.

| group | orientation | have | need |
|---|---|---|---|
| primary | portrait | 4 (2 flat + 2 lifestyle) | +6 → 3 flat + 7 lifestyle |
| 5x7 | portrait | 0 | 10 — **blocks GL-13 Round 2** |
| 10x24 | portrait | 0 | 10 — **blocks GL-13 Round 2** |

Loop per group: generate keyed batch → `scene_screen.py` ranks → owner picks from
a labelled contact sheet → `scene_author.py` derives → `mockup_qa.py` gates →
full-frame review → commit per scene.

Group-specific requirements:
- **5x7** — the panel must read as a *small tabletop/shelf print* (13×18 cm
  feel), not a statement wall piece. `group_type:"5x7"`.
- **10x24** — tall narrow/panoramic panel. Preview through the compositor with
  **GL-14's cover-crop** of the master, not the master itself; confirm the crop
  fills the frame (this is the group whose missing crop caused the live-run white
  bars).
- Foreground props may clip **<~15 %** of the print, never ~40 %.
- Near-frontal only. Steep/angled scenes → author-and-shelve for v1.1, keep out
  of `mockup_templates`.
- **Landscape stays out entirely** → GL-18.

**P4b gate:** every bundle passes the gate incl. the F2 matte budget; per-group
sets complete or owner-approved as smaller. **Stop for owner review per group**,
not once at the end.

---

## P5 — Wire and close.

- `config/static_config.json` `mockup_templates`: **3 flat IDs before the 7
  lifestyle IDs** per group — the list order *is* the Etsy rank order.
- `assets/mockups/manifest.json` updated; drop its stale "prototype / 5x7 and
  10x24 out of scope" `_note`.
- Full suite green; the placeholder fail-loud test still passes (any scene ID in
  config **must** have a bundle on disk).
- `scripts/gl19_m1_render.py` extended to cover the secondary groups; record
  hashes.
- Findings doc: scenes kept per group with seeds + prompts + licence, the P4a
  go/no-go outcome, per-group **Round-2 readiness** statement (GL-13), and
  anything shelved for v1.1.

### Out of scope

Landscape (GL-18), the Gelato readiness-poll change (GL-20), Round 2 itself
(GL-13), and any change to `pipeline/group_product.py` or the bundle-on-disk
contract.

### Definition of done

F1–F3 fixed and PR #2 merged; P4a answered with evidence; per-group sets
authored, gated and owner-reviewed; config + manifest wired in rank order; suite
green; findings doc written with Round-2 readiness per group. No live writes.
FLUX.1 [schnell] only. Seeds and prompts recorded.
