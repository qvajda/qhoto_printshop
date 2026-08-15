# Phase 7 owner sign-off — 2026-08-15

Owner decisions on `docs/2026-08-15-qops-phase7-enforcement-proposal.md`, plus
three additions the proposal did not request. This file is the sign-off; turn
each item into its ADR or issue and do not re-argue settled ones.

## The seven requested decisions

1. **APPROVED.** `to-spec` becomes model-invocable; the publish-to-tracker step
   stays owner-confirmed. `triage` stays owner-only. → ADR-0019.
2. **APPROVED.** Build the PreToolUse branch guard, scoped to
   `pipeline/ scripts/ qops/ tests/`, with the counted `no-issue/<slug>` escape.
   → ADR-0019.
3. **APPROVED.** Stop hook records unfinished state to the ledger; the next
   brief leads with it. It never refuses to stop. → ADR-0019.
4. **APPROVED — highest priority of the seven.** Adopt the routing rule (§2) in
   full. `gate:machine` = no owner contact before review. This is the fix for
   the babysitting regression and everything else queues behind it. → ADR-0017.
5. **APPROVED.** Option B sized by C: write the three qops-native skill bodies
   (interview, spec→issue, triage), substrate injects the rest, uninstall
   everything outside the declared set, pay ADR-0013's displacement, add an
   upstream ref to `skills-lock.json` for survivors. → ADR-0018.
6. **APPROVED.** Rollback rejected on the figures; re-decide at n ≥ 20 scored
   sessions. Record on the Phase 6 issue + `revisit-after` on ADR-0013.
7. **DECLINED for now.** No STE prose lint in CI. Polish while autonomy is
   switched off is the wrong order. Revisit after the routing rule has run for
   a month. The banned-word list may go into review guidance as prose, no gate.

## Three additions (owner-initiated)

8. **Auto-merge green `gate:machine` PRs.** ADR-0016 already dropped the
   approval count; take the next step. Conditions: gate green, guard green,
   branch matches `<type>/<issue#>-<slug>` or `no-issue/`, label
   `gate:machine`, no `no-auto`. Owner review is reserved for `gate:taste`.
   A mindless approval button is not a control. → new ADR.
9. **One-page cap on owner-facing decision requests.** Anything asking me to
   decide gets: ≤1 page, summary first, at most 4 options, one recommendation.
   Long analysis may exist but goes behind a link, never in the ask. Enforce in
   the interactor/planner agent definitions, not as a wish. → amend agent defs.
10. **Purge always-yes permission prompts.** Sweep `.claude/settings.json` /
    per-task permission mode so waits, reads, test runs and other zero-risk
    calls stop asking. If I have never once said no to a prompt class, it is
    allowlisted. → config change + short ledger note of what was allowlisted.

## The acceptance run — do this before anything else new

**One supervised autonomous sortie, end to end, hands off.** Pick a small open
issue that is pure local code (GL-63 class), label it `gate:machine` +
`ready:auto`, enable `pickup-loop` for one scheduled window, and let it run
brief → branch → TDD → PR → gates → auto-merge (per item 8) with zero owner
messages. I watch; I do not steer. If any step needs me, that step is the next
issue to file. Phase 6 tested the substrate; this tests the autonomy, which is
the product I actually asked for.

## Two issues to file

11. **Regression investigation: "dumber since the CLAUDE.md slim".** Diff the
    mistakes from the 2026-08-14 evening session against the archived 372-line
    CLAUDE.md (`docs/archive/2026-08-14-claude-md-pre-slim.md`). Any mistake
    matching an archived rule becomes a hook-injected context line at the
    relevant stage — not a paragraph restored to CLAUDE.md. Do it before the
    transcript context goes stale.
12. **Reframe `qops metrics` around usage, not ROI.** Add: owner-minutes per
    merged PR, share of merged PRs that ran through the full flow, count of
    owner interruptions per sortie. Payback-weeks is retired as the headline
    number. Success = it gets used.

## Parked, recorded so it is not re-derived

- **Notion as an input source** (parked-ideas backlog feeding the pipeline):
  wanted eventually, not now. Interim: ideas are logged directly as issues.
- **qrchardist / meta-orchestration:** stays Phase 8+, after a second project
  exists. My workflow sketches from today's review are the requirements input
  when it starts.
- **n8n or similar:** rejected while the project is subscription-only — its
  LLM nodes need API billing, and Actions/Routines/scheduled tasks already
  cover the deterministic wiring. Trigger to revisit: a move to API billing.
