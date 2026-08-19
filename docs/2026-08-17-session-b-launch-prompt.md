# Session B launch prompt — Phase 8, P8.1 through P8.4b

**Run this in Claude Code, in a terminal. Not in Cowork** — `gh`, `git remote` and
repo creation are all unavailable from the Cowork sandbox.

**Predecessor: Session A must have landed** (`docs/2026-08-17-session-a-launch-prompt.md`).
Specifically: the triage sweep is applied, so `mission:qops` is correct and #49 is
inside it. P8.5 stranding #49 is the failure this ordering exists to prevent. If
the sweep has not run, stop and say so rather than working around it.

```bash
claude --remote-control "qops Phase 8 extraction"
```

`/config` → **Push when actions required**. P8.4b step 4 is an owner-only action
and the session will block on it.

---

You are running **Phase 8**: extracting qops out of `qhoto_printshop` into
`qvajda/qops`, and — this is the part earlier drafts missed — leaving it able to
work its own backlog.

**Read first, and only these:**

1. `docs/2026-08-17-qops-phase8-extraction-prd.md` — **revision 2.** Read the
   revision-2 header, then §Success criteria (eight, not seven), §Scope including
   the pickup-runtime split, §Plan, §Risks. Where revision 1 and revision 2
   disagree, revision 2 wins.
2. `docs/adr/0015-qops-tracks-itself.md` — the interim this phase ends, and the
   exact migration query.
3. `docs/adr/0009-local-desktop-cron-host.md` — you will be amending it.
4. `docs/adr/0016-...` and `0020-auto-merge-green-machine-gated-prs.md` — why
   branch protection is load-bearing rather than hygiene.
5. `.qops/config.yml` — the file you are about to write a second, different
   version of.
6. `docs/reference/loops.md` — the six loops, and which of them the new repo needs.

**Cleared to start, 2026-08-19.** P8.0 is satisfied: A.5 landed and criterion 8
passed on attempt 3 (#160 — pick 08:28, row `state:done` 08:41, no human touch in
between). `docs/2026-08-19-attempt-3-findings.md`.

**Owner authorisations already given, do not re-ask:**

- **P8.2 is pre-authorised — conditionally.** Create `qvajda/qops`, public, with no
  separate go-ahead, **provided #167 and #168 are closed first.** They are P8.1
  exit criteria (see below). If either is open when you reach P8.2, stop and
  report: the authorisation was given on 2026-08-17 against a substrate whose
  guard was believed sound, and #168 says it is routable.
- Sequencing per open question 4: the acceptance run does not gate packaging.

**Two P8.1 exit criteria, added 2026-08-19 from attempt 3's findings.** Full
reasoning is in the PRD's P8.1; the short version is that both travel and both are
worse in a public repo than here:

- **#167** — `digest.yml:114–115` writes a status issue that
  `install.issue_invariants()` rejects, so `qops doctor` reports 3 problems today
  and **cannot reach zero**. Criterion 5 is unevaluable until this is fixed. When
  you run `doctor` at the start of this session, those three lines are expected and
  are not new. Fix: exempt `cfg.ci.status_issue_label`.
- **#168** — `qops guard` reads a flag as the push target and falls back to the
  checked-out branch, and `git push origin :<branch>` bypasses it entirely; plus
  `_FORCE` has no prose exemption, so the substrate cannot document its own git
  rules through a `--body` argument. **This one needs a design decision, not a
  patch** — and it is the reason P8.2 is now conditional. A guard that a caller
  routes around becomes the reference implementation consumer #2 copies.

**#169 and #170 do not block.** They migrate as open issues under P8.5. Do not fix
them here — #169 especially is a design question (`produced_work()` still answers
"does this repo have a branch with commits" rather than "did this run commit"), and
its history is part of what the new repo should inherit.

**Still requires an explicit stop (CLAUDE.md §4):** anything deleting qops source
from this repo (P8.4), and branch protection settings (P8.4b step 4, owner-only —
`.claude/settings.json` denies `gh api -X` against them by design, and that denial
is a taken decision, not an obstacle to route around).

**Closed, never to be proposed:** any git history rewrite — no `filter-repo`, no
`filter-branch`, no BFG, no subtree surgery, no force-push. The extraction copies
files into a fresh initial commit and records provenance in the new repo's README.

## P8.0 — prereq gate

Tree clean, #142 closed. **The acceptance-run clause is struck** — see the PRD's
P8.0 entry. If Session A's acceptance run failed, that is information for the
findings doc; it does not block this session.

## P8.1 — freeze the contract

*Ships value even if nothing after it happens.* Do this fully before creating
anything outward-facing.

Three leaks, not the two the original audit found:

1. `qops/templates/guard.yml.tmpl:29` — a comment naming Gelato and the pipeline's
   three tripwires. Generalise it; the tripwire list is config's, not the
   template's.
2. `tests/test_qops.py` — `etsy` / `replicate` fixture strings.
3. `scripts/qops_pickup.py:30` and `scripts/qops_import.py:28` — both derive
   `ROOT` from `Path(__file__)`. Move both to `config.find_root()`, which is what
   `qops/__main__.py:43` already does correctly. **This is the leak that decides
   whether the extracted package works at all**: as a pinned dependency,
   `Path(__file__).parents[1]` is site-packages, not the consuming repo.

Two new tests:

- A portability test failing on any project-specific string outside
  `.qops/config.yml`. The property becomes enforced rather than measured once.
- `qops guard scan` exits 0 against an **empty** `tripwires:` list. The substrate
  repo has none, that path has never been exercised, and a crashing guard job
  fails every build in the new repo from its first push.

Then document the config schema and the CLI contract. `myThirdwheel` is consumer
#2 and its first week is the design review — the schema is frozen before it
starts, and complaints get collected rather than patched inside that week.

## P8.2 — create the repo

Pre-authorised. `qvajda/qops`, public (ADR-0012's decision is inherited
explicitly, in a new ADR — it does not get to be silent). Licence, README with
provenance pointing at source commits here, its own gate running
`tests/test_qops.py`.

The irreversible parts, flagged not blocked: a public repo cannot be un-published
for anyone who cloned it, and the licence choice is a one-way door for outside
contributions. Pick the licence deliberately.

## P8.3 — move

Copy the §Scope-in paths into a fresh initial commit. **Criterion 3 is the gate:**
re-rendering the six workflows from the extracted package produces output
byte-identical to what is on disk here today. Diff it, don't eyeball it. If it
differs, the difference is either a leak you missed or a template that was never
purely generated — both are findings, and neither is fixed by accepting the new
output.

## P8.4 — rewire this repo

Pinned **tag**, not a branch (§Risks: a substrate mutating under a live pipeline
is the GL-53 failure mode). Delete qops source — **stop and ask first.** `qops
doctor` clean, workflows unchanged, `qops brief` states which repo it queried.
That last one is non-negotiable and lands here: with two trackers, a session
reading the wrong one is the dominant new failure mode.

## P8.4b — stand up autonomy in the new repo

**The phase that answers "can qops work its own issues?"** Follow the PRD's
ordered checklist. Each step's failure is invisible until the next one runs, which
is why the order is part of the spec. In particular, step 3: a repo with no labels
makes the picker's query return empty **and exit 0** — an hourly task reporting
"nothing eligible" is indistinguishable from a healthy idle queue.

Step 4 is the owner's: branch protection with the gate as a required check, plus
the repo's "Allow auto-merge" setting. Block and ask. `automerge-loop` only
switches *on* native auto-merge; required checks are what merge.

Step 6 is criterion 8: one real issue in `qvajda/qops`, `state:planned` +
`ready:auto` + `gate:machine`, picked → branched → PR'd → auto-merged with no
owner keystroke in between. **Nothing else in this PRD proves the runtime**, so do
not declare Phase 8 done without it, and do not simulate it.

Triage R3 applies unchanged in the new repo: when unsure, `gate:taste`. Substrate
work is unusually machine-gateable, which makes an over-permissive `gate:machine`
cheap to apply and expensive to be wrong about — a bad autonomous change there
governs every project that consumes qops.

## P8.5 — migrate the issues

**Re-run the query. Do not trust a count** — not 12, not 13. Session A's sweep
changed the set; read it fresh. Each issue closes here with a pointer to its new
home. Partial migration is the worst state: both trackers authoritative.

## P8.6 — record

Amend ADR-0015 (interim ends). Amend ADR-0009 — "the cron host is the local
Windows desktop" now has to say how many repo roots that host serves. New ADR for
the split. Update CLAUDE.md's ways-of-working section: **there are now two
trackers, and the brief says which one it read.** Mind the 150-line cap; `groom.yml`
and `tests/test_qops.py` both enforce it, and this is exactly the edit that
historically breached it.

## Stop conditions

Stop and report rather than proceeding if: criterion 3's diff is not
byte-identical; `qops doctor` cannot be made clean in the new repo without editing
a test to suit; or the criterion-8 sortie fails. Each of those is a finding about
the seams, and the seams are what this phase exists to get right before consumer
#2 arrives.
