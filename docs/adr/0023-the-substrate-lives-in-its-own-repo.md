---
status: accepted
revisit-after: 2027-02-01
amends: 0009, 0015
---

# The substrate lives in its own repo, and this one consumes it at a pinned tag

**Date:** 2026-08-19 · **Session:** Phase 8 · **Ends the interim in:** ADR-0015

## Context

qops was built here, for this project, over six phases. That was the right place
to build it and the wrong place to keep it, for three reasons that had all
stopped being hypothetical:

1. **ADR-0015's interim had become the arrangement.** It said qops issues stay
   here carrying `mission:qops` "until the plugin repo exists". When it was
   written the migration query returned nothing. It now returns a backlog.
2. **Shared CI and a shared hot path.** `test`/`gate`/`guard`/`groom`/`digest`/
   `automerge`, `.claude/`, `skills-lock.json` and the 150-line `CLAUDE.md` cap
   served both concerns, so a substrate change and a pipeline change contended
   for the same green build.
3. **No second consumer could exist** while the substrate was a subdirectory of
   one project — and a second consumer is now days away, which turns the cost of
   waiting into a hand-copied fork with no merge path back.

## Decision

**`qvajda/qops` is the substrate. This repo consumes it at a pinned tag.**

| | |
|---|---|
| Where the code lives | `qvajda/qops`, public, MIT (that repo's ADR-0022) |
| How this repo gets it | a **pinned tag**, never a branch |
| What stays here | `.qops/config.yml`, the tripwire list, `tests/test_qops_project.py`, the pipeline's own ADRs and scheduled tasks |
| Where qops's issues live | `qvajda/qops`. This repo's tracker is the shop's again |
| How the split was made | files copied into a fresh initial commit; **no history rewrite, no subtree surgery** |

**Pinned, not tracked, and the reason is a failure this repo has already had.**
A substrate that mutates under a live pipeline is the GL-53 shape: something
changes underneath, nothing announces it, and the first evidence is a defect in
the thing that depends on it. A tag makes the upgrade an act.

## Consequences

**There are two trackers, and that is the new dominant failure mode.** Not a
wrong answer — a right answer read out of the wrong repo. The mitigation is not
a convention: `qops brief` names the repo it queried, every session, every time.
`CLAUDE.md`'s ways-of-working section says which is which.

**Criterion 3 was the gate on the move itself.** Re-rendering all six workflows
from the extracted package against this repo's config produced output
byte-identical to what was on disk here — 6/6, diffed rather than eyeballed. A
difference would have been either a leak that was missed or a template that was
never purely generated, and neither is fixed by accepting the new output.

**The extraction found what an audit could not.** The 2026-08-17 portability
audit grepped for project *strings* and found two leaks. Three more surfaced
only when the question changed from "is anything project-specific here" to "does
this work as somebody else's dependency": `Path(__file__)` rooting in both
`scripts/` entry points, a hardcoded schema path inside `doctor`, and a
`docs/agents/` file naming the repo. A fourth — `bash -lc` in
`metrics.state_report` — had been found the week before by a run, not by a read.
All four are now assertions rather than measurements, which is the actual
deliverable of P8.1: the property is enforced on every commit instead of being
true on the day someone checked.

**ADR-0009 is amended, not superseded.** The cron host is still the local
Windows desktop. It now serves **two repo roots**, so a scheduled task must name
the root it operates on rather than deriving one — see the amendment there, and
#176 for the registration that broke exactly this way while disabled.

**ADR-0015's interim paragraph is deleted rather than amended.** The condition it
named has been met.

**What this does not do:** it does not deliver meta-orchestration. Phase 8
*enables* it. The deliverable here is a substrate that a second project can
install and that can work its own backlog — nothing more, and the second half of
that is the half nothing before criterion 8 tested.
