# Etsy AI POD pipeline

Full spec: SPEC_v4.4.md. Changelog/decision history: CHANGELOG.md.
Read the relevant spec section before touching a pipeline stage — don't
guess at behavior that's already specified.

## Hard constraints — do not change without flagging first
- Image generation: Replicate + FLUX.1 [schnell] only. Never substitute
  FLUX.1 [dev] without raising it explicitly (different commercial license).
- Runtime is discrete scheduled functions on two cron cadences (hourly
  Telegram poll, twice-daily batch) — not a persistent service, not one
  agent loop. One function per pipeline stage (research, generate, mockup,
  compliance-draft, critic-pass, digest, publish, cleanup).
- Telegram digest = sendMediaGroup (gallery) + separate sendMessage
  (text + buttons), one pair per candidate. Never one combined call.
- Critic-pass retry cap is exactly 3 attempts, then abandon: log locally
  as `failed`, DELETE the Gelato product via
  DELETE /v1/stores/{storeId}/products/{productId}, trigger the
  Go/Hold/Kill fallback.
- Data storage is SQLite, not a flat file.
- Static config (Gelato template IDs, Etsy taxonomy_id, shipping_profile_id,
  production_partner_ids, who_made value) is resolved once and hardcoded/
  read from config — never discovered dynamically at runtime.

## Static config values (fill in as each is resolved)
- Gelato template IDs: { "12x16_portrait": "", "12x16_landscape": "",
  "18x24_portrait": "", "18x24_landscape": "" }
- Etsy taxonomy_id:
- Etsy shipping_profile_id:
- Etsy production_partner_ids (Gelato):
- Etsy who_made value:
- Gelato base cost per size (for margin check):

## Conventions
- One module per pipeline stage, independently testable, per section 4.
- Commit after each stage passes its manual M1 test.
- Never call Etsy publish or Gelato product-create against real
  endpoints without an explicit go-ahead during development — use
  Gelato/Etsy sandbox or dry-run flags where available while iterating.