# Etsy AI POD pipeline

Full spec: SPEC_v4.10.md. Changelog/decision history: CHANGELOG.md.
Gelato cost reference: gelato_premium_matte_poster_prices_BE_2026-07-05.csv.
Shop currency: EUR. Read the relevant spec section before touching a
pipeline stage — don't guess at behavior that's already specified.

## Hard constraints — do not change without flagging first
- Image generation: Replicate + FLUX.1 [schnell] only. Never substitute
  FLUX.1 [dev] without raising it explicitly (different commercial license).
  A design is only ever image-generated once — group-level crop/retry
  (below) reuses the same base image, it never triggers a new generation
  call.
- Runtime is discrete scheduled functions on two cron cadences (hourly
  Telegram poll, twice-daily batch) — not a persistent service, not one
  agent loop. One function per pipeline stage (research, generate,
  primary-mockup, compliance-draft, critic-pass, digest,
  publish-primary-group, group-mockup, group-critic-pass, group-digest,
  publish-group, cleanup).
- Telegram digest = sendMediaGroup (gallery) + separate sendMessage
  (text + buttons), one pair per digest entry. Never one combined call.
  There are up to **three** digest entries per design now, not one — see
  the aspect-ratio-group rule below.
- Critic-pass retry cap is exactly 3 attempts per group, then abandon
  that group only: log locally as `failed`, DELETE that group's Gelato
  product(s) via DELETE /v1/stores/{storeId}/products/{productId}. At the
  primary-group level this also triggers the Go/Hold/Kill fallback
  (abandoning the whole candidate); at the 5x7/10x24-group level it only
  abandons that one group — the design's already-published groups are
  untouched.
- **Aspect-ratio-group review flow (the core mechanic — see spec section
  3, steps 6–7):**
  1. Only the primary size (21x29.7cm/8x12″) gets generated, critic-passed,
     and shown in the first digest entry.
  2. On approval, the **primary group** (8x12″ + A3 + A2 + A1 — same ISO
     aspect ratio, ~1:1.414) publishes immediately, all four, with **no
     further review** — they render identically, just scaled.
  3. Independently, the **5x7 group** and the **10x24 group** (each a
     genuinely different aspect ratio from the primary) each get their
     own re-crop of the same approved artwork, their own critic pass, and
     their own separate follow-up digest entry + Approve/Edit/Reject,
     sent in the same evening run.
  4. A design can end up selling at 4, 5, or 6 sizes depending on whether
     the 5x7/10x24 groups each pass their own review — this is expected,
     not a bug.
- Data storage is SQLite, not a flat file — one row per aspect-ratio group
  per candidate, not one row per candidate (each group has its own
  decision, critic-pass history, and Gelato/Etsy IDs).
- Static config (Gelato template IDs, Etsy taxonomy_id, shipping_profile_id,
  production_partner_ids, who_made value, Telegram admin/allowlist user ID)
  is resolved once and hardcoded/read from config — never discovered
  dynamically at runtime.
- **Telegram admin/allowlist user ID has two jobs, both required:** (1) every
  inbound getUpdates message and button callback is checked against it
  before being treated as a real command/decision — anything else is
  discarded and logged, never acted on; (2) it's also the chat_id target
  for every outbound sendMediaGroup/sendMessage digest call. There is no
  other access-control layer on the bot, so treat this ID with the same
  care as an API key — **read it from `.env` (e.g. `TELEGRAM_ADMIN_CHAT_ID`),
  never hardcode it in this file.** Unlike the Gelato/Etsy static IDs below,
  it's not project documentation, it's closer to a credential.
- **Placeholder policy for Gelato template IDs:** it's expected that most
  of the 12 template-ID slots below start out as placeholder strings
  (real ones require a manual step in the Gelato dashboard). Build and
  test everything against placeholders freely. The one rule: if a
  still-placeholder templateId ever reaches a real (non-mocked)
  `products:create-from-template` call, that must fail loudly with a
  clear error — never silently skip the size or proceed with a fake ID.

## Static config values (fill in template IDs as each is resolved — see
SPEC_v4.10.md section 4 for the full cost/price table and per-size notes;
prices below are final, not placeholders)
- Telegram admin/allowlist user ID: **not listed here** — read from
  `TELEGRAM_ADMIN_CHAT_ID` in `.env` (git-ignored), same as the bot token.
  This file is committed to git, so it's the wrong place for it.
- Gelato template IDs (6 sizes × 2 orientations — primary size marked) and
  final EUR retail prices:
  {
    "5x7_portrait": "", "5x7_landscape": "",       // price: €19 (entry tier)
    "8x12_portrait": "", "8x12_landscape": "",     // price: €24 (entry tier) — primary size, fill first
    "A3_portrait": "", "A3_landscape": "",         // price: €35
    "A2_portrait": "", "A2_landscape": "",         // price: €39 (both orientations, same price despite slightly different Gelato cost)
    "10x24_portrait": "", "10x24_landscape": "",   // price: €45
    "A1_portrait": "", "A1_landscape": ""           // price: €49
  }
- Etsy taxonomy_id: **1027** ("Home & Living > Home Decor > Wall Decor" —
  resolved via live `getSellerTaxonomyNodes`; Etsy has no plain
  "Posters"/"Wall Art" leaf, this parent node was chosen over
  "Art & Collectibles > Prints > Giclée" (id 121) as the better fit)
- Etsy shipping_profile_id: **not filled yet — needs a per-size mapping,
  not a single ID.** Gelato auto-created ~49 shipping profiles on
  connecting to the shop; product line is confirmed **unframed** premium
  matte posters (matches the cost-reference CSV and business layer — the
  earlier framed_poster_mounted Gelato test call in
  `docs/gelato_call_response_example_from_manual_tests.txt` was an early
  exploratory API test, not the real product). The matching family is
  plain **"Posters"**, but it only has two size tiers, not six or three:
  `287910553824` ("Small Posters", €12.44 shipping) and `287910565714`
  ("Large Posters", €14.55 shipping) — no Medium tier exists for this
  family. Coding-session TODO: restructure `etsy_shipping_profile_id` in
  `config/static_config.json` into a per-size mapping (same shape as
  `gelato_templates`), decide which of the 6 sizes (5x7, 8x12, A3, A2,
  10x24, A1) map to Small vs Large, and update `pipeline/config.py`'s
  reader to match.
- Etsy production_partner_ids (Gelato): **[5717252]** — resolved via live
  `getShopProductionPartners` after Gelato was manually added as a
  production partner in Shop Manager → Settings → Partners you work
  with (listed there as "A print shop", Brussels, Belgium).
- Etsy who_made value: **"i_did"** — verified live: the API's `who_made`
  enum has only 3 raw values (`i_did`/`someone_else`/`collective`), no
  separate AI-disclosure field exists anywhere in the spec. Etsy's
  "Designed by a seller" AI-context label is just the display name for
  `i_did`, not a distinct value. Must be paired with `is_supply: false`
  and `when_made: "made_to_order"` on every `createDraftListing` call
  (required together, not stored here since they're fixed per-call
  values, not IDs to resolve).
- Shop listing currency: **EUR** (resolved, spec section 1)

## Conventions
- One module per pipeline stage, independently testable, per section 4.
- Commit after each stage passes its manual M1 test.
- Never call Etsy publish or Gelato product-create against real
  endpoints without an explicit go-ahead during development — use
  Gelato/Etsy sandbox or dry-run flags where available while iterating.
- Before the first real M1 manual run: at minimum, the 8x12″ (primary)
  templates must be real. Before the M1 multi-size fan-out test: at
  minimum, one secondary size's templates must also be real.