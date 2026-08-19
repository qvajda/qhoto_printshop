# Attempt 3 launch prompt — criterion 8, watched, once

**Claude Code, terminal, repo root. Not Cowork** — needs `gh`.

**This session exists to answer one question:** does a sortie now go from pickup
to `state:done` with no human touch in between? Criterion 8 of the Phase 8 PRD.
It is **0 for 2** — attempt 1 (#59) worked through the merge and broke at
row-advance; attempt 2 (#57, #71) broke earlier and never reached a PR. Both
fixes were correct. Each time the next unexercised inch failed, which is why
this is a session of its own and not a step inside Session B.

**State, verified 2026-08-19:**

- `qops-pickup-loop` is **disabled** — the owner disabled it manually after the
  two sorties. **Leave it disabled.** See §1 for why the launch is manual.
- #163 landed the empty-branch fix (`produced_work()` counts commits ahead of
  `default_branch`, still accepting a PR as evidence) plus four tests. **It has
  never been exercised by a real sortie.**
- The scheduled-task wiring **is** proven: the loop fired on time, twice, at
  19:23 and 20:23 on 2026-08-18. That question is closed and needs no retest.
- Residue: seven unmerged branches, five of them dead sortie branches
  (`fix/57-…`, `fix/71-…`, `fix/59-…`, `fix/150-…`, `fix/pickup-empty-branch-…`)
  plus two `no-issue/` ones. `state-report.md` is uncommitted and behind HEAD.

**Read first, and only these:**

1. `docs/reference/loops.md` §`pickup-loop` — including the 2026-08-19 amendment,
   which is the record of what attempt 2 did.
2. `scripts/qops_pickup.py` — `eligible()`, `produced_work()`, `release()`.
   **Read the actual conditions.** Attempt 1's subject was chosen without doing
   this and was structurally unpickable.
3. `docs/2026-08-17-qops-phase8-extraction-prd.md` — criterion 8 and P8.0.
4. `docs/2026-08-17-triage-sweep-plan.md` §The rules — R5, R6, R7 govern subject
   selection.

**Do not read** the acceptance-run findings or A.5's prompt. They are closed and
their fixes are in; re-reading them invites re-litigating decisions.

```bash
claude --remote-control "qops attempt 3 - criterion 8"
```

## §0 — Pre-flight

1. Tree clean. Regenerate `.qops/state-report.md` (`python -m qops metrics --state`)
   and commit it — it currently reads `measured-at: 57e898c`, two commits stale.
   **Read the values**: if any row is not a number, A.5's metrics fix regressed
   and this session stops here.
2. **Prune the five dead sortie branches, local and remote.** They are empty refs
   from failed and merged runs. `produced_work()` now counts commits so they are
   harmless to the logic, but they are noise in `git branch --no-merged` and
   Phase 8's criterion 3 wants a quiet tree. Leave
   `remotes/origin/feat/gl6-scene-library` alone — it is not sortie residue and
   not yours to judge.
3. `python -m pytest -q` green. `python -m qops doctor` clean.
4. Confirm `qops-pickup-loop` is still disabled before doing anything else.

## §1 — The instrument: manual `--launch`, not the scheduler

Run `python scripts/qops_pickup.py --launch` by hand, at a moment you are watching.
Reasoning, so you do not "improve" on it: the scheduled path is already proven, so
firing on a cron buys nothing this session needs, and it costs observation — an
hourly task can fire at a moment nobody is reading, which is how attempt 2's
silence lasted as long as it did. **#152 (worktree isolation) is still open**, so
the launch mutates this working tree; a watched manual run is how that stays
bounded until #152 is decided.

Dry-run first (`without --launch`), confirm the pick, then launch.

## §2 — Choosing the subject

The queue is drained: #57, #59 and #71 are done, so **there may be nothing
eligible**. Selecting and planning the subject is most of this session's work, and
it is judgement — do not rush it to get to the interesting part.

Print your candidate and your reasoning, and **get the owner's confirmation before
granting `ready:auto`.** That flag is the owner's alone (`.claude/agents/triager.md`).

Conditions, all of which must hold:

- `state:planned` — R7. `eligible()` reads it, and a `ready:auto` on anything else
  is inert and invisible (finding 1). This is the condition attempt 1's named
  subject failed.
- `gate:machine`, and honestly so. R3: when unsure, `gate:taste`.
- No `no-auto`, not `type:manual` (R5 — retype to `type:code` if it is scriptable
  rather than relabelling around it).
- **Nothing touching Etsy publish, Gelato product-create or Replicate** (R6).
- **New, and the constraint attempt 2 discovered:** the change must be provable by
  the tests it *touches*, in well under a minute. The full suite is ~3m33s, longer
  than one Bash call may run, and a `claude -p` process exits with its turn — so a
  sortie that needs the whole suite as its evidence cannot finish, by construction.
  `test.yml` is the full-suite gate and it runs on the push. **If you cannot name
  the specific test file that proves the issue done, the issue is not auto-eligible
  — pick another.**
- Prefer a subject that is **not** `mission:qops`, so Phase 8's P8.5 migration set
  does not change underneath the extraction.

**#52** (GL-27, asset and doc hygiene) is the likeliest fit and was held in the
sweep only because its scope was never written down. Writing that scope is
legitimate work for this session. Check it against every condition above rather
than taking this as a recommendation — particularly the size rule, because "doc
hygiene" can quietly mean a hundred files.

Write the plan **into the issue**: what done looks like, which files, which test
proves it. An unattended sortie reads the issue and nothing else.

## §3 — The run

Launch, then **do not intervene.** No fixing its branch name, no committing on its
behalf, no re-running its tests. If it stalls, let it stall and record that.

Watch for, and write down:

| Inch | What proves it |
|---|---|
| Claim | `state:planned` → `state:building` **before** the launch |
| Work | ≥1 commit ahead of `master` on `<type>/<issue#>-<slug>` |
| PR | opened, body carries `Refs #<n>` |
| Gate | `test`, `gate`, `tripwires`, `doc-links` all green |
| Merge | `automerge-loop` enables native auto-merge; required checks merge it |
| Row | `state:done`, `ready:auto` dropped |

For the last row, do not wait for 06:00 UTC — `gh workflow run digest.yml` forces
the reconciler on demand.

**`state:review` is deliberately absent from that table.** `automerge.yml` sets it
only on the *non*-`gate:machine` path — the branch that stops with "the owner
merges this one" — so on a `gate:machine` sortie it is correctly never set. #151 is
working when the label does **not** appear here. Do not read its absence as a
defect and do not add it to the sortie's instructions; the whole point of #151 was
that the signal is set by the workflow rather than asked of the agent (GL-53).

## §4 — Reading the result. Three outcomes, and do not blur them.

- **Pass.** Every inch above, no human touch between launch and reconcile.
  Criterion 8 is met on this repo and Session B's gate is cleared. Say so plainly.
- **Loud failure.** The sortie fails but `release()` fires: `state:building` →
  `state:planned` with a comment saying why. **This is #163 working and criterion 8
  still failing.** Both halves are true and the report must say both — scoring it
  as a pass because the guard worked is precisely the error attempt 2 made in the
  other direction.
- **Silent failure.** Anything left in a wrong state with nothing saying so. This
  is the serious outcome. It means the loop has a third unexercised inch, and the
  recommendation that follows is **a design pass on the unattended path before
  extraction** — not a fourth patch. Two consecutive point-fixes that each
  revealed the next defect is evidence about the method, not just the code.

**Do not repair anything in flight**, whatever happens. Every finding this project
has that was worth having came from writing it down first
(`docs/reference/loops.md` §Audit).

## §5 — Close out

- Findings in `docs/2026-08-19-attempt-3-findings.md`, same shape as the
  acceptance-run doc: what was observed, in order, then one section per finding.
  Include anything that worked by accident.
- File one issue per finding. Do not fix them here.
- `python -m qops metrics --state`, `qops doctor`, `pytest -q`.
- A ledger checkpoint stating **which of the three outcomes** occurred, and
  therefore whether Session B is cleared. Session B reads checkpoints; A.5's said
  "do not enable the loop" and was overtaken by events, so make this one accurate
  about what was actually decided.

**Then stop.** Do not enable `qops-pickup-loop` — leaving it on is a standing
arrangement that depends on the tree being clean at every fire, which is an
intention and not a control until #152 lands. Do not start Phase 8; that is
`docs/2026-08-17-session-b-launch-prompt.md`, and whether it may start is the
output of this session, not an assumption of it.
