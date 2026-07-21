# Generation-quality round 2 — follow-up plan + code-session kickoff (2026-07-21)

Follows `docs/2026-07-20-remediation-plan-consolidated.md` +
`docs/2026-07-20-execution-steps-1-4-kickoff.md`. Steps 1–4 of that plan are
**executed and validated**: the 10-candidate validation batch ran (candidates
5–14, base artwork only, no upscale) and the owner's blind review came back
**3 good (8, 10, 12) / 7 refine / 0 reject** — strictly dominating the S4-a
baseline (1 good / 2 refine / 4 reject). **Round 1 is a GO.** This doc is the
round-2 plan: fix the *new* failure modes the better batch exposed, add prompt
provenance, fix the misdiagnosed Replicate throttle, and add a second
(batch-ideation) input method.

**New frozen baseline for round 2: 3 good / 7 refine / 0 reject** (candidates
5–14 + owner grades below). The prior 7-master baseline is retired.

---

## 1. Round-1 validation scorecard (owner grades, ground truth)

| # | Niche | Grade | Owner note (condensed) |
|---|---|---|---|
| 5 | MCM botanical, bold filled foliage | Refine | Random orange orb in the empty "channel"; needs a real subject there (e.g. butterfly) or nothing |
| 6 | MCM botanical, abstract leaf composition | Refine | Good, but negative-space opening needs an insect (ladybug, butterfly…) |
| 7 | art deco geometric botanical line art | Refine | Not actually line art (brief drift); reads as an excellent border around a missing central subject |
| 8 | art deco geometric sunburst | **Good** | — |
| 9 | minimalist landscape, desert mesa at dusk | Refine | Should be landscape orientation, or needs a foreground subject |
| 10 | minimalist landscape, coastal cliffs | **Good** | — |
| 11 | wildflower botanical, meadow bouquet | Refine | Fore/middle ground good; background circle not |
| 12 | wildflower botanical, single stem study | **Good** ("great") | — |
| 13 | vintage herbarium print | Refine | Too many thin flowers; background circle is the accidental focal point |
| 14 | Japanese woodblock botanical | Refine | Flowers excellent; background circle out-of-place / negative space missing a subject (dragonfly?) |

## 2. Round-2 failure taxonomy (root causes, with code evidence)

**FM-1 — Backdrop-circle overuse. CONFIRMED in the stored briefs; highest
frequency.** 8 of the 10 persisted `candidates.art_brief` values (6, 7, 8, 10,
11, 12, 13, 14) contain a "circular backdrop", "circular frame", "circular
vignette", "arch motif", or "ochre arc". Root cause is the brief template
itself: `art_brief.py` field 4 reads *"optionally anchored by a backdrop shape
like a colored circle or arch"* — Haiku treats "optionally" as "yes" and the
two named examples are the only devices it ever picks. The bestseller-study
trait 4 ("backdrop shapes anchor **small** subjects") was ported into the
template without its conditionality: the device is for anchoring a small
single motif, not for dense full-frame compositions, where it becomes a
floating orb (5, 11, 13) or an out-of-place halo (14).

**FM-2 — Missing focal subject / unoccupied negative space. Highest
owner-impact.** 5, 6, 7, 13, 14 all read as excellent *surroundings* to a
central subject that isn't there. Root cause: the mandatory density clause
("dense full-frame composition") plus botanical niches steers FLUX toward
wreath/border/allover-pattern compositions, and the template has **no
focal-hierarchy field** — nothing requires one primary subject plus a rule for
what occupies any enclosed negative space. The random orb (5) is FLUX filling
that hole with the only anchor the prompt gave it (the backdrop circle).

**FM-3 — Medium drift.** 7's niche says "line art"; the delivered brief says
"medium-weight lines **and bold filled shapes**", and the render came out
filled. The template's field-3 boldness vocabulary can override the niche's
medium instead of qualifying it.

**FM-4 — Orientation mismatch.** 9 is a landscape-native scene forced into
2:3 portrait with no foreground anchor. `generate_image` hardcodes
`aspect_ratio: "2:3"`; the landscape Gelato template config exists
(`config/static_config.json` `*_landscape` keys) but nothing upstream ever
selects it (`group_product.create_group_product` defaults
`orientation="portrait"` everywhere).

**FM-5 — Batch monotony (palette + device).** All 10 briefs draw from the
same sage/terracotta/olive/cream corner of palette family (a), and 8/10 share
the same backdrop device. Root cause: brief calls are per-candidate and
independent — the writer never sees its siblings, and a single fixed template
at temperature-ish sampling herds toward the same choices. A shopfront of 10
near-identically-palettes listings also merchandises badly.

**FM-6 — Replicate throttle misdiagnosis (correction, docs-verified
2026-07-21).** The round-1 session hit a 6 generations/minute throttle and
attributed it to the balance nearing the $5 floor. Wrong: balance was > $9.
Replicate's rate-limits doc states the *exact* observed number: **"If you have
been granted credit and don't have a payment method on file, you'll also be
rate limited to 1 request per second with a maximum of 6 requests per
minute"** (replicate.com/docs/topics/predictions/rate-limits). A separate,
softer mechanism throttles "as you approach running out of credit" (their
stated remedy: auto-reload keeping balance above $20). The fix is primarily an
**owner account action** (add a payment method and/or credit auto-reload), not
code — but the code currently has zero 429 handling and `replicate_client._predict`'s
error text speculates "outage or throttling, not a pipeline bug", which is how
the misdiagnosis happened.

**Provenance gap (owner-requested change).** Only `candidates.art_brief` is
persisted. The **full generation prompt** (brief + correction note + scaffold),
the correction-note history across retries, the template versions, and the
per-attempt prediction IDs are not stored anywhere — round-2's brief-template
changes would be unmeasurable against round 1 without this.

## 3. Candidate solutions

**R2-a — Brief-writer v2 (`art_brief.py`). The main quality lever.**
Rework `ART_BRIEF_PROMPT_TEMPLATE`:
1. *Focal hierarchy (new mandatory field, fixes FM-2):* every brief names ONE
   primary focal subject and states where it sits. Hard rule in the
   instructions: if the composition creates an enclosed opening or channel of
   negative space, it must either contain a small secondary subject
   (butterfly, ladybug, dragonfly, single bloom, sun/moon — chosen to fit the
   idiom) or the composition must close over it; an abstract floating orb is
   never the occupant. (This is the owner's own remedy on 5/6/14, generalized.)
2. *Backdrop device demoted (fixes FM-1):* remove "colored circle or arch"
   from field 4's phrasing. Replace with: a backdrop shape is a deliberate
   anchoring device for a SMALL, single-motif subject only; dense full-frame
   compositions use none. When one is used, pick from a wider menu (arch,
   wash, band, sun disc behind the subject, torn-paper edge…), and the shape
   must sit *behind and touching* the subject — never floating in leftover
   space.
3. *Medium fidelity (fixes FM-3):* field 3 becomes "qualify the niche's
   medium, never replace it" — a line-art niche stays line art with confident
   medium-weight strokes; boldness language adapts to the stated medium.
4. *Batch diversity (fixes FM-5):* `generate_art_brief` gains an optional
   `sibling_briefs: list[str]` parameter; `run_generate_cycle` passes the
   briefs already written this batch, and the template instructs: choose a
   palette, composition device, and focal-subject type distinct from the
   siblings; both palette families must appear across a batch.
5. *Portrait-landscape rule (cheap half of FM-4):* a landscape-native scene
   rendered in portrait must name a foreground anchor subject (the owner's own
   "or" on 9). The full landscape-orientation path is a separate, gated
   decision — see Open questions.
Word cap: keep the brief ≤ 60 words if possible, allow 75 if the focal field
needs it — but then re-verify the T5 budget test (`approx_t5_tokens`, 240-token
ceiling incl. worst-case correction note) still passes; trim the scaffold's
redundant clauses before raising any cap.

- Root cause: FM-1/2/3/5 (+ half of FM-4). Impact: **high**. Effort: **S–M**
  (template + one plumbed parameter + tests; no schema change). Confidence:
  high — every fix maps 1:1 to an owner note plus stored-brief evidence.

**R2-b — Critic rubric v2 (`critic_pass.py`).** The pipeline critic passed
designs the owner graded refine — it can't see the new failure modes.
1. Amend criterion 4 (composition) to name the two new defect classes:
   an unintegrated floating backdrop shape/orb, and an enclosed negative-space
   opening with no focal occupant. Keep 7 criteria — amend wording, don't
   renumber (per-criterion telemetry comparability).
2. Add a brief-vs-image adherence note to criterion 7's text check: does the
   image realize the brief's named focal subject and medium?
3. Restate the calibration set against the NEW masters: rubric should grade
   {8, 10, 12} good and {5, 6, 7, 9, 11, 13, 14} refine (none reject). Local
   sanity gate thresholds stay untouched — measured cov for 5–14 is 0.058 to
   0.933, all above the 0.05 hard-fail floor. **Calibration caveat (measured
   2026-07-21):** design 12 — owner-graded "great" — sits at cov 0.058,
   inside the 0.05–0.12 flag-to-critic band; the recalibrated rubric must
   PASS it despite the flag (single-stem studies are a legitimate low-cov
   idiom). It becomes the new must-pass borderline anchor, replacing old
   master 3. Re-run the critic on all 10 and diff against §1 — zero design
   cost, same protocol as the round-1 fan-in re-run.
- Impact: medium (measurement + retry feedback quality). Effort: **S**.

**R2-c — Prompt/brief provenance (owner-requested).** New table
`generation_attempts`: `candidate_id`, `attempt_number`, `prompt_text` (the
exact string sent to Replicate), `art_brief_snapshot`, `correction_note`,
`brief_template_version`, `scaffold_version`, `model`, `prediction_id`,
`created_at`. Written on **every** FLUX call including critic-retry
regenerations (`generate_for_candidate` is the single choke point). Add
`BRIEF_TEMPLATE_VERSION` / `SCAFFOLD_VERSION` constants bumped on every
template edit, so round-2 vs round-1 briefs are queryable. Backfill what's
recoverable for candidates 5–14 (briefs exist; prompts are reconstructable as
brief + current scaffold since no correction notes fired).
- Impact: medium (enables all future prompt iteration to be measured).
  Effort: **S**. One additive schema block, no migration conflicts expected.

**R2-d — Replicate throttle handling.**
1. **Owner account action (not code):** add a payment method on the Replicate
   account (lifts the 6/min granted-credit cap) and ideally enable credit
   auto-reload with the balance floor ≥ $20 (avoids the low-balance soft
   throttle). Code session flags this and waits; it can't do it.
2. Code: typed `ReplicateThrottledError` on 429, honoring the reset hint in
   the response body / `retry-after`; pace `run_generate_cycle` between
   candidates (config-driven inter-call delay, default safe at 6/min until
   the account action lands); correct `_predict`'s misleading error text.
- Impact: low-medium (batch reliability + correct diagnosis next time).
  Effort: **S**.

**R2-e — Input mode B: batch ideation seam (owner question — recommendation:
YES, as a seam, not a fork).** Assessment of "deeper research (Claude in
Chrome) produces a batch of ideas/briefs/prompts the pipeline executes":
- *For:* the highest-signal research so far (S4-a bestseller study) was
  exactly this — an interactive Cowork/Chrome Etsy session, which the cron
  pipeline structurally cannot do (scheduled functions, no browser). A batch
  author sees all N briefs at once — diversity control comes free (FM-5's
  strongest fix). Brief authoring moves to a stronger model + a human glance
  *before* any Replicate spend. Cost ≈ zero.
- *Against / risks:* it's a manual, session-bound step — it must not become
  the only path (the twice-daily cron cadence stays autonomous on mode A).
  Biggest design risk is **forking the prompt logic**: if mode B injects
  full generation prompts, the scaffold/token/versioning machinery is
  bypassed and provenance breaks.
- *Design (the seam):* mode B produces **briefs, not prompts**. A
  `seed_candidates_from_briefs(json)` CLI/function ingests
  `[{niche, trend_source, art_brief, go_hold_kill_rationale}]`, inserts
  candidates with `art_brief` pre-filled (so `generate_for_candidate` skips
  the Haiku call — the hook already exists: it only writes a brief `if not
  candidate.get("art_brief")`), and everything downstream (scaffold, token
  budget, critic, provenance) is byte-identical to mode A. A shared
  **brief-lint** validator enforces the R2-a mandatory fields + batch
  diversity rules on BOTH modes (reject a batch where >2 briefs share a
  backdrop device or palette). Plus one authoring doc:
  `docs/deep-research-briefing-template.md`, the reusable prompt for the
  Cowork/Chrome research session (what to observe on Etsy — traits only,
  never saving competitor imagery, per the S4-a protocol — and the exact JSON
  to emit).
- Impact: medium-high (research quality + diversity). Effort: **M** (ingest
  function + lint + doc + tests). Confidence: medium-high.

## 4. Execution order + parallelization

Smaller surface than round 1; three near-disjoint areas:

```
  A ▶  R2-a + R2-b   art_brief.py, generate.py (sibling plumbing),
        │             critic_pass.py rubric + recalibration
  B ▶  R2-c + R2-d   schema.sql (generation_attempts), generate.py
        │             (attempt logging), replicate_client.py (429/pacing)
  C ▶  R2-e          seed/ingest module, brief-lint (imports A's field
        │             definitions), authoring doc
        └── FAN-IN: A+B touch generate.py (sibling param vs attempt logging
            — trivial merge); C's brief-lint consumes A's final template
            fields, so C finishes that seam at fan-in. Full suite green.
  LAST ▶ validation (serial, gated, real money)
```

**Validation (go/no-go):** 10 new candidates, **base artwork only, NO
upscale** (the `no_upscale` path from round 1), split **5 mode-A / 5 mode-B**
(the mode-B five authored in a Cowork deep-research session before the code
session's batch run). Propose-then-stop before any live Replicate call: print
the 10 briefs, est. cost, confirm the account action (R2-d-1) status. Owner
blind-reviews on good/refine/reject without knowing which mode produced which.
**Pass criteria vs the new 3/7/0 baseline:** ≥ 5 good, 0 reject, AND the two
named defect classes (floating orb/backdrop shape; unoccupied negative space)
each appear in at most 1 design. Secondary read-out: mode A vs mode B grade
split (informs how much to invest in mode B).

## 5. Open questions / owner decision gates

1. **Replicate payment method / auto-reload** — owner-only account action;
   without it every batch is capped at 6/min (a 10-design batch is fine;
   retries + upscales in a real run are not).
2. **Landscape orientation scope** — the full path (orientation column,
   3:2 generation, landscape template selection, crop-group/mockup review)
   is real scope touching publish flow; R2-a-5's foreground-anchor rule is
   the cheap stopgap. Build now or defer to its own round? Recommendation:
   defer, revisit if landscape-native niches keep under-grading.
3. **Brief word cap** 60 → 75 if the focal field needs room (T5 budget test
   must stay green either way).
4. **Validation split** 5/5 mode A/B — confirm, or all-10 mode A if you'd
   rather not run the deep-research session first.

Steps 5–7 of the round-1 consolidated plan (model A/B, gallery dedup,
listing-shape decision) remain deferred and are untouched by this doc.

---

## PROMPT — paste from here down into a fresh Claude Code session

You are executing the round-2 generation-quality plan in the qhoto_printshop
repo: `docs/2026-07-21-generation-quality-round2-plan.md`. Read, in this
order, before writing any code: `CLAUDE.md` (hard constraints, v4.11), the
round-2 plan (especially §2 failure taxonomy and §3 R2-a…R2-e), and skim
`docs/2026-07-20-remediation-plan-consolidated.md` for the round-1 context it
builds on. Do not guess at behavior that's already specified.

### Ground truth you must not re-litigate

- Round-1 validation PASSED: candidates 5–14, owner grades 3 good (8, 10, 12)
  / 7 refine / 0 reject — this is the new frozen baseline.
- The Replicate 6/min throttle was NOT low balance (balance > $9). It is the
  documented granted-credit-without-payment-method cap (1 req/s, 6/min —
  replicate.com/docs/topics/predictions/rate-limits). Flag the account action
  to me; don't code around a limit that a dashboard change removes.
- 8 of the 10 stored briefs contain a circle/arch/arc backdrop device —
  verify with one SELECT on `candidates.art_brief` (ids 5–14) before touching
  the template, so your rewrite targets the real text.

### Method — SDD + parallel sub-agents in worktrees

Follow the repo's SDD convention (`.superpowers/sdd/`): one task = one commit,
brief before / report after, append to a NEW progress ledger
(`round2-progress.md` — don't touch the existing ones). Full test suite after
every task; baseline was 380 passed at round-1 close — confirm on first run,
stay green.

**Stage 0:** confirm clean tree on master, then base branch
`fix/generation-quality-round2`. Spawn three sub-agents in isolated git
worktrees (`isolation: "worktree"`), branches off that base:

- **Agent A — R2-a + R2-b (prompts + critic).** `art_brief.py` template v2
  (focal-hierarchy field; backdrop device demoted + widened menu, never a
  floating shape; medium fidelity; sibling-diversity instructions;
  portrait-foreground rule), `generate.py`/`run_generate_cycle` sibling-brief
  plumbing, `critic_pass.py` criterion-4 amendment (floating orb + unoccupied
  negative space) and criterion-7 brief-adherence note — amend wording, do
  NOT renumber criteria. Restate the calibration doc-comment against masters
  5–14; note owner-great design 12 measures cov 0.058 (inside the
  flag-to-critic band) — the rubric must pass it despite the flag (plan §3
  R2-b-3 caveat). Keep the T5 240-token test green; if the brief cap must rise past 60
  words, stop and ask me first (open question 3).
- **Agent B — R2-c + R2-d (provenance + throttle).** `generation_attempts`
  table + write path on every FLUX call in `generate_for_candidate` (incl.
  retries), `BRIEF_TEMPLATE_VERSION`/`SCAFFOLD_VERSION` constants, backfill
  for candidates 5–14; `replicate_client` 429 typed error honoring the reset
  hint, config-driven inter-call pacing in `run_generate_cycle` (default safe
  at 6/min), fix `_predict`'s misleading "outage" error text.
- **Agent C — R2-e (mode-B seam).** `seed_candidates_from_briefs` ingest
  (briefs, NOT prompts — everything downstream of `candidates.art_brief`
  stays byte-identical to mode A), shared brief-lint validator (mandatory
  fields + batch-diversity rules, applied to both modes), and
  `docs/deep-research-briefing-template.md` (traits-only Etsy observation
  protocol per S4-a — no competitor imagery saved — and the exact JSON
  schema). C's lint must consume A's final field definitions — build against
  the plan's field list, reconcile at fan-in.

A and B both touch `generate.py` (sibling param vs. attempt logging) —
trivial merge, resolve by keeping both. B owns the only `schema.sql` block.

### Fan-in (coordinator, you)

Merge A → B → C onto the base branch, wire C's lint to A's final template
fields, full suite green. Then, zero design cost: re-run the pipeline critic
on masters 5–14 and diff per-criterion verdicts against the owner scorecard
(§1 of the plan) — the amended criterion 4 should now flag 5, 11, 13, 14's
orb/negative-space defects. Report the diff to me.

### Validation — LAST and GATED

Prepare the 10-candidate round-2 validation: 5 mode-A candidates through the
new brief writer + 5 mode-B slots awaiting briefs I'll author in a separate
deep-research session (using Agent C's authoring doc). Base artwork only —
NO upscale (`no_upscale=True`). **STOP before any live Replicate call**:
print the exact plan (briefs, est. cost, throttle-cap status, payment-method
question) and wait for my explicit "proceed". After the batch runs, present
the 10 raw masters for my blind grading WITHOUT telling me which mode
produced which; reveal the mapping after I've graded. Pass = ≥ 5 good,
0 reject, and floating-shape / unoccupied-negative-space defects each in at
most 1 design. Report GO/NO-GO + the mode-A-vs-B split.

### Hard rules (CLAUDE.md + reversibility policy)

- No real external calls (Replicate/Gelato/Etsy/Telegram/R2) without my
  explicit go-ahead; the validation batch is the only live spend in scope and
  is propose-then-stop.
- FLUX.1 [schnell] only; never substitute dev. One image-generation per
  design; the 3-attempt critic-retry cap is the only exception.
- Flag contradictions with SPEC v4.11 / CLAUDE.md before acting.
- Commit per passing stage; keep the tree green.

Before writing code, ask me: (1) the Replicate payment-method/auto-reload
account action (I need to do it, you need to know its status for pacing
defaults), (2) landscape-orientation scope (recommend defer — confirm),
(3) whether the 5/5 mode-A/B validation split stands.
