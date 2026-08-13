# Etsy AI-assisted POD pipeline — spec v0.4.4 (SerpApi evaluated, parked for now)

Status: all five flagged decisions/verifications from prior revisions
(D1–D5) remain resolved (see section 9). v0.4.3 fixed the Telegram digest
mechanism. This revision adds one parked fast-follow item after
researching SerpApi's Google Trends API as a possible trend-research
booster (section 8) — starting without it, per your call. No spec
behavior changes as a result. Ready to build once the Etsy app is
approved.

---

## 1. Business layer

- **Product:** AI-generated wall art / posters, produced and shipped via Gelato,
  sold through your existing Etsy shop.
- **Relationship to existing shop:** ✅ resolved — new AI-generated designs
  will be listed in the existing shop, assigned to a dedicated Etsy shop
  **section** (e.g. "AI-generated designs") via the `section_id` field on
  listing creation. Shop underperformance means pollution risk is low
  priority, but separation is cheap enough to do anyway.
- **Target buyer:** ✅ resolved — two segments, primary first: **self-purchase
  redecorators**, women 28–45, buying to match an existing aesthetic
  (neutral boho, modern minimalist, coastal), price-sensitive, searching by
  aesthetic + room + mood rather than generic terms. Secondary/fast-follow:
  **gift/nursery buyers**, less price-sensitive, buying matched sets of
  3–6 prints — higher order value but needs more design range than a first
  test warrants.
- **Niche (first test):** ✅ resolved — nature/botanical/minimalist
  landscape. Broadest and most evergreen, plays to AI's strengths (no
  faces/text needed), and it's what the primary buyer segment searches for.
  Nursery sets parked as fast-follow once this niche is validated.
- **Price point:** ~$22 (small/mid, ~12x16) and ~$32 (larger, ~18x24),
  unframed (skip framing for the first test). Target 40–50% margin after
  Etsy fees.
  - **Etsy fees, precisely:** $0.20 listing fee + 6.5% transaction fee +
    ~3% + $0.25 payment processing ≈ **9.5% + $0.45 flat per order**.
  - **Offsite Ads — ✅ resolved:** confirmed the shop has never crossed
    $10,000 in sales in any trailing 365-day window, so Offsite Ads is
    optional, and it's currently turned **off** in Shop Manager. The
    40–50% margin target does not need to absorb the 12% Offsite Ads cut.
    Worth re-checking this if the shop's sales trajectory changes
    materially, since crossing the threshold later would make it mandatory
    for the lifetime of the shop with no opt-out.
  - **Gelato base cost per size:** resolve **before build starts**, not
    during M1 — `GET /v3/products/{productUid}/prices` returns cost by
    quantity in a single API call. The $22/$32 price points and the
    40–50% margin target are both downstream of this number.
- **Success metric:** ✅ resolved and recalibrated — new, unranked listings
  realistically run ~0.5–1.5% conversion and ~1–2% CTR, roughly one sale
  per 5,000–15,000 impressions before reviews/ranking kick in. One
  profitable sale in month 1 from a *single* listing isn't reliable; the
  original "at least one net-profitable design" metric holds, but expect
  it to require 8–12 listings (a few designs × 2–3 sizes) to have decent
  odds, not one design tested in isolation.
- **Paid ads:** ✅ confirmed — small ad budget, capped at **$5/day** (Etsy
  Ads, distinct from Offsite Ads above). Real recurring spend beyond Etsy
  fees and the subscription, accepted deliberately rather than inherited
  by default.
- **Definition of "worth it":** subscription cost offset, not a business.
  Keep this framing — it prevents scope creep into a real e-commerce build.

## 2. Content / compliance layer

- **Asset type:** AI-generated poster/wall-art imagery. No text-heavy
  products in this pipeline (that's a separate, simpler idea if you ever want
  it).
- **Etsy listing category:** "Seller-prompted AI creation" + "produced by a
  production partner" — both disclosures required on every listing.
- **Disclosure template (draft, to refine):**
  > "This design was created using AI image generation from the seller's own
  > prompts, then selected, edited, and prepared for print by the seller.
  > Printed and shipped by our production partner, Gelato."
- **Required listing metadata (compliance-critical, not just copy):** the
  disclosure text above is necessary but not sufficient. Etsy's Creativity
  Standards for AI-generated items also require specific API fields to be
  set correctly at listing-creation time — getting these wrong is the most
  common cause of AI listings getting flagged or taken down, not a
  cosmetic issue. See section 4, "Static configuration," for the specific
  fields (`who_made`, `production_partner_ids`, `taxonomy_id`,
  `shipping_profile_id`) and how they're resolved.
- **Generated text must respect Etsy's hard format limits, checked
  programmatically, not just by convention:** 13 tags max (≤20 characters
  each) and a 140-character title cap. Violating these isn't a soft SEO
  miss — it's an API validation error at publish time. The compliance-draft
  step (section 3, step 4) must validate against these limits before a
  candidate ever reaches the Telegram digest, so a human never spends
  review time on a listing that would be rejected at publish anyway.
- **Alt text per image:** generate alt text for every image in the listing
  gallery (section 3, step 3 — flat mockup plus the lifestyle/room-context
  images Gelato returns alongside it), not just a single image, in the
  same compliance-draft call. Free SEO/accessibility value, costs nothing
  extra to add.
- **Hard no-go list (baked into generation prompts, not just review):**
  no named artists' styles, no recognizable characters/franchises/logos, no
  implied celebrity likeness, no claims of "hand-painted" or "original
  artwork."
- **Human review gate:** every design is reviewed by you before publish — no
  exceptions, regardless of how automated the rest of the pipeline gets.
  (The critic pass added in section 3 is additive to this gate, not a
  replacement for it.)

## 3. Pipeline layer

1. **Trend research** — three inputs feeding a shared "trend candidates" pool
   (niche + urgency + rationale), consumed by design generation:
   - **Trending now scan (scheduled):** ✅ investigated — Google Trends has
     an official API but it's alpha, rolling/limited access (worth applying
     now, zero cost, same pattern as the Etsy app); Etsy SEO tools (eRank,
     Marmalead, EtsyHunt) are seller dashboards, not developer APIs, so
     skip them. Pragmatic approach: use a Claude API call with web search
     enabled as the actual research engine, supplemented by Etsy's own API
     to check candidate-keyword listing counts/favorites as a demand proxy.
     A third-party option (SerpApi's Google Trends API) was evaluated and
     deliberately not adopted for now — see section 8 for the rationale
     and what would need to be true to revisit it.
   - **Event lookahead (scheduled):** ✅ resolved and dated — two-layer as
     before, now with confirmed near-term dates researched from early July
     2026:

     | Window | Relevance |
     |---|---|
     | **Nov 10 – Dec 20 (holiday peak)** | Biggest window overall — full Q4 (Oct–Dec) runs roughly 25–32% of annual Etsy GMS per Etsy's own investor filings; this window is narrower than full Q4 so its actual share is likely somewhat below that range. Treat as a ballpark, not a cited figure. |
     | Diwali — Sun, Nov 8, 2026 | Cultural gifting/home decor |
     | Black Friday (Nov 27) / Cyber Monday (Nov 30) | General gift-shopping surge |
     | Fall/cozy aesthetic (Sept–Oct) | Strong for nature/botanical specifically — the chosen niche |
     | Engagement season (late Nov–Feb 14) | Gift/registry shopping, "first home" decor |
     | January (New Year refresh) | Self-purchase redecorating |

     **Nearest real target from today:** get botanical/minimalist listings
     live and indexed *before* the Nov 10 holiday peak — new listings need
     review/ranking time, so this favors not letting M1/M2 drag. Not a hard
     deadline, but real momentum matters here. Mother's Day and Lunar New
     Year 2026 have already passed this year; both recur on the calendar
     for next cycle. Refresh monthly as before to keep dates current
     year over year.
   - **Telegram on-demand:** ✅ resolved — command-polling handled by the
     hourly poll described in section 4 (decoupled from the twice-daily
     batch). A `/research <topic>` command triggers scoped research; the
     actual research still runs on the normal schedule. Results come back
     as a digest and feed into the next scheduled batch as a prioritized
     candidate, rather than immediately spending image-gen budget on an
     ad hoc request.
   - **Go / Hold / Kill classification:** every research cycle classifies
     each candidate into one of three states — research doesn't just hand
     everything to design generation by default:
     - **Go** — reasonable demand signal, timing is live or upcoming
       (matches an event window with lead time still available). Proceeds
       to generation as normal.
     - **Hold** — signal exists but timing has already passed this cycle
       (e.g. a seasonal window closes before you could realistically list
       and get ranking time). Logged with a re-check date (e.g. "revisit
       60 days before next year's window") instead of silently
       disappearing or silently consuming generation budget anyway.
     - **Kill** — weak or saturated (e.g. listing-count-to-favorites ratio
       below a threshold you set once baseline data exists, or a keyword
       with very high competition and no differentiation angle). Logged
       with the specific reason, and **triggers a fallback**: fall back to
       the next-highest-scored candidate already in the pool that cycle,
       or fall back to a standing **"safe evergreen" bucket** — a fixed
       list of always-relevant botanical/minimalist searches that don't
       depend on trend timing at all — so the pipeline never skips a whole
       batch just because the top signal didn't pan out. This is the same
       fallback a candidate falls into after exhausting its regeneration
       attempts in step 5.
     - Start these thresholds as rough manual heuristics; revisit at M3
       once real data exists to calibrate them, same posture as the rest
       of the learning loop.
2. **Design generation** — image-gen API call(s) per candidate, driven by
   trend output.
3. **POD mockup** — render the design onto a Gelato poster product via
   Gelato's API, using the static template-ID lookup from section 4 (there
   is no way to discover templates dynamically at runtime — see section 4).
   ✅ confirmed: a single `products:create-from-template` call returns
   the full image gallery for the product automatically — the flat mockup
   shot plus lifestyle/room-context images showing the poster in a room
   setting — with no separate compositing or image-generation step needed
   and no additional template configuration beyond the existing
   size/orientation mapping. The pipeline takes this returned image set
   and orders it for the listing with **the flat mockup first, followed by
   the lifestyle/room-context images** (Gelato's own return order isn't
   assumed to already match this — the pipeline picks/orders them
   explicitly when assembling the gallery).
4. **Compliance draft** — auto-fills, per candidate:
   - the disclosure template text (section 2);
   - the required listing metadata fields — `who_made`,
     `production_partner_ids`, `taxonomy_id`, `shipping_profile_id` — from
     the static configuration in section 4;
   - a first-pass title/tags/description, validated against Etsy's format
     limits (13 tags ≤20 characters, 140-character title) before moving on;
   - alt text for every image in the gallery produced by step 3 (flat
     mockup + lifestyle/room-context images).
5. **Critic pass** — a separate model call (a vision-capable Claude call,
   distinct from the generation call so it isn't grading its own homework)
   reviews every image in the gallery (flat mockup and in-context shots)
   plus the draft title/tags/description against a fixed rubric before the
   candidate reaches you:
   - hard no-go list compliance (named styles, characters/logos, implied
     hand-painted/celebrity claims) — checked across all gallery images,
     not just the flat mockup;
   - basic image-quality checks (obvious artifacts, garbled/watermark-like
     elements, off-center or cut-off composition) on each image;
   - whether the draft title/description actually match the images and
     niche.
   - Output is a simple **pass/fail plus reason**, not a tunable score —
     there's no data yet to calibrate a threshold, and a binary gate with a
     logged reason is enough to start.
   - **Fail — retry policy:** up to **3 auto-regenerate attempts** per
     candidate, each with the prior failure reason fed back as a prompt
     correction (design generation → mockup → compliance draft → critic
     pass, repeated). **After 3 failed attempts, abandon the candidate** —
     no further retries — and:
     - **Log it locally as `failed`**, keeping the full record (trend
       source, every attempt's prompt, every attempt's critic-pass failure
       reason, style/theme tags) in the same structured decision log as
       everything else (section 6), so the learning loop can learn from
       *why* a candidate never made it to review, not just from
       successful ones.
     - **Clean up the Gelato-side product. ✅ confirmed:**
       `DELETE /v1/stores/{storeId}/products/{productId}` is a real,
       working endpoint — call it directly for any product created during
       a failed attempt, as part of abandoning the candidate. No orphaned
       draft products should be left in Gelato for designs that will never
       publish.
     - **Trigger the Go/Hold/Kill fallback** (step 1) to bring in the
       next-highest-scored candidate or a safe-evergreen-bucket item to
       fill the batch slot the abandoned candidate would have used.
   - **Pass:** proceeds to the Telegram digest exactly as before.
   - This is additive to the human review gate in section 2, not a
     replacement for it — it exists so your review time goes to real
     judgment calls (does this match the niche, is it good enough to sell)
     rather than to catching AI artifacts or policy violations by hand.
   - Implemented as its own named, independently testable stage (see
     section 4), since it needs the rendered gallery images as input.
6. **Telegram digest (daily batch)** — for every candidate that passed the
   critic pass, sent as **two separate Telegram API calls per candidate**,
   not one combined call — Telegram's Bot API does not support attaching
   an inline keyboard to a media group, so a single call can't carry both
   the gallery and the Approve/Edit/Reject buttons:
   - **`sendMediaGroup`** — the image gallery as an album (flat mockup
     first, then lifestyle/room-context images), unlabeled beyond what
     Telegram allows as a single caption on the group.
   - **`sendMessage`** (sent immediately after, same candidate) — the
     draft listing text (title/tags/description excerpt) plus the
     Approve/Edit/Reject inline keyboard, tagged with the candidate ID so
     the callback can be matched back to it.
   - This repeats once per candidate in the batch (not one message for the
     whole batch) — "digest" describes the batch cadence, not a single
     Telegram message. The hourly poll (section 4) picks up the
     button-press callbacks the same way regardless of this change.
7. **Evening run** — reads your responses; approved items get published to
   Etsy (assigned to the dedicated "AI-generated designs" section via
   `section_id`, full image gallery uploaded in the fixed mockup-then-
   room-images order, each with its alt text), rejected ones are
   discarded and logged the same way as critic-pass failures (image
   gallery + full listing text + decision, so rejects also feed the
   learning loop), "edit" ones get a note fed back into step 2 for
   regeneration.
8. **Fulfillment** — handled entirely by Gelato once an order comes in; no
   pipeline involvement needed here.
9. **Performance monitor (future, post-M2)** — slower-cadence job (daily/
   weekly) pulling Etsy order data + Gelato fulfillment status, digesting via
   Telegram, feeding "what's selling" back into step 1 (trend research) and
   step 2 (design generation). Needs real listing data to exist before it's
   useful — sequence after M2 is live. The decision log it draws on now
   also carries Go/Hold/Kill state and failed/abandoned attempts (section
   6) alongside approve/edit/reject outcomes.

## 4. Technical layer

- **Runs as:** a **cron-triggered script on two cadences**, not a
  persistent service and not one monolithic agent loop. Buildable in
  Claude Code as a real, testable codebase; Claude Code is the tool used to
  *build* this, but the *runtime* is plain scheduled functions, not a
  long-running agentic session.
  - **Hourly, lightweight poll:** calls Telegram's `getUpdates`, checks for
    new `/research <topic>` commands and pending Approve/Edit/Reject
    responses (from the `sendMessage` calls in section 3, step 6), writes
    them to local state. No image-gen, Gelato, or Etsy calls happen here —
    this trigger is cheap and only reads/records.
  - **Twice-daily, heavy batch:** morning run does trend research → design
    generation → mockup (flat + lifestyle images in one call) →
    compliance draft → critic pass (with up to 3 regenerate-and-retry
    loops per candidate) → Telegram digest (`sendMediaGroup` +
    `sendMessage` per candidate, per section 3 step 6); evening run reads
    approvals → publishes, per section 5's M1/M2 description.
  - Each pipeline stage (research, generate, mockup, compliance-draft,
    critic-pass, digest, publish, cleanup) is a **discrete, independently
    callable function**, not steps folded into a single loop — this lets
    you rerun one stage without re-running the ones before it, and lets
    each stage be tested in isolation. All stages share the local state
    store below.
- **Static configuration** — resolved once before M1, referenced by ID at
  runtime; none of these can be discovered dynamically by the relevant API,
  so they have to exist as owned config before the first real run:
  - **Gelato template-ID mapping:** `{size × orientation → templateId}` —
    e.g. 12x16 portrait, 12x16 landscape, 18x24 portrait, 18x24 landscape.
    Gelato's API has no list/search endpoint for templates (only
    fetch-by-ID), so this mapping is created manually in the dashboard and
    hardcoded into the pipeline. Design generation decides orientation
    from the prompt/composition; the mockup step does a plain dictionary
    lookup. You own this mapping and update it whenever a new size or
    orientation is added. No separate room-scene template/style ID is
    needed — confirmed the same `templateId` used for the flat mockup
    also drives the lifestyle/room-context images Gelato returns
    alongside it.
  - **Etsy `taxonomy_id`:** the category node for wall art/home decor,
    resolved once via `getSellerTaxonomyNodes` (no keyword-search endpoint
    exists here either — fetch the tree once, pick a node).
  - **Etsy `shipping_profile_id`:** created via `createShopShippingProfile`,
    with processing time matched to Gelato's actual stated production/
    shipping timelines for posters — this has to be accurate or you're
    over- or under-promising delivery to buyers, a common documented POD
    failure mode.
  - **Etsy `production_partner_ids`** record for Gelato, and the exact
    current `who_made` enum value that maps to "Designed by a seller" (not
    "I did," which is for genuinely handmade items) — verify this value
    against the live API schema via the Etsy Dev MCP server before the
    first publish; Etsy has changed this schema before, and a wrong value
    risks takedown, not just a cosmetic error.
- **External dependencies:**
  - Image generation — **decision:** Replicate, hosting FLUX.1 [schnell],
    for M1 (validate fast, pay-per-image, no setup cost). FLUX.1 [schnell]
    is Apache 2.0 (unrestricted commercial use, confirmed directly from
    Black Forest Labs' license file) — a meaningfully different license
    from FLUX.1 [dev], which requires a paid BFL license for commercial
    use. **Do not substitute "dev" for quality reasons without
    re-evaluating licensing** — this is the same license-clean model
    family planned for local/M2+ self-hosting, so prompting behavior
    carries over directly at migration. Switch to local/rented-GPU hosting
    for M2+ once a niche is validated, at which point a photography-style
    LoRA fine-tune becomes worth building as a brand differentiator.
    Replicate's schnell pricing (~$0.003/image) is cheap enough that
    pay-per-image holds for any realistic M1 volume — note that up to 3
    retry attempts per candidate multiplies the number of image-gen calls
    per published listing; still cheap at schnell's per-image price, but
    worth watching once volume ramps up. (The lifestyle/room-context
    images do not add to this cost — they come from the Gelato mockup
    call, not a separate image-gen call.)
  - Gelato API (product mockup + order fulfillment) — ✅ confirmed via live
    test calls: `products:create-from-template` returns a working mockup
    `previewUrl` end to end, and also returns lifestyle/room-context
    mockup images automatically as part of the same call, and
    `DELETE /v1/stores/{storeId}/products/{productId}` is a real, working
    endpoint for removing a created product. Templates (reusable
    blueprints) are dashboard-only with no creation or list API — see the
    static template-ID mapping above; products (a specific design
    instantiated from a template) are what the pipeline actually
    automates.
  - Etsy Open API v3 (listing creation) — 🕓 **app registered, pending
    approval** (personal access, own shop). ✅ process clarified: apps get
    personal access immediately on registration (own shop, up to 5 shops) —
    the heavier "commercial access" review only applies to apps serving
    other sellers, not this case. Shop-section mechanism confirmed real:
    `createShopSection` + `updateListing` with `section_id`, via
    `shops_w`/`listings_w` scopes. Rate limit is 10,000 requests/day and
    10/sec by default — confirmed more than sufficient for this volume
    (twice-daily batch + hourly poll), including the extra image uploads
    from multi-image galleries; no action needed.
  - 💡 Etsy publishes a free **Dev MCP server** (no API key needed) that
    gives an AI assistant full knowledge of the API spec — useful for
    verifying endpoint capabilities without needing full OAuth access
    (this is how the views/favorites vs. CTR question, and the `who_made`
    enum value, get resolved/verified).
  - Telegram Bot API — **`sendMediaGroup` (image gallery) + `sendMessage`
    (listing text + inline Approve/Edit/Reject buttons), two calls per
    candidate**, per section 3 step 6 — not a single combined call, since
    Telegram doesn't support inline keyboards on media groups. `getUpdates`
    polled hourly per the cadence above to pick up button-press callbacks
    and `/research` commands — no webhook/always-on requirement.
  - **Not adopted for M1: SerpApi's Google Trends API** (or similar
    third-party Google Trends scraper), evaluated as a possible booster
    for the trending-now scan above. See section 8 for the full rationale
    — not a technical or cost problem, but an active-litigation
    continuity risk against the official-alpha + Claude-web-search path
    already in place.
- **Data storage:** **SQLite**, must persist to disk between the hourly and
  twice-daily triggers (not in-memory) and hold enough state to compute
  daily `views`/`numFavorers` deltas (section 6) across multiple listings.
  Schema must also accommodate: multiple images per candidate (with alt
  text and gallery order), per-attempt critic-pass history up to 3 retries,
  a `failed`/abandoned status distinct from pending/approved/rejected/live,
  and enough of a mapping between a candidate ID and its `sendMessage`
  message ID to match an incoming button-press callback back to the right
  candidate.

## 5. Milestones (crawl → walk → run)

- **M1 — build for real, run manually one item at a time:** skip a separate
  fully-manual rehearsal (existing Etsy/Gelato operational experience already
  covers that ground). Build the actual pipeline stages, but trigger them
  manually on single candidates before turning on the schedule and batch
  volume — validates design/niche/compliance quality without a throwaway
  manual phase. **M1 must include manually exercising the Kill branch**
  (section 3, step 1) at least once, deliberately, not just the happy-path
  Go candidates — that branch won't get exercised naturally if your first
  few manual candidates are all reasonable ones. **M1 must also include
  manually exercising a full 3-attempt critic-pass failure** (section 3,
  step 5) at least once, confirming both the abandon/fallback logic and
  that the `DELETE` cleanup call actually removes the Gelato product it
  targets, not just that it's logged as attempted.
- **M2 — semi-automated:** the scheduled script handles research/generation/
  mockup/compliance draft/critic pass; Telegram digest + your approval gate;
  publish is still a deliberate step you trigger.
- **M3 — feedback loop:** performance monitor comes online once there's real
  listing data; more automation only if M2 proves the unit economics work.
  Human review gate stays regardless.

## 6. Learning loop (approvals + sales/CTR feed back into generation)

Two feedback signals, deliberately treated differently — not one loop, two,
at different speeds and different confidence levels:

- **Fast loop — your Telegram decisions.** Dense signal, available daily
  from the start of M2. Every candidate's decision (approve/edit/reject +
  any edit notes) is logged and can shape generation aggressively from
  day one. The log also captures which Go/Hold/Kill state a candidate was
  in upstream (section 3), and now also **candidates abandoned after 3
  failed critic-pass attempts**, with the failure reasons from each
  attempt — so the M3 adaptive-bandit revisit has data on everything that
  didn't make it to review, not just outcomes of things that did.
- **Slow loop — sales & engagement data (not CTR).** ✅ investigated: Etsy
  exposes no impressions/CTR/analytics endpoint at all — this was the wrong
  mental model. Real signal available: `views` (cumulative, tabulated once
  daily, listing-detail endpoint only) and `numFavorers` (cumulative,
  available everywhere), plus actual orders via `ShopReceipt`. Since Etsy
  only returns cumulative counters, the performance monitor must snapshot
  `views`/`numFavorers` daily itself and compute deltas locally — there's
  no "views today" field to read directly. **Treated as advisory, not
  authoritative**, until **14 days since listing went live** (✅ decision —
  starting heuristic, revisit once real data exists) — daily tabulation lag
  makes early counts unreliable and a fresh listing's `views: 0` is
  ambiguous (genuinely zero vs. not-yet-tabulated vs. fetch error).

**Mechanism:** not model fine-tuning. A structured decision log (design
metadata: trend source, prompt(s) across attempts, style/theme tags,
Go/Hold/Kill state, critic-pass outcomes, your decision, and later
outcomes) is summarized and fed back in as context before each generation
run — retrieval/context-based learning, no ML training infra required.

**Guardrail — avoid premature convergence:** once the loop favors past
winners, there's a natural pull toward only generating variations of them,
which quietly kills exploration. ✅ **decision:** 70% exploit / 30% explore
per batch as the M2 starting default — a simple fixed split, not adaptive
bandit logic, since volume doesn't justify more yet. Revisit at M3 once
there's enough data to make it adaptive.

**Longer-term extension (M3+):** once on a local image-gen model, the log of
approved/high-performing designs becomes training data for periodically
fine-tuning a LoRA — the loop eventually shapes the model itself, not just
the prompts feeding it.

## 7. Open questions to resolve before building anything

- Apply for Google Trends API alpha access — action item, no decision
  needed, zero cost, do in parallel with everything else. (Program is
  confirmed real, launched July 2025, free, rolling approval.)
- Everything else in this spec is now either resolved (✅) or an explicit,
  revisitable decision. Nothing remains open in section 9 as of this
  revision. What remains is building it and letting the learning-loop
  thresholds prove themselves against real data.

## 8. Parked ideas (separate from core pipeline, revisit later)

- **Email triage agent:** Gmail/Outlook-connected agent flagging Etsy/Gelato
  policy-update emails and summarizing promotional noise. Transactional
  emails (orders, shipping) are better sourced from the APIs directly via
  the performance monitor, not parsed from email. Build after core pipeline
  is stable — not a pipeline dependency.
- **Marketing suite on top of the learning loop:** separate Instagram/TikTok
  accounts promoting the shop, built on the same asset-creation and
  performance-learning components once they exist. Real scope of its own —
  each platform has its own API, posting cadence, and content norms. Not
  before the core pipeline and learning loop are proven.
- **Own-photography pipeline:** a parallel automated setup using the user's
  own photography as input instead of AI-generated designs. Different
  content-sourcing model, not a variant of the existing pipeline — would
  need its own mini-spec (sourcing/selection method, editing/prep steps)
  when revisited.
- **Read-only pipeline status view (M2 nice-to-have, not a blocker):**
  Telegram is a queue you react to, not a place you go look things up — it
  doesn't give an at-a-glance view of pending/live/rejected/failed
  candidates or running ad/image-gen spend. Once M2 is live, a persisted,
  re-openable status view (pulling from the local SQLite store and the
  Etsy/Gelato APIs on each open) covering pending/live/rejected/failed
  counts, the current batch's candidates with thumbnails, and running
  spend totals is worth adding. Not needed for M1 — premature for a
  not-yet-validated niche. Revisit a fuller dashboard only if M3's
  feedback loop needs more analysis surface than a static grid gives you.
- **SerpApi's Google Trends API as a trend-research booster (evaluated,
  parked, not adopted for M1):** technically a good fit — its Google
  Trends API mirrors the public site (interest-over-time, related
  queries/topics, geo breakdown) plus a dedicated "Trending Now" endpoint,
  as structured JSON. Estimated usage at this pipeline's cadence (twice-
  daily batch + occasional `/research` triggers) is roughly 140–200 calls/
  month, comfortably inside SerpApi's free tier (250 searches/month, 50/
  hour throughput, confirmed directly from serpapi.com/pricing) — so cost
  is not the blocker.
  - **Why parked anyway:** Google filed suit against SerpApi in December
    2025 (Northern District of California) alleging DMCA circumvention and
    Terms of Service violations from large-scale search-result scraping,
    seeking $2.8M in damages *and* a permanent injunction that could shut
    down SerpApi's core business model. SerpApi moved to dismiss in
    February 2026; oral argument is scheduled for May 19, 2026, and the
    case is unresolved as of this writing. Depending on a vendor whose
    entire scraping-based product could be enjoined mid-operation is a
    real continuity risk for a pipeline stage meant to run indefinitely —
    not a one-time integration risk.
  - **Why it's safe to start without it:** the spec's existing trend-
    research path (official Google Trends API alpha, already applied for,
    plus the Claude-web-search fallback already in step 1) covers this
    pipeline's actual volume needs without taking on that risk.
  - **Revisit if:** the Google v. SerpApi case resolves in SerpApi's favor
    (watch for the outcome of the May 2026 hearing) or is dismissed, *or*
    the official Google Trends alpha access and Claude-web-search research
    turn out to be insufficient in practice once M1/M2 are running on real
    data. Re-check SerpApi's then-current pricing and terms before
    adopting, since both may have changed.

## 9. Decisions Needed

**None open as of this revision.** All five items raised across prior
revisions are resolved:

- D1 (Offsite Ads threshold) — resolved in v0.4.1: shop confirmed under
  the $10k/365-day threshold, Offsite Ads off. See section 1.
- D2 (single- vs. multi-image listings) — resolved in v0.4.1: multi-image
  galleries in scope for M1. See section 3, steps 3 and 6.
- D3 (critic-pass retry policy) — resolved in v0.4.1: 3 auto-regenerate
  attempts, then abandon. See section 3, step 5.
- D4 (Gelato native lifestyle/room-mockup support) — resolved in v0.4.2 via
  a live Claude Code API test: confirmed native, no separate build item.
  See section 3, step 3, and section 4.
- D5 (Gelato product delete/archive endpoint) — resolved in v0.4.2 via the
  same test: `DELETE /v1/stores/{storeId}/products/{productId}` confirmed
  working. See section 3, step 5.

v0.4.3 fixed a Telegram API mechanism error (`sendMediaGroup` +
`sendMessage` instead of one combined call, section 3 step 6; section 4)
flagged by a second red-team pass — a factual correction, not a tradeoff,
so it did not introduce a new decision item.

This revision (v0.4.4) evaluated SerpApi's Google Trends API as a
trend-research booster and parked it (section 8) rather than adopting it —
your call, made with full information (technical fit, free-tier cost fit,
and the active Google v. SerpApi litigation risk all surfaced). Not listed
as an open decision since it was resolved, not deferred.

This section is kept (rather than removed) so the counter-reviewer can see
at a glance that nothing was silently dropped between revisions. If new
ambiguities or tradeoffs surface during build, they belong here.
