# Round-3 deep-research session prompt (mode B, comparative Etsy study)

Paste the prompt below into a **fresh Cowork session with Claude in
Chrome connected**, with the `qhoto_printshop` folder mounted. It runs the
owner-approved R3-e comparative study (see
`docs/2026-07-21-generation-quality-round3-plan.md` §3) and produces the 5
mode-B briefs for the round-3 validation split, loadable via
`python -m pipeline.seed_mode_b` (built in the round-3 code session —
if the CLI doesn't exist yet, save the JSON to
`docs/round3_mode_b_briefs.json` and stop; loading happens later).

---

## Session prompt (paste from here down)

You are running a comparative Etsy deep-research session for the
qhoto_printshop AI print-on-demand pipeline. Read first, in this order:
`CLAUDE.md`, `docs/deep-research-briefing-template.md` (the observation
protocol and output schema — if the round-3 code session has already
updated it to v3, follow that version), and
`docs/2026-07-21-generation-quality-round3-plan.md` §1–§3 (the round-2
scorecard, the current failure taxonomy, and what round 3 is fixing).

### Goal — comparative, not a fresh trait list

Two prior studies exist; this one is different: compare **what
bestseller-badged Etsy listings do** against **what our generated rounds
1–2 actually produced** (described in the round-2/round-3 plan scorecards —
work from those text descriptions, do not pull our images into the
browser). Focus on the trait axes where our batches are weakest:

1. **Secondary-subject integration** — when bestsellers include a small
   creature/motif, how big is it relative to the frame, where does it
   sit, is it physically connected to the main subject, static or in
   motion?
2. **Backdrop/badge devices** — how often do bestsellers use a backdrop
   shape (circle, arch, band, sun disc, badge), behind what kind of
   subject, at what subject scale? (Our usage went 8/10 → 0/10 across two
   rounds; the owner wants a calibrated middle.)
3. **Edge treatment** — do stem/botanical bestsellers run stems off the
   bottom edge, ground them, or float them with margins?
4. **Sparse-vs-dense** — when bestsellers go sparse, how large is the
   dominant subject? Does "one big subject + empty space" actually sell?
5. Anything else where the bestseller pattern clearly diverges from the
   round-2 batch descriptions.

**Every recorded trait MUST ship with its applicability condition** —
"backdrop circles appear behind X-scale subjects in Y-style listings",
never a bare "bestsellers use circles". A previous study's trait lost its
condition in translation and caused a full failure mode (FM-1); this is
the single most important protocol rule after the imagery rule below.

### Observation protocol — traits only (hard rules)

Same as `docs/deep-research-briefing-template.md`:

- Browse Etsy search with the Bestseller filter (`is_best_seller=true`)
  across the shop's niche families (mid-century modern botanical, art
  deco geometric, minimalist landscape, wildflower botanical, vintage
  herbarium, Japanese woodblock botanical — plus adjacent families you
  judge promising). Badge-carrying listings only.
- Record attribute-level observations **in text only**. Never save,
  screenshot, download, or embed any competitor image. Never name a
  shop, seller, or listing title in any output. Never describe a
  specific listing closely enough to reconstruct it — extract traits,
  not copies.

### Deliverable 1 — traits-delta memo

Write `docs/2026-07-21-round3-traits-delta-memo.md`: per trait axis above,
(a) the bestseller pattern WITH its applicability condition, (b) what our
rounds 1–2 did instead, (c) a one-line implication for brief-writing.
Keep it short — a page or two of prose, no image references.

### Deliverable 2 — 5 mode-B briefs (JSON)

Produce exactly **5** design briefs as a JSON array per the schema in
`docs/deep-research-briefing-template.md`
(`{niche, trend_source, art_brief, go_hold_kill_rationale}`,
`trend_source` prefixed `cowork_deep_research:`). Requirements:

- Each brief applies the memo's findings — especially integration
  (occupant scale/contact/pose), calibrated backdrop-device usage, and
  edge grounding. Follow the template's current mandatory-field wording
  (the v3 version if the code session has shipped it; the file on disk is
  the source of truth).
- Diversity across the 5: both palette families present; at most 2 share
  a backdrop device (a batch where 1–2 of 5 use one is the target — not
  0, not 4); at most 2 share a focal-subject type. Niches may be new
  (research-driven) rather than repeats of rounds 1–2.
- Briefs, never generation prompts: no FLUX/scaffold language, no
  negations, ≤ 60 words each (75 outer ceiling).

Save the array to `docs/round3_mode_b_briefs.json`. Then, if
`pipeline/seed_mode_b.py` exists in the repo, run
`python -m pipeline.seed_mode_b docs/round3_mode_b_briefs.json` (dry-run,
NO `--commit`), show me the preview table and lint findings, and stop —
I decide whether to commit. If the CLI doesn't exist yet, stop after
saving the JSON and tell me; the code session will load it later.

Do not touch any other pipeline code, the DB, or any live API in this
session.
