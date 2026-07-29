# PRD — Ways-of-working overhaul ("qops")

**Status:** DRAFT, awaiting owner sign-off. No implementation until approved.
**Date:** 2026-07-26
**Scope:** how work gets planned, executed, reviewed, tracked and remembered —
across Cowork, Claude Code, and scheduled runs. Not a change to the POD
pipeline itself.
**Decisions already taken by owner (2026-07-26), round 1:** GitHub Issues =
source of truth · unattended agents may branch+PR but never touch `master` ·
**no pay-as-you-go API spend — everything inside the subscription's 5h windows** ·
packaged as its own portable plugin repo from day one.

**Round 2 (§8 closed):** name = **`qops`** · **keep `master`**, plugin resolves
the default branch instead of hardcoding it · **reuse** the existing Telegram bot
here, but ship a per-project dev-bot setup guide · `gh` 2.96.0 authenticated as
`qvajda` (scopes: `gist, read:org, repo, workflow`) — sufficient, no change
needed · Cowork-hook uncertainty accepted **and downgraded to a 10-minute Phase 1
spike** · `codebase-memory-mcp` **deferred** · `pickup-loop` **off by default,
with machine-decided eligibility plus owner override** · Phase 4 branch deletion
keeps its own explicit "proceed" gate.

---

## 1. Problem

### 1.1 Measured state of `qhoto_printshop` (2026-07-26)

| Symptom | Measurement |
|---|---|
| Plan/doc sprawl | 50 files in `docs/`, **11,967 lines**; 37,337 lines counting `.superpowers/` |
| One mega-plan doc | `2026-07-22-go-live-plan-of-attack.md`, 431 lines, hand-maintained, tracks GL-1…GL-21 in a markdown table |
| Copy-paste ritual | 8 dated `*-kickoff-prompt.md` / `*-session-prompt.md` files, each with literal `[PASTE: …]` slots |
| Per-session fixed cost | root `CLAUDE.md` 174 lines / 11.6 KB **plus** global operating instructions — loaded in full, every session, forever |
| Git entropy | 24 local branches, of which **21 are already merged into `master`** and are pure noise (11 `fix/*` + 9 `worktree-agent-*` + master). Only 3 carry unmerged work. Plus 6 agent worktrees and 24 dirty/untracked paths including 13 uncommitted docs |
| Actual at-risk work | **Corrected 2026-07-26:** far smaller than first stated. Absent from `origin`: `feat/gl6-scene-library` (+12 commits), `proto/mockup-scene-prototype` (+2), and 1 unpushed commit on `feat/gl5-mockup-compositor`. Everything else is reachable via `master` on origin |
| No machine gate in front of the human | `scripts/mockup_qa.py` (6 defect detectors) was written *after* the owner manually rejected 3 of 4 scenes — twice |
| No CI | no `.github/` directory; 36 test files, 504 tests, run only when someone remembers |
| Issue tracker | none |
| Automated status | none — Notion is updated only when explicitly asked |

### 1.2 Root causes behind the thirteen stated frustrations

Five causes explain all thirteen:

1. **State lives in prose, in one place, maintained by a human.** A 431-line
   table can only be updated by re-reading it, so it only gets updated when
   asked, and its cost scales with the project's age.
2. **Context is re-derived, not resumed.** There is no machine-written record of
   "where we are", so every session — and every post-limit `continue` — pays to
   rebuild it from 12k lines of docs. This is the 10–20%-of-a-window tax.
3. **Verification is delegated to the owner.** Nothing blocks a request for
   review, so obviously-bad output reaches him. The 6 detectors that would have
   caught it exist, but as an artifact, not a gate.
4. **Nothing decays.** CLAUDE.md, docs, ADR-shaped one-line sign-offs and
   branches all accumulate. There is no size cap and no revisit date, so the
   system grows monotonically and old decisions harden into unchallengeable law.
5. **One planning granularity.** GSD gives one plan per task. A go-live effort
   with pre-foreseen forks (keyed generation → fallback to Dynamic Mockups;
   local host → cheap always-on host) has no place to record the fork, so the
   fork gets re-planned as a new doc each time it's reached.

### 1.3 The constraint that shapes everything

**Subscription-only.** Background agents compete for the same 5h budget as
interactive work. This inverts the usual design: **an LLM is the most expensive
component in the system, so the design must push work down to free layers**
(scripts, hooks, GitHub Actions, git itself) and spend tokens only on judgment.
Every mechanism below is scored on that.

---

## 2. Success criteria

Measurable, checked 3 weeks after go-live of the new system:

| # | Criterion | Target | Today |
|---|---|---|---|
| S1 | Tokens to resume after a session limit or a fresh session | ≤ 1 small read (~2k tokens) | 10–20% of a window |
| S2 | Manual copy-paste steps to move work between sessions | 0 | 8+ prompt docs |
| S3 | Status of every open item viewable without asking Claude | yes (issue list + digest) | no |
| S4 | Owner review requests that arrive with a failing/absent machine gate | 0 | the norm |
| S5 | Notion/status freshness | ≤ 24h, unprompted | days, prompted |
| S6 | Per-session fixed instruction cost | ≤ 150 lines total | 174 + global |
| S7 | Live branches not attached to an open issue | 0 | 23 of 24 |
| S8 | Documented decisions carrying a revisit date | 100% | 0% |
| S9 | Time from "next thing is decided" to "agent is working on it" | 1 command | write a kickoff doc, open a session, paste |
| S10 | System size (instruction lines + doc lines in the hot path) | flat or falling month-over-month | growing |

Non-goal: full autonomy. Owner stays the decision-maker on merges, external
writes, and forks. The goal is that he is *only* that.

---

## 3. Target architecture

Four layers. Cost per layer is the organising principle: **L0 is free, L1 is
nearly free, L2 costs tokens, L3 costs owner attention.** Work is pushed as far
down as it will go.

```
L3  OWNER            approvals · fork decisions · merges          (attention)
        ▲ escalation only when a machine gate has already passed
L2  AGENTS           planner(Opus) coder(Sonnet) reviewer(Sonnet)
                     scribe/triager/interactor(Haiku)             (tokens)
        ▲ reads a ~400-token brief, never the doc pile
L1  STATE            GitHub Issues · CONTEXT.md · docs/adr/ ·
                     .qops/state.json · .qops/resume.md           (~free)
        ▲ written by scripts and hooks, not by the model
L0  SUBSTRATE        git conventions · hooks · guardrails ·
                     GitHub Actions CI · machine gates            (free)
```

### 3.1 L0 — Deterministic substrate (zero token cost)

**Hooks** (`.claude/settings.json`, shipped by the plugin):

| Hook | Script | Effect |
|---|---|---|
| `SessionStart` | `qops brief` | Injects ≤400 tokens: active issue #, branch, last 3 commits, CI/gate status, pending approvals, next action. **Replaces the kickoff-prompt ritual and the re-read tax.** |
| `PostToolUse` (git commit, test run) | `qops ledger` | Appends one line to `.qops/ledger.jsonl`. Free, continuous. |
| `Stop` + `PreCompact` | `qops resume` | Regenerates `.qops/resume.md` from ledger + git + issue state. **Checkpointing stops depending on memory, and a mid-session cut-off loses at most one pass.** |
| `PreToolUse` | `qops guard` | Hard-blocks: commit/push to `master`, `push --force`, `reset --hard`, `worktree` sprawl, and the project's own tripwires (`create_draft_listing`, non-mocked Gelato create with a placeholder template ID, FLUX `[dev]`). |
| `SessionEnd` | `qops close` | Ensures the active issue has a comment with the pass result; queues the Notion mirror. |

**GitHub Actions CI** — free compute that does not touch the token budget, and
runs while the 5h window is resetting:

- `test.yml` — pytest (504), ruff, import guard (no `urllib` in `pipeline/`).
- `gate.yml` — runs the project's machine gates and uploads artifacts:
  `scripts/mockup_qa.py` (6 detectors + contact sheet), `scripts/gl19_m1_render.py`
  harness, `brief_lint`, spec-conformance checks.
- `guard.yml` — asserts hard constraints textually: no `create_draft_listing`
  call site, no `FLUX.1 [dev]`, no hardcoded `TELEGRAM_ADMIN_CHAT_ID`, no
  placeholder template ID reaching a live path.
- `digest.yml` (cron, **no LLM**) — renders open issues + CI status + pending
  approvals to markdown and pushes it to Telegram. This is the daily status
  update, at zero token cost.

**The gate rule (fixes frustration #5):** a PR cannot request owner review
unless `gate.yml` is green and its artifact (e.g. the contact sheet) is
attached. Enforced by branch protection + PR template. The reviewer agent's
instructions forbid escalating on prose; it must cite gate output.

### 3.2 L1 — State and memory

| Artifact | Owner | Contains | Replaces |
|---|---|---|---|
| **GitHub Issues** | agents + owner | one issue per open item (GL-x → #n). Labels: `type:research\|code\|manual\|test\|decision`, `state:triage\|planned\|building\|gate\|review\|blocked`, `mission:<epic>`. The **plan lives in the issue body**. | the 431-line plan table, the 8 kickoff docs |
| **`MISSION.md`** | generated | rendered view of the epic issues + their fork trees, for humans skimming the repo | narrative status sections |
| **`CONTEXT.md`** | planner, capped | the project's ubiquitous language: *group, primary group, bundle, matte, keyed generation, cover-crop, Mode I/O, sortie, gate*. ~80 lines. | agents re-deriving jargon; verbose prose |
| **`docs/adr/NNN-*.md`** | planner | one decision each: context, decision, consequences, `status: accepted\|superseded`, **`revisit-after: <date>`** | one-line sign-offs buried in chat that become permanent law |
| **`.qops/state.json`** | scripts | active issue, branch, phase, last gate result, next action | nothing (this is new) |
| **`.qops/resume.md`** | `qops resume` | ≤40 lines: what was being done, what passed, what's next, exact next command | "continue" + 20% of a window |
| **`.qops/ledger.jsonl`** | hooks | append-only event log | `.remember/` daily files |
| **`docs/archive/`** | migration | all 50 current docs, verbatim, out of the hot path | 12k lines of live docs |

**CLAUDE.md is capped at 150 lines** and holds only: hard constraints, pointers,
and the gate rule. Everything currently in it that is *data* (the Gelato/Etsy
static config table, prices, taxonomy IDs, shipping profiles) moves to
`docs/reference/static-config.md` + the existing `config/static_config.json`,
read on demand. Everything that is a *decision* becomes an ADR. This is a
recurring saving on every single session, forever.

**Anti-bloat rule (fixes frustration #12):** when a closed issue produces a
lesson, it may add **at most 3 lines** — and only to one of: a skill, a CI check,
CONTEXT.md, or an ADR. Never CLAUDE.md. If CLAUDE.md exceeds 150 lines the
weekly groom loop must remove something before adding. A monthly consolidation
pass (the existing `consolidate-memory` skill) merges duplicates and deletes
dead entries. **Net rule: the hot path must be flat or shrinking.**

**Anti-ossification rule (fixes frustration #9):** every ADR carries
`revisit-after`. The weekly groom loop surfaces expired ones with a single
question: *"still true?"* A quick sign-off therefore has a shelf life. Recurring
corrections, conversely, get written down once — as a check or a CONTEXT entry —
so they stop being repeated.

### 3.3 L2 — Agents with distinct responsibilities

Model tier is chosen by cost, not prestige. Under subscription-only this is the
main token lever.

| Agent | Model | Responsibility | Never does |
|---|---|---|---|
| **orchestrator** | Sonnet 5 | main thread. Reads the brief, routes to a subagent, reports. Keeps its own context tiny. | write code |
| **planner** | Opus 5 | grill → mission tree with **explicit pre-committed forks** → child issues with acceptance criteria and named gates. Writes ADRs and CONTEXT entries. | implement |
| **coder** | Sonnet 5 | one issue, one branch, red-green-refactor, runs the gate locally, opens the PR | merge, touch `master`, plan scope |
| **reviewer** | Sonnet 5 | adversarial review of the diff against the issue's acceptance criteria **and** the gate artifacts; must reproduce the gate, not trust the coder's prose | approve on narrative; escalate without a green gate |
| **scribe** | Haiku 4.5 | issue comments, state.json, resume.md, Notion mirror | judgement calls |
| **triager** | Haiku 4.5 | label hygiene, stale/blocked detection, expired-ADR detection | change plans |
| **interactor** | Haiku 4.5 | Telegram/Cowork digests and approval prompts; routes the answer back to the issue | decide |

Isolation matters as much as tiering: subagents keep the orchestrator's context
small, which is what keeps the *next* hour of the window usable.

### 3.4 L3 — Loops and two-tier planning (fixes frustration #6)

The GSD-doesn't-scale problem is a granularity problem. Two tiers:

- **Mission** = epic issue. Holds the **fork tree**: pre-committed branches with
  their trigger conditions. Written once by the planner; updated by *outcome*,
  not rewritten. Example, already latent in the current plan: `GL-6 keyed
  generation → if generation-acceptance fails twice → Dynamic Mockups escape
  hatch (Addendum §7)`. Today that fork lives in prose and is re-litigated each
  time it's approached; as a mission fork it is a recorded, pre-approved edge.
- **Sortie** = child issue. One GSD-sized plan, one branch, one PR, one gate,
  fits comfortably inside half a 5h window. GSD's discipline stays useful here.

**Named bounded loops** (loopy's contribution — each has an acceptance check, a
max pass count, and a stop-and-escalate condition):

| Loop | Trigger | Acceptance check | Max passes | On exhaustion |
|---|---|---|---|---|
| `gate-loop` | sortie in `state:building` | `gate.yml` green | 3 | comment, label `blocked`, escalate one question |
| `review-loop` | PR open, gate green | reviewer verdict + owner approval | 2 | escalate |
| `triage-loop` | daily (CI, no LLM) | every open issue has state + owner | 1 | digest lists exceptions |
| `groom-loop` | weekly | CLAUDE.md ≤150 lines, no expired ADRs, mission trees current | 1 | one question to owner |
| `pickup-loop` | scheduled | highest-priority `state:planned` issue moved to `building` with a branch | 1 | report "nothing ready" |

Note the deliberate mirror of the pipeline's own 3-attempt critic cap — same
shape, same reason.

### 3.5 Git standards (fixes frustration #11)

- **Branch name stays `master`.** No rename: the only argument for `main` is that
  tooling defaults to it, which is better solved by the plugin resolving the
  default branch (`gh repo view --json defaultBranchRef`) than by renaming. That
  resolution is required for portability anyway — other projects may differ.
  Renaming would cost a remote rename, re-pointing 24 branches and 6 worktrees,
  re-doing branch protection, and stale `master` references across 12k lines of
  docs, for zero functional gain.
- `master` protected: no direct pushes. **Enforced server-side by GitHub branch
  protection** — the authoritative control, unbypassable by any client — with the
  `PreToolUse` guard as a fast local convenience layer on top, not as the control
  itself.
- Branch name **must** carry the issue number: `<type>/<issue#>-<slug>`, e.g.
  `fix/47-matte-compositor`. This is what lets the scribe link commit → branch →
  PR → issue with zero LLM involvement.
- One issue → one branch → one PR → **squash merge** → branch deleted
  automatically.
- Worktrees only at `.qops/wt/<issue#>`, pruned by the daily loop. The 9
  `worktree-agent-*` branches are an artifact of the current sprawl and go away.
- Nothing uncommitted at session end: the `SessionEnd` hook fails loudly if the
  working tree is dirty outside `outputs/`.
- PR template: issue link, gate artifact, acceptance criteria checklist,
  constraint attestation (FLUX schnell, no Etsy create, no placeholder IDs).

### 3.6 Scheduled tasks (redesigned for subscription-only)

The current instinct — "use more scheduled tasks" — is right, but LLM-backed
schedules would eat the budget they're meant to protect. So:

| Job | Runs on | Cadence | Token cost |
|---|---|---|---|
| Status digest → Telegram | GitHub Actions, pure script | daily 07:00 | **zero** |
| Test + gate + guard on every push | GitHub Actions | on push/PR | **zero** |
| Worktree/branch pruning, stale detection | GitHub Actions | daily | **zero** |
| `groom-loop` (CLAUDE.md size, expired ADRs, mission-tree health) | Cowork scheduled task, Haiku | weekly Mon | small |
| `pickup-loop` (start the next `ready:auto` sortie, branch+PR only) | Cowork scheduled task | **off by default**, see below | medium |
| Tool-fit review (existing) | Cowork scheduled task | bi-weekly | small |

**Telegram (owner decision):** reuse the pipeline's existing bot + admin chat ID
for dev digests and approvals, distinguished by a `[qops]` message prefix and its
own inline-button callback namespace so a dev approval can never be mistaken for
a design approval. **But** the per-project dev bot is a real need, not a
maybe — so the plugin ships `docs/telegram-dev-bot-setup.md` (BotFather → token →
chat ID → `.env` keys → allowlist wiring) as a first-class deliverable in Phase 3,
and the portable config exposes `telegram.bot_token_env` /
`telegram.chat_id_env` so project #2 points at its own bot without code changes.
Reuse here is a convenience for one project, not the architecture.

#### `pickup-loop` eligibility (owner decision: off by default, system decides)

Default is **off**. An issue is picked up automatically only if it carries the
`ready:auto` label, which arrives one of two ways:

1. **Owner marks it** — "this one next". Always sufficient, no other test applied
   beyond the hard blocks below.
2. **The triager derives it** — applied only when *every* condition holds:
   - `state:planned`, with acceptance criteria present and a **named machine gate**;
   - the gate is **fully machine-checkable** — no criterion requiring owner taste
     (this alone excludes the entire GL-6 scene-authoring class of work);
   - no `fork` label — no decision point sits inside the sortie;
   - touches no path in `.qops/config.yml → sensitive_paths`
     (`publish_*.py`, `gelato_client.py`, `etsy_client.py`, `static_config.json`);
   - **no external write and no paid API call in scope** (a Replicate generation
     is real money — needs `budget:approved` from the owner);
   - blocked by nothing open;
   - planner-estimated at ≤½ a window.

Hard blocks that apply to both routes: branch + PR only, never a merge; **one
auto-sortie per night, maximum**; if `gate-loop` exhausts its 3 passes the loop
stops, labels `blocked`, and escalates rather than trying a fourth. Any issue
that fails derivation just stays `state:planned` — visible in the digest as
"planned, not auto-eligible", with the reason, so the owner can override.

This is deliberately conservative: the failure mode to avoid is an overnight run
consuming a window and producing something only the owner can judge.

### 3.7 Session-limit strategy (fixes frustration #7)

Five mechanisms, in order of impact:

1. **Resume is a read, not a reconstruction.** `.qops/resume.md` is always
   current because a hook writes it. Recovery after a limit = one small read.
2. **Sorties are window-sized.** The planner sizes a sortie at ≤½ window and
   states that in the issue. An interruption costs one pass, not a session.
3. **Fixed cost cut.** 150-line cap + data moved out of CLAUDE.md + a 400-token
   brief instead of a doc sweep.
4. **Cheap work is cheap.** Status, labels, mirrors and digests never touch
   Sonnet or Opus; most never touch an LLM at all.
5. **Spend the reset window on free compute.** CI runs the gates overnight; the
   morning brief reports results. The window is used for judgment, not waiting.

Expected effect on the felt problem: the pressure to "use the whole budget
before it resets" drops, because progress no longer requires the owner to be
present — and the cost of *not* being present is one CI run, not a re-derivation.

---

## 4. Frustration → mechanism map

| # | Frustration | Mechanism | Layer |
|---|---|---|---|
| 1 | Manual copy-paste between sessions | `SessionStart` brief + issue body as the plan; kickoff docs deleted | L0/L1 |
| 2 | Can't track full status; nothing updates unless asked | Issues + labels as SoT; scribe on `SessionEnd`; zero-token daily digest | L0/L1 |
| 3 | Wasting tokens re-writing plans | Two-tier plans; mission trees updated by outcome; plan = issue body, written once | L1/L3 |
| 4 | Notion checkpointing only when remembered | `Stop` hook writes resume.md; scribe mirrors to Notion; digest is scripted | L0 |
| 5 | Owner catches obviously bad output | **Gate rule**: no review request without a green machine gate + artifact | L0 |
| 6 | GSD doesn't scale to projects with foreseen forks | Mission (fork tree) / sortie (GSD-sized) split | L3 |
| 7 | 5h-window pressure and rough recovery | §3.7 — resume-as-read, window-sized sorties, free CI, cheap tiers | all |
| 8 | Underusing scheduled tasks | §3.6 — most schedules move to free CI; LLM schedules are small and armed | L0/L2 |
| 9 | Repeating myself / old sign-offs unchallengeable | Corrections become checks or CONTEXT entries (write once); ADRs carry `revisit-after` | L1 |
| 10 | Underusing skills / skill creation | Twice-repeated correction ⇒ skill or CI check, by rule; plugin is the home for them | L1/L2 |
| 11 | Git all over the place | §3.5 — issue-numbered branches, protected master, squash+delete, guard hook | L0 |
| 12 | System bloats instead of learning | 150-line cap, 3-line lesson budget, monthly consolidation, flat-or-shrinking rule | L1 |
| 13 | Rough recovery after "come back in 5h" | resume.md + brief; one pass lost, not a window | L0 |

---

## 5. What is borrowed from where

| Source | Taken | Rejected |
|---|---|---|
| **mattpocock/skills** | `CONTEXT.md` shared language (the single biggest token idea here); ADRs; `to-issues` vertical slicing; issue-tracker-agnostic setup step; git guardrail hooks; caveman (already in use) | its full skill set — too many entry points |
| **oh-my-claudecode** | model×agent tiering; distinct agent roles; bounded persistence loops; skill extraction from sessions | the framework itself (35k-star, tmux workers, multi-provider CLIs) — it is exactly the bloat being escaped, and its parallel workers assume budget headroom that subscription-only does not have |
| **SkillClaw** | "skills must be deduplicated and pruned, not just accumulated" → the consolidation pass and the 3-line budget | the proxy/evolve-server infrastructure — needs API-key routing, which the no-API-spend decision rules out |
| **GSD (installed)** | kept, at sortie level, where it works | as the top-level planner |
| **loopy / loop engineering** | loops need an acceptance check, a pass cap, and a stop-and-escalate; run receipts | the public catalog and publication flow |
| **mission-control** | agent-first task API; inbox/decisions queue; loop detection escalating after 3 failures; token-optimised context snapshot (~650 tokens) | the Next.js app + daemon — a second system to maintain, and its daemon burns subscription quota |
| **codebase-memory-mcp** | ADR persistence; the token argument for structural queries over file sweeps | installing it now — **deferred**, see §8. A 4k-line Python pipeline does not need a knowledge graph yet; revisit if the repo triples |
| **GitHub Issues** | the whole state layer | — |

---

## 6. Migration plan — no loss of progress

Phases 0–3 are **additive**: nothing existing is deleted or moved, so rollback
is `git checkout` of a tag. Only Phase 4 is destructive, and only after Phase 5
proves the system works.

### Phase 0 — Freeze and inventory (30 min, zero risk)
Runs in **Claude Code**, not Cowork — it needs authenticated `git push` and `gh`,
neither of which exist in the Cowork sandbox. Delivered as a script plus a
pre-drafted inventory, **not** as a prose kickoff prompt (a kickoff doc for
deterministic git work would be reproducing frustration #1).

- `scripts/qops_phase0.sh` — idempotent, read-mostly: tag `pre-qops-2026-07-26`
  at each branch tip, push the 3 branches carrying unmerged work to `origin`
  (`feat/gl6-scene-library`, `proto/mockup-scene-prototype`, the 1 unpushed commit
  on `feat/gl5-mockup-compositor`), then emit branch metadata.
- **One-time secret scan of git history.** The repo is **public** (anonymous
  `ls-remote` succeeds). `HEAD` is clean — only `.env.example` and a token-refresh
  *script* are tracked, no secrets — but Etsy OAuth, Gelato, Replicate and
  Telegram tokens have been handled throughout this project's life, so history
  gets scanned once (`gitleaks detect` or equivalent). **If anything is found,
  rotate the credential first and treat history rewriting as a separate decision.**
  This is unrelated to ways of working and is the highest-value thing in Phase 0.
- `docs/archive/2026-07-26-branch-inventory.md` — pre-drafted keep/merge/delete
  per branch, so the owner confirms a recommendation rather than deriving one.
- Snapshot `.remember/` and `.superpowers/sdd/`.
- **Gate:** owner confirms the inventory; secret-scan result reported either way.

### Phase 1 — Stand up L1 state (issues), keep old docs intact
- **Hook spike first (10 min, de-risks §3.1 before anything is built on it):**
  add a trivial `SessionStart` hook echoing a marker string, then open one Cowork
  session and one Claude Code session and check whether the marker appears.
  Outcome recorded in an ADR. If Cowork ignores project hooks, `/qops:brief` and
  `/qops:resume` ship as skills for Cowork while Claude Code keeps the automatic
  path — a known, bounded degradation rather than a late surprise.
- Create the plugin repo; scaffold `.qops/`, labels, milestones. Plugin resolves
  the default branch rather than assuming `main`.
- **Script-assisted conversion** of the 431-line plan table: each GL row → one
  issue. Fully-resolved rows (GL-1, 2, 4, 9, 14, 15, 16) → **closed** issues
  carrying their resolution text verbatim, so history is searchable rather than
  lost. Open rows (GL-3, 5, 6, 7, 8, 10, 11, 12, 13, 17, 18, 19, 20, 21) → open
  issues with type/state labels, acceptance criteria, and their gate named —
  note GL-5 (built, PR #2 open, merge-blocked) and GL-19 (ran, must re-run) stay
  **open**, since "done as scoped" is not done.
- Epic issues for the two live missions: **mockup track** (GL-21 → GL-6 a3 →
  GL-19 re-run → PR #2 merge, with the Dynamic-Mockups fork recorded) and
  **unattended operation** (GL-7 → GL-8 → soak).
- Plan doc gets a header: "superseded by issues; retained for history."
- **Gate:** owner spot-checks 5 issues against the plan doc for fidelity.

### Phase 2 — Distil CONTEXT.md + ADRs (one Opus session, the big one-time cost)
- `CONTEXT.md` from the existing vocabulary (~80 lines).
- ~15 ADRs extracted from CLAUDE.md's constraint list and the plan doc's decided
  rows — each with `revisit-after`. Candidates: variant listings (v4.11), Gelato
  pushes/we patch, FLUX schnell only, flat full-bleed artwork, discrete cron
  functions, 3-attempt critic cap, self-hosted OpenCV compositor, keyed
  generation, unframed poster line, `who_made: i_did`, per-group shipping
  profiles, local desktop host (preliminary — short revisit date).
- **Gate:** owner reads the ADR list; anything mis-stated is corrected here, and
  anything he wants re-opened gets a near-term `revisit-after`.

### Phase 3 — L0 substrate (still additive)
- Hooks + `qops` CLI (brief/ledger/resume/guard/close), wired per the Phase 1
  spike outcome.
- `.github/workflows/`: test, gate, guard, digest. **Prerequisite satisfied:**
  `gh` 2.96.0 authenticated as `qvajda`, scopes `repo` + `workflow` — exactly what
  issue CRUD and Actions dispatch need. And since the repo is **public**, GitHub
  Actions minutes are **unlimited and free** — the "push verification down to free
  compute" strategy in §3 is stronger than costed, not weaker.
- `docs/telegram-dev-bot-setup.md` (per-project dev bot), plus `telegram.*` keys
  in the portable config so project #2 uses its own bot.
- Slim CLAUDE.md to ≤150 lines; move the static-config table to
  `docs/reference/`. Old CLAUDE.md preserved in `docs/archive/`.
- Branch protection on `master`; PR template.
- **Gate:** a deliberate bad-input test — push a change that trips `mockup_qa`
  and confirm the PR cannot request review.

### Phase 4 — Git hygiene (first destructive step)
- Execute Phase 0's keep/merge/delete decisions: merge what's mergeable, tag
  and delete the rest, prune the 9 `worktree-agent-*` branches and the 6 agent
  worktrees.
- Commit or archive the 13 untracked docs; clean the working tree.
- Move all 50 `docs/*.md` to `docs/archive/` except SPEC_v4.11, the cost CSV,
  and reference material.
- **Explicitly irreversible:** branch deletion. Mitigated by Phase 0's tags and
  the push to origin. Requires a separate explicit "proceed".

### Phase 5 — Acceptance test on real work
Run the **next real sortie — GL-21 (matte compositor)** end to end under the new
system: brief → issue → branch → TDD → local gate → PR → CI gate → reviewer →
owner approval → squash merge → scribe closes the issue and mirrors to Notion.
Measure S1, S2, S4, S9. If the sortie is not measurably cheaper and calmer than
the GL-6-attempt-2 session was, the design is wrong and gets revised before
Phase 6.

### Phase 6 — Portability proof
Install the plugin into **myThirdWheel**. Everything project-specific must live
in one `.qops/config.yml` (issue repo, gate commands, constraint tripwires,
model tiers, review policy) — if anything else needs editing, the plugin isn't
portable and gets fixed. Then document the 10-minute onboarding for project #3.

**Estimated effort:** Phase 0 ≈ 0.5h · P1 ≈ 2h · P2 ≈ 2–3h (Opus) · P3 ≈ 3–4h ·
P4 ≈ 1h · P5 = the GL-21 sortie itself · P6 ≈ 1h. Roughly two working sessions
plus one real sortie. **P1–P3 are net token-positive within ~2 weeks** on the
CLAUDE.md/brief savings alone.

---

## 7. Proposed changes to standing instructions

Owner invited boundary changes. Six proposed; the compliance boundary is
untouched.

| # | Current | Proposed | Why |
|---|---|---|---|
| B1 | Full PRD if external system **or** >30 min | Full PRD at **mission** level only; sorties use a structured issue body (problem, acceptance criteria, gate, out-of-scope, fork) | Kills most plan re-writing (frustration #3) while keeping rigour where consequences are real |
| B2 | Show plan and wait for explicit "proceed" before hard-to-undo actions | Unchanged for external systems, money, comms, deletions. **Exempt** branch-scoped code changes — the branch *is* the reversibility | Removes per-edit friction; blast radius already bounded by the never-touch-master rule |
| B3 | "Checkpoint every 25–30 exchanges or on topic switch" | Delete. Replaced by the `Stop`/`PreCompact` hook | An instruction that depends on remembering is the frustration itself |
| B4 | — | **New:** never request owner review of generated output without a passing machine gate and its artifact attached | Frustration #5, directly |
| B5 | — | **New:** CLAUDE.md ≤150 lines. Overflow becomes a skill, an ADR, a CI check, or is deleted. Lessons cost ≤3 lines | Frustration #12 |
| B6 | — | **New:** documented decisions carry `revisit-after`; expired ones are surfaced weekly and may be challenged | Frustration #9 |
| — | One-way valve (no work-inbound data) | **Unchanged** | Compliance, not friction. `qops` must never be pointed at a work repo or work tracker |

---

## 8. Decisions — closed 2026-07-26

| # | Question | Resolution |
|---|---|---|
| 1 | Plugin name | **`qops`** |
| 2 | `master` → `main`? | **Keep `master`.** Plugin resolves the default branch instead of hardcoding — needed for portability anyway. Rename cost (remote rename, 24 branches, 6 worktrees, branch protection, stale doc refs) for zero functional gain. §3.5 |
| 3 | Telegram | **Reuse** the pipeline bot here, `[qops]`-prefixed with its own callback namespace. Per-project dev bot is a **standing requirement**: setup guide + `telegram.*` config keys ship in Phase 3. §3.6 |
| 4 | `gh` available? | **Yes** — 2.96.0, `qvajda`, scopes `gist, read:org, repo, workflow`. `repo` + `workflow` are exactly what's needed; no token change required |
| 5 | Cowork hook risk | **Accepted, and reduced.** Moved from a Phase 3 validation item to a **10-minute Phase 1 spike**. Scope of the risk: if Cowork ignores project hooks, Cowork sessions lose *automatic* brief/resume and gain two explicit commands instead — still far cheaper than today's doc sweep. Claude Code, where all coding happens, keeps the automatic path. **Safety does not depend on hooks**: `master` protection is server-side GitHub, unbypassable; the guard hook is convenience only |
| 6 | `codebase-memory-mcp` | **Deferred.** Revisit if the repo triples or a second service appears |
| 7 | `pickup-loop` default | **Off.** Two routes to `ready:auto`: owner marks it, or the triager derives it against 7 conservative conditions (machine-checkable gate, no fork, no sensitive path, no external write or paid API call, unblocked, ≤½ window). Hard caps: PR only, one auto-sortie per night, stop-and-escalate on gate exhaustion. §3.6 |
| 8 | Phase 4 gating | **Confirmed** — branch deletion requires its own explicit "proceed" |

No open questions remain. The document is ready for approve / revise.

---

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The overhaul itself becomes a bloat project and delays go-live | **high** — this is the main one | Phases 0–3 are ~2 sessions and strictly additive; Phase 5 *is* the next real sortie (GL-21), so the pipeline keeps moving. If P1–P3 slip past two sessions, stop and ship GL-21 the old way |
| Issue-based state becomes as stale as the plan doc | medium | Labels are changed by hooks and CI, not by memory; the daily digest lists every issue missing a state |
| A green gate ships a bad result (false confidence) | medium | The reviewer must reproduce the gate, not trust it; every owner rejection that a gate missed becomes a new detector (that's the learning loop's main input) |
| Hooks unavailable or flaky in Cowork | medium | **Retired early** by the Phase 1 spike. Worst case is bounded: Cowork loses automatic brief/resume (two explicit commands instead), Claude Code unaffected, and `master` protection is server-side so no safety property depends on hooks |
| GitHub outage blocks all work | low | `.qops/state.json` + `resume.md` are local; issues are recoverable from the archived plan doc |
| Subscription-only means the plugin's own agents still eat budget | medium | Most schedules carry zero token cost; `pickup-loop` is opt-in; tiering keeps mechanical work on Haiku |

---

## 10. What happens on approval

1. **Phase 0** — script + pre-drafted inventory + **secret scan of a public
   repo's history** → owner confirms. Runs in Claude Code (needs `gh` + push).
   Worth doing regardless of this PRD, mainly for the secret scan.
2. **Phase 1** — hook spike (10 min), then plugin scaffold + GL rows → issues →
   owner spot-checks 5 issues for fidelity.
3. **Phase 2** — CONTEXT.md + ~15 ADRs → owner reviews the ADR list.
4. **Phase 3** — hooks, `qops` CLI, CI workflows, slim CLAUDE.md, branch
   protection, Telegram dev-bot guide → bad-input test proves the gate blocks.
5. **Phase 4** — git hygiene. **Requested separately, flagged irreversible.**
6. **Phase 5** — GL-21 run end-to-end under the new system; measured against
   S1/S2/S4/S9. If it isn't measurably calmer than GL-6 attempt 2, revise before
   Phase 6.
7. **Phase 6** — install into myThirdWheel; anything needing an edit outside
   `.qops/config.yml` is a portability bug.

§8 is closed. Awaiting approve / revise on the design in §3 and the instruction
changes in §7. No implementation begins until then.
