---
status: accepted
revisit-after: 2026-11-01
---

# qops's own work is tracked as issues, not as a document — and it leaves this repo when the plugin repo exists

PRD v3 Phase 5, which is one line of policy and is written here because a line
of policy in a phase list is a line nobody trips over.

## Context

Every previous ways-of-working push lived as a planning document: v1, v2, v3,
the kickoffs, the go-live plan. The go-live plan reached 401 KB and ~100,000
tokens — past the point where a single file read can return it, so consulting it
means scripted extraction. That is root cause 1 reaching its end state, and it
is the strongest argument in the PRD because the PRD did not have to make it.

qops cannot fix that for the pipeline and reproduce it for itself.

## Decision

**qops's own work is issues, not a document.** From Phase 5 onward:

1. **`qhoto_printshop` issues track pipeline work only.** GL-numbered sorties,
   defects, live-run findings — the shop.
2. **qops's work lives in the qops plugin repo.** Its build, its bugs, its
   portability work, its next phase.
3. **Neither is a planning doc.** A PRD may state a decision; it may not hold
   state. When the two disagree, the issue wins — that rule is already in
   `CLAUDE.md` and this extends it to qops itself.

**The interim is over (2026-08-19).** It said qops issues stay in
`qhoto_printshop` carrying **`mission:qops`** until the plugin repo existed, and
named the exact migration query: `gh issue list --label mission:qops --state all`.
When this ADR was written that query returned nothing, and the note recorded that
the next qops issue filed here would be "a migration item, not a resident".

`qvajda/qops` exists as of 2026-08-19 (ADR-0023), the query was re-run rather
than trusted, and every row it returned was migrated and closed here with a
pointer to its new home. The interim paragraph is deleted rather than amended,
as this ADR said it would be.

**What the interim actually cost, since it is the reusable part:** it ran for
five days and accumulated a working backlog. Nothing was wrong with the interim
— the repo was a separate, outward-facing act and correctly was not authorised
in the same breath as the policy. But an interim with no expiry becomes the
arrangement, and the thing that ended this one was a deadline arriving from
outside (a second project), not the interim being noticed.

## Consequences

- Phase 7's portability proof gets easier: a plugin whose own backlog lives in
  the project it was extracted from is not portable, it is entangled.
- The digest and `qops metrics` read one repo. When the split happens, both need
  a second `--repo`, and `.qops/config.yml`'s `repo:` key is the single place
  that changes.
- **The failure mode to watch for is a qops issue quietly filed here without
  `mission:qops`.** Then the migration query misses it and it becomes pipeline
  backlog forever. `groom.yml`'s label-hygiene job lists issues missing labels,
  and the digest now renders that list, which is the closest thing to a check
  this has.

**Revisit** when the plugin repo is created — at which point the interim
paragraph is deleted rather than amended, and the migration is one `gh issue
transfer` per `mission:qops` row.
