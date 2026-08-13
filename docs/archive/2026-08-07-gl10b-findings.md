# GL-10b findings — QhotoArt storefront teardown

**Artefact 1 of 5.** Sweep run 2026-08-06/07 in one Cowork session, per brief
§12.1. Raw coding lives in `docs/data/gl10b-rubric.md` (rubric + counts +
Layer 2) and `docs/data/gl10b-keyword-surface.md` (bestseller discovery). This
file is the argument; those are the evidence.

Sample: **n = 10 shops**, every one reached by being behind a listing that
ranks, never by looking good (§4 sampling rule). Combined **458,802 sales**.

---

## 0. Three things about the method, before any rule is read

**M1 — Two rubric fields could not be coded as written, and are marked so
rather than guessed.** Etsy no longer exposes listing **tags** to buyers
anywhere — not rendered, not in the HTML, not in a meta tag. The Tags row is
`NOT OBSERVABLE` for all ten shops and **title tokens are used as the proxy**.
Per-listing **sales** are also unavailable; the Bestseller badge and review
count stand in. The practical cost: artefact 5's keyword delta is built from
what competitors put in *titles* and from SERP occupancy, not from their tag
lists. It is a weaker instrument than the brief assumed and the rules below are
scoped accordingly.

**M2 — The sort is a proxy and it has a known bias.** Etsy has no "most sold"
sort; `order=highest_reviews` is the closest thing and it favours shop age and
review momentum. That is precisely the bias §4 predicted, and it shows: the
sample skews to shops 4–13 years old. Every keyword the sweep discovered is
tagged trend-or-evergreen in artefact 5 before it can reach
`safe_evergreen_bucket.md`.

**M3 — I corrected one of my own mid-sweep findings.** I recorded from
competitor CDN filenames (`isbl_1680x420`) that Etsy's banner spec had moved to
1680 × 420. **It has not.** Etsy's own help page still recommends 1600 × 400,
and 1680 × 420 is the CDN render size. The wrong version is left in the data
file with the correction beneath it, because §7.0 obs. 4 explicitly asked not to
assume either the old spec or the live file was right — and the answer turned
out to be "the old spec, and GL-10a was correct."

---

## 1. The rules

Fifteen rules. Each carries **(a)** the evidence, **(b)** the surface it
changes, **(c)** structural or aesthetic per §2.

---

### R1 — Do not compete on head terms. The head of "wall art" is a personalisation market, and the pipeline cannot enter it.

**(a) Evidence.** Sorted by review count with digital downloads excluded, the
top **9 of 9** non-ad results for `wall art print` are personalised or
customer-supplied-file products: custom song lyrics, pet portraits, photo
canvases, name prints. Zero are a fixed pre-designed print. The pattern repeats
inside our own niches: `minimalist line art poster` returns custom couple and
pet portraits at 4 of 8; `moon phase print` returns custom date-derived prints
at 4 of 10.

**(b) Surface.** `pipeline/research.py` — niche selection. And the listing-copy
spec's title formula, which must not spend tokens on head terms.

**(c) Structural.** This is about what the pipeline *can physically make*, not
about taste. QhotoArt generates fixed designs; personalisation is a different
product with a different fulfilment path.

**So what.** Every term in `safe_evergreen_bucket.md` should be checked for
personalisation occupancy before it is trusted, and the shop's ranking strategy
is long-tail aesthetic-descriptor, not category head term.

---

### R2 — `moon phase print` is in the evergreen bucket and should not be. Its SERP is owned by dated calendars.

**(a) Evidence.** Of the top 10 results, **4 carry a year in the title**
(2026 or 2027) and a further 4 are personalised. `OriginalLunarPhase` — a
**3-listing, 13-year, 5.0-rated, 22,508-sale** shop whose single section is
literally named **`2026`** — is the category's anchor. A dated calendar is
seasonal by construction: it is worthless on 1 January.

**(b) Surface.** `docs/safe_evergreen_bucket.md` (proposed removal/rewording)
and `collect_event_lookahead()` (proposed seasonal window).

**(c) Structural.** The bucket's own test — "roughly flat search volume
year-round" — is failed by the listings that occupy the term, even though the
term itself sounds evergreen.

**So what.** The bucket was validated on *terms*. This sweep is the first time
it has been validated against *who actually ranks for them*, and one entry
fails. See artefact 5.

---

### R3 — Colour-family words and room words are a large, cheap, entirely missing keyword axis.

**(a) Evidence.** Recurring across every niche SERP and absent from
`safe_evergreen_bucket.md` in its entirety: *neutral, beige, sage green, dusty
pink, terracotta, navy blue, amber, honey, orange, pastel, black and white* and
*bedroom, kitchen, nursery, living room, hallway, entryway, office, bathroom*.
Concrete instances: `Beige Botanical Line Art Print Set` (LotusNurseryArt,
11.9k reviews); `Set of 3 **Neutral** Wall Prints, Botanical Wall Prints,
**Bedroom** Wall Prints` (WoodSagePrints, Bestseller badge); `Peeking Dog Wall
Art, Minimalist Line Art Poster, **Terracotta Kitchen** Wall Decor` (EdFoxEd,
Bestseller badge). Six of ten shops run **room** sections.

**(b) Surface.** Two of them. `pipeline/research.py`'s term list (artefact 5),
**and** the listing-copy title formula — because a colour word is a property of
the *generated artwork*, knowable at draft time, and a room word is a property
of the *niche*.

**(c) Structural.** These are search-behaviour facts, not style preferences.

**So what.** This is the highest-leverage, lowest-risk finding in the sweep. It
adds a token slot to the title formula and a modifier axis to research, and it
changes nothing about what the art looks like.

---

### R4 — Sets are the basket-size lever, and they show up in the *title as a number*.

**(a) Evidence.** 4 of 8 botanical results and **7 of 7** gallery-wall results
sell a multi-print set, with the quantity stated numerically in the title
("Set of 3", "Set of 6", "4 Piece", "3 Print Bundle"). **6 of 10** shops run a
set/bundle **section**; TheWorldGallery's `SETS OF 3` section alone holds
**1,369 listings**; LotusNurseryArt productises it further with `CREATE YOUR
SET` and `MIX & MATCH` sections; GateOfDesign's whole taxonomy is
`[qualifier] Gallery Sets` vs `[qualifier] Single Prints`.

**(b) Surface.** **None inside GL-10b.** Sets are a Gelato product change and
§10 defers them explicitly.

**(c) Structural.**

**So what.** Recorded as a **roadmap finding with a size**: it is the single
mechanism by which every high-volume shop in the sample raises order value, and
QhotoArt currently has no path to it. It should be filed as its own item, not
implied by this one.

---

### R5 — The icon question is settled by a clean 10/10 split, and GL-10a already got it right.

**(a) Evidence.** Judged at true avatar size (74 px rendered), never zoomed:

| | Legible at 74 px | Illegible at 74 px |
| --- | --- | --- |
| **Symbol-led** (no wordmark, or a dominant symbol) | **4** — LotusNurseryArt (bear), galerie61 (`g61` monogram), BrightBlueStar (star), OriginalLunarPhase (moon) | **0** |
| **Wordmark-led** | **0** | **6** — TheWorldGallery, WoodSagePrints, MotherAndSunStudioUK, DIVANNO, SimplyExtraJordanary, GateOfDesign |

Ten out of ten, on one variable, with no exceptions in either cell. Two of the
illegible six are Star Sellers with 20k+ sales — so a bad icon does not stop a
shop, but none of them gains anything from theirs.

**(b) Surface.** The shop icon. `assets/brand/` + `verify.py`'s legibility
assertion.

**(c) Aesthetic in form, measured in substance** — and §2.3 puts legibility
outside the research's vote for exactly this reason.

**So what.** **GL-10a's icon — Bone badge on a Pine ground, symbol only, no
wordmark, 8.7:1 — is already the treatment that goes 4/4.** It arrived there by
measurement (README "Colourway"), before this sweep existed, and the sweep
independently confirms it. **The live `shop_icon.jpg` — a monogram stacked over a
"Qhoto-Art" wordmark filling the lower half — is the treatment that goes 0/6.**

---

### R6 — Every banner in the sample is on a light ground. That is a differentiation opportunity, not an instruction.

**(a) Evidence.** **10 / 10 light. 0 / 10 dark.** Warm cream, white, sage,
blush, candy-stripe pink, grass green.

**(b) Surface.** The shop banner, and D-A (§2.2).

**(c) Aesthetic** — and therefore, per §2.4, it only moves D-A as a **count**,
never as a preference.

**So what.** §2.4 wrote the reading rule in advance and it applies literally:
*"'The mean is bright' is not evidence that bright wins."* A 10/10 uniformity
with no sales correlation attached to it (see R7) is the definition of an
undifferentiated field. Qrchard's Ink/Charcoal ground is the only thing in the
category that would not look like everything else.

---

### R7 — Register does not correlate with sales in this sample. §2.4 predicted this, and it is the finding that resolves D-A.

**(a) Evidence.** Sales per listing, against banner register:

| Shop | Register | Listings | Sales | Sales/listing |
| --- | --- | --- | --- | --- |
| OriginalLunarPhase | photographic, silent, no type | 3 | 22,508 | **≈7,500** |
| galerie61 | **type-led, white, hairline serif, no imagery, no promo** | 98 | 23,230 | **237** |
| GateOfDesign | hybrid + `SALE UP TO 75% OFF` | 686 | 46,859 | 68 |
| SimplyExtraJordanary | lifestyle photo, no type | 393 | 20,925 | 53 |
| BrightBlueStar | 4-panel + tagline | 656 | 22,790 | 35 |
| MotherAndSunStudioUK | **`30% OFF` in hand-lettering on candy stripes** | 1,276 | 31,961 | 25 |
| WoodSagePrints | hybrid + free-shipping panel | 819 | 17,346 | 21 |
| DIVANNO | product still-life, no type | 1,081 | 17,408 | 16 |
| TheWorldGallery | photographic gallery interior, no type | 13,368 | 195,865 | 15 |
| LotusNurseryArt | lifestyle + tagline | 7,820 | 59,910 | 7.7 |

The restrained end and the shouty end are interleaved. The calmest brand in the
sample (galerie61) is second-best per listing; the loudest (MotherAndSun,
GateOfDesign) sit mid-table; the biggest shop by absolute sales
(TheWorldGallery) is third-*worst* per listing.

**(b) Surface.** D-A.

**(c) Structural** — it is a null result about an aesthetic variable, which is
itself a structural fact.

**So what.** **§2.4's own words: "register may simply not correlate with sales,
in which case D-A resolves to A1 by default."** That is what the counts say.
The full decision is §2 of this file.

**And the honest caveat, because §2.4 demands it.** Both outliers are
confounded. galerie61 sells **public-domain artist reproductions** (Picasso,
Monet, Matisse, William Morris) — its 237 sales/listing is a demand story about
Picasso, not a branding story about hairline serifs. OriginalLunarPhase sells
one dated product with 13 years of reviews. **Neither proves restraint sells.**
What they jointly establish is the weaker but sufficient claim: **restraint is
not a handicap**, so the default stands.

---

### R8 — The panelled banners are a paid feature. Half the sample's treatment is not available to QhotoArt.

**(a) Evidence.** Etsy's own image-requirements page: *"The carousel and collage
banners are only available to sellers subscribed to Etsy Plus."* Five of the ten
sampled shops run a panelled or carousel banner (dot indicators visible on
WoodSagePrints, LotusNurseryArt, MotherAndSunStudioUK; four-panel grid on
BrightBlueStar; three-zone composition on GateOfDesign).

**(b) Surface.** The banner brief, and any recommendation derived from it.

**(c) Structural.**

**So what.** QhotoArt on the free tier has exactly **one** option: a single
static 1600 × 400 big banner. Any "do what BrightBlueStar does" recommendation
is covertly a recommendation to buy Etsy Plus and must be labelled as one. It
also means the honest comparison set for our banner is the four imagery-only
shops and galerie61 — not the five panelled ones.

---

### R9 — The live QhotoArt banner fails on four independent counts, none of which is about taste.

**(a) Evidence.** Measured locally on `assets/brand/etsy-banner.png`:
**1600 × 896, 1497.5 KB.**
1. **Promise mismatch.** It depicts framed *figurative portrait* works. The
   pipeline generates botanical / minimalist / celestial / abstract from
   `safe_evergreen_bucket.md`. The banner advertises a product line the shop
   does not sell.
2. **A visible generation artifact** — one framed poster carries garbled
   lettering ("O E M Y A I T"), in the largest brand surface on the page.
3. **File size.** 1,497.5 KB against Etsy's stated *"Images larger than 1MB in
   file size may not finish uploading."*
4. **Dimensions.** 1600 × 896 matches **no documented Etsy format** — not big
   (1600 × 400), not mini (1600 × 213), not carousel (1200 × 300), not collage.
   Etsy will crop it, and we do not control where.

**(b) Surface.** The banner.

**(c) Structural, all four** — they survive the §2 filter regardless of what
D-A returns. Points 3 and 4 are now sourced from Etsy's own help page rather
than assumed (§7.0 obs. 4 asked for exactly this).

---

### R10 — Nobody in the sample names a section "Posters", and the one shop that splits by product form does it with an ALL-CAPS qualifier prefix.

**(a) Evidence.** **0 / 10** shops use the bare word "Posters" as a section
name. Median section count 17 (range 5–20). Naming axes observed: subject (9/10),
room (6/10), set/bundle (6/10), style-era (5/10), tone (3/10), season (3/10),
**orientation** (SimplyExtraJordanary: `HORIZONTAL PRINTS`), and **year**
(OriginalLunarPhase: `2026`). **GateOfDesign** — the closest structural analogue
to QhotoArt, because it too sells two fulfilment types side by side — splits its
catalogue with `PRINTED Gallery Sets`, `PRINTED Single Prints`, `VINTAGE Gallery
Sets`, `VINTAGE Single Prints`. The qualifier is **product form / fulfilment,
in caps, first**; the descriptor follows.

**(b) Surface.** The §3.1 section rename. See artefact 2.

**(c) Structural.**

**So what.** "Framed Photography" is `[qualifier] + [medium]` with a
product-form qualifier — the same shape GateOfDesign uses, and it is the shape
the sweep says works. The rename candidates in artefact 2 are built to complete
that pair.

---

### R11 — Renaming the section is free. The brief's "get it right now" urgency is unfounded.

**(a) Evidence.** Etsy's sections help page confirms the 24-character cap, a
20-section maximum, and one-section-per-listing. On the URL question the page is
silent, but every sampled shop's section links are of the form
`?section_id=<numeric>` — **the name is not in the URL.** `static_config.json`'s
`etsy_shop_section_id` (59380312) is likewise unaffected.

**(b) Surface.** §3.1's constraint list.

**(c) Structural.**

**So what.** Get it right because it is a browse and relevance surface, not
because it is a one-way door. It is not.

---

### R12 — There is a sixth copy surface the brief does not list: the 55-character shop tagline. QhotoArt has none.

**(a) Evidence.** Etsy's SEO help page: *"Your tagline appears under your shop
name on your shop homepage. It can be up to 55 characters… this can help Google
better understand what kinds of products your shop sells."* The same page names
the four shop-page SEO elements as **tagline, About, images/video, policies**.

**(b) Surface.** Shop Manager → shop title/tagline. Added to artefact 2.

**(c) Structural.**

**So what.** A free, indexed, shop-level keyword surface that costs one paste,
and it was not in the brief's success criteria. Also unbuilt: the About section
accepts **5 images and a video**, which is a real trust surface for an AI-art
shop and is worth a later item.

---

### R13 — The Gelato-pushes-we-patch architecture permanently freezes every listing's URL to Gelato's title.

**(a) Evidence.** Etsy's SEO help page, verbatim: *"Your listing's URL is based
on the title you enter when you first publish the listing. Once it's published,
the URL won't change again, even if [the title changes]."* CLAUDE.md's
integration constraint has Gelato create the listing and the pipeline PATCH
title/description/tags/price afterwards.

**(b) Surface.** **None in GL-10b.** It is an architecture note for GL-29/GL-11.

**(c) Structural.**

**So what.** Every QhotoArt listing will carry a URL slug derived from Gelato's
auto-generated product title, and the patched title will never reach it. The
cost is Google SEO only — Etsy's internal search reads the title field, not the
slug — so it is real but bounded. **Flagged, not solved, and deliberately not
folded into this project's scope.** It should be filed.

---

### R14 — Tags are capped at 20 characters, which disqualifies a third of the discovered surface.

**(a) Evidence.** Etsy's tags help page: 13 tags per listing, **20 characters
each**. Measured against `safe_evergreen_bucket.md`: `mid century modern wall
art` (27), `continuous line illustration` (28), `minimalist landscape print`
(26), `geometric shapes wall art` (24), `single line drawing art` (23) — all
**cannot be tags at all**. Etsy's guidance also asks for *"a diverse array"*
and flags tags as the right home for *"aspirational or buyer-minded search
terms"*.

**(b) Surface.** The listing-copy template spec's tag strategy (artefact 3).

**(c) Structural.**

**So what.** The tag generator needs a **length budget as a first-class
constraint**, not a post-hoc trim, and long phrases must be routed to the
*title* (which has no such cap) while their short heads go to tags.

---

### R15 — 8 of 10 lead with a framed or in-room first image. This is the biggest lever in the sweep and it is out of scope by design.

**(a) Evidence.** First gallery image: framed / in-room / lifestyle **8/10**;
flat art with no frame **2/10** (TheWorldGallery, MotherAndSunStudioUK);
product photography of the physical object **1/10** (OriginalLunarPhase, and it
is the highest-converting shop in the sample). Staging is *consistent within a
shop* — galerie61 uses one repeated leaning-frame scene across all 98 listings;
DIVANNO uses one plain-wall single-frame scene; SimplyExtraJordanary uses one
sunlit ledge.

**(b) Surface.** **The mockup/scene layer — GL-6 / GL-21**, as a scene-authoring
note, subject to the 2 % crop budget and `scripts/mockup_qa.py` like every other
scene (brief §5 point 3, §10).

**(c) Structural.**

**So what — routed, not built.** Two notes for GL-6/GL-21: (i) the field's
default is a framed print in a styled room, and the two shops that lead with
flat art are the two lowest per-listing performers among the type-led group,
which is suggestive and nothing more; (ii) **scene consistency across a
catalogue appears to be worth more than scene variety** — every shop in the
sample repeats one or two scenes rather than varying them, which is convenient,
because a small hand-authored scene library is exactly what CLAUDE.md's
Nano-Banana-into-`inflow` workflow produces.

---

## 2. D-A resolved — **A1, with two parameter-level amendments**

Argued from counts only, per §2.4. Ratification is the owner's (§7.3).

**The counts that bear on it:**

| Claim | Count |
| --- | --- |
| The field's ground is uniformly light | **10 / 10 light, 0 / 10 dark** |
| Register correlates with sales | **No.** Calm and shouty interleave across the sales/listing table (R7) |
| Wordmark-led icons survive avatar size | **0 / 6.** Symbol-led: **4 / 4** (R5) |
| Type-led banners are the field norm | **No — 1 / 10** (galerie61) |
| Banners carrying imagery carry *product* imagery | **8 / 10** (framed prints, in rooms or on shelves) |

**Why A1.** §2.4 wrote the decision rule before the data existed: if register
does not correlate with sales, D-A resolves to **A1** by default and the
differentiation argument for a dark, calm storefront in a bright field gets
*stronger*. R7 is that null result. R6 is that uniformity. And R5 shows GL-10a's
icon independently landing on the only treatment that survives the sample's
legibility test. A1 is also the only option already built, verified against 27
assertions, and free.

**The Qrchard nod (§2.1) is satisfied trivially at A1** — it is the badge
geometry itself, and the element that carries the link is nameable: the Q-bowl
and ring construction, shared with Qrchard, differing only in the tail
(Q-as-O vs Q-as-P, `badge.py` docstring).

**Amendment 1 — the banner gains a product-imagery band.** This is a
composition change *inside* A1, not a move to A2: the palette, typefaces, badge
geometry and `verify.py` constants are untouched. It is warranted because
type-led is a 1/10 minority treatment and the one shop running it is confounded
(R7 caveat), while 8/10 carry framed-print imagery. **The imagery should be
composited from existing mockup renders** — real QhotoArt prints, in the
existing scenes, on the Ink ground — which also fixes R9's promise mismatch at
its root: the banner then depicts exactly what the shop sells.

**Amendment 2 — `verify.py` gains one new assertion and one re-parameterisation.**
New: **no alpha channel** (Etsy renders transparency as black, per its own image
requirements page; nothing currently catches it). Re-parameterised: the
**safe-zone assertions** (lines 82–88), which are written for a full-width
centred type lockup and will not hold once the imagery band moves it.

> **Correction to my own first draft of this amendment.** I proposed a second
> new assertion — file size < 1 MB — before reading the file. **It already
> exists**, at `verify.py` line 45. The count of assertions must go **up**, not
> down: losing the verifier is the actual risk of any asset change here (brief
> §7.4), so a re-parameterisation must never become a deletion.

**What would have changed the answer.** A2 or A3 would have needed a count
showing register moving sales — e.g. light-ground shops out-selling dark ones
per listing. **There are no dark-ground shops in the sample at all**, so that
count cannot be constructed from this data, and a decision to move away from
Qrchard would have had to come from taste. §2.4 forbids that.

## 3. Banner / icon decision — **replace the live pair with the GL-10a pair; adjust the banner; keep the icon**

| Asset | Decision | Grounds |
| --- | --- | --- |
| **Icon** | **Keep GL-10a's** `qhoto-shop-icon-500.png` — Bone badge on Pine ground, symbol only. Upload it. | R5 (4/4 vs 0/6), and the 8.7:1 measurement it was already built on |
| **Banner** | **Adjust GL-10a's**, don't rebuild: keep the Ink ground and the Pine/Bone lockup; add a band of composited mockup renders of real listings; re-emit at 1600 × 400, flattened, under 1 MB | R6 + R7 (A1 stands) and Amendment 1 (8/10 carry product imagery) |
| **Live pair** | **Retire both.** Not a D-A judgement — R9's four structural failures | R9 |

**Nano Banana Pro role: C — concept exploration only.** §7.3's rule, applied
mechanically. Role **A** requires imagery-led banners in a clear majority
**and** the imagery to be *atmospheric rather than product*. The first clause
passes (8/10); **the second fails** — every one of those eight is framed
product in a styled room, which is not a texture plate, it is a mockup. Role
**B** halts by owner decision and nothing here disturbs that. **The imagery
Amendment 1 calls for is already produced deterministically by the compositor**,
so there is nothing for a generative model to make that we cannot make better
and reproducibly. Default C also applies independently: the treatment signal is
split 4 imagery-only / 5 hybrid / 1 type-led, which §7.3 calls "too varied to
read a signal."

## 4. What this changes, by file

| Finding | Lands in | Status |
| --- | --- | --- |
| R2, R3 | `docs/safe_evergreen_bucket.md`, `collect_event_lookahead()` | **Proposed** in artefact 5. Not applied — owner approval required by that file's header |
| R1, R3, R14 | `pipeline/compliance_draft.py` `DRAFT_TEXT_PROMPT_TEMPLATE` | Spec written in artefact 3; **build is GL-10c, post-launch** |
| R10, R11, R12 | Shop Manager — section name, tagline, About, policies | Paste-ready in artefact 2; **owner executes** |
| R5, R6, R7, R9 | `assets/brand/` + `verify.py` | Decision above; **build is phase 7, Claude Code**, only on owner ratification |
| R15 | GL-6 / GL-21 scene authoring | **Routed.** Recorded here, built there |
| R4 | Roadmap — set/bundle products | **Filed as a finding.** §10 defers the build |
| R13 | GL-29 / GL-11 architecture note | **Flagged, unsolved, out of scope** |

## 5. Open contradiction the brief carries, surfaced rather than absorbed

**Brief §6.1 is stale.** It states that *"`DISCLOSURE_TEXT` in
`compliance_draft.py` currently carries [the written AI disclosure]"* and that
the new template spec "must keep it."

**It does not carry it.** `pipeline/compliance_draft.py` line 25 reads
`DISCLOSURE_TEXT = ""`, with a comment at line 8 recording its removal on
2026-08-06 by owner decision under GL-37 — the same decision CLAUDE.md records,
together with the reason it is safe (the structured "an AI generator" tick
happens at publish in the web editor) and the paired consequence (GL-29,
programmatic activation, is cancelled; `update_listing_state` stays
`# DELIBERATELY UNWIRED`).

The brief and CLAUDE.md were evidently written within hours of each other and
the brief lost the race. **Artefact 3 follows CLAUDE.md, not the brief**: the
listing-copy spec does *not* reintroduce a prose disclosure, and says why in the
spec itself. §6 point 2 — that **the About text should carry the AI-generation
statement plainly** — is unaffected and is honoured in artefact 2. If the prose
disclosure is ever reinstated, GL-29 must be reopened in the same change.

---

## 6. Verification pass (brief §8 phase 8)

Run 2026-08-07 over all five artefacts. Every claim re-checked; **six errors
found and fixed**, listed here rather than quietly corrected.

**Constraints re-checked, all clear.**

- **Nothing written to the live shop.** Every Etsy interaction this project made
  was a `GET`. The session was never signed in (shop pages rendered the signed-out
  "Sign in" header throughout). No form was submitted, no listing touched, no
  Shop Manager page opened.
- **No pipeline code changed.** `git status` shows `pipeline/compliance_draft.py`
  modified, but its mtime is 2026-08-06 and its diff is the GL-37
  `DISCLOSURE_TEXT` removal — pre-dating this project. GL-10b wrote only to
  `docs/` and `docs/data/`.
- **No hard constraint touched.** Nothing here proposes a change to the schnell
  rule, the 2 % crop budget, the scene-word rule, or prices. The one finding
  that lands near a hard constraint (R3/keyword-delta A2, room words) is
  explicitly routed *away* from `art_brief.py` for exactly that reason.
- **Every D-A claim is a count** (§2.4), and each is reproducible from
  `docs/data/gl10b-rubric.md`'s per-shop rows.

**Arithmetic re-derived from the raw rows.** Sales-per-listing recomputed for
all ten shops; the median is **29.85 ≈ 30**, as stated. Combined sales
**458,802**.

**Errors found and fixed:**

| # | Error | Fix |
| --- | --- | --- |
| 1 | Claimed the current Etsy banner spec was 1680 × 420, inferred from a competitor's CDN filename | Checked Etsy's own help page: it is **1600 × 400**. GL-10a was right. Wrong note kept in the data file with the correction beneath it (M3 above) |
| 2 | Proposed adding a `< 1 MB` assertion to `verify.py` | **It already exists**, line 45. Amendment 2 reduced to one new assertion |
| 3 | Combined sales stated as "462,000+" | Recomputed: **458,802** |
| 4 | Tagline character counts one short on all three options | Measured: **51 / 54 / 55**. Option C sits exactly on the cap — a further argument for A |
| 5 | The listing-copy spec's own worked title example **broke two of the rules printed beneath it** (17 words vs the 15-word ceiling; "Art" three times vs "no word more than twice") | Replaced with a 104-char, 15-word example. The failure is recorded in the spec, because a formula whose example violates it is worthless |
| 6 | `japandi` appeared as EVERGREEN in the keyword delta's Part A **and** as TREND in Part C; `geometric shapes wall art` mis-measured at 24 chars | `japandi` removed from Part A (evergreen total 28 → **27**); the term is **25** chars |

**Two further corrections, found 2026-08-08 by re-checking cited pages rather
than cited facts.** Both facts are right; both were attributed to the wrong page,
which is worse than it sounds — a reader who follows the citation and can't find
the claim is entitled to distrust everything else in the table.

| # | Error | Fix |
| --- | --- | --- |
| 7 | The **140-character listing-title cap** was cited to the SEO page. That page does not state it — it carries the "< 15 words" advice and the 50–60-character Google-display figure only | Re-sourced to [How to Create a Listing](https://help.etsy.com/hc/en-gb/articles/115015628707-How-to-Create-a-Listing), verified verbatim: *"A listing's title can be up to 140 characters long."* Applied in the listing-copy spec |
| 8 | R11 hedged correctly ("the page is silent, but every sampled shop's section links are…"), but the **checklist restated it flatly** as "free and reversible… the name is not in the URL" | Checklist item 2 re-hedged. The inference is strong — `?section_id=<numeric>` on 10 of 10 shops — but it is an observation, not documentation, and it now says so |

**Two limitations that are not errors but bound everything above**, restated so
they travel with the conclusions: competitors' **tags are unobservable** (M1),
so the keyword delta is built from title tokens; and the sales-vs-register null
result (R7) rests on **two confounded outliers** and supports only the claim
that restraint is not a handicap — not that it sells.

---

## Sources

- Live Etsy, 2026-08-06/07, via Claude in Chrome: search SERPs for `wall art
  print`, `botanical line art print`, `moon phase print`, `mid century modern
  wall art`, `minimalist line art poster`, `gallery wall set prints`; shop pages
  for TheWorldGallery, WoodSagePrints, LotusNurseryArt, MotherAndSunStudioUK,
  galerie61, BrightBlueStar, DIVANNO, OriginalLunarPhase, SimplyExtraJordanary,
  GateOfDesign
- Etsy Help Centre: [Requirements and Best Practices for Images in Your Etsy Shop](https://help.etsy.com/hc/en-gb/articles/115015663347-Requirements-and-Best-Practices-for-Images-in-Your-Etsy-Shop) ·
  [How to Create and Manage Shop Sections](https://help.etsy.com/hc/en-gb/articles/360000345048-How-to-Create-and-Manage-Shop-Sections) ·
  [SEO for Shop and Listing Pages](https://help.etsy.com/hc/en-gb/articles/115015663987-Search-Engine-Optimisation-SEO-for-Shop-and-Listing-Pages) ·
  [How to Use Tags to Get Found in Search](https://help.etsy.com/hc/en-gb/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search)
- Local: `docs/2026-08-06-gl10b-storefront-copy-brief.md`, `assets/brand/README.md`,
  `pipeline/compliance_draft.py`, `docs/safe_evergreen_bucket.md`, `CLAUDE.md`
- Raw coding: `docs/data/gl10b-rubric.md`, `docs/data/gl10b-keyword-surface.md`
