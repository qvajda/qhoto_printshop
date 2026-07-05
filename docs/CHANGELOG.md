# Changelog — spec v0.3 → v0.4

For the counter-reviewer: each entry maps a change to the red-team finding
that drove it, so coverage can be checked without re-diffing the full
document. "RT §" refers to the red-team report's own section numbers.

## Blocking findings (all incorporated)

1. **Hourly-poll vs. twice-daily-script contradiction (RT §3, "Concrete
   technical architecture").** Section 4's "Runs as" bullet rewritten:
   two explicit cron cadences (hourly lightweight Telegram poll;
   twice-daily heavy batch), pipeline restated as discrete named
   functions/stages sharing one state store, not a monolithic loop.
2. **No template-ID lookup for Gelato (RT §3, "Template selection").**
   New "Static configuration" subsection in section 4: explicit
   `{size × orientation → templateId}` mapping, ownership stated
   (you, updated on new sizes). Section 3 step 3 (POD mockup) now
   references this lookup instead of implying dynamic discovery.
3. **No Go/Hold/Kill branch in trend research (RT §3, "Trend research").**
   Section 3 step 1 rewritten with the three-state classification and the
   safe-evergreen-bucket / next-candidate fallback on Kill. Section 5 (M1)
   updated to require manually exercising a Kill case. Section 6's decision
   log updated to capture this state.
4. **`who_made`/`production_partner_ids` not specified (RT §2).** Added to
   section 2 (flagged as compliance-critical, not copy) and detailed in
   section 4's new "Static configuration" subsection, including the
   instruction to verify the current `who_made` enum value via the Etsy
   Dev MCP server before first publish.
5. **Offsite Ads not accounted for in margin (RT §1, price point).** Added
   to section 1. Not resolved in the spec itself — moved to Decisions
   Needed (D1) because it depends on your shop's actual sales history,
   which I have no way to check.

## Nice-to-fix-later findings (all incorporated)

6. **Etsy fee breakdown imprecise (RT §1).** Section 1 updated with the
   precise breakdown ($0.20 + 6.5% + ~3%+$0.25 ≈ 9.5% + $0.45/order).
7. **Gelato base-cost check deferred to M1 unnecessarily (RT §1).** Section
   1 now says resolve before build starts, not during M1.
8. **"27–38% of annual revenue" stat overstated/uncited (RT §1).** Section
   3's event table now reads "roughly 25–32% of annual Etsy GMS... treat as
   a ballpark, not a cited figure," sourced to Etsy's own investor filings
   rather than the original blog-derived range.
9. **Data storage left as "local file or lightweight DB" (RT §3).** Section
   4 now commits explicitly to SQLite, with the reasoning (must persist
   across both cron cadences, must support delta computation) stated
   inline.
10. **No read-only pipeline status view (RT §4, "Human-facing interface").**
    Added to section 8 (Parked ideas) as an M2 nice-to-have, using this
    environment's artifact mechanism, per the red-team's own scoping
    recommendation (not a blocker, not M1 scope).

## Findings from the RT report's §9 follow-up (content-generation completeness)

11. **`taxonomy_id` required, no search endpoint (RT §9).** Added to
    section 4's "Static configuration" subsection — same
    resolve-once-reference-by-ID pattern as the template mapping.
12. **Shipping profile required, must match Gelato's real timelines
    (RT §9).** Added to section 4's "Static configuration" subsection.
13. **Tag/title format limits not enforced programmatically (RT §9).**
    Added to section 2 and to section 3 step 4 (compliance draft): 13 tags
    ≤20 chars, 140-char title, validated before a candidate reaches the
    Telegram digest.
14. **Alt text not generated (RT §9).** Added to section 2 and section 3
    step 4 as a cheap addition to the existing compliance-draft call.
15. **Image gallery composition (single vs. multi-image) undecided
    (RT §9).** Section 3 step 6 now states single-image as explicit M1
    scope, multi-image as M2 fast-follow — the red-team's own
    recommended default. Also listed in Decisions Needed (D2) because the
    red-team explicitly framed this as your call, not a fact to resolve.
16. **No adversarial critic pass before the human review gate (RT §9).**
    New section 3 step 5, "Critic pass" — vision-capable model call,
    pass/fail plus reason, against the no-go list / image-quality /
    title-match rubric described in the red-team report. Explicitly
    additive to the human review gate in section 2, not a replacement.
    Retry/fallback behavior on failure defaulted in the spec but also
    flagged in Decisions Needed (D3), since the red-team explicitly left
    that choice to you.

## Confirmed-no-change findings (left as-is, noted for completeness)

- Target buyer, niche, success metric, paid-ads cap (RT §1) — business
  judgment calls, no external fact to check.
- Hard no-go list, human review gate (RT §2) — sound as written.
- Milestone structure (RT §5) — internally consistent, only the M1 Kill-case
  addition above applied.
- Views/`numFavorers`/no-CTR-endpoint claim, 70/30 split, 14-day advisory
  window (RT §6) — confirmed accurate / reasonable starting heuristics.
- Google Trends alpha program characterization (RT §7) — confirmed
  accurate.
- Parked ideas (RT §8) — appropriately out of scope.
- Etsy API access model, rate limits, FLUX.1 [schnell] licensing (RT §3)
  — confirmed solid; added one explicit caution line in section 4 against
  silently swapping to FLUX.1 [dev], since that changes the license
  position.

## Independent trims (not red-team-driven)

- Removed a duplicated explanation of "Etsy only returns cumulative
  counters, so deltas must be computed locally" — it appeared once in the
  slow-loop bullet and again as a separate "Implementation note" in
  section 6 of v0.3. Consolidated into the slow-loop bullet only; no
  content lost.
- Removed a redundant closing note in section 6 of v0.3 ("the slow loop's
  data source... was confirmed via direct investigation... No longer a
  blocker") that restated the same point already made earlier in the same
  section.
- No other redundant requirements, speculative features, or
  no-longer-relevant sections were found. Section 8 (Parked ideas) was
  reviewed for scope creep and left intact — the red-team review and this
  pass both agree those items are correctly out of scope rather than
  under-specified in-scope work.

## Decisions Needed (summary — see spec section 9 for full detail)

- **D1** — Offsite Ads $10k/365-day threshold: needs you to check your
  shop's actual sales history.
- **D2** — Single-image (M1) vs. multi-image (M1) listings: real
  conversion-vs-complexity/cost tradeoff, defaulted to the red-team's
  recommendation but not silently finalized.
- **D3** — Critic-pass retry policy: auto-regenerate-once-then-fallback
  (default in this spec) vs. fallback-on-first-failure: explicitly left
  open by the red-team, defaulted here but confirm before M1.

---

# Changelog — spec v0.4 → v0.4.1

D1–D3 are now resolved based on your direct input, not defaulted or
guessed. Two new items surface as a result — flagged as D4/D5, but they're
unverified technical assumptions about Gelato's API, not judgment-call
tradeoffs like D1–D3 were.

1. **D1 resolved — Offsite Ads (section 1).** You confirmed the shop has
   never crossed the $10,000/365-day threshold and Offsite Ads is off.
   Section 1's price-point bullet updated: margin target does not need to
   absorb the 12% cut. Removed from Decisions Needed.
2. **D2 resolved — multi-image listings (section 3, steps 3–7; section 2;
   section 4; section 6).** You want multi-image galleries in M1 itself,
   not deferred to M2: image 1 = Gelato flat mockup, followed by in-context
   room images. Changes:
   - New step 3.5 ("In-context room images") between mockup and critic
     pass.
   - Step 4 (compliance draft): alt text now generated per image across
     the whole gallery, not one image.
   - Step 5 (critic pass): rubric now reviews every gallery image, not
     just the flat mockup.
   - Step 6 (digest) and step 7 (evening run/publish): explicit fixed
     image order (mockup, then room shots) carried through to the actual
     Etsy listing upload.
   - Section 2: alt-text bullet updated to "every image in the gallery."
   - Section 4: static Gelato template-ID mapping note extended to cover
     a possible room-scene template/style ID per size, contingent on D4.
   - Section 4: added a note that multi-image galleries increase image-gen
     call volume per candidate (still cheap at schnell pricing).
   - **New open item, not silently assumed:** whether Gelato's API can
     natively produce the room-context images, or whether a separate
     compositing/generation step is needed — this wasn't checked in the
     original red-team audit and I can't verify live API behavior in this
     session. Flagged as **D4** rather than guessed, since building against
     the wrong assumption here is a real rework risk, not a config tweak.
3. **D3 resolved — critic-pass retry policy (section 3, step 5; section 5;
   section 6).** You want exactly 3 auto-regenerate attempts, then abandon
   and move to the next candidate. Changes:
   - Step 5 rewritten: 3-attempt cap, explicit abandon behavior on the 3rd
     failure.
   - **Local logging on abandon:** failed candidates are logged with
     `failed` status and the full per-attempt history (prompts, critic-pass
     reasons), so the learning loop can use them — added to section 6's
     fast-loop description and section 4's data-storage schema notes.
   - **Gelato-side cleanup on abandon:** any Gelato product created during
     a failed attempt must be removed rather than left orphaned. **New
     open item:** whether Gelato actually exposes a delete/archive
     endpoint was never checked (the original investigation only confirmed
     creation works). Flagged as **D5** rather than assumed, with a stated
     no-op fallback (stop referencing the orphaned product) if no such
     endpoint exists.
   - Step 1's Kill-branch fallback and the post-abandon fallback are now
     explicitly the same mechanism (one fallback path, two triggers).
   - Section 5 (M1): added a requirement to manually exercise a full
     3-attempt failure at least once, alongside the existing Kill-branch
     exercise, so the abandon/cleanup/fallback path is actually tested
     before M2 turns on the schedule.
   - Section 3 step 7 (evening run): rejected candidates are now logged
     with the same full gallery + text + decision detail as critic-pass
     failures, for learning-loop consistency (minor extension, not
     red-team- or decision-driven, but a natural consequence of treating
     "didn't make it live" data consistently across reject/fail/abandon).

## New Decisions Needed (replacing D1–D3, which are resolved)

- **D4 — Gelato native lifestyle/room-mockup support.** Unverified;
  determines whether step 3.5 is a config lookup (if native) or a real
  build item (separate compositing/generation step, if not).
- **D5 — Gelato product delete/archive endpoint.** Unverified; determines
  whether critic-pass-failure cleanup calls a real endpoint or falls back
  to a documented no-op.

Both are flagged rather than assumed because neither was checked in the
original red-team audit, and confirming them wrong after M1 is built would
mean rebuilding the affected step rather than tweaking a config value.

---

# Changelog — spec v0.4.1 → v0.4.2

D4 and D5 are now resolved via a live Claude Code API test against Gelato.
No open items remain in section 9 as of this revision.

1. **D4 resolved — Gelato native lifestyle/room-mockup support (section 3,
   step 3; section 4).** Confirmed: a single `products:create-from-template`
   call returns the flat mockup plus lifestyle/room-context images
   automatically — no separate compositing/image-generation step, and no
   additional Gelato config beyond the existing size/orientation
   template-ID mapping. Changes:
   - Section 3: the separate "step 3.5 — In-context room images" from
     v0.4.1 is folded back into step 3 (POD mockup), since it turns out to
     be the same API call, not a distinct pipeline stage. Added an
     explicit note that the pipeline still orders the returned images
     (flat mockup first) itself, since Gelato's own return order isn't
     assumed to already match the desired listing order.
   - Section 4: removed the conditional "if Gelato's mockup system
     supports lifestyle variants, extend the mapping" language from the
     template-ID bullet — replaced with a confirmed statement that the
     existing mapping already covers it, no second lookup needed.
   - Section 4 (external dependencies, Gelato): updated from "not yet
     confirmed" to "✅ confirmed via live test calls."
   - Section 4 (external dependencies, image generation): added a note
     that lifestyle/room-context images don't add to the Replicate/
     image-gen bill, since they come from the Gelato call, not a separate
     generation call — this is a real cost difference from what v0.4.1
     left open, worth surfacing for anyone re-checking the M1 budget math.
2. **D5 resolved — Gelato product delete/archive endpoint (section 3, step
   5).** Confirmed: `DELETE /v1/stores/{storeId}/products/{productId}` is
   real and working. Changes:
   - Section 3, step 5 (critic-pass failure cleanup): replaced the
     "verify, and fall back to a no-op if unavailable" language with a
     direct instruction to call the endpoint.
   - Section 5 (M1 milestone): tightened the required manual test of the
     3-attempt-failure path to explicitly include confirming the `DELETE`
     call actually removes the Gelato product, not just that cleanup was
     logged as attempted — this is a slightly stronger bar than v0.4.1's
     wording now that a real endpoint exists to verify against.
3. **Section 9 rewritten, not deleted.** All five decisions/verifications
   raised across v0.4, v0.4.1, and v0.4.2 (D1–D5) are now resolved. Kept
   the section as a closed-out log (each item with a one-line resolution
   and pointer to where it landed in the spec) rather than removing it, so
   the counter-reviewer has a single place to confirm nothing was quietly
   dropped across three revisions.
4. **No independent trims or red-team-driven changes in this revision** —
   this was a narrow, targeted update incorporating exactly the two
   confirmations you provided. Everything else carried over unchanged from
   v0.4.1.

## Decisions Needed status: none open.

If new ambiguities surface once build starts, add them to spec section 9
rather than resolving them silently — same policy as the last two
revisions.

---

# Changelog — spec v0.4.2 → v0.4.3

A second red-team pass caught a Telegram API mechanism error in the digest
step. Fixed directly — this is a factual correction (Telegram's Bot API
doesn't support inline keyboards on media groups), not a tradeoff, so no
new Decisions Needed item was added.

1. **Telegram digest mechanism fixed (section 3, step 6).** Previously
   described as one message (or short batch) carrying both the image
   gallery and the Approve/Edit/Reject buttons per candidate. Rewritten:
   per candidate, `sendMediaGroup` (the gallery as an album, flat mockup
   first) followed by a separate `sendMessage` (listing text + inline
   keyboard), tagged with the candidate ID for callback matching. "Digest"
   now explicitly describes the batch cadence (repeated per candidate),
   not a single Telegram message.
2. **Section 4 updated to match:**
   - "Runs as" / twice-daily batch bullet: now names the
     `sendMediaGroup` + `sendMessage` pair explicitly as part of the
     digest stage.
   - Telegram Bot API external-dependency bullet: rewritten to state the
     two-call pattern and why (no inline-keyboard support on media
     groups), rather than "digest message + inline buttons" as one thing.
   - Hourly poll bullet: clarified that `getUpdates` picks up callbacks
     from the `sendMessage` half of the pair specifically.
   - Data storage: added a note that the local state store needs a
     mapping between a candidate ID and its `sendMessage` message ID, so
     an incoming button-press callback can be matched back to the right
     candidate — this becomes necessary once the gallery and the buttons
     are two separate messages instead of one.
3. **Section 9:** no new entry. Noted at the end of the section that this
   fix was made and explicitly why it isn't a tradeoff-flagged decision,
   so the counter-reviewer doesn't go looking for a D6 that doesn't exist.
4. **No other changes.** Everything else carries over unchanged from
   v0.4.2, including all of D1–D5's resolutions.

## Decisions Needed status: still none open.

---

# Changelog — spec v0.4.3 → v0.4.4

You asked me to research SerpApi's Google Trends API as a possible
trend-research booster before build. Findings and your decision (start
without it, flag as a fast-follow) are incorporated — no pipeline behavior
changed, only documentation of a deliberately-not-taken path.

1. **Section 3, step 1 (trend research):** added a one-line pointer noting
   SerpApi was evaluated and deliberately not adopted, referencing section
   8 for the reasoning, so a reader hitting the trending-now-scan bullet
   doesn't wonder whether it was overlooked.
2. **Section 4 (external dependencies):** added a matching bullet under
   external dependencies stating SerpApi is "not adopted for M1," with a
   one-line summary of why (continuity risk from active litigation, not a
   technical or cost problem) and a pointer to section 8.
3. **Section 8 (parked ideas): new entry — "SerpApi's Google Trends API as
   a trend-research booster."** This is the substantive addition. Captures:
   - Technical fit: mirrors the public Google Trends site (interest-over-
     time, related queries/topics, geo breakdown) plus a "Trending Now"
     endpoint, as structured JSON — a reasonable fit for the existing
     trending-now-scan bullet.
   - Cost fit: estimated 140–200 calls/month at this pipeline's cadence
     (twice-daily batch + occasional `/research` triggers), against
     SerpApi's confirmed free tier of 250 searches/month / 50 requests-
     per-hour throughput (checked directly against serpapi.com/pricing,
     not a secondary source) — cost was not the reason to hold off.
   - The actual reason to hold off: Google filed suit against SerpApi in
     December 2025 (N.D. Cal.) alleging DMCA circumvention and ToS
     violations, seeking $2.8M in damages and a permanent injunction that
     could shut down SerpApi's core business. SerpApi's motion to dismiss
     is pending oral argument on May 19, 2026; case unresolved as of this
     writing. Flagged as a continuity risk (a pipeline stage depending on
     a vendor whose product could be enjoined mid-operation), not a
     one-time integration risk.
   - Explicit revisit trigger: reconsider if the litigation resolves in
     SerpApi's favor or is dismissed, or if the official Google Trends
     alpha + Claude-web-search path proves insufficient once M1/M2 are
     running on real data — re-check SerpApi's pricing/terms at that point
     since both may have changed.
4. **Section 9:** added one sentence noting this was resolved (start
   without SerpApi), not deferred — so it isn't mistaken for an open
   decision on a future re-read.
5. **No other changes.** No pipeline stage, milestone, or cost figure
   changed as a result of this revision — this was research-and-document,
   not a build change.

## Decisions Needed status: still none open.

---

# Changelog — spec v0.4.4 → v0.4.5

You chose simple, single-size Gelato templates over Gelato's multi-size/
multi-price-point template option ("start easy with simpler template with
each an individual size and cost"). That's a direct, unambiguous request,
but it surfaced a real architectural gap the spec hadn't made explicit:
how a design sold at 2–3 sizes (already assumed since v0.4, section 1's
"8–12 listings... a few designs × 2–3 sizes") actually flows through
mockup, critic pass, digest, and publish once each size is its own
separate Gelato product instead of one shared multi-variant product.
Resolved with a "review once at a primary size, fan out to secondary
sizes only after approval" model — one new item flagged, not silently
decided.

1. **Section 4 (static configuration):** Gelato template-ID mapping bullet
   rewritten to state explicitly that each size × orientation is its own
   individual, single-variant, single-price template — not a shared
   template with Gelato's multi-size-variant option — and why (starting
   simple, avoiding Gelato's per-template variant/price-selection surface
   for M1). **New: "Primary size designation"** — one size per orientation
   (defaulting to the smaller/cheaper one, ~12x16) is marked primary and
   used for generation/review; the rest are secondary, created only after
   approval.
2. **Section 3, step 3 (POD mockup) — now primary-size only.** Previously
   ambiguous about how many sizes get rendered per candidate. Now: exactly
   one Gelato product, at the primary size, per candidate — secondary
   sizes are explicitly deferred to step 7. This is the core mechanical
   change everything else follows from.
3. **Section 3, step 4 (compliance draft):** clarified the draft text is
   generated once, at the primary size, and reused (with a small
   size-specific title/price adjustment) for secondary-size listings at
   publish time — not redrafted per size.
4. **Section 3, step 5 (critic pass):** clarified this is inherently a
   single review per design now, since only the primary size exists at
   this point — removes what would otherwise have been a real cost/
   thoroughness tradeoff (reviewing N sizes vs. one). Cleanup on 3-attempt
   failure simplified to match: only ever one Gelato product to delete per
   attempt, not one per size.
5. **Section 3, step 6 (Telegram digest):** clarified the gallery shown is
   the primary size's (the only one that exists yet), and that approving
   a candidate approves the whole design — all configured sizes — not
   just the primary one. Flagged as D6 (see section 9) since this means
   secondary-size renders are never individually reviewed before
   publishing.
6. **Section 3, step 7 (evening run) — new fan-out logic.** On approval:
   publish the primary-size listing (already created), then for each
   remaining configured size, create its Gelato product (using that size's
   template), reuse the compliance draft with a size-specific adjustment,
   and publish it as its own Etsy listing. Added a lightweight retry-once-
   then-surface-in-next-digest fallback for a secondary size's creation/
   publish failure — deliberately simpler than the Go/Hold/Kill/critic-pass
   machinery, since there's no compliance risk at this stage.
7. **Section 3, step 9 (performance monitor) and section 6 (learning
   loop):** clarified that per-listing `views`/`numFavorers`/order data is
   tracked per size-variant listing but rolled up to the design level
   before feeding the fast/slow learning loops, since a design's overall
   performance across sizes — not one size in isolation — is the
   meaningful signal.
8. **Section 4 (data storage):** schema description updated — one design/
   candidate row links to exactly one primary Gelato product
   (pre-approval, subject to the retry/cleanup cycle) and zero or more
   secondary Gelato products + Etsy listing IDs (post-approval only).
9. **Section 5 (M1 milestone):** added a third required manual test — a
   full approve → multi-size fan-out run — alongside the existing Kill-
   branch and 3-attempt-failure tests, since the fan-out logic only runs
   after approval and wouldn't be exercised by the other two.
10. **Section 1:** minor cross-references added (primary/secondary size
    labels on the two price points; per-size Gelato cost check clarified
    as a simple per-size lookup, not a shared multi-variant price table).
    No numbers changed.
11. **Section 9 — new item, D6 (flagged, not blocking):** approve-once-
    per-design vs. approve-per-size. Defaulted to approve-once (matches
    your "start easy" direction and keeps the Telegram flow unchanged),
    but flagged because it means secondary-size renders publish without
    individual review — low risk since the artwork is identical across
    sizes and Gelato's rendering is mechanical, but not zero risk (a
    lifestyle image could crop/scale differently at a larger size). Noted
    the small addition needed (show secondary renders in a follow-up
    digest message) if you'd rather review them individually.

## Decisions Needed status: one flagged (D6), not blocking.

---

# Changelog — spec v0.4.5 → v0.4.6

You provided the real size lineup you want (six sizes, both orientations)
and the actual Gelato per-size cost data (`gelato_premium_matte_poster_
prices_BE_2026-07-05.csv`, Belgium market, EUR) — this finally resolves
the "Gelato base cost per size" item that section 1 had flagged as an
action item since v0.4. You also asked for explicit placeholders on the
12 Gelato template IDs since creating them is a manual step on your side.
Two new items are flagged (D7, D8) rather than decided silently, since the
real cost data changes the pricing math in ways that go beyond what you
asked me to resolve.

1. **Section 1 — size lineup replaced.** The old 2-size ($22/$32 USD,
   12x16/18x24) placeholder pair is replaced with your six real sizes
   (5x7″, 8x12″, 10x24″, A3, A2, A1), each in both orientations, with real
   product/shipping/total cost pulled directly from your CSV. **Flagged,
   not normalized away:** A2 is the one size where Gelato's own price list
   has portrait and landscape costing differently (€20.21 vs €19.60) —
   you said all sizes are "the same price point" across orientations,
   which is true for five of six, so this discrepancy is called out
   explicitly rather than silently averaged.
2. **Section 1 — success metric recalculated.** One approved design now
   produces 6 listings (was 2–3), so roughly 2 approved designs reach a
   similar 8–12-listing sample size, versus "a few designs" before.
3. **Section 3, steps 3, 6, 7 — fan-out updated from 1–2 secondary sizes
   to 5.** Mockup/critic-pass/digest still touch only the primary size
   (unchanged mechanism from v0.4.5); step 7's publish fan-out now creates
   and publishes five secondary-size listings per approved design instead
   of one or two.
4. **Section 4 (static configuration) — Gelato template-ID mapping
   expanded to 12 entries (6 sizes × 2 orientations) and seeded with
   explicit placeholder values**, per your request, since real template
   IDs require a manual Gelato-dashboard step on your side. Added an
   explicit **placeholder policy**: all code/config/tests can be built
   against placeholders now; the actual blocking point is the first live
   `products:create-from-template` call, and a still-placeholder
   `templateId` reaching that call should fail loudly, not silently skip
   or publish against a fake ID. Primary size default changed from
   12x16-equivalent to **21x29.7 cm / 8x12″** (one of the five sizes
   without the A2-style orientation cost asymmetry).
5. **Section 5 (M1 milestone) — sequencing clarified against the
   placeholder policy.** Only the primary size's two templates need to be
   real before M1's first manual run; only one secondary size's templates
   need to be real before M1's required multi-size fan-out test; the
   remaining four sizes can stay as placeholders until you're ready to
   sell them. This directly answers "when does this become blocking."
6. **Section 6 (learning loop):** views/favorites/orders now tracked
   across up to six size-variant listings per design instead of two or
   three, still rolled up to the design level before feeding the loop —
   mechanism unchanged from v0.4.5, just a larger fan-out.
7. **Section 9 — two new flagged items, not decided silently:**
   - **D7 (shop listing currency):** the real cost data is EUR; the
     spec's price points were previously USD. I don't know which currency
     your actual Etsy shop lists in, and I'm not guessing — this needs
     your confirmation before final prices are locked in.
   - **D8 (final retail prices per size):** provided illustrative
     cost-plus pricing at a 45% margin for reference, but flagged that a
     strict margin percentage makes small sizes (e.g. 5x7″ at ~€29) land
     well above the old $22 anchor, which may cut against the
     "price-sensitive" buyer framing in section 1 — offered alternatives
     (lower margin on entry sizes, round-number anchors) without picking
     one for you. **D8a** bundled in: whether A2's two orientations get
     cost-accurate or unified pricing.
   - **D6 re-flagged, not re-resolved:** noted that the existing
     approve-once-per-design tradeoff now spans five unreviewed secondary
     renders instead of one or two, since the size lineup grew — same
     open question as v0.4.5, just higher stakes now that it's real sizes
     instead of a placeholder pair.
8. **CSV added to the repo-facing outputs**, alongside the spec, per your
   stated plan to commit it for reference.
9. **No changes** to sections 2, 7, 8, or the trend-research/critic-pass/
   Telegram-mechanism logic beyond the size-count substitution — those
   remain exactly as resolved in v0.4.3–v0.4.5.

## Decisions Needed status: two new items flagged (D7, D8/D8a), plus D6
carried over from v0.4.5 — none blocking the build from starting, but D7
and D8 should be resolved before any listing actually goes live with real
prices.

---

# Changelog — spec v0.4.6 → v0.4.7

You resolved D7, D8, and D8a directly: EUR confirmed, lower margins on
entry sizes, round-number price anchors preferred over precise margin
targeting, and a single shared price for A2 despite its orientation cost
asymmetry. All three are now locked into the spec, not left as reference
math.

1. **D7 resolved — shop currency: EUR (section 1).** All USD framing
   removed; the earlier $22/$32 anchors are fully retired rather than
   just superseded. The €5/day Etsy Ads cap restated in EUR (the round
   "5" figure carries over unchanged). Etsy's own flat fees are still
   USD-denominated globally and convert at time of charge — kept as a
   noted approximation (~€0.40), not treated as a fixed EUR number.
2. **D8 resolved — final retail prices, tiered by margin (section 1,
   section 3 steps 4/7, section 4).** Six round-number EUR prices set:
   €19 (5x7″), €24 (8x12″, primary), €35 (A3), €39 (A2), €45 (10x24″),
   €49 (A1). Two sizes (5x7″, 8x12″) deliberately priced at lower margin
   (~21%, ~32%) than the rest (~38–44%), per your "lower margins for
   entry versions" instruction — framed against the existing
   "price-sensitive self-purchase redecorator" buyer segment in section 1
   so the reasoning is traceable, not just the numbers. Noted (not
   flagged as a problem) that 10x24″ prices above A2 despite covering
   less print area, since it genuinely costs more to produce — prices
   follow real Gelato cost, not physical size.
3. **D8a resolved — A2 orientation pricing (section 1, section 4).**
   Single €39 price for both A2 orientations, per your explicit
   instruction to prefer one round number over cost-accurate per-
   orientation pricing. Documented the resulting small margin difference
   (~38% portrait vs. ~39% landscape) so it's a known, deliberate choice
   rather than something a future reviewer flags as an inconsistency.
4. **Section 3, steps 4 and 7:** compliance draft and the fan-out/publish
   step now reference the specific final EUR price per size rather than
   a placeholder or illustrative figure.
5. **Section 4 (static configuration):** template-ID mapping table now
   also lists each size's final retail price alongside its (still
   placeholder) template IDs, so the two pieces of config live in one
   place instead of two.
6. **Section 5 (M1 milestone):** the required multi-size fan-out test now
   explicitly confirms listings publish "at their real EUR prices," not
   just that they publish at all.
7. **Section 9:** D7, D8, D8a moved to resolved. **D6 remains the only
   open item** — unaffected by this revision, still the approve-once-
   per-design-vs-per-size tradeoff from v0.4.5, now covering five
   secondary sizes with real, final prices attached rather than
   illustrative ones.
8. **No other changes.** Trend research, critic pass, Telegram mechanism,
   Gelato confirmations (D4/D5), and SerpApi's parked status (section 8)
   all carry over unchanged from v0.4.6.

## Decisions Needed status: one open item (D6). Everything else in the
spec — including currency, final pricing, and the size lineup — is now
resolved, not just flagged with reference numbers.

---

# Changelog — spec v0.4.7 → v0.4.8

You resolved D6 with a specific middle-ground rule: review the primary
size first; if approved, bundle and approve the rest by aspect ratio
rather than either auto-publishing everything or reviewing every size
individually. This is the last open item — **section 9 now has zero
unresolved decisions.**

1. **Aspect-ratio groups derived from the actual six sizes' geometry
   (section 1, section 4) — a factual determination, not a judgment
   call.** 8x12″ (21x29.7cm) is literally A4 dimensions, and A3/A2/A1
   share the exact same ISO ratio (~1:1.414) — these four form the
   **primary group**. 5x7″ (13x18cm, ~1:1.385) is close but distinctly
   different. 10x24″ (25x60cm, ~1:2.4) is a genuinely different,
   elongated ratio. Both get their own group.
2. **Section 3, steps 6–7 — the core rewrite.** Step 6 is now explicitly
   "primary group review" only. Step 7 splits into: (a) primary-group
   approval auto-publishes A3/A2/A1 alongside the primary with no further
   review, since they share its exact aspect ratio and render identically
   just scaled; (b) the 5x7 and 10x24 groups are then independently
   generated (re-cropped from the same approved artwork — no new
   image-gen call), critic-passed with the same rubric as step 5, and
   sent as their own follow-up digest entries (same `sendMediaGroup` +
   `sendMessage` mechanism, sent immediately in the same evening run) for
   their own separate Approve/Edit/Reject.
3. **Failure handling scoped per group, not per design.** A 5x7 or 10x24
   group that fails critic pass 3 times is abandoned on its own — cleanup
   removes only that group's Gelato product, and the design's
   already-published primary group is untouched. Documented explicitly
   that a design can end up selling at 4, 5, or 6 sizes depending on
   which groups pass review — framed as expected behavior, not an error
   state.
4. **Section 4 (static configuration):** new "aspect-ratio group mapping"
   entry; template-ID table now shows each size's group; data-storage
   schema rewritten around one row per group per candidate (not one row
   per candidate) so each group can carry its own decision, critic-pass
   history, and Gelato/Etsy IDs independently.
5. **Section 5 (M1 milestone):** replaced the old "one secondary size"
   fan-out test with a requirement to exercise the full group flow at
   least once — primary-group auto-publish, plus both an approve and a
   reject/abandon outcome across the 5x7/10x24 groups — flagged as the one
   genuinely new behavior this revision introduces, needing a real-world
   test, not just unit tests against mocks.
6. **Section 6 (learning loop):** decision log now records up to three
   separate approve/edit/reject decisions per design instead of one;
   sales/views data rolls up through group level before reaching the
   design level.
7. **Section 9:** D6 resolved. **No open Decisions Needed items remain.**
8. **No other changes.** Pricing (D7/D8/D8a), the Gelato/Telegram/Etsy
   mechanics, and SerpApi's parked status all carry over unchanged from
   v0.4.7.

## Decisions Needed status: none open. All flagged items across this
spec's revision history (D1–D8a) are resolved.
