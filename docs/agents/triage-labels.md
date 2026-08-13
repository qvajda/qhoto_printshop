# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those
roles to the actual label strings used in this repo's issue tracker.

**The defaults were not kept.** This repo already has a taxonomy — PRD v3 §9,
held in `.qops/config.yml` — and it was amended and signed off before any issue
existed. Taking the skills' default five would have created a **second**
vocabulary describing the same states, which is the duplication `/triage` says to
avoid. Every role below maps onto a label the taxonomy already defines; **no new
label is created by this mapping.**

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `state:triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `state:blocked`      | Open, waiting on a named external party  |
| `ready-for-agent`          | `ready:auto`         | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `no-auto`            | Requires human implementation            |
| `wontfix`                  | `state:cancelled`    | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the
corresponding label string from this table.

## Two riders the mapping carries, both load-bearing

1. **`ready:auto` is a control, not a description.** No row was given it at
   import (review finding D1), and a row cannot hold it while its `gate:` is
   `none`. `/triage` may propose it; the validator refuses it at import.
2. **`state:cancelled` is not `done`.** It exists because GL-29 was struck rather
   than completed, and closing it as `done` would be a lie the tracker then
   repeats. Map `wontfix` here and nowhere else.

Edit the right-hand column to match whatever vocabulary you actually use — but if
you do, change `.qops/config.yml` in the same commit. The validator reads that
file, not this one.
