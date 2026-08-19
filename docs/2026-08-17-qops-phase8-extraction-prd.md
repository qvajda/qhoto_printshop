# PRD — Phase 8: extract qops into its own repo

Status: **draft, awaiting owner sign-off.** No work starts until signed.
Written against the owner's instruction of 2026-08-17 ("full extraction now").

**Revision 5, 2026-08-19.** Attempt 3 **passed** — criterion 8 is met on this repo,
first try, unattended, every inch observed
(`docs/2026-08-19-attempt-3-findings.md`; ledger checkpoint `attempt-3`). P8.0 is
therefore satisfied and **Session B may start.** The run filed four new substrate
defects, and two of them are publication blockers rather than patches: **#167**
(`digest.yml` writes a status issue that `issue_invariants` rejects, so `doctor`
can never be clean — criterion 5 is unevaluable until it is fixed) and **#168**
(`qops guard` reads a flag as the push target and falls back to the checked-out
branch, so `git push origin :<branch>` routes around it; and `_FORCE` has no
prose exemption, so the substrate cannot document its own git rules through any
tool taking prose on the command line). Both become **P8.1 exit criteria**, and
**P8.2's pre-authorisation is now conditional on them** (owner, 2026-08-19).
**#169** (`produced_work()` still answers a question about the repo rather than
about this run — a squash-merged branch from a previous sortie on the same issue
scores as work forever) and **#170** (the schema parser silently skips a table
declared without `IF NOT EXISTS`) migrate as open issues under P8.5.

**Revision 4, 2026-08-19.** The second unattended attempt (#57, #71) failed at an
earlier inch than the first: both sorties backgrounded the full test suite, ended
their turn waiting for a notification a `-p` run cannot receive, and left bare
branches that `produced_work()` scored as successes. Fixed in #163, unexercised.
Changes: **P8.0 now requires criterion 8 observed once on this repo** (attempt 3),
and P8.1 gains the `ready:auto` size constraint — the eligibility rule attempt 2
discovered, which currently exists only as launch-prompt prose.

**Revision 3, 2026-08-18.** Written against the acceptance run's findings
(`docs/2026-08-17-acceptance-run-findings.md`). The run proved every step from
claim to merge works unattended first try, and that the substrate's last inch —
the row that says a sortie finished — does not. Three of the four findings are
substrate defects and therefore travel. Changes: **P8.0 now requires Session A.5**,
P8.1 gains a fourth leak (`bash -lc` in `metrics.state_report`), the undeclared
`qops:status` label, four tests in place of two, the row-advance reconciler and the
rewritten `pickup-loop` acceptance check; criterion 8 no longer stops at the merge.

**Revision 2, 2026-08-17.** Answers the owner's question "will qops in its own
repo be able to use its own automated way of working to continue tackling the
open issues?" As drafted, no — the substrate was portable but the *runtime* was
not, and no success criterion tested for it. Six gaps closed: criterion 8 added,
the pickup runtime moved out of §Scope-out, P8.1 gained a third leak and the
empty-tripwire test, **P8.4b** is new, two risk rows added, and P8.0's stale
acceptance-run clause is struck. **P8.2 is pre-authorised** by the owner in the
same exchange — creating `qvajda/qops` public no longer stops for a go-ahead. The
one irreversible act inside it stays flagged: a public repo cannot be made
un-public in the eyes of anyone who cloned it, and its licence choice is a
one-way door for contributions.

## Problem

`qops` is a general ways-of-working substrate — brief, ledger, guard, install,
doctor, metrics, the label taxonomy, the agent roster, three native skills, six
rendered workflows — and it lives inside the repo of the one project it happens
to serve. Three costs follow:

1. **The shop's tracker is no longer the shop's.** ADR-0015 decided qops's work
   leaves this repo and set an interim: qops issues stay here carrying
   `mission:qops`. When that ADR was written the migration query returned
   nothing. **Today it returns 12 open issues** — the interim has become the
   arrangement.
2. **Shared CI and shared hot path.** `test/gate/guard/groom/digest/automerge`,
   `.claude/`, `skills-lock.json` and the 150-line CLAUDE.md cap all serve both
   concerns at once, so a qops change and a pipeline change contend for the same
   green build.
3. **No second consumer can exist.** Phase 8's actual object — meta-orchestration
   across projects — is unreachable while the substrate is a subdirectory of one
   project.

**Amended 2026-08-17 (owner):** consumer #2 is no longer hypothetical. New
projects start within days, and `myThirdwheel` is the named integration target.
This removes the "packaging cost for one user" objection that the Phase 7
sign-off rested on — and it moves the deadline. **The extraction is now paced by
the first new project, not by the acceptance run:** a project started before the
package exists will copy `qops/` and `.qops/` by hand, and two divergent
substrates with no merge path is a materially worse outcome than extracting one
week early. P8.1 and P8.2 become the critical path.

## What the portability audit says (measured 2026-08-17)

Better than expected. The split is packaging, not a rewrite:

- `qops/*.py` (1,124 lines across 9 modules): **zero** project-specific strings.
- `.github/workflows/*.yml` contain `qvajda/qhoto_printshop`, but every one is
  headed `RENDERED BY 'qops install' from qops/templates/... + .qops/config.yml`.
  Generated output, not source.
- **Two real leaks only:** `qops/templates/guard.yml.tmpl:29` names Gelato in a
  comment, and `tests/test_qops.py` carries `etsy`/`replicate` fixture strings.
- `.qops/config.yml` is, as designed, the single project-specific surface.

Phase 7's portability proof therefore holds by measurement. Technical risk is low;
the real cost is workflow, in §Risks.

**Amended 2026-08-17 — what the audit measured, and what it did not.** The audit
asked "does anything project-specific exist outside `.qops/config.yml`". It did
**not** ask "can the extracted substrate run its own backlog autonomously", and
the two are different questions. Four findings from a second pass:

- **The CLI is portable by construction, better than the audit claimed.**
  `qops/__main__.py:43` resolves the repo through `config.find_root()` — the
  nearest ancestor holding `.qops/config.yml`. Installed as a package in any
  repo, every verb finds the right root from cwd.
- **The two `scripts/` entry points are not.** `scripts/qops_pickup.py:30` and
  `scripts/qops_import.py:28` derive `ROOT` from `Path(__file__)`. Once qops is a
  pinned dependency that root is site-packages, not the consuming repo. This is a
  third leak the audit missed because it grepped for project *strings*, not for
  project *rooting*.
- **The pickup runtime is a per-machine registration, not a file.** The loop is a
  Windows scheduled task (`qops-pickup-loop`, disabled — `docs/reference/loops.md`),
  bound to one root. Copying `qops_pickup.py` into a new repo copies the picker
  and not the thing that fires it.
- **`qops doctor` has unconditional preconditions.** `install.doctor` reads
  `CLAUDE.md` (`install.py:151`), requires `.claude/settings.json` to invoke qops,
  and `skill_drift` (`install.py:109–137`) asserts installed skills == declared
  and demands a `skills-lock.json` ref per external. A fresh repo satisfies none
  of these, so criterion 5 is not free.

Consequence for the plan: criterion 1 proves *packaging*. It does not prove
*autonomy*, and until 2026-08-17 nothing in this PRD did — see criterion 8 and
P8.4b.

## Success criteria

Measurable, checked in this order:

1. `qops install` in a **fresh** repo containing only `.qops/config.yml` renders
   all six workflows and they run green.
2. `qhoto_printshop` consumes qops as a pinned dependency; **no qops source in
   this repo** beyond `.qops/config.yml`.
3. Re-rendering the six workflows from the extracted package produces output
   **byte-identical** to what is on disk today. This is the acceptance test for
   the move itself.
4. `gh issue list --label mission:qops --state all` here returns only closed
   migration records; all live qops issues exist in the qops repo. **The count is
   read at migration time, not from this document** — the 2026-08-17 triage sweep
   retypes #49 from `mission:post-launch` to `mission:qops`, so the set is 13 if
   that sweep has landed and 12 if it has not. P8.5 re-runs the query rather than
   trusting either number.
5. `qops doctor` clean in both repos. In the new repo this requires its own
   `CLAUDE.md`, its own `.claude/settings.json` invoking qops, and a `skills:`
   block declaring **native-only** — the seven external skills are model and
   image tooling with no use in a substrate repo, and `skill_drift` fails on a
   declared-but-absent native or a lock entry outside the declared set.
6. `tests/test_qops.py` passes in the qops repo with no pipeline fixtures; this
   repo retains only its own tripwire/guard tests.
7. Owner CI attention does not double: one digest, not two (see open question 4).
8. **The new repo works its own backlog unattended.** An issue in `qvajda/qops`
   carrying `state:planned` + `ready:auto` + `gate:machine` is picked by
   `pickup-loop`, branched, committed, opened as a PR, and auto-merged by
   `automerge-loop` with no owner keystroke between pick and merge. This is the
   criterion that makes the extraction worth doing rather than a filing exercise,
   and it is the only one that exercises the runtime rather than the package.
   Its preconditions are P8.4b's checklist.
   **Amended after the 2026-08-17/18 acceptance run:** "auto-merged" is not the
   end of the criterion. The sortie's issue must reach `state:done` with
   `ready:auto` dropped — the run proved every step up to the merge works and the
   row-advance does not (finding 3). A criterion that stops at the merge would
   have scored that run as a pass.

## Scope

**In:** `qops/` package + `qops/templates/`, `scripts/qops_import.py`,
`scripts/qops_pickup.py`, `tests/test_qops.py`, `.claude/agents/*` (6 roles), the
three native skills (`interview`, `spec-to-issue`, `triage`), `skills-lock.json`,
the enforcement hooks, the label taxonomy + importer, ADRs 0013–0020, `docs/agents/`.

**Out:** `.qops/config.yml` (stays with each project, by design); the tripwire
list (those are *pipeline* constraints — Gelato, FLUX licence, placeholder
template ids — and must not travel); pipeline ADRs 0001–0012; the seven external
skills (reinstallable, tracked by `skills-lock.json`); **any rewrite of this
repo's git history** (closed decision); qrchardist / meta-orchestration itself —
Phase 8 *enables* it, it is not the deliverable.

**Moved out of "Out" on 2026-08-17 — the pickup runtime.** This list previously
excluded "the Windows scheduled tasks (ADR-0009)" wholesale, which quietly
excluded the only thing that makes the substrate autonomous. Corrected split:

- **Stays here:** the pipeline's own scheduled tasks — the two cron cadences of
  ADR-0005, the Telegram listener. Those are shop runtime and never travel.
- **Travels, and must be re-registered per repo:** `qops-pickup-loop`. The task
  binds to a single repo root, so a second consumer needs either its own
  registered task or one task taking a repo argument. Neither exists today.
  Built in P8.4b; ADR-0009 gets amended, because "the cron host is the local
  Windows desktop" now has to say *how many roots* that host serves.

## Constraints

- **No history rewrite.** The extraction therefore copies files into a fresh
  initial commit and records provenance in the new repo's README, pointing at
  source commits here. No `filter-repo`, no subtree surgery on this repo.
- **Subscription-only, no API billing.** Distribution must not need hosted infra
  or LLM-node billing (the reason n8n was rejected).
- **ADR-0012 keeps this repo public.** The new repo inherits that decision
  explicitly or amends it — it does not get to be silent.
- **ADR-0009: the cron host is the local Windows desktop.** Hooks invoke `py -3`.
  Nothing in the extracted package may assume POSIX.
- **Owner-facing asks are capped at one page**, four options, one recommendation
  (Phase 7 sign-off item 9). This PRD's open questions obey it.

## Plan

Each phase is independently revertible; each ends in a checkable state.

- **P8.0 — prereq gate.** The dirty tree (#142 follow-up) is committed and #142 is
  closed. **Added 2026-08-19: criterion 8 has been observed once on *this* repo**
  — `docs/2026-08-19-attempt-3-launch-prompt.md`. **Satisfied, 2026-08-19:
  attempt 3 passed on #160, first try, every inch, no human touch between the
  launch and the reconcile** (`docs/2026-08-19-attempt-3-findings.md`). This
  clause is met and **P8.0 no longer blocks on it**; the design pass held in
  reserve below is not needed. Two qualifications travel with the pass: it is
  one observation on a subject that satisfied the size rule — which is evidence
  the rule works, not that the loop survives a subject that breaks it — and the
  run was manual and watched with `qops-pickup-loop` disabled, so it says
  nothing about an enabled schedule (#152). Four findings filed. ~~none
  blocking~~ — **corrected by the owner, 2026-08-19:** #167 and #168 are P8.1 exit
  criteria and P8.2 is gated on them (see revision 5). The attempt-3 session
  scored all four as non-blocking because none of them blocks *this repo*; two of
  them block **publishing the substrate**, which is a different question and not
  one that session was asked. #169 and #170 do migrate as open issues.
  The record of the two failures follows.
  It was 0 for 2: attempt 1 (#59)
  worked through the merge and broke at row-advance; attempt 2 (#57, #71) broke
  earlier and never reached a PR, and `produced_work()` scored both bare branches
  as successes. Each fix was correct and each time the next unexercised inch
  failed. Extracting an unattended path with that record hands consumer #2 a
  substrate whose core mechanic has never completed, and the failures are cheap to
  find here and expensive to find in a public repo two projects depend on. **If
  attempt 3 fails silently, the recommendation is a design pass on the unattended
  path before extraction, not a fourth point-fix** — two consecutive fixes that
  each revealed the next defect is evidence about the method.
  **Added 2026-08-18: Session A.5 has landed** — PR #158, merged 17:36 UTC. It
  closed #150 (the reconciler), #151, #153, #147 and #136; #152 (finding 4,
  worktree isolation) is `gate:taste` and stays open. The reconciler was
  observed advancing a real merge and found #122 unaided. Two things it did
  NOT prove: the `digest.yml` `reconcile` job has never fired on its
  schedule, and no digest has run since `qops:status` was created — both are
  read from one 06:00 UTC run. Source:
  `docs/2026-08-18-session-a5-launch-prompt.md`. The acceptance run found four
  defects in the substrate's *last inch*, and three of them travel. Extracting
  first means fixing them in two repos or back-porting from the new one; both are
  worse than a half-day here. This is a prereq on the substrate's correctness, not
  on the acceptance run's existence — which is the distinction the struck clause
  below got wrong.
  ~~and the Phase 7 acceptance run has happened~~ — **struck 2026-08-17:**
  this clause contradicted open question 4, which resolves the acceptance run to a
  parallel qhoto-repo experiment and explicitly not a gate on packaging. OQ4 is
  the later decision and carries the owner amendment; this clause was residue from
  the pre-amendment draft.
- **P8.1 — freeze the contract.** Document the config schema and the CLI
  contract. Fix the leaks — now **three**, not two: `guard.yml.tmpl:29`'s Gelato
  comment, `tests/test_qops.py`'s `etsy`/`replicate` fixtures, and the
  `Path(__file__)` rooting in `scripts/qops_pickup.py:30` +
  `scripts/qops_import.py:28`, which both move to `config.find_root()`. Add a
  portability test that fails on any project-specific string outside
  `.qops/config.yml`, so the property is enforced rather than measured once. Add
  a test that `qops guard scan` exits 0 against an **empty** `tripwires:` list —
  the substrate repo has no tripwires, that path has never been exercised, and a
  crashing guard job fails every build in the new repo on day one.

  **FIXED in PR #158; this paragraph is the record, not the task. A fourth
  leak, found by the acceptance run (2026-08-18) and not by the
  audit.** `metrics.state_report` shells its nine rows through `bash -lc`
  (`qops/metrics.py:359`) and captures stdout without checking the exit code. On
  the ADR-0009 cron host `bash` resolves to the WSL launcher, so every value in
  `.qops/state-report.md` currently reads *"Windows Subsystem for Linux has no
  installed distributions."* — nine garbage numbers in a table that looks fine,
  and the file is untracked so CI never saw it. Two fixes, not one: the POSIX
  assumption (exactly the ADR-0009 constraint in §Constraints — the audit missed
  it because it grepped for project *strings*, not platform assumptions), and the
  swallowed non-zero exit, which is CLAUDE.md's `try/except: continue` convention
  applied to a subprocess.

  **A label the taxonomy never declares. FIXED in PR #158.** `ci.status_issue_label: 'qops:status'`
  is read by `digest.yml:71`/`:75` but is absent from `labels.flags` in
  `.qops/config.yml`, so `qops_import.py` never creates it and the daily digest
  has failed at 06:00 UTC ever since. That is #136's real cause, and it is a
  substrate defect — the new repo reproduces it at P8.4b step 3.

  **Four new tests**, replacing the two above:

  1. No project-specific string outside `.qops/config.yml`.
  2. No module assumes POSIX — no `bash`, no `sh -c`, no hardcoded `/`
     interpreter. `python: py -3` exists in config precisely so nothing else has
     to guess.
  3. `qops guard scan` exits 0 against an **empty** `tripwires:` list.
  4. Every label named anywhere in `.qops/config.yml` appears in the `labels:`
     taxonomy. Cheap, and the assertion that would have caught `qops:status`.

  **`ready:auto` carries a size constraint, and it must stop being prose
  (2026-08-19).** Attempt 2 discovered it the hard way: the full suite is ~3m33s,
  longer than a single Bash call may run, and a `claude -p` process exits with its
  turn — so a sortie whose evidence of doneness *is* the full suite cannot finish,
  by construction. #163's countermeasure is half a control (`produced_work()`
  counts commits, so the failure is now loud) and half a launch-prompt
  instruction — and by GL-53 an instruction in a prompt is a preference. So the
  eligibility rule is real, load-bearing, and currently written down nowhere
  checkable: **an issue is auto-eligible only if a named test file it touches
  proves it done.** Two things before the contract freezes: state it as a triage
  rule alongside R5/R6/R7, and get as close to an assertion as the substrate can —
  at minimum `qops doctor` flagging a `ready:auto` issue whose plan names no test.
  This travels: consumer #2 otherwise inherits an eligibility criterion that
  exists only in one repo's prompt prose, which is exactly the class of thing this
  phase is supposed to be extracting *away* from.

  **The row-advance reconciler ships here, not in the new repo.** Session A.5
  builds it (owner decision 2026-08-18: a scheduled reconciler — not a
  `workflow_run` rewire, not a PAT) and P8.1 freezes it into the contract. It
  belongs to the substrate, so criterion 8 inherits a working row-advance instead
  of re-discovering finding 3. The reasoning is worth carrying: the failure being
  repaired is *an event that was never observed*, so a reconciler — which reads
  state rather than reacting to events — is strictly more robust than any trigger,
  and it is the only candidate that would have surfaced #115 without a human
  noticing.

  **The `pickup-loop` acceptance check is rewritten, not carried.** Owner decision
  2026-08-18: `docs/reference/loops.md`'s "requests review" clause is replaced by a
  `state:review` label that the digest renders as a waiting-on-you section. The
  clause is unsatisfiable — GitHub rejects a self-review request and the repo has
  one collaborator — and it was already obsolete under ADR-0020, where the gate is
  the review for `gate:machine` and auto-merge refuses `gate:taste` regardless.
  This matters to the extraction specifically: `loops.md` travels, and an
  unmeetable clause in a document consumer #2 reads as authoritative is the GL-53
  pattern — an instruction that looks like a control.

  **Two exit criteria added 2026-08-19 — P8.1 is not done until both are closed,
  and P8.2 does not start until P8.1 is done.**

  - **#167 — `doctor` can never be clean.** `digest.yml:114–115` opens the daily
    status issue with exactly one label, `qops:status`, and
    `install.issue_invariants()` requires one `type:`, one `state:` and one
    `gate:` with no exemption. Two halves of the substrate disagree about what a
    valid issue is: one writes it, the other rejects it. Three permanent problems
    today, and **criterion 5 cannot be evaluated at all** until it is fixed — in
    either repo, since both halves travel. The findings doc's argument is the
    operative one: a gate that can never be green stops being read, which is how
    those three lines hide the fourth. Fix: `issue_invariants` skips issues
    carrying `cfg.ci.status_issue_label` — machine-authored bookkeeping is not a
    sortie.
  - **#168 — the guard is fail-open on two paths.** `qops/guard.py:67–68` reads
    the push target as the last `\S+` and, when that token starts with `-`, falls
    back to the *checked-out* branch — so on `master` any `git push` ending in a
    flag reads as a push to `master`, while the refspec form
    `git push origin :<branch>` is not caught at all and does the job. A control
    a caller routes around is a speed bump. Second half: `_FORCE`
    (`guard.py:19`) matches the whole command string with no prose exemption — the
    tripwire scan four lines below it has one for exactly this reason — so the
    substrate cannot document its own git rules through any tool that takes prose
    on the command line, and the workaround (`--body-file`) is a path the guard
    cannot see into. **This is the one that must not be published:** the extracted
    guard becomes the reference implementation consumer #2 copies, and a
    known-routable control is worse in a public repo than in a private one.
    Needs a design decision — tighten the parse or recognise `--delete`
    explicitly — not a patch chosen in passing.

  *Ships value even if P8.2+ never happen.*
- **P8.2 — create the repo.** **Pre-authorised by the owner, 2026-08-17,
  conditionally as of 2026-08-19:** the pre-authorisation stands and no separate
  go-ahead is needed — **provided #167 and #168 are closed.** If either is still
  open, stop and report rather than creating the repo; the authorisation was given
  against a substrate whose guard was believed sound. `qvajda/qops`, public,
  licence, README with provenance, its own gate running `tests/test_qops.py`.
- **P8.3 — move.** Copy the §Scope-in paths, fresh initial commit. Success
  criterion 3 (byte-identical rendering) is the gate.
- **P8.4 — rewire.** This repo installs the pinned package, deletes qops source,
  `qops doctor` clean, workflows unchanged.
- **P8.4b — stand up autonomy in the new repo.** New phase, 2026-08-17. Without
  it the substrate is filed but inert, and criterion 8 is what proves otherwise.
  Ordered, because each step's failure is invisible until the next one runs:
  1. Author `.qops/config.yml` for the new repo: `project: qops`,
     `repo: qvajda/qops`, `tripwires: []`, `doc_link_roots: [qops, scripts,
     tests]`, `skills.native` only and `skills.external: []`, `gate_command`
     pointing at `tests/test_qops.py`. Everything else copies.
  2. Add its own `CLAUDE.md` (doctor reads it unconditionally) and
     `.claude/settings.json` invoking `python -m qops` (doctor reads CLAUDE.md at
     `install.py:151` and checks the settings file at `:147–150`).
  3. `python scripts/qops_import.py` to create the label taxonomy. A repo with no
     labels cannot hold a `ready:auto` and the picker's query returns empty
     forever without erroring — a silent failure by construction.
  4. **Branch protection on `master`, with the gate as a required check.** Not
     previously in scope or criteria, and load-bearing:
     `automerge-loop` only switches on GitHub's *native* auto-merge; required
     checks are what actually merge (ADR-0016, ADR-0020). Skip this and every
     `gate:machine` sortie opens a PR that sits forever, which reads exactly like
     a broken picker. **Owner action, not the agent's** — `.claude/settings.json`
     denies `gh api -X` against branch protection on purpose, and that denial is
     a taken decision. Also enable the repo's "Allow auto-merge" setting.
  5. Register the second `qops-pickup-loop` task, or give the existing one a
     `--repo` argument, per §Scope. Leave it **disabled**, as it ships here.
  6. Then criterion 8: one real issue, end to end, unattended.
- **P8.5 — migrate the issues.** ADR-0015's exact query
  (`gh issue list --label mission:qops --state all`) — **re-run it, do not trust a
  count.** 12 today, 13 once the triage sweep retypes #49. **P8.5 must not run
  before that sweep has landed**, or #49 is stranded in the wrong tracker with
  both trackers believing they own it. Each issue closes here with a pointer to
  its new home. **#169 and #170 migrate as open issues** (owner, 2026-08-19) —
  both are substrate defects with named fix shapes and neither is exercised today.
  Carrying two honest known-defects into the new tracker is what the migration is
  for; #169 in particular deserves its history in the new repo, since it is the
  third layer of one defect (a ref exists → a ref has commits → *this run*
  committed) and the next person to touch `produced_work()` needs that record.
- **P8.6 — record.** Amend ADR-0015 (interim ends), new ADR for the split, update
  the ways-of-working section of CLAUDE.md: **there are now two trackers**, and
  the brief must say which one it read.

## Risks

| Risk | Mitigation |
|---|---|
| Two trackers double the "issues are the source of truth" surface — the failure mode is a session reading the wrong one. | `qops brief` states which repo it queried, every time. Non-negotiable, lands in P8.4. |
| Version skew: the pipeline pinned to a stale qops while the substrate moves. | Pin a tag, not a branch. A substrate mutating under a live pipeline is the GL-53 failure mode. |
| Rendered-workflow drift between the two repos. | `qops doctor` already detects drift; criterion 3 makes it the move's gate. |
| ~~One consumer.~~ Superseded: `myThirdwheel` + the new projects are consumer #2 and are the design review. The live risk inverts — the seams get judged by a caller that doesn't exist yet at freeze time. | Freeze the contract (P8.1) *before* project #2 starts, then treat its first week as the review window. No config-schema changes inside that week; collect complaints instead of patching. |
| **Hand-copying.** A new project started before the package exists copies `qops/` and `.qops/` and diverges immediately, with no merge path back. | This is now the dominant risk and it has a date on it. P8.2 lands before the first new project is scaffolded, or the first new project is deliberately started *without* qops. |
| Extracting an unproven autonomy substrate — the hands-off sortie has never run. | Overstated as written: it *has* run, once, successfully — #116 was picked, shipped and advanced by `automerge-loop` (`docs/reference/loops.md`, ADR-0020 amendment). The mechanism is proven; what is unproven is the mechanism in a *second* repo. Run the acceptance sortie inside P8.1's window on this repo, then criterion 8 on the new one. Neither gates P8.2 (open question 4). |
| **The substrate is extracted and cannot work its own backlog.** The failure is silent: the picker's query returns empty against a repo with no labels, no `ready:auto` and no branch protection, and exits 0 while doing so. An hourly task reporting "nothing eligible" looks identical to a healthy idle queue. | Criterion 8 and P8.4b. The queue's health is asserted by a sortie completing, never by the loop's own output. |
| qops's own backlog is *more* auto-eligible than the pipeline's — local code, a real test suite, no vendor endpoint, so triage R6 excludes nothing — which makes an over-permissive `gate:machine` cheap to apply and expensive to be wrong about. | Triage R3 stands unchanged in the new repo: when unsure, `gate:taste`. A wrong `machine` label on substrate work ships a change to the thing that governs every other project. |

## Open questions

1. **Distribution mechanism?** *Recommendation: Claude Code plugin repo*, since
   the skills and agents are already consumed that way, plus `pip install -e` for
   the CLI during development. Alternatives: pip-from-git, submodule.
2. **Pin or track?** *Recommendation: pin a tag* in this repo, per §Risks.
3. **Do all 12 `mission:qops` issues migrate, or does open work finish here
   first?** *Recommendation: migrate all 12.* ADR-0015 already says the next qops
   issue filed here is a migration item, not a resident — there are 12, and a
   partial migration keeps both trackers authoritative, which is the worst state.
4. ~~**Sequencing — extract first, or run the Phase 7 acceptance run first?**~~
   **Resolved 2026-08-17.** *Recommendation: extract first, acceptance run in
   parallel.* The Phase 7 sign-off parked this until "a second project exists";
   a second project now exists in the next few days, so the condition it named
   is met rather than overridden — the contradiction I recorded this morning
   dissolves on its own terms. The acceptance run still matters, but it is a
   qhoto-repo experiment and no longer a gate on packaging.

5. **Does `myThirdwheel` want all of qops, or only the taxonomy and the brief?**
   *Recommendation: only the taxonomy, brief and ledger at first.* The guard's
   tripwire mechanism is valuable but its content is per-project, the six
   workflows assume a Python test suite, and `myThirdwheel` is a different shape
   of project. Forcing the whole substrate onto consumer #2 is how the abstraction
   gets hardened around the wrong seams. Ship the package with an explicit
   minimum-viable subset and let it grow by request.
