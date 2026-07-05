# Changelog — Etsy AI-assisted POD pipeline spec

Append-only. Each entry maps changes to their cause (red-team finding,
your direct decision, or independently-verified research), so a
counter-reviewer can trace every revision back to why it happened.

---

# Changelog — spec v0.3 → v0.4

**Cause:** initial red-team review (`etsy-pod-spec-redteam.md`) against
the original `SPEC_v3.md`.

- Incorporated every red-team finding without exception, including
  security/correctness items the instructions explicitly said not to trim:
  - Etsy AI-disclosure compliance requirements made explicit and
    API-field-specific (`who_made`, `production_partner_ids`,
    `taxonomy_id`, `shipping_profile_id`), not just template copy —
    red-team flagged that disclosure text alone doesn't satisfy Etsy's
    Creativity Standards enforcement, which checks these fields directly.
  - Etsy hard format limits (13 tags ≤20 chars, 140-char title) called out
    as a validation-time failure mode, not a soft SEO concern, with a
    requirement that the compliance-draft step check them programmatically
    before anything reaches review.
  - Added a critic pass as a distinct, separately-callable pipeline stage
    (vision-capable model call reviewing rendered images + text against a
    fixed rubric) — red-team noted the original spec had no automated
    quality/compliance gate before human review, relying on the human
    reviewer to catch everything.
  - Added the Go/Hold/Kill trend classification system with a safe
    evergreen fallback bucket — red-team flagged that treating every
    research candidate as automatically worth generating risked wasting
    generation budget on saturated/low-signal candidates.
  - Flagged the single combined Telegram message assumption as unverified
    against the actual Bot API (later confirmed broken and fixed in
    v0.4.3).
  - Clarified the runtime architecture as cron-triggered on two cadences
    (hourly lightweight poll, twice-daily heavy batch), not a persistent
    service or single long-running agent loop — red-team noted the
    original spec was ambiguous about this, which has real cost and
    reliability implications.
  - Called out that Gelato template IDs cannot be discovered dynamically
    (dashboard-only, fetch-by-ID only, no list/search endpoint) and must
    be resolved as static configuration before build.
  - Called out that Etsy's `taxonomy_id` similarly has no keyword-search
    endpoint — resolved once via `getSellerTaxonomyNodes`.
  - Specified SQLite (not flat files) as the local data store, given the
    need for transactional safety across two independent cron cadences and
    delta-computation queries against daily-snapshotted Etsy metrics.
  - Confirmed FLUX.1 [schnell] specifically (Apache 2.0, unrestricted
    commercial use) as the image-gen model via Replicate, with an explicit
    warning against silently substituting FLUX.1 [dev] (BFL paid license)
    for quality reasons without re-evaluating licensing.
- Trimmed redundant/speculative content from the original spec (not
  substance): removed duplicated framing paragraphs and spec sections that
  restated the same business goal in multiple places; removed speculative
  future-feature language not tied to any near-term milestone.
- Preserved the original spec's section structure and headers throughout,
  per your instructions, so a counter-reviewer can navigate old vs. new
  content directly.
- Added section 9, "Decisions Needed," flagging every genuine ambiguity
  the red-team review surfaced rather than guessing silently: initial set
  included Offsite Ads threshold status (D1), single- vs. multi-image
  listing behavior (D2), critic-pass retry policy (D3), Gelato native
  lifestyle-mockup support (D4, unverified at the time), and the Gelato
  product delete/archive endpoint's existence (D5, unverified at the
  time).

---

# Changelog — spec v0.4 → v0.4.1

**Cause:** your direct answers to D1, D2, and D3.

- **D1 resolved:** confirmed the shop has never crossed the $10,000
  trailing-365-day sales threshold, and Offsite Ads is turned off in Shop
  Manager. Section 1 updated to state Offsite Ads is optional and
  currently off; margin figures do not need to absorb the 12% Offsite Ads
  cut.
- **D2 resolved:** confirmed multi-image generation — first image is the
  flat Gelato-rendered mockup, followed by "in context" lifestyle/room
  images. Section 3 (mockup + digest steps) and section 4 (static config)
  updated to specify gallery ordering: flat mockup first, then
  lifestyle/room-context images.
- **D3 resolved:** confirmed a 3-attempt auto-regenerate cap, with
  explicit cleanup requirements for abandoned candidates — failed designs
  logged locally as `failed` (for the learning loop to use), and removed
  from Gelato if any product was created there. Section 3, step 5,
  rewritten to specify the full fail/retry/abandon/cleanup flow, and
  section 6 (learning loop) updated to note failed/abandoned candidates
  are logged with full attempt history, not discarded.
- Section 9 updated: D1, D2, D3 marked resolved with pointers to the
  relevant sections; D4 and D5 remained open pending your independent
  verification.

---

# Changelog — spec v0.4.1 → v0.4.2

**Cause:** your independently-verified test results for D4 and D5 (run via
Claude Code against the live Gelato API).

- **D4 resolved:** confirmed `products:create-from-template` natively
  renders multiple lifestyle/room-context mockup images alongside the flat
  shot, per product, automatically in one call. Removed the separate
  compositing/image-generation build item that the original spec and
  v0.4/v0.4.1 had carried as an open technical risk; section 3 step 3 and
  section 4's static config simplified to reference the existing
  template-ID mapping directly, since the room-scene images come free with
  product creation.
- **D5 resolved:** confirmed `DELETE /v1/stores/{storeId}/products/{productId}`
  is a real, working endpoint. Section 3 step 5's abandon-after-3-failures
  cleanup path rewritten to call this endpoint directly, replacing the
  previous fallback language about a possible orphaned-product no-op.
- Section 9 updated: D4 and D5 marked resolved with pointers to sections 3
  and 4; both removed from the open list.

---

# Changelog — spec v0.4.2 → v0.4.3

**Cause:** a second red-team finding on the Telegram digest mechanism.

- **Fixed the Telegram digest mechanism (section 3 step 6, section 4):**
  red-team flagged that a single Telegram API call combining the image
  gallery and the Approve/Edit/Reject inline keyboard is not something the
  Bot API supports — `sendMediaGroup` (albums) cannot carry a
  `reply_markup`. Rewrote the digest mechanism as two separate, sequenced
  calls per candidate: `sendMediaGroup` for the image gallery, followed
  immediately by `sendMessage` carrying the draft listing text and the
  inline keyboard, tagged to the candidate ID. Section 4's Telegram
  Bot API dependency entry updated to match.
- No changes to sections 1, 2, 5, 6, 7, 8, or 9 in this revision.

---

# Changelog — spec v0.4.3 → v0.4.4

**Cause:** your request for build-kickoff guidance, which surfaced a gap —
trend research had no explicit third-party Google Trends option evaluated,
and the spec's research step referenced Google Trends only in passing.

- Section 3 step 1 ("Trending now scan") expanded: documented that Google
  Trends has an official API but it is alpha/rolling-access (worth
  applying for now, zero cost); documented that Etsy SEO tools (eRank,
  Marmalead, EtsyHunt) are seller dashboards with no developer API, so are
  skipped; confirmed the pragmatic research approach is a Claude API call
  with web search enabled, supplemented by Etsy's own API for
  candidate-keyword listing-count/favorites demand-proxy checks.
  Introduced SerpApi's Google Trends API as a third-party option under
  evaluation (not yet adopted — see v0.4.4's section 8 addition below).
- Section 7 updated with the Google Trends alpha-access application as a
  standing action item (no decision needed, zero cost).
- No changes to sections 1, 2, 4, 5, 6, or 9 in this revision.

---

# Changelog — spec v0.4.4 → v0.4.5

**Cause:** independent research into SerpApi's Google Trends API as a
trend-research booster, prompted by evaluating it as an alternative to the
alpha-access Google Trends API.

- Added section 8 entry: SerpApi's Google Trends API evaluated in full —
  technically a strong fit (mirrors the public Trends site, has a
  dedicated "Trending Now" endpoint) and comfortably within its free tier
  (250 searches/month, 50/hour) against this pipeline's estimated 140–200
  calls/month usage. **Deliberately not adopted** due to the active
  Google v. SerpApi lawsuit (filed Dec 19, 2025, N.D. Cal.; DMCA
  circumvention/ToS violation claims; $2.8M damages plus a permanent
  injunction sought that could shut down SerpApi's core business; motion
  to dismiss pending oral argument May 19, 2026). Documented what would
  need to be true to revisit it (litigation resolves in SerpApi's favor,
  or the existing Google-Trends-alpha + Claude-web-search path proves
  insufficient on real data).
- Section 9 updated: added SerpApi as a resolved item (parked, not a
  Decisions Needed item requiring your input, since the litigation risk
  made the call itself straightforward) with a pointer to section 8.
- No changes to sections 1–7 in this revision.

---

# Changelog — spec v0.4.5 → v0.4.6

**Cause:** your uploaded Gelato Belgium-market price CSV and your
direction to start with simpler, individual-size-and-cost templates
instead of Gelato's multi-size-variant template model.

- Section 1: added a size lineup structure using **single-variant, single-
  price Gelato templates** (one template per size, not Gelato's option to
  bundle multiple sizes/prices into one template) — chosen for build
  simplicity at this stage.
- Section 4: added the static "Gelato template-ID mapping" concept as a
  required piece of static configuration, since templates cannot be
  discovered dynamically (dashboard-only, fetch-by-ID only).
- Costs and specific sizes were not yet finalized in this revision — that
  followed in v0.4.7 once you specified the exact six sizes you wanted.
- No changes to sections 2, 3, 5, 6, 7, 8, or 9 in this revision beyond
  pointers to the new static-config concept.

---

# Changelog — spec v0.4.6 → v0.4.7

**Cause:** your specification of the exact six sizes to use (5x7″, 8x12″,
10x24″, A3, A2, A1, each in both orientations), your instruction to use
placeholder template IDs pending manual Gelato dashboard creation, and
your resolution of D7 (currency) and D8 (pricing strategy, including the
A2 orientation cost asymmetry).

- Section 1: replaced the generic size-lineup placeholder with the real
  six-size lineup (12 Gelato products total: 6 sizes × 2 orientations),
  using real cost data from your uploaded
  `Premium Matte Paper Poster_BE_2026-07-05.csv` (Belgium market).
- **D7 resolved:** shop currency set to EUR throughout the spec — all
  prices, costs, and fee figures converted/framed in EUR.
- **D8 resolved:** final retail prices set using round-number anchors
  (€19 / €24 / €35 / €39 / €45 / €49) rather than precise
  margin-percentage targeting, with intentionally lower margins (~21%,
  ~32%) on the two "entry" sizes (5x7″, 8x12″) versus ~38–44% on the four
  "standard" sizes (A3, A2, 10x24″, A1).
- **D8a resolved (A2 orientation cost asymmetry):** Gelato's real cost for
  A2 differs slightly by orientation; both orientations priced at the
  same round €39 rather than two near-identical prices, accepting a
  slightly thinner margin on the portrait variant.
- Section 4: added the full 12-entry Gelato template-ID mapping table
  (6 sizes × 2 orientations), all entries as explicit placeholders (e.g.
  `PLACEHOLDER_5x7_PORTRAIT`) pending your manual template creation in the
  Gelato dashboard, plus a placeholder policy: safe to build/test against
  now, but the first live non-mocked `products:create-from-template` call
  must fail loud on encountering a placeholder rather than silently
  skip/succeed.
- Section 9 updated: D7, D8, D8a marked resolved with pointers to section
  1.
- The CSV itself (full ~29-size Belgium price list, not just the six used
  sizes) kept on disk for reference, per your stated plan to commit it to
  the build repo.

---

# Changelog — spec v0.4.7 → v0.4.8

**Cause:** your resolution of D6, the last open Decisions Needed item —
the review-granularity tradeoff between approving an entire design once
for all six sizes versus requiring a separate approval per size. Your
instruction: review the primary size first; if approved, bundle and
approve the remaining sizes by aspect ratio rather than all-at-once or
one-by-one.

- **D6 resolved** via a derived-from-geometry aspect-ratio grouping (not a
  further judgment call — the six sizes' real dimensions determine the
  groups): 8x12″/A3/A2/A1 share the ISO A-series ratio (~1:1.414, 8x12″
  being literally A4 dimensions) and form the **primary group**; 5x7″
  (~1:1.385) and 10x24″ (~1:2.4) are each meaningfully different ratios
  and form their own **5x7 group** and **10x24 group** respectively.
- Section 1: added the aspect-ratio-group table alongside the existing
  size/cost/price table.
- Section 3: steps 6 and 7 rewritten so that approving the primary group
  auto-publishes the rest of the primary group (A3, A2, A1) with no
  further review, while the 5x7 and 10x24 groups are each independently
  generated, critic-passed, and sent as their own follow-up Telegram
  digest entry with their own Approve/Edit/Reject — so a design can end up
  selling at 4, 5, or 6 sizes depending on those two groups' outcomes.
- Section 4: added the "Aspect-ratio group mapping" static-configuration
  entry, and updated the SQLite schema description to require one row per
  aspect-ratio group per candidate (not just one row per design), each
  with its own decision, critic-pass attempt history, Gelato product
  ID(s), Etsy listing ID(s), and failed/abandoned status independent of
  the other groups on the same design.
- Section 5 (milestones): M1 updated to require a full end-to-end test of
  the new group-flow behavior — approving the primary group, confirming
  the fan-out publish, and exercising both an approve and a reject/abandon
  outcome across the 5x7/10x24 groups — not just unit tests against mocks.
- Section 6 (learning loop): updated to log up to three decisions per
  design (one per group) instead of one.
- Section 9: D6 marked resolved; **all Decisions Needed items are now
  resolved — section 9 reads "None open."**

---

# Changelog — spec v0.4.8 → v0.4.9

**Cause:** your question "what do I do with my Telegram User ID?" and your
follow-up instruction "fold it in now," after I explained its two roles
(admin/allowlist check on incoming messages, and the `chat_id` destination
for outbound digest calls).

- Section 4 (static configuration): added a new static-configuration item,
  **Telegram admin/allowlist user ID**, alongside the existing
  `taxonomy_id`/`shipping_profile_id`/`production_partner_ids`/`who_made`
  entries. Documented its two roles explicitly: (1) every inbound
  `getUpdates` message and callback (commands and Approve/Edit/Reject
  button presses) is checked against this ID before the pipeline acts on
  it, so the bot only responds to you; (2) it doubles as the `chat_id`
  destination for every outbound `sendMediaGroup`/`sendMessage` digest
  call, since your personal chat with the bot is the only destination
  needed for this single-user pipeline.
- Section 3 (pipeline layer): added a note to the Telegram digest and
  hourly-poll descriptions (steps 1, 6, 7) that every inbound message is
  allowlist-checked against the static admin ID before being treated as a
  real command or decision.
- No changes to sections 1, 2, 5, 6, 7, 8, or the "None open" status of
  section 9 — this is a small, additive static-config item, not a new
  ambiguity.
- **Note on this revision's provenance:** v0.4.8 was authored in the prior
  session but did not persist to disk due to a file-write/session issue;
  this changelog and the accompanying `SPEC_v4.9.md` restore v0.4.8's full
  content (aspect-ratio-group resolution, D6) and layer the Telegram
  admin-ID addition on top in the same delivery, so nothing from v0.4.8
  is lost.
