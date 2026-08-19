# Attempt 3 findings — criterion 8 — 2026-08-19

The third attempt at PRD criterion 8: does a sortie go from pickup to
`state:done` with no human touch in between? It was 0 for 2 — attempt 1 (#59)
broke at row-advance, attempt 2 (#57, #71) never reached a PR. Written from
observation; **nothing here was repaired in flight**
(`docs/reference/loops.md` §Audit).

**Outcome: PASS.** Every inch, first try, unattended. See §Verdict.

**Subject:** #160 (live-DB schema drift undetected by `qops doctor`) — *not*
#52 (GL-27), which the launch prompt floated. See finding 1.

**Instrument:** manual `python scripts/qops_pickup.py --launch`, watched. The
scheduled task `qops-pickup-loop` stayed disabled throughout and is still
disabled.

## What happened, in order

| Step | Observed |
|---|---|
| Pre-flight | `.qops/state-report.md` regenerated at HEAD (was two commits stale at `57e898c`); every row a number, so A.5's metrics fix has not regressed. Five merged sortie branches pruned local+remote — see finding 4. `pytest -q` 1014 passed. `qops doctor` **not** clean, 4 problems — findings 2 and 3. |
| Arming | #160 already carried the owner's `ready:auto` and sat at `state:triage`, so it was inert (the acceptance run's finding 1, still live in the queue). Sortie plan written into the issue, then `state:triage` → `state:planned`. |
| Dry run | `python scripts/qops_pickup.py` printed `pickup-loop: #160 …` + `dry run, not launching`, exit 0. #160 was the only eligible issue. |
| Launch | 08:28:23Z. `claude -p`, `--permission-mode acceptEdits`, coder toolset, `QOPS_UNATTENDED=1`. No blanket bypass. |
| Claim | `state:planned` → `state:building` **before** the launch, observed at 08:28:5x. |
| Branch | 08:29:46Z, `fix/160-schema-drift-doctor-guard` — commit type, not an issue label. ADR-0019 satisfied. |
| Commit | one, `5248b74`, `fix(qops):`, body ends `Refs #160`. |
| PR | #166 at ~08:30:5x, body carries `Refs #160` (not `Closes`), no review requested, no merge attempted. Launch exited 0 at 08:30:59Z — **2m36s from launch to PR**. |
| `state:review` | correctly **absent** — `automerge.yml` sets it only on the non-`gate:machine` path. #151 working. |
| automerge `enable` | fired on `opened`, read `gate:machine` off the *issue*, enabled native auto-merge at 08:31:21Z. |
| Gate | `gate`, `test`, `tripwires`, `doc-links` all pass. |
| Merge | GitHub merged at 08:40:15Z, squash, branch deleted. No human touch. |
| `advance` | `skipping`, as it has every time — the merge event does not reach it. Expected under A.5's design; the reconciler is the path. |
| Row | `gh workflow run digest.yml` dispatched 08:40:33Z; reconciler advanced #160 to `state:done` and dropped `ready:auto` by 08:41:17Z. Inside one minute. |

The sortie's own work is sound. `qops doctor` on `master` at `631d017` reports
no schema-drift problem; the parser resolves all 16 tables in `db/schema.sql`;
`pytest -q` reports 1017 passed. It correctly scoped out the migrations ledger, and it
independently found the trap the plan named — a check that fails on a machine
with no `db/qhoto.sqlite3` would have failed `gate` on every future PR.

## Verdict

**Pass**, on §4's definition: every inch, and no human touch between launch and
reconcile. The one command issued in between — `gh workflow run digest.yml` —
is §3's sanctioned way to force the reconciler rather than wait for 06:00 UTC,
and the reconciler is what advanced the row, not a hand edit.

Criterion 8 is met on this repo. **P8.0's added clause is satisfied and Session
B's gate is cleared.** The design pass §4 held in reserve for a silent failure
is not needed.

Two qualifications the record should carry:

1. **It is one observation, not a rate.** The subject was well-specified, small
   and provable by a 4-second test file — which is exactly the eligibility rule
   attempt 2 discovered, and the run is evidence that the rule works, not that
   the loop survives a subject that breaks it. PRD P8.1 already carries the
   action: make that rule checkable rather than prose.
2. **The tree was clean and watched.** #152 is still open and was observed
   again (finding 5). Criterion 8 passing does not make an *enabled* schedule
   safe; those are different claims.

## Finding 1 — #52 (GL-27) was not auto-eligible, and the size rule is why

The launch prompt named #52 as the likeliest fit, with the caveat to check it.
It fails on two of the conditions:

- It carries `gate: none — defined when the sortie is planned` in its body. The
  labels say `gate:machine`, so `eligible()` would have passed it, but the
  issue itself says the finish line was never decided (R3/R2 in spirit, and the
  `gate:none` invariant in `doctor` cannot see a gate written in prose).
- Its board row names roughly eight unwired bundles, untracked inflow sources
  across three groups, three sidecars with no `key_rgb`, a dead
  `manifest.json`, a stray `desktop.ini` and a bundle with no recorded reason.
  **There is no single test file that proves it done**, and no size bound.
  Under the rule attempt 2 discovered, that is disqualifying.

#160 was chosen instead and satisfies every condition, including the new one:
`tests/test_qops.py`, 4.3 seconds.

This is not a defect, it is the rule working — but it is worth recording that
the rule *did* exclude the first plausible subject, and that the exclusion was
only visible by reading the issue body, not its labels. **Not filed.** The
gap it points at is already PRD P8.1's `ready:auto` size constraint.

## Finding 2 — `qops doctor` can never be clean, because the substrate creates an issue that violates its own invariants

`digest.yml:115` opens the daily status issue with exactly one label,
`qops:status`. `install.issue_invariants()` requires every open issue to carry
exactly one `type:`, one `state:` and one `gate:`, with no exemption. So the
status issue (#164 today, a new one whenever the old is closed) is guaranteed
to produce three permanent `doctor` problems:

```
#164: carries 0 `type:` labels, wants exactly one
#164: carries 0 `state:` labels, wants exactly one
#164: carries 0 `gate:` labels, wants exactly one
```

Two halves of the substrate disagree about what a valid issue is: one *writes*
the issue, the other *rejects* it. The consequence is worse than the noise —
`doctor` clean is a stated gate in this session's own pre-flight and in PRD
P8.4a, and it is unreachable by construction. A gate that can never be green
stops being read, which is how #164's three lines will hide the fourth.

It travels: consumer #2 inherits both halves.

Fix shape: `issue_invariants` skips issues carrying `cfg.ci.status_issue_label`.
It is machine-authored bookkeeping, not a sortie.

Filed as **#167**.

## Finding 3 — `qops guard` misparses the push target, and reads quoted prose as a command

Pre-flight step 2 is "prune the five dead sortie branches, local and remote".
`git push origin --delete <branch>` was refused:

```
[python -m qops guard]: qops guard: push to master is blocked. Open a PR.
```

Root cause, `qops/guard.py:67-72`: the target is read as the last `\S+` after
`git push`, and a token starting with `-` is rejected as a target — at which
point it falls back to `branch`, the *currently checked-out* branch. On
`master`, every `git push` whose last argument is a flag reads as a push to
`master`. `--delete <branch>` puts the branch name last, but `--delete` is
matched by `(?:\S+\s+)?(\S+)` as the target, so the flag wins.

The refspec form `git push origin :<branch>` is not caught and did the job, so
the guard is not a control here — it is a speed bump that a caller routes
around, which is the worst state for a guard to be in. Filed rather than fixed:
whether the parse is tightened or `--delete` is explicitly recognised is a
design call on a file whose whole job is being conservative.

**Second half, found while filing the first.** The `gh issue create --body`
call carrying the paragraph above was itself refused — `qops guard:
force-push is blocked` — because the body *quoted* a force-push inside a code
fence, as documentation. `_FORCE` (`guard.py:19`) matches the whole command
string with no exemption. The tripwire scan four lines below it *has* one, for
exactly this reason ("a commit message that quotes a tripwire is describing the
constraint, not breaking it"); the force and reset rules never got it. So the
substrate cannot document its own git rules through any tool that takes prose
on the command line — and the workaround, `--body-file`, is a path the guard
cannot see into at all. Same fail-open shape as the first half.

Both filed as **#168**.

## Finding 4 — the "dead sortie branches" were merged, not empty, and `produced_work()` cannot tell the difference

The launch prompt and the amended `loops.md` both describe the residue as
"empty refs from failed and merged runs". Measured, all five carried commits:

| Branch | ahead of `master` | PR |
|---|---|---|
| `fix/150-row-advance-reconciler` | 2 | #158 merged |
| `fix/57-gl30b-authoring-time-r2-sync` | 1 | #162 merged |
| `fix/59-orphan-gap-create-intent` | 1 | #148 merged |
| `fix/71-modifier-class-schema` | 1 | #161 merged |
| `fix/pickup-empty-branch-is-not-work` | 1 | #163 merged |

They were **squash**-merged, so the original commits are unreachable from
`master` and `git rev-list master..<branch>` still counts them. Harmless to
prune, and pruned.

The latent defect is in `produced_work()` (`scripts/qops_pickup.py:138`).
It answers "does a branch matching `*/<num>-*` have commits ahead of the
default branch?" — and a squash-merged branch from a *previous* sortie on the
same issue answers yes forever. So an issue that is re-picked after a partial
first pass (released by `release()`, then picked again) will score as having
produced work even if the second session writes nothing, and the claim will
not be released. This is the same defect as #163's, one layer out: #163
replaced "a ref exists" with "a ref has commits", and "a ref has commits" is
still not "this run committed".

It was not exercised today — the tree had no stale `*/160-*` branch — which is
precisely why it is worth filing before it is discovered by a fourth attempt.

Fix shape: record `git rev-parse HEAD` before the launch and require a commit
newer than it, or scope the check to branches created after the claim.

Filed as **#169**.

## Finding 5 — the launch mutates the owner's working tree, observed

Known as #152 (`gate:taste`, open). Recorded here because it was observed
rather than reasoned about: after the sortie exited, this working tree was left
checked out on `fix/160-schema-drift-doctor-guard` with `.qops/state-report.md`
modified. Both were cleaned by hand afterwards, which is a human touch *after*
the criterion was met and does not affect the verdict.

The consequence is the standing one: an *enabled* hourly task depends on the
tree being clean and unattended at every fire, and that is an intention, not a
control. `qops-pickup-loop` stays disabled. **Not filed — #152 is the issue.**

## Finding 6 — two permission rules in `.claude/settings.json` are inert

The launched session printed, before doing any work:

```
Permission allow rule (..\..\..\.claude\settings.json): Write(.planning/*) is
not matched by file permission checks — only Edit(path) rules are. Use
Edit(.planning/*) instead (Edit rules cover all file-editing tools).
Permission allow rule (..\..\..\.claude\settings.json): Write(STATE.md) is not
matched by file permission checks — only Edit(path) rules are.
```

Two grants in the *user-level* settings file that do nothing. Nothing in this
repo needed them, so the sortie was unaffected. Recorded because an inert
permission rule has the same failure shape as an inert `ready:auto`: it reads
like a grant and is not one, and the only reason anyone saw it is that an
unattended run happened to print to a file someone read.

Not this repo's file, and not a sortie. **Not filed** — flagged to the owner.

## Finding 7 — the schema parser silently skips a table declared without `IF NOT EXISTS`

In the merged work. `_CREATE_TABLE` (`qops/install.py`) matches
`CREATE TABLE IF NOT EXISTS <name> (...\n);` only. All 16 tables in
`db/schema.sql` use that form today, so coverage is complete and the tests
pass honestly.

But a future `CREATE TABLE foo (...)` — or one whose closing paren is not
preceded by a newline — is not parsed, not reported, and produces no warning.
A drift *detector* that silently declines to check part of the schema fails in
the same direction as the bug it was written for: quietly.

Small and cheap: assert the count of `^CREATE TABLE` lines equals the number of
tables parsed, and report the difference as a problem.

Filed as **#170**.

## What worked by accident

- **The tree happened to be clean at launch.** Nothing enforces that; the
  pre-flight commit and merge just landed first. Under a scheduled fire it is a
  coin toss (finding 5).
- **The pre-flight PR merged before the sortie branched.** Had it not, the
  sortie would have branched off a `master` without the pruning and the state
  report, and `produced_work()`'s `*/160-*` glob would still have matched — no
  harm today, but the ordering was luck, not design.
- **`gh pr list --search 160`** matched the right PR. That search is a free-text
  number match; on a repo with more history a body mentioning "160" would match
  too. Untested, unexercised, not filed.
