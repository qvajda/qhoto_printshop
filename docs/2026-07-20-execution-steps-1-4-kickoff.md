# Execution steps 1–4 + code-session kickoff prompt (2026-07-20)

Source of truth: `docs/2026-07-20-remediation-plan-consolidated.md` (which folds
the 2026-07-19 remediation plan + the executed S4-a taxonomy). This doc covers
**only steps 1–4** of that plan's execution order; steps 5–7 (model A/B,
gallery dedup, listing-shape decision) are out of scope here.

S4-a is already **done** (folded into the consolidated plan), so it is not a
live step. The four steps below are: fix the instruments (#3) → fix the biggest
lever (S4-b/c) → improve the measuring stick (S4-d) → **validate on 10 fresh,
un-upscaled candidates**.

---

## Why sub-agents: the dependency graph

Steps 1–3 touch three near-disjoint areas of the codebase and can be built in
**parallel worktrees**, then merged and validated together in step 4:

```
        ┌──────────────────────────────────────────────┐
        │  PARALLEL (3 isolated git worktrees)          │
        │                                               │
  A ▶  #3 error handling      http.py, anthropic_client.py,
        │                     parse_json_response, retry, call-log table
        │                                               │
  B ▶  S4-b + S4-c(1-2)       new art_brief module, generate.py scaffold,
        │                     research→generate seam, T5 token test,
        │                     candidates.art_brief column
        │                                               │
  C ▶  S4-d                   critic_pass.py (cov metric + calibration),
        │                     critic_pass_attempts schema, two-tier gate
        └───────────────┬───────────────────────────────┘
                        │  FAN-IN: coordinator merges A+B+C onto one
                        │  branch, resolves schema.sql conflicts, runs
                        │  the FULL test suite to green
                        ▼
  4 ▶  VALIDATION (serial, last)   regenerate 10 candidates, base artwork
                                    only (NO upscale), owner blind-review
                                    vs the S4-a frozen baseline → GO / NO-GO
```

**Parallel-safety notes the coordinator must enforce:**

- **schema.sql is the one shared file.** B adds `candidates.art_brief`; C
  extends `critic_pass_attempts` + (optionally) adds the `cov` column. Give B
  and C **separate, non-overlapping migration blocks** and expect a trivial
  merge conflict in `schema.sql` / the migration list — resolve by
  concatenation, not by picking one side.
- **C's two-tier gate calls Anthropic** (Haiku vision pre-filter) and so
  benefits from A's typed errors, but must be built against the *current*
  `anthropic_client` interface, not blocked on A. Wire it to A's new typed
  errors during fan-in.
- **B and C do not import each other.** S4-d(4) (feeding per-criterion
  failures back into the brief) is the only real coupling — implement the
  *data shape* in C, wire the *consumer* in B, and finish that one seam during
  fan-in, not in isolation.
- A is fully independent of B and C.

Recommended: one coordinator session spawns three sub-agents in **git
worktrees** (`isolation: "worktree"`), each on its own branch off the same base
commit; coordinator does the merge, conflict resolution, full-suite run, and
then step 4.

---

## Step 1 (Agent A) — Finding 3: error handling, typed errors, logging

Goal: no Anthropic response ever silently becomes `{}` or a JSONDecodeError far
from its cause. **Sequenced first because steps 2–4's measurements are poisoned
by silent `{}` responses** (S4-a explicitly deferred the live-critic re-run for
this reason).

- `http.send`: never return `{}`; raise `EmptyResponseBodyError(status,
  headers)` capturing `request-id`/`cf-ray`; log it.
- `anthropic_client`: validate the envelope — require `type == "message"`,
  record `stop_reason`+`usage`, raise `TruncatedResponseError` on
  `max_tokens`, handle `pause_turn` by continuing the turn, raise
  `NoTextContentError` (listing the block types returned) when text is absent.
- `parse_json_response`: wrap `json.loads`, raise `MalformedJSONError` with the
  first ~200 chars.
- Centralize retry: transient classes only (timeouts, 5xx/429/529, honor
  `retry-after`), one place; validation errors propagate.
  `compliance_draft`'s 3-attempt loop catches only `ValueError`/
  `MalformedJSONError`, not bare `Exception`.
- Structured call log: request-id, stop_reason, token usage → small DB
  table/logfile.
- While in here: verify the `web_search` tool-type string + `pause_turn`
  semantics against current Anthropic docs (clears the UNVERIFIED marker at
  `anthropic_client.py:30-33`).
- **Tool-fit decision (flag to owner, don't decide solo):** the official
  `anthropic` Python SDK does typed errors/retries/`retry-after` natively and
  deletes most of the above. The raw-httpx posture exists for Cloudflare-1010
  on *Gelato/Etsy* traffic only — Anthropic doesn't need it, so the SDK is
  admissible. Present both paths; let the owner pick.

Effort: S–M. No external decisions block coding.

## Step 2 (Agent B) — S4-b art-brief stage + S4-c(1-2) generation fix

Goal: replace keyword-into-generic-scaffold with a per-candidate visual brief +
a positive-only, budget-checked scaffold. **Biggest quality lever** (RC-A/B/C).

- **S4-b:** new module — one Haiku-class text call turning {niche keyword,
  trend rationale, buyer segment} → a ≤60-word positive visual brief. Store as
  `candidates.art_brief`. Mandatory brief fields (from S4-a): one concrete
  subject in a **named art idiom**; a **density/coverage clause**; **mark
  boldness** (never unqualified "line art"); a **ground** (+ optional backdrop
  shape); **2–4 named accent colors**. The no-go list moves into the
  *brief-writing instructions* — the image model never sees negations.
- **S4-c(1):** rewrite `NICHE_STYLE_SCAFFOLD` to ~40 words positive-only; delete
  `NO_GO_LIST` from the image prompt. Scaffold vocabulary from S4-a: "flat 2D
  full-bleed artwork", "one coherent centered subject", "dense composition
  filling the frame", "bold filled color zones with crisp clean edges", "warm
  muted palette on a soft cream ground". Generation prompt = `art_brief + ~30-
  word positive scaffold`.
- **S4-c(2):** build-time T5 token check — unit test fails if
  `t5_tokens(build_prompt(...)) > 240` incl. a worst-case correction note; move
  the correction note **before** the scaffold tail (`generate.py:53-54`), not
  last. Verify empirically with the `google/t5-v1_1-xxl` tokenizer offline
  first (confirms/kills RC-C).
- **Do NOT** touch the model tier — `flux-schnell` stays (S4-c(3) is a later,
  owner-gated step). CLAUDE.md hard constraint: schnell only, never dev without
  explicit sign-off.

Effort: M. New module + prompt + tests + one candidates column.

## Step 3 (Agent C) — S4-d critic telemetry + two-tier gate

Goal: make quality **measurable** and cheaper to gate. Runs parallel to Step 2.

- Restructure critic output `{passed, reason}` → per-criterion
  `{criterion_1..7: {passed, note}, overall}` persisted in
  `critic_pass_attempts` (schema extension). Adopt the owner's three tiers
  (good / refine / reject) so grades and critic verdicts stay comparable.
- **Add `cov` (subject-coverage) to the local sanity gate** (the S4-a headline
  fix): hard-fail below **0.05** (catches condemned 4, 6, 7 for free, no vision
  call), flag-to-critic **0.05–0.12**. Keep the existing stddev/edge test —
  complementary, not a replacement.
- **Restate the calibration set** to current files: must-FAIL {4, 6, 7},
  must-PASS {1, 2, 5}, borderline {3}; update the stale `critic_pass.py:39-45`
  comment (it cites fingerprints of overwritten images).
- Two-tier gate: free local sanity gate → cheap Haiku vision pre-filter on the
  flat master only → full Sonnet gallery+text pass for survivors.
- Expose the per-criterion failure shape for S4-b's regeneration feedback
  (consumer wired during fan-in).
- **Do NOT** soften rubric points 4/6 — S4-a found the minimalism-false-fail
  worry has no evidence in the current set; wait for live telemetry.

Effort: M. Net *reduces* per-candidate vision spend.

## Step 4 (coordinator, serial, LAST) — Validation: 10 un-upscaled candidates

**This is the go/no-go for whether steps 1–3 worked.** It is deliberately the
last step and validates all three code changes together, not just the prompt
rework.

- Precondition: A+B+C merged onto one branch, full test suite green.
- Generate **10 new candidates** end-to-end through the *new* path (art-brief →
  positive scaffold → schnell), across the S4-a baseline niche families.
- **Base artwork only — do NOT upscale.** `generate.generate_for_candidate`
  (`generate.py:58`) always runs `real-esrgan` ×8 (`replicate_client.py:16`,
  `UPSCALE_MODEL = "nightmareai/real-esrgan"`, scale=8 on the 832×1216 FLUX
  master) and only writes the row on upscale success. For validation, stop
  after the FLUX prediction and archive the raw 832×1216 output — add a
  `--no-upscale` path (or a `generate_base_only` variant) that skips the
  ESRGAN call and the DPI gate. Rationale: (i) we're judging *generation*, and ESRGAN halo is a
  separate RC-E variable that would confound the review; (ii) it halves the
  Replicate spend and latency for a throwaway batch.
- **This calls Replicate for real (money).** Per CLAUDE.md + the reversibility
  policy this is **propose-then-stop**: print the exact plan (10 base gens, no
  upscale, est. cost, the 10 niches/briefs) and **wait for the owner's explicit
  "proceed"** before any live call. Everything upstream runs on dry-run/mocks.
- Present the 10 raw masters to the owner for a **blind review** graded on the
  same good/refine/reject scale as the S4-a scorecard.
- **Pass criterion:** the new batch's owner-grade distribution **strictly
  dominates** the S4-a baseline (baseline = 1 good / 2 refine / 4 reject). If it
  does → steps 1–3 are effective, proceed to step 5 (model A/B) only if a
  fidelity ceiling remains. If it does not → the prompt rework alone is
  insufficient; do not proceed to spend, diagnose against the per-criterion
  telemetry that Step 3 now produces.

Effort: S (code) + the owner review. One gated live spend.

---

## PROMPT — paste from here down into a fresh Claude Code session

You are executing steps 1–4 of
`docs/2026-07-20-remediation-plan-consolidated.md` in the qhoto_printshop repo.
Read, in this order, before writing any code: `CLAUDE.md` (hard constraints,
v4.11), the consolidated remediation plan (especially "Finding 3", "Finding 4
→ S4-a", and the S4-b/c/d candidate solutions), and
`docs/2026-07-20-execution-steps-1-4-kickoff.md` (this step breakdown + the
sub-agent dependency graph). Do not guess at behavior that's already specified.

### Method — SDD + parallel sub-agents in worktrees

Follow the SDD convention already in this repo (`.superpowers/sdd/progress.md`):
one task = one commit, a task brief before + task report after, append to a
progress ledger (new files under `.superpowers/sdd/`, don't touch the existing
base-artwork/readiness ones). Run the FULL test suite after every task; a task
isn't done below full green (baseline: **316 passed, 0 skipped** — confirm on
first run).

**Stage 0 (before any code):** resolve the uncommitted state on master with me
(there may be an EOL/line-ending diff + untracked dirs from prior sessions —
don't branch on top of an undecided dirty tree). Then create a base branch
`fix/remediation-steps-1-4` off master.

**Parallelize steps 1–3 as three sub-agents in isolated git worktrees**
(`isolation: "worktree"`), each on its own branch off that base:

- **Agent A — Finding 3 error handling.** Scope: `http.py`,
  `anthropic_client.py`, `parse_json_response`, centralized retry, structured
  call-log table. Fully independent. Flag the anthropic-SDK-vs-raw-httpx
  tool-fit decision to me — do not decide it solo.
- **Agent B — S4-b + S4-c(1-2).** Scope: new art-brief module,
  `generate.py` scaffold rewrite (positive-only, delete `NO_GO_LIST` from the
  image prompt), research→generate seam, offline T5 token test + build-time
  240-token unit test, `candidates.art_brief` column. Keep `flux-schnell` —
  never substitute dev (CLAUDE.md hard constraint).
- **Agent C — S4-d.** Scope: `critic_pass.py` `cov` metric + restated
  calibration set + stale-comment fix, `critic_pass_attempts` per-criterion
  schema, two-tier gate (local → Haiku vision pre-filter → Sonnet). Do NOT
  soften rubric points 4/6 (S4-a found no evidence for it). Expose the
  per-criterion failure shape for B's regeneration feedback.

Give B and C **non-overlapping `schema.sql` migration blocks**; expect a
trivial concatenation conflict there and resolve by keeping both.

### Fan-in (coordinator, you)

Merge A → B → C onto `fix/remediation-steps-1-4`, resolving the `schema.sql`
conflict by concatenation. Wire the two cross-agent seams: C's typed-error
call sites onto A's new errors, and B's regeneration-feedback consumer onto
C's per-criterion failure shape. Run the full suite to green. Then, at zero
design cost, re-run the *pipeline* critic on the 7 baseline masters in
`db/base_artwork/` and diff its per-criterion verdicts against the S4-a vision
assessment (closes the "gates unproven live" gap).

### Step 4 — validation, LAST, and GATED

After fan-in is green, prepare the 10-candidate validation: 10 new candidates
through the new art-brief→positive-scaffold→schnell path across the S4-a
baseline niches, **base artwork only — NO upscale** (add a `--no-upscale` /
`generate_base_only` path in `generate.generate_for_candidate` that stops after
the FLUX prediction, skips `real-esrgan` and the DPI gate). **STOP before any live Replicate call**: print
the exact plan (10 base gens, no upscale, the briefs, estimated cost) and wait
for my explicit "proceed" — this is the only real-money, live step and
CLAUDE.md requires propose-then-stop for it. Everything upstream stays on
dry-run/mocks. After I approve and the batch runs, present the 10 raw masters
for my blind good/refine/reject grading. **Pass = the new distribution strictly
dominates the S4-a baseline (1 good / 2 refine / 4 reject).** Report GO/NO-GO;
do not proceed to any step-5 model A/B without a separate go-ahead.

### Hard rules (CLAUDE.md + reversibility policy)

- No real external calls (Gelato/Etsy/Telegram/Replicate/R2) without my
  explicit go-ahead. The only live call in this scope is Step 4, and it's
  propose-then-stop.
- FLUX.1 [schnell] only; never substitute dev (that's a later owner-gated
  step). One image-generation per design; the existing 3-attempt critic-fail
  regeneration cap is the one exception — work inside it.
- Flag contradictions with SPEC v4.11 / CLAUDE.md before acting; never silently
  patch around a hard constraint.
- Commit per passing stage; keep the tree green.

Ask me the Stage-0 dirty-tree question and the anthropic-SDK-vs-raw-httpx
tool-fit question before you start writing code.
