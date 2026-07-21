# Deep-research briefing template (mode B: batch-ideation seam, R2-e; v3 wording per R3-d)

Reusable prompt/protocol for a human-in-the-loop deep-research session
(Claude in Chrome / Cowork) that produces a batch of art briefs for the
qhoto_printshop pipeline's **mode B** input path. Mode A is the
autonomous cron research -> `art_brief.py` writer; mode B is this — a human
session with a stronger model and a browser, run before a validation batch,
not on a schedule. Paste the "Session prompt" section below into a fresh
Claude in Chrome / Cowork session as-is.

To load the resulting JSON into the pipeline, use the R3-d seam CLI —
`python -m pipeline.seed_mode_b <briefs.json>` — which previews the batch
(niche/palette/backdrop/occupant/word-count table) and prints all lint
findings, then stops; add `--commit` only after reviewing the preview. It
is a thin wrapper around `pipeline.seed_candidates.seed_candidates_from_briefs`
(the actual insert path) and never forks it.

Everything this session produces is a **brief**, never a generation prompt.
`generate_for_candidate` builds the actual FLUX prompt from `art_brief` +
its own positive scaffold + token budget — this session must not try to
write scaffold language, negative instructions, or anything FLUX-specific.
Its only output is the JSON array at the bottom.

---

## Etsy observation protocol — traits only, never save competitor imagery

Same rule as the pipeline's own S4-a bestseller trait study
(`docs/2026-07-20-s4a-failure-taxonomy.md` section 2): observing what sells
well on Etsy is legitimate research; copying it is not, and storing it
creates a real legal/reputational liability this project does not need.

- Browse Etsy (search + the `is_best_seller=true` filter) for the niches
  you're researching. Look at listings that carry Etsy's actual Bestseller
  badge — badge-carrying only, not just top-of-search.
- Record **attribute-level observations in text only**: composition style,
  subject type, coverage/density, line weight vs. filled shapes, palette
  family, backdrop device (or none), named art idiom. Never describe a
  specific listing closely enough that it could be reconstructed or
  attributed — you are extracting a *trait*, not a *copy*.
- **Never save, screenshot, download, or embed any competitor image** in
  your notes or in the output. If a tool you're using auto-captures
  screenshots, discard them before finishing — they must not end up in this
  repo or in the JSON output.
- Do not reference a specific shop name, listing title, or seller in the
  output JSON — the `art_brief` and `go_hold_kill_rationale` fields describe
  a *pattern you observed*, not a specific competitor's product.

### Comparative-trait protocol: every trait ships WITH its applicability condition

This is the round-1 lesson (FM-1): a bare "bestsellers use circles" is not
a usable trait — it caused a prior failure mode when a demoted-but-still-
bare rule swung to the opposite extreme instead. A trait is only useful
written as **"[pattern] appears when [condition]"** — e.g. "a sun-disc
backdrop appears behind sparse/atmospheric single-subject scenes, never
behind a dense full-frame composition." Every trait you record in your own
notes, and every pattern that shapes an `art_brief` or a
`go_hold_kill_rationale` below, must carry its condition explicitly. See
`docs/2026-07-21-round3-traits-delta-memo.md` for a worked example of this
protocol applied across 5 axes (secondary-subject integration, backdrop
devices, edge treatment, sparse-vs-dense, palette/boldness lanes).

## What to produce: one brief per design idea

For each design idea, write a brief that would pass this repo's shared
brief-lint (`pipeline/brief_lint.py`) — mandatory fields, current wording
(subject to revision as the pipeline's own template evolves; if this doc and
`pipeline/art_brief.py`'s `ART_BRIEF_PROMPT_TEMPLATE` ever disagree, the code
is the source of truth):

1. **One concrete subject in a NAMED art idiom** (e.g. "mid-century modern
   botanical", "Bauhaus", "Japanese woodblock", "vintage herbarium" — never
   a generic phrase like "minimalist plant").
2. **A density/coverage clause, conditional (FM-13):** EITHER a dense
   full-frame composition ("filling the frame edge to edge") OR one large
   dominant subject holding generous, intentional empty space (optionally on
   a badge/backdrop) — both are legitimate. The invalid combination is a
   *small* subject stranded in a *mostly empty* frame; a large subject with
   calm space around it is not a defect.
3. **Marked boldness** — "bold filled shapes" or "confident medium-weight
   lines" (or a close variant — the lint's boldness check now matches
   families of phrasing, not one fixed string); never unqualified "line art"
   or "hairline strokes". If the niche itself says "line art", the boldness
   language must qualify that medium, not replace it.
4. **Occupant conditionality + integration vocabulary (FM-7, FM-11):** name
   ONE primary subject and where it sits. A secondary occupant is a
   deliberate, CONDITIONAL choice, not a default — use one only when the
   composition has a natural opening AND an occupant genuinely improves it;
   "the composition closes over it" and "no secondary subject" are both
   valid, stated choices. When you do use an occupant, state all three:
   (a) **relative scale in positive terms** ("large enough to read across a
   room", "spanning a third of the frame width" — err bigger, not smaller);
   (b) **physical contact in verbs** ("legs gripping the stem", "feet on the
   path") OR a **dynamic in-flight/mid-motion pose** if it has no natural
   perch (prefer motion over a static perch for airborne creatures); (c)
   **anatomical completeness/symmetry** ("both wings spread symmetrically").
   Never describe the *shape of the surrounding negative space* itself
   ("triangle gap", "rectangular opening") — FLUX renders shape-words for
   emptiness as literal drawn geometry; describe the occupant's position
   relative to the surrounding subject matter (stems, fronds, petals)
   instead.
5. **Bottom-edge grounding (FM-9), for stem/bouquet/herbarium-native
   subjects:** state explicitly how the composition meets the frame's lower
   edge — either grounded ("stems rooted at and running off the bottom
   edge", no bottom margin — meadows/bouquets) or deliberately floated
   ("even margins on all four sides" — a single cut-specimen plate). Never
   leave grounding unstated; schnell reverts to a lopsided one-sided blank
   band when it is.
6. **A ground, with a backdrop-device rebalance (FM-10):** a backdrop device
   (badge, arch, wash, band, sun disc, torn-paper edge…) is a positive,
   encouraged choice for SOME designs — not banned, and not mandatory. Use
   it on sparse or single-subject compositions (including behind a large
   dominant subject, per point 2), sitting behind and touching the subject,
   never floating in leftover space; dense full-frame compositions still use
   none. Across a batch, this should land at roughly 1-in-5 to 2-in-5
   briefs, not 0 and not most of them (see the batch-diversity section).
7. **2-4 named accent colors from exactly one palette family** — neutral
   (sage, olive, terracotta, dusty pink) or saturated retro (burnt orange,
   teal, mustard, deep green). Do not mix the two families in one brief.

Keep each brief to natural, flowing prose (no lists, no headings), ≤ 60
words if possible (75 is the outer ceiling — ask the pipeline maintainer
before assuming 75 is safe, it's gated on a token-budget test).

Never reference a named artist's style, a recognizable character/franchise/
logo, celebrity likeness, or describe the piece as hand-painted/one-of-a-kind
— it is a print reproduction (same no-go list as `art_brief.py`).

## Batch diversity (do this across the WHOLE batch, not per-brief)

The lint's diversity caps scale with batch size (not a fixed "2" regardless
of N): roughly, no palette family should cover much more than half the
batch, and no single backdrop device should cover much more than 30% of it
— this is the highest-signal fix for round 1's monotony finding (FM-5), and
it's exactly what a human looking at all N ideas at once can do that the
autonomous per-candidate writer cannot. Before finalizing, scan your own
batch: if most ideas landed on the same circle-backdrop + sage/terracotta
combination, change some of them. `pipeline.seed_mode_b`'s preview + lint
output will flag both an over-concentrated palette/device split (errors)
and the backdrop-device floor/ceiling on batches of 6+ (warnings — see point
6 above: 0-in-N is now flagged same as most-of-N).

## Output: JSON array, one object per design

Emit **only** a JSON array (no markdown fences, no commentary before/after)
of objects shaped exactly:

```json
[
  {
    "niche": "mid-century modern botanical",
    "trend_source": "cowork_deep_research:2026-07-21_mcm_botanical_bestseller_cluster",
    "art_brief": "A mid-century modern botanical bouquet in bold filled leaf shapes, dense full-frame composition, a small yellow finch tucked in the lower-left negative space, warm cream ground, sage and terracotta accents.",
    "go_hold_kill_rationale": "Bestseller-badge cluster observed across 6+ MCM botanical listings, BE locale; strong overlap with the round-1 confirmed-good niche family."
  }
]
```

Field notes:
- `niche` — short keyword phrase, same shape as mode A's research niches.
- `trend_source` — a short machine-readable tag identifying this as a
  Cowork/deep-research origin (`cowork_deep_research:<slug>` convention),
  distinct from mode A's `trending_now:`/`event_lookahead:`/
  `telegram_on_demand:` prefixes.
- `art_brief` — the finished brief text (see field list above). This is
  persisted verbatim to `candidates.art_brief` and used exactly as mode A's
  Haiku-written briefs are — no special-casing downstream.
- `go_hold_kill_rationale` — one sentence: why this idea, what you observed
  that supports it. Folded into `trend_source` on ingest (no dedicated
  column yet) — keep it short.

---

## Session prompt (paste this into Claude in Chrome / Cowork)

> You are researching Etsy for print-on-demand wall art design ideas for a
> shop selling AI-generated flat 2D poster artwork (FLUX.1 schnell,
> Replicate). Browse Etsy using the Bestseller-badge filter
> (`is_best_seller=true`) across [FILL IN: the niche families to research,
> e.g. "mid-century modern botanical, art deco geometric, minimalist
> landscape, wildflower botanical, Japanese woodblock botanical"]. For each
> badge-carrying listing you look at, record attribute-level traits only —
> composition, subject, coverage/density, line weight, palette, backdrop
> device — in your own notes. **Never save, screenshot, or embed any
> competitor image; never name a specific shop or listing in your output.**
>
> Produce [FILL IN: N] design ideas as art briefs, following the field list
> and diversity rule in `docs/deep-research-briefing-template.md` (mandatory
> fields: named art idiom; a conditional density clause — dense full-frame
> OR one large dominant subject with generous empty space, never a small
> subject in an empty frame; marked boldness; a focal-hierarchy subject,
> with any secondary occupant used conditionally and given explicit scale,
> physical-contact/motion, and anatomy wording — never describing the SHAPE
> of the negative space around it; bottom-edge grounding stated explicitly
> for stem/bouquet/herbarium subjects; a ground with a backdrop device used
> on roughly 1-in-5 to 2-in-5 sparse/single-subject briefs, never 0 and
> never most of them; 2-4 named accent colors from one palette family).
> Record every observed trait WITH its applicability condition (a pattern
> plus WHEN it applies, never a bare rule). Across the whole batch, keep
> palette families roughly balanced and don't let one backdrop device (or
> "none") dominate.
>
> Reply with ONLY a JSON array of
> `{niche, trend_source, art_brief, go_hold_kill_rationale}` objects, no
> other text, no markdown fences.
