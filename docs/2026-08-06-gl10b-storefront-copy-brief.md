# GL-10b brief — QhotoArt storefront: copy, section naming, listing-copy spec, and the re-opened visual direction — 2026-08-06

The **remainder of GL-10** after GL-10a, for the shop **QhotoArt**. Covers
**About, policies, the pipeline section's name, and the per-listing
title/tag/description template the pipeline writes into** — plus, **re-opened by
owner decision 2026-08-06, the shop banner and shop icon, and with them the
brand's visual direction.**

**The banner and icon are back in scope, and so is the branding itself.**
GL-10a is **not frozen** and the live pair is reference material, not a
constraint. How far QhotoArt's storefront should sit from the Qrchard sheet —
applied to the letter, used as inspiration, or alluded to while the store takes
its own direction — is **an output of the research**, formalised as the D-A
decision in §2.2. The one invariant is a visible nod to Qrchard. **Nano Banana
Pro is on the table for the banner as a one-off**, with its role also decided by
the research (§7.3).

**Out of scope, decided 2026-08-06:** the **listing first image**. It is the
larger conversion lever, but it belongs to the mockup/scene layer (GL-6/GL-21),
is governed by the 2 % crop budget and `scripts/mockup_qa.py`, and folding it in
would blur a clean scope. Findings about it are *recorded and routed there* —
see §5 point 3.

**Status: brief only. Nothing is executed until this is signed off** (CLAUDE.md
§2.4). No live storefront write, no code change, no research pass.

**One-way-valve:** clear. Inputs are the owner's own brand sheet plus public
Etsy sources and public competitor storefronts. Output travels to the owner's
own Etsy shop. Safe.

---

## 1. Problem / success criteria

The shop is **QhotoArt** (registered name, one word — confirmed 2026-08-06, Q8;
neither GL-10a's "Qhoto Art" nor the live icon's "Qhoto-Art"). Every word-shaped
surface on it is Etsy default or absent: no About, two sections of which the
pipeline's is still called "Posters" (`shop_section_id` 59380312), no
announcement, and a listing-copy generator whose entire brand and SEO strategy
is one hardcoded phrase — `"AI-generated botanical/minimalist wall art poster
print, niche: {niche}"` in `DRAFT_TEXT_PROMPT_TEMPLATE`
(`pipeline/compliance_draft.py`). That template has no title formula, no tag
strategy, no section awareness, and no brand voice.

The banner and icon are a separate failure mode, and a worse one than first
assessed: the live pair is not merely untested treatment, it is **off-system
entirely** — a different name, mark, ground and palette from anything the brand
sheet defines (§7.0). Two questions follow, and only the research answers
either: how far the branding should sit from Qrchard (§2.2), and what treatment
actually works on a surface that sits in a grid of product-led ones.

**Success = five artefacts plus one sub-task, in this order:**

1. **A findings file** — a coded competitor rubric plus 10–15 evidence-backed
   rules, written so each rule names the surface it changes.
2. **A storefront checklist** — the exact text for About and policies, in a
   form the owner pastes into Shop Manager. GL-10's stated acceptance is a
   how-to/checklist, then the owner executes.
   **Includes the sub-task: the pipeline section's new name** (§3.1).
3. **A listing-copy template spec** — the replacement for
   `DRAFT_TEXT_PROMPT_TEMPLATE`, written as a spec for a later coding session.
   **That session, GL-10c, is now post-launch and outside GL-10** (§10).
4. **A banner/icon decision** — D-A resolved (§2.2), plus keep/adjust/rebuild
   and the Nano Banana role, all from the same findings (§7). Executed only if
   the answer is "change".
5. **A keyword delta** — the terms discovered by the bestseller sweep, each
   tagged trend-or-evergreen, proposed as edits to
   `docs/safe_evergreen_bucket.md` (evergreen) and to
   `collect_event_lookahead()`'s windows (seasonal). **Proposed, not applied** —
   that file is `research.py`'s live input and carries an owner-approval note in
   its header; changing it changes what the pipeline makes.

### Goal reframe — read this before the rubric

The original framing was "attract buyers and turn them into recurring
customers." **Recurrence is the weakest of the three goals and should not
anchor the research.** Repeat-purchase rates for wall art are structurally low:
a buyer fills a wall and the wall stays full. The levers that compound for a
POD art shop are **search rank, first-image conversion, basket size (series and
sets bought together), and follows/favourites that buy a second visit at a
seasonal moment.** Recurrence, where it exists at all, is a downstream effect of
selling in series — which is a *merchandising* decision, not a copy one, and it
lands on shop sections and the series-naming convention rather than on an email
list.

## 2. Brand latitude — what the research may and may not touch

**Revised 2026-08-06 (Q7), and the revision is large enough to be worth stating
plainly rather than editing in quietly.** An earlier draft of this section said
"adopt structural findings, reject aesthetic ones" and treated the Qrchard
palette and register as untouchable. **That is no longer the rule.** Owner
decision: *the sheet is the reference for Qrchard, the mother brand; Qrchard is
not meant to block optimised branding of its child brands.* GL-10a is **not
frozen**, and the live pair is reference material that may be diverged from
wildly.

So the aesthetic question is not a constraint on the research — **it is one of
the things the research is for.**

### 2.1 The one invariant

**A visible nod to Qrchard — a cue that reads as lineage to someone who has
seen the parent brand.** That is the whole of the lock.

**The two-toned "Q" is an example of such a cue, not the cue itself** (Q10,
2026-08-06). Any device that does the same job qualifies: a shared letterform
trick, a shared mark construction, a carried-through accent behaviour, a
retained type pairing. This matters most at A3, which would otherwise have been
"free rein except one specific mark" — a much tighter brief than intended.

**The bar, since "reads as lineage" is not self-evaluating:** the proposal must
be able to state *which* element carries the link and *why* someone who knows
Qrchard would catch it. A nod nobody can name is not a nod. Below that,
everything — ground, palette, typeface, register, mark construction — is in
play.

### 2.2 D-A — the aesthetic-latitude decision the research must return

A named decision with three levels, resolved by the findings and ratified by the
owner:

| Level | Meaning | Consequence |
| --- | --- | --- |
| **A1 — to the letter** | Qrchard's system applied as GL-10a did: Ink/Charcoal ground, Bone, Pine `#23402F`, Fraunces + Inter, badge geometry | GL-10a's assets stand; `verify.py` unchanged |
| **A2 — inspiration** | The register and family survive; specific values move — a lighter ground, a different accent, a different display face — while the sheet is still legibly the parent | `verify.py`'s constants are re-parameterised, its *structure* reused |
| **A3 — allusion only** | Storefront branding optimised for the store on its own terms; the Qrchard link reduced to a single nameable lineage cue (§2.1) | Substantially new asset work; `verify.py` largely rewritten |

**Default in the absence of a clear signal: A1.** Not because it is right, but
because it is the only one already built, verified, and free.

### 2.3 What the research still gets no vote on

Shorter than before, and none of it is aesthetic:

- **Prices.** Locked in SPEC_v4.11 §4 and load-bearing for the margin table.
- **The Qrchard nod** (§2.1).
- **Legibility.** Whatever the icon becomes, it must survive avatar size. This
  is a measurement, not a taste — see §7.2.
- **Anything CLAUDE.md marks as a hard constraint** — the schnell rule, the
  crop budget, the scene-word rule. None of these are storefront concerns, but
  a finding that implies one is out of GL-10's scope by definition.

### 2.4 The mean-reversion risk, which has not gone away

The original filter existed for a reason: market research pulls toward the mean,
and the Etsy mean for wall art is bright, high-contrast, emoji-heavy and shouty
about discounts. Removing the lock removes the guardrail with it. **The
replacement discipline is evidential, not categorical:** D-A must be argued from
*coded rubric fields* — how many top shops run dark grounds, what the light/dark
split is among bestsellers specifically, whether register correlates with sales
volume at all — and never from "this looked better." A finding that cannot be
expressed as a count does not move D-A.

Worth holding in mind while coding: **register may simply not correlate with
sales**, in which case D-A resolves to A1 by default and the differentiation
argument for a dark, calm storefront in a bright field gets stronger, not
weaker. "The mean is bright" is not evidence that bright wins.

### 2.5 Two brand facts the copy must carry regardless

- **QhotoArt is a child of Qrchard**, not a standalone. The About should survive
  a second Qrchard venture existing — true at every D-A level.
- **The shop's second line is the owner's own photography**, and unlike the
  earlier draft this is not a hypothetical: it already has its own live section
  (§3.1).

## 3. Sections — two, not a taxonomy

**Re-scoped 2026-08-06 (Q2 revised).** An earlier draft proposed a subject-based
taxonomy — "Botanical", "Celestial", "Minimalist Abstract". **Dropped from
GL-10.** The shop has exactly two sections and keeps them:

1. **"Framed Photography"** — the owner's own photography listings. Outside the
   pipeline entirely, and **its name is settled** (Q9, 2026-08-06).
2. **The pipeline section** — currently "Posters", `shop_section_id`
   **59380312**, where every generated listing lands via
   `etsy_shop_section_id` in `config/static_config.json`.

A subject taxonomy would require section-per-listing routing in the publish
path, which is code. **That, and GL-10c, move out of GL-10 to a post-launch
item** (§9) — the right call: neither is a launch blocker, and both are cheaper
once there are real listings and real traffic to route.

### 3.1 Sub-task — optimise the pipeline section's name

Small, concrete, and the one section deliverable inside GL-10. "Posters" is
generic. The name is a real ranking and browse surface: it appears in the shop's
left rail, in the section URL, and Etsy uses it as a relevance signal.

Constraints and inputs:

- **One name serving every generated listing** — botanical, celestial,
  minimalist abstract, mid-century, landscape. It must not narrow the shop to
  one niche, which rules out anything subject-specific.
- **Etsy caps section names at 24 characters** — verify in Layer 2 before
  committing, and check whether renaming a section changes its URL (if it does,
  renaming later has a cost, which argues for getting it right now while the
  shop has no traffic to lose).
- **Layer 1 codes competitor section names** (rubric row "Sections", §4) — this
  sub-task keys off that field directly.
- **It must pair with "Framed Photography"**, and that name does more work than
  it first appears. It is `[qualifier] + [medium]`, and its qualifier is
  **product-form, not subject** — *framed*. That gives the naming sub-task a
  pattern to match and a distinction to lean on: the two sections separate
  cleanly on **framed photography vs unframed generated prints**, which is a
  real difference a buyer cares about, rather than an arbitrary split. "Posters"
  currently states the form but not the medium, and states neither well.
  Candidates should complete the pair, not just improve one half of it.

Deliverable: 3–5 candidate names with the evidence for each, one recommended.
Owner renames it in Shop Manager — no API write, and `static_config.json`'s ID
is unaffected by a rename.

## 4. Research plan — three layers, in trust order

**Layer 1 — bestseller-first teardown (highest value, most mechanical).**
Sampling method set by owner decision 2026-08-06 (Q1), and it inverts the usual
order: **start from the posters that are actually selling, then walk back to the
shops behind them.** Not "shops that rank for terms we already use" — the point
is to *discover* keywords, not to confirm the ones in
`docs/safe_evergreen_bucket.md`.

Sequence:

1. **Find bestselling / high-volume poster listings** on Etsy — bestseller
   badges, high review counts, "X people have this in their cart", and Etsy's
   own popularity sorts. Cast wider than the current niches on purpose.
2. **Extract the keyword surface from those listings** — title tokens, tags,
   the subjects and styles that recur. This is the discovery output, and it is
   the input to artefact 5.
3. **Walk back to the 8–12 shops behind them** and code each on the fixed
   rubric below.

Driven through **Claude in Chrome** rather than plain fetch: Etsy's search
results and shop pages are client-rendered, and gallery ordering, review text,
the section rail, and the bestseller badges are precisely what a raw HTML fetch
loses.

**The bias this method carries, stated so it can be corrected for.** Bestsellers
skew toward established shops with review-count momentum and toward whatever is
currently trending — which is exactly the class of thing
`safe_evergreen_bucket.md` was written to *exclude* ("several POD niche
round-ups list trend items as evergreen — they aren't"). So a discovered
keyword is not automatically an evergreen one. **Every discovered term gets
tagged trend-or-evergreen before it can reach the bucket**, using that file's
own stated test: does it map to a stable aesthetic or universal subject with
roughly flat year-round volume. Trend-tagged terms are still useful — they
belong in `collect_event_lookahead()`'s seasonal windows, not the evergreen
list.

Each shop coded on the **same fixed fields** — a fixed rubric is what makes
this comparable rather than a vibes summary:

| Field | What gets recorded |
| --- | --- |
| First gallery image | flat art / framed-in-room / lifestyle / size-chart; crop; whether text is burned in |
| Gallery composition | image count, order, presence of size chart / detail shot / styling shot |
| Title pattern | token order, length, where the niche sits, separators used |
| Tags | count, long-tail vs head, overlap with title |
| Description skeleton | block order; where (and whether) the AI disclosure sits |
| Price ladder | price at each size, ratio between smallest and largest |
| Sections | count, naming pattern, whether series-based or subject-based |
| Series behaviour | are designs sold as sets/pairs; is there cross-linking |
| About | length, whether it exists, what questions it answers |
| Reviews | recurring themes, especially complaints about print/colour/size |
| Scale | listing count, sales count, shop age |
| **Banner treatment** | type-led / imagery-led / product-grid / photographic; ground light or dark; % of width carrying imagery vs type; is the shop name repeated in it; is there a tagline; any promo text |
| **Banner and icon coherence** | do the two read as one system; is the icon the banner mark or something else |
| **Icon treatment** | mark-in-ground vs mark-on-ground; wordmark vs symbol vs product photo; legible at 40 px (judged at actual avatar size, not zoomed) |
| **Shop-name-in-search** | how the icon+name pair reads in a search result row, where it is genuinely small |

The four rows above are the ones the banner/icon decision keys off. **They must
be coded at true display size**, not on a zoomed shop page — the whole GL-10a
icon finding (Pine-on-Ink at 1.6:1 collapsing to an "O" below 40 px) came from
measuring at real size, and coding these at 100 % zoom would reproduce exactly
the mistake that finding exists to prevent.

**Sampling rule:** shops reach the sample by being *behind a bestselling
listing*, never by looking nice. A sample chosen by taste measures the owner's
taste, which is already documented in the brand sheet.

**Layer 2 — Etsy primary sources.** Search-ranking documentation and the
Creativity Standards, from Etsy's own help/seller-handbook pages only. The SEO
blog ecosystem is recycled and gets used at Layer 3 or not at all.

> **Correction carried from the prior session:** this layer was going to be run
> jointly with GL-37. **GL-37 was answered 2026-08-06** and that overlap no
> longer exists — see §5.

**Layer 3 — best-practice literature**, used as a cross-check on Layers 1–2,
never as a source of rules on its own.

**Not a source: the current shop.** It is in Developer Mode with no
representative traffic (GL-11), so it is a *brand* reference and nothing more.
There are no first-party stats to mine and any drawn from pre-launch traffic
are invalid by GL-11's own note.

**Output shape:** the rubric table, filled, plus 10–15 rules each carrying (a)
the evidence behind it, (b) the surface it changes, (c) whether it is
structural or aesthetic per §2. Not a listicle.

## 5. Feeding findings back into generation — three named injection points

"Use the learnings" is unactionable. These are the three places a finding can
actually land, with the file that owns each:

1. **`pipeline/research.py` — what gets made at all.** Niches come from
   `docs/safe_evergreen_bucket.md` via `load_safe_evergreen_terms()`, from
   `collect_event_lookahead()`'s seasonal windows, and from the LLM search
   classifier. Market findings update the term list and the seasonal windows.
   Cheapest, highest leverage, zero risk to any other stage.
2. **`pipeline/art_brief.py` — what the artwork looks like.** Findings about
   which compositions convert become **traits and constraints inside the brief**
   (`ART_BRIEF_PROMPT_TEMPLATE`, currently `BRIEF_TEMPLATE_VERSION = "v2"`),
   never raw prompt strings appended downstream. Note `sanitize_niche()` and
   `SCENE_TOKENS` already exist to strip scene words — findings phrased as
   "shown on a gallery wall" will be stripped, correctly, and must be
   re-expressed as subject/style or routed to point 3 instead.
3. **The mockup/scene layer (GL-6/GL-21).** The first gallery image is the
   single largest conversion lever on Etsy and it is fully under our control via
   the compositor and the hand-authored scenes. Any Layer-1 finding about
   first-image treatment lands here, as a scene-authoring note — subject to the
   2 % crop budget and `scripts/mockup_qa.py` like every other scene.

**Two hard limits on all three.** Artwork generation stays **Replicate +
FLUX.1 [schnell]** — research can change *what we ask for*, never *which model*.
And **no scene words leak into artwork prompts**; that defect is what made the
first live run print lifestyle mockups as the artwork.

**Everything produced here is a prior, not a measurement.** The real feedback
loop needs post-go-live listing stats — views, favourites, conversion by
listing — which requires GL-11 done and listings live. That is a separate
project and should be filed as such rather than implied by this one.

## 6. The GL-37 constraint this brief inherits

GL-37 (answered 2026-08-06) established that Etsy's two Creativity Standards
fields — "How does your shop produce this item?" and "What tools are used?" —
are **not settable through the v3 API at listing or shop level**, and that the
web listing editor's only save action is *Activate with changes* (no
draft-save).

Three consequences that are GL-10b's problem, not GL-37's:

1. **The written AI disclosure is load-bearing, not decorative.** It is the only
   disclosure surface that is automatable. `DISCLOSURE_TEXT` in
   `compliance_draft.py` currently carries it; the new template spec must keep
   it and should treat its placement in the description skeleton as a
   *researched* decision (Layer 1 records where competitors put theirs).
2. **The About text is a second disclosure surface** and should carry the
   AI-generation statement plainly. Shop-level, set once, no per-listing cost.
3. **Ticking the structured field by hand is an activation.** So it cannot be
   framed in the checklist as "a quick tick before launch" — it publishes the
   listing. Sequencing belongs to GL-29/GL-11 and this brief must not quietly
   assume it away.

## 7. The banner and icon — re-opened, and research-gated

Owner decision 2026-08-06: both are back in scope, and **the role Nano Banana
Pro plays is itself decided by the teardown, not chosen up front.** This section
is the decision rule, written now so the findings resolve it mechanically.

### 7.0 The baseline — and a discrepancy worth resolving before anything else

Resolved 2026-08-06 (Q4). **Two different asset sets exist, and they are not
versions of each other — they are different brands.**

| | Live on Etsy | GL-10a deliverable |
| --- | --- | --- |
| Files | `assets/brand/etsy-banner.png`, `assets/brand/shop_icon.jpg` (added manually, untracked; file dates Nov 2025) | `qhoto-shop-banner-1600x400.png`, `qhoto-shop-icon-500.png` |
| Name | **"Qhoto-Art"** (hyphenated) | **"Qhoto Art"** |
| Mark | Q/A monogram on an easel | Qrchard badge geometry, Q-as-P |
| Ground | **Light** cream/bone | **Dark** Ink/Charcoal |
| Accent | none | Pine `#23402F` |
| Banner treatment | illustrated photo-studio scene, bright cool blue-grey, framed posters on a wall | type-led lockup on dark ground |
| Banner size | **1600 × 896**, **1.53 MB** | 1600 × 400, 101 KB |
| Icon size | 1200 × 1200 | 500 × 500 |

**Baseline for §7 = the live pair** (owner decision 2026-08-06, Q6). The GL-10a
assets were **never uploaded**, so the live "Qhoto-Art" banner and icon are what
a buyer actually sees and are therefore what any change is measured against.

> ⚠️ **This overrides my initial call and it carries an unresolved question —
> flagged rather than absorbed (CLAUDE.md §3).** The live pair contradicts the
> brand sheet on **name, mark, ground, and accent simultaneously.** GL-10a's
> entire premise was *"not a redesign — a brand application"*: applying
> Qrchard's documented system to Qhoto. If the live off-system pair is now the
> reference, then either (a) it is the baseline-to-beat and the brand sheet is
> still the target, or (b) the brand sheet's authority over the storefront is
> itself in question. **These lead to completely different work** — (a) is a
> comparison, (b) reopens GL-10a. See **Q7**; do not proceed past phase 1
> without it settled.

**Four observations that are findings in their own right, independent of any
research:**

1. **The live banner depicts a product line the shop does not sell.** The
   framed works in it are figurative and portrait-led — stylised faces,
   characters. The pipeline generates botanical/minimalist/celestial/abstract
   work off `docs/safe_evergreen_bucket.md`. A banner promising portraits above
   a grid of botanicals is a promise mismatch, and it is **structural, not
   aesthetic** — it survives the §2 filter regardless of what the teardown says
   about treatment.
2. **The live banner contains a visible generation artifact** — one framed
   poster carries garbled lettering ("O E M Y A I T"). Buyers read that as
   low-effort, and it sits in the largest brand surface on the page.
3. **The live icon will not survive avatar size.** It is a monogram stacked
   over a "Qhoto-Art" wordmark occupying the lower half. At 40 px the wordmark
   is noise. This is the same class of failure GL-10a measured and fixed —
   worth confirming by rendering both at true size side by side as the first
   step of the teardown, since the rubric's icon rows now require it anyway.
4. **Spec compliance is questionable on both.** The banner is **1.53 MB against
   Etsy's ~1 MB limit** as recorded in the GL-10a brief §3, and 1600 × 896
   matches neither the big-banner (1600 × 400) nor mini (1600 × 213) spec that
   brief verified. **Do not treat this as settled** — Etsy may have added a
   larger format since 2026-07; re-verify against Etsy's own help pages in
   Layer 2 rather than assuming either the old spec or the live file is
   correct.

**A third name, and it is the real one.** The live icon reads **"Qhoto-Art"**,
GL-10a wrote **"Qhoto Art"**, and the registered shop is **`QhotoArt`**
(confirmed 2026-08-06, Q8). All three exist in the wild simultaneously. **Copy
uses QhotoArt** — About, policies, listing titles — because that is what a buyer
sees in the shop URL and the search row. Whether the *wordmark* sets it as one
word, two, or hyphenated is a design question under D-A and can differ from the
registered string; what cannot differ is the copy.

### 7.1 What is actually being asked

Not "is the banner good" — it is on-system and verified. The question is
**whether a dark, type-led, gallery-register banner is the right treatment for a
surface that sits in a grid of product-led ones**, and the same for the icon at
40 px. Both are answerable from the four new rubric rows in §4.

### 7.2 What stays locked regardless of the answer

**Revised 2026-08-06 (Q7) — this list used to hold Pine, the badge geometry and
the typefaces. It no longer does.** They are now D-A-dependent (§2.2). What
survives:

- **The Qrchard nod** — one nameable lineage cue, of which the two-toned Q is
  an example (§2.1).
- **Legibility at avatar size.** GL-10a measured Pine-on-Ink at **1.6:1**, where
  the stem vanishes below 40 px and the mark reads as an "O" — the worst
  available failure, since "O" is what Qrchard's badge means. **The specific
  hexes are now negotiable; the measurement is not.** Any icon proposal, at any
  D-A level, is rendered at true avatar size and checked before it is judged.
  This is the finding most likely to be lost in a rebrand, because it is
  invisible at the size you design at.
- **Etsy's own specs** — dimensions and file size, re-verified in Layer 2 (see
  §7.0 observation 4).

**Two things that become *findings* rather than constraints**, and should be
carried into any A2/A3 work rather than discarded with the palette:

- The **Q-as-P letterform reasoning** in `badge.py`'s docstring — Qrchard is a
  Q masquerading as an O, Qhoto as a P; tail at 6 o'clock reads as an
  exclamation mark. Hard-won, and still true of any Q-based mark.
- **Generative models cannot reproduce measured geometry.** Whatever the mark
  becomes, it is drawn deterministically.

### 7.3 The Nano Banana decision rule

Three candidate roles. **The teardown picks between them; the owner ratifies.**

| Role | Chosen when the findings show | Cost to the locked set |
| --- | --- | --- |
| **A — ground/texture plate** | competitors' banners carry meaningful imagery (imagery-led or photographic in a clear majority), *and* the imagery is atmospheric rather than product | none — badge, wordmark and tagline still composite deterministically in SVG; `verify.py`'s palette and geometry assertions stay binding on everything that carries identity |
| **B — full generated banner** | competitors' banners are photographic and type-light, such that a composited wordmark would read as pasted-on | **high** — means dropping exact-hex and badge-geometry assertions for the banner. An explicit, recorded departure from GL-10a's locked decisions, requiring its own owner sign-off, not a consequence of this one |
| **C — concept exploration only** | banners are predominantly type-led, or the field is too varied to read a signal | none — nothing generated ships; chosen directions are rebuilt in SVG |

**Default if the signal is weak or split: C.** A tie is not a mandate to change
something that already passes 27 assertions.

**Role B halts (owner decision 2026-08-06, Q5).** Its rationale narrowed when
Q7 unlocked the palette, so restating what B now costs: not "it breaks locked
brand decisions" — those are open — but **it removes the deterministic
guarantee itself.** A generated banner cannot hold an exact value of *any*
palette, cannot reproduce a measured mark, and cannot be regenerated identically
later. That is a durable loss regardless of which D-A level wins, and it is why
the halt stands. A and C proceed without a stop.

**D-A and the Nano Banana role are separate decisions and must not be
collapsed.** D-A says how far the branding may move from Qrchard; the role says
how the banner is *produced*. A3 does not imply B — a wholly new visual
direction can still be drawn deterministically, and probably should be.

Two facts that travel with any of A/B, and neither is a blocker:

- **SynthID watermark.** Every Nano Banana output carries one. The licence bar
  is met — this is offline authoring input, a storefront asset, never a printed
  product, exactly the reasoning CLAUDE.md already records for scene generation.
  Worth *recording* on a brand asset, not worth vetoing one.
- **Aspect.** 1600×400 is 4:1, more extreme than anything the scene work has
  needed. CLAUDE.md's standing finding is that **aspect is specified with a
  geometry card, not with prose** — no image model reliably renders a stated
  ratio. So: a 4:1 geometry card passed as a reference image, or generate wider
  and crop deterministically. Not a prompt that says "4:1".

### 7.4 If the answer is "change"

Rebuild runs through the **existing GL-10a toolchain** — `build_final.py` and
`verify.py` in `assets/brand/`, which encode the specs, the circle-crop safety,
the banner safe zone, the legibility check and the downsampling method (4×
supersample + area-average; LANCZOS ringing broke the exact-palette requirement
and `verify.py` catches the regression).

**Under Q7 those assertions are parameters, not law.** At A2 the constants are
re-pointed at a new palette; at A3 much of `verify.py` is rewritten. What must
survive at every level is the *shape* of it — a build script that emits the
assets deterministically and a verifier that asserts specs, safe zones and
legibility, so the next change is measurable rather than eyeballed. **Losing the
verifier is the actual risk of a rebrand here**, not losing the palette.

Upload stays manual in Shop Manager; icon and banner are not API writes, so
nothing publishes without the owner doing it.

## 8. Phases

1. **Sign-off on this brief** — including §2's latitude framing and the D-A
   levels, which must be agreed *before* any finding is read.
2. **Layer 1 sweep** via Claude in Chrome — bestselling poster listings first,
   keyword surface extracted, then the ~10 shops behind them coded to the
   rubric. Raw coding saved as a data file, not prose.
3. **Layers 2–3**, the findings file assembled, and the keyword delta tagged
   trend-or-evergreen.
4. **D-A resolved** (§2.2) and the banner/icon decision put to the owner
   against §7.3. If D-A returns A1 and the decision is "keep", this phase ends
   here and costs nothing further.
5. **Storefront checklist** — About, policies, and the section rename
   candidates (§3.1), as paste-ready text. Owner executes in Shop Manager.
6. **Listing-copy template spec** written, and handed to the post-launch GL-10c
   item rather than built.
7. **Banner/icon rebuild**, only if phase 4 said change — through
   `build_final.py` + `verify.py`, owner uploads.
8. **Verification pass** — every rule re-checked against §2's latitude rules and
   CLAUDE.md's constraints; every D-A claim re-checked as a count rather than an
   impression, per §2.4.

Phases 4 and 7 are deliberately far apart. The decision is made while the
findings are fresh; the build waits until the copy work is done, so a
half-formed visual idea cannot quietly expand into a redesign — a risk that got
larger, not smaller, once Q7 unlocked the palette.

## 9. Definition of done

Findings file, storefront checklist (including the section-name recommendation),
listing-copy template spec, banner/icon decision with D-A resolved, and keyword
delta — all five in `docs/`. Every rule traceable to evidence, and every D-A
claim to a count. If the decision was "change", new assets pass a `verify.py`
that still asserts specs, safe zones and legibility — re-parameterised is fine,
absent is not. Nothing written to the live shop by this project — GL-10's
acceptance is that the owner executes. No pipeline code changed.

## 10. Deferred / explicitly out of scope

- **GL-10c — building the new listing-copy template. Moved out of GL-10
  entirely, to a post-launch item** (owner decision 2026-08-06). Touches
  `pipeline/compliance_draft.py`; a coding session with tests. GL-10b still
  *writes the spec* (artefact 3) — only the build moves.
- **Multi-section routing — same post-launch item.** Writing listings into
  different sections by subject means the publish path stops reading a single
  `etsy_shop_section_id` from `config/static_config.json`. Natural pair with
  GL-10c: both touch the publish/draft path, both are cheaper once there are
  real listings and real traffic to route. **Neither is a launch blocker**, which
  is the whole reason they move.
- **The listing first image** (owner decision 2026-08-06). The larger
  conversion lever, but it lives in the mockup/scene layer under the 2 % crop
  budget and `scripts/mockup_qa.py`. Findings about it are recorded and routed
  to GL-6/GL-21, never built here.
- ~~**Re-opening Pine, the badge geometry, or the typefaces.**~~ **No longer
  deferred — Q7 put all three in scope** as D-A-dependent (§2.2). Struck rather
  than deleted, because it was a stated constraint for part of this brief's
  life and the change of mind is the point.
- **Post-launch measurement.** Needs GL-11 done and listings live; the real
  feedback loop, and a separate item.
- **Series/set merchandising as a product change** (multi-print bundles as
  their own Gelato products). If Layer 1 says sets matter, that is a finding
  about the *roadmap*, not something GL-10b builds.
- **A Qhoto page on the brand sheet**, still open from GL-10a §8.
- **Applying the keyword delta.** Artefact 5 is a *proposal* against
  `safe_evergreen_bucket.md` and the seasonal windows. Editing them changes what
  the pipeline generates and needs its own owner approval, as the file's own
  header records.
- **Anything touching prices.** Locked in SPEC_v4.11 §4 and load-bearing for
  the margin table; a research finding about price ladders is input to a
  separate decision, not authority to change them.

## 11. Open questions for sign-off

### Answered 2026-08-06

- **Q1 — sampling and keywords. Discovery, not confirmation.** Start from
  bestselling posters, extract their keyword surface, then walk back to the
  shops. `safe_evergreen_bucket.md` is an *output* of this, not an input.
  Method and its bias correction: §4 Layer 1. New artefact 5.
- **Q2 — sections: subject-based *in principle*, but out of GL-10 in practice.**
  Superseded within hours of being answered, and worth keeping both halves.
  Subject-based is the eventual direction; **GL-10 keeps the two live sections
  and only optimises the pipeline section's name** (§3, §3.1). Multi-section
  routing is code — the publish path writes every listing into one
  `etsy_shop_section_id` — and it moves post-launch with GL-10c (§10).
- **Q3 — announcement bar: not used.** (It is the banner-width text strip at
  the top of an Etsy shop, typically used for sale messaging and shipping
  notices.) Default is off; if Layer 1 shows a strong structural use — dispatch
  times, size guidance — it can be revisited as a finding.
- **Q5 — role B halts** for a fresh decision. Applied in §7.3.
- **Q6 — GL-10a assets were never uploaded**; the live pre-GL-10a pair is the
  baseline. Applied in §7.0, and it raises Q7 below.
- **Q4 — answered:** the live pair (`assets/brand/etsy-banner.png` +
  `shop_icon.jpg`) is the reference. Recorded in §7.0.

- **Q7 — the brand sheet does *not* have blocking authority over the
  storefront.** It is the reference for **Qrchard, the mother brand**, and
  Qrchard is not meant to block optimised branding of its children. GL-10a is
  **not frozen**; the live pair is reference material that may be diverged from
  wildly. A nod — the two-toned Q or equivalent — is enough of a link.
  **How far to diverge is itself a research output**, now formalised as the D-A
  decision (§2.2). This rewrote §2 and §7.2, and it is the largest single change
  to this brief.
- **Q8 — registered shop name is `QhotoArt`**, one word. Neither GL-10a's
  "Qhoto Art" nor the live icon's "Qhoto-Art". All copy uses **QhotoArt**;
  whether the *wordmark* renders it as one word is a design question under D-A,
  not a naming one.

- **Q9 — the photography section is "Framed Photography"**, and settled. Not
  renamed by this brief; it becomes a *constraint* on §3.1 instead, since the
  new name has to complete that pair. Its `[qualifier] + [medium]` shape, with a
  product-form qualifier, is the pattern to match.
- **Q10 — the two-toned Q is an example of a lineage cue, not the cue.** §2.1
  and the A3 row rewritten accordingly; A3 is meaningfully freer than the
  earlier wording implied.

### Still open

Nothing blocking. The brief is ready for sign-off.

## 12. Execution venue (owner decision 2026-08-06)

**Phases 2–6: Cowork, and the sweep runs in a single session.** The research is
browser-driven and visually judged — banner treatment, icon legibility at true
avatar size, D-A — which needs images looked at and decisions put to the owner
mid-stream. Same reasoning that put GL-10a here.

**Phase 7 (rebuild, only if phase 4 says change): Claude Code.**
`build_final.py`, `verify.py`, cairosvg/numpy/Pillow, iterate until the
assertions pass, commit. A repo test loop, and cheaper there. **The handoff is
safe because phase 7's input is a decision document** — D-A level, chosen
treatment, target values — not accumulated conversational context. Same for the
post-launch item (GL-10c + multi-section routing): Claude Code, unambiguously.

### 12.1 One session for the sweep — what that requires

Owner decision: **do not split the Layer 1 sweep across sessions.** D-A is a
comparative judgement across the whole sample, and a single session keeps every
shop in one head. The cost is context: ~10 shops of browsing is the heaviest
thing in this brief. Four disciplines make it viable, and they are part of the
plan rather than nice-to-haves:

1. **Write each shop's rubric row to the data file the moment it is coded.**
   Not a splitting mechanism — **crash insurance.** If the session dies at shop
   7, six rows survive and resuming is cheap *because the rubric is fixed*.
2. **Text over pixels by default.** Page text for the copy/structure rows;
   screenshots only for the four visual rows (banner treatment, banner/icon
   coherence, icon treatment, shop-name-in-search), and one per shop, not one
   per page.
3. **Terse structured rows, not prose.** The rubric is a table. Narrative
   summaries per shop are the main avoidable cost, and they get written once at
   the end, from the data file.
4. **Hard cap at the sample size, and no wandering.** Discovery pass first
   (bestsellers → keyword surface → shortlist), then code the shortlist. Do not
   follow interesting shops found mid-sweep; note them for a later pass.

**If context runs short anyway, it degrades gracefully rather than failing** —
the data file is the deliverable, and a continuation session reads it instead of
re-browsing. That is the safety net; it is not the plan.

## Sources
- Local: `docs/2026-07-24-gl10a-store-visual-identity-brief.md`,
  `assets/brand/README.md`, `Qrchard/brand_sheet.pdf`, `assets/brand/badge.py`,
  `assets/brand/verify.py`
- Local: `docs/2026-07-22-go-live-plan-of-attack.md` (GL-37 row, GL-29 row,
  GL-11 row), `.qops/issues.md` (GL-10 acceptance)
- Code: `pipeline/compliance_draft.py`, `pipeline/research.py`,
  `pipeline/art_brief.py`
