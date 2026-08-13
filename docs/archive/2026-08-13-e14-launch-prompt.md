# E14 launch prompt — qops Phase −1 and Phase 1

**Paste everything below the line into a fresh Claude Code session, started from
the repo root.** Start it with Remote Control on, because §0 exists to prove that
works:

```bash
claude --remote-control "qops E14"
```

Then, inside the session, `/config` → enable **Push when actions required**.

> **Note the irony, and it is deliberate.** This is a `*-launch-prompt.md` file,
> which is exactly the artefact S2 counts and qops exists to abolish. It is
> written anyway because the machinery that replaces it is what this session
> builds. **It should be one of the last two or three ever written in this repo**
> — after Phase 1, work starts from `qops brief` and an issue number.

---

You are running **E14**, the first execution session of qops PRD v3.

**Read first, in this order, and nothing else yet:**

1. `docs/2026-08-13-qops-prd-v3.md` — the PRD. §8.1 holds nine owner decisions
   (30–38); they are closed, not open for re-litigation.
2. `CLAUDE.md` — project constraints. §2's PRD threshold is already satisfied by
   PRD v3; do not write another PRD.
3. `.qops/issues.md` — **header only**, not the 86 blocks. It explains what the
   corpus is and how it was derived.

**Do not read** `docs/2026-07-22-go-live-plan-of-attack.md`. It is 401 KB and
exceeds a single read call; that fact is §1.1 of the PRD and is the reason this
session exists. If you need a board row, grep for it or read the matching block
in `.qops/issues.md`.

## §0 — Before anything: disagree with the PRD, once

PRD v3 was written in one session by one agent. **Spend your first pass looking
for what it got wrong**, not confirming it. Specifically check:

- Are §1's measured numbers still true today? Re-run the commands in the table.
- Does anything in §3.3's configure-vs-build map assume a capability that does
  not actually exist in the installed toolchain?
- Is the §2.1 arithmetic reproducible from the stated inputs?

**Report what you find in one short list, then stop and wait.** If you find
nothing material, say so in one line and continue to §1. Do not restructure the
PRD; propose amendments and let the owner take them.

## §1 — Phase −1: measure S1 and S2, retroactively if possible

**This is the gate on everything else. Scope is decided by this number, not by
argument.**

§2.1's payback rests on "≈1.5 resumes a day", which nothing has ever counted. At
1.5 the payback is ~5 weeks; at 1.0 with the low estimate it is ~10.5 and the
right answer may be substrate-only.

**Try retroactive first.** Check whether `~/.claude/projects/` holds per-session
JSONL transcripts for this repo. If it does, compute over every session since
**2026-07-14**:

- **S1** — for each session, the number of file reads before the first *productive*
  tool call (a write, an edit, a test run, or a commit), and whether any of those
  reads exceeded 200 lines. Report the median and the distribution, not just a
  mean.
- **S2** — count of files matching `*kickoff*`, `*session-prompt*`, `*launch*`,
  `*brief*`, `*runbook*` added under `docs/` in the same window:
  `git log --since=2026-07-14 --diff-filter=A --name-only --format= -- 'docs/*kickoff*' …`
  The E13 figure was **43**. Confirm or correct it.
- **Resumes per day** — sessions started with `--resume`/`--continue`, or
  restarted after a limit, per active day. **This is the number that matters.**

**If the transcripts are absent or do not record what is needed, say so plainly
and fall back** to the prospective week in PRD §7 Phase −1. Do not invent a proxy
and present it as the measurement; a wrong number here is worse than no number,
because it is what the scope decision is made on.

**Write the result to `docs/2026-08-XX-e14-phase-minus-1-findings.md`, then STOP
and report.** The owner picks full build or substrate-only from that document.
The analysis script is throwaway — **do not commit it**, same rule as E13's
corpus extractor, and `qops metrics` supersedes it in Phase 4.

## §2 — Phase 1, only after the owner has chosen scope

In PRD order. Each item is small; do them one at a time and commit after each.

1. **Run the hook spike.** `.qops/hook-spike/` has existed since 2026-07-26 and
   has never run — it is the oldest unexecuted item in the whole plan, and
   nothing in Phase 4 is designable without it. Answer the five-question matrix
   in PRD v2 §7 Phase 1 for **both** Claude Code and Cowork: do
   `SessionStart` / `Stop` / `PreCompact` / `PreToolUse` / `SessionEnd` fire; can
   `PreToolUse` actually **block** a Bash call; is the command string available to
   `PostToolUse`; does `Stop` fire per turn. **Record the outcome as an ADR.**
2. **Apply the `.qops/` tracked/ignored split** as its own commit — PRD decision
   21. Tracked: `config.yml`, `issues.md`. Ignored, explicit block: `state.json`,
   `resume.md`, `ledger.jsonl`, `outbox.jsonl`, `wt/`. It is currently untracked
   *by omission*, which is the accident E1 says to stop inheriting.
3. **Install eleven skills as editable copies** — decision 36, and note the count:
   `npx skills add mattpocock/skills --agent claude-code` taking exactly
   `wayfinder`, `to-spec`, `to-tickets`, `grill-me`, `grill-with-docs`,
   `domain-modeling`, `code-review`, `tdd`, `triage`, `setup-matt-pocock-skills`;
   then `npx skills add Forward-Future/loop-library --skill loopy --agent claude-code`.
   **Not the marketplace bundle. Not all 21.** Then run
   `/setup-matt-pocock-skills`: tracker = GitHub, labels = PRD §9's taxonomy, docs
   location = `docs/`.
4. **Telegram dev bot + channel plugin.** A *new* bot from BotFather — the
   production bot that approves real Etsy publishes is never reused (finding
   B13). `/telegram:configure`, pair, `/telegram:access policy allowlist`.
   **Permission relay stays off** (decision 31); approvals come from Remote
   Control (decision 38), which you are already running.
5. **Labels and milestones** from PRD §9's amended taxonomy. Note `state:` gained
   `cancelled` and `mission:` was replaced wholesale — do not use PRD v2 §7.1.
6. **Re-extract the corpus and diff it against `.qops/issues.md`.** The E13
   snapshot is from board commit `17f35cf`; anything that has landed since will
   show up here. The extraction rules are in the corpus header. **An empty diff or
   an explained diff is a gate item** — PRD §4.2.
7. **Import: `--validate` before `--execute`.** The validator fails if any open
   issue lacks `type:` / `state:` / `gate:`, or if any row carries `ready:auto`.
   Expect **86 issues, 26 open, 60 closed**, one of them cancelled (GL-29) and one
   blocked (GL-11). `no-auto` on **GL-63** only.
8. **Header on the board doc:** superseded by issues, retained for history. Do not
   delete it — Phase 3 archives it.

**Phase 1 gate, all five:** spike ADR written · validator green · extraction diff
empty or explained · owner spot-checks 5 rows for fidelity · owner has already
signed off the one net-new object (GL-63, decision 35).

## Standing constraints for this session

- **Activation is not a planning variable.** Do not propose, schedule or prompt
  for publishing a listing. Everything stays a draft.
- **Git history is not rewritten.** Closed decision. Do not raise `filter-repo`,
  BFG or a force-push under any framing.
- **No pipeline work.** GL-53's remaining stage loops, GL-66, GL-67, GL-73 are all
  out of scope — mixing pipeline code into a ways-of-working session is exactly
  what qops exists to stop. **GL-63 is reserved** as the Phase 6 acceptance
  sortie; do not fix it now, that destroys the measurement.
- **Nothing is deleted this session.** Phase 3 is the first destructive phase and
  it is not in scope. `.remember/` and `.superpowers/sdd/` stay where they are —
  they are archived (`docs/archive/2026-08-13-remember-sdd-snapshot-manifest.md`)
  but Phase 3 removes them, not you.
- **Two stop-and-report gates**, and they are hard: after §0, and after §1. Do not
  run past either.
- **Scope fence.** Deliver what is asked at the scope intended. If the PRD looks
  wrong, say so in a sentence and continue as asked rather than quietly widening.
  Do not spawn subagents to verify your own work; do keep a read-only review pass
  before any commit, which is a convention this project earned the hard way
  (board tool-fit flag, 2026-08-01).
- **Verification conventions stand.** "Verify by measurement, not by status code"
  (GL-22a) and "gate the side effect, not the value" (GL-48) are not
  prompt-level nagging and are not dropped.
