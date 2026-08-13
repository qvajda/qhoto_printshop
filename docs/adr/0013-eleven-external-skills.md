---
status: accepted
revisit-after: 2026-11-01
---

# Eleven external skills are adopted as editable copies, over incumbent equivalents

Eleven skills — ten from `mattpocock/skills` plus `loopy` — are installed as
**editable copies** (`npx skills add --copy`), not as the auto-updating
marketplace bundle and not all 35 the repo now ships. Copies are pinnable and
diffable; `skills-lock.json` is tracked at the repo root and records source plus
content hash per skill, so the pin survives even though the bodies live under a
gitignored `.claude/skills/`.

**The uncomfortable half, recorded because §3.3 of the PRD never checked it:**
this install already carries superpowers, GSD, and built-in equivalents of
`code-review`, `tdd` and bug diagnosis. Three or four implementations of each
role now coexist. That is a real maintenance surface and it is the exact shape of
the sprawl this overhaul exists to remove.

**Why it is accepted anyway:** the eleven are what the qops design *routes
through* — `/wayfinder` for missions, `/to-spec` → `/to-tickets` for sorties,
`/triage`'s state machine for labels. The incumbents were never wired into a
workflow; these are. **The mitigation is the count, and the next reviewer should
check it:** eleven is a set one person can re-read. If a twelfth arrives without
displacing something, this ADR is being ignored.

**Displacement is owed, not done.** Nothing was uninstalled this session —
nothing is deleted before PRD Phase 3.
