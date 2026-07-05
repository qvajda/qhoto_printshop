# Etsy AI-assisted POD pipeline — spec v0.3 (ready to build)

Status: core architecture, milestones, learning loop, and trend research are
resolved. Remaining 🔶 markers are minor and self-contained (target buyer,
price point, success metric — deliberately left for M1's real data rather
than guessed). Ready to move from spec to build once the Etsy app is
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
- **Price point:** ✅ resolved — ~$22 (small/mid, ~12x16) and ~$32 (larger,
  ~18x24), unframed (skip framing for the first test). Target 40–50% margin
  after Etsy fees (~9%). 🔶 still need to confirm actual Gelato base cost
  per size to lock in real margin — quick check via the same quote/order
  API already tested.
- **Success metric:** ✅ resolved and recalibrated — new, unranked listings
  realistically run ~0.5–1.5% conversion and ~1–2% CTR, roughly one sale
  per 5,000–15,000 impressions before reviews/ranking kick in. One
  profitable sale in month 1 from a *single* listing isn't reliable; the
  original "at least one net-profitable design" metric holds, but expect
  it to require 8–12 listings (a few designs × 2–3 sizes) to have decent
  odds, not one design tested in isolation.
- **Paid ads:** ✅ confirmed — small ad budget, capped at **$5/day**. Real
  recurring spend beyond Etsy fees and the subscription, accepted
  deliberately rather than inherited by default.
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
- **Hard no-go list (baked into generation prompts, not just review):**
  no named artists' styles, no recognizable characters/franchises/logos, no
  implied celebrity likeness, no claims of "hand-painted" or "original
  artwork."
- **Human review gate:** every design is reviewed by you before publish — no
  exceptions, regardless of how automated the rest of the pipeline gets.

## 3. Pipeline layer (see diagram above)

1. **Trend research** — three inputs feeding a shared "trend candidates" pool
   (niche + urgency + rationale), consumed by design generation:
   - **Trending now scan (scheduled):** ✅ investigated — Google Trends has
     an official API but it's alpha, rolling/limited access (worth applying
     now, zero cost, same pattern as the Etsy app); Etsy SEO tools (eRank,
     Marmalead, EtsyHunt) are seller dashboards, not developer APIs, so
     skip them. Pragmatic approach: use a Claude API call with web search
     enabled as the actual research engine, supplemented by Etsy's own API
     to check candidate-keyword listing counts/favorites as a demand proxy.
   - **Event lookahead (scheduled):** ✅ resolved and dated — two-layer as
     before, now with confirmed near-term dates researched from today
     (July 4, 2026):

     | Window | Relevance |
     |---|---|
     | **Nov 10 – Dec 20 (holiday peak)** | Biggest window overall — 27–38% of annual Etsy revenue |
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
   - **Telegram on-demand:** ✅ resolved — command-polling cadence set to
     **hourly** (cheap, decoupled from the twice-daily batch poll). A
     `/research <topic>` command triggers scoped research; the actual
     research still runs on the normal schedule. Results come back as a
     digest and feed into the next scheduled batch as a prioritized
     candidate, rather than immediately spending image-gen budget on an
     ad hoc request.
2. **Design generation** — image-gen API call(s) per candidate, driven by
   trend output.
3. **POD mockup** — render the design onto a Gelato poster product via
   Gelato's API.
4. **Compliance draft** — auto-fill the disclosure template + a first-pass
   title/tags/description.
5. **Telegram digest (daily batch)** — one message (or short batch of
   messages) with mockup image + draft listing text + Approve / Edit /
   Reject buttons per candidate.
6. **Evening run** — reads your responses; approved items get published to
   Etsy (assigned to the dedicated "AI-generated designs" section via
   `section_id`), rejected ones are discarded, "edit" ones get a note fed
   back into step 2 for regeneration.
7. **Fulfillment** — handled entirely by Gelato once an order comes in; no
   pipeline involvement needed here.
8. **Performance monitor (future, post-M2)** — slower-cadence job (daily/
   weekly) pulling Etsy order data + Gelato fulfillment status, digesting via
   Telegram, feeding "what's selling" back into step 1 (trend research) and
   step 2 (design generation). Needs real listing data to exist before it's
   useful — sequence after M2 is live.

## 4. Technical layer

- **Runs as:** a scheduled script (two runs/day), not a persistent service.
  Buildable in Claude Code as a real, testable codebase.
- **External dependencies:**
  - Image generation — **decision:** Replicate, hosting FLUX.1 [schnell],
    for M1 (validate fast, pay-per-image, no setup cost). Deliberately the
    same license-clean model family planned for local/M2+ self-hosting —
    prompting behavior carries over directly at migration, no throwaway
    work. Switch to local/rented-GPU hosting for M2+ once a niche is
    validated, at which point a photography-style LoRA fine-tune becomes
    worth building as a brand differentiator.
  - Gelato API (product mockup + order fulfillment) — ✅ confirmed via a live
    test call: `products:create-from-template` returns a working mockup
    `previewUrl` end to end. **Templates vs. products:** templates (reusable
    blueprints — size, variants, default mockup style) are dashboard-only,
    no creation API found; products (a specific design instantiated from a
    template) are what the pipeline actually automates, and that's already
    confirmed working. Existing art print templates are reused as-is — no
    template management needed in normal operation.
  - Etsy Open API v3 (listing creation) — 🕓 **app registered, pending
    approval** (personal access, own shop). ✅ process clarified: apps get
    personal access immediately on registration (own shop, up to 5 shops) —
    the heavier "commercial access" review only applies to apps serving
    other sellers, not this case. Shop-section mechanism confirmed real:
    `createShopSection` + `updateListing` with `section_id`, via
    `shops_w`/`listings_w` scopes.
  - 💡 Etsy publishes a free **Dev MCP server** (no API key needed) that
    gives an AI assistant full knowledge of the API spec — useful for
    verifying endpoint capabilities without needing full OAuth access
    (this is how the views/favorites vs. CTR question got resolved).
  - Telegram Bot API (digest message + inline buttons, polled twice daily —
    no webhook/always-on requirement)
- **Data storage:** 🔶 likely a simple local file or lightweight DB tracking
  candidate designs, their status (pending/approved/rejected/live), and
  daily snapshots of `views`/`numFavorers` per live listing (required since
  Etsy only returns cumulative counters — deltas must be computed locally).

## 5. Milestones (crawl → walk → run)

- **M1 — build for real, run manually one item at a time:** skip a separate
  fully-manual rehearsal (existing Etsy/Gelato operational experience already
  covers that ground). Build the actual pipeline stages, but trigger them
  manually on single candidates before turning on the schedule and batch
  volume — validates design/niche/compliance quality without a throwaway
  manual phase.
- **M2 — semi-automated:** the scheduled script handles research/generation/
  mockup/compliance draft; Telegram digest + your approval gate; publish is
  still a deliberate step you trigger.
- **M3 — feedback loop:** performance monitor comes online once there's real
  listing data; more automation only if M2 proves the unit economics work.
  Human review gate stays regardless.

## 6. Learning loop (approvals + sales/CTR feed back into generation)

Two feedback signals, deliberately treated differently — not one loop, two,
at different speeds and different confidence levels:

- **Fast loop — your Telegram decisions.** Dense signal, available daily
  from the start of M2. Every candidate's decision (approve/edit/reject +
  any edit notes) is logged and can shape generation aggressively from
  day one.
- **Slow loop — sales & engagement data (not CTR).** ✅ investigated: Etsy
  exposes no impressions/CTR/analytics endpoint at all — this was the wrong
  mental model. Real signal available: `views` (cumulative, tabulated once
  daily, listing-detail endpoint only) and `numFavorers` (cumulative,
  available everywhere), plus actual orders via `ShopReceipt`. **Treated as
  advisory, not authoritative**, until **14 days since listing went live**
  (✅ decision — starting heuristic, revisit once real data exists) — daily
  tabulation lag makes early counts unreliable and a fresh listing's
  `views: 0` is ambiguous (genuinely zero vs. not-yet-tabulated vs. fetch
  error).
- **Implementation note:** since Etsy only returns cumulative counters, the
  performance monitor must snapshot `views`/`numFavorers` daily itself and
  compute deltas — there's no "views today" field to read directly.

**Mechanism:** not model fine-tuning. A structured decision log (design
metadata: trend source, prompt, style/theme tags, your decision, and later
outcomes) is summarized and fed back in as context before each generation
run — retrieval/context-based learning, no ML training infra required.

**Guardrail — avoid premature convergence:** once the loop favors past
winners, there's a natural pull toward only generating variations of them,
which quietly kills exploration. ✅ **decision:** 70% exploit / 30% explore
per batch as the M2 starting default — a simple fixed split, not adaptive
bandit logic, since volume doesn't justify more yet. Revisit at M3 once
there's enough data to make it adaptive.

**Note:** the slow loop's data source (views/favorites, not CTR) was
confirmed via direct investigation of the Etsy API — see the resolved
finding above. No longer a blocker.

**Longer-term extension (M3+):** once on a local image-gen model, the log of
approved/high-performing designs becomes training data for periodically
fine-tuning a LoRA — the loop eventually shapes the model itself, not just
the prompts feeding it.

## 7. Open questions to resolve before building anything

- Apply for Google Trends API alpha access — action item, no decision
  needed, zero cost, do in parallel with everything else
- Everything else in this spec is now either resolved (✅) or an explicit,
  revisitable decision. What remains is building it and letting the
  learning-loop thresholds prove themselves against real data.

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