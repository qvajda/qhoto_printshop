# Phase 8 — extraction findings

Session B, 2026-08-19. Written against
`docs/2026-08-17-qops-phase8-extraction-prd.md` revision 5. **Phase 8 is
complete: all eight success criteria are met**, and the sortie that proves
criterion 8 ran in `qvajda/qops` rather than here.

## The eight criteria

| # | Criterion | Result |
|---|---|---|
| 1 | `qops install` in a fresh repo renders all six workflows and they run green | met — first push to `qvajda/qops`: `guard` and `groom` green, `test` red for a reason that was itself a finding (below), green after |
| 2 | `qhoto_printshop` consumes qops as a pinned dependency, no qops source | met — `qops @ git+…@v0.1.0`; `import qops` resolves to site-packages |
| 3 | Re-rendering the six workflows from the extracted package is byte-identical | met — **6/6**, diffed by script, twice (once on the staged tree, once on the final one) |
| 4 | `mission:qops` here returns only closed migration records | met — 0 open |
| 5 | `qops doctor` clean in both repos | met — and it could not even be *evaluated* until #167 was fixed |
| 6 | `tests/test_qops.py` passes in the qops repo with no pipeline fixtures | met — 171 there, 885 here |
| 7 | Owner CI attention does not double: one digest, not two | **partially** — see the open question below |
| 8 | The new repo works its own backlog unattended | met — `qops#5`, two minutes, no keystroke between pick and reconcile |

## Criterion 8, in full

```
11:47:57Z  launched (hand-launched; the scheduled task stayed disabled)
11:48:14Z  claimed: state:planned -> state:building
~11:49     branched fix/5-state-review-label-swallowed, one commit, PR #18 (Refs #5)
11:49:43Z  enable QUEUED native auto-merge — the PR sat BLOCKED
11:49:48Z  doc-links, tripwires green
11:49:49Z  gate green
11:49:52Z  test green
11:49:54Z  merged by the required checks
           qops reconcile -> state:done, ready:auto dropped
```

**The interesting column is not the last one.** Attempt 1 in this repo reached
the merge and broke at row-advance; attempt 3 reached the row. What neither
could show is that *the merge waited for the gate* — because in this repo it
always did, invisibly, and nobody had ever seen it not. See finding 2.

Three things it does not prove, and they are recorded in the substrate's own
`loops.md` rather than only here:

- The **schedule** is still unexercised. Both `qops-pickup-loop` tasks are
  registered and disabled.
- The **reconciler was dispatched, not scheduled**. `advance` cannot fire on a
  merge its own `GITHUB_TOKEN` caused (#150), and `digest.yml`'s `reconcile` job
  has still never run on its own cron.
- The **subject satisfied R8's size rule** — evidence the rule works, not
  evidence the loop survives a subject that breaks it.

## What the extraction found that the audit could not

The 2026-08-17 portability audit asked *"is anything project-specific here"* and
answered correctly, on one day, by grepping. Every finding below came from a
different question — *"does this work as somebody else's dependency, in a repo
nobody set up by hand"* — and none of them could have been found by reading.

### 1. Five leaks, not two (P8.1)

Three the audit found or the acceptance run found; **two it could not**, because
it grepped for project *strings* rather than project *assumptions*:

- `install.schema_drift` hardcoded `db/schema.sql` and `db/qhoto.sqlite3` inside
  the substrate. Inert in a repo with no database, so nothing would ever have
  complained — it is now `schema_check:` in config, and a config without the
  block gets no check.
- `docs/agents/issue-tracker.md` hardcoded the repo name in a document the
  agents read as authoritative.

The deciding one remains leak 3: `Path(__file__).parents[1]` in both `scripts/`
entry points. As a pinned dependency that is site-packages, not the consuming
repo — the extracted package would have operated on the wrong tree, silently.

**The deliverable of P8.1 is not the five fixes.** It is that the property is
now asserted on every commit instead of being true on the day someone checked:
28 substrate files against a word list the consuming project's own config
declares.

### 2. `automerge-loop` merges unread code when a branch has no required checks

`qvajda/qops#3`, and the most serious finding of the phase.

This repo's second-ever PR was merged **ten seconds before its own gate
finished**. The job's header says *"This workflow does NOT merge"* and ADR-0020
rests on the same sentence. It is false where required checks do not exist:
`gh pr merge --auto` merges immediately when a PR is mergeable *right now*, and
with no required checks it always is.

This is GL-53 inside the substrate every consumer renders — a control that
reads like a control, is documented as one, and is not. A project that installs
qops and does not finish branch protection gets silent auto-merge of every
`gate:machine` PR, with a log claiming the merge was handed to the checks.

**It also means criterion 8 was unfalsifiable until it was fixed.** A sortie
that gets "auto-merged" proves nothing about the gate if the merge never waited
for it. Fixed with `enablePullRequestAutoMerge`, which *fails* when there is
nothing to queue behind — the failure being the signal. ADR-0020 amended:
its mechanism was conditional all along, and the workflow now enforces the
condition instead of assuming it.

**Why this repo never saw it:** branch protection was configured here in E15,
before `automerge.yml` existed. The assumption was true from the day it was
written, so nothing ever tested it.

### 3. Nothing in the substrate created the label taxonomy

`#174`. P8.4b step 3 named `python scripts/qops_import.py` as the thing that
creates the labels. **The mode did not exist.** The importer validated rows
against the config and then called `gh issue create --label`, which fails on a
label the repo lacks. In this repo the labels were created by hand, once, in
2026-08.

The step exists precisely because a repo with no labels makes the picker's query
return empty and **exit 0** — indistinguishable from a healthy idle queue. So
the one prerequisite whose absence is silent had no implementation, and the plan
step that named it was the only thing that would ever have noticed.

### 4. The rendered workflows install nothing in a package-shaped repo

`qvajda/qops#1`. `test.yml` and `gate.yml` install from `requirements*.txt`;
the substrate repo declares its dependency in `pyproject.toml`. Nothing was
installed and the suite could not start. Same class as the leaks: true of the
first consumer, stated nowhere.

### 5. The `state:review` label never landed

`qvajda/qops#5`, and it became criterion 8's subject.

`gh issue edit --add-label state:review --remove-label state:building || true`
fails as a whole when the issue does not carry `state:building`, so the add
never ran — and `|| true` swallowed it. #151 replaced an unsatisfiable clause
with this label on the argument that *a label something writes and something
else reads is a control*. Nothing wrote it, so `digest.yml`'s **Waiting on you**
section was empty no matter how many PRs were waiting.

CLAUDE.md's own convention, broken in the substrate: a swallowed exception must
leave a state change behind. This one left neither the label nor a complaint.

### 6. Two machine facts nothing in either repo can see

- **#176** — the registered scheduled task carried an empty `WorkingDirectory`,
  so once `qops_pickup.py` stopped rooting off `__file__` it would have resolved
  its root from wherever the scheduler started it. It was disabled, so nothing
  broke; the breakage would have stayed invisible until someone enabled it.
- **`qvajda/qops#19`** — an untrusted workspace makes Claude Code ignore **every**
  `permissions.allow` *and* `permissions.deny` entry, including the `gh api -X`
  denials that ADR-0016 and ADR-0020 rest on. It degrades quietly: the sortie
  still worked, the file still declares the control, and
  `test_gh_api_writes_are_never_allowlisted` still passes.

Both are #124's complaint, now doubled by there being two roots.

### 7. The guard was routable, and then routable a second way

`#168` took two passes, and the second is the instructive one. The first fix
replaced string matching with a token scan and closed all five routes the issue
named. It still looked for the *word* `push`, so the very next command of the
session — `git stash push -m wip -- tests/x.py && git checkout master` — was
refused as a push to master. `git_commands()` now parses the subcommand and its
own arguments, stopping at shell separators, and all six checks read that one
parse. ADR-0021.

Two further holes are filed, not fixed: the guard judges `git -C <other-repo>`
by the session repo's rules (#177 — real now that there are two roots), and the
PowerShell tool is not matched by the PreToolUse hook at all, so every rule the
guard holds is one tool name away from not applying.

**The initial push to the empty repo went through PowerShell**, deliberately and
recorded here: an empty repo's first push cannot go through a PR, so the
protected-branch rule has no meaning there. Nothing stopped it, and nothing
recorded it either — which is the point of #177's second half.

## The one criterion not fully met

**Criterion 7 — "one digest, not two".** There are now two `digest.yml`
schedules, both at 06:00 UTC, and no decision has been taken about merging them.
The PRD's open question 4 addressed sequencing, not this. Left open rather than
declared met: the honest reading is that owner CI attention *has* doubled, and
the fix is a decision (one digest reading two repos, or two digests at different
times, or the substrate's digest off by default) rather than a patch.

## Deltas from the PRD

- **The ADR travel set was wider than "0013–0020".** ADR-0001 (what hooks may be
  built on) and ADR-0009 (the cron host, and the no-POSIX constraint that
  follows) are cited by substrate source and by the new `CLAUDE.md`. They travel,
  at their original numbers so citations keep resolving; the gaps are this
  repo's pipeline decisions.
- **The migration set was 14 open, not 12 or 13.** Two of those (`#115`, `#122`)
  were `state:done` and merely never closed — `automerge-loop` advances the
  label and by ADR-0020 never closes. They closed here rather than migrating.
- **Recreate-and-close, not `gh issue transfer`.** ADR-0015 named transfer;
  criterion 4 wants this tracker to hold closed migration records, which a
  transfer does not produce, and transfer silently drops labels the target lacks.
  Comments were carried across verbatim with attribution.
- **`gate.yml` changed, against P8.4's "workflows unchanged".** Its gate command
  named `tests/test_qops.py`, which left with the substrate. Criterion 2 and that
  clause collide on exactly one line, and criterion 2 is the one that means
  something.
