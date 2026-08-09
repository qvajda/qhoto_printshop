# GL-13 / GL-17 — Round 2 live re-test, delta launch guide (2026-08-02)

**This is the last gate before the store can publish.** It proves the two
slices Round 1 (GL-9) deliberately left out — the **custom mockup gallery**
and the **v4.12 single-listing publish** — plus the control paths GL-9 never
touched.

Round 1's scenarios (allowlist rejection, Kill branch, 3-attempt critic fail
+ DELETE, orphan-delete idempotency) **passed and are not repeated**. Read
`docs/2026-07-22-v411-live-test-launch-guide.md` for what is already proven;
this document only carries the delta.

Branch: **`master` @ `7cbaee7`** (GL-23b merged). Suite: **635/635 green**.

---

## First: two handover items are stale, and one is not worth buying

Session 2 handed over six live-only items. **Two of them describe a shape
`[D1]` killed**, and repeating them here would mean testing behaviour the
code deliberately does not have. Corrected rather than copied:

| Handover item | Status |
|---|---|
| "**4→5→6 variants across one listing's lifecycle**" | **Stale.** Under `[D1]` the listing is created **once, at its final size** — it never grows. This item was written for the publish-primary-patch-later shape that Q2 killed. **Replaced by:** the listing is created *exactly once*, with *exactly* the validated sizes, and **no duplicate product exists** — which is the part that was ever load-bearing (Q2 proved a title collision silently creates a second product). |
| "**A gallery grown across two reviews**, checked against the real listing" | **Stale at the listing level** — the gallery is assembled once at publish, not appended to. **Still real one level down:** 5x7's render must not wipe primary's images on disk or in the DB. Session 2 has a test for exactly that, and it is cheaper and stricter offline than live. **Replaced by:** verify the *assembled* gallery is complete and correctly ordered on the real listing. |
| "**The 20-cap against a real Etsy rejection**" | **Descoped, deliberately.** `GalleryTooLargeError` raises *before any upload*, so Etsy never sees a 21st image. Proving "Etsy really rejects it" would mean bypassing our own guard to upload 21 images to a live listing — that tests Etsy, not us, and spends real calls to do it. The shipping gallery is 13; the cap is not reachable. **If you disagree, say so** — it is a judgement call, not a fact. |
| "The real `listing_image_id` shape the idempotent re-patch depends on" | **Kept — R4.** Dry-run could assert the mechanism, not the payload. |
| "A rejected group that deleted nothing, `GET`-verified" | **Kept — R5.** |
| "The stall rule" | **Not here.** It cannot fire until GL-7 runs the gate on a cadence. Already recorded as a **GL-7 DoD item**. |

---

## What v4.12 changes about the run itself

**The flow is now three runs of the harness, not one.** `run_m1_live_test.py`
already carries this in its docstring. Under `[D1]`:

1. **Run 1** — seed → generate → primary local render → compliance → critic →
   primary digest. **Zero Gelato calls, zero Etsy calls.**
2. *(you tap Approve on the primary digest entry)*
3. **Run 2** — settles the primary group, then 5x7/10x24 re-crop + local
   render + critic + their digest entries. **Still zero Gelato, zero Etsy.**
4. *(you tap the two secondary digest entries)*
5. **Run 3** — the last decision creates the **single** Gelato product and
   patches the **single** Etsy listing.

**This is a cheaper and safer test than Round 1 was**, and worth noticing:
every external write is concentrated in run 3. Everything before it is local
render and Anthropic/Replicate calls. If something is wrong with the gallery
or the crops, you see it in Telegram **before** anything reaches Gelato.

---

## Ground rules (CLAUDE.md §4)

- **Full suite green before any live call.** Re-run it; do not trust the
  session's number.
- **Every live call is named before it fires. No call runs without an
  explicit per-call go-ahead.** Same STOP-gate discipline as the 2026-07-18
  runbook and the v4.11 guide.
- **`GELATO_LIVE_MODE` / `ETSY_LIVE_MODE` stay `false`** for every scenario
  that does not strictly need a live write — that is R1 and R2 entirely, and
  runs 1 and 2 of R3.
- **Etsy is still in Developer Mode.** Listings created stay non-public
  drafts. **Never call `update_listing_state`; never activate.** That is
  GL-29, it is a one-way door, and it is not part of this test.
- **Gelato has no dev mode.** Every product created is real and must be
  deleted at cleanup.
- **Back up the DB first**, and note that v4.12's migration rebuilt `groups`:
  `cp db/qhoto.sqlite3 db/qhoto.sqlite3.bak-2026-08-02-pre-gl13`
- **One generation for the whole round.** R5 reuses R3's master, the way
  v4.11's S4 reused a condemned one.

## Run order (no-spend first, spend last)

**R0** pre-flight → **R1** placeholder fail-loud *(dry)* → **R2**
`mockup_failed` retry *(dry)* → **R3** the happy path, 6/6 *(the one real
generation + the only Gelato/Etsy writes)* → **R4** re-patch idempotency
*(reuses R3's listing, no new spend)* → **R5** reject path + the Reject
button *(second candidate, no new generation)*.

---

## R0 — Pre-flight (read-only, LIVE_MODE off)

**Hypothesis:** environment and external state are clean before we write.

1. `git log --oneline -1` → `7cbaee7`, working tree clean.
2. Full test suite green.
3. **Reconcile external state before trusting it.** `GET` the Gelato store's
   product list and the Etsy shop's listings. Expect **zero** leftovers from
   GL-22a — session 2 deleted both research drafts (confirmed 404). Anything
   else present is a finding: note its id, do not delete it reflexively.
4. Confirm the shipping gallery is on disk and wired: **13 bundles** (10
   primary + 1 5x7 + 2 10x24), matching GL-19b's reviewed set.
5. Confirm `static_config.json` carries **real** Gelato template/variant IDs
   (no placeholders) and `etsy_shipping_profile_id` is the single value
   `288734253315`.
6. Confirm `.env` has `TELEGRAM_ADMIN_CHAT_ID` set and the bot reachable.

**Pass:** all six. **Any surprise in (3) stops the round** until explained.

---

## R1 — Placeholder fail-loud guard (dry-run, zero spend)

**Hypothesis:** a still-placeholder template/variant ID reaching a real
`products:create-from-template` fails **loudly**, never silently skips the
size or proceeds with a fake ID (CLAUDE.md's placeholder policy).

Temporarily substitute a placeholder ID for one size in a **copy** of
`static_config.json`, run the publish path against it, confirm the error is
loud and names the offending size. Restore the config.

**Pass:** loud failure naming the size. **Fail:** anything silent.

---

## R2 — `mockup_failed` retry, no Gelato fallback (dry-run, zero spend)

**Hypothesis:** a failed local render marks the row `mockup_failed` and
retries **without** falling back to a Gelato-generated mockup.

Note the v4.12 semantic change: `mockup_failed` now means **the local render
failed**, not "the Gelato readiness poll timed out". Verify the retry path
still behaves, and that no Gelato mockup ever enters `product_images`.

**Pass:** retry occurs, gallery stays 100% self-hosted composites.

---

## R3 — The happy path, six sizes, one listing *(the core)*

**Hypothesis:** one candidate, approved at all three groups, becomes
**exactly one** Gelato product and **exactly one** Etsy draft listing,
carrying six variants at their own prices and the full 13-image gallery.

**This burns the round's one generation, one Gelato product, one Etsy
listing.**

### Run 1 — seed → primary digest *(LIVE_MODE off for Gelato/Etsy)*

`python run_m1_live_test.py`

Verify before touching Telegram:
- The generated artwork is **flat full-bleed art** — not a poster-in-a-room
  render. (The first live run printed lifestyle mockups *as* the artwork.)
- The primary digest arrives as **sendMediaGroup + a separate sendMessage**
  with buttons — never one combined call.
- The gallery in that entry is the **custom composited scenes**, in rank
  order, flat scenes first.

→ **Tap Approve** on the primary entry.

### Run 2 — secondaries rendered and sent *(still no external writes)*

`python run_m1_live_test.py`

Verify:
- **The 5x7 and 10x24 crops are real cover-crops** — filling the frame, no
  white bars. This is the defect the first live run shipped; it is the single
  most important thing to eyeball here.
- Each secondary group gets **its own digest entry** with its own buttons.
- **Primary's gallery is untouched** — check `product_images` for the primary
  group's rows and the rendered files on disk. This is the scoped-delete fix
  and the `persist_mockup_render` filesystem-key fix, together.

→ **Tap Approve** on both secondary entries.

### Run 3 — the single publish *(the only live writes in this round)*

**Name each call before it fires.** Flip `GELATO_LIVE_MODE` and
`ETSY_LIVE_MODE` to `true` only now.

`python run_m1_live_test.py`

Verify, by `GET` against the real APIs — not from the DB:
1. **Exactly one Gelato product** for this candidate. `GET` the store's
   product list and count. **A second product with the same title is the
   Q2 failure mode and the highest-value catch in this round.**
2. **Exactly one Etsy listing**, resolved from the product's `externalId`.
3. **Six variants**, each at its own price: 5x7 €19 · 8x12 €24 · A3 €35 ·
   A2 €39 · 10x24 €45 · A1 €49.
4. **13 gallery images**, in rank order, all self-hosted composites.
5. **Shipping profile `288734253315`** on the listing, €0 at checkout.
6. `who_made: i_did`, `is_supply: false`, `when_made: made_to_order`,
   `shop_section_id: 59380312`, `taxonomy_id: 1027`, production partner
   `[5717252]`.
7. **The listing is a draft.** Not active. Confirm.

**Pass:** all seven. **Fail on (1) stops everything** — a duplicate product
means the idempotent-create guarantee is broken and nothing below is safe.

---

## R4 — Re-patch idempotency (reuses R3's listing, no new spend)

**Hypothesis:** running the publish stage a second time against an
already-published candidate **does not duplicate the gallery** — the
`product_images.etsy_listing_image_id` path recognises what is already there.

Re-run the publish stage. `GET` the listing's images and **count**. Still 13.

**Also capture the real `listing_image_id` payload shape** and check it
against what the code assumes — this is the item dry-run could not prove, and
a shape mismatch here is silent until it duplicates a live gallery.

**Pass:** 13 images, no duplicates, shape as assumed.

---

## R5 — Reject path + the Reject button (GL-17), second candidate

**Hypothesis:** rejecting a secondary group **deletes nothing** and yields a
five-size listing.

Seed a second candidate **reusing R3's master** — no new generation. Approve
primary, approve 5x7, **Reject 10x24**.

> **The Reject button has never been tapped in a live run.** That is GL-17's
> entire content. Do it deliberately and watch what the callback does.

Verify:
1. **`GET` the Gelato product and Etsy listing before and after the
   rejection.** Variant count and image count unchanged by the act of
   rejecting.
2. The published listing carries **five** variants — 10x24 absent.
3. The 10x24 group is marked `rejected`; **no Gelato product and no Etsy
   listing was deleted**.
4. The other groups' images and variants are intact.

**Pass:** all four. **This is the constraint v4.12 rewrote CLAUDE.md for** —
under v4.11 this same action deleted a product.

---

## Cleanup & exit

Both candidates' products and listings are **real** and must be removed.

- **Use the `GET`-before-delete discipline session 2 learned the hard way:**
  match on a stable marker, **not on the title** — Q3's patch test renamed
  two drafts and the title-based guard correctly refused. Record every id
  **before** deleting; confirm 404 after.
- Delete the Gelato products (no dev mode — they are real).
- Delete the Etsy drafts via `delete_listing` (`listings_d` is authorised).
- Set `GELATO_LIVE_MODE` / `ETSY_LIVE_MODE` back to `false`.
- Restore or retain the DB backup deliberately, and say which.

## Failure protocol

Unchanged from the 2026-07-18 runbook and the v4.11 guide:

1. **Incident note first** — what failed, which stage, exact error /
   CF-Ray / API response, what was ruled out, and **the state left behind**
   (DB rows, Gelato product ids, Etsy listing ids).
2. If diagnosable, write a resume prompt so the round restarts **without
   redoing passed scenarios**.
3. Success or failure, end with a handoff: branch state, external-account
   state with ids, and the single next action.

**Do not hand-delete a Gelato product or Etsy listing on a failure** until
you have `GET`-confirmed what state it is actually in. Q2 and Q3 both showed
the product/listing pair can desync without anything having gone wrong from
the buyer's side — and the PRD's rollback section says the same.

## Exit criteria → the go-live gate

GL-13 + GL-17 pass when **R0–R5 pass**. That clears the custom gallery, the
v4.12 single-listing publish, and the last untested control path.

**Then, in order:** the **GL-11 email goes out** (owner sequencing — it waits
on this pass, and from that moment it is the only critical-path item on
someone else's clock), **GL-29** activation behind its flag proven with one
paid activation, **GL-11** Developer Mode off.

**Still independent and unblocked by this:** GL-7 cron + soak (the long
pole, and where the stall predicate finally gets proven), GL-10 storefront,
GL-30 corpus backup, GL-12.
