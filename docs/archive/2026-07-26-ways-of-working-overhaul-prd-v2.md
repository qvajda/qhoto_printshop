# PRD v2 — Ways-of-working overhaul (`qops`)

**Status:** DRAFT, awaiting owner sign-off. No implementation beyond Phase 0
until approved.
**Date:** 2026-07-26
**Supersedes:** `docs/2026-07-26-ways-of-working-overhaul-prd.md` (v1), retained
for history.
**Written against:** `docs/2026-07-26-qops-prd-independent-review.md` — all 33
numbered findings (A1–A5, B1–B14, C1–C4, D1–D5, E1–E5). Coverage table in §11.

**Scope:** how work gets planned, executed, reviewed, tracked and remembered —
across Cowork, Claude Code, and scheduled runs. Not a change to the POD pipeline
itself.

**What changed most between v1 and v2, in one paragraph:** every number in §1.1
was re-measured rather than inherited; the gate rule no longer depends on a file
that does not exist; the phases are reordered so the hygiene rules are switched
on in a tree that can satisfy them; every automated loop is assigned to a runtime
that can actually perform its job; five success criteria that were unmeasurable
or unmeetable are restated; and the "net token-positive within ~2 weeks" claim is
computed for the first time — **and is wrong by roughly a factor of five**. §2.3
says so plainly, and §9 draws the consequence.

**Decisions carried forward from v1 (unchanged):** GitHub Issues = source of
truth · unattended agents may branch+PR but never touch `master` · no
pay-as-you-go API spend · packaged as its own portable plugin repo · name =
`qops` · keep `master` · `gh` 2.96.0 as `qvajda` is sufficient ·
`codebase-memory-mcp` deferred · `pickup-loop` off by default.

**New decisions taken this round (§10 has the full list):** repo **stays
public**, deliberately and for recorded reasons · CI gets its artwork from
**committed downscaled fixture masters** · a **separate dev Telegram bot** is
created before any CI touches Telegram · Phase "prove the gate" uses a gate that
**exists today**, not `mockup_qa.py`.

---

## 1. Problem

### 1.1 Measured state of `qhoto_printshop` — re-measured 2026-07-26

v1's table was inherited from an earlier session and had drifted. Every row below
was re-measured today, and each carries the command that produced it, so the
next reader can re-run rather than re-trust. **This is the baseline S10 and S7
are measured against, so it is now reproducible by construction.**

| Symptom | Measurement (2026-07-26) | Command |
|---|---|---|
| Plan/doc sprawl | **47** `.md` files in `docs/`, **12,957 lines** — of which 2 files / 990 lines are the qops PRD and its review (3 once this document lands), i.e. **45 files / 11,967 lines** of pre-existing docs | `ls docs/*.md \| wc -l` · `cat docs/*.md \| wc -l` |
| One mega-plan doc | `2026-07-22-go-live-plan-of-attack.md`, **431 lines**, hand-maintained, tracks GL-1…GL-21 in a markdown table | `wc -l` |
| Copy-paste ritual | 8 dated `*-kickoff-prompt.md` / `*-session-prompt.md` files with literal `[PASTE: …]` slots | `ls docs/ \| grep -E 'kickoff\|session-prompt'` |
| Per-session fixed cost | root `CLAUDE.md` **174 lines / 11,592 bytes ≈ 2,900 tokens**, plus global operating instructions — loaded in full, every session | `wc -lc CLAUDE.md` |
| Git entropy | **24 local branches** = 2 `feat/*` + 11 `fix/*` + 1 `proto/*` + 9 `worktree-agent-*` + `master`. **20 non-master branches are already merged** into `master`; **3 are not**. Plus **6 agent worktrees** and **30 dirty/untracked paths** (31 once this document lands), including **14 untracked docs** | `git branch`, `git branch --merged master`, `git worktree list`, `git status --porcelain` |
| Actual at-risk work | Absent from `origin`: `feat/gl6-scene-library` (+12 commits), `proto/mockup-scene-prototype` (+2), and 1 unpushed commit on `feat/gl5-mockup-compositor`. Everything else is reachable via `master` on origin | `git branch --no-merged master` |
| **No machine gate exists at all** | **`scripts/mockup_qa.py` does not exist.** `scripts/` contains `gl19_m1_render.py`, `gl6_author.py`, `qops_phase0.py`, `qops_phase1.py`. The 6 defect detectors are an **unbuilt deliverable of GL-21** | `ls scripts/` |
| No CI | no `.github/` directory; **34** test files, **501** test functions, run only when someone remembers | `ls tests/test_*.py \| wc -l` · `grep -rh '^def test_' tests/ \| wc -l` |
| Issue tracker | none | — |
| Automated status | none — Notion is updated only when explicitly asked | — |

**Corrections against v1, for the record (findings C1, C2, A1):** v1 said 50 docs
files / 11,967 lines (the line count was right for the pre-qops set, the file
count was not); 36 test files (34); 504 tests (501); "21 branches already merged"
(20 non-master, plus `master` itself, which is how the 21 arose); and — the
consequential one — that `mockup_qa.py` **had been written**. It had not.

### 1.2 Root causes behind the thirteen stated frustrations

Five causes explain all thirteen. **Root cause 3 is restated from v1**, because
v1's version was built on the `mockup_qa.py` error and pointed at the wrong fix.

1. **State lives in prose, in one place, maintained by a human.** A 431-line
   table can only be updated by re-reading it, so it only gets updated when
   asked, and its cost scales with the project's age.
2. **Context is re-derived, not resumed.** There is no machine-written record of
   "where we are", so every session — and every post-limit `continue` — pays to
   rebuild it from ~12k lines of docs. This is the 10–20%-of-a-window tax.
3. **Verification is specified but not built, and the owner is the fallback.**
   v1 said the detectors "exist, but as an artifact, not a gate". They do not
   exist. What actually happened: the need for six detectors was correctly
   identified *after* the owner had rejected 3 of 4 scenes twice, written into
   GL-21's scope, and then not built — because nothing in the system makes
   building a gate a precondition for requesting a review. **The fix is
   therefore not "wire up the existing gate" but "no review request without a
   gate, which makes building the gate the cheapest path."** Same mechanism, but
   it has to arrive *with* the work, not after it. This distinction is what
   §6's phase order now reflects.
4. **Nothing decays.** CLAUDE.md, docs, one-line sign-offs and branches all
   accumulate. There is no size cap and no revisit date, so the system grows
   monotonically and old decisions harden into unchallengeable law.
5. **One planning granularity.** GSD gives one plan per task. A go-live effort
   with pre-foreseen forks has no place to record the fork, so the fork gets
   re-planned as a new doc each time it is reached.

### 1.3 The constraint that shapes everything

**Subscription-only.** Background agents compete for the same 5h budget as
interactive work. This inverts the usual design: an LLM is the most expensive
component in the system, so the design pushes work down to free layers
(scripts, hooks, GitHub Actions, git itself) and spends tokens only on judgment.

**The free-compute claim, now qualified (finding B14).** The repo is public, and
the owner has decided in §10 that it stays public. Standard GitHub-hosted runner
minutes on **public** repositories remain free and unmetered — confirmed against
GitHub's own December-2025 pricing announcement, which reiterates it explicitly
while introducing charges elsewhere. So the "push verification down to free
compute" strategy holds **for this project specifically, because it is public**.
It does not transfer automatically to a private project #2 (2,000 min/month on
Free), and §7 Phase 7 now tests that assumption rather than inheriting it.

---

## 2. Success criteria

Measurable, checked 3 weeks after go-live of the new system. **Five of the ten
criteria in v1 were unmeasurable, unmeetable, or excluded the case that
motivated them; those are restated here with their definitions attached
(findings B1, B2, B3, B10, B12).** A criterion that cannot fail is not a
criterion.

| # | Criterion | Definition / how measured | Target | Today |
|---|---|---|---|---|
| S1 | Cost to resume after a session limit or fresh session | Tokens read before the first productive tool call. Captured by `qops metrics` from the ledger (§2.2) | ≤ 1 small read (~2k tokens) | 10–20% of a window |
| S2 | Manual copy-paste steps to move work between sessions | Count of new files matching `*kickoff*` / `*session-prompt*` created in the measurement window | 0 | 8+ prompt docs |
| S3 | Status of every open item viewable without asking Claude | GitHub issue list + daily digest, both exist and are current | yes | no |
| **S4** | **Owner review requests arriving without their *applicable* machine gate green** | See §2.1 — **taste reviews are in the denominator**; a taste review is legitimate only when every machine-checkable precondition is green and its artifact is attached | 0 | the norm |
| **S5** | **Status freshness in the canonical surface, unprompted** | GitHub issues + the `digest.yml` daily run. **Notion is demoted to an optional mirror** (§4.6) — it is no longer what S5 measures, because nothing unattended could write it | ≤ 24h | days, prompted |
| **S6** | **Always-loaded project instruction lines** | `CLAUDE.md` only. **CONTEXT.md is explicitly *not* always-loaded** (§4.2) — it is retrieved on demand by planner/coder sorties. Global operating instructions are out of scope: this PRD does not control them | ≤ 150 | 174 |
| **S7** | **Live non-master branches not attached to an open issue** | *Attached* = the branch name carries the issue number, **or** `.qops/config.yml → branch_aliases` maps it to one (§4.5, finding B10). Baseline reconciled to §1.1: 23 non-master branches, none attached | 0 | 23 of 23 |
| S8 | **Decisions** carrying a revisit date | ADRs only. **External constraint records are a separate class** (§4.2, finding B11) and carry `verified-on` / `verify-by` instead | 100% of ADRs | 0% |
| S9 | Time from "next thing is decided" to "agent is working on it" | Delta between an issue gaining `state:planned` and the first commit on its branch | 1 command | write a kickoff doc, open a session, paste |
| **S10** | **Hot-path size, month over month** | **"Hot path" is now defined** (§2.2): content entering a session's context *without being explicitly requested*. Everything else is cold storage and may grow freely | flat or falling | growing |

Non-goal: full autonomy. Owner stays the decision-maker on merges, external
writes, and forks. The goal is that he is *only* that.

### 2.1 Two gate classes — and why S4 now covers the review that motivated it

v1's S4 target of zero was quietly unachievable, because v1 §3.6 excluded "the
entire GL-6 scene-authoring class of work" from machine checking — and scene
review is precisely the review that produced frustration #5 (3 of 4 scenes
rejected, twice). As written, either the number excluded the case it existed
for, or scenes could never legitimately reach the owner (finding B2).

The fix is to stop treating "gated" as binary:

- **Machine gate** — fully automatable, binary, no taste. Example: the 6
  `mockup_qa` detectors (perspective error, edge bleed, occlusion, colour cast,
  aspect distortion, resolution floor). Runs in CI, produces an artifact.
- **Taste gate** — irreducibly the owner's judgment. Example: "is this scene
  attractive enough to sell from?"

**The rule (B4 in §8, unchanged in force, sharpened in wording):** a taste gate
may only be *requested* when every machine gate that applies to the same artifact
is green and its artifact is attached. So scene bundles reach the owner — but
only after the detectors pass, which is exactly the filter that would have
stopped both rejected rounds. S4 counts requests of both classes.

Consequence, carried into §4.6: **taste-gated work is never `ready:auto`.** That
was already true in v1 and is now derived from the class, not asserted per-issue.

### 2.2 Definitions that make S1/S2/S4/S9/S10 measurable (finding E3, B3)

v1 measured these in Phase 5 with nothing specified to capture them, which made
its own revise-or-proceed decision a judgement call — the thing the PRD exists to
replace. All four are cheap to instrument, none needs an LLM, and they become a
`qops metrics` subcommand built in Phase 4 (§7):

| Metric | Source | Extraction |
|---|---|---|
| S1 | `.qops/ledger.jsonl` | `session_start` events record brief size and whether any file >200 lines was read within the first 10 tool calls |
| S2 | git | `git log --diff-filter=A --name-only` filtered on the kickoff/session-prompt patterns |
| S4 | `gh` | PRs where `review_requested` precedes a successful `gate` check conclusion |
| S9 | issue timeline + git | timestamp of the `state:planned` label event vs. the first commit on the matching branch |

**"Hot path", defined (S10).** Content that enters a session's context *without
an explicit request*: `CLAUDE.md`, anything a hook injects (the `SessionStart`
brief), and any file a standing instruction requires reading. **Not** hot path:
ADRs, constraint records, issue bodies, `CONTEXT.md`, workflows, CLI source,
`docs/archive/`. These are cold storage, retrieved by name when needed, and are
*allowed and expected* to grow. S10 is measured by `qops metrics --hot-path`,
which sums the token count of the hot-path set and writes it to the ledger
monthly.

### 2.3 The payback claim, computed — and it does not survive (finding B5)

v1 asserted "P1–P3 are net token-positive within ~2 weeks" with no arithmetic,
and that claim was doing real work: it was the answer to §9's top risk, that the
overhaul becomes a bloat project. It should be the one number in the document
that is calculated. Here it is.

**Recurring saving, per working day:**

- CLAUDE.md slimming: 174 lines / 11,592 bytes ≈ **2,900 tokens** today. A
  150-line pointer-and-constraint file with the static-config data removed is
  ≈ 6 KB ≈ **1,500 tokens**. Saving ≈ **1,400 tokens per session**, ~2 sessions
  a day ≈ **2,800 tokens/day**.
- Resume-as-read: today a resume costs reading 2–5 docs — call it 400–1,200
  lines, **6k–18k tokens**, plus the reasoning to reconcile them. The brief is
  ~400 tokens. At ~1.5 resumes a day, saving ≈ **9k–26k tokens/day**.
- Total ≈ **12k–29k tokens/day**, call it **~15 minutes of window time per
  working day** reclaimed.

**One-time cost:** §7's phases sum to **≈ 10.75h of build** plus ≈1.75h of owner
time, of which ~2.5h is an Opus session.

**Payback: 12.5h ÷ 0.25h/day ≈ 50 working days ≈ 10 weeks** (≈8–9 weeks counting
build time only). Not two.

**What this means, stated plainly.** The token argument alone does not justify
this overhaul on a project that hopes to launch sooner than nine weeks out. The
overhaul has to be justified on the things that are not token savings — the gate
rule (frustration #5, the one that has already cost two rounds of rework), status
visibility without asking, and recovery that does not depend on remembering. If
those are not worth ~10 hours, the right answer is to build **only** the gate
rule and the brief, and drop the rest. §9's stop-rule is rewritten around this,
and §10 puts the reduced-scope option to the owner as a live alternative rather
than burying it in a risk row.

---

## 3. Target architecture

Four layers. Cost per layer is the organising principle: **L0 is free, L1 is
nearly free, L2 costs tokens, L3 costs owner attention.** Work is pushed as far
down as it will go.

```
L3  OWNER            approvals · fork decisions · merges          (attention)
        ▲ escalation only when the applicable machine gate is green
L2  AGENTS           planner(Opus) coder(Sonnet) reviewer(Sonnet)
                     scribe/triager/interactor(Haiku)             (tokens)
        ▲ reads a ~400-token brief, never the doc pile
L1  STATE            GitHub Issues · CONTEXT.md · docs/adr/ ·
                     docs/constraints/ · .qops/                   (~free)
        ▲ written by scripts and hooks, not by the model
L0  SUBSTRATE        git conventions · hooks · guardrails ·
                     GitHub Actions CI · machine gates            (free)
```

### 3.1 Runtime capability matrix — read this before assigning any job

v1 assigned `pickup-loop`, `groom-loop` and the `SessionEnd` scribe to Cowork
scheduled tasks, while simultaneously justifying Phase 0 running in Claude Code
on the grounds that authenticated `git push` and `gh` "**do not exist in the
Cowork sandbox**" (finding A3). Both cannot be true. This table is the single
source for what each runtime can do, and **every job in §4.6 now names its
runtime and is checked against it.**

| Runtime | Repo files | `git` local | `git push` / `gh` | LLM | Runs unattended | Costs subscription budget |
|---|---|---|---|---|---|---|
| **Claude Code** (desktop) | yes | yes | **yes** | yes | only if the desktop is awake | **yes** |
| **Cowork** | yes (mounted folder) | sandbox only, no credentials | **no** | yes | scheduled tasks | **yes** |
| **GitHub Actions** | yes (checkout) | yes | **yes** (`GITHUB_TOKEN`) | no | **yes** | **no** |

Three consequences, applied throughout:

1. **Anything that must push a branch or call `gh` runs in Actions or Claude
   Code — never Cowork.** `pickup-loop` therefore becomes a *scheduled Claude
   Code* job, not a Cowork task, and inherits the desktop-awake caveat.
2. **`groom-loop` needs no LLM at all.** Counting CLAUDE.md lines, scanning ADR
   front-matter for expired `revisit-after`, and checking mission-tree staleness
   are all deterministic. It moves to Actions, opens/updates a single recurring
   "weekly groom" issue, and only escalates the questions a human must answer.
   Token cost drops from "small" to **zero**.
3. **The scribe writes to an outbox, not to GitHub.** A session in *any* runtime
   appends its intended issue comments and state updates to
   `.qops/outbox.jsonl`. A drain step — the next Claude Code session's
   `SessionStart`, or an Actions cron — applies them. This makes the scribe
   host-agnostic and is what lets `SessionEnd` do useful work in Cowork at all.

### 3.2 L0 — Deterministic substrate (zero token cost)

**Hooks.** v1's table assigned three of five hooks jobs the hook system does not
provide as described (finding B6). Corrected:

| Hook | Matcher / semantics | Script | Effect |
|---|---|---|---|
| `SessionStart` | fires once per session | `qops brief` | Injects ≤400 tokens: active issue #, branch, last 3 commits, CI/gate status, pending approvals, next action — **and, first, any dirty-tree violation**, so the brief leads with the mess rather than papering over it. Also drains `.qops/outbox.jsonl` when credentials are present. Replaces the kickoff ritual and the re-read tax |
| `PostToolUse` | **matcher is `Bash`** (hooks match *tool names*, not semantic actions); the script parses the command string for `git commit` / `pytest` / gate invocations | `qops ledger` | Appends one line to `.qops/ledger.jsonl`. Free, continuous. Non-matching Bash calls are a no-op |
| `Stop` + `PreCompact` | **`Stop` fires per assistant turn, not per session** | `qops resume` | Regenerates `.qops/resume.md` from ledger + git + issue state. Per-turn is *better* than per-session and costs ~5ms; **v1's "checkpointing" framing implied session semantics the event does not have and is dropped.** A mid-session cut-off loses at most one turn |
| `PreToolUse` | matcher `Bash`, can **block** | `qops guard` | Hard-blocks: commit/push to `master`, `push --force`, `reset --hard`, worktree sprawl, and the project tripwires (`create_draft_listing`, non-mocked Gelato create with a placeholder template ID, FLUX `[dev]`) |
| `SessionEnd` | **fires after the session; cannot block anything** | `qops close` | Drains the outbox if credentials exist; writes the final ledger entry. **The "fail loudly if the tree is dirty" job is removed from here** — there is nobody left to read the failure. Dirty-tree enforcement moves to `Stop` (warns in-session, where it can be acted on) and `SessionStart` (leads with it) |

**GitHub Actions CI** — free on this public repo, and runs while the 5h window is
resetting:

- `test.yml` — pytest (501), ruff, import guard (no `urllib` in `pipeline/`).
- `gate.yml` — runs the project's machine gates and uploads artifacts. **See
  §3.3 for how it obtains artwork** — v1 specified a gate that could not execute.
- `guard.yml` — asserts hard constraints textually: no `create_draft_listing`
  call site, no `FLUX.1 [dev]`, no hardcoded `TELEGRAM_ADMIN_CHAT_ID`, no
  placeholder template ID reaching a live path.
- `digest.yml` (cron, **no LLM**) — renders open issues + CI status + pending
  approvals to markdown, posts to the **dev** Telegram bot (§4.6), and updates
  the pinned status issue. Daily status at zero token cost.
- `groom.yml` (cron weekly, **no LLM**) — the groom loop, per §3.1.

**The gate rule (fixes frustration #5):** a PR cannot request owner review unless
`gate.yml` is green and its artifact is attached. Enforced by branch protection +
PR template. The reviewer agent's instructions forbid escalating on prose; it
must cite gate output.

### 3.3 How `gate.yml` gets its artwork (finding A2 — a design decision v1 never took)

`scripts/gl19_m1_render.py` hard-codes `MASTER = ROOT / "db" / "base_artwork" /
"39.png"`, and `.gitignore:37` excludes `db/base_artwork/` wholesale — `git
ls-files db` returns exactly 1 file. On a clean CI checkout the harness fails on
its first render, and whatever `mockup_qa.py` becomes will hit the same wall.
The gate that catches the defects the owner has been catching by hand was the one
gate that could not run on the free compute the whole cost argument rests on.

**Decision: committed fixture masters.**

- A new tracked directory `tests/fixtures/masters/` holds **3 deliberately
  chosen, downscaled master images** (~1024px long edge, well under 1 MB each):
  one portrait, one landscape, one deliberately awkward (high-contrast edges, to
  exercise the edge-bleed and colour-cast detectors).
- `.gitignore` is narrowed so `db/base_artwork/` stays ignored but
  `tests/fixtures/` is tracked.
- `gl19_m1_render.py` and `mockup_qa.py` take the master path as an argument
  with the fixture as the CI default; full-resolution runs against real artwork
  stay local and are what the owner actually reviews.
- **Stated limitation:** a fixture gate proves the detectors work and catches
  regressions; it does not prove a given real bundle is good. That remains the
  local run plus the taste gate. This is the honest boundary of what free
  compute buys here, and §2.1's two-class model is what makes it coherent.
- The repo is public, so committing fixtures publishes them. That is accepted
  under §10's public-repo decision; the fixtures are chosen to be
  non-commercial and unremarkable.

### 3.4 Portability: how hooks and workflows ship (findings A4, A5)

v1's §3.1 heading — "Hooks (`.claude/settings.json`, shipped by the plugin)" —
named two different mechanisms at once, and v1's Phase 6 pass condition
(the portability proof, now **Phase 7**)
("everything project-specific must live in one `.qops/config.yml`; if anything
else needs editing, the plugin isn't portable") failed by construction, because
both `.claude/settings.json` and `.github/workflows/*.yml` must be present per
project and are inherently project-flavoured. Worse, **`.gitignore:42` ignores
`.claude/` wholesale**, so the hook config could not be committed at all — the
hook layer would have worked on one desktop and silently not existed for any
clone.

**Resolution — generated, not hand-maintained:**

1. **Narrow the gitignore.** `.claude/` → `.claude/settings.local.json` (which
   is the owner's personal permission allow-list and stays local) plus any cache
   paths. `.claude/settings.json` becomes trackable. This is a Phase 4 task and
   the hook spike's README already flags it.
2. **`qops install` renders both.** The plugin ships *templates*;
   `qops install` renders `.claude/settings.json` and the four workflow files
   from those templates plus `.qops/config.yml`. The rendered files are
   committed (so a clone works), but no human edits them.
3. **`qops doctor` detects drift** — if a rendered file differs from what the
   current template + config would produce, it says so.
4. **Phase 7's criterion is restated accordingly:** *no project-specific
   **content** may live outside `.qops/config.yml`; generated files are
   permitted provided `qops install` produces them and no hand-editing is
   required.* Falsifiable, and no longer guaranteed to fail.

The hook config itself is thin by design: every entry invokes `qops <verb>`, and
all project specifics (test command, gate command, tripwire strings, sensitive
paths, model tiers, Telegram env-var names) live in `.qops/config.yml`.

---

## 4. L1 — State and memory

| Artifact | Tracked? | Owner | Contains | Replaces |
|---|---|---|---|---|
| **GitHub Issues** | n/a | agents + owner | one issue per open item (GL-x → #n). The **plan lives in the issue body** | the 431-line plan table, the 8 kickoff docs |
| **`MISSION.md`** | tracked | generated | rendered view of the epic issues + fork trees | narrative status sections |
| **`CONTEXT.md`** | tracked | planner, capped ~80 lines | the project's ubiquitous language: *group, primary group, bundle, matte, keyed generation, cover-crop, Mode I/O, sortie, gate*. **On-demand, not always-loaded** (§4.2) | agents re-deriving jargon |
| **`docs/adr/NNN-*.md`** | tracked | planner | one **decision** each: context, decision, consequences, `status`, **`revisit-after`** | one-line sign-offs that become permanent law |
| **`docs/constraints/NNN-*.md`** | tracked | planner | one **externally-imposed constraint** each: what, source, `verified-on`, `verify-by`, how to re-verify | ADRs that ask "still true?" about things nobody decided |
| **`.qops/config.yml`** | **tracked** | owner + plugin | all project-specific configuration | scattered constants |
| **`.qops/issues.md`** | **tracked** | Phase 1 import | the import corpus, kept as history and as the GitHub-outage fallback | — |
| **`.qops/state.json`** | **ignored** | scripts | active issue, branch, phase, last gate result, next action | nothing (new) |
| **`.qops/resume.md`** | **ignored** | `qops resume` | ≤40 lines: what was being done, what passed, what's next, exact next command | "continue" + 20% of a window |
| **`.qops/ledger.jsonl`** | **ignored** | hooks | append-only event log; also the S1/S2/S9 instrument | `.remember/` daily files |
| **`.qops/outbox.jsonl`** | **ignored** | scribe | pending issue comments / state writes awaiting a credentialled drain | — |
| **`docs/archive/`** | tracked | migration | the current docs, verbatim, out of the hot path | 12k lines of live docs |

### 4.1 `.qops/` is split, not all-or-nothing (finding E1)

`.qops/` is currently untracked **and** un-gitignored — undecided by default, and
Phase 1 scaffolds it immediately. v1 never said which it should be, and the
review is right that both blanket answers break a stated rule: committed, the
per-turn `state.json`/`resume.md` churn dirties the tree on every turn and
collides with the dirty-tree rule; ignored, the whole thing is desktop-only,
which undercuts §9's outage mitigation and Phase 7's portability story.

**Split it.** Config and import corpus are tracked and travel; machine state is
ignored and stays local. Explicit `.gitignore` block, added in Phase 1:

```
.qops/state.json
.qops/resume.md
.qops/ledger.jsonl
.qops/outbox.jsonl
.qops/wt/
```

§9's outage row is corrected accordingly: `state.json`/`resume.md` are local to
**one machine**, so the real recovery path in a GitHub outage is `.qops/issues.md`
(tracked) plus the archived plan doc — not the ignored state files.

### 4.2 CLAUDE.md, CONTEXT.md and what "always loaded" means (finding B1)

v1's S6 said "per-session fixed instruction cost ≤150 lines **total**" while the
design deliberately added CONTEXT.md (~80 lines, "written explicitly so agents
read it every session") on top of a 150-line CLAUDE.md and unchanged global
instructions. 150 + 80 + global is comfortably over 150. The criterion was
unmeetable as worded.

**Two changes resolve it:**

1. **CONTEXT.md is retrieved, not injected.** The `SessionStart` brief *names*
   it; planner and coder sorties read it; a scribe or triager pass never does.
   Most sessions never load it. It is cold storage with a hot pointer.
2. **S6 is scoped to CLAUDE.md** and says so (§2). Global operating instructions
   are out of this PRD's control and are excluded explicitly rather than
   silently.

**CLAUDE.md is capped at 150 lines** and holds only hard constraints, pointers,
and the gate rule. Everything currently in it that is *data* (the Gelato/Etsy
static config table, prices, taxonomy IDs, shipping profiles) moves to
`docs/reference/static-config.md` + the existing `config/static_config.json`,
read on demand. Everything that is a *decision* becomes an ADR; everything that
is an *externally-imposed fact* becomes a constraint record (§4.3).

**Anti-bloat rule (fixes frustration #12):** a lesson from a closed issue may add
**at most 3 lines**, and only to a skill, a CI check, CONTEXT.md, or an ADR.
Never CLAUDE.md. If CLAUDE.md exceeds 150 lines the weekly groom must remove
something before adding. Monthly consolidation (the `consolidate-memory` skill)
merges duplicates. **Net rule: the hot path, as defined in §2.2, must be flat or
shrinking. Cold storage may grow.**

### 4.3 Decisions vs. constraints (finding B11)

S8's "100% of documented decisions carry `revisit-after`" misfires on things
nobody decided. Phase 2's ADR candidate list included: FLUX schnell (a **licence**
boundary), `who_made: i_did` (the Etsy API has no other value — verified live),
per-group shipping profiles (Etsy allows one profile per listing), the unframed
poster line. Asking "still true?" on these produces recurring noise with no
decision attached, which is exactly how a prompt gets trained into invisibility.

**Two record types:**

| | `docs/adr/` | `docs/constraints/` |
|---|---|---|
| Records | a choice we made between real alternatives | a limit imposed on us from outside |
| Front-matter | `status`, `revisit-after` | `source`, `verified-on`, `verify-by` |
| The weekly question | "**still true?**" — is this still the right choice? | *(none)* |
| The annual question | — | "**has the vendor changed?**" — often answerable by a script (an Etsy API probe, a licence-page diff) |
| Surfaced by | `groom.yml`, weekly | `groom.yml`, only when `verify-by` passes |

Reclassifying Phase 2's list: **ADRs** — variant listings (v4.11), Gelato
pushes/we patch, discrete cron functions, 3-attempt critic cap, self-hosted
OpenCV compositor, keyed generation, local desktop host (short revisit),
flat full-bleed artwork, taxonomy 1027 over 121, public repo (§10).
**Constraints** — FLUX schnell licence, `who_made: i_did`, one shipping profile
per listing, unframed poster line, Etsy's lack of an AI-disclosure field.

S8 is scoped to ADRs. Constraint coverage is tracked separately and is not a
success criterion.

### 4.4 L2 — Agents with distinct responsibilities

Model tier is chosen by cost, not prestige. Under subscription-only this is the
main token lever.

| Agent | Model | Runtime | Responsibility | Never does |
|---|---|---|---|---|
| **orchestrator** | Sonnet 5 | any | main thread. Reads the brief, routes to a subagent, reports. Keeps its own context tiny | write code |
| **planner** | Opus 5 | any | grill → mission tree with **explicit pre-committed forks** → child issues with acceptance criteria and a **named gate of a stated class** (§2.1). Writes ADRs and constraint records | implement |
| **coder** | Sonnet 5 | **Claude Code** | one issue, one branch, red-green-refactor, runs the gate locally, opens the PR | merge, touch `master`, plan scope |
| **reviewer** | Sonnet 5 | any | adversarial review of the diff against acceptance criteria **and** gate artifacts; must reproduce the gate | approve on narrative; escalate without a green machine gate |
| **scribe** | Haiku 4.5 | any (**via outbox**, §3.1) | issue comments, state.json, resume.md, optional Notion mirror | judgement calls |
| **triager** | Haiku 4.5 | Actions or Claude Code | label hygiene, stale/blocked detection, `ready:auto` derivation | change plans |
| **interactor** | Haiku 4.5 | any | Telegram/Cowork digests and approval prompts; routes the answer back to the issue | decide |

### 4.5 Git standards (fixes frustration #11)

- **Branch name stays `master`.** The plugin resolves the default branch
  (`gh repo view --json defaultBranchRef`) rather than hardcoding — required for
  portability anyway.
- **`master` protection, stated accurately (finding B8).** v1 called branch
  protection "the authoritative control, **unbypassable by any client**", and
  §8 decision 5 concluded from it that "safety does not depend on hooks". That
  is conditional, not absolute: **repository admins bypass branch protection
  unless "Do not allow bypassing the above settings" is explicitly enabled**, and
  the unattended agent authenticates with the same `gh` token as the owner, who
  is admin. GitHub cannot tell them apart. Two requirements make the claim true,
  and both are now explicit Phase 4 deliverables:
  1. **"Do not allow bypassing the above settings" is enabled** on the `master`
     rule. Without it the protection is decorative for this account.
  2. **Unattended agents get a separate identity** — a fine-grained PAT with
     `Contents: write` + `Pull requests: write` + `Issues: write` and **no admin**,
     stored as `QOPS_AGENT_TOKEN`. The owner's own token is never what an
     unattended run uses.
  With both: unbypassable *by the agent identity*. Without both: a local
  convenience. The PRD now says which.
- Branch name **must** carry the issue number: `<type>/<issue#>-<slug>`.
- **Grandfathering (finding B10).** The convention binds branches created after
  the Phase 1 import. `feat/gl5-mockup-compositor` — kept, under open PR #2, and
  the base for GL-21 — cannot be renamed without breaking that PR. It is
  *attached* instead, via `.qops/config.yml → branch_aliases`, which maps a
  legacy branch name to its issue number. S7 measures **attachment**, not naming
  (§2). The scribe reads the alias map, so the zero-LLM linking property holds.
- **Stacked sorties (finding B9).** v1's model — one issue → one branch → one PR
  → squash → delete — has no answer for dependent work, and the next mission is
  a 4-deep stack: GL-21 → GL-6 attempt 3 → GL-19 re-run → PR #2 merge, none of
  which targets `master`. Squash-merging a stack rewrites SHAs and produces
  duplicate-content conflicts down the chain. The rule becomes:
  - **A PR targeting the default branch is squash-merged**, then its branch is
    deleted. Unchanged.
  - **A PR targeting another feature branch is rebase-merged**, preserving the
    stack. Merge order is bottom-up.
  - The epic issue records the stack as an **ordered list**, and the triager
    blocks any sortie whose parent is unmerged.
  - After the stack's base lands on `master`, remaining branches are rebased
    once, by script, not by hand.
- Worktrees only at `.qops/wt/<issue#>`, pruned by the daily Actions job.
- **Dirty-tree rule, relocated (finding B6):** `Stop` warns in-session,
  `SessionStart` leads the brief with it. `SessionEnd` cannot enforce anything.
  The allowlist (`outputs/`, the ignored `.qops/` state files, `__pycache__`)
  lives in `.qops/config.yml`.
- PR template: issue link, gate artifact, gate class, acceptance criteria
  checklist, constraint attestation (FLUX schnell, no Etsy create, no
  placeholder IDs).

### 4.6 Scheduled work — every job checked against §3.1

| Job | **Runtime** | Cadence | Token cost | Changed from v1? |
|---|---|---|---|---|
| Status digest → dev Telegram + pinned issue | **Actions**, pure script | daily 07:00 | **zero** | Telegram bot changed (below) |
| Test + gate + guard on every push | **Actions** | on push/PR | **zero** | — |
| Worktree/branch pruning, stale detection | **Actions** | daily | **zero** | — |
| `triage-loop` | **Actions** | daily | **zero** | — |
| `groom-loop` (CLAUDE.md size, expired ADRs, due constraint re-verifications, mission-tree health) | **Actions** (was: Cowork + Haiku) | weekly Mon | **zero** (was: small) | **yes — needs no LLM, and Cowork cannot do the `gh` half anyway (A3)** |
| `pickup-loop` | **Claude Code, scheduled** (was: Cowork) | **off by default** | medium | **yes — branch+PR needs `git push` + `gh`, which Cowork does not have (A3)** |
| Optional Notion mirror | **Actions**, plain HTTPS to the Notion API with a scoped integration token | daily | **zero** | **yes — v1 had no unattended mechanism at all (B12)** |
| Tool-fit review (existing) | Cowork scheduled task | bi-weekly | small | — |

**S5 and Notion (finding B12).** v1's only Notion mirror was the scribe on
`SessionEnd`, and its schedule table contained no Notion job — so two days
without a session missed S5 *by design*, which is the same "only updates when I'm
there" failure S5 exists to fix. Resolution: **S5 no longer measures Notion.**
The canonical status surface is the GitHub issue list plus `digest.yml`, both of
which run without a session. Notion becomes an optional daily mirror written
directly from Actions via a **separate, scoped integration token** that grants
access to one dev-status page and nothing else. If the owner would rather not put
any Notion credential in CI, the mirror is simply not enabled and S5 is still met.

**Telegram — the production bot is no longer reused (finding B13).** v1 reused the
pipeline's live bot token and admin chat ID so `digest.yml` could post from
Actions. That would put the credentials of the bot that approves **real Etsy
publishes** into a public repository's Actions secrets, and give that bot a
CI-triggered write path. CLAUDE.md itself classes `TELEGRAM_ADMIN_CHAT_ID` as
credential-grade, and Phase 0's whole rationale is that a public repo makes
secret hygiene the highest-value item. The `[qops]` prefix and a separate
callback namespace separate the *messages*; they do not separate the *credential*.

**Decision: a dedicated dev bot is created in Phase 1**, before any CI touches
Telegram — BotFather → token → chat ID → `.env` keys → allowlist wiring, ~10
minutes. `QOPS_TELEGRAM_BOT_TOKEN` / `QOPS_TELEGRAM_CHAT_ID` are what Actions
holds; the production token never enters GitHub. This also promotes
`docs/telegram-dev-bot-setup.md` from "a guide we wrote" to "a procedure we ran",
which is what Phase 7 needs anyway.

### 4.7 Two-tier planning and named loops (fixes frustration #6)

- **Mission** = epic issue. Holds the **fork tree**: pre-committed branches with
  trigger conditions, updated by *outcome*, not rewritten. Example, already
  latent: `GL-6 keyed generation → if generation-acceptance fails twice →
  Dynamic Mockups escape hatch (Addendum §7)`.
- **Sortie** = child issue. One GSD-sized plan, one branch, one PR, one gate,
  fits inside half a 5h window. GSD's discipline stays useful here.

| Loop | Runtime | Trigger | Acceptance check | Max passes | On exhaustion |
|---|---|---|---|---|---|
| `gate-loop` | Claude Code | sortie in `state:building` | `gate.yml` green | 3 | comment, label `blocked`, escalate one question |
| `review-loop` | any | PR open, gate green | reviewer verdict + owner approval | 2 | escalate |
| `triage-loop` | Actions | daily | every open issue has `state:` + `type:` + an owner | 1 | digest lists exceptions |
| `groom-loop` | Actions | weekly | CLAUDE.md ≤150, no expired ADRs, no overdue constraint checks, mission trees current | 1 | one question to owner |
| `pickup-loop` | **Claude Code, scheduled** | off by default | highest-priority `ready:auto` issue moved to `building` with a branch | 1 | report "nothing ready" |

Deliberate mirror of the pipeline's own 3-attempt critic cap — same shape, same
reason.

**GSD's place, decided (finding E5).** GSD is kept at sortie level. Its
`.superpowers/sdd/` state (2.1 MB of brief/report/progress) is **subordinate**:
the issue body is authoritative, always. If they disagree, the issue wins. At
sortie close, `qops close` copies the GSD report into the issue as a comment and
the sortie's sdd directory is archived. Without this rule, GSD state is root
cause 1 re-created in a second location.

**`pickup-loop` eligibility.** Default **off**. `ready:auto` arrives two ways:

1. **Owner marks it** — always sufficient, subject only to the hard blocks.
2. **The triager derives it** — only when *every* condition holds:
   - `state:planned`, acceptance criteria present, and a named gate;
   - **the gate's class is `machine`** (§2.1) — no taste component. This is the
     condition that excludes the GL-6 scene-authoring class, and it is now
     derived from the gate class rather than asserted case by case;
   - no `fork` label;
   - touches no path in `.qops/config.yml → sensitive_paths`
     (`publish_*.py`, `gelato_client.py`, `etsy_client.py`, `static_config.json`);
   - no external write and no paid API call in scope (a Replicate generation is
     real money — needs `budget:approved`);
   - blocked by nothing open, and **no unmerged parent in a stack** (§4.5);
   - planner-estimated at ≤½ a window;
   - **no `no-auto` label** (below).

Hard blocks on both routes: branch + PR only, never a merge; **one auto-sortie
per night, maximum**; on `gate-loop` exhaustion, stop, label `blocked`, escalate.
Any issue that fails derivation stays `state:planned` and appears in the digest
as "planned, not auto-eligible", with the reason.

**`no-auto`, new (findings D1, D2).** An explicit label meaning "never
auto-eligible regardless of derivation". Applied at import to **GL-21**, because
GL-21 is the Phase 6 acceptance sortie the owner runs end-to-end to measure
S1/S2/S4/S9 — if `pickup-loop` ever fires on it, the measurement is gone.

### 4.8 Session-limit strategy (fixes frustration #7)

1. **Resume is a read, not a reconstruction.** `.qops/resume.md` is current
   because a hook writes it every turn. Recovery = one small read.
2. **Sorties are window-sized.** The planner sizes at ≤½ window and states it.
3. **Fixed cost cut.** 150-line cap, data moved out, CONTEXT.md on demand, a
   400-token brief instead of a doc sweep.
4. **Cheap work is cheap.** Status, labels, mirrors, digests and the entire
   groom loop never touch an LLM.
5. **Spend the reset window on free compute.** CI runs the gates overnight; the
   morning brief reports results.

---

## 5. Frustration → mechanism map

| # | Frustration | Mechanism | Layer |
|---|---|---|---|
| 1 | Manual copy-paste between sessions | `SessionStart` brief + issue body as the plan; kickoff docs deleted | L0/L1 |
| 2 | Can't track full status; nothing updates unless asked | Issues + labels as SoT; scribe via outbox; zero-token daily digest | L0/L1 |
| 3 | Wasting tokens re-writing plans | Two-tier plans; mission trees updated by outcome; plan = issue body | L1/L3 |
| 4 | Notion checkpointing only when remembered | `Stop` hook writes resume.md; digest and optional Notion mirror both run from Actions, session or no session | L0 |
| 5 | Owner catches obviously bad output | **Gate rule** + the two-class model (§2.1): no review request, taste included, without its machine gate green | L0 |
| 6 | GSD doesn't scale to projects with foreseen forks | Mission (fork tree) / sortie split; GSD subordinate to the issue | L3 |
| 7 | 5h-window pressure and rough recovery | §4.8 | all |
| 8 | Underusing scheduled tasks | §4.6 — most schedules are free CI; only `pickup-loop` costs tokens, and it is off | L0/L2 |
| 9 | Repeating myself / old sign-offs unchallengeable | Corrections become checks or CONTEXT entries; ADRs carry `revisit-after`; constraints tracked separately so the prompt stays meaningful | L1 |
| 10 | Underusing skills / skill creation | Twice-repeated correction ⇒ skill or CI check, by rule | L1/L2 |
| 11 | Git all over the place | §4.5 — issue-attached branches, real protection, squash-on-master / rebase-in-stack, guard hook | L0 |
| 12 | System bloats instead of learning | 150-line cap, 3-line lesson budget, defined hot path, monthly consolidation | L1 |
| 13 | Rough recovery after "come back in 5h" | resume.md + brief; one turn lost, not a window | L0 |

---

## 6. What is borrowed from where

Unchanged from v1 except where noted.

| Source | Taken | Rejected |
|---|---|---|
| **mattpocock/skills** | `CONTEXT.md` shared language; ADRs; `to-issues` vertical slicing; issue-tracker-agnostic setup; git guardrail hooks | its full skill set — too many entry points |
| **oh-my-claudecode** | model×agent tiering; distinct agent roles; bounded persistence loops; skill extraction | the framework itself — the bloat being escaped; its parallel workers assume budget headroom |
| **SkillClaw** | skills must be pruned, not accumulated → the consolidation pass and the 3-line budget | the proxy/evolve-server infrastructure — needs API-key routing |
| **GSD (installed)** | kept at sortie level, **explicitly subordinate to the issue** (§4.7) | as the top-level planner |
| **loopy** | loops need an acceptance check, a pass cap, a stop-and-escalate; run receipts | the public catalog and publication flow |
| **mission-control** | agent-first task API; inbox/decisions queue; loop detection escalating after 3 failures | the Next.js app + daemon — a second system, and its daemon burns quota |
| **codebase-memory-mcp** | ADR persistence; the token argument for structural queries | installing it now — deferred; revisit if the repo triples |
| **GitHub Issues** | the whole state layer | — |

---

## 7. Migration plan — reordered

**The v1 order was wrong (finding B7).** v1 switched on the guard hook, branch
protection and the "nothing uncommitted at session end" rule in Phase 3, and
then cleaned the 30 dirty paths, 20 stale branches and 6 worktrees in Phase 4 —
*after*. Every session in between would have tripped the dirty-tree check on
`outputs/gl19_m1/_dbg_*.png`, `assets/brand/`, 15 untracked docs and `.qops/`
itself. You cannot enable a cleanliness rule in a dirty tree.

**Git hygiene therefore moves before the substrate.** It keeps its own explicit
"proceed" gate (§8 decision 8, honoured — the gate moves with the phase, it is
not weakened), and Phase 0's tags plus the push to origin remain the safety net.
Numbering shifts by one from Phase 3 onward.

### Phase 0 — Freeze and inventory — **partially executed; two items outstanding**

Runs in **Claude Code** (needs authenticated `git push` and `gh`).

Done: `scripts/qops_phase0.py` (**note: `.py`, not the `.sh` v1 specified** —
deliberate, for Windows/git-bash portability; finding C4, and the script was
right, the PRD was wrong), tags at each branch tip, the 3 unmerged branches
pushed to origin, `docs/archive/2026-07-26-branch-inventory.md`.

> **✅ PHASE 0 IS COMPLETE AS OF 2026-08-13. Both outstanding items below are
> closed and neither is to be re-run.** The secret scan ran as **E13a** —
> result CLEAN, nothing rotated, no history rewritten, and the history-rewrite
> question is now a closed standing owner decision
> (`docs/2026-08-13-e13a-findings.md`, `CLAUDE.md`). The snapshot ran as **E13
> §7b** — `docs/archive/2026-08-13-remember-sdd-snapshot-manifest.md`. The two
> bullets are kept below as the record of what was owed, not as a to-do list.

**Outstanding (finding C3) — Phase 0 is not complete, and Phase 3 assumes it is:**

- **Snapshot `.remember/` (24 entries) and `.superpowers/sdd/` (2.1 MB).**
  `grep` for `remember|superpowers|snapshot|archive` in `qops_phase0.py` returns
  nothing; `docs/archive/` holds exactly one file. Phase 3 archives and deletes
  on the assumption this snapshot exists. **Must be done before Phase 3.**
- **One-time secret scan of git history.** The repo is public. `HEAD` is clean —
  only `.env.example` and a token-refresh *script* are tracked — but Etsy OAuth,
  Gelato, Replicate and Telegram tokens have been handled throughout this
  project's life. `gitleaks detect` or equivalent, once. **If anything is found,
  rotate the credential first**; history rewriting is a separate decision. This
  remains the highest-value item in the whole plan and is worth doing whether or
  not this PRD is approved.
- **Gate:** owner confirms the inventory; secret-scan result reported either way.

### Phase 1 — L1 state: issues, spike, dev bot

- **Hook spike, widened (finding B6).** v1's spike answered only *"do hooks fire
  in Cowork?"*. §3.2 depends on five hooks doing five specific jobs, so the spike
  answers a matrix instead — still ~20 minutes:
  | Question | Why it matters |
  |---|---|
  | Does each of `SessionStart` / `Stop` / `PreCompact` / `PreToolUse` / `SessionEnd` fire, in Cowork and in Claude Code? | the brief, resume, guard and close all assume it |
  | Can `PreToolUse` actually **block** a Bash call? | the entire guard layer |
  | What payload does `PostToolUse` receive for a Bash call — is the command string available? | the ledger has to parse it |
  | Does `Stop` fire per turn as documented? | resume.md's freshness claim |
  Outcome recorded as an ADR. If Cowork ignores project hooks, `/qops:brief` and
  `/qops:resume` ship as Cowork skills while Claude Code keeps the automatic
  path — a bounded, known degradation.
- **Create the dev Telegram bot** (§4.6) — before any CI exists to misuse the
  production one.
- Create the plugin repo; scaffold `.qops/` **with the tracked/ignored split of
  §4.1 applied at creation**; create labels and milestones from the canonical
  taxonomy (§7.1). Plugin resolves the default branch.
- **Script-assisted conversion** of the 431-line plan table. Fully-resolved rows
  (GL-1, 2, 4, 9, 14, 15, 16) → **closed** issues carrying their resolution text
  verbatim. Open rows → open issues with type/state labels, acceptance criteria,
  and their gate **named and classed** — where no gate exists yet, `gate: none —
  defined in <issue>`, which is legal at import and is a `ready:auto` blocker
  until filled (finding B7's second half; v1 required a named gate before any
  gate existed).
- **`--validate` must pass before `--execute` (finding D3).** The importer gains
  a validator that fails if any open issue lacks `state:` or `type:`, or carries
  `ready:auto`. Today 10 open issues (GL-6, 7, 8, 10, 11, 12, 17, 18, 20, 21)
  have no `state:` label, which would fail `triage-loop` on day one.
- **Strip `ready:auto` from the import corpus entirely (findings D1, D2).**
  `.qops/issues.md` currently pre-labels GL-8, GL-20 and GL-21 `ready:auto`,
  short-circuiting both routes in §4.7 — neither the triager nor its conditions
  exist until Phase 4. No issue carries `ready:auto` at import. **GL-21 gets
  `no-auto`** permanently.
- **Split GL-21 (finding D2).** As scoped it is three compositor changes (C1–C3)
  **plus** six defect detectors **plus** a contact-sheet generator **plus** tests
  — the largest sortie in the corpus, and self-evidently over the ≤½-window bar
  it would need to clear. Split:
  - **GL-21a** — compositor changes C1–C3 + tests. The Phase 6 acceptance sortie.
  - **GL-21b** — `scripts/mockup_qa.py`: the 6 detectors + contact sheet + tests.
    Independently useful, and the thing that finally makes the gate rule real.
- Epic issues for the live missions, and their stacks recorded as ordered lists
  (§4.5): **mockups** (GL-21a → GL-21b → GL-6 a3 → GL-19 re-run → PR #2 merge,
  with the Dynamic-Mockups fork recorded) and **unattended operation**
  (GL-7 → GL-8 → soak).
- **Net-new objects, listed here for explicit approval (finding D4).** The Phase
  1 artefacts already contain 8 objects with no counterpart in the plan doc,
  which a gate worded "spot-check for **fidelity**" cannot catch:
  `EPIC-launch` (GL-10 storefront + GL-11 Etsy Developer Mode + GL-12 Google
  Trends, all owner-driven and external-account-touching), and `BL-1`…`BL-7`
  (post-launch backlog, all `state:triage`). Both additions look right; they are
  put here to be approved rather than smuggled through a fidelity check.
- Plan doc gets a header: "superseded by issues; retained for history."
- **Gate:** `--validate` green, **and** owner spot-checks 5 GL issues for
  fidelity, **and** owner signs off the 8 net-new objects above.

### Phase 2 — Distil CONTEXT.md, ADRs and constraint records (one Opus session)

- `CONTEXT.md` from the existing vocabulary (~80 lines), written to be read on
  demand rather than injected (§4.2).
- **~10 ADRs** (revisitable decisions) and **~5 constraint records**
  (externally imposed), split per §4.3 — v1's undifferentiated list of ~15 was
  what made S8 misfire.
- **Gate:** owner reads both lists; anything mis-stated is corrected here;
  anything he wants re-opened gets a near-term `revisit-after`.

### Phase 3 — Git hygiene *(was Phase 4; moved before the substrate — first destructive step)*

- **Prerequisite: Phase 0's outstanding snapshot is done. ✅ AMENDED 2026-08-13
  (E13 §7b) — this now resolves to an artefact, not to a memory:
  `docs/archive/2026-08-13-remember-sdd-snapshot-manifest.md`.** 216 files
  archived out-of-repo (reading (i)), counts verified in and out, `sha256`
  recorded, `.remember/tmp/` excluded, the 89 `.diff` files kept on a measurement
  (excluding them bought 258 KB). **One condition before this phase may delete
  either tree:** the manifest's Custodian row must name where the archive was
  saved. Until it does, the only copy is in a session outputs folder.
- Execute Phase 0's keep/merge/delete decisions: merge what is mergeable, tag and
  delete the rest, prune the 9 `worktree-agent-*` branches and the 6 worktrees.
- Commit or archive the 15 untracked docs; clean the working tree.
- Move the pre-existing `docs/*.md` to `docs/archive/` except SPEC_v4.11, the
  cost CSV, and reference material.
- Apply the `.gitignore` changes: `.qops/` split (§4.1), `.claude/` narrowing
  (§3.4), `tests/fixtures/` un-ignored (§3.3).
- **Explicitly irreversible:** branch deletion. Mitigated by Phase 0's tags and
  the push to origin. **Requires a separate explicit "proceed"** — §8 decision 8,
  unchanged, moved with the phase.

### Phase 4 — L0 substrate *(was Phase 3)*

- Hooks + `qops` CLI (`brief` / `ledger` / `resume` / `guard` / `close` /
  `install` / `doctor` / `metrics`), wired per the Phase 1 spike outcome.
- `.github/workflows/`: test, gate, guard, digest, groom — **rendered by
  `qops install`** from templates + `.qops/config.yml` (§3.4).
- **`tests/fixtures/masters/`** — the 3 fixture masters (§3.3), and
  `gl19_m1_render.py` parameterised to accept a master path.
- **`qops metrics`** — the S1/S2/S4/S9/S10 instrument (§2.2). Without it Phase 6
  cannot measure what it exists to measure.
- Branch protection on `master`, **with "do not allow bypassing" enabled**, and
  the separate `QOPS_AGENT_TOKEN` identity provisioned (§4.5, finding B8).
- `docs/telegram-dev-bot-setup.md`, written from the Phase 1 run-through.
- Slim CLAUDE.md to ≤150 lines; static-config table to `docs/reference/`. Old
  CLAUDE.md preserved in `docs/archive/`.
- **Gate — the circularity is broken (finding A1).** v1's exit test was "push a
  change that trips `mockup_qa` and confirm the PR cannot request review", but
  `mockup_qa.py` is GL-21b, which lands in Phase 6. Phase 4 instead proves the
  **mechanism** with gates that exist today:
  1. plant a `FLUX.1 [dev]` string on a branch → `guard.yml` red → PR cannot
     request review;
  2. break one test deliberately → `test.yml` red → same;
  3. confirm a green run *does* permit the request.
  `mockup_qa.py` then plugs into the proven slot when GL-21b ships. The mechanism
  is validated in Phase 4; the specific detector is validated in Phase 6.

### Phase 5 — qops tracks itself (finding E2)

From here on, **qops's own work lives as issues in the qops plugin repo**, not in
`qhoto_printshop` and not in a doc. `qhoto_printshop` issues track pipeline work
only. This is a one-line policy and a free dogfood test: if the system is
unpleasant to use on its own remaining work, that is worth knowing before Phase 7
rather than after.

### Phase 6 — Acceptance test on real work *(was Phase 5)*

Run **GL-21a (matte compositor)** end to end under the new system: brief → issue
→ branch → TDD → local gate → PR → CI gate → reviewer → owner approval → squash
merge → scribe closes the issue. **Measured by `qops metrics`, not by
impression:** S1, S2, S4, S9. If the sortie is not measurably cheaper and calmer
than the GL-6-attempt-2 session, the design is wrong and gets revised before
Phase 7. GL-21b follows and makes the mockup gate real.

### Phase 7 — Portability proof *(was Phase 6)*

Install the plugin into **myThirdWheel**. Pass condition, restated per §3.4: **no
project-specific content outside `.qops/config.yml`; generated files
(`.claude/settings.json`, `.github/workflows/*`) are permitted provided
`qops install` produces them and nothing needs hand-editing.** Also the first
real test of §1.3's caveat — myThirdWheel may be private, where Actions minutes
are capped at 2,000/month, so the free-compute assumption gets re-measured rather
than inherited. Then document the 10-minute onboarding for project #3.

### Effort — recomputed (finding B4)

v1 summed to ≈10.5h and called it "roughly two working sessions", with no
allowance for the owner sign-off gates, reading time, or the Opus session's own
review — while §9's stop-rule was "if P1–P3 slip past two sessions, stop". The
plan's own optimistic estimate triggered its own stop-rule.

| Phase | Build | Owner |
|---|---|---|
| 0 (finish) | 0.5h | 0.25h |
| 1 | 2h | 0.5h |
| 2 | 2.5h (Opus) | 0.5h |
| 3 git hygiene | 1h | 0.25h |
| 4 substrate | 3.5h | 0.25h |
| 5 self-tracking | 0.25h | — |
| 7 portability | 1h | — |
| **Total** | **≈10.75h** | **≈1.75h** |

Phase 6 is the GL-21a sortie itself and is not overhead. **Realistically three to
four 5h windows**, not two — build time is not the only thing consuming a window.
§9's stop-rule is rewritten against this number rather than against a wish.

---

### 7.1 Canonical label taxonomy (finding D5)

The label set is the state layer's schema and belongs in the document being
signed off, not discovered in the importer. `qops_phase1.py` currently defines
both `type:epic` and a bare `epic` and applies both, plus `type:impl-research`,
`go-live-blocker` and `mission:launch-prep`, none of which appear in v1's §3.4.
Canonical set, to be read by the importer from `.qops/config.yml`:

| Namespace | Values |
|---|---|
| `type:` | `epic` · `research` · `code` · `manual` · `test` · `decision` |
| `state:` | `triage` · `planned` · `building` · `gate` · `review` · `blocked` · `done` |
| `mission:` | `mockups` · `automation` · `launch-prep` |
| `gate:` | `machine` · `taste` · `none` |
| flags | `ready:auto` · `no-auto` · `fork` · `budget:approved` · `go-live-blocker` |

Removed: bare `epic` (use `type:epic`), `type:impl-research` (→ `type:research`).
Every open issue must carry exactly one `type:`, one `state:` and one `gate:`;
the `--validate` step enforces it.

---

## 8. Proposed changes to standing instructions

| # | Current | Proposed | Why |
|---|---|---|---|
| B1 | Full PRD if external system **or** >30 min | Full PRD at **mission** level only; sorties use a structured issue body (problem, acceptance criteria, gate + class, out-of-scope, fork) | Kills most plan re-writing (frustration #3) while keeping rigour where consequences are real |
| B2 | Show plan and wait for explicit "proceed" before hard-to-undo actions | Unchanged for external systems, money, comms, deletions. **Exempt** branch-scoped code changes — the branch *is* the reversibility | Removes per-edit friction; blast radius bounded by the never-touch-master rule |
| **B3** | "Checkpoint every 25–30 exchanges or on topic switch" | **Deferred, not approved now (finding E4).** v1 deleted this on the strength of a spike that has not run. If the spike returns "Cowork ignores project hooks" — the outcome its own README calls *expected* — B3 removes Cowork's only checkpoint mechanism and replaces it with a command someone must remember to type, which is verbatim the failure mode B3's justification cites. **B3 is re-proposed after Phase 1's spike, per host:** dropped where the hooks demonstrably fire, retained where they do not | An instruction should not be deleted before the evidence that replaces it exists |
| B4 | — | **New:** never request owner review of generated output without the applicable machine gate green and its artifact attached — **including taste reviews** (§2.1) | Frustration #5, directly |
| B5 | — | **New:** CLAUDE.md ≤150 lines. Overflow becomes a skill, an ADR, a constraint record, a CI check, or is deleted. Lessons cost ≤3 lines | Frustration #12 |
| B6 | — | **New:** documented **decisions** carry `revisit-after` and are challenged weekly; **external constraints** carry `verify-by` and are re-verified on their own, much slower cadence (§4.3) | Frustration #9, without training the prompt into noise |
| — | One-way valve (no work-inbound data) | **Unchanged** | Compliance, not friction. `qops` must never be pointed at a work repo or work tracker |

---

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **The overhaul becomes a bloat project and delays go-live** | **high — still the main one** | **Stop-rule rewritten against §7's real estimate, not v1's wish:** if the build exceeds **five** 5h windows, or if GL-21a has not started within **two calendar weeks** of approval, stop and ship GL-21 the old way. §2.3's computed payback (~10 weeks, not 2) means the token argument alone does not carry this — see §10's reduced-scope option |
| Issue-based state becomes as stale as the plan doc | medium | Labels are changed by hooks and CI, not by memory; `triage-loop` runs daily in Actions and lists every issue missing a state |
| A green gate ships a bad result (false confidence) | medium | The reviewer reproduces the gate; every owner rejection a gate missed becomes a new detector. **Sharpened:** the CI gate runs on fixtures (§3.3), so it proves detectors work, not that a real bundle is good — the taste gate remains, by design |
| Hooks unavailable or flaky in Cowork | medium | Retired early by the widened Phase 1 spike. Worst case bounded: Cowork loses automatic brief/resume, Claude Code unaffected. **But note the honest correction (B8):** safety is not hook-independent unless "do not allow bypassing" *and* the separate agent token are both in place — both are now explicit Phase 4 deliverables |
| GitHub outage blocks all work | low | **Corrected (E1):** `state.json`/`resume.md` are local to *one machine*. The real fallback is `.qops/issues.md` (tracked) plus the archived plan doc |
| Subscription-only means qops's own agents eat budget | **low, improved** | `groom-loop` moved to Actions at zero token cost; every scheduled job except `pickup-loop` (off) and the bi-weekly tool-fit review is now LLM-free |
| **Phase 3's destructive step now runs earlier, before the system is proven** | **medium — new, introduced by the reorder** | Accepted deliberately: the alternative is enabling cleanliness rules in a dirty tree (B7). Phase 0's tags + the origin push make it recoverable, and branch deletion keeps its own explicit "proceed" |
| Fixture masters prove less than real artwork | medium | Stated as a limitation in §3.3 rather than discovered later; the local full-res run remains what the owner reviews |

---

## 10. Decisions

### Closed in v1, unchanged

| # | Question | Resolution |
|---|---|---|
| 1 | Plugin name | **`qops`** |
| 2 | `master` → `main`? | **Keep `master`**; plugin resolves the default branch |
| 4 | `gh` available? | **Yes** — 2.96.0, `qvajda`, scopes `gist, read:org, repo, workflow` |
| 6 | `codebase-memory-mcp` | **Deferred** |
| 7 | `pickup-loop` default | **Off**, two routes to `ready:auto` |
| 8 | Phase gating for branch deletion | **Confirmed** — own explicit "proceed"; moves with the phase to Phase 3 |

### Taken this round

| # | Question | Resolution |
|---|---|---|
| 9 | **Repo public or private?** (B14) | **Stays public** — taken deliberately, after establishing that going private on GitHub Free would remove branch protection and rulesets entirely (both are public-repo-only on Free) and cap Actions at 2,000 min/month. Public keeps unmetered Actions and real branch protection. **Cost accepted:** the prompts, niche research, scene library and price/cost table are world-readable. **Recorded as an ADR with a `revisit-after` at launch**, when the trade may look different. Consequences discharged in §4.6 (dev bot) and Phase 0 (secret scan) |
| 10 | **How does CI get artwork?** (A2) | **Committed downscaled fixture masters** in `tests/fixtures/masters/`, gitignore narrowed. Limitation stated in §3.3 |
| 11 | **Telegram credential** (B13) | **Separate dev bot, created in Phase 1**, before any CI touches Telegram. The production token never enters GitHub |
| 12 | **How does Phase 4 prove the gate?** (A1) | **With gates that exist today** — a planted `FLUX [dev]` tripwire and a deliberately failing test. `mockup_qa.py` (GL-21b) plugs into the proven slot in Phase 6 |
| 13 | **Notion** (B12) | **Demoted from S5.** Canonical status = issues + `digest.yml`. Optional daily mirror from Actions via a scoped integration token, or not at all |
| 14 | **Phase order** (B7) | **Git hygiene before substrate.** Its explicit "proceed" gate moves with it |
| 15 | **Where does qops track itself?** (E2) | **Its own plugin repo, from Phase 5** |
| 16 | **GSD vs. issue authority** (E5) | **Issue wins, always.** GSD is a sortie-level working aid; its report is copied into the issue at close |

### Open — one question for the owner

**Scope.** §2.3's computed payback is ~10 weeks, not the ~2 v1 asserted. That
does not invalidate the design, but it does mean the justification rests on the
qualitative fixes rather than on reclaimed tokens. Two viable shapes:

- **Full build** (§7, ≈10.75h + ≈1.75h owner) — everything above.
- **Reduced build** (≈4h) — the gate rule + `SessionStart` brief + `qops resume`
  + issues, and nothing else. Drops the loops, the digest, `pickup-loop`, the
  portability work and the plugin packaging. Fixes frustrations 1, 2, 5, 7 and
  13; leaves 3, 6, 8, 9, 10, 11, 12 for later.

The reduced build is the recommendation **if go-live is expected within ~2
months**. Otherwise the full build pays back before launch. This is a call
about launch timing, which is the owner's, so it is left open rather than
assumed.

---

## 11. Review coverage — all 33 findings

| # | Finding | Resolution | Where |
|---|---|---|---|
| **A1** | `mockup_qa.py` does not exist; gate rule and diagnosis both built on it | §1.1 corrected; **root cause 3 rewritten** (it was never built, not merely unwired); Phase 4's gate test uses existing gates; GL-21 split so GL-21b *is* the detector work | §1.1, §1.2, §7 P1/P4, §10 #12 |
| **A2** | `gate.yml` cannot run — artwork gitignored | Committed downscaled fixture masters; gitignore narrowed; harness parameterised; limitation stated | §3.3, §10 #10 |
| **A3** | `pickup-loop`/`groom-loop`/scribe assigned to a runtime that cannot push | **Runtime capability matrix** added; `groom-loop` → Actions (and needs no LLM); `pickup-loop` → scheduled Claude Code; scribe → outbox + credentialled drain | §3.1, §4.6 |
| **A4** | Hooks: plugin vs `.claude/settings.json`; `.claude/` gitignored | Gitignore narrowed; both hook config and workflows **rendered by `qops install`**; drift detected by `qops doctor` | §3.4, §7 P3/P4 |
| **A5** | `.github/workflows/` same portability problem; Phase 6 fails by construction | Same install-renders-templates model; **Phase 7 criterion restated** to permit generated files | §3.4, §7 P7 |
| **B6** | Three hooks assigned jobs the hook system does not provide | Hook table rewritten with real semantics; `SessionEnd` loses the dirty-tree job; per-turn `Stop` framing corrected; **spike widened to a 5-question matrix** | §3.2, §7 P1 |
| **B7** | Phase 3 enables rules Phase 4 makes satisfiable | **Git hygiene moved before the substrate**; "gate named" relaxed to `gate: none — defined in <issue>` at import | §7 P3/P4, §9 |
| **B8** | "Unbypassable by any client" is false as stated | Restated as conditional; **two explicit Phase 4 requirements**: "do not allow bypassing" enabled, and a separate non-admin `QOPS_AGENT_TOKEN` | §4.5, §7 P4, §9 |
| **B9** | No model for stacked work; next mission is a 4-deep stack | Squash on default branch, **rebase-merge within a stack**; epic records an ordered stack; triager blocks on unmerged parents | §4.5 |
| **B10** | Branch naming violated on day one by branches the plan keeps | **S7 measures attachment, not naming**; `branch_aliases` in config grandfathers `feat/gl5-*`; baseline reconciled | §2, §4.5 |
| **B1** | S6 unmeetable — design adds to the fixed path | **CONTEXT.md made on-demand**, not injected; S6 scoped to CLAUDE.md; globals excluded explicitly | §2, §4.2 |
| **B2** | S4 excludes the review that motivated it | **Two gate classes**; taste reviews are in S4's denominator and legitimate only behind a green machine gate; `ready:auto` exclusion now *derived* from gate class | §2.1, §4.7 |
| **B3** | S10 unfalsifiable — "hot path" undefined | **"Hot path" defined**, with the measuring command; cold storage explicitly free to grow | §2.2, §4.2 |
| **B4** | Effort estimate contradicts the plan's own stop-rule | Recomputed with owner time: ≈10.75h + 1.75h ≈ **three to four windows**; stop-rule rewritten to five windows / two calendar weeks | §7 effort, §9 |
| **B5** | "Net token-positive in ~2 weeks" asserted, not computed | **Computed: ~8–9 weeks.** Stated plainly, with the consequence drawn and a reduced-scope alternative put to the owner | §2.3, §10 open |
| **B11** | `revisit-after` misfires on external constraints | **Two record types**: `docs/adr/` (`revisit-after`) vs `docs/constraints/` (`verified-on`/`verify-by`); Phase 2's list reclassified; S8 scoped to ADRs | §4.3, §7 P2 |
| **B12** | S5 has no mechanism that runs without a session | **S5 no longer measures Notion**; canonical surface is issues + `digest.yml` from Actions; Notion optional, from Actions, scoped token | §4.6, §2 |
| **B13** | Production Telegram credential into a public repo's CI secrets | **Dedicated dev bot created in Phase 1**, before CI exists | §4.6, §7 P1, §10 #11 |
| **B14** | PRD never asks whether the repo should be public | **Asked and decided: stays public**, after establishing that private-on-Free loses branch protection entirely; recorded as an ADR with a launch-time revisit | §1.3, §10 #9 |
| **C1** | §1.1's measured state already wrong | Every row re-measured today, **with the command that produced it**; corrections listed | §1.1 |
| **C2** | Three different branch counts | Reconciled to one: 24 = 2+11+1+9+master; 20 merged non-master; 3 unmerged; **S7 baseline restated as 23 of 23** | §1.1, §2 |
| **C3** | Phase 0's snapshot never delivered; Phase 4 assumes it | **Phase 0 marked incomplete**; snapshot is an explicit prerequisite of the (now earlier) hygiene phase | §7 P0/P3 |
| **C4** | `qops_phase0.sh` vs shipped `.py` | Corrected in the doc, noting the script was right and the PRD wrong | §7 P0 |
| **D1** | `ready:auto` pre-assigned at import | **Stripped entirely from the corpus**; validator rejects it at import | §7 P1 |
| **D2** | GL-21 must not be auto-eligible; also oversized | **`no-auto` label** introduced and applied; **GL-21 split into 21a/21b** | §4.7, §7 P1 |
| **D3** | Corpus fails `triage-loop` on import (10 issues lack `state:`) | `--validate` gate before `--execute`, enforcing one `type:`/`state:`/`gate:` each | §7 P1, §7.1 |
| **D4** | Unapproved scope growth behind a fidelity gate | The 8 net-new objects **listed in the PRD for explicit sign-off**; Phase 1 gate reworded to cover them | §7 P1 |
| **D5** | Label taxonomy in the script ≠ taxonomy in the PRD | **Canonical taxonomy specified here**, read by the importer from config; duplicates removed | §7.1 |
| **E1** | Is `.qops/` tracked? Both answers break a rule | **Split**: config + import corpus tracked, machine state ignored; explicit gitignore block; §9's outage row corrected | §4.1, §9 |
| **E2** | Where does qops's own work get tracked? | **Its own plugin repo, from Phase 5** — dogfood before Phase 7 | §7 P5, §10 #15 |
| **E3** | No instrumentation for S1/S2/S4/S9 | **`qops metrics`**, built in Phase 4, with the extraction for each metric specified | §2.2, §7 P4 |
| **E4** | B3 deleted on the strength of an unrun spike | **B3 deferred**, re-proposed per host after the spike | §8 B3 |
| **E5** | GSD's role asserted but not wired | **Issue is authoritative**; GSD subordinate; report copied into the issue at close; sdd archived per sortie | §4.7, §6 |

**On the review's two structural observations.** Both are accepted. (1) *The
evidence base was not re-verified before it became a plan* — §1.1 is now
re-measured with commands attached, which is the only durable fix. (2) *Phase 1
was started before the design was approved* — the Phase 1 artefacts are kept, but
§7 Phase 1 now names every divergence (D1–D5) as a change to make before
`--execute`, and the net-new objects are listed for sign-off rather than
inherited.

---

**Status: awaiting approve / revise.** One question is open (§10, scope: full vs
reduced build, which turns on expected launch timing). Everything else is closed.
No implementation beyond finishing Phase 0 begins until approval.
