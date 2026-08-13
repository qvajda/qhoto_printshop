---
status: accepted
revisit-after: 2026-11-01
---

# Scene generation is not bound to the artwork's model licence

Mockup **scenes** are generated with Nano Banana Pro (`google/nano-banana-pro`),
not with FLUX.1 [schnell]. A scene is offline authoring input — a photograph of a
room, never a printed product a buyer pays for — so the bar is "commercial use
permitted", not "Apache-2.0 weights". Owner decision, 2026-07-29.

**Why schnell could not do the job, measured rather than argued:** it ignores
stated proportions (54 of 61 images in the P4b1 batch failed `aspect`; the 10x24
group went 0/18 with a minimum gap of 0.20 against a 0.02 budget) and it has no
negative channel, so "no mat, no glazing" reliably summons both.

**Two things this carries.** Every Nano Banana output has a **SynthID
watermark**. And scene generation is hand-run by the owner into
`assets/mockups/inflow/` — there is no batch harness and it does not need one,
because the only reason `scene_generate.py` existed was schnell needing ~60
attempts per usable scene.

**This ADR governs scenes and nothing else.** The artwork constraint is a
licence boundary, not a decision — see `docs/constraints/001-flux-schnell-licence.md`.
