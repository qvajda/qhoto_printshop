# GL-10b storefront checklist — paste-ready

**Artefact 2 of 5.** GL-10's stated acceptance is a how-to/checklist; **the owner
executes in Shop Manager.** Nothing here is an API write and nothing in this
project touches the live shop.

**Copy uses `QhotoArt`, one word** (Q8) — that is what a buyer sees in the shop
URL and the search row. The *wordmark* may set it differently; that is a design
question and it lives in artefact 4 §4.4.

**Order matters for one item only.** Item 5 (the structured AI-generator tick)
**publishes the listing** — see the warning there. Items 1–4 and 6 are safe in
any order.

---

## 1. Shop tagline — **new surface, not in the original brief**

**Shop Manager → Shop Manager → Sales Channels → edit shop → Shop title.**
Cap: **55 characters.** Etsy: *"Your tagline appears under your shop name on
your shop homepage… this can help Google better understand what kinds of
products your shop sells."* QhotoArt currently has none (findings R12).

Three options. Character counts are exact.

| # | Text | Chars |
| --- | --- | --- |
| **A (recommended)** | `AI-made botanical & minimalist art prints, unframed` | **51** |
| B | `Calm botanical, celestial & minimalist wall art prints` | **54** |
| C | `Minimalist art prints & framed photography from Qrchard` | **55** |

*(Counts measured, not estimated — an earlier draft of this table was one
character short on all three. C sits **exactly** on the 55 cap with no margin;
if Etsy counts the field differently in any way, it is the one that breaks.
A further argument for A.)*

**Why A.** It carries the three things the surface is for: the **subject**
(botanical, minimalist — the two largest buckets in
`docs/safe_evergreen_bucket.md`), the **product form** (art prints, unframed —
which is also the section-name axis, item 2), and the **AI disclosure**, at the
shop level, where it costs nothing per listing. Option C spends 8 of 55
characters on brand lineage that the About already carries better.

---

## 2. Rename the pipeline section

**Shop Manager → Listings → Manage → rename the section currently called
"Posters"** (`shop_section_id` **59380312**).

**This looks free and reversible, on observation rather than documentation**
(findings R11): section URLs are `?section_id=<numeric>` on every shop in the
sample, so the name is not in the URL. **Etsy's own help page is silent on it**,
so treat "renaming breaks nothing" as a strong inference, not a guarantee —
worth a 30-second check on your own shop before you lean on it.
`config/static_config.json`'s `etsy_shop_section_id` is genuinely unaffected by a
rename, since it stores the numeric id. Cap: **24 characters.**

### The constraint the candidates are built against

"Framed Photography" is `[qualifier] + [medium]` with a **product-form**
qualifier — *framed*. The two sections therefore separate on **framed
photography vs unframed generated prints**, which is a real difference a buyer
cares about. GateOfDesign — the sample's closest structural analogue, because it
too sells two fulfilment types side by side — does exactly this: `PRINTED
Gallery Sets` / `PRINTED Single Prints` / `VINTAGE Gallery Sets`. **Qualifier
first, medium second.** And **0 of 10 shops in the sample use the bare word
"Posters"** (findings R10).

### Candidates

| # | Name | Chars | Evidence for | Against |
| --- | --- | --- | --- | --- |
| **1 — recommended** | **`Unframed Art Prints`** | **19** | Exact pattern match to "Framed Photography": product-form qualifier + medium. Reads as a deliberate pair in the left rail. "Art print" is the dominant medium word in the sample's titles; "poster" is a distant second | Leads with a negation — a buyer could read "unframed" as a lack rather than a choice |
| 2 | `Wall Art Prints` | 15 | Highest keyword value of the five: "wall art" is the category head term and "prints" the medium. Neutral, no negation | Breaks the pair — the qualifier is not product-form, so the two sections no longer separate on a stated axis |
| 3 | `Unframed Wall Prints` | 20 | Keeps the pair **and** carries "wall". A compromise between 1 and 2 | "Wall prints" is a less-used medium phrase than "art prints" in the sample |
| 4 | `Rolled Art Prints` | 17 | Most literally true — Gelato ships rolled in a tube, and TheWorldGallery's description block sells exactly that ("strong poster tubes") | "Rolled" is fulfilment jargon; buyers don't search it |
| 5 | `Art Prints & Posters` | 20 | Widest keyword net | No qualifier at all, so it neither pairs nor differentiates; and it keeps the word the whole sample avoids |

**Recommended: `Unframed Art Prints` (19).** It is the only candidate that
completes the pair on the axis §3.1 identified, and the sweep's one structural
analogue names its sections the same way. **If the negation reading worries you,
take #3 `Unframed Wall Prints` (20)** — same pair, one extra keyword, one
character under the cap's comfort margin.

> **Not in scope:** a subject taxonomy (Botanical / Celestial / Minimalist).
> Routing listings into different sections by subject means the publish path
> stops reading a single `etsy_shop_section_id`, which is code, and it is
> deferred post-launch with GL-10c (brief §10).

---

## 3. About — paste as-is

**Shop Manager → Sales Channels → edit shop → About.**

Written to ~120 words. The sample's About sections run ~80 words; this one runs
longer because it carries a disclosure the others don't need. Etsy's own SEO
guidance for this field asks for *"your background, creative process, and years
of experience"* — the two paragraphs below are process and provenance in that
order.

```
QhotoArt makes calm wall art for rooms people actually live in — botanical,
minimalist, celestial and mid-century designs, printed on demand and shipped
unframed.

The designs in this shop are made with AI image generation. I write and direct
every prompt, choose the composition, colour and crop, and review each design
before it is listed — but the image itself is generated, not drawn or
photographed by hand, and I would rather say so plainly than bury it. Printing
and delivery are handled by a print partner, so your print is made when you
order it rather than sitting in a warehouse.

The Framed Photography section is different: those are my own photographs.

QhotoArt is part of Qrchard.
```

**Why it reads the way it does.**

- **The AI statement is a paragraph, not a footnote** (brief §6 point 2). It is
  a **shop-level** disclosure surface, set once, with no per-listing cost — and
  under GL-37 it is the only *written* disclosure that exists anywhere, since
  `DISCLOSURE_TEXT` in `pipeline/compliance_draft.py` is now `""`.
- **It says what is and isn't human.** "I write and direct every prompt… but the
  image itself is generated" is the honest version. Vaguer phrasings ("created
  with the help of AI tools") are what buyers read as evasive.
- **It discloses the print partner** without naming Gelato, which is what
  Etsy's production-partner field is for and which is already set
  (`production_partner_ids: [5717252]`).
- **It survives a second Qrchard venture.** "QhotoArt is part of Qrchard" is a
  single line that stays true whatever else Qrchard launches (§2.5).
- **It names the photography line**, which has its own live section.

**Also unbuilt and worth a later item:** the About section accepts **up to 5
images and a video**. For an AI-art shop that is the strongest available trust
surface — process shots, the print in hand, packaging. Not in GL-10b's scope.

---

## 4. Policies — fill and paste

**Correction (2026-08-08): §4 originally assumed all five sub-items were free-text
policy fields in Shop Manager → Settings → Policies. They aren't.** Etsy's
actual Policies surface, per the owner's own dashboard, only has two settable
things: a **Returns & exchanges picker** (toggles + a number of days, not
prose) and a **Privacy free-text field**. Dispatch & delivery, Sizes & colour,
and How these designs are made are not policy fields at all — there's nowhere
in Policies to paste them. Renumbered below to match what's actually there.

### 4.1 Returns & exchanges — picker, not prose

**Shop Manager → Settings → Policies → Returns & exchanges.** This is
accept-returns (y/n) + accept-exchanges (y/n) + a number-of-days field, not a
text box.

**Configured (owner, 2026-08-08): returns accepted, 14 days, no exchanges.**

> The earlier draft's caveat about EU distance-selling law (14-day withdrawal
> right, with a "made to the consumer's specifications" exemption that's
> arguable for made-to-order posters) still applies to *whether* 14-day
> returns is the right call — it's just now a toggle decision instead of a
> wording decision. 14 days matches the safe default the draft recommended,
> so no further action unless you want to revisit accepting returns at all.

### 4.2 Privacy — free text, confirmed real

**Shop Manager → Settings → Policies → Privacy.** This field is genuinely
free text (unlike the three below, this one really is a Policies field).
Use the drafted policy in `docs/2026-08-08-gl10b-privacy-policy.md` —
paste-ready, built from Etsy's seller-handbook GDPR writing guide with
QhotoArt's actual facts (Etsy + Gelato as the only data recipients, no
mailing list, Belgium tax-retention framing). Confirm the Belgium assumption
noted there before pasting.

### 4.3 Dispatch & delivery — dropped

**Owner decision (2026-08-08): drop this as a separate block.** Processing
time is already declared numerically on the Gelato shipping profile
(`288734253315`) and Etsy surfaces that automatically on every listing —
a free-text duplicate has no field to live in and would just repeat it.

### 4.4 Sizes & colour, and how designs are made — not yet placed

These aren't policy fields, and where they *should* live is still open:
candidates are the shop's **FAQs** field (Shop Manager → Settings → Info &
Appearance, if that's what you see there — not independently confirmed
against your dashboard the way the Returns picker now is) or folded into
each listing's description. **Flagging rather than assuming** given the
Policies-field guess just turned out wrong — worth a quick look at what's
actually on that settings screen before drafting copy for it.

Note on 4.4's content specifically ("designs made with AI, directed and
reviewed by me / Framed Photography is my own photography"): this already
exists almost verbatim in the pasted About text (item 3), so it may not need
a second home at all — check whether About already covers it well enough
before deciding.

---

## 5. ⚠️ The structured AI-generator tick — **this publishes the listing**

**Per listing, in the web listing editor**, under Etsy's Creativity Standards:
*"How does your shop produce this item?"* and *"What tools are used to make this
item?"* → **an AI generator**.

**These two fields are not settable through the v3 API** — not on the listing,
not among taxonomy 1027's properties, not as a shop-level default (GL-37,
re-verified 2026-08-06; upstream `etsy/open-api` Discussion #1630 still
unactioned). **And the web editor's only save action is "Activate with
changes" — there is no draft-save.**

> **So this is not "a quick tick before launch." Ticking it activates the
> listing.** It is the publish action. Sequence it with GL-11/GL-29 accordingly,
> and do not do it on a listing you are not ready to make live.

**Two things are load-bearing on each other here — do not undo either half
alone.** The prose AI disclosure has been removed from listing descriptions
(`DISCLOSURE_TEXT = ""`), which is only safe *because* this structured tick
happens at publish; and GL-29, programmatic draft→active activation, is
cancelled for the same reason (`etsy_client.update_listing_state` stays
`# DELIBERATELY UNWIRED`). Automating activation while the description carries
no disclosure would publish a listing with **neither**.

---

## 6. Announcement — leave off

**Q3 decided: not used.** Nothing in the sweep changes that. Of the ten sampled
shops only TheWorldGallery ran one and it was inert ("Welcome! Contact us if you
wish to inquire about custom sizes", last updated April 2025).

**Revisit only on a structural use** — dispatch delays, a holiday cutoff date —
never for sale messaging.

---

## Checklist

- [x] **1.** Paste tagline (option A, 50 chars)
- [x] **2.** Rename section 59380312 → `Unframed Art Prints`
- [x] **3.** Paste About
- [x] **4a.** Returns & exchanges picker: 14 days, returns yes, exchanges no
- [x] **4b.** Paste privacy policy (`docs/2026-08-08-gl10b-privacy-policy.md`) into Policies → Privacy
- [x] **4c.** Decide where Sizes/colour + how-designs-made copy actually lives (FAQs? per-listing?) — not a Policies field, not yet placed
- [x] **5.** *(publish step — sequence with GL-11)* tick "an AI generator" per listing
- [x] **6.** Announcement: leave off
- [x] **7.** *(artefact 4)* upload `qhoto-shop-icon-500.png` and the rebuilt banner, replacing the live pair

**Not in this checklist and not in this project:** the listing title/tag/
description template (artefact 3 — spec only, build is GL-10c, post-launch), the
keyword delta (artefact 5 — proposed, needs its own approval), and the banner
rebuild (artefact 4 — phase 7, Claude Code).
