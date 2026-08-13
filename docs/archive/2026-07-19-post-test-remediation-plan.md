# Post-test remediation plan (2026-07-19)

Scope: the four findings from manual testing + Etsy/Gelato inspection after the
E2E live run (`docs/e2e_live_run_runbook_2026-07-18.md`). Grounded in the code
at commit `b2a3fe9` and SPEC_v4.11. This is a plan for a future Claude Code
session to execute — no code was changed while writing it.

Conventions for the executing session: follow CLAUDE.md (no live Gelato/Etsy
calls without explicit go-ahead, commit per passing stage, dry-run flags while
iterating). Where this plan says "verify live", that is a named, user-gated
call per the runbook's protocol.

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
  wastes the retry budget that Finding 4 depends on.

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
same-looking, sparse, low-subject outputs.

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

### Candidate solutions

**S4-a — Failure-sample instrumentation FIRST (do this before tuning).**
> **EXECUTED 2026-07-20** — see `docs/2026-07-20-s4a-failure-taxonomy.md`
> (supersedes this item's description: sample became a graded set after
> designs 1–3 were regenerated; scope extended with an Etsy bestseller
> trait study). Executing sessions implement against that doc's §3.
Run the 7 condemned masters (local archive `db/base_artwork/`, not in git —
owner has them) + any new failures through: the local stats gate, the critic
rubric per-criterion, and a 1-line owner tag each. Produce a small failure
taxonomy (empty / malformed subject / muddy edges / sparse / scene leak /
other). 30 minutes of work that turns the next three items from guesses into
targeted fixes and creates the baseline to measure them against.
- Root cause addressed: none directly — de-risks all of them.
- Impact: high (indirect). Effort: **S**. Cost: a few vision calls.
  Confidence: high (as a diagnostic).

**S4-b — Research-step fix: add a prompt-enrichment ("art brief") stage.**
One Claude text call per candidate transforms {niche keyword, trend
rationale, buyer segment} into a concrete visual brief: subject, composition,
palette, style/medium, mood — ≤60 words, positive natural language, no
product/scene words. Store as `candidates.art_brief` (feeds the learning
loop later: approvals correlate with briefs, not keywords). The generation
prompt becomes `art_brief + ~30-word positive scaffold` — specific, varied
per candidate, comfortably inside 256 tokens. The hard no-go list moves into
the *brief-writing instructions* (a text LLM handles "don't reference named
artists" reliably; the image model never needs to see the negations).
- Root cause: RC-A (primary), RC-B/RC-C (secondary).
- Impact: **high** — most direct attack on "most candidates fail".
- Effort: **M** (one new module + prompt + tests + a candidates column).
- Cost/latency: +1 cheap text call per candidate (Haiku-class is fine;
  fractions of a cent, ~1–2s). Confidence: **high**.

**S4-c — Generation-step fix: positive-only scaffold + token budget
enforcement (+ optional model upgrade).**
1. Rewrite `NICHE_STYLE_SCAFFOLD` to positive-only (~40 words: "flat 2D
   full-bleed artwork… one coherent centered subject… crisp clean edges
   between flat color zones… soft muted natural palette…"); delete
   `NO_GO_LIST` from the image prompt (it lives in S4-b's brief
   instructions).
2. Add a build-time token check: fail a unit test if
   `t5_tokens(build_prompt(...)) > 240` including a worst-case correction
   note; put the correction note **before** the scaffold tail, not last.
3. Optional model upgrade, A/B'd: `black-forest-labs/flux-dev` on Replicate
   (~$0.025–0.03/image, ~512-token cap, materially better adherence) or
   `flux-1.1-pro` (~$0.04). Replicate's terms grant commercial use of
   outputs generated on their platform (they hold a BFL agreement), which
   addresses the license concern — **but this is a CLAUDE.md hard
   constraint ("never substitute dev without raising it explicitly"), so it
   requires the owner's explicit sign-off with the license terms in front of
   them, not a code-session decision.** At realistic volume (≤ ~40
   images/day incl. retries) the delta is a few €/month; latency rises from
   ~1–2s to ~10s (still inside the 60s `Prefer: wait` window —
   `replicate_client.py:36-41` — verify live once).
   A/B protocol: same 10 art briefs → schnell vs dev → owner blind-ranks.
- Root cause: RC-B/RC-C (steps 1–2), RC-D (step 3).
- Impact: medium-high (1–2), potentially high (3).
- Effort: **S** (1–2), **S** + a decision gate (3).
- Cost: (1–2) none; (3) ~10× per image but trivial absolute terms.
  Confidence: high (1–2), medium-high (3 — needs the A/B).

**S4-d — Review-gate fix: per-criterion telemetry + two-tier gating +
structured retry feedback.**
1. Restructure the critic output from `{passed, reason}` to per-criterion
   verdicts (`{criterion_1..7: {passed, note}, overall}`) persisted in
   `critic_pass_attempts` (schema extension) — failure patterns become
   queryable instead of prose.
2. Soften rubric points 4/6 for *intentional* minimalist negative space
   (the current wording invites false-fails on exactly the style being
   sold); S4-a's data will show whether this is actually happening.
3. Two-tier gate: keep the free local sanity gate → add a cheap Haiku-class
   vision pre-filter on the flat master only (empty/malformed/artifact
   check) → full Sonnet gallery+text pass only for survivors. Cuts vision
   spend on hopeless candidates and shortens retry loops.
4. Feed the *per-criterion* failures (not the free-text reason) back into
   S4-b's brief for regeneration — structured correction that survives the
   token budget.
- Root cause: gate calibration + retry-loop efficiency (RC-C interaction).
- Impact: medium (quality measurement + cost), low-medium (direct quality).
- Effort: **M**. Cost: *reduces* per-candidate vision spend on failures.
  Confidence: medium — the gates are unproven live either way; telemetry is
  valuable regardless of whether recalibration turns out to be needed.

### Effort / Priority

- Combined effort: **M–L** total, but cleanly stageable
  (S4-a → S4-b → S4-c(1-2) → S4-d → S4-c(3) decision).
- Priority: **1st of 4.** This is the business-critical finding; nothing
  publishes profitably while most candidates fail.

### Open questions

- S4-a needs the condemned masters (`db/base_artwork/` on the owner's
  machine) and ideally the owner's one-line reason per condemned design.
- Verify the 256-token overflow empirically (T5 tokenizer) before crediting
  RC-C in the fix messaging.
- flux-dev licensing sign-off (owner decision, sources in hand) before any
  A/B spend.
- Confirm real-esrgan behavior at ×8 on the new flat-art outputs (RC-E) —
  one visual inspection, no code.

---

## Suggested execution order (future Claude Code session)

Dependencies drive this more than priority labels:

1. **#3 error handling** (S–M) — first, because every later step runs
   through these Anthropic call sites; silent `{}` responses would poison
   the measurements in step 2. No external decisions needed.
2. **#4 S4-a instrumentation** (S) — needs the owner's `db/base_artwork/`
   masters + condemnation reasons. Produces the failure taxonomy baseline.
3. **#4 S4-b + S4-c(1-2)** (M) — art-brief stage, positive scaffold, token
   test. Then regenerate ~10 candidates and have the owner review — this is
   the go/no-go measurement for whether prompt work alone suffices.
4. **#4 S4-d** (M) — per-criterion critic telemetry + two-tier gate, so the
   step-3 batch (and everything after) generates queryable quality data.
5. **#4 S4-c(3) model A/B** — only if step 3's owner review still shows an
   adherence/fidelity ceiling; gated on the flux-dev license sign-off.
6. **#2 gallery dedup** (S–M) — independent of everything above; needs the
   Gelato re-sync open question answered first (one live probe). Do it
   before #1 because it's needed under *every* #1 option.
7. **#1 listing-shape decision** — owner decision gate (A/B/C above), then
   implement. Deliberately last: it contradicts SPEC v4.11/D6, reopens the
   just-finished migration, and any B/C work must start with the SPEC +
   CLAUDE.md constraint rewrite (sequencing lesson from 2026-07-16).

Rationale for the ordering in one line: fix the instruments (#3), measure
(#4a), fix the biggest lever (#4b/c), improve the measuring stick (#4d),
then spend money/decisions (#4c-3), then polish (#2), then re-litigate
design (#1).

## References (external, for finding 4)

- FLUX.1 schnell 256-token T5 cap; dev 512:
  https://skywork.ai/blog/flux-prompting-ultimate-guide-flux1-dev-schnell/ ,
  https://medium.com/@lbq999/flux-1-dev-encoders-and-token-limitations-8631c179eaad
- No negative prompts in FLUX; use positive descriptive language; natural-
  language captions over keyword lists:
  https://www.imagetoprompt.dev/blog/flux-ai-prompt-guide/ ,
  https://deapi.ai/blog/flux-1-schnell-prompting-guide-how-to-write-prompts-and-avoid-common-mistakes ,
  https://fal.ai/learn/tools/how-to-use-flux
- Commercial use of FLUX dev outputs generated on Replicate:
  https://replicate.com/black-forest-labs/flux-dev ,
  https://flowith.io/blog/flux-2-pro-dev-faq-licensing-lora-fine-tuning-api-rate-limits-self-hosting/
