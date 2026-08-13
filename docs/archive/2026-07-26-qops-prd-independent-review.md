# Independent review — `qops` ways-of-working PRD

**Reviewing:** `docs/2026-07-26-ways-of-working-overhaul-prd.md` (+ the Phase 0/1
artefacts already on disk)
**Date:** 2026-07-26 · **Reviewer role:** review only. Nothing here is fixed,
patched or implemented — every item is stated as a problem for the planner.
**Method:** every factual claim in §1.1 and §6 was checked against the working
tree, git, `.gitignore`, `scripts/`, `.qops/` and the plan of record.

**Verdict in one line:** the architecture is coherent; the *plan* has one true
circular dependency, one gate that cannot execute where it is specified to
execute, and a cluster of contradictions between §3.6 and §6 about what a Cowork
sandbox can do. Phase 1 is also already half-built, and what is built diverges
from the document awaiting sign-off.

Findings are ordered by consequence, not by section.

---

## A. Blockers — these break the plan as sequenced

### A1. `scripts/mockup_qa.py` does not exist. The gate rule is built on a file that has not been written.

`ls scripts/` returns `gl19_m1_render.py`, `gl6_author.py`, `qops_phase0.py`,
`qops_phase1.py`. There is no `mockup_qa.py`.

The PRD asserts otherwise in four places, and each one is load-bearing:

- **§1.1**, in the *measured state* table: "`scripts/mockup_qa.py` (6 defect
  detectors) **was written** after the owner manually rejected 3 of 4 scenes".
- **§1.2 root cause 3**: "The 6 detectors that would have caught it **exist**,
  but as an artifact, not a gate."
- **§3.1** `gate.yml` runs it.
- **§6 Phase 3's exit gate**: "push a change that trips `mockup_qa` and confirm
  the PR cannot request review."

In reality it is an unbuilt deliverable of **GL-21** — `.qops/issues.md` and the
plan of record (line 142) both list it under GL-21's scope: *"Plus
`scripts/mockup_qa.py`: 6 automated defect detectors … **This is the machine gate
that must pass** before any owner review of scenes."*

Two consequences:

1. **Circular dependency.** Phase 3 cannot pass its own gate until GL-21 ships.
   GL-21 is Phase 5. Phase 5 runs after Phase 3.
2. **The diagnosis in §1.2 is wrong, not just the inventory.** Root cause 3 says
   the problem was a gate that existed but wasn't wired. The actual problem is
   that it was never built. Those imply different fixes, and §1.2 is what the
   whole L0 layer is justified by.

### A2. `gate.yml` cannot run on GitHub Actions. The artwork it needs is gitignored.

`scripts/gl19_m1_render.py` hard-codes `MASTER = ROOT / "db" / "base_artwork" /
"39.png"`. `.gitignore:37` excludes `db/base_artwork/` wholesale (`git
check-ignore -v` confirms). `git ls-files db` returns **1** file.

So on a clean CI checkout the harness fails on its first render. Whatever
`mockup_qa.py` ends up doing over real bundles will hit the same wall, since it
also needs an approved master to composite.

This is not a detail — §1.3 and §3.1 rest the entire cost argument on "push
verification down to free compute", and the one gate that actually catches the
defects the owner has been catching by hand is the one that cannot run there.
The PRD never asks how CI gets the artwork (LFS? a fixture master committed
deliberately? a self-hosted runner? gate-runs-locally-and-uploads?). That is a
design decision, not an implementation detail, and it changes the L0 story.

### A3. `pickup-loop` is assigned to a runtime that the PRD itself says cannot do the job.

§6 Phase 0 states the reason Phase 0 runs in Claude Code: it "needs authenticated
`git push` and `gh`, **neither of which exist in the Cowork sandbox**."

§3.6 then assigns to *Cowork scheduled tasks*:

- `pickup-loop`, whose acceptance check is "highest-priority `state:planned`
  issue **moved to `building` with a branch**", and whose hard block is "branch
  **+ PR** only, never a merge";
- `groom-loop`, which must read and act on repo state weekly.

Opening a branch and a PR is precisely `git push` + `gh`. Either the Phase 0
claim is wrong, or these two loops are in the wrong runtime. The same
contradiction reaches the **scribe**: §3.1's `SessionEnd` hook "ensures the
active issue has a comment", which is a `gh` call, in whichever host the session
happened to be.

### A4. Hooks: the delivery mechanism contradicts itself, and the file cannot be committed.

§3.1 heading: "**Hooks** (`.claude/settings.json`, shipped by the plugin)". Those
are two different mechanisms:

- a **plugin** carries its own hook configuration and travels between projects;
- `.claude/settings.json` is per-project and must be present in each repo.

If it is the latter, Phase 6's pass condition — "everything project-specific must
live in one `.qops/config.yml`; if anything else needs editing, the plugin isn't
portable" — fails by construction, because a settings file has to be installed
and maintained per project.

Worse, **`.gitignore:42` ignores `.claude/` wholesale**, so the file cannot be
committed at all today. The hook-spike README (`.qops/hook-spike/README.md`)
catches this and proposes a narrowing; the PRD does not mention it, and the PRD
is the document being signed off. As it stands, the hook layer works on one
desktop and silently does not exist for any clone — the failure mode where a
system appears to work and is actually one laptop.

### A5. `.github/workflows/` has the same portability problem, and Phase 6 will fail on it.

Four workflow files (`test`, `gate`, `guard`, `digest`) must live in each
consuming project's `.github/workflows/`, and their contents are inherently
project-specific (test command, gate command, tripwire strings). They cannot be
driven from `.qops/config.yml` without an installer step that the PRD does not
describe. Phase 6's stated pass/fail criterion therefore already has a known
failure, before it runs.

---

## B. Internal inconsistencies in the design

### B6. Three of the five hooks are assigned jobs the hook system does not provide as described.

- **`SessionEnd` "fails loudly if the working tree is dirty"** (§3.5). SessionEnd
  runs *after* the session has ended. There is nothing left to block and nobody
  left to read the failure. A dirty-tree check has to be a `PreToolUse`/`Stop`
  concern, or a CI concern, to have any effect.
- **`Stop` → `qops resume`** (§3.1). `Stop` fires when the assistant finishes a
  *turn*, not a session. As written, `resume.md` is rewritten on every turn. That
  may be acceptable (it is cheap), but §3.1's framing — "checkpointing stops
  depending on memory" — implies session-level semantics the event does not have,
  and the estimate "a mid-session cut-off loses at most one pass" quietly depends
  on which one it is.
- **`PostToolUse (git commit, test run)`** (§3.1). PostToolUse matches *tool
  names*, not semantic actions; the ledger will have to parse Bash command text.
  Feasible, but the table describes a granularity that does not exist.

The Phase 1 spike, as scoped, only answers *"do hooks fire in Cowork?"*. It does
not answer *"can these five hooks do these five jobs?"*, which is the question
§3.1 actually depends on.

### B7. Phase ordering: Phase 3 switches on rules that Phase 4 is what makes satisfiable.

Phase 3 enables the guard hook, branch protection, and the "nothing uncommitted
at session end" rule. Phase 4 — after it — is what cleans the 24 dirty/untracked
paths, 20 stale branches and 6 worktrees. Every session between P3 and P4 trips
the dirty-tree check on `outputs/gl19_m1/_dbg_*.png`, `assets/brand/`, 13
untracked docs and `.qops/` itself.

Related: Phase 1 requires each open issue to carry "their **gate named**", but no
gate exists until Phase 3 (`gate.yml`) and A1 (`mockup_qa.py`).

### B8. "Unbypassable by any client" is not true as stated, and the safety argument leans on it.

§3.5 and §8 decision 5 both rest on branch protection being "**the authoritative
control, unbypassable by any client**", which is what lets §8 conclude "safety
does not depend on hooks".

Repository admins bypass branch protection unless *"do not allow bypassing the
above settings"* is explicitly enabled. The unattended agent authenticates as
`qvajda` with the same `gh` token as the owner — so GitHub cannot distinguish
"agent" from "owner", and both are admin. The safety property is real but
conditional on a configuration the PRD never states as a requirement, and on the
absence of a separate agent identity it never proposes.

### B9. The git standard has no model for stacked work, and the next mission is a 4-deep stack.

§3.5: one issue → one branch → one PR → **squash merge** → delete.

The actual work: GL-21 branches off `feat/gl5-mockup-compositor` (per
`.qops/issues.md`, "Base branch: `feat/gl5-mockup-compositor` →
`feat/gl21-matte-compositor`"), PR #2 for GL-5 is still open, and the chain is
GL-21 → GL-6 attempt 3 → GL-19 re-run → PR #2 merge. That is four dependent
sorties, none of which targets `master`.

Squash-merging a stack rewrites SHAs and produces duplicate-content conflicts
down the chain. The PRD's git model does not cover it, and it is the shape of the
entire mockup mission — i.e. of Phase 5 itself.

### B10. Branch naming is violated on day one by the branches the plan keeps.

§3.5 mandates `<type>/<issue#>-<slug>` with the **GitHub issue number**, "what
lets the scribe link commit → branch → PR → issue with zero LLM involvement".

`feat/gl5-mockup-compositor` (kept, per the inventory, as the GL-21 base, under
an open PR) does not comply, and the Phase 1 artefact already specifies
`feat/gl21-matte-compositor` — a GL id, not an issue number. **S7** ("live
branches not attached to an open issue: 0") is therefore either failed at go-live
or requires renaming a branch that has an open PR against it.

### B1. S6 is not achievable as worded, because the design adds to the fixed path.

S6: "per-session fixed instruction cost ≤ **150 lines total**", today "174 +
global". B5 caps *CLAUDE.md alone* at 150.

But the new design deliberately adds fixed-path content: **CONTEXT.md (~80
lines)**, written explicitly so agents read it every session; the ~400-token
brief; plus qops's own rules landing in CLAUDE.md. The global operating
instructions (~110 lines) are unchanged and also fixed. 150 + 80 + global is
comfortably over 150 "total".

Either S6 means "CLAUDE.md only" — in which case it duplicates B5 and the
"total" claim in the criterion is wrong — or it is unmeetable.

### B2. S4 excludes the review that motivated it.

S4: "owner review requests that arrive with a failing/absent machine gate: **0**".

§3.6 states that a fully machine-checkable gate "**alone excludes the entire GL-6
scene-authoring class of work**". Scene acceptance is exactly the review that
produced frustration #5 (3 of 4 scenes rejected, twice).

So either taste-reviews are outside S4's denominator — which should be said,
because it shrinks the headline claim considerably — or scene bundles can never
legitimately reach the owner. The PRD needs to define which reviews S4 counts,
and what a *partial* gate (detectors pass, taste still pending) is allowed to do.

### B3. S10 is unfalsifiable as written, and Phases 1–3 all add.

S10 requires "instruction lines + doc lines **in the hot path**" to be flat or
falling. Phase 1 adds `.qops/issues.md` (463 lines) plus ~31 issue bodies; Phase
2 adds ~15 ADRs, CONTEXT.md and MISSION.md; Phase 3 adds four workflows, a CLI, a
PR template and a Telegram setup guide. The escape hatch is that ADRs are not
"hot path" — but **"hot path" is never defined**, and the anti-bloat rule only
ever counts CLAUDE.md. A criterion whose denominator is undefined cannot fail.

### B4. The effort estimate contradicts the plan's own stop-rule.

§6 sums to ≈10.5h excluding Phase 5 (0.5 + 2 + 2.5 + 3.5 + 1 + 1), then calls it
"roughly two working sessions". Under 5h windows that is ~2 windows of *pure
execution*, with zero allowance for the four owner sign-off gates between phases,
the owner's reading time, or the Phase 2 Opus session's own review.

§9's top-risk mitigation is "if P1–P3 slip past two sessions, stop and ship GL-21
the old way". P1–P3 alone is 7.5–9.5h ≈ two windows at *best case*. The stop-rule
is triggered by the plan's own optimistic estimate.

### B5. "Net token-positive within ~2 weeks" is asserted, not computed.

The recurring saving is roughly the ~60 lines of static-config data leaving
CLAUDE.md (order 1.5–2k tokens/session) plus the avoided doc sweep. The one-time
cost includes a dedicated **Opus** session (Phase 2) and 3–4h of Sonnet build
(Phase 3). No arithmetic is shown anywhere.

This claim is doing real work in the argument — it is the answer to §9's #1 risk
("the overhaul itself becomes a bloat project"). It should be the one number in
the document that is calculated rather than assumed.

### B11. `revisit-after` on 100% of ADRs (S8) misfires on externally-imposed constraints.

Phase 2's ADR candidate list includes items that are not revisitable decisions:
FLUX schnell (a **licence** boundary), `who_made: i_did` (the Etsy API has no
other value — verified live), per-group shipping profiles (Etsy allows one
profile per listing), unframed poster line. Asking "still true?" on these
generates recurring noise with no decision attached, which is the failure mode
that trains people to ignore the prompt.

The anti-ossification rule needs either an exempt class or a distinction between
*decisions* and *recorded external constraints* — and if the latter aren't ADRs,
S8's "100%" is measuring a smaller set than Phase 2 will produce.

### B12. S5 (Notion ≤24h, unprompted) has no mechanism that runs without a session.

The only Notion mirror in the design is the **scribe on `SessionEnd`** (§3.1,
§3.3). §3.6's schedule table — the place where unprompted things live — contains
**no Notion job**. Two days without a session means S5 is missed by design, which
is the same failure mode ("only updates when I'm there") that S5 exists to fix.

### B13. The production Telegram credential goes into a public repo's CI secrets, unflagged.

§3.6 reuses the *pipeline's* bot token and admin chat ID so `digest.yml` can post
from GitHub Actions. That means the live design-approval bot's credentials are
stored as Actions secrets on a **public** repository, and the same bot that
approves real Etsy publishes now has a CI-triggered write path.

`CLAUDE.md` explicitly classes `TELEGRAM_ADMIN_CHAT_ID` as credential-grade
("treat this ID with the same care as an API key — read it from `.env`, never
hardcode"), and Phase 0's entire rationale is that the repo being public makes
secret hygiene the highest-value item. §3.6 waves this through as "a convenience
for one project". The `[qops]` prefix and callback namespace separate the
*messages*; they do not separate the *credential*.

### B14. The PRD never asks whether the repo should be public.

"Public" appears twice: as a secret-scan risk (Phase 0) and as a benefit ("Actions
minutes are **unlimited and free** — the strategy is stronger than costed"). It is
never asked whether the pipeline itself — prompts, niche research, the scene
library, the price/cost table, the whole method of an intended revenue stream —
should be world-readable.

If the answer is "it shouldn't", the free-CI argument weakens (Free plan private
repos get 2,000 minutes/month), §1.3's cost model shifts, and B13 becomes
sharper. This is a strategic question the PRD's own evidence raises and does not
put to the owner.

---

## C. Factual drift against the repository

### C1. §1.1's measured state is already wrong.

| §1.1 claim | Measured now |
|---|---|
| `docs/` = 50 files, **11,967 lines** | **52 files, 13,149 lines** |
| 36 test files | **34** `test_*.py` in `tests/` |
| `scripts/mockup_qa.py` exists | **does not exist** (see A1) |

Small in isolation. It matters because §1.1 is the evidence base for the whole
document *and* the baseline S10 is measured against.

### C2. Three different branch counts for the same fact.

- §1.1: "24 local branches, of which **21** are already merged (11 `fix/*` + 9
  `worktree-agent-*` + master)"
- Branch inventory §2/§3: "**20** of the 24 are already merged into master"
- S7: "Live branches not attached to an open issue — today **23 of 24**"

Verified: 2 `feat/*` + 11 `fix/*` + 1 `proto/*` + 9 `worktree-agent-*` + `master`
= 24; merged non-master = 20; unmerged = 3. Only the inventory's framing is
defensible. §1.1 and S7 should be reconciled to it — S7 in particular is a
success criterion with a stated baseline.

### C3. A Phase 0 deliverable was not delivered, and Phase 4 assumes it was.

§6 Phase 0 bullet 4: "**Snapshot `.remember/` and `.superpowers/sdd/`**."

`scripts/qops_phase0.py` contains no reference to either path (`grep` for
`remember|superpowers|snapshot|archive` returns nothing). `docs/archive/` holds
exactly one file — the branch inventory. `.remember/` (19 files) and
`.superpowers/sdd/` (2.1 MB) are untouched.

Phase 0 is marked executed. Phase 4 archives/deletes on the assumption the
snapshot exists.

### C4. Phase 0's artefact name doesn't match what shipped.

PRD says `scripts/qops_phase0.sh`; shipped as `scripts/qops_phase0.py`
(deliberately — the script documents why: Windows/git-bash portability). Cosmetic,
but the PRD is the sign-off document.

---

## D. Phase 1 is already half-built, and diverges from the PRD awaiting sign-off

`scripts/qops_phase1.py` (270 lines) and `.qops/issues.md` (463 lines, 31 issue
blocks) already exist. Reviewing them against §6 Phase 1:

### D1. `ready:auto` is pre-assigned at import, bypassing the control §8 decision 7 was written to create.

`.qops/issues.md` labels **GL-8, GL-20 and GL-21** `ready:auto` in the import
corpus. §3.6 says the label arrives exactly two ways: the owner marks it, or the
triager derives it against 7 conditions. Neither the triager nor the conditions
exist until Phase 3. The import short-circuits both routes for three issues.

### D2. GL-21 in particular must not be auto-eligible.

Phase 5 designates GL-21 as **the** acceptance sortie the owner runs end to end to
measure S1/S2/S4/S9. If `pickup-loop` ever fires on it, the measurement is gone.

Separately, GL-21 fails the *"planner-estimated at ≤½ a window"* condition on its
face: three compositor changes (C1–C3) **plus** six defect detectors **plus** a
contact-sheet generator **plus** tests. Its own issue body calls it "the first
half of the PR-#2 unblock". It is also the biggest single sortie in the corpus,
labelled as the safest.

### D3. The corpus fails `triage-loop` on import.

`triage-loop`'s acceptance check is "every open issue has state + owner". Ten open
issues carry no `state:` label at all (GL-6, 7, 8, 10, 11, 12, 17, 18, 20, 21).
And `ready:auto` on GL-8/GL-20/GL-21 without `state:planned` contradicts the
first of §3.6's seven eligibility conditions.

### D4. Unapproved scope growth in the phase whose gate is "spot-check for **fidelity**".

PRD Phase 1: "Epic issues for the **two** live missions". Artefact: three
(`EPIC-mockups`, `EPIC-automation`, **`EPIC-launch`**). PRD: 21 GL rows → issues.
Artefact: 21 GL rows **+ 7 `BL-*` backlog issues**.

Both additions look like improvements. But the Phase 1 gate is "owner spot-checks
5 issues against the plan doc **for fidelity**", and eight of the 31 objects have
no counterpart in the plan doc to be faithful to.

### D5. Label taxonomy in the script isn't the taxonomy in the PRD.

`qops_phase1.py` defines both `type:epic` and `epic` and applies both. §3.4's
taxonomy (`type:research|code|manual|test|decision`) has neither, nor
`type:impl-research`, `go-live-blocker`, `mission:launch-prep`. The label set is
the state layer's schema; it should be specified in the document that gets signed
off, not discovered in the importer.

---

## E. Decisions the PRD defers that Phase 1 will force anyway

### E1. Is `.qops/` tracked or not? Both answers break a stated rule.

`.qops/` is currently untracked **and not gitignored** — undecided by default.

- **Committed:** hook-written `state.json` and `resume.md` dirty the tree on
  every turn, colliding with §3.5's "nothing uncommitted at session end" and
  generating merge noise on every branch.
- **Ignored:** it is desktop-only, which undercuts §9's "GitHub outage blocks all
  work → low; `.qops/state.json` + `resume.md` are local" (local to *one machine*)
  and Phase 6's portability story.

The PRD never says which, and Phase 1 scaffolds `.qops/` immediately.

### E2. Where does qops's own work get tracked?

Phase 1 creates a plugin repo. §3.5 refers to an "issue repo" in config. Nothing
says whether qops's own bugs and its Phase 3–6 work become issues in that repo —
i.e. whether the system tracks itself, or whether the overhaul is the last thing
ever managed outside the overhaul.

### E3. No instrumentation exists for S1/S2/S4/S9.

Phase 5 measures them. Nothing in the design is specified to capture them. The
ledger is the obvious candidate but §3.1 defines it as "one line per git commit /
test run" — which gives none of the four. Without this, Phase 5's revise-or-
proceed decision is a judgement call, which is the thing the PRD is trying to
replace.

### E4. B3 deletes the checkpoint instruction on the strength of an unvalidated spike.

§7 B3 removes "checkpoint every 25–30 exchanges" *now*, replaced by the
`Stop`/`PreCompact` hook. But the Phase 1 spike hasn't run, and per B6 the `Stop`
event may not have the semantics assumed. If the spike returns "Cowork ignores
project hooks" — the outcome the spike README calls "expected" — B3 removes
Cowork's only checkpoint mechanism and replaces it with a command someone has to
remember to type, which is verbatim the failure mode B3's own justification cites
("an instruction that depends on remembering is the frustration itself").

The instruction changes in §7 are being asked for approval *before* the evidence
that decides one of them.

### E5. GSD's continued role is asserted but not wired.

§5 keeps GSD "at sortie level, where it works". Phase 0 snapshots
`.superpowers/sdd/` (2.1 MB of brief/report/progress state) and Phase 4 archives
docs. Nothing says whether GSD keeps writing there, whether its state duplicates
the issue body, or which of the two is authoritative when they disagree — which
is a re-run of root cause 1 ("state lives in prose, in one place, maintained by a
human") in a second location.

---

## Summary — what a planner should resolve before Phase 1 proceeds

**Must resolve (plan does not execute otherwise):** A1, A2, A3, A4.
**Should resolve before sign-off (the document is being approved on them):** A5,
B8, B9, B13, B2, B5, C2, C3.
**Should resolve before the Phase 1 import runs:** D1, D2, D3, E1.
**Worth putting to the owner as questions rather than fixing:** B14 (should the
repo be public), B11 (what counts as an ADR), E4 (defer B3 until the spike
reports).

Two structural observations that no single finding captures:

1. **The PRD's evidence base was not re-verified before it became a plan.** A1
   and C1–C3 are all the same class of error: a claim written once, then built
   on. That is the failure the document itself diagnoses as root cause 1.
2. **Phase 1 was started before the design it implements was approved.** The
   artefacts are good work, but D1–D5 exist *because* they were written against
   an evolving document rather than a signed one — and D1/D2 in particular
   quietly undo an owner decision (§8 #7) that was closed the same day.
