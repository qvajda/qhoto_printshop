# Post-test remediation plan — consolidated (2026-07-20)

Supersedes and merges two docs into one source of truth:

- `docs/2026-07-19-post-test-remediation-plan.md` (the four post-E2E findings +
  execution order), and
- `docs/2026-07-20-s4a-failure-taxonomy.md` (the executed S4-a instrumentation +
  Etsy bestseller trait study — the refinement of Finding 4's S4-a).

The S4-a stub in the 2026-07-19 plan is now replaced in place by the executed
taxonomy (§ "Finding 4 → S4-a"), and that taxonomy's §3 recommendations are
threaded directly into S4-b / S4-c / S4-d below. The two source docs are kept
for provenance; this consolidated doc is what an executing session reads.

Scope: the four findings from manual testing + Etsy/Gelato inspection after the
E2E live run (`docs/e2e_live_run_runbook_2026-07-18.md`). Grounded in the code
at commit `b2a3fe9` and SPEC_v4.11.

Conventions for the executing session: follow CLAUDE.md (no live Gelato/Etsy/
Replicate calls without explicit go-ahead, commit per passing stage, dry-run
flags while iterating). Where this plan says "verify live", that is a named,
user-gated call per the runbook's protocol.

---

## Finding 1 — Variant/listing split (ISO sizes in one listing, 5x7 in another)

### Root cause — CONFIRMED: this is spec-intended behavior, not a bug

The observed state (8x12/A3/A2/A1 as variants of one listing, 5x7 as its own
listing) is exactly what SPEC_v4.11 and CLAUDE.md specify:

- CLAUDE.md hard constraint: "**One Etsy listing per aspect-ratio group**,
  sizes are variants (v4.11)" — three groups: primary (ISO ratio), 5x7, 10x24.
- SPEC_v4.11 §1 (group table), §3 step 7, and decision **D6** (§9): the split
  was an explicit, argued decision, not an accident.
- Code implements it faithfully: `publish_primary_group.py:81` publishes
  `aspect_ratio_groups["primary"]` as one product; `publish_group.py` +
  `group_product.py` give 5x7/10x24 their own single-variant product → own
  Etsy listing.

So the remediation question is really a **design decision reversal**, and the
original rationale needs to be weighed before any code changes:

1. **Shipping profiles.** Etsy allows exactly one shipping profile per
   listing. 5x7 maps to "Small Posters" (€12.44); everything else to "Large
   Posters" (€14.55). Merging means 5x7 buyers get charged Large shipping
   (+€2.11 on a €19 entry-price item) or the margin absorbs it.
2. **Aspect-ratio crops.** 5x7 (1:1.385) and especially 10x24 (1:2.4) render
   a different crop of the artwork than the ISO group. The per-group review
   gates (own critic pass + own Telegram approval, SPEC §3 step 7) exist
   because those crops can genuinely fail on a composition that passed at ISO.
3. **Gelato product structure.** One Gelato product ↔ one Etsy listing. A
   merged listing = one product carrying all sizes' variants; the current flow
   creates the 5x7/10x24 products only *after* their independent approvals.

### Proposed fixes (pick one — decision gate, see Open questions)

- **Option A — keep the split, close as by-design (S).** Optionally add a
  "also available in 5x7 / panoramic" cross-link line to each description.
  Zero risk; the finding is resolved by documentation.
- **Option B — merge 5x7 into the primary listing, keep 10x24 separate (M).**
  5x7's ratio is close to ISO (1.385 vs 1.414 — a sliver of crop), so its
  review gate adds little; 10x24 genuinely differs and keeps its own listing.
  Requires: add 5x7 to `aspect_ratio_groups["primary"]` in
  `config/static_config.json`, collapse the 5x7 group flow, accept the
  shipping compromise (5x7 rides the Large profile), migrate DB rows, update
  SPEC to v4.12 + CLAUDE.md constraints FIRST (same sequencing lesson as the
  2026-07-16 brainstorm: never leave hard constraints contradicting the code
  being written).
- **Option C — one listing per design, all six sizes (L).** What the finding
  literally asks for. Everything in B plus: the 10x24 review gate has to move
  *before* first publish (all crops reviewed up front, delaying time-to-list)
  OR be dropped; adding a variant to an already-published Gelato product on
  late approval has **no known API** (likely delete+recreate → a NEW Etsy
  listing, losing views/favorites accrued); single shipping profile for all
  sizes; gallery mixes three aspect ratios. Interacts badly with Finding 2
  (more variants → more near-duplicate mockups).

### Effort / Priority

- Effort: A = S, B = M, C = L.
- Priority: **4th of 4.** Revenue impact is speculative; every option except A
  reopens the v4.11 migration that just stabilized.

### Open questions for the executing session

- **Decision gate (owner):** which option? The finding contradicts D6/SPEC
  v4.11 — per the project's own contradiction rule this must be resolved
  explicitly, not silently patched. Recommendation: A now, revisit B with
  real sales data at M3; C only if conversion data shows split listings
  measurably hurt.
- If B/C: verify whether Gelato supports adding variants to an existing
  product (dashboard + API probe) before designing the flow.
- If B/C: confirm Etsy keeps listing history when Gelato replaces a product.

---

## Finding 2 — Duplicate gallery images on the ISO listing

### Root cause — HYPOTHESIZED (high confidence), partially linked to #1

**No image curation or dedup logic exists anywhere in the pipeline.**

- `group_product.py:291-298`: every `productImages` entry Gelato returns is
  inserted verbatim into `product_images` (ordered only by `isPrimary`).
- `patch_etsy_listing` (`group_product.py:309-373`) patches text + inventory
  **only** — it never touches listing images. The Etsy gallery is whatever
  Gelato pushed.
- `etsy_client.py` has `upload_listing_image` but no list/delete image ops —
  the pipeline *couldn't* curate the gallery today even if it wanted to.

For a 4-variant product, Gelato renders a mockup set per variant of the same
artwork → one near-duplicate per variant, which Gelato pushes straight into
the Etsy gallery. So: a *symptom* of multi-variant products (hence correlated
with #1), but **not fixed by any #1 option** — Option A keeps 4 variants,
B/C increase them. Dedup is needed regardless.

Verify first: one read-only `get_product` on the live primary product;
confirm `productImages` count ≈ per-variant mockups and identify which are
near-identical.

### Proposed fix

Add a **gallery-curation step** inside the listing patch:

1. Perceptual-hash dedup (PIL is already a dependency; dhash/average-hash
   with a small Hamming threshold) across `productImages` — keep the flat
   mockup + each *visually distinct* lifestyle shot, drop near-dupes.
2. Extend `etsy_client` with `get_listing_images` + `delete_listing_image`
   (both exist in Etsy v3), and delete the duplicate images Gelato pushed
   during `patch_etsy_listing` — same patch-not-create posture as v4.11.
3. Dedupe `product_images` rows too, so critic galleries, digests, and
   alt-text counts (`compliance_draft.update_gallery_alt_text` asserts
   alt_texts == gallery length) stay consistent.

### Effort / Priority

- Effort: **S–M** (M if Gelato re-syncs images — see below).
- Priority: **3rd of 4.** Buyer-facing polish; cheap; independent of #1's
  decision.

### Open questions

- Does Gelato's sync *re-add* images to the Etsy listing after we delete
  them (periodic re-sync)? Needs one live create→patch→wait→inspect cycle.
  If yes, curation must instead happen Gelato-side (check dashboard mockup
  settings) or run periodically.
- Confirm Etsy image-delete keeps gallery order stable / primary image first.

---

## Finding 3 — Silent JSON-parse crash on empty Anthropic response body

### Root cause — CONFIRMED masking layers; trigger conditions hypothesized

Two code layers convert an empty/textless Anthropic response into a crash far
from its cause, and broad retry/except loops then swallow that crash:

1. **`http.py:67-70` (`send`)**: `if not raw_body: return {}` — a 2xx with an
   empty body silently becomes `{}`. This is the core mask: no log, no error,
   no request-id captured.
2. **`anthropic_client.py`**: `result.get("content", [])` on `{}` → zero text
   blocks → `text == ""` → `parse_json_response("")` →
   `json.JSONDecodeError` raised from a completely different module.
3. **Swallowers**: `compliance_draft.build_compliance_draft` retries any
   `Exception` up to 3× with the error fed back as "feedback" (a JSON parse
   error is not model feedback); `publish_primary_group.attempt()` runs
   twice (`try: attempt() except: attempt()`); every `run_*_cycle` loop
   catches `Exception` and `print`s. Net effect: the "retry once and hope"
   behavior observed.

**Likely trigger conditions to verify** (the "empty body" may actually be an
empty *text* at either of two layers):

- **No-text-block responses (most likely):** `research_web_search` uses the
  server-side web-search tool. A turn can legally end with
  `stop_reason: "pause_turn"` (long tool turn) or `"max_tokens"` (2048 cap
  eaten by search-result blocks) — content then contains tool blocks but **no
  text block**, producing `text == ""` with a perfectly healthy HTTP body.
  Note `WEB_SEARCH_TOOL_TYPE` is still flagged UNVERIFIED live
  (`anthropic_client.py:30-33`).
- **Transport-level empty body (less likely):** connection/stream reset after
  headers on the shared `httpx` HTTP/2 client. Distinguishable only with
  logging (layer 1 below).
- Rate limits/overload (429/529) are *not* this bug — they raise `HTTPError`.

### Proposed fix — validation + typed errors + logging, no new retry wrapper

1. **`http.send`**: never return `{}`. Raise `EmptyResponseBodyError(status,
   headers)` capturing `request-id` / `cf-ray`; log it. Callers that
   legitimately expect empty bodies (none found today) opt in explicitly.
2. **`anthropic_client`**: validate the envelope after every call — require
   `type == "message"`; record `stop_reason` + `usage`; raise
   `TruncatedResponseError` on `stop_reason == "max_tokens"` (actionable:
   raise the cap), handle `pause_turn` by continuing the turn (resend with
   the returned content, per API docs), raise `NoTextContentError` (listing
   the content-block types actually returned) when text blocks are absent.
3. **`parse_json_response`**: wrap `json.loads` and raise a typed
   `MalformedJSONError` carrying the first ~200 chars of the offending text.
4. **Centralize retry policy**: retry only transient classes (timeouts,
   5xx/429/529, honoring `retry-after`) with exponential backoff, in ONE
   place; validation errors from 1–3 must propagate, not loop.
   `compliance_draft`'s 3-attempt loop then catches only
   `ValueError`/`MalformedJSONError` (real model-output problems it can feed
   back), not bare `Exception`.
5. **Structured call log**: append every Anthropic call's request-id,
   stop_reason, and token usage to a small DB table (or logfile) so the next
   occurrence is diagnosable from data instead of reproduction.

Alternative worth flagging (tool-fit): swap the three raw-HTTP Anthropic call
sites to the official `anthropic` Python SDK, which does typed errors,
retries, and `retry-after` natively. The repo's raw-httpx posture exists for
Cloudflare-1010 reasons on *Gelato/Etsy* traffic — the Anthropic API doesn't
need the shared-client trick, so the SDK is admissible here and deletes most
of steps 1–4's custom code. Decide by preference; either path satisfies the
finding.

### Effort / Priority

- Effort: **S–M** (SDK path S; hand-rolled path M).
- Priority: **2nd of 4.** Every stage (research, compliance, both critic
  passes) routes through these call sites; silent `{}` corrupts runs and
  wastes the retry budget that Finding 4 depends on. **This is why it is
  sequenced first in the execution order** — S4-a's live-critic re-run and the
  final 10-candidate validation are both poisoned by silent `{}` responses.

### Open questions

- Reproduce once with layer-5 logging enabled to confirm which layer is
  actually empty (HTTP body vs text blocks). The live traceback from the
  original incident is in session memory (`.remember/`), not the repo —
  the executing session should ask the owner for it if available.
- Verify current `web_search` tool type string + `pause_turn` semantics
  against current Anthropic docs while in there (clears the standing
  UNVERIFIED marker).

---

## Finding 4 — Generated art quality (HIGHEST PRIORITY)

### Evidence from the repo

- Runbook Step 1b: **all 7 queued candidates from run #1 were condemned by
  the owner's artwork review** — the failure rate is real and owner-judged,
  not just gate-judged.
- Known failure modes already caught and patched piecemeal: near-empty cream
  canvases (masters 2 & 6 — the sanity-gate calibration set,
  `critic_pass.py:39-45`), lifestyle-mockup scene leak (H5 "prevent" commit
  `36a57bd`), malformed/hybrid subjects (H5 rubric extension `451d1cb`).
- `critic_pass_attempts` was **empty** before the E2E (runbook: "the critic
  rubric and the local sanity gate have never run live") — so there is no
  data yet showing the gates fail *good* candidates. Owner condemnation of
  all 7 points the finger primarily at **generation**, not gating.

### Root causes (ranked, with code evidence)

**RC-A — Low-signal prompts (research→generation seam). Confirmed by
reading; highest impact.** `build_prompt` (`generate.py:50-55`) injects a raw
research artifact into a fixed scaffold. But the "niche" is an *Etsy SEO
keyword* (`research.py`: trending-now keywords, or literally
`"botanical/minimalist nature illustration - fall_cozy_aesthetic"` with the
event slug, `research.py:97`) — a search term, not a picture description.
FLUX guidance is unambiguous: it was trained on descriptive natural-language
captions of a single concrete image; keyword-style prompts underperform
badly. No enrichment step exists between "keyword with demand signal" and
"image prompt". Every candidate therefore hits FLUX with a near-identical
generic scaffold plus a 3-6 word keyword — which also explains the
same-looking, sparse, low-subject outputs. **Confirmed independently by the
S4-a natural experiment below** (candidate 1's descriptive niche → the only
owner-good design).

**RC-B — Negation-heavy scaffold. Confirmed by reading.**
`NICHE_STYLE_SCAFFOLD` + `NO_GO_LIST` contain ~10 negated clauses ("no
frame, no border, no wall, no room, no mockup, no photograph of a poster",
"no text or watermarks", "not sparse, not a near-empty background", "Do not
depict…"). FLUX.1 has **no negative-prompt channel**; best practice is
positive description only — negations waste tokens and can *evoke* the named
concepts. (The scene-leak fix worked by removing scene words from the niche —
the sanitizer, `generate.py:28-38` — which supports this mechanism; the
negations themselves remain.)

**RC-C — Token budget overflow at schnell's 256-token cap. Hypothesized,
cheaply verifiable.** schnell's T5 encoder caps at **256 tokens** (dev: 512).
Scaffold + NO_GO + correction note ≈ 175–190 words ≈ 230–270 T5 tokens —
at/over the cap. Critically, the **correction note is appended last**
(`generate.py:53-54`), so on retry the critic's failure feedback is the first
text truncated — plausibly why 3-attempt regeneration rarely rescues a
candidate. Verify with the actual T5 tokenizer
(`google/t5-v1_1-xxl` tokenizer, offline, 5 lines).

**RC-D — Weakest model tier.** schnell is the 4-step distilled variant —
lowest prompt adherence and detail fidelity in the FLUX family. Fine for
volume; a real ceiling for "one clear coherent subject, clean flat zones"
poster art. Upgrades exist at small absolute cost (below).

**RC-E — Minor/secondary.** (a) ESRGAN ×8 on flat minimalist art can halo or
oversmooth zone edges — inspect the condemned masters at 100% before blaming
FLUX for mushy boundaries. (b) Generation is 2:3 while the primary group
prints at ISO 0.707 — the small crop is by-design (CLAUDE.md), just keep it
in mind when judging composition failures near frame edges.

---

### Finding 4 → S4-a — Failure taxonomy & bestseller trait study (EXECUTED 2026-07-20)

*This section replaces the original S4-a stub. It executed and refined S4-a;
scope changed vs. the original spec: images 1–3 in `db/base_artwork/` are
**new designs generated over the original run-#1 masters 1–3**, with owner
grades — so the sample is now a quality gradient (1 good, 2 refine,
3 borderline, 4–7 condemned), not 7 binary failures. Extended, per owner
request, with an Etsy bestseller trait study (observed traits only — no
competitor imagery copied or stored).*

Method notes: local stats computed with the exact
`critic_pass.compute_image_sanity_stats` logic plus two extra metrics
(`ncol` = distinct colors at 256px thumbnail; `cov` = fraction of grayscale
pixels deviating >15 from the median — a subject-coverage proxy). Rubric
assessment done per-criterion by a vision model (Claude) against the 7-point
`CRITIC_RUBRIC_PROMPT_TEMPLATE`; the pipeline's own critic was NOT re-run
live (deferred to the Claude Code session, **after Finding 3's error-handling
fixes**, so results aren't poisoned by the empty-response bug). Bestseller
study done via live Etsy browsing (etsy.com, BE locale, 2026-07-20) using the
`is_best_seller=true` filter — every listing observed carried the real badge.

#### Scorecard — the 7 masters

Owner verdicts are ground truth. Rubric points: 1 no-go / 2 subject presence /
3 coherence / 4 composition / 5 detail quality (smudging) / 6 visual density /
7 text match (n/a — no listing text in scope).

| # | Niche (from DB / memory) | Owner verdict | stddev | edge | ncol | cov | Local gate | Rubric failures |
|---|--------------------------|---------------|-------:|-----:|-----:|----:|-----------|-----------------|
| 1 | mid-century modern botanical, bold filled foliage, dense full-frame, warm muted palette | **Good** | 56.6 | .074 | 8398 | .265 | pass | none — dense centered bouquet, clean flat zones |
| 2 | retro travel poster line art (rendered as bird line art on peach circle) | **Refine** — good idea, some smudging, fairly sparse | 23.6 | .049 | 2686 | .148 | pass | 5 (minor wobble/smudge), 6 borderline (single-weight thin lines, large empty margins) |
| 3 | art deco geometric line art (rendered as single-stem botanical) | **Borderline** — too sparse, lines too thin, but aesthetically pleasing | 15.7 | .029 | 1061 | .020 | pass | 6 (very sparse — one stem, hairline strokes), 4 borderline (large dead zones) |
| 4 | wildflower line drawing | **Reject** — far too empty; should be prevented | 6.9 | .017 | 387 | .006 | **pass (gate miss)** | 2 (borderline no-subject), 4 (two tiny tufts, 99% empty), 6 |
| 5 | (minimalist landscape family) | **Best of the lot** — refine; smudging around finer details | 69.4 | .047 | 3494 | .297 | pass | 5 (soft/mushy edges — check RC-E ESRGAN halo at 100% before blaming FLUX) |
| 6 | (unknown) | **Reject** — empty cream gradient; should be prevented | 0.4 | .010 | 31 | .000 | **FAIL — correct** | 2 (hard fail) |
| 7 | (unknown) | **Reject** — off-center, mostly empty, nonsensical subject (half-chair half-animal + palm trunk) | 8.3 | .024 | 1169 | .029 | **pass (gate miss)** | 2, 3 (hard fail — hybrid), 4 (crammed bottom-left, ~90% empty), 6 |

#### Failure taxonomy (counts over the 5 non-good designs)

- **Too sparse / low subject coverage:** 4 of 5 (2, 3, 4, 7) — the dominant
  failure mode by far.
- **Empty canvas:** 1 (6) — only case the current local gate catches.
- **Malformed/nonsensical subject:** 1 (7).
- **Off-center composition / dead zones:** 2 (4, 7).
- **Smudging / soft detail:** 2 (2, 5) — the *refine*-tier defect; never the
  sole reason for rejection.
- Scene leak: 0 — the H5 "prevent" fix (`36a57bd`) appears to be holding.

#### Key quantitative finding — `cov` separates the set perfectly

Subject coverage (`cov`): good/refine designs score **.148–.297**; sparse or
empty rejects score **.000–.029**; borderline 3 sits at .020 (owner-graded
borderline, metric-graded reject — consistent). A clean ~5x gap exists
between .029 and .148. The current gate (stddev<3 AND edge<0.012) only
catches truly empty frames: **4 and 7 pass it while being owner-condemned
"should be prevented" failures.** Thin line art produces enough local edge
signal to clear `edge_ratio` while covering almost nothing — a structural
blind spot that `cov` closes. → S4-d(1).

#### Calibration-set staleness (action required)

`critic_pass.py:39-45` documents the sanity thresholds as calibrated on
"masters 2/6 must FAIL, 1/5 must PASS" — but masters 1, 2, 3 have been
**overwritten by new designs**. Old master 2's fingerprint (stddev 0.18,
edge .0096) no longer exists on disk; only 6 still matches its comment. The
labeled set must be restated against current files: must-FAIL {6, 4, 7},
must-PASS {1, 5, 2}, borderline {3} — which the current thresholds do NOT
satisfy (4, 7 pass). → S4-d(2).

#### Natural-experiment evidence for RC-A (prompt quality)

Candidate 1's stored niche is already a full visual description
("mid-century modern botanical poster, bold filled abstract foliage and
leaves, dense full-frame composition, warm muted palette") — and it produced
the only owner-good design. Candidates 2/3 got shorter, keyword-style niches
and landed in refine/borderline. n=3, but the direction exactly matches
RC-A/S4-b's prediction. The S4-b art-brief stage is doing deliberately what
candidate 1's niche did by accident.

#### Etsy bestseller trait study (observed 2026-07-20, BE locale)

Searches run with the Bestseller-badge filter across the pipeline's niche
families (botanical line art, mid-century botanical, art deco geometric,
minimalist landscape, wildflower, retro travel). Attribute-level observations
only; no competitor images saved.

Traits shared by bestsellers (ranked by consistency):

1. **High subject coverage — even in "minimalist" niches.** Bestselling art
   fills most of the frame; genuinely sparse single-motif whitespace posters
   are almost absent from badge results.
2. **Bold, confident marks.** Filled color shapes or medium-weight lines.
   Hairline single-weight line art essentially never carries a badge alone.
3. **Warm, muted, non-white grounds.** Cream/beige/textured-paper dominate.
   Two palette families recur: (a) neutral ground + 2–4 muted accents (sage,
   olive, terracotta, dusty pink); (b) saturated retro (burnt orange, teal,
   mustard, deep green) for MCM/Bauhaus.
4. **Backdrop shapes anchor small subjects.** Colored circles, arches, washes
   — exactly design 2's peach-circle device. Design 2's instinct is
   bestseller-aligned; it failed on execution (line weight, smudge), not
   concept.
5. **Style specificity beats generic minimalism.** Badges cluster on
   identifiable idioms (vintage herbarium, Bauhaus, Japanese woodblock,
   Matisse cutout) — not "minimalist plant".
6. **Sets of 2/3/6 dominate line-art niches.** Merchandising structure —
   relevant to Finding 1's future revisit, out of scope here.
7. **Typography is core in some niches.** MCM/Bauhaus headers and especially
   retro travel (city names ARE the product) — the pipeline's hard no-text
   constraint structurally disadvantages these. Retro travel should be
   deprioritized in research/Go-Hold-Kill until that constraint is revisited
   (consistent with live-test 2 drifting to a bird — the niche keyword itself
   fights the constraint).

Gap analysis — our failures vs. bestseller traits:

| Bestseller trait | Our set |
|---|---|
| High coverage (trait 1) | The #1 failure mode: 2/3/4/7 all sparse. Design 1 (cov .265) is the only match — and the only owner-good design. |
| Bold marks (trait 2) | 3 and 4 hairline; 2 thin. 1 and 5 (filled shapes/silhouettes) are the two best-rated. |
| Warm non-white ground (trait 3) | Mostly followed — not a failure driver. |
| Backdrop shape (trait 4) | Design 2 already does this; keep and execute better. |
| Style specificity (trait 5) | Candidate 1's niche names an idiom; weaker niches were generic. |

**Bottom line:** the bestseller study independently converges on the same two
levers as the failure taxonomy — **coverage/density and mark boldness** —
both prompt-controllable (RC-A/RC-B). This strengthens the case that S4-b +
S4-c(1-2) should precede any model upgrade (S4-c-3).

---

### Candidate solutions (S4-a's §3 recommendations folded into each)

**S4-a — DONE (this section).** Output artifact = the recommendations threaded
below. One remaining zero-cost item deferred to the code session: **re-run the
pipeline critic on the 7 masters once Finding 3's fixes land**, and diff its
per-criterion verdicts against the vision assessment above — closes the "gates
unproven live" gap at no design cost.

**S4-b — Research-step fix: add a prompt-enrichment ("art brief") stage.**
One Claude text call per candidate transforms {niche keyword, trend
rationale, buyer segment} into a concrete visual brief: subject, composition,
palette, style/medium, mood — ≤60 words, positive natural language, no
product/scene words. Store as `candidates.art_brief`. The generation prompt
becomes `art_brief + ~30-word positive scaffold`. The hard no-go list moves
into the *brief-writing instructions* (a text LLM handles "don't reference
named artists" reliably; the image model never sees the negations).

*S4-a directives (mandatory brief fields):* every brief must specify, in
positive natural language — (i) one concrete subject in a **named art idiom**
(trait 5); (ii) a **density/coverage clause** ("dense full-frame composition",
"filling the frame edge to edge") — this is the single biggest lever from both
studies; (iii) **mark boldness** ("bold filled shapes" / "confident
medium-weight lines" — never unqualified "line art"); (iv) a **ground**
("warm cream background", optionally a backdrop shape per trait 4); (v) **2–4
named accent colors** from palette family (a) or (b). Candidate 1's niche
string is the working prototype of the target output format.

- Root cause: RC-A (primary), RC-B/RC-C (secondary).
- Impact: **high** — most direct attack on "most candidates fail".
- Effort: **M** (one new module + prompt + tests + a candidates column).
- Cost/latency: +1 cheap text call per candidate (Haiku-class; fractions of a
  cent, ~1–2s). Confidence: **high**.

**S4-c — Generation-step fix: positive-only scaffold + token budget
enforcement (+ optional model upgrade).**
1. Rewrite `NICHE_STYLE_SCAFFOLD` to positive-only (~40 words); delete
   `NO_GO_LIST` from the image prompt (it lives in S4-b's brief instructions).
   *S4-a scaffold vocabulary:* "flat 2D full-bleed artwork", "one coherent
   centered subject", "**dense composition filling the frame**", "bold filled
   color zones with crisp clean edges", "warm muted palette on a soft cream
   ground". The coverage/density language is the piece the current scaffold
   lacks entirely.
2. Add a build-time token check: fail a unit test if
   `t5_tokens(build_prompt(...)) > 240` including a worst-case correction
   note; put the correction note **before** the scaffold tail, not last.
3. Optional model upgrade, A/B'd: `black-forest-labs/flux-dev` on Replicate
   (~$0.025–0.03/image, ~512-token cap, materially better adherence) or
   `flux-1.1-pro` (~$0.04). Replicate's terms grant commercial use of outputs
   generated on their platform, addressing the license concern — **but this is
   a CLAUDE.md hard constraint ("never substitute dev without raising it
   explicitly"), so it requires the owner's explicit sign-off with the license
   terms in front of them, not a code-session decision.** At realistic volume
   (≤ ~40 images/day incl. retries) the delta is a few €/month; latency rises
   from ~1–2s to ~10s (still inside the 60s `Prefer: wait` window —
   `replicate_client.py:36-41` — verify live once).
   A/B protocol: same 10 art briefs → schnell vs dev → owner blind-ranks.
- Root cause: RC-B/RC-C (steps 1–2), RC-D (step 3).
- Impact: medium-high (1–2), potentially high (3).
- Effort: **S** (1–2), **S** + a decision gate (3).
- Confidence: high (1–2), medium-high (3 — needs the A/B).

**S4-d — Review-gate fix: per-criterion telemetry + two-tier gating +
structured retry feedback.**
1. Restructure the critic output from `{passed, reason}` to per-criterion
   verdicts (`{criterion_1..7: {passed, note}, overall}`) persisted in
   `critic_pass_attempts` (schema extension).
   *S4-a directive — add `cov` (subject-coverage) to the local sanity gate:*
   measured gap is condemned sparse/empty ≤ .029, owner-acceptable ≥ .148.
   Proposed: **hard-fail below 0.05** (catches 4, 6, 7 for free, no vision
   call), **flag-to-critic between 0.05–0.12** (catches 3-type borderlines).
   Keep the existing stddev/edge test too — `cov` alone wouldn't catch a
   full-canvas gradient; together they're complementary.
2. *S4-a directive — restate the calibration set* against the current (partly
   overwritten) files: must-FAIL {4, 6, 7}, must-PASS {1, 2, 5},
   borderline {3}. Update the `critic_pass.py:39-45` comment — it currently
   cites fingerprints of deleted images.
3. Two-tier gate: keep the free local sanity gate → add a cheap Haiku-class
   vision pre-filter on the flat master only (empty/malformed/artifact check)
   → full Sonnet gallery+text pass only for survivors.
4. Feed the *per-criterion* failures (not the free-text reason) back into
   S4-b's brief for regeneration.

*S4-a corrections to the plan's priors:* (a) **Rubric point 6 is vindicated,
not over-strict** — every owner-condemned "too sparse" design is one the
rubric would also fail; the S4-d(2) worry about false-fails on intentional
minimalism shows **no evidence** in this set. Hold off softening points 4/6
until live telemetry shows real false-fails. (This reverses the 2026-07-19
plan's prior that softening was likely needed.) (b) **Smudging (point 5) is
the refine-tier defect** (2, 5) and interacts with RC-E — inspect 2/5 at 100%
pre- vs post-ESRGAN before attributing to FLUX; if the halo appears at
upscale, the fix is upscaler config, not prompts. (c) **Verdict vocabulary:**
adopt the owner's three tiers (good / refine / reject) in the restructured
critic output so owner grades and critic verdicts stay comparable over time.

- Root cause: gate calibration + retry-loop efficiency (RC-C interaction).
- Impact: medium (quality measurement + cost), low-medium (direct quality).
- Effort: **M**. Cost: *reduces* per-candidate vision spend on failures.
  Confidence: medium — telemetry is valuable regardless of recalibration.

### Baseline / regression set (from S4-a)

The 7 current masters + owner grades in the scorecard are the **frozen
baseline** for measuring S4-b/S4-c. Success = the new batch's owner grades
strictly dominate the scorecard's distribution (≥ the 1-good / 2-refine /
4-reject baseline). This is the yardstick the final 10-candidate validation
step measures against.

### Effort / Priority

- Combined effort: **M–L** total, cleanly stageable.
- Priority: **1st of 4.** Business-critical; nothing publishes profitably
  while most candidates fail.

### Open questions

- S4-a is done. Remaining: re-run the *pipeline* critic on the 7 masters after
  Finding 3 lands (zero design cost).
- Verify the 256-token overflow empirically (T5 tokenizer) before crediting
  RC-C in the fix messaging.
- flux-dev licensing sign-off (owner decision, sources in hand) before any
  A/B spend.
- Confirm real-esrgan behavior at ×8 on the new flat-art outputs (RC-E) — one
  visual inspection, no code.

---

## Suggested execution order (future Claude Code session)

S4-a is now **complete** (folded above), so it drops out of the live sequence.
Dependencies drive the ordering more than priority labels:

1. **#3 error handling** (S–M) — first, because every later step runs through
   these Anthropic call sites; silent `{}` responses would poison both the
   S4-a pipeline-critic re-run and the final 10-candidate validation. No
   external decisions needed.
2. **#4 S4-b + S4-c(1-2)** (M) — art-brief stage, positive scaffold, token
   test.
3. **#4 S4-d** (M) — per-criterion critic telemetry + two-tier gate + the
   `cov` metric + restated calibration set, so the validation batch (and
   everything after) generates queryable quality data.
4. **Validation — regenerate ~10 candidates (base artwork, NOT upscaled) and
   have the owner blind-review against the S4-a frozen baseline.** This is the
   go/no-go measurement for whether steps 1–3 worked. (Deliberately pulled out
   of step 2 and made the *last* step so it validates all three code changes
   together, not just the prompt rework.)
5. **#4 S4-c(3) model A/B** — only if step 4's owner review still shows an
   adherence/fidelity ceiling; gated on the flux-dev license sign-off.
6. **#2 gallery dedup** (S–M) — independent of everything above; needs the
   Gelato re-sync open question answered first (one live probe). Do it before
   #1 because it's needed under *every* #1 option.
7. **#1 listing-shape decision** — owner decision gate (A/B/C), then implement.
   Deliberately last: it contradicts SPEC v4.11/D6, reopens the just-finished
   migration, and any B/C work must start with the SPEC + CLAUDE.md constraint
   rewrite (sequencing lesson from 2026-07-16).

Steps 1–4 are the scope of `docs/2026-07-20-execution-steps-1-4-kickoff.md`
(with the accompanying code-session prompt). Steps 5–7 are deferred.

Rationale in one line: fix the instruments (#3), fix the biggest lever
(#4b/c), improve the measuring stick (#4d), **then validate on 10 fresh
candidates**, then spend money/decisions (#4c-3), then polish (#2), then
re-litigate design (#1).

## References (external, for Finding 4)

- FLUX.1 schnell 256-token T5 cap; dev 512:
  https://skywork.ai/blog/flux-prompting-ultimate-guide-flux1-dev-schnell/ ,
  https://medium.com/@lbq999/flux-1-dev-encoders-and-token-limitations-8631c179eaad
- No negative prompts in FLUX; positive descriptive language; natural-language
  captions over keyword lists:
  https://www.imagetoprompt.dev/blog/flux-ai-prompt-guide/ ,
  https://deapi.ai/blog/flux-1-schnell-prompting-guide-how-to-write-prompts-and-avoid-common-mistakes ,
  https://fal.ai/learn/tools/how-to-use-flux
- Commercial use of FLUX dev outputs generated on Replicate:
  https://replicate.com/black-forest-labs/flux-dev ,
  https://flowith.io/blog/flux-2-pro-dev-faq-licensing-lora-fine-tuning-api-rate-limits-self-hosting/
