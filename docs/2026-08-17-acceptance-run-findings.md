# Acceptance run findings — 2026-08-17/18

The first end-to-end unattended run of `pickup-loop` → `automerge-loop` with
nobody intervening. Written from observation; **nothing here was repaired in
flight** (`docs/reference/loops.md` §Audit: every prior finding came from
writing it down rather than fixing it in passing).

**Subject:** #59 (GL-32, the orphan gap) — *not* #136, which the Phase 7 sign-off
and the sweep plan both named. See finding 1.

## What happened, in order

| Step | Observed |
|---|---|
| Dry run | `py -3 scripts/qops_pickup.py` printed `pickup-loop: #59 …` + `dry run, not launching`, exit 0. Nothing spent. |
| Claim | `state:planned` → `state:building` on #59 **before** the launch, as the 2026-08-14 Loop Doctor fix requires. |
| Launch | `claude -p` with `--permission-mode acceptEdits` and the coder toolset. No blanket bypass. `QOPS_UNATTENDED=1` set. |
| Branch | `fix/59-orphan-gap-create-intent` — commit type, not an issue label. ADR-0019 satisfied; the #116 defect did not recur. |
| Commit | one, `6cf46ea`, conventional prefix, scoped `fix(gl32)`. |
| PR | #148, body ends `Refs #59` (not `Closes`), as the launch prompt asks. |
| Review | **not requested** — see finding 2. |
| automerge `enable` | fired on `opened`, read `gate:machine` off the *issue*, enabled native auto-merge at 06:36:20Z. |
| Merge | required checks went green (`test` 982 passed, `gate`, `tripwires`, `doc-links`); GitHub merged at 06:44:20Z, squash, branch deleted. |
| `advance` | **never ran** — see finding 3. #59 is still `state:building` + `ready:auto` with its code on `master`. |

The sortie's own work is sound: `python -m pytest -q` reports 982 passed on
`master` at `f3da8cb`, the migration is idempotent on both paths, and the agent
correctly reported that the `discard_superseded_attempt` half needed no change
because an existing test already locked it.

## Finding 1 — the named acceptance subject was structurally unpickable

#136 carries `gate:machine` + `ready:auto` and `state:triage`. `eligible()`
(`scripts/qops_pickup.py:47`) requires `state:planned`, so #136 was never in the
queue at all. Both the Phase 7 sign-off (which named a "GL-63 class" issue) and
the sweep plan (which substituted #136) picked a subject without checking the
one condition the loop actually reads.

`ready:auto` on a non-`state:planned` issue is **inert and invisible**: it looks
like a filled queue and is not one. Two of four `ready:auto` issues were in this
state before the sweep (#115 merged-but-building, #136 triage), which is most of
why the queue read as "starving".

Not filed separately — added to **#147** (the `qops doctor` label-invariant
assertion) as a second invariant to check.

## Finding 2 — "requests review" is unsatisfiable on this repo

`loops.md` §pickup-loop's acceptance check says the run "branches, commits,
opens a PR and **requests review** — and stops there." GitHub rejects a
self-review request and the repo has no second collaborator, so the launched
agent could not satisfy it and said so. It is not an agent failure; the
criterion cannot be met by construction here.

Filed as an issue against the loop definition, `gate:taste` — whether the
criterion is dropped, replaced by a review *agent*, or left as a known-inert
clause is a judgement, not a test.

## Finding 3 — `advance` never fires on a PR that `automerge-loop` merged itself

The exact leak #128 was written to close, still open in the only path that
matters: the unattended one.

`advance` triggers on `pull_request` + `action == closed` + `merged == true`.
When auto-merge is enabled by `GITHUB_TOKEN` (the `enable` job), the resulting
merge is attributed to `github-actions[bot]`, and **GitHub does not start new
workflow runs from events raised by `GITHUB_TOKEN`**. So no `closed` run exists
and `advance` never executes.

Evidence, two PRs on the same workflow file, hours apart:

- **#146** (`no-issue/triage-sweep-plan`) — auto-merge enabled by a *human*
  token (`gh pr merge --auto` as `qvajda`). A `closed` run exists:
  `32074528054`, `advance success`.
- **#148** (`fix/59-…`) — auto-merge enabled by the `enable` job as
  `app/github-actions`. `gh run list --workflow automerge.yml` shows exactly one
  run for that branch, `32107634613`, event `pull_request` (opened),
  `advance skipped`. There is no `closed` run.

Consequence, live right now: #59's code is on `master` and its issue reads
`state:building` + `ready:auto`. `metrics.S9` counts a finished sortie as
in-flight — the same instrument error #128 diagnosed — and because
`state:building` is not eligible, the row is also silently out of the pickup
queue. It is not a stuck loop; it is a wrong number and a lost row.

This is why #115 looked the way it did. It was never a one-off stale row.

Filed. Candidate directions, none chosen here: trigger `advance` off
`workflow_run`/`check_suite` instead of `pull_request`, run a scheduled sweep
that reconciles merged PRs against issue labels, or enable auto-merge with a PAT
so the merge is not `GITHUB_TOKEN`-attributed. The last one buys the trigger at
the cost of a stored credential.

## Finding 4 — the launch runs in the owner's working tree

`launch_argv` starts the agent with `cwd=ROOT`. It branched, so the session's
checked-out branch changed under an in-progress owner session (this one). No
uncommitted work was lost — the tree was clean, which was luck rather than a
control. `superpowers:using-git-worktrees` and `max_worktrees: 2` in
`.qops/config.yml` both exist; the loop uses neither.

Filed, `gate:taste` — worktree isolation is a design call, not a bug fix.

## Minor, not filed

The launched session printed two harness warnings from `.claude/settings.json`:
`Write(.planning/*)` and `Write(STATE.md)` allow-rules are not matched by file
permission checks (only `Edit(path)` rules cover file-editing tools). Cosmetic
for this run — `acceptEdits` was in force — but the rules are doing nothing.

## What the run proves

Everything between the claim and the merge works unattended, first try, with no
hand-holding: claim, branch naming, scoped grant, commit, PR, gate reading,
native auto-merge, required checks, squash, branch delete. The failure is at the
last inch — the row that says the sortie is finished.
