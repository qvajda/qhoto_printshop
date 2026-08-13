---
status: accepted
revisit-after: 2027-02-01
---

# Mockups are composited in-repo with OpenCV, and the compositor is never worked around

`pipeline/mockup_render.py` warps the artwork onto an authored quad and reveals it
through a matte. The alternative — a mockup service or Gelato's own scene
previews — was rejected because the defects that matter here are sub-pixel seam
artefacts that no vendor exposes a control for.

**The standing rule this ADR exists to hold:** if the composite is wrong, fix the
compositor and add a test; never work around a compositor defect from inside a
bundle. GL-6 attempt 2 honoured a freeze over a measured border defect and
repainted the photograph over every print's outer 3 px — trading a dark hairline
for a bright one across four bundles. The freeze is lifted; if a constraint blocks
the correct fix, flag it and stop.

**Consequences worth stating:** the colour warp uses `BORDER_REPLICATE` while the
mask warp stays `BORDER_CONSTANT`; `overlay.png` may only paint where the print
is; `overfill` is deprecated for matte bundles; and authoring is gated by
`scripts/mockup_qa.py` before any owner review.
