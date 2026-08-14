# Static configuration — the resolved values

**Cold storage.** Read on demand; not injected into every session. This is the
data half of the pre-2026-08-14 `CLAUDE.md` (archived at
`docs/archive/2026-08-14-claude-md-pre-slim.md`). The machine-readable copy is
`config/static_config.json`; where the two disagree, the JSON is what runs.

Every value here is **resolved and final, not a placeholder**, and each is
resolved *once* and read from config — never discovered dynamically at runtime.
Full cost/price table and per-size notes: `docs/SPEC_v4.11.md` §4.

## Telegram

| | |
|---|---|
| Admin / allowlist user ID | **not written down here.** `TELEGRAM_ADMIN_CHAT_ID` in `.env` (git-ignored) |

It has two jobs, both required: every inbound `getUpdates` message and button
callback is checked against it before being treated as a command or a decision
(anything else is discarded and logged, never acted on), **and** it is the
`chat_id` target of every outbound `sendMediaGroup`/`sendMessage`. There is no
other access-control layer on the bot — treat it as a credential, which is why
this committed file does not contain it.

## Gelato

**Two multi-variant templates (portrait + landscape), sizes are the variants** —
not 12 separate templates. In `config/static_config.json`, `gelato_templates` is
keyed `<size>_<orientation>` → `{template_id, template_variant_id,
image_placeholder_name}`. All six portrait keys share one `template_id` (a
distinct `template_variant_id` per size); all six landscape keys share another.
Real IDs are filled in.

**Placeholder policy.** The slots may hold placeholder strings while building —
real ones need a manual step in the Gelato dashboard. Build and test against
placeholders freely. The one rule: if a still-placeholder `templateId` /
`variantId` ever reaches a real (non-mocked) `products:create-from-template`
call, it **must fail loudly** — never silently skip the size, never proceed with
a fake ID. Enforced by the `placeholder_template_id` tripwire in
`.qops/config.yml`.

Cost reference: `gelato_premium_matte_poster_prices_BE_2026-07-05.csv`.

## Prices — final, EUR, set per-variant on the listing

| Size | Price | Note |
|---|---|---|
| 5x7 | €19 | entry |
| 8x12 | €24 | entry, **primary size** |
| A3 | €35 | |
| A2 | €39 | both orientations, same price |
| 10x24 | €45 | |
| A1 | €49 | |

All six clear cost at 21–44 % with €0 shipping shown at checkout. Shop listing
currency: **EUR**.

## Etsy

| Field | Value | How it was resolved |
|---|---|---|
| `taxonomy_id` | **1027** | live `getSellerTaxonomyNodes`. "Home & Living > Home Decor > Wall Decor". Etsy has no plain Posters/Wall Art leaf; this parent beat "Art & Collectibles > Prints > Giclée" (121). See `docs/adr/0011-etsy-taxonomy-1027.md` |
| `shipping_profile_id` | **288734253315** | "Gelato: Free shipping", €0 to every destination. Confirmed live 2026-08-01. **One per candidate, not per group** — see `docs/constraints/003-one-shipping-profile-per-listing.md` |
| `production_partner_ids` | **[5717252]** | live `getShopProductionPartners`, after Gelato was added manually in Shop Manager → Settings → Partners you work with (listed as "A print shop", Brussels, Belgium) |
| `who_made` | **`i_did`** | the API enum has only 3 raw values and no AI-disclosure field. Pair with `is_supply: false` and `when_made: "made_to_order"`. See `docs/constraints/002-who-made-i-did.md` |
| `shop_section_id` | **59380312** | manually created "Posters" section; `etsy_shop_section_id` in `config/static_config.json`. Shared across all groups for a candidate |

Under v4.11 these are applied on the **listing patch** (`updateListing`), not at
creation — Gelato creates the listing. See
`docs/adr/0004-gelato-pushes-we-patch.md`.

The previous per-group Small/Large shipping split (5x7 → `287910553824`,
primary + 10x24 → `287910565714`) **no longer applies** once sizes share a
listing. Retail prices are unchanged: Gelato's per-item shipping (€5.10–€5.86)
is billed to the seller under either profile and was always inside the cost
basis. Evidence: `docs/archive/2026-08-01-gl22a-findings.md` GL-22b.

## The manual disclosure step

Etsy's two Creativity Standards questions — `production_process` and
`tools_used` (where "an AI generator" lives) — are **absent from the v3 API**,
and the web editor's only save action is "Activate with changes". The owner
ticks "an AI generator" as part of the same editor save that takes a listing
live. Consequences, both load-bearing:

1. the prose AI/production-partner disclosure is **removed** from listing
   descriptions (`compliance_draft.DISCLOSURE_TEXT == ""`, and the draft prompt
   forbids reintroducing one) — safe only because the structured tick happens at
   publish;
2. programmatic draft→active activation (GL-29) is **cancelled**;
   `etsy_client.update_listing_state` stays `# DELIBERATELY UNWIRED` with its
   guard test intact.

**If either half is ever revisited, revisit both** — wiring activation while the
description carries no disclosure publishes a listing with neither. Re-check
quarterly (GL-39) starting from `etsy/open-api` Discussion #1630, not from first
principles. Full record: `docs/constraints/005-no-api-for-creativity-standards.md`
and `docs/archive/2026-08-06-gl37-findings.md`.
