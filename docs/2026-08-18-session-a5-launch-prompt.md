# Session A.5 launch prompt — repair the last inch, then stop

**Claude Code, terminal, repo root. Not Cowork** — needs `gh`.

**Predecessor:** Session A. Sweep applied (#112 closed, 27 issues re-gated, 39
open, 0 `gate:none`), three issues planned and granted `ready:auto` (#59, #57,
#71), and the first unattended sortie ran end to end. Findings:
`docs/2026-08-17-acceptance-run-findings.md`. Issues filed: **#147, #150, #151,
#152, #153**.

**Verified by the owner, 2026-08-18:** `qops-pickup-loop` is **still disabled**
(checked in PowerShell). So #57 and #71 are sitting eligible but nothing is firing
at them. **Do not enable the task in this session.** It gets enabled once the row
advances correctly, and that is a separate decision.

**This session is not Phase 8.** Do not create `qvajda/qops`, do not touch
`qops/` packaging, do not migrate an issue. Session B is
`docs/2026-08-17-session-b-launch-prompt.md` and its P8.0 gate is *this session
having landed*.

```bash
claude --remote-control "qops A.5 - repair the last inch"
```

---

You are repairing the four defects the acceptance run found, plus two the run
exposed indirectly. The run's verdict is worth holding onto: **everything from
claim to merge works unattended, first try.** Nothing here is a rewrite. Every
item is at the last inch — the row that records that a sortie finished.

**Read first, and only these:**

1. `docs/2026-08-17-acceptance-run-findings.md` — the observations. **These are
   findings, not hypotheses. Do not re-run the sortie to reproduce them**; finding
   3's evidence is two PRs on the same workflow file hours apart and it is
   conclusive.
2. `docs/reference/loops.md` — §`pickup-loop` and §`automerge-loop`. You are
   editing both.
3. `docs/adr/0020-auto-merge-green-machine-gated-prs.md` — the decision the
   `advance` job implements, and #128's history: this is the **second** attempt to
   close this leak, so read why the first one missed.
4. `.qops/config.yml` — `labels:`, `ci:`.
5. `docs/2026-08-17-qops-phase8-extraction-prd.md` §Plan P8.1 — where each of
   these lands in the contract freeze. Written, do not re-decide.

## §0 — Repair the live wrong row first

**#59 is on `master` and its issue says `state:building` + `ready:auto`.** Until
that is corrected, `metrics.S9` reports a finished sortie as in-flight and the row
is silently out of the pickup queue. Fix it by hand — `state:done`, drop
`ready:auto` — and **note in the issue that it was corrected manually and why**,
because a hand-corrected row is indistinguishable from a reconciled one otherwise,
and §2's reconciler needs an honest before-state to be tested against.

Then check whether **#115** is in the same shape. The findings doc's conclusion was
that #115 was never a one-off stale row but the first instance of finding 3. If so,
correct it the same way and say so.

## §1 — Owner decisions taken 2026-08-18. Implement, do not reopen.

**Finding 2 — the "requests review" clause is replaced by a digest signal.**
A sortie sets `state:review` on its issue instead of requesting a GitHub review;
`digest.yml` renders those as a waiting-on-you section. Rationale, so you do not
argue with it: GitHub rejects a self-review request and this repo has one
collaborator, so the clause is unsatisfiable; and under ADR-0020 the gate is the
review for `gate:machine` while auto-merge refuses `gate:taste` regardless.
Rewrite the §`pickup-loop` acceptance check in `loops.md` to say what now happens.
`state:review` already exists in the `state:` taxonomy — check before adding it.

**Finding 3 — a scheduled reconciler, not a trigger rewire, not a PAT.**
Rationale: the failure is *an event that was never observed*
(`GITHUB_TOKEN`-raised merges start no new workflow runs), so a mechanism that
reads state beats any mechanism that reacts to events. It also repairs the row
however the PR merged — bot, human, or hand-merge — and it is the only candidate
that would have surfaced #115 unaided. The PAT was rejected: a stored credential
in a public repo cuts against the posture E13a settled on.

Build it as: list merged PRs whose branch names an issue (ADR-0019 already puts
the number there — **do not depend on `Closes #n`**, #116 proved that is a
preference and not a control), read each issue, and where the code is on `master`
but the row is not `state:done`, advance it. Requirements:

- **Idempotent.** It will run against rows `advance` already handled correctly —
  a human-token merge still fires `advance`, as PR #146 showed. Running twice must
  be a no-op. Test this explicitly.
- **It labels; it never closes.** Same limit as `advance` (ADR-0020): a merge means
  the code landed, not that the sortie is judged. Closing stays the owner's.
- **It leaves a state change behind on every skip.** CLAUDE.md's convention: a
  swallowed per-item exception must write a status and a reason, and still fail the
  run once after the loop. A reconciler that silently reconciles nothing is the
  defect it exists to fix, wearing a different hat.
- **Cadence:** align with an existing cron rather than adding a third. `digest_cron`
  is 06:00 UTC daily and the digest is the thing that consumes the result.

Keep `advance` as-is. It works on human-token merges and the reconciler is a
backstop, not a replacement — deleting the fast path to install the slow one
trades latency for nothing.

## §2 — The two the run exposed indirectly

**`.qops/state-report.md` is nine garbage numbers.** `metrics.state_report`
(`qops/metrics.py:359`) shells each row through `bash -lc`; on this host `bash` is
the WSL launcher, which prints *"Windows Subsystem for Linux has no installed
distributions."* to stdout, and the function captures that as the value without
checking the exit code. Session A's close-out wrote that file and nobody noticed,
which is the whole problem — it looks like a table of measurements.

Two fixes, and the second is the one that matters: drop the POSIX assumption
(ADR-0009 says nothing may assume it, and `python: py -3` exists in config so
nothing has to guess), **and** make a non-zero exit fail loudly. Regenerate the
file afterwards and eyeball that the numbers are numbers.

**`qops:status` is referenced but never declared.** `ci.status_issue_label` is read
by `digest.yml:71`/`:75`, and the label is absent from `labels.flags`, so
`qops_import.py` never creates it. That is #136's actual cause — the daily digest
has been failing at 06:00 UTC on a missing label, not on anything in its logic.
Add the label to the taxonomy, create it, and add the assertion in §3.

## §3 — #147's invariants

#147 is the `qops doctor` label-invariant assertion, already carrying the
scope comment from finding 1. Three checks, all cheap, each one the machine version
of something a human got wrong this week:

1. Every open issue carries exactly one `type:`, one `state:`, one `gate:`, and no
   `gate:none`. (The sweep's step-4 assertion — the plan is explicit that this
   does not belong in a human's eyes.)
2. **No `ready:auto` on an issue that is not `state:planned`.** Finding 1: such a
   flag is inert *and invisible*, reads as a filled queue, and is most of why the
   backlog looked like it was starving. #136 is in this state right now.
3. Every label named anywhere in `.qops/config.yml` appears in the `labels:`
   taxonomy. This is the `qops:status` check.

## §4 — Close out

- `python -m pytest -q` green. New tests for: reconciler idempotency, the
  non-POSIX metrics path, the exit-code failure, and each §3 invariant.
- `python -m qops doctor` clean.
- `python -m qops metrics --state` — and **read the output this time.** If any row
  is not a number, §2 is not done.
- Close #150–#153 as their fixes land; leave #147 open if any invariant is
  deferred, with the reason on the issue.
- A ledger checkpoint usable as a handoff into Session B: which findings are
  closed, whether the reconciler has been observed working on a real merge, and
  the state of #59/#115/#136.

**Then stop.** Do not enable `qops-pickup-loop`, do not start Phase 8. The next
decision after this session is whether the row now advances on its own — and the
honest way to answer it is a second unattended sortie on #57 or #71, which is a
separate session with the owner watching.
