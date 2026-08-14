# The five loops

Cold storage. One row of prose per loop was all v2 ever had; this file is the
definition the runtimes are built from, so an audit has something to read.

Four of the five are **LLM-free** and run in Actions. The one that costs money
is `pickup-loop`, and it is off.

| Loop | Runtime | Cadence | LLM | Authority |
|---|---|---|---|---|
| `gate-loop` | Actions — `gate.yml` + `test.yml` + `guard.yml` | every PR, every push | none | may fail a build; may not merge |
| `review-loop` | a session, on request — `/code-review` | per PR | yes, owner-initiated | reports; may not commit |
| `triage-loop` | Actions — `groom.yml` label-hygiene job | weekly + on demand | none | warns; may not label |
| `groom-loop` | Actions — `groom.yml` hot-path job | on any `CLAUDE.md` change, weekly | none | fails the build |
| `pickup-loop` | Windows scheduled task `qops-pickup-loop`, **disabled** | hourly when enabled | yes | branch + commit + PR; **never merge** |

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
and stops there. It never merges, never activates a listing, never touches
`master`.
**Every eligibility condition is the owner's to grant.** `ready:auto` is granted
by the owner alone; the triager is forbidden from applying it.
**Runtime note:** `scripts/qops_pickup.py` without `--launch` prints what it
would pick and starts nothing, which is how the wiring is proved without
spending anything.

## Audit

Loop Doctor, 2026-08-14, once (PRD v3 Phase 4 item 10). A **design** audit —
none of the five had fired yet, so no finding is connected to an observed
failure. Verdict: repair needed. `groom-loop` and `review-loop` were sound and
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
