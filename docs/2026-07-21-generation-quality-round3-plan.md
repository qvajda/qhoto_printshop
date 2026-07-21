# Generation-quality round 3 — follow-up plan + code-session kickoff (2026-07-21)

Follows `docs/2026-07-21-generation-quality-round2-plan.md` and its execution
ledger `.superpowers/sdd/round2-progress.md`. Round 2 is **executed and
validated**: the 10-candidate batch ran (candidates 15–24, same 10 niches as
round 1's 5–14, all mode-A, base artwork only, no upscale) and the owner's
blind review came back **5 good / 5 refine / 0 reject** — passing round 2's
own gate (≥ 5 good, 0 reject, both round-2 defect classes at 0 occurrences).
**Round 2 is a GO.** This doc is the round-3 plan: fix the *new* failure
family the round-2 batch exposed (secondary-subject integration), correct
two over-corrections (backdrop-device extinction, mandatory-occupant
over-application), close the sparse-gate gap the owner has now ruled on, fix
the two brief-lint false positives, ship the Cowork seam-population script,
and run the first 5/5 mode-A/mode-B validation split fed by an
owner-approved parallel Etsy comparative deep-research session.

**New frozen baseline for round 3: 5 good / 5 refine / 0 reject**
(candidates 15–24 + owner grades below). The round-1 3/7/0 baseline is
retired.

---

## 1. Round-2 validation scorecard (owner grades, ground truth)

Candidate IDs assumed 15–24 in owner-presentation order — **verify with one
SELECT on `candidates` (ids 15–24, match niche text) before recalibrating
anything against these IDs.**

| # | id | Niche (owner's description) | Grade | Owner note (condensed) |
|---|----|---|---|---|
| 1 | 15 | Bold filled MCM foliage, dragonfly in the gap | **Good** | Refinement: dragonfly (the subject) should be larger |
| 2 | 16 | Line-art monstera bouquet, sun disc nested in stems | Refine | "Sun disc" rendered as an odd small circle in the same color as the stems; stems stop short of the bottom edge leaving an unpleasant white band |
| 3 | 17 | Art deco geometric dahlia pattern | **Good** | Refinement: some small background flowers malformed (4 petals, kiss-shaped rather than flower-shaped) |
| 4 | 18 | Art deco sunburst | **Good** | — |
| 5 | 19 | Desert mesa, sun disc behind peak | **Good** | — |
| 6 | 20 | Coastal sea stack, seabird perched | Refine | Mostly good, but the seabird is either unnecessary or should have been flying rather than perched |
| 7 | 21 | Wildflower meadow bouquet (daisies/cosmos) | **Good** | Refinement: a paintbrush-style horizontal/slight-diagonal darker band in the background would make the design pop |
| 8 | 22 | Single stem study, beetle on stem | Refine | Beetle as color pop is nice, but it's superimposed on the stem with zero physical connection; an odd no-background rectangle shape around the beetle |
| 9 | 23 | Vintage herbarium (fern + red blooms), ladybug in triangle gap | Refine | A literal triangle *drawn* around the ladybug; ladybug smudgy, half-merging into a nearby flower; same bottom white band as #2 |
| 10 | 24 | Japanese-style peony, butterfly below bloom | Refine | Peony execution great; butterfly-below-bloom is a bad placement choice AND the butterfly is missing a wing (anatomically incomplete) |

**Owner's two cross-cutting observations (ground truth, drive this plan):**

1. **Backdrop-device pendulum:** round 1 used a backdrop shape in 8/10
   briefs (FM-1, over-use); round 2 uses it in **0/10** (over-correction).
   It is a good device that should still appear *sometimes* — the round-2
   demotion language plus the sibling-diversity nudge extinguished it
   entirely.
2. **Secondary-subject integration is the new dominant defect:** a subject
   is now usually present (round 2's fix worked at the "is there one" level)
   but it integrates poorly — scale too small (1, 2's disc), layered on top
   with no physical connection (8), merged/smudged into neighbors (9),
   poorly positioned (10), anatomically incomplete (10), or not needed at
   all (6).

**Owner ruling on the sparse gate (new, supersedes the ambiguity behind the
round-2 fan-in's candidate-12 REJECT):** stylishly sparse is OK — one big
subject covering most of the space, optionally with a badge/backdrop shape,
is a legitimate idiom and may keep generous empty space. The defect to
catch is **overall-empty-with-a-tiny-subject**. A large, clearly visible
main subject with empty space around it must pass.

## 2. Round-3 failure taxonomy (root causes, with code evidence)

**FM-7 — Secondary-subject integration failure. Highest frequency AND
highest owner-impact (5 of 10 designs: 1, 2, 8, 9, 10).** Five sub-modes:
(a) scale too small (1's dragonfly, 2's sun disc); (b) layered without
contact (8's beetle floats on the stem, connected to nothing); (c) merged/
smudged into neighboring detail (9's ladybug half-absorbed by a flower);
(d) poor placement choice (10's butterfly *below* the bloom); (e) anatomy
incomplete (10's butterfly missing a wing). Root causes, three converging:
1. `art_brief.py` template field 3 mandates a named occupant but gives the
   writer **no scale, contact, pose, or anatomy vocabulary** — briefs say
   "a ladybug in the gap", never how big, touching what, in what pose.
2. FLUX schnell's documented weak spot is exactly this: small-object
   spatial binding. Positional prepositions ("in", "below", "beside") are
   frequently dropped or misread; reliable integration needs **contact
   phrasing** ("legs gripping the stem", "wings overlapping the leaf edge")
   and **explicit relative scale** ("spanning a third of the frame width"),
   with the main subject stated early in the prompt (prompt-craft research,
   2026-07-21 — re-verify and extend in the Agent-A pre-task below).
3. `generate.py`'s `POSITIVE_SCAFFOLD` says "one coherent centered
   subject, dense composition filling the frame edge to edge" — it actively
   competes with any brief describing a primary + small secondary
   hierarchy, and every token of a schnell prompt fights for attention
   inside a 256-token T5 window.

**FM-8 — Literal containment geometry (8's rectangle, 9's triangle).**
Briefs describe the negative space *shape* ("in the triangle gap", "a
rectangular opening") and FLUX renders the geometry literally as drawn
lines/shapes around the occupant. Root cause: the round-2 template tells
the writer about "enclosed openings or channels of negative space" —
geometric descriptors of *space* leak into the brief and then into the
image as *objects*. The fix is wording hygiene: describe where the occupant
sits relative to the *subject matter* (stems, fronds, petals), never the
shape of the surrounding emptiness.

**FM-9 — Bottom-edge white band (2, 9).** Stem-based compositions
(bouquet, herbarium) stop short of the bottom edge. The scaffold's
"full-bleed / edge to edge" is generic; botanical specimen imagery is
overwhelmingly trained as a cut specimen floating on paper with margins,
so schnell reverts to it unless the brief states the grounding explicitly
("stems running off the bottom edge of the frame" / rooted at the lower
edge). Both affected designs are the stem-native niches.

**FM-10 — Backdrop-device extinction (0/10, owner observation 1).** Round
2's field-5 rewrite ("a deliberate anchoring device for a SMALL,
single-motif subject only — dense full-frame compositions use none") plus
the sibling-diversity note ("do not repeat their backdrop device") turned
a demotion into a prohibition: with density mandatory (field 2), the
"small single-motif" precondition never fires, and diversity pressure
punishes the device further. Fix: reframe as a positive device with a
target share, and make the sibling note *floor* it as well as cap it.

**FM-11 — Mandatory-occupant over-application (6's seabird).** Field 3's
"opening must hold a small secondary occupant OR close over it" reads to
the writer as "always add a creature". 6's sea stack needed either nothing
or a *flying* bird — motion suits an occupant that has no natural perch.
Fix: conditionality ("no secondary subject" is a valid choice when the
composition is complete) + pose guidance (dynamic poses — in flight,
mid-crawl — when the occupant isn't physically anchored to the subject).

**FM-12 — Small repeated-element malformation (3's kiss-shaped background
flowers). Low priority.** Schnell's small-detail limit: many small
repeated organic elements degrade. Mitigation via brief wording (background
motifs as simplified geometric abstractions of the idiom, or fewer/larger
repeats), plus critic criterion-3 coverage. Accept residual risk.

**FM-13 — Sparse-gate misfire (owner ruling, closes the round-2 fan-in's
headline finding).** The round-2 critic re-run REJECTED candidate 12
(owner: "great") because the low-cov `flag_note` steered the rubric into
rejecting a legitimate sparse idiom — and the "must pass despite flag"
calibration caveat lived only in a doc comment, enforced by nothing. The
owner has now ruled (§1): big-subject-with-empty-space passes;
tiny-subject-with-empty-frame fails. Neither the local stats (`cov`
measures ink fraction, not subject size) nor criterion 6's wording can
currently tell these apart.

**Carried-over environment issue (not code):** the Replicate account still
has no payment method — round 2's batch hit 4/10 sync-wait timeouts
(queue backpressure consistent with granted-credit status; correctly NOT
429s, per the round-2 error-text fix). Owner action stands.

**Tooling debt from round 2 (small, in scope):** `brief_lint.py` produced
two false positives on a clean batch: (a) `BOLDNESS_TERMS` phrase-matching
is too literal (a valid brief failed the boldness check on wording); (b)
`MAX_BRIEFS_SHARING_PALETTE = 2` cannot mathematically admit the *ideal*
5/5 palette split on a 10-brief batch. Also the calibration-fixture
collision: `db/base_artwork/<id>.png` filenames collide between validation
batches and calibration masters — it has now destroyed original masters
twice (round-1 stage 0 finding).

## 3. Candidate solutions

**R3-a — Brief-writer v3 + scaffold v2 (`art_brief.py`, `generate.py`).
The main quality lever. Bump `BRIEF_TEMPLATE_VERSION` to "v2" and
`SCAFFOLD_VERSION` to "v2".**

*Pre-task (owner-approved): prompt-craft research pass.* Before rewriting,
Agent A does a focused web pass on FLUX.1 [schnell] prompting for subject
integration: contact phrasing vs. positional prepositions, explicit
relative-scale wording, subject-first ordering, constraint-stacking limits
at 4-step inference, and any schnell-specific findings on small-object
anatomy. Findings summarized in the task report with sources; every
template change cites which finding motivated it. Seed findings from the
planning session (verify, don't trust): put the primary subject first with
explicit scale; use physical-contact verbs, not prepositions, to bind
small objects; fewer stacked constraints beat more at schnell's step
count.

Template changes (each maps to an FM):
1. *Occupant conditionality (FM-11):* a secondary occupant only when the
   composition genuinely has an enclosed opening AND an occupant improves
   it; "the composition closes over it" and "no secondary subject" are
   both valid, stated choices. When an occupant has no natural perch,
   prefer a dynamic pose (in flight, mid-glide) over a static perched one.
2. *Integration vocabulary (FM-7):* when an occupant IS used, the brief
   must state (a) its relative scale in positive terms ("large enough to
   read across a room", "spanning a quarter of the frame width" — the
   owner's note on 1 says err bigger), (b) its physical connection in
   contact language ("six legs gripping the stem", "wings brushing the
   leaf edge") or its dynamic pose if airborne, and (c) anatomically
   complete, symmetric wording ("both wings spread symmetrically") —
   positive-only, per the no-negations hard rule.
3. *Negative-space wording hygiene (FM-8):* the template's own
   instruction text stops using "opening/channel of negative space"
   geometry talk in ways the writer can echo; instruct: describe the
   occupant's position relative to the surrounding subject matter (stems,
   fronds, blooms), never the shape of the space around it — shape-words
   for emptiness become drawn geometry in the render.
4. *Bottom-edge grounding (FM-9):* stem/bouquet/herbarium-native subjects
   must state how the composition meets the lower edge ("stems running off
   the bottom edge"); general rule: name where the composition touches
   the frame edges.
5. *Backdrop-device rebalance (FM-10):* reframe from "only for small
   single-motif subjects" to a positive menu device: a badge, arch, sun
   disc, wash, or band *behind and touching the primary subject* is a
   deliberate, encouraged choice for SOME designs — including behind a
   large main subject (owner ruling §1; 7's owner note even asks for a
   band). Sibling note gains a floor as well as a cap: "if no earlier
   brief in this batch uses a backdrop device, strongly consider one here;
   if two already do, use none."
6. *Sparse idiom legitimized (FM-13, brief side):* field 2's density
   clause becomes conditional: EITHER dense full-frame OR one large
   dominant subject (with optional badge/backdrop) holding generous,
   intentional empty space — the invalid combination is a small subject
   in a mostly empty frame.

Scaffold v2 (`POSITIVE_SCAFFOLD`): remove "one coherent centered subject"
and "dense composition" (both now fight legitimate briefs — hierarchy
briefs and sparse-idiom briefs respectively); keep flat/full-bleed/crisp/
print-ready; add edge-contact wording compatible with FM-9. Keep the T5
240-token test green; brief word cap unchanged (60, outer 75).

- Root cause coverage: FM-7/8/9/10/11 (+13's brief side). Impact:
  **high**. Effort: **M** (research pre-task + template + scaffold +
  tests). Confidence: high — every change maps 1:1 to an owner note.

**R3-b — Critic rubric v3 + sparse-gate rework (`critic_pass.py`).**
1. Criterion 3 (subject coherence) amended: name anatomical
   incompleteness of small secondary subjects (missing wing/legs) and
   smudge-merging into neighboring elements as defects (9, 10).
2. Criterion 4 (composition) amended, round-3 defect classes: (a) a
   secondary subject layered on the composition with no physical contact
   or integration; (b) literal drawn geometry (triangle, rectangle,
   outline) containing or framing a subject; (c) a composition that
   visibly stops short of a frame edge leaving an unintended blank band.
   Keep 7 criteria, amend wording only, never renumber (telemetry).
3. Criterion 6 + flag logic reworked per the owner ruling (FM-13): the
   rubric text itself (not a doc comment) states the exception — "one
   large dominant subject with generous empty space is a legitimate
   style, PASS it; fail only when the frame is mostly empty AND the
   subject itself is small". `local_sanity_flag_note`'s wording changes
   accordingly: instead of "scrutinize points 2, 4, 6 closely" it must
   carry the distinction ("low ink coverage — check whether a single
   large subject dominates (legitimate) or the subject is small in a
   mostly empty frame (defect)").
4. Local gate: add a **subject-extent stat** to
   `compute_image_sanity_stats` — the bounding-box area fraction of the
   largest connected non-background region (cheap connected-component on
   the same 512px thumbnail). Flag-to-critic only when cov is low AND
   subject-extent is small; big-subject-low-cov skips the flag entirely.
   Thresholds calibrated on masters 5–24 + owner grades (12 and 22 are
   the key sparse anchors: both must pass unflagged or pass-with-flag).
5. Recalibrate the doc-comment calibration set against masters 15–24
   (good {15, 17, 18, 19, 21} / refine {16, 20, 22, 23, 24}), then
   re-run the critic on all 10 and diff against §1 — zero design cost,
   same protocol as both previous fan-ins. Watch specifically: does
   amended criterion 4 catch 8/22's contact defect and 9/23's triangle,
   does criterion 3 catch 10/24's wing, does the reworked flag logic
   stop over-firing on sparse designs.
- Impact: high (it's also the retry-loop feedback signal). Effort: **M**.

**R3-c — Brief-lint v2 (`brief_lint.py`).**
1. Fix false positive (a): boldness check widened to a families-of-
   phrases match (or downgraded to a warning) so valid medium wording
   passes; sync vocabulary with A's final v3 template at fan-in.
2. Fix false positive (b): diversity caps scale with batch size —
   `max(2, ceil(N * 0.4))` for palette (a 5/5 split on N=10 must lint
   clean), `max(2, ceil(N * 0.3))` for backdrop device.
3. New checks: (i) FM-8 guard — geometric shape-words ("triangle",
   "rectangle", "square", "circle") used to describe a gap/opening/space
   in a brief → error; (ii) FM-10 pendulum guard at batch level — for
   N ≥ 6, at least one and at most ~30% of briefs use a backdrop device
   (floor AND ceiling, warning-level); (iii) FM-9 — stem/bouquet/
   herbarium-keyword briefs missing a bottom-edge/grounding clause →
   warning.
- Impact: medium (protects both modes; mode B hard-gates on it). Effort:
  **S**.

**R3-d — Cowork seam-population script (owner-requested).** A thin CLI the
Cowork deep-research session (or the owner) can run to load mode-B briefs:
`python -m pipeline.seed_mode_b <briefs.json>`. Behavior: parse the JSON
array (the deep-research template's exact schema), run `lint_batch`,
print a human-readable preview table (niche, palette family, backdrop
device or none, occupant summary, word count) plus all lint findings —
then STOP. Insertion only with an explicit `--commit` flag (dry-run is
the default, per the reversibility policy), which calls the existing
`seed_candidates_from_briefs` (all-or-nothing, hard lint via
`assert_batch_valid`) and prints the inserted candidate IDs. No new
insert logic — the CLI wraps the round-2 seam, it must not fork it.
Update `docs/deep-research-briefing-template.md` to the v3 field wording
(integration vocabulary, occupant conditionality, backdrop rebalance,
bottom-edge rule) and add the comparative-trait protocol note (every
recorded trait ships with its applicability condition — the FM-1 lesson:
trait 4 lost its conditionality in translation and caused a failure mode).
- Impact: medium (unblocks the 5/5 validation split). Effort: **S**.

**R3-e — Etsy comparative deep research (owner-approved, runs in a
PARALLEL Cowork/Chrome session — NOT in the code session).** Scoped as
*comparative*: trait deltas between bestseller-badged listings and the
rounds-1/2 generated batches (what do bestsellers do that our batch
doesn't, and vice versa), every trait recorded WITH its applicability
condition; traits-only protocol per S4-a (no competitor imagery saved, no
shops/listings named). Outputs: (1) 5 mode-B briefs as the template's
JSON, loaded via R3-d's CLI; (2) a short traits-delta memo committed to
`docs/`. Session prompt: `docs/2026-07-21-round3-deep-research-session-prompt.md`.
The code session treats this as an external input: it prepares the 5
mode-B slots and waits; it never blocks on it (validation can fall back
to all-10 mode-A if the research session hasn't run — owner call at the
validation gate).

## 4. Execution order + parallelization

Three near-disjoint code areas + one human-session dependency:

```
  A ▶  R3-a          prompt-craft research pre-task, then art_brief.py
        │             template v3, generate.py scaffold v2 (+ version bumps)
  B ▶  R3-b          critic_pass.py rubric v3, flag-note rework,
        │             subject-extent stat, calibration refresh vs 15-24
  C ▶  R3-c + R3-d   brief_lint.py v2, seed_mode_b CLI,
        │             deep-research-briefing-template.md v3
        └── FAN-IN: C's lint vocabulary + the briefing doc consume A's
            final template wording (same seam as round 2); A and B are
            disjoint files this round. Then the zero-cost critic re-run
            on masters 15-24, diff vs §1.
  PARALLEL (owner session, not code): R3-e deep research → 5 mode-B
            briefs JSON + traits-delta memo
  LAST ▶ validation (serial, gated, real money)
```

Also in scope at fan-in (small, prevents a third data loss): stop the
`db/base_artwork/<candidate_id>.png` calibration-fixture filename
collision — move calibration masters to a dedicated non-colliding path
(e.g. `db/calibration_masters/`), repoint the two known-failing tests,
and either re-baseline them on current masters or retire the stale 6/7
entries explicitly. The suite must end the round green with zero
known-failing tests, or with the exclusion documented in the ledger.

**Validation (go/no-go):** 10 new candidates, base artwork only, NO
upscale, split **5 mode-A / 5 mode-B** (mode-B briefs from R3-e, loaded
through R3-d's CLI). Fresh niches allowed for mode B (research-driven);
mode A re-uses round-2 niches for comparability where sensible.
Propose-then-stop before any live Replicate call: print all 10 briefs,
est. cost, throttle/payment-method status. Owner blind-reviews
good/refine/reject without knowing which mode produced which; reveal the
mapping after grading. **Pass criteria vs the 5/5/0 baseline:** ≥ 6 good,
0 reject, AND each round-3 integration defect class (unconnected/
mis-scaled secondary subject; drawn containment geometry; bottom-edge
blank band) appears in at most 1 design, AND backdrop-device usage lands
in 1–4 of 10 (pendulum check — neither extinct nor dominant). Secondary
read-outs: mode A vs mode B grade split; anatomy defects (should be 0).

## 5. Open questions / owner decision gates

1. **Replicate payment method / auto-reload** — still pending from round
   2; round 2's batch needed 4 retries purely from granted-credit queue
   backpressure. Owner-only action; code keeps conservative pacing until
   it lands.
2. **Scaffold v2 scope** — removing "centered subject" and "dense
   composition" from the scaffold is a behavior change for ALL future
   generations, not just briefs that need it. Recommendation: yes (the
   brief now carries density/hierarchy explicitly), but it's a
   confirm-before-build item for Agent A.
3. **Calibration-fixture relocation** — recommend doing the small rename
   now (it has destroyed masters twice); confirm.
4. **Mode-B fallback** — if the deep-research session hasn't produced its
   5 briefs by validation time: wait, or run all-10 mode-A? Recommendation:
   wait (the split is the point of this round's validation design).

Steps 5–7 of the round-1 consolidated plan (model A/B, gallery dedup,
listing-shape decision) and the full landscape-orientation path remain
deferred and untouched by this doc.

---

## PROMPT — paste from here down into a fresh Claude Code session

You are executing the round-3 generation-quality plan in the qhoto_printshop
repo: `docs/2026-07-21-generation-quality-round3-plan.md`. Read, in this
order, before writing any code: `CLAUDE.md` (hard constraints, v4.11), the
round-3 plan (especially §2 failure taxonomy and §3 R3-a…R3-e), and skim
`docs/2026-07-21-generation-quality-round2-plan.md` +
`.superpowers/sdd/round2-progress.md` for the round-2 context this builds
on. Do not guess at behavior that's already specified.

### Ground truth you must not re-litigate

- Round-2 validation PASSED: candidates 15–24, owner grades 5 good
  (15, 17, 18, 19, 21) / 5 refine (16, 20, 22, 23, 24) / 0 reject — the
  new frozen baseline. Verify the id↔niche mapping with one SELECT on
  `candidates` (ids 15–24) against the §1 table before recalibrating
  anything; the mapping is presentation-order-assumed.
- Backdrop-device usage went 8/10 (round 1) → 0/10 (round 2). Owner
  ruling: it's a good device that should appear SOMETIMES. Rebalance,
  don't re-prohibit and don't restore the old default.
- Owner ruling on sparseness: one large dominant subject with generous
  empty space (optionally on a badge/backdrop) is a legitimate style and
  must PASS; the defect is a mostly-empty frame with a SMALL subject.
  This must be enforced in rubric text and flag logic — round 2 proved a
  doc comment enforces nothing (the candidate-12 REJECT).
- Round 2's brief-lint tripped two false positives on a clean batch
  (boldness phrase-match too literal; palette cap of 2 can't admit a 5/5
  split on N=10). These are lint bugs to fix, not brief defects.
- Round 2's 4/10 generation timeouts were granted-credit queue
  backpressure, NOT 429s and NOT low balance. The payment-method account
  action is still owner-pending; keep conservative pacing.
- The deep research (R3-e) runs in a SEPARATE owner-driven Cowork
  session, approved and scoped comparative. You build the seam tooling
  (R3-d) and the 5 mode-B validation slots; you never run browser
  research yourself and never block on it.

### Method — SDD + parallel sub-agents in worktrees

Follow the repo's SDD convention (`.superpowers/sdd/`): one task = one
commit, brief before / report after, append to a NEW progress ledger
(`round3-progress.md` — don't touch the existing ones). Full test suite
after every task; round-2 close was 411 passed + 2 known-failing
(calibration-fixture collision — being FIXED this round at fan-in, see
below). Confirm on first run, stay green.

**Stage 0:** confirm clean tree, base branch `fix/generation-quality-round3`
off master (merge round 2's branch to master first if not already done —
ask me, ff-only expected). Spawn three sub-agents in isolated git
worktrees (`isolation: "worktree"`), branches off that base:

- **Agent A — R3-a (brief template v3 + scaffold v2).** FIRST a focused
  web-research pre-task: FLUX.1 [schnell] prompting for small-subject
  integration — contact phrasing vs. positional prepositions, explicit
  relative scale, subject-first ordering, constraint-stacking limits at
  4-step inference; write findings + sources into the task report and cite
  which finding motivates each template change. THEN rewrite
  `ART_BRIEF_PROMPT_TEMPLATE` (occupant conditionality incl. dynamic-pose
  preference; integration vocabulary — scale/contact/anatomy in
  positive-only language; negative-space wording hygiene — never
  shape-words for emptiness; bottom-edge grounding for stem-native
  subjects; backdrop-device rebalance with sibling-note floor AND cap;
  conditional density: dense full-frame OR large-dominant-subject sparse)
  and `POSITIVE_SCAFFOLD` (drop "centered subject" + "dense composition",
  keep flat/full-bleed/crisp, add edge-contact wording) — scaffold change
  is gated on my confirm (open question 2), ask before committing it.
  Bump `BRIEF_TEMPLATE_VERSION` and `SCAFFOLD_VERSION` to "v2". Keep the
  T5 240-token test green; word cap unchanged (60/75) — if it must rise,
  stop and ask.
- **Agent B — R3-b (critic rubric v3 + sparse gate).** Amend criterion 3
  (secondary-subject anatomy, smudge-merging), criterion 4 (three round-3
  defect classes: contactless layered subject; drawn containment
  geometry; bottom-edge blank band), criterion 6 + the rubric text
  carrying the owner's sparse ruling explicitly. Rework
  `local_sanity_flag_note` wording per plan §3 R3-b-3. Add the
  subject-extent stat (largest connected non-background component bbox
  fraction on the 512px thumbnail) to `compute_image_sanity_stats`, gate
  the flag on cov-low AND extent-small, calibrate on masters 5–24
  (sparse anchors: 12 and 22 must not be over-flagged). 7 criteria kept,
  amend wording only, never renumber. Restate the calibration
  doc-comment against masters 15–24.
- **Agent C — R3-c + R3-d (lint v2 + seam CLI + doc).** Fix the two lint
  false positives (boldness families-of-phrases or warning-level;
  size-proportional diversity caps — a 5/5 palette split on N=10 lints
  clean). Add: FM-8 shape-word-for-gap error; FM-10 device floor/ceiling
  batch warning (N ≥ 6: ≥ 1 and ≤ ~30%); FM-9 grounding-clause warning
  for stem-native briefs. Build `python -m pipeline.seed_mode_b
  <briefs.json>`: parse → lint → preview table + findings → STOP;
  insert only with `--commit`, via the EXISTING
  `seed_candidates_from_briefs` (never fork the insert path). Update
  `docs/deep-research-briefing-template.md` to v3 wording + the
  comparative-trait/applicability-condition protocol. Build against the
  plan's field list; reconcile vocabulary with A's final template at
  fan-in.

A and C share the template-vocabulary seam (same as round 2); A and B are
disjoint files this round. B owns critic_pass.py exclusively.

### Fan-in (coordinator, you)

Merge A → B → C onto the base branch, reconcile C's lint vocabulary and
the briefing doc against A's shipped template text, full suite green.
Fix the calibration-fixture collision (open question 3, ask me first):
move calibration masters out of `db/base_artwork/<id>.png` into a
dedicated path, repoint the two known-failing tests, re-baseline or
explicitly retire the stale 6/7 entries — the suite ends this round
green with no known-failing carve-outs. Then, zero design cost: re-run
the pipeline critic on masters 15–24 and diff per-criterion verdicts
against the plan's §1 scorecard — amended criterion 4 should flag 22's
contactless beetle and 23's drawn triangle, criterion 3 should flag 24's
missing wing, and NO sparse design should be rejected on
coverage/composition grounds. Report the diff to me.

### Validation — LAST and GATED

Prepare the 10-candidate round-3 validation: 5 mode-A through the v3
writer + 5 mode-B slots for the briefs I'll produce in the parallel
deep-research session (loaded via `pipeline.seed_mode_b`, dry-run first,
`--commit` only after I've seen the preview). Base artwork only — NO
upscale. If my research session hasn't produced the briefs yet, WAIT
(open question 4 default) — don't silently fall back to all mode-A.
**STOP before any live Replicate call**: print the exact plan (all 10
briefs, est. cost, pacing/payment-method status) and wait for my
explicit "proceed". Present the 10 raw masters for blind grading WITHOUT
revealing modes; reveal the mapping after I've graded. Pass = ≥ 6 good,
0 reject, each integration defect class (contactless/mis-scaled subject;
drawn containment geometry; bottom-edge band) in ≤ 1 design, and
backdrop-device usage in 1–4 of 10. Report GO/NO-GO + the mode-A-vs-B
split.

### Hard rules (CLAUDE.md + reversibility policy)

- No real external calls (Replicate/Gelato/Etsy/Telegram/R2) without my
  explicit go-ahead; the validation batch is the only live spend in
  scope and is propose-then-stop.
- FLUX.1 [schnell] only; never substitute dev. One image-generation per
  design; the 3-attempt critic-retry cap is the only exception.
- Flag contradictions with SPEC v4.11 / CLAUDE.md before acting.
- Commit per passing stage; keep the tree green.

Before writing code, ask me: (1) Replicate payment-method status (pacing
defaults depend on it), (2) scaffold-v2 confirm (open question 2),
(3) calibration-fixture relocation confirm (open question 3), (4) confirm
the id↔niche mapping your SELECT produced matches the §1 table.
