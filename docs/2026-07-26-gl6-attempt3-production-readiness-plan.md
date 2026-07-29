# GL-6 attempt-3 — make mockup generation, authoring and compositing production-ready (2026-07-26)

Planning artifact (Cowork session). No code written, no assets touched. Input:
`docs/2026-07-24-gl6-attempt2-solution-plan.md`, the 5 attempt-2 commits
(`30124f1..00ac765`), `scripts/gl6_author.py`, `pipeline/mockup_render.py`, the
4 shipped bundles, the 4 renders in `outputs/gl19_m1/`, and owner review of
2026-07-26. Supersedes attempt-2's Phase A/B; keeps its §2 doctrine but replaces
its primitives.

Status: **PRD — §7 decisions resolved by owner 2026-07-26; plan itself awaiting
sign-off** (CLAUDE.md §2 — this touches an external account (Replicate) and is
multi-session).

---

## 1. Verdict on attempt 2, and the direct answer to the colour question

> *"are you purposefully changing the color so that it's less obvious to my
> review instead of fixing the actual problem?"*

Partly yes, and it should not have shipped that way. Attempt 2 measured a real
defect — a dark hairline around the print — correctly identified its cause
(interpolation contamination at the artwork border), then, because
`mockup_render.py` was declared frozen, "fixed" it **bundle-side** by painting
the real photograph back over the art's outer 3 px and 8 px outward
(`EDGE_PX`/`RING_PX` in `scripts/gl6_author.py`). That does not remove the
contamination; it hides it under a repainted band. On `lifestyle_sage_terracotta`
that band is measurably *brighter* than both the art and the mat beside it
(≈ +18 L where the art is dark) — a dark hairline was traded for a light one,
which is what you saw as white dotted lines. Documenting the trade in the
handover does not make it a fix. The frozen-file constraint was the wrong
constraint to respect here.

**The actual bug, and its actual fix.** `cv2.warpPerspective` defaults to
`borderMode=BORDER_CONSTANT` with value 0 — black. `_warp_into_quad` warps the
RGB with `INTER_CUBIC` under that default, so every partial-coverage pixel at
the artwork border is blended toward black before it is composited. Measured
across the four shipped bundles:

| scene | partial-alpha border px | mean colour error vs. a correct warp | max |
|---|---|---|---|
| flat_clips_windowlight | 1 203 | 121 / 255 | 250 |
| flat_leaning_bookstack | 1 479 | 120 / 255 | 250 |
| lifestyle_bedroom_console | 710 | 118 / 255 | 250 |
| lifestyle_sage_terracotta | 938 | 119 / 255 | 250 |

Adding `borderMode=cv2.BORDER_REPLICATE` to the **colour** warp (the mask warp
must stay `BORDER_CONSTANT`) removes it exactly — verified on a synthetic flat
warp: border pixels read 246 instead of 0. Twelve characters, one test. Every
bundle-side edge hack in `gl6_author.py` is then deleted, not generalised.

---

## 2. What each of your four observations actually is

**(a) `flat_clips_windowlight` — "the shadow is still curved".** Correct, and
it cannot be fixed by annotation. Mode O expands the art quad past the
photographed paper, but the paper in that photo is *curled*: its right/bottom
silhouette bows, and FLUX drew the wall shadow to match that bowed silhouette.
A homography maps a rectangle to a **quad**. The composite therefore shows a
straight-edged print with a curved shadow, plus a grey tapered wedge of
un-covered photographed paper at the bottom-right corner (visible at 3× zoom,
x≈660–700, y≈880–950). Attempt 2's own §2 said Mode O must "draw a synthetic
sharp paper edge **+ soft drop shadow**" in the overlay — the synthetic shadow
was never implemented, so the photographed one was left to contradict the print.

**(b) `flat_leaning_bookstack` — "odd square cutouts near the books".** The art
quad reaches ~14 px *below* the board's real bottom edge (Mode O overfill), so
the print spills onto the floor. Where it spills is then clipped back by
`occluders=[(168, 886, 328, 962), (532, 872, 728, 962)]` — two **axis-aligned
boxes** inside which a chroma/darkness test repaints the photograph at α255.
The floor is chroma-far from the paper, so inside the boxes the floor is
correctly restored and outside them it is not. The box borders are the square
steps. The primitive is wrong: any error inside a rectangle shows up as a
straight vertical or horizontal edge.

**(c) `lifestyle_bedroom_console` — good.** Confirmed: clean 1-px transition at
every border, no fringe, no spill. It still carries the repaint-band hack and
must be rebuilt without it.

**(d) `lifestyle_sage_terracotta` — "white dotted lines" + "the further inset
artwork doesn't look right".** Two things, and your reading of the second is
right. The scene's mat carries a **photographed inner panel line** ~16 px inside
the mat opening (measured: L 179 against 250 at row 500). The Mode-I quad sits
~62 px *inside* that line, so the composite reads frame → mat → panel line →
more mat → art: a border inside a border. Your rule is the correct one —
**if the generated frame has its own inset, the art must land on that inset, not
inside it.** The dotted line is that panel line plus the repaint band from §1.
Compounding it, the opening's aspect is 0.59 against the master's 0.684, so a
correctly-proportioned print can never fill it.

**Common thread:** attempt 2 kept trying to express a *photographed silhouette*
as a **four-point quad plus rectangular patches**. Curl, soft taper, book
spines, clip jaws and nested mat lines are none of those things. The doctrine
("the art must never have to meet a photographed edge") was right; the
primitives could not express it.

---

## 3. The fix: one new primitive, applied across all three stages

> **A per-pixel `matte.png` replaces the quad-as-silhouette, the occluder boxes
> and the repaint band.** The quad keeps one job only — *where the art is
> projected*. What is *visible* is decided by the matte, per pixel, with
> anti-aliasing. Nothing then has to be traced to sub-pixel accuracy, because
> nothing is traced at all: the matte is derived from the image.

That single change dissolves (a), (b) and (d): a curl is just a matte shape; a
book spine is just a hole in the matte; a mat opening is exactly the matte's
outline, so "inset" stops being a parameter anyone can get wrong.

### 3.1 Compositing — unfreeze `pipeline/mockup_render.py`, 3 additive changes

| | change | why | risk |
|---|---|---|---|
| **C1** | `borderMode=BORDER_REPLICATE` on the colour warp only | removes the black contamination measured in §1 | none; mask path untouched |
| **C2** | optional `matte.png` in the bundle; warped-art alpha ×= matte | the new primitive | absent file ⇒ today's behaviour exactly, so all 504 tests and the existing bundles are unaffected |
| **C3** | load-time aspect guard: **cover-crop** the artwork to the quad's aspect, fail loud if the crop exceeds 2 % | attempt 2 found quads ranging 0.63–0.70 against a 0.684 master — up to 5 % silent non-uniform stretch of a print a buyer is paying for | changes render output for any aspect-mismatched bundle — intended |

With a matte, `overfill` becomes unnecessary: the quad is derived as the
**min-area quad of the matte, expanded on the short axis to the master's
aspect**, so coverage is guaranteed and the matte trims the anti-aliased edge.
`overfill` stays in the schema for backwards compatibility, authored at 0.0.

Cost: ~40 lines and ~8 tests. The freeze was a GL-19 convention, not a spec
constraint; it should be lifted explicitly in CLAUDE.md and the addendum rather
than worked around a third time.

### 3.2 Generation — make the matte extractable by construction

The cheapest place to solve an extraction problem is upstream of it. Generate
scenes whose print area is a **solid flat key-colour panel** instead of blank
white paper:

- the matte becomes exact and automatic — including the curl, and including
  every prop that overlaps the panel (a clip jaw is simply a non-key hole);
- the photographed drop shadow now belongs to the *actual* silhouette the art
  will occupy, so defect (a) cannot recur by construction;
- FLUX still renders the scene's light **onto** the panel, which is precisely
  the input the existing gain-map extractor wants — that part of attempt 2
  works and is kept;
- there is no blank low-contrast insert left to mis-trace, which was the
  original generation-side complaint.

Still FLUX.1 [schnell] on Replicate, unchanged licence. Key colour is chosen per
scene family (emerald vs. magenta) and validated for spill. The 2026-07-23 brief
told the session *not* to prompt for a keyed insert; that instruction is what
left two sessions hand-tracing soft white-on-white edges, and this plan reverses
it.

**Machine-checked generation acceptance** (replaces the prose criteria): key
area fraction in range · single connected key component · solidity ≥ threshold ·
opening aspect within 3 % of the group's target ratio · occluder coverage ≤ 15 %
· key edge gradient sharp · no key colour outside the panel · near-frontal
(opposite-edge length ratio) · **no nested mat/panel line inside the opening**
(new, from defect (d)). Schnell is near-free, so generate 40 and let the screen
rank them; the owner reviews only survivors, on a labelled contact sheet.

### 3.3 Authoring — derive, don't hand-read

`scripts/gl6_author.py` currently hard-codes four hand-read paper quads, four
margin tuples and four occluder box lists. That is the thing that does not
scale to the ~20 remaining bundles and the thing that has now failed twice.
Replace with `scripts/scene_author.py`:

- `extract <scene>` — key matte (Lab distance + despill) → hole-filled occluder
  mask → anti-aliased matte → `background.png` with the key region *neutralised*
  (chroma removed, luminance kept, so partial-alpha edges blend into paper, not
  green) → gain map (attempt 2's extractor, kept) → quad = min-area quad of the
  matte snapped to the master's aspect.
- `extract --seeded <scene>` — **Plan B** for scenes with no key (the existing
  four, or a photo the owner loves): matte from a coarse owner polygon used as a
  GrabCut/flood **seed**, refined against the image. Tolerance is ±several px
  because the image refines it, not the hand.
- `verify <scene>` — the QA gate below; nothing reaches the owner unless it
  passes.
- `build <scene>` — writes `background.png`, `matte.png`, `overlay.png`,
  `meta.json`, plus `scene.json` provenance (model, prompt, seed, key colour,
  derived quad, aspect delta, crop %). **No per-scene constants in source.**

### 3.4 Verification — `scripts/mockup_qa.py`, gate before eyeballs

Attempt 1 signed off from crops; attempt 2 added full-frame review but still
relied on judgement for things a computer can measure. Automate these:

1. **Fringe test** — at every partial-alpha border pixel the composite must lie
   between its art and background neighbours. Catches C1-class bugs permanently.
2. **Spill test** — no residual key chroma anywhere in the composite.
3. **Distortion test** — |quad aspect ÷ art aspect − 1| ≤ 1 %; report crop %.
4. **Coverage test** — no art outside the matte; no matte pixel left un-covered
   (catches (b)-class holes).
5. **Occluder-opacity test** — matte holes are 0 or 1 apart from AA (catches the
   attempt-1 α-172 see-through class).
6. **Silhouette-vs-shadow test** — flag when the photographed shadow's silhouette
   and the matte disagree beyond tolerance (catches (a) directly).
7. **Contact sheet** — full frame + four corners @3× + a 1-px edge strip, one PNG
   per scene.

Owner review = the contact sheets of scenes that already passed 1–6.

---

## 4. Disposition of the four existing scenes

| scene | call | reason |
|---|---|---|
| `lifestyle_bedroom_console` | **keep**, rebuild | passes review; only needs the repaint band removed and a matte |
| `flat_leaning_bookstack` | **try `--seeded` first (≈30 min), else regenerate** | white board against warm wall/floor is a favourable seeded-matte case; the books become matte holes |
| `flat_clips_windowlight` | **regenerate keyed** | curled silhouette + matched shadow are unobtainable from a white-on-white photo |
| `lifestyle_sage_terracotta` | **regenerate keyed** | 0.59 opening aspect vs. 0.684 master, plus the nested panel line — scene geometry, pre-approved for regeneration by attempt-2 decision #2 |

---

## 5. Phases and gates

| phase | work | gate |
|---|---|---|
| **P0 — keyed-generation spike** | 3 prompt variants × 4 scene types on schnell; run the screen; take one scene end-to-end (extract → matte → render) | **go/no-go.** ≥2 of 4 scene types yield a clean key ⇒ go. No-go ⇒ Plan B (`--seeded`) with §3.1/§3.3/§3.4 unchanged |
| **P1 — compositor** | C1 + C2 + C3 + tests; unfreeze note in CLAUDE.md + addendum | 504 + ~8 new green; existing bundles render byte-identical except the C1 border fix |
| **P2 — tooling** | `scene_author.py` + `mockup_qa.py` + contact sheets | QA gate reproduces every §2 defect on the *current* bundles (a detector that can't see a known defect is not a detector) |
| **P3 — the four primary scenes** | per §4; auto-authored, QA-gated, owner full-frame review | 4/4 at the B+ bar ⇒ **GL-19 harness re-run ⇒ PR #2 unblocked** |
| **P4 — library scale-out** | primary +6, 5x7 ×10, 10x24 ×10 (§7.4 target = 3 flat + 7 lifestyle per group, ~26 bundles): batch generate → screen → owner picks → auto-author | every bundle passes QA; 10x24 previewed with GL-14's cover-crop |
| **P5 — wire + close** | `mockup_templates` (flat-first order) + manifest + full suite + findings doc | Round-2 secondary slice unblocked (GL-13) |

P0–P3 is the PR-#2 unblock and is one Claude Code session if P0 goes.
P4 is a second session, owner-in-the-loop for selection only.

**Process safeguards retained from attempts 1–2, non-negotiable:** full-frame
gestalt check before any zoom; harness re-run after every bundle edit; no
sign-off from crops alone; one commit per scene after its full-frame pass. Added
here: **no bundle-side workaround for a compositor defect** — if the composite is
wrong, fix the compositor and cover it with a test.

---

## 6. Risks

| risk | mitigation |
|---|---|
| FLUX schnell won't render a clean flat key panel (adds texture, gradients, or refuses) | that is exactly what P0 tests, before any commitment; Plan B (`--seeded`) needs no generation at all |
| Key spill onto frame/props tints the composite | despill in `extract`; spill test in QA; per-scene key-colour choice |
| Matte edges look "cut out" against soft photographic edges | matte is anti-aliased and derived from the photograph's own gradient, so it inherits the real edge softness; QA fringe test bounds it |
| Unfreezing `mockup_render.py` destabilises a validated PR | all three changes are additive and default-off (C2) or provably-correct (C1); C3 is the only behaviour change and it fails loud rather than silently |
| Scope creep into a rewrite | the pipeline contract (`load_bundle` / `render_scene` / bundle-on-disk) is unchanged; group_product.py is untouched |

---

## 7. Decisions — RESOLVED by owner (2026-07-26, Cowork session)

1. **Scene supply: keyed generation — APPROVED as Plan A.** Regenerate
   `flat_clips_windowlight` and `lifestyle_sage_terracotta` keyed;
   `flat_leaning_bookstack` gets the ≈30-min `--seeded` trial first per §4, keyed
   regeneration if it fails. `lifestyle_bedroom_console` kept and rebuilt.
   `--seeded` is still built (it is the P0 no-go fallback), but keyed is the
   default path for every new scene in P4.
2. **Compositor: unfreeze `mockup_render.py` for C1 + C2 + C3 — APPROVED.** The
   freeze is lifted in CLAUDE.md and the Addendum as part of P1. Every
   bundle-side edge workaround in `gl6_author.py` is deleted in the same phase;
   the new standing rule is §5's — no bundle-side workaround for a compositor
   defect, fix the compositor and cover it with a test.
3. **Aspect policy: cover-crop ≤2 %, fail loud beyond — APPROVED.** No silent
   stretch, no letterbox. The crop percentage is recorded per bundle in
   `scene.json` and reported by the QA distortion test.
4. **Library target: 3 flat + 7 lifestyle per group — CONFIRMED.** ~26 further
   bundles (primary/portrait +6, 5x7 ×10, 10x24 ×10). This makes P4 the larger
   phase and is the reason §3.3's derive-don't-hand-read requirement is
   load-bearing rather than tidiness: at attempt-2's hand-authoring rate this
   target is not reachable.

## 8. Tool fit

Execution belongs in **Claude Code** in-repo (Replicate skills for generation,
bash for the QA harness), not Cowork. This planning session is the right use of
Cowork; the render/annotate/verify loop is not.
