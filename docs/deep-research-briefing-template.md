# Deep-research briefing template (mode B: batch-ideation seam, R2-e)

Reusable prompt/protocol for a human-in-the-loop deep-research session
(Claude in Chrome / Cowork) that produces a batch of art briefs for the
qhoto_printshop pipeline's **mode B** input path
(`pipeline.seed_candidates.seed_candidates_from_briefs`). Mode A is the
autonomous cron research -> `art_brief.py` writer; mode B is this — a human
session with a stronger model and a browser, run before a validation batch,
not on a schedule. Paste the "Session prompt" section below into a fresh
Claude in Chrome / Cowork session as-is.

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

## What to produce: one brief per design idea

For each design idea, write a brief that would pass this repo's shared
brief-lint (`pipeline/brief_lint.py`) — mandatory fields, current wording
(subject to revision as the pipeline's own template evolves; if this doc and
`pipeline/art_brief.py`'s `ART_BRIEF_PROMPT_TEMPLATE` ever disagree, the code
is the source of truth):

1. **One concrete subject in a NAMED art idiom** (e.g. "mid-century modern
   botanical", "Bauhaus", "Japanese woodblock", "vintage herbarium" — never
   a generic phrase like "minimalist plant").
2. **A density/coverage clause** — the subject fills most of the frame, not
   floating in empty space ("dense full-frame composition" /
   "filling the frame edge to edge").
3. **Marked boldness** — "bold filled shapes" or "confident medium-weight
   lines"; never unqualified "line art" or "hairline strokes". If the niche
   itself says "line art", the boldness language must qualify that medium,
   not replace it.
4. **A focal-hierarchy subject** — name ONE primary subject and where it
   sits. If the composition has an enclosed opening or channel of negative
   space, either give it a small secondary occupant (butterfly, ladybug,
   dragonfly, single bloom, sun/moon — whatever fits the idiom) or close the
   composition over it. Never leave it for FLUX to fill with a floating orb.
5. **A ground**, optionally anchored by a backdrop device (arch, wash, band,
   sun disc, torn-paper edge…) — only for a SMALL, single-motif subject;
   dense full-frame compositions use none. When used, the shape sits behind
   and touching the subject, never floating in leftover space.
6. **2-4 named accent colors from exactly one palette family** — neutral
   (sage, olive, terracotta, dusty pink) or saturated retro (burnt orange,
   teal, mustard, deep green). Do not mix the two families in one brief.

Keep each brief to natural, flowing prose (no lists, no headings), ≤ 60
words if possible (75 is the outer ceiling — ask the pipeline maintainer
before assuming 75 is safe, it's gated on a token-budget test).

Never reference a named artist's style, a recognizable character/franchise/
logo, celebrity likeness, or describe the piece as hand-painted/one-of-a-kind
— it is a print reproduction (same no-go list as `art_brief.py`).

## Batch diversity (do this across the WHOLE batch, not per-brief)

A batch of N briefs must not let more than 2 briefs share the same backdrop
device (or "none") or the same palette family — this is the highest-signal
fix for round 1's monotony finding (FM-5), and it's exactly what a human
looking at all N ideas at once can do that the autonomous per-candidate
writer cannot. Before finalizing, scan your own batch: if 3+ ideas landed on
the same circle-backdrop + sage/terracotta combination, change some of them.

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
> fields: named art idiom, density/coverage clause, marked boldness, a
> focal-hierarchy subject with a rule for any enclosed negative space, a
> ground with an optional backdrop device only for small single-motif
> subjects, 2-4 named accent colors from one palette family). Across the
> whole batch, no more than 2 ideas may share the same backdrop device (or
> "none") or the same palette family.
>
> Reply with ONLY a JSON array of
> `{niche, trend_source, art_brief, go_hold_kill_rationale}` objects, no
> other text, no markdown fences.
