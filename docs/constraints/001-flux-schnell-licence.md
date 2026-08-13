---
source: Black Forest Labs model licensing — FLUX.1 [schnell] is Apache-2.0; FLUX.1 [dev] is a non-commercial licence
verified-on: 2026-07-12
verify-by: 2027-01-31
---

# The printed artwork may only come from FLUX.1 [schnell]

Nobody chose this and there is no alternative to weigh: **[dev] carries a
different commercial licence**, and the artefact a buyer pays for is the one
thing in this project that must be unambiguously licensed for sale. Substituting
[dev] is not a tuning decision, it is a licensing change.

**Scope, exactly:** this governs `pipeline/generate.py` and nothing else. Mockup
**scene** generation is a separate concern with a different bar and its own
decision — `docs/adr/0008-scene-generation-not-bound-to-schnell.md`.

**How to re-verify:** re-read Black Forest Labs' licence page for both models and
diff it against this record. A licence change on [schnell] is the event that
matters; a change on [dev] is not, because we do not use it.

**Enforcement is owed, not in place.** Today this is held by `CLAUDE.md` alone,
which is a preference and not a control (GL-53). PRD v3 Phase 4's `guard.yml`
is what makes it a control: it asserts textually that no `FLUX.1 [dev]` string
reaches the generation path, and Phase 4's gate is proved by planting one.
