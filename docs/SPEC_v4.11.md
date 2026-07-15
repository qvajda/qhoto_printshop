# Etsy AI-assisted POD pipeline — spec v0.4.11 (variant listings + Gelato-pushes-we-patch, post-first-live-run)

Status: **All Decisions Needed items resolved (D1–D8a).** The Etsy app is
approved and the first end-to-end live run has happened.

**v4.11 changes (this revision) — driven by the first live run's feedback.**
The live run exposed that the earlier "one Etsy listing per size, created by
the pipeline via the Etsy API" model is wrong on two counts, so this revision
supersedes it. See `docs/superpowers/specs/2026-07-16-live-test-fixes-brainstorm.md`
for the full root-cause analysis. The two model changes:

1. **One Etsy listing per design, with sizes as variants** (not one listing
   per size). Each aspect-ratio group is ONE listing whose sizes are Etsy
   variations, each variation at its own price. The 12 config "slots" are
   really **2 Gelato multi-variant templates** (one portrait, one landscape)
   whose variants are the sizes — not 12 single-variant templates.
2. **Gelato pushes the Etsy listing; the pipeline patches it** (not the
   pipeline creating listings directly). The Gelato store is connected to
   Etsy and auto-mirrors each created Gelato product into an Etsy listing.
   The pipeline stops calling the Etsy listing-creation API; instead, after
   Gelato syncs the listing, the pipeline resolves the Etsy `listing_id` and
   PATCHes it (title, description, tags, `taxonomy_id`, `who_made`,
   `when_made`, `is_supply`, `shop_section_id`, `production_partner_ids`) via
   `updateListing`, plus per-variant price via `updateListingInventory` if
   Gelato doesn't carry it.

These changes touch section 1 (size lineup), section 2 (AI metadata),
section 3 (steps 2–7, the publish flow), and section 4 (template mapping,
integration model). Passages below are updated accordingly; the business/
research/fee layers are unchanged from v4.10.

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
- **Shop currency:** ✅ resolved — EUR. All prices, costs, and fee figures
  throughout this spec are EUR.
- **Size lineup, aspect-ratio groups, and final retail prices — ✅
  resolved:** six sizes, each in both portrait and landscape orientation.
  These map to **two Gelato multi-variant templates** (one portrait, one
  landscape); each of the six sizes is a *variant* within its orientation's
  template, not its own template (section 4). Costs are real, from
  `gelato_premium_matte_poster_prices_BE_2026-07-05.csv`. The six sizes
  fall into **three aspect-ratio groups**, based on their actual
  dimensions — this grouping drives the review flow in section 3:

  | Group | Sizes | Aspect ratio | Retail price(s) |
  |---|---|---|---|
  | **Primary group** | 21x29.7 cm / 8x12″ *(primary)*, A3, A2, A1 | ~1:1.414 (ISO A-series ratio — 8x12″ is literally A4 dimensions, and A3/A2/A1 share the exact same ratio) | €24 / €35 / €39 / €49 |
  | **5x7 group** | 13x18 cm / 5x7″ | ~1:1.385 — close to, but distinctly different from, the primary group's ratio | €19 |
  | **10x24 group** | 25x60 cm / 10x24″ | ~1:2.4 — a genuinely different, elongated/panoramic ratio | €45 |

  Full cost table:

  | Size | Total cost | Retail price | Resulting margin | Tier |
  |---|---|---|---|---|
  | 13x18 cm / 5x7″ | €12.88 | €19 | ~21% | Entry |
  | 21x29.7 cm / 8x12″ *(primary)* | €13.64 | €24 | ~32% | Entry |
  | A3 (29.7×42 cm) | €17.92 | €35 | ~38% | Standard |
  | A2 (42×59.4 cm), both orientations | €19.60 (landscape) / €20.21 (portrait) | €39 | ~39% (landscape) / ~38% (portrait) | Standard |
  | 25x60 cm / 10x24″ | €20.57 | €45 | ~44% | Standard |
  | A1 (59.4×84.1 cm) | €23.45 | €49 | ~42% | Standard |

  - **Entry-tier rationale:** 5x7″ and 8x12″ intentionally carry lower
    margin (~21%, ~32%) than the rest (~38–44%) — the impulse/first-
    purchase sizes for the price-sensitive self-purchase-redecorator
    segment, versus the "statement piece" sizes (A3/A2/10x24″/A1) closer
    to the original 40–50% target.
  - **A2 orientation cost asymmetry:** Gelato's own cost differs slightly
    by orientation for A2 only. Both orientations are listed at the same
    €39 (one round number preferred over two near-identical prices),
    accepting a very slightly thinner margin on the portrait variant.
  - **10x24″ priced above A2 despite covering less print area:**
    intentional — Gelato's real production cost for this narrow/elongated
    format is higher than A2's, likely reflecting real paper-waste/
    handling differences for that aspect ratio. Prices follow real cost,
    not physical size.
- **Success metric:** ✅ resolved and recalibrated — new, unranked listings
  realistically run ~0.5–1.5% conversion and ~1–2% CTR, roughly one sale
  per 5,000–15,000 impressions before reviews/ranking kick in. One
  profitable sale in month 1 from a *single* listing isn't reliable; the
  original "at least one net-profitable design" metric holds. One
  approved design fans out to up to 6 listings across the three aspect-
  ratio groups (section 3), so reaching an 8–12-listing sample size takes
  roughly 2 fully-approved designs — fewer if a design's 5x7 or 10x24
  group ends up not approved (see section 3).
- **Paid ads:** ✅ confirmed — small ad budget, capped at **€5/day** (Etsy
  Ads, distinct from Offsite Ads below). Real recurring spend beyond Etsy
  fees and the subscription, accepted deliberately rather than inherited
  by default.
  - **Etsy fees, precisely:** $0.20 listing fee + 6.5% transaction fee +
    ~3% + $0.25 payment processing ≈ **9.5% + $0.45 flat per order**, as
    Etsy states them in USD globally; converts at Etsy's rate at time of
    charge for a EUR-listing shop (approximated here as ~€0.40) — a
    small, fluctuating variable, not a fixed EUR figure.
  - **Offsite Ads — ✅ resolved:** confirmed the shop has never crossed
    $10,000 in sales in any trailing 365-day window, so Offsite Ads is
    optional, and it's currently turned **off** in Shop Manager. The
    margin figures above do not need to absorb the 12% Offsite Ads cut.
- **Definition of "worth it":** subscription cost offset, not a business.
  Keep this framing — it prevents scope creep into a real e-commerce build.

## 2. Content / compliance layer

- **Asset type:** AI-generated poster/wall-art imagery. No text-heavy
  products in this pipeline (that's a separate, simpler idea if you ever want
  it).
- **Etsy listing category:** "Seller-prompted AI creation" + "produced by a
  production partner" — both disclosures required on every listing, across
  all three aspect-ratio groups.
- **Disclosure template (draft, to refine):**
  > "This design was created using AI image generation from the seller's own
  > prompts, then selected, edited, and prepared for print by the seller.
  > Printed and shipped by our production partner, Gelato."
- **Required listing metadata (compliance-critical, not just copy):** the
  disclosure text above is necessary but not sufficient. Etsy's Creativity
  Standards for AI-generated items also require specific API fields to be
  set correctly — getting these wrong is the most common cause of AI
  listings getting flagged or taken down, not a cosmetic issue. See section
  4, "Static configuration," for the specific fields (`who_made`,
  `production_partner_ids`, `taxonomy_id`, `shipping_profile_id`) and how
  they're resolved. These apply identically to every listing, in every
  group, generated from an approved design. Under v4.11, they are set by the
  pipeline's **patch** of the Gelato-created listing (section 3, step 7),
  not at pipeline-side listing creation.
- **"What tools are used to make this item?" — the AI-generator tick.** The
  live run showed this Etsy question unset on published listings. Note the
  constraint (verified: `who_made` has only three enum values —
  `i_did`/`someone_else`/`collective` — and no separate AI-disclosure field
  exists in the listing API): Etsy surfaces "Designed by a seller / made
  with an AI generator" as the *display treatment* of `who_made: i_did`,
  not as a distinct settable API field. So the compliance mechanism stays:
  `who_made: i_did` + the written disclosure text in the description. If a
  dedicated AI-tools API field has since been added, set it in the patch
  step; otherwise the description disclosure is required and remains the
  authoritative signal — do not drop it.
- **Generated text must respect Etsy's hard format limits, checked
  programmatically, not just by convention:** 13 tags max (≤20 characters
  each) and a 140-character title cap. Violating these isn't a soft SEO
  miss — it's an API validation error at publish time. The compliance-draft
  step (section 3, step 4) must validate against these limits before a
  candidate ever reaches the Telegram digest, and the same validation
  applies to each group's size-adjusted title before its own follow-up
  digest entry (section 3, step 7).
- **Alt text per image:** generate alt text for every image in every
  group's gallery (section 3), not just the primary group's, in the same
  compliance-draft-style pass. Free SEO/accessibility value, costs nothing
  extra to add.
- **Hard no-go list (baked into generation prompts, not just review):**
  no named artists' styles, no recognizable characters/franchises/logos, no
  implied celebrity likeness, no claims of "hand-painted" or "original
  artwork."
- **Human review gate:** every design is reviewed by you before publish —
  no exceptions. ✅ genuinely per-aspect-ratio-group (section 3): the
  primary group is reviewed first; the 5x7 and 10x24 groups each get their
  own separate review before they publish, since their aspect ratios (and
  therefore the actual crop/composition Gelato renders) differ from the
  primary. The critic pass (section 3) is additive to this gate at every
  group level, not a replacement for any of them. **Every review response
  — regardless of which group it's for — only counts if it comes from
  you** (section 4's Telegram admin/allowlist ID).

## 3. Pipeline layer

1. **Trend research** — three inputs feeding a shared "trend candidates" pool
   (niche + urgency + rationale), consumed by design generation:
   - **Trending now scan (scheduled):** ✅ investigated — Google Trends has
     an official API but it's alpha, rolling/limited access (worth
     applying now, zero cost, same pattern as the Etsy app); Etsy SEO tools
     (eRank, Marmalead, EtsyHunt) are seller dashboards, not developer APIs,
     so skip them. Pragmatic approach: use a Claude API call with web
     search enabled as the actual research engine, supplemented by Etsy's
     own API to check candidate-keyword listing counts/favorites as a
     demand proxy. A third-party option (SerpApi's Google Trends API) was
     evaluated and deliberately not adopted for now — see section 8 for the
     rationale and what would need to be true to revisit it. **✅ endpoint
     confirmed live:** `GET /v3/application/listings/active`
     (`findAllListingsActive`), api-key-only auth (no OAuth token needed),
     keyed by a `keywords` query param; response gives `count` (listing
     count for the keyword) and each result's `num_favorers` (favorites).
     **No view-count field exists on this endpoint** — the demand proxy is
     listing-count and favorites only, not views. See the CHANGELOG and
     `docs/etsy_call_response_example_from_manual_tests.txt` for the raw
     verified request/response.
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
     ad hoc request. **Every inbound command is checked against the
     Telegram admin/allowlist ID (section 4) before it's treated as real —
     messages from any other Telegram user are ignored outright.**
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
   trend output. One design (one generated image) per candidate — the
   artwork is shared across all six sizes and all three groups; only the
   print dimensions, crop/composition, and Gelato variant differ per
   group.
   - **The generated image must be the flat artwork itself — full-bleed 2D
     art that fills the frame edge to edge — NOT a photograph of a poster on
     a wall or in a room.** The first live run generated lifestyle/room
     renders (because the prompt and niche carried scene words like "wall
     poster / wall art print"), and that room photo became the printed
     artwork. The generation prompt must force flat art (no frame, no
     border, no wall, no room, no mockup) and the injected niche must
     describe subject/style only, not the product container. Gelato adds the
     mockup framing at step 3; generation must not.
3. **POD mockup — primary size only.** Render the design onto **one**
   Gelato poster product at the candidate's **primary size** (21x29.7 cm /
   8x12″), created from the **portrait (or landscape) multi-variant
   template's 8x12 variant** (section 4) — there is no way to discover
   templates dynamically at runtime. ✅ confirmed: a single
   `products:create-from-template` call returns the full image gallery for
   that product automatically — flat mockup plus lifestyle/room-context
   images. The pipeline orders this gallery with **the flat mockup first,
   followed by the lifestyle/room-context images**. **No other size is
   rendered or created here** — the primary group's other three sizes (A3,
   A2, A1), and both the 5x7 and 10x24 groups, are only created after their
   respective approvals, in step 7.
   - **Pre-review Etsy leak — must be prevented.** Because the Gelato store
     is Etsy-connected (v4.11), creating this pre-review Gelato product can
     cause Gelato to push an Etsy listing before you've approved anything —
     the live run leaked exactly one such listing. Creating the product here
     must NOT result in a live/public Etsy listing until approval: keep it a
     non-synced/hidden draft and only trigger the Etsy publish + patch on
     approval (step 7), or obtain the mockup gallery from a non-publishing
     Gelato preview path and defer product creation to approval. (Exact
     Gelato flag behavior is an open verification item — see the brainstorm
     doc.)
4. **Compliance draft** — auto-fills, for the primary-size listing:
   - the disclosure template text (section 2);
   - the required listing metadata fields — `who_made`,
     `production_partner_ids`, `taxonomy_id`, `shipping_profile_id` — from
     the static configuration in section 4;
   - a first-pass title/tags/description, validated against Etsy's format
     limits (13 tags ≤20 characters, 140-character title) before moving on;
   - alt text for every image in the gallery produced by step 3.
   - This draft is the shared base text for the design — step 7 reuses it
     as the single listing text for each group's listing. Under v4.11 a
     group is ONE listing with size variants, so the title is a single
     design-level title (no per-size suffix); price is set **per variant**
     (each size's own EUR price, section 1), not per listing. The title is
     still validated against the 140-character cap.
5. **Critic pass — primary group.** A separate model call (a vision-
   capable Claude call, distinct from the generation call so it isn't
   grading its own homework) reviews every image in the primary-size
   gallery plus the draft title/tags/description against a fixed rubric
   before the candidate reaches you:
   - hard no-go list compliance (named styles, characters/logos, implied
     hand-painted/celebrity claims) — checked across all gallery images;
   - basic image-quality checks (obvious artifacts, garbled/watermark-like
     elements, off-center or cut-off composition) on each image;
   - whether the draft title/description actually match the images and
     niche.
   - Output is a simple **pass/fail plus reason**, not a tunable score.
   - **Fail — retry policy:** up to **3 auto-regenerate attempts** per
     candidate, each with the prior failure reason fed back as a prompt
     correction (design generation → primary-size mockup → compliance
     draft → critic pass, repeated). **After 3 failed attempts, abandon
     the candidate entirely** — no further retries, and none of the three
     groups proceed:
     - **Log it locally as `failed`**, keeping the full record (trend
       source, every attempt's prompt, every attempt's critic-pass failure
       reason, style/theme tags) in the same structured decision log as
       everything else (section 6).
     - **Clean up the Gelato-side product. ✅ confirmed:**
       `DELETE /v1/stores/{storeId}/products/{productId}` is a real,
       working endpoint — call it for the primary-size product created
       during each failed attempt.
     - **Trigger the Go/Hold/Kill fallback** (step 1) to bring in the
       next-highest-scored candidate or a safe-evergreen-bucket item.
   - **Pass:** proceeds to the Telegram digest (below), and only then can
     the 5x7 and 10x24 groups ever be considered (step 7).
   - This is additive to the human review gate in section 2, not a
     replacement for it.
   - Implemented as its own named, independently testable stage (see
     section 4), since it needs the rendered gallery images as input.
6. **Telegram digest (daily batch) — primary group review.** For every
   candidate that passed the primary group's critic pass, sent as **two
   separate Telegram API calls**, not one combined call — Telegram's Bot
   API does not support attaching an inline keyboard to a media group —
   **both sent to the chat_id resolved from the Telegram admin ID
   (section 4)**:
   - **`sendMediaGroup`** — the primary-size image gallery as an album
     (flat mockup first, then lifestyle/room-context images) — the only
     gallery that exists at this point, standing in for the whole design.
   - **`sendMessage`** (sent immediately after, same candidate) — the
     draft listing text plus the Approve/Edit/Reject inline keyboard,
     tagged with the candidate ID.
   - **✅ Resolved (D6): approving the primary group does not
     auto-publish everything.** It publishes the primary group only
     (8x12″, A3, A2, A1 — see step 7) and triggers the 5x7 and 10x24
     groups to each go through their *own* critic pass and their *own*
     separate follow-up digest entry, per step 7 below — reviewed as
     their own aspect-ratio groups, not bundled with the primary and not
     reviewed size-by-size individually either.
   - This repeats once per candidate in the batch — "digest" describes
     the batch cadence, not a single Telegram message.
7. **Evening run — reads your responses and drives the group-by-group
   fan-out.** Every incoming callback (button press) is checked against
   the Telegram admin/allowlist ID (section 4) before being treated as a
   real decision — a callback from any other user is discarded and
   logged, not acted on.
   - **Primary group rejected:** discarded and logged the same way as
     critic-pass failures (image gallery + full listing text + decision).
     Nothing else happens — the 5x7 and 10x24 groups are never generated.
   - **Primary group edited:** a note fed back into step 2 for
     regeneration (still at the primary size only, per step 3). Nothing
     else happens yet.
   - **Primary group approved:**
     1. **Publish the primary group immediately, no further review, as ONE
        Etsy listing with four size variants.** The primary group is a
        single Gelato product created from the multi-variant template with
        all four variants — 8x12″ (€24), A3 (€35), A2 (€39), A1 (€49) — at
        their per-variant prices. Gelato mirrors it into **one** Etsy
        listing whose size variations are those four. **No critic pass and
        no separate approval for these** — they share the primary's aspect
        ratio (the ISO A-series ratio; the 8x12/2:3 vs A-series 0.707
        difference is a small crop, not a re-composition), so the same
        composition renders across all four, just scaled. Because they are
        one listing, they inherently share `section_id`, disclosure text,
        `who_made`/`production_partner_ids`/`taxonomy_id`, and
        `shipping_profile_id`.
        - **Publish = Gelato-pushes-we-patch (v4.11).** The pipeline does
          not create the Etsy listing. Gelato's Etsy sync creates it; the
          pipeline then resolves the Etsy `listing_id` (from Gelato's
          product `externalId` once the async sync populates it) and
          PATCHes the listing via `updateListing` to set the real title,
          description, tags, `taxonomy_id`, `who_made`, `when_made`,
          `is_supply`, `shop_section_id`, and `production_partner_ids`.
          Per-variant price is set via `updateListingInventory` if Gelato
          doesn't carry it. This patch is what fixes the live run's missing
          title/description/tags/section/partner — those were missing
          because Gelato's raw push, not the pipeline, had governed the
          listing.
     2. **Then, independently, generate and review the 5x7 group and the
        10x24 group** — each is its own aspect-ratio group with a
        genuinely different crop/composition from the primary (5x7 is
        close to but not exactly the primary's ratio; 10x24 is a
        meaningfully different, elongated ratio), so each gets its own
        check before publishing:
        - Create that group's Gelato product (one product, that group's
          single size as its variant) from the same approved artwork,
          **re-cropped to that size's aspect ratio — a real cover-crop, not
          a fit/letterbox.** No new image-generation call (the base design
          was already approved); only the crop differs per group. The live
          run's 10x24 white-bars bug was exactly this crop step missing —
          the ISO image was dropped raw into the elongated placeholder in
          fit/contain mode. Cover-crop: 10x24 crops the sides (keeps full
          height), 5x7 crops top/bottom.
        - Run the same critic-pass rubric (step 5) against that group's
          resulting gallery, reusing the already-approved title/
          description as the base text.
        - **Pass:** send its own follow-up digest entry (same
          `sendMediaGroup` + `sendMessage` mechanism as step 6, to the
          same admin chat_id) with its own Approve/Edit/Reject, sent
          right away in this same evening run rather than waiting for
          the next scheduled digest.
        - **Fail:** up to 3 crop/composition retry attempts (same cap and
          logging pattern as step 5), then abandon **only that group** —
          `DELETE` its Gelato product, log it, and leave the rest of the
          design's already-published groups untouched. A design can
          therefore end up selling at 4, 5, or 6 sizes depending on
          whether its 5x7 and/or 10x24 groups pass review — this is
          expected, not an error state.
        - **You approve/edit/reject each of these two groups
          independently** — e.g. you can approve the 10x24 group and
          reject or edit the 5x7 group for the same design. Approving one
          publishes that group's single listing (its one size as its sole
          variant) the same Gelato-pushes-we-patch way as the primary group
          (own `section_id`, disclosure, metadata, `shipping_profile_id`);
          rejecting or editing behaves the same as it does for the primary
          group, scoped to that one group.
     - If a group's Gelato product creation or Etsy publish fails for
       operational reasons (not a critic-pass fail), retry once
       automatically; if it still fails, leave that group unpublished,
       publish/keep the groups that succeeded, and surface the failure in
       the next digest.
     - **Retries must be idempotent — no duplicate Gelato products.** The
       live run created some Gelato products *twice* (a create that
       succeeded server-side, then a poll timeout, then a retry that created
       a second product). Before creating, reuse the group's already-stored
       `gelato_product_id` if present; on a genuine failed create, delete
       any orphan first. Applies to every Gelato create path (primary
       mockup, group mockup, publish) — route them through one shared
       create-or-reuse helper so the guard lives in one place.
8. **Fulfillment** — handled entirely by Gelato once an order comes in on
   any listing's size variant; no pipeline involvement needed here.
9. **Performance monitor (future, post-M2)** — slower-cadence job (daily/
   weekly) pulling Etsy order data + Gelato fulfillment status, digesting
   via Telegram, feeding "what's selling" back into step 1 (trend research)
   and step 2 (design generation). Needs real listing data to exist before
   it's useful — sequence after M2 is live. Tracks each **listing's**
   `views`/`numFavorers`/orders (up to three listings per design — one per
   aspect-ratio group), with order-level size-variant breakdown where Etsy
   exposes it, and rolls up to the design level when feeding the learning
   loop. The
   decision log also carries Go/Hold/Kill state, per-group approve/edit/
   reject outcomes, and failed/abandoned attempts at both the whole-design
   level (primary group) and the individual-group level (5x7/10x24).

## 4. Technical layer

- **Runs as:** a **cron-triggered script on two cadences**, not a
  persistent service and not one monolithic agent loop. Buildable in
  Claude Code as a real, testable codebase; Claude Code is the tool used to
  *build* this, but the *runtime* is plain scheduled functions, not a
  long-running agentic session.
  - **Hourly, lightweight poll:** calls Telegram's `getUpdates`, checks for
    new `/research <topic>` commands and pending Approve/Edit/Reject
    responses — now potentially up to three per design (primary group,
    5x7 group, 10x24 group) — after checking the sender against the
    Telegram admin/allowlist ID below, writes valid ones to local state.
    No image-gen, Gelato, or Etsy calls happen here.
  - **Twice-daily, heavy batch:** morning run does trend research → design
    generation → primary-size mockup → compliance draft → critic pass
    (primary group, up to 3 regenerate-and-retry loops) → Telegram digest
    (primary group review); evening run reads the primary-group decision,
    publishes the primary group on approval, then immediately generates,
    critic-passes, and sends follow-up digest entries for the 5x7 and
    10x24 groups (their approve/reject responses are then picked up by a
    later hourly poll, same mechanism as the primary group's).
  - Each pipeline stage (research, generate, primary-mockup, compliance-
    draft, critic-pass, digest, publish-primary-group, group-mockup,
    group-critic-pass, group-digest, publish-group, cleanup) is a
    **discrete, independently callable function**, parameterized by which
    group it's operating on where relevant. All stages share the local
    state store below.
- **Static configuration** — resolved once before M1, referenced by ID at
  runtime; none of these can be discovered dynamically by the relevant API,
  so they have to exist as owned config before the first real run:
  - **Telegram admin/allowlist user ID (new in this revision):** your
    numeric Telegram user ID, obtained once from BotFather/the bot's own
    `getUpdates` response after you message it directly. Serves **two
    distinct roles**, both load-bearing:
    1. **Allowlist/access control** — every inbound `getUpdates` message
       and button-press callback is checked against this ID before the
       pipeline treats it as a real command or decision (section 3, steps
       1 and 7). Anything from another sender is discarded and logged,
       never acted on. This is the only access-control layer on the bot —
       there is no separate authentication scheme, so this ID is
       effectively the credential.
    2. **`chat_id` for outbound messages** — every `sendMediaGroup` and
       `sendMessage` digest call (section 3, steps 6 and 7) targets this
       same ID as the destination chat. Since this is a single-user
       pipeline, one static ID covers both directions.
    Stored as a config value (e.g. an environment variable, not hardcoded
    in source) alongside the other static IDs below. Losing or rotating
    this value (e.g. if you message the bot from a different account)
    requires updating the config before the pipeline will respond to you
    again — treat it with the same care as an API key, since anyone who
    obtains it could in principle message your bot and appear as you,
    though the practical risk is low for a personal bot only you know the
    handle of.
  - **Aspect-ratio group mapping:** a fixed, derived-from-geometry
    mapping — not something to recompute at runtime — assigning each of
    the six sizes to one of three groups (see section 1's table): primary
    group (8x12″/A3/A2/A1), 5x7 group, 10x24 group. Determines which
    sizes auto-publish alongside the primary (step 3, step 7) versus
    which get their own critic-pass-and-approval cycle.
  - **Gelato template mapping — 2 multi-variant templates (portrait +
    landscape), sizes are the variants:** confirmed by the live
    `config/static_config.json` — all six portrait sizes share one
    `template_id` (differing only by `template_variant_id` per size), and
    all six landscape sizes share another. So there are **two** Gelato
    templates, each carrying the six sizes as variants, not 12 separate
    templates. Gelato's API has no list/search endpoint for templates (only
    fetch-by-ID), so the two template IDs and their per-size variant IDs are
    created manually in the Gelato dashboard and hardcoded into the pipeline
    (`gelato_templates` in `config/static_config.json`, keyed
    `<size>_<orientation>` → `{template_id, template_variant_id,
    image_placeholder_name}`).

    | Size | Group | Retail price | Portrait template | Landscape template |
    |---|---|---|---|---|
    | 13x18 cm / 5x7″ | 5x7 group | €19 | portrait template, 5x7 variant | landscape template, 5x7 variant |
    | 21x29.7 cm / 8x12″ *(primary)* | Primary group | €24 | portrait template, 8x12 variant | landscape template, 8x12 variant |
    | A3 (29.7×42 cm) | Primary group | €35 | portrait template, A3 variant | landscape template, A3 variant |
    | A2 (42×59.4 cm) | Primary group | €39 | portrait template, A2 variant | landscape template, A2 variant |
    | 25x60 cm / 10x24″ | 10x24 group | €45 | portrait template, 10x24 variant | landscape template, 10x24 variant |
    | A1 (59.4×84.1 cm) | Primary group | €49 | portrait template, A1 variant | landscape template, A1 variant |

    A group's listing is created as ONE Gelato product from its orientation's
    template, passing **the variants for that group's sizes** (primary =
    8x12/A3/A2/A1; 5x7 = 5x7; 10x24 = 10x24) in one `create-from-template`
    call — Gelato mirrors it to one Etsy listing with those size variations.

    **Placeholder policy — what's safe to build now vs. what actually
    blocks:** the config loader, the mapping data structure, unit tests,
    and every pipeline stage's logic can be built and tested against
    placeholder strings right now. The **actual blocking point is
    the first live, non-mocked call to `products:create-from-template`**
    — that call needs a real `templateId`/`templateVariantId` or it fails
    outright. Concretely:
    - You need **at least the primary size's two templates** (8x12″
      portrait + landscape) created and filled in before M1's first real
      manual candidate run (section 5).
    - You need **at least one other size from the primary group** (A3,
      A2, or A1) filled in before M1's required primary-group fan-out
      test (section 5).
    - You need **the 5x7 and/or 10x24 group's templates** filled in
      before M1's required per-group review test (section 5) can be
      exercised for real.
    - Remaining placeholders can stay unfilled until you're ready to sell
      that size — a still-placeholder `templateId` reaching a real call
      must fail loud, never silently skip or publish against a fake ID.
  - **Primary size designation:** **21x29.7 cm / 8x12″** — used for
    generation, critic pass, and digest review (section 3, steps 3–6).
  - **Etsy `taxonomy_id`:** the category node for wall art/home decor,
    resolved once via `getSellerTaxonomyNodes` (no keyword-search endpoint
    exists here either — fetch the tree once, pick a node).
  - **Etsy `shipping_profile_id`:** ✅ resolved — Gelato auto-created ~49
    shipping profiles on connecting to the shop. Etsy allows only one
    shipping profile per listing, and each listing is an aspect-ratio group,
    so the profile is mapped **per group** (rounded up to the group's largest
    size, at Gelato's A4 flat/tube packaging threshold): 5x7 group → Small
    Posters (`287910553824`); primary group → Large Posters (`287910565714`);
    10x24 group → Large Posters (`287910565714`). Stored as a
    per-group-type dict in `config/static_config.json`.
  - **Etsy `production_partner_ids`** ✅ **[5717252]** (Gelato), and
    `who_made: i_did` (verified: the only enum value that carries Etsy's
    "Designed by a seller / made with AI" treatment — see section 2). Both
    are set by the pipeline's **listing patch** (section 3, step 7), since
    Gelato's raw push does not set them.
  - **Etsy integration model — Gelato pushes, the pipeline patches (v4.11).**
    The Gelato store is connected to Etsy and auto-mirrors each created
    Gelato product into an Etsy listing (this is also why ~49 shipping
    profiles appeared on connect). The pipeline therefore does **not** call
    the Etsy listing-*creation* API — doing so alongside Gelato's push
    created colliding/duplicate listings in the first live run. Instead, once
    Gelato's async sync produces the Etsy listing, the pipeline resolves the
    `listing_id` (via the Gelato product's `externalId`) and PATCHes the
    listing (`updateListing` for text/metadata, `updateListingInventory` for
    per-variant price) to impose the real title/description/tags/section/
    partner/`who_made`. Retrieving the `listing_id` after the async sync is a
    known verification item (see the brainstorm doc).
- **External dependencies:**
  - Image generation — **decision:** Replicate, hosting FLUX.1 [schnell],
    for M1. FLUX.1 [schnell] is Apache 2.0 (unrestricted commercial use).
    **Do not substitute "dev" for quality reasons without re-evaluating
    licensing.** Replicate's schnell pricing (~$0.003/image) is cheap
    enough that pay-per-image holds for any realistic M1 volume — note
    that up to 3 retry attempts per candidate (primary group) plus up to
    3 crop-retry attempts per secondary group multiplies calls somewhat,
    but a design is only ever *image-generated* once — group-level
    retries are crop/composition adjustments on the same base image, not
    new generation calls.
  - Gelato API (product mockup + order fulfillment + Etsy sync) — ✅
    confirmed via live test calls: `products:create-from-template` returns a
    working mockup `previewUrl` end to end, plus lifestyle/room-context
    images automatically, and `DELETE /v1/stores/{storeId}/products/{productId}`
    is a real, working endpoint. The store is Etsy-connected, so creating a
    Gelato product also pushes an Etsy listing (v4.11 integration model
    above). Templates are dashboard-only with no creation or list API — see
    the two-multi-variant-template mapping above.
  - Etsy Open API v3 — ✅ **approved** (personal access, own shop). Rate
    limit is 10,000 requests/day and 10/sec by default — ample. Under v4.11
    the pipeline uses Etsy only to **patch** Gelato-created listings
    (`updateListing`, `updateListingInventory`, image ops), not to create
    them, so call volume is even lower than the earlier per-size-creation
    estimate: up to three listing patches per fully-approved design, spread
    across up to three approval events.
  - 💡 Etsy publishes a free **Dev MCP server** (no API key needed) —
    useful for verifying endpoint capabilities (e.g. whether any AI-tools
    listing field exists) and the `who_made` enum without full OAuth access.
  - Telegram Bot API — **`sendMediaGroup` (image gallery) + `sendMessage`
    (listing text + inline Approve/Edit/Reject buttons), two calls per
    digest entry** — now up to three digest entries per design (primary
    group, 5x7 group, 10x24 group), not one — not a single combined call,
    since Telegram doesn't support inline keyboards on media groups.
    `getUpdates` polled hourly to pick up button-press callbacks (tagged
    per group, not just per candidate) and `/research` commands, both
    checked against the Telegram admin/allowlist ID above before being
    acted on.
  - **Not adopted for M1: SerpApi's Google Trends API**, evaluated as a
    possible trend-research booster. See section 8 for the full rationale.
- **Data storage:** **SQLite**, must persist to disk between the hourly and
  twice-daily triggers and hold enough state to compute daily
  `views`/`numFavorers` deltas across listings. Schema must also
  accommodate: one design/candidate row, plus **one row per aspect-ratio
  group (primary, 5x7, 10x24) per candidate**, each with its own
  approve/edit/reject decision, its own critic-pass attempt history (up to 3
  retries), and — under v4.11 — **one Gelato product and one Etsy listing
  per group** (the group's sizes are variants within that one product/
  listing, not separate products), with per-variant price. Each group also
  carries its own `failed`/abandoned status independent of the other groups.
  **v4.11 migration note:** the earlier schema stored one row per *size*
  (each with its own `gelato_product_id`/`etsy_listing_id`/`price_eur`);
  reshaping to one product/listing per group with size as a variant touches
  `group_products`, `product_images`, and `listing_metrics_snapshots`
  (all size-keyed today) and must preserve the review queries' invariant of
  one `status='created'` product per group. Also stored: multiple images per
  listing (with alt text and gallery order); per-listing
  `views`/`numFavorers` snapshots rolling up to the design level; and a
  mapping between each group's `sendMessage` message ID and its
  candidate+group identity for callback routing.

## 5. Milestones (crawl → walk → run)

- **M1 — build for real, run manually one item at a time:** build the
  actual pipeline stages, but trigger them manually on single candidates
  before turning on the schedule and batch volume. **Before M1's first
  real manual run, the primary size's (8x12″) two Gelato templates must
  be created and their real IDs filled into static config, and your real
  Telegram admin/allowlist user ID must be filled in** (section 4).
  **M1 must include manually exercising the Kill branch** (section 3,
  step 1) at least once. **M1 must also include manually exercising a
  full 3-attempt critic-pass failure at the primary-group level**
  (section 3, step 5) at least once, confirming the `DELETE` cleanup call
  actually removes the primary-size Gelato product. **M1 must also
  include one full run that exercises the entire group flow**: approve
  the primary group (confirming it and at least one other primary-group
  size publish together, no separate review needed), then confirm the
  5x7 and/or 10x24 groups each generate their own follow-up digest entry,
  and exercise both an approve and a reject/abandon outcome across those
  two groups at least once each — this is the one genuinely new behavior
  in v0.4.8 and needs its own explicit real-world test, not just unit
  tests against mocks. **M1 must also include one manual test of the
  allowlist check itself** — e.g. sending a callback or command from a
  non-admin Telegram account (or a second test account) and confirming
  it's discarded/logged rather than acted on. This requires at least one
  primary-group secondary size's and one of {5x7, 10x24}'s real template
  IDs to be filled in first. Remaining template IDs can stay as
  placeholders until you're ready to sell those specific sizes, per
  section 4's placeholder policy. **Note on current M1 testing state:**
  the Etsy shop has been switched into Etsy's Developer Mode for the
  duration of this manual live-testing phase, so real API calls (listing
  creation, etc.) can be exercised without live listings being publicly
  visible/purchasable — this is the closest thing Etsy v3 offers to a
  sandbox on an existing shop, filling the same role Gelato/Etsy
  dry-run flags fill elsewhere per CLAUDE.md's testing conventions.
  Reverting Developer Mode is **not self-service** — it requires emailing
  developer@etsy.com and waiting for Etsy's approval — so budget lead
  time for that step before any real go-live milestone, and don't treat
  listing visibility/indexing behavior observed during M1 as fully
  representative of a normal live shop.
- **M2 — semi-automated:** the scheduled script handles research/generation/
  primary-size mockup/compliance draft/critic pass; Telegram digest + your
  approval gate at each of up to three group levels per design; publish is
  still a deliberate step you trigger per group. **All 12 template IDs
  need to be real by the time M2 runs a design you intend to sell at all
  six sizes** — the placeholder fail-loud behavior (section 4) will
  surface any that aren't.
- **M3 — feedback loop:** performance monitor comes online once there's real
  listing data; more automation only if M2 proves the unit economics work.
  Human review gate stays regardless, at every group level.

## 6. Learning loop (approvals + sales/CTR feed back into generation)

Two feedback signals, deliberately treated differently — not one loop, two,
at different speeds and different confidence levels:

- **Fast loop — your Telegram decisions.** Dense signal, available daily
  from the start of M2. Every group's decision (approve/edit/reject + any
  edit notes) is logged and can shape generation aggressively from day
  one — **up to three decisions per design now** (primary group, 5x7
  group, 10x24 group), not one. The log also captures which Go/Hold/Kill
  state a candidate was in upstream (section 3), and candidates or
  individual groups abandoned after 3 failed critic-pass attempts, with
  the failure reasons from each attempt. Only decisions from the allowlisted
  admin ID (section 4) are ever logged as real decisions.
- **Slow loop — sales & engagement data (not CTR).** ✅ investigated: Etsy
  exposes no impressions/CTR/analytics endpoint at all. Real signal
  available: `views` (cumulative, daily-tabulated) and `numFavorers`
  (cumulative), plus actual orders via `ShopReceipt`, per size-variant
  listing. The performance monitor must snapshot these daily and compute
  deltas locally, then roll them up first to their aspect-ratio group and
  then to the design level before feeding the learning loop. **Treated as
  advisory, not authoritative**, until **14 days since listing went
  live**, applied per listing before roll-up.

**Mechanism:** not model fine-tuning. A structured decision log (design
metadata: trend source, prompt(s) across attempts, style/theme tags,
Go/Hold/Kill state, critic-pass outcomes per group, your decision per
group, and later outcomes rolled up across the design's size-variant
listings) is summarized and fed back in as context before each generation
run.

**Guardrail — avoid premature convergence:** ✅ **decision:** 70% exploit /
30% explore per batch as the M2 starting default. Revisit at M3 once
there's enough data to make it adaptive.

**Longer-term extension (M3+):** once on a local image-gen model, the log of
approved/high-performing designs becomes training data for periodically
fine-tuning a LoRA.

## 7. Open questions to resolve before building anything

- Apply for Google Trends API alpha access — action item, no decision
  needed, zero cost, do in parallel with everything else.
- **Nothing else remains open** — section 9 has no unresolved items as of
  this revision. What remains is filling in the primary size's Gelato
  templates, obtaining your Telegram admin user ID, and building.

## 8. Parked ideas (separate from core pipeline, revisit later)

- **Email triage agent:** Gmail/Outlook-connected agent flagging Etsy/Gelato
  policy-update emails and summarizing promotional noise. Build after core
  pipeline is stable — not a pipeline dependency.
- **Marketing suite on top of the learning loop:** separate Instagram/TikTok
  accounts. Not before the core pipeline and learning loop are proven.
- **Own-photography pipeline:** a parallel automated setup using the user's
  own photography instead of AI-generated designs. Would need its own
  mini-spec when revisited.
- **Read-only pipeline status view (M2 nice-to-have, not a blocker):** a
  persisted, re-openable status view covering pending/live/rejected/failed
  counts (now trackable per group, not just per design) and spend totals.
  Revisit a fuller dashboard only if M3 needs more analysis surface.
- **SerpApi's Google Trends API as a trend-research booster (evaluated,
  parked, not adopted for M1):** technically a good fit and comfortably
  inside its free tier at this pipeline's volume, but Google filed suit
  against SerpApi in December 2025 (N.D. Cal., DMCA circumvention/ToS
  claims, seeking a permanent injunction that could shut down SerpApi's
  core business); case unresolved (oral argument scheduled May 19, 2026).
  Safe to start without it given the existing Google Trends alpha +
  Claude-web-search path. Revisit if the litigation resolves in SerpApi's
  favor, or if the existing path proves insufficient on real data.

## 9. Decisions Needed

**None open.** Full resolution history, kept for the counter-reviewer:

- D1 (Offsite Ads threshold) — resolved in v0.4.1. See section 1.
- D2 (single- vs. multi-image listings) — resolved in v0.4.1. See section
  3, steps 3 and 6.
- D3 (critic-pass retry policy) — resolved in v0.4.1. See section 3, step 5.
- D4 (Gelato native lifestyle/room-mockup support) — resolved in v0.4.2.
- D5 (Gelato product delete/archive endpoint) — resolved in v0.4.2.
- SerpApi (evaluated in v0.4.4) — resolved: parked, not adopted for M1.
  See section 8.
- D6 (approve-once-per-design vs. per-size) — resolved in v0.4.8: neither
  extreme. The primary group is reviewed first; once approved, sizes
  sharing its exact aspect ratio (A3, A2, A1) auto-publish with no further
  review; the 5x7 and 10x24 groups — whose aspect ratios genuinely differ
  from the primary's — each get their own critic pass and their own
  separate Approve/Edit/Reject before publishing. See section 3, steps
  6–7, and section 4.
- D7 (shop listing currency) — resolved in v0.4.7: EUR. See section 1.
- D8 (final retail prices for the six sizes) — resolved in v0.4.7. See
  section 1.
- D8a (A2 orientation cost asymmetry) — resolved in v0.4.7. See section 1.

This section is kept (rather than removed) so the counter-reviewer can see
at a glance that nothing was silently dropped between revisions. If new
ambiguities or tradeoffs surface during build, they belong here.
