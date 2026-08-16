# The six loops

Cold storage. One row of prose per loop was all v2 ever had; this file is the
definition the runtimes are built from, so an audit has something to read.

Five of the six are **LLM-free** and run in Actions. The one that costs money
is `pickup-loop`, and it is off.

| Loop | Runtime | Cadence | LLM | Authority |
|---|---|---|---|---|
| `gate-loop` | Actions — `gate.yml` + `test.yml` + `guard.yml` | every PR, every push | none | may fail a build; may not merge |
| `review-loop` | a session, on request — `/code-review` | per PR | yes, owner-initiated | reports; may not commit |
| `triage-loop` | Actions — `groom.yml` label-hygiene job | weekly + on demand | none | warns; may not label |
| `groom-loop` | Actions — `groom.yml` hot-path job | on any `CLAUDE.md` change, weekly | none | fails the build |
| `pickup-loop` | Windows scheduled task `qops-pickup-loop`, **disabled** | hourly when enabled | yes | branch + commit + PR; merges only via `automerge-loop` |
| `automerge-loop` | Actions — `automerge.yml` | every PR event | none | turns on native auto-merge for a `gate:machine` PR; may not merge a `gate:taste` one |

## gate-loop

**Trigger:** a pull request, or a push to any branch.
**Does:** runs the test suite (`test.yml`), the substrate tests and `qops
doctor` (`gate.yml`), and the tripwire + doc-link scans (`guard.yml`).
**Acceptance check:** every applicable machine gate is green before a taste
review is requested. That is S4, and S4 counts review requests that arrive
without it.
**Failure mode it exists for:** a taste review spent on something a script
could have rejected.

## review-loop

**Trigger:** the owner, on a PR whose machine gates are green.
**Does:** `/code-review` — Standards and Spec as two parallel read-only
subagents, so neither pollutes the other's context.
**Acceptance check:** findings are reported as `path:line`, and the reviewer
never edits.
**Why it is not automated:** it is a taste gate. Automating the *request* is
S4's job; automating the *judgement* is not wanted.

## triage-loop

**Trigger:** weekly, and on demand.
**Does:** lists every open issue missing `type:` / `state:` / `gate:`.
**Acceptance check:** the list is empty.
**Deliberate limit:** it **warns and does not label.** A guessed label reads
exactly like a decided one. `ready:auto` is never applied by any loop.

## groom-loop

**Trigger:** any change to `CLAUDE.md`, plus weekly.
**Does:** fails the build if `CLAUDE.md` exceeds `claude_md_max_lines` (150).
**Acceptance check:** the cap holds.
**Why it is load-bearing rather than hygiene:** `CLAUDE.md` is the larger half
of the measured daily saving, and it grew ~10 lines/day for a month while the
cap was written down and unenforced. Unchecked, the cap is re-breached in about
three weeks. `tests/test_qops.py` asserts the same thing locally, so a breach
fails before CI sees it.

## pickup-loop

**Trigger:** hourly, **only when the task is enabled. It ships disabled.**
**Does:** picks the least-recently-updated issue carrying `state:planned` **and**
`ready:auto`, with a real gate (`gate:none` is not one) and no `no-auto` /
`blocked` flag, then starts a session on it.
**Acceptance check:** it branches, commits, opens a PR and requests review —
and stops there. It never merges by hand, never activates a listing, never
pushes to `master`.
**Amended 2026-08-16 (ADR-0020):** its PR may still be merged, by
`automerge-loop`, if the issue is `gate:machine` and every required check is
green. `pickup-loop` itself gained no authority — it opens a PR and stops; the
merge is a separate loop with its own conditions, and neither can merge a
`gate:taste` PR.
**Every eligibility condition is the owner's to grant.** `ready:auto` is granted
by the owner alone; the triager is forbidden from applying it.
**Runtime note:** `scripts/qops_pickup.py` without `--launch` prints what it
would pick and starts nothing, which is how the wiring is proved without
spending anything.
**Amended 2026-08-16 (#122):** the first acceptance run read for 62 seconds and
wrote nothing — the launch carried no permission mode, so every branch and edit
waited on an approval nobody was there to give. Three repairs:

- **A scoped launch grant.** `--permission-mode acceptEdits` plus
  `--allowedTools` set to the *coder role's* toolset and no wider. It removes
  the interactive prompt; it widens nothing. The PreToolUse guard and branch
  protection remain the controls, and a blanket bypass
  (`--dangerously-skip-permissions`) is asserted absent, not merely omitted. If
  the grant later needs a per-role shape, that is #123 arriving.
- **The claim is released on failure.** A non-zero exit, *or* an exit with no
  branch and no PR, reverts `state:building` → `state:planned` and comments why.
  The 62-second run exited 0, so exit code alone would have kept the door shut.
- **No sandbox escape unattended.** The denied session retried with
  `dangerouslyDisableSandbox`. The launch sets `QOPS_UNATTENDED=1` and `qops
  guard` refuses that flag when it is set. An owner at a keyboard may still
  make that call; a loop with nobody reading may not.

## automerge-loop

**Trigger:** any pull-request event — opened, reopened, synchronised, labelled,
unlabelled, ready-for-review.
**Does:** turns on GitHub's **native** auto-merge for a qualifying PR. It does
not merge; branch protection's required checks do, when they go green.
**Qualifies:** not a draft, not from a fork, a branch matching
`<type>/<issue#>-<slug>` (ADR-0019), and the **linked issue** carrying
`gate:machine` and no `no-auto`. The gate is read from the issue, not the PR —
nothing labels a PR. `no-issue/` has no issue, so it never auto-merges.
**Acceptance check:** a `gate:taste` PR is never merged by it, and a red gate
never merges anything.
**Why it exists:** on a `gate:machine` PR the owner's click had nothing left to
judge — the gate judged it. A mindless approval button is not a control
(ADR-0020).
**Failure mode it accepts:** a defect the machine gate cannot see reaches
`master` unread. That is the same exposure every unread manual merge already
carried, made honest — so a defect that lands this way is a **missing check**,
and the fix is the check, not the restoration of the click.

## Audit

Loop Doctor, 2026-08-14, once (PRD v3 Phase 4 item 10). A **design** audit —
none of the five then defined had fired yet, so no finding is connected to an
observed failure. Verdict: repair needed. `groom-loop` and `review-loop` were sound and
were left alone. Three material findings, all fixed in the same commit:

1. **`pickup-loop` re-picked the same sortie forever.** It chose the
   least-recently-updated eligible issue and never changed that issue's state,
   so an hourly fire on a sortie that failed or stalled picked the same issue
   again next hour — one session per hour, indefinitely. **Fix:** claim the
   issue (`state:planned` → `state:building`) *before* launching, and abort the
   launch if the claim fails. The claim is the no-progress stop.
2. **`gate-loop`'s acceptance check and its instrument disagreed.** The
   definition says "every applicable machine gate green"; `metrics.s4` looked
   only for a check named `gate` or `test`, so a red `guard.yml` — the tripwire
   and doc-link scan — scored as clean. **Fix:** S4 now reads every check's
   conclusion rather than two names.
3. **`triage-loop` warned into a place nobody reads.** Weekly `::warning::`
   lines in an Actions log, consumed by nothing, so the loop had no terminal
   state and could warn identically forever. **Fix:** the untriaged list is
   rendered into the digest, which reaches the owner and can reach zero.
