# qops v3 — resumption assessment and standing decisions (2026-08-13)

**Not a PRD.** This is the checkpoint that authorises a PRD v3 to be written
later, and records why. No build starts from this document.

**Predecessors:** `docs/2026-07-26-ways-of-working-overhaul-prd-v2.md` (the
design), `docs/2026-07-26-qops-prd-independent-review.md` (33 findings),
`.qops/issues.md` (the frozen import corpus).
**Board at time of writing:** gate 25 of 28, open GL-11, GL-69, GL-71.
Next session: `docs/2026-08-13-e12-kickoff.md`.

> **Amendment 2026-08-13 (planner, post-E12).** **O2 is satisfied** — E12 merged
> (PR #16 → `9c4eed1`, 810 green), GL-69 and GL-71 both closed, gate now **27 of
> 28** with **GL-11** the only open row. The §5 programme is carried into
> `docs/2026-08-13-e13-kickoff.md` unchanged in substance, with one correction
> to sequencing: **the secret scan did not run alongside E12** as O2 assumed, so
> it is now §7a of the E13 PRD and is sequenced *before* the research pass, not
> beside it. This document remains the authorising record; E13 is where its §5
> gets executed.

---

## §1. Verdict — resume, but it is a re-extraction, not a resume

### Why yes

1. **The PRD's one open question has already been answered, indirectly.** §10
   left scope open: *reduced build (≈4h) if go-live is within ~2 months, full
   build (≈10.75h) otherwise.* The standing owner decision of 2026-08-12
   retires activation as a planning variable — there is no launch date to pay
   back before. **By the PRD's own rule the full build is indicated.** This did
   not need re-arguing, only noticing.
2. **The board keeps generating evidence for its own automation.** Four
   consecutive integration passes found prose/cell drift; the 08-12 pass had to
   re-derive the gate count from the rows because the inherited number could not
   be reconstructed under any rule. Eight rows closed in header prose only. A
   correct manual discipline failing repeatedly is the case for a deterministic
   substrate.
3. **BL-6 already anticipates the orchard layer** — "generalize into a reusable
   pattern for sibling projects" has been parked since July.

### Why not straight away

1. **The PRD's evidence base is dead.** `.qops/issues.md` freezes the world at
   GL-21 open, GL-6 attempt 3 unstarted, PR #2 unmerged. The live board is at
   GL-74, PR #15, 803 green, mockup mission landed. Review finding C1 already
   called §1.1's measured state wrong *on the day it was written*; it is now 18
   days and ~15 sessions older. **Importing that corpus would import a fiction.**
2. **Two live measurements are still open.** GL-69 and GL-71 are cheap and are
   the last code-side rows on the gate. Starting a ~10h infrastructure build in
   front of them is a yak-shave, and it also wastes E12 as the natural "before"
   baseline for the acceptance test.

### Correction to the record — "partially started" overstates it

| Phase | Doc claims | Measured 2026-08-13 |
|---|---|---|
| 0 | partially executed, 2 items outstanding | correct — **but `scripts/qops_phase0.py` no longer exists**; only `scripts/__pycache__/qops_phase0.cpython-310.pyc` remains, and `git log --all --diff-filter=A` shows it was never committed |
| 1 | "already half-built" (review §D) | **0% executed.** `qops_phase1.py` likewise deleted and uncommitted (`.pyc` only). Hook spike never run — no `.qops/hook-spike/fired.log`, no `.claude/settings.json`. No labels, no milestones, no issue import |

**Do independently of any qops decision:** the outstanding **secret scan of git
history**. The repo is public, `HEAD` is clean, but Etsy OAuth / Gelato /
Replicate / Telegram tokens have moved through this project's life. The PRD
calls it the highest-value item in the whole plan and it has been open since
2026-07-26. If anything is found, **rotate first**; history rewriting is a
separate decision.

---

## §2. What changed in the tooling (input to the v3 research pass)

The Notion capture *"Etsy POD — way of working overhaul (4 items)"* listed four.
All four have moved; three of them plausibly **shrink** the build.

| # | Item | State 2026-08-13 | Bearing on qops |
|---|---|---|---|
| 1 | Matt Pocock's skills | 21 composable skills, official Claude Code marketplace, `/setup-matt-pocock-skills` per repo. Includes `/wayfinder` (multi-session planning), `/to-spec` → `/to-tickets`, `/grill-me`, dual-axis `/code-review`, `/tdd` | Overlaps §4.4 (agents with distinct responsibilities) and §4.7 (two-tier planning + named loops). Several components may become *configure*, not *build* |
| 2 | Opus 5 recommended changes | Anthropic guidance: remove "double-check your work" (Opus 5 self-verifies; re-asking burns tokens); delegates to subagents more readily and expands scope on its own judgement, so scope-fencing > verification-nagging; `effort` (low/medium/high/xhigh) is the primary cost lever | §2.3's ~10-week payback is computed on pre-Opus-5 economics and must be re-run. Also gives throttling a real knob. **Flags a tension with CLAUDE.md's verification-heavy conventions — those were earned by GL-22a and GL-48 and must not be dropped reflexively; the guidance is about redundant prompt-level nagging, not about measured verification** |
| 3 | Stacked PRs on GitHub | Unresolved | Review finding **B9** — the git standard has no model for stacked work, and the mockup mission was a 4-deep stack. Still open |
| 4 | "Send message" in Code sessions | **Shipped** — Claude Code v2.1.224 added `SendMessage` + `ListAgents`; sessions exchange *summaries* (not raw history) across terminals, projects and machines | **The single most consequential new fact for the orchard layer.** A hand-off channel, not shared memory |

**Terminology warning — "handoff" is ambiguous right now** and three unrelated
things carry the name: (a) `/rewind`'s learning-summary handoff message, (b) the
`SendMessage` cross-session channel, (c) Claude **Design** → Claude Code
prototype handoff (June 2026, irrelevant here). This document means **(b)**
throughout. Any later doc should say which.

---

## §3. The orchard layer (`qrchard` / `qrchardist`) — critical read

Owner's design, recorded verbatim in intent: each project runs its own `qops`;
a master `qrchardist` sits above the `qrchard` of projects with four
responsibilities — (1) launch new projects with their own qops, (2) distribute
resources against owner-defined priority, (3) maintain cross-project
communication and identify foundations to splinter off and share, (4) minor:
check each project's Notion second-brain status is current.

Five challenges to resolve **before** it is designed, not during:

- **a) Name the runtime first, or it is fiction.** Responsibilities 2 and 3 only
  have value *between* sessions. There is no persistent runtime. The PRD already
  hit this wall — finding **B12**, "Notion ≤24h unprompted has no mechanism that
  runs without a session," resolved by *demoting the requirement*. The
  qrchardist multiplies it across N projects. Three non-equivalent candidates:
  **Cowork scheduled task** (real clock, weak repo access), **GitHub Actions**
  (real clock, real repo, no judgement), **SendMessage/ListAgents** (real
  judgement, fires only when a session is already alive). Likely answer: a
  cron-triggered pass that writes into each project's `.qops/`, plus SendMessage
  for live cross-talk. **This is decision #1 of the orchard phase.**
- **b) It is a factory for 1.5 projects, and the foundation cannot be extracted
  yet.** quriculum does not exist. A shared "etsy pipeline" foundation cannot be
  derived from one instance without guessing at the seam — the same error class
  as GL-71 (no fix for an unmeasured cause) and GL-48 (a dry run on a different
  branch proves nothing). **Build quriculum by copy, instrument the divergences,
  extract on evidence.** v1 of the qrchardist *records* echo obligations; it
  does not satisfy them automatically.
- **c) Responsibility 1 is not orchestration.** "Launch a new project with its
  own qops" is a scaffold command — `qops init`. Cheapest of the four, needs no
  orchestrator, and is the portability proof (PRD Phase 7) under another name.
  Ship it first.
- **d) Responsibility 2 needs a measurement before a mechanism.** Cross-project
  token starvation is currently hypothetical (one active project), and nothing
  collects per-project consumption — cf. review finding **E3**, no
  instrumentation exists for S1/S2/S4/S9 either. The control surface is coarse:
  cron cadence, model choice, Opus 5 effort setting. That is a policy file plus
  config knobs, not a scheduler.
- **e) Responsibility 4 should be promoted, not treated as minor.** Notion
  freshness is a read + diff + write, already a scheduled-task shape, and the
  only one of the four whose runtime exists today.

---

## §4. Decisions taken 2026-08-13 (owner)

| # | Question | Decision |
|---|---|---|
| O1 | Orchard vs qops PRD structure | **One PRD.** qops v3 covers the per-project layer; the orchard ships as a named later phase (Phase 8+), with its runtime decision (§3a) taken up front but built after quriculum exists |
| O2 | Sequencing against E12 | **E12 first, then qops v3.** Secret scan runs alongside E12. E12 also serves as the clean "before" baseline for the acceptance sortie |
| O3 | Build vs adopt (Pocock et al.) | **Research-first, as v2 did.** Research all references and take what serves the goal; adoption depth is an *output* of that research, not a prior. Do not pre-commit to a level |

---

## §5. What the next planning session must do

Not "execute Phase 1". In order:

1. **Re-extract the corpus from the live board** (`docs/2026-07-22-go-live-plan-of-attack.md`,
   37 `GL-` rows + the E-series session logs), replacing `.qops/issues.md`
   wholesale. The old corpus becomes history, not input.
2. **Run the references research pass** per O3 — Pocock's skills,
   SendMessage/ListAgents, Opus 5 guidance, stacked-PR workflows — and let the
   findings set adoption depth per component.
3. **Re-run §2.3's payback computation** on post-Opus-5 economics and against the
   re-measured §1.1 state (both are stale).
4. **Carry forward the review findings that are still live** — at minimum B9
   (stacked work), B12 (no unprompted runtime), E3 (no instrumentation), C1
   (measured state drifts faster than the doc), and the Phase 0 outstanding items.
5. **Take the orchard runtime decision (§3a)** even though the build is deferred.

**Not in scope for that session:** anything touching activation or publishing —
standing owner decision 2026-08-12, recorded in `CLAUDE.md`.
