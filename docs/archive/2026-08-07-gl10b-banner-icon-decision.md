# GL-10b banner/icon decision — D-A resolved, and the phase 7 handoff

**Artefact 4 of 5.** Decided 2026-08-07 from the counts in
`docs/data/gl10b-rubric.md`; **ratified by the owner the same day**, all three
questions as recommended.

**This file is deliberately self-contained.** Brief §12 puts phase 7 (the
rebuild) in Claude Code, and says the handoff is safe *"because phase 7's input
is a decision document — D-A level, chosen treatment, target values — not
accumulated conversational context."* That is this file. Nothing below assumes
the Cowork session it came from.

---

## 1. The three decisions

| | Decision | Ratified |
| --- | --- | --- |
| **D-A** | **A1 — to the letter.** Qrchard's system applied as GL-10a did: Ink/Charcoal ground, Bone, Pine `#23402F`, Fraunces + Inter, badge geometry | 2026-08-07 |
| **Banner / icon** | **Retire the live pair. Keep GL-10a's icon unchanged. Adjust GL-10a's banner.** | 2026-08-07 |
| **Nano Banana Pro** | **Role C — concept exploration only.** Nothing generated ships | 2026-08-07 |

## 2. Why A1 — the counts, in one place

§2.4 required every D-A claim to be a count, never an impression. These are the
counts, n = 10 shops, all reached by being behind a ranking listing.

| Claim | Count | Reading |
| --- | --- | --- |
| Field ground is light | **10 / 10 light, 0 / 10 dark** | Uniform field. Per §2.4, *"'the mean is bright' is not evidence that bright wins"* — it is evidence the field is undifferentiated |
| Register correlates with sales | **No** | Sales/listing: galerie61 (calmest) **237**, OriginalLunarPhase (silent) **≈7,500**, GateOfDesign (`75% OFF`) **68**, MotherAndSunStudioUK (`30% OFF`) **25**, TheWorldGallery (biggest shop) **15**. Calm and shouty interleave |
| Type-led banners are the norm | **1 / 10** | The only type-led shop is galerie61 |
| Banners carrying imagery carry *product* imagery | **8 / 10** | Framed prints, in rooms or on shelves |
| Wordmark-led icons survive 74 px | **0 / 6** | vs **4 / 4** for symbol-led. No exceptions in either cell |

**The decisive one is row 2**, and §2.4 wrote its consequence before the data
existed: *"register may simply not correlate with sales, in which case D-A
resolves to A1 by default and the differentiation argument for a dark, calm
storefront in a bright field gets stronger, not weaker."*

**Both outliers are confounded and the argument does not lean on them.**
galerie61 sells public-domain artist reproductions (Picasso, Monet, Matisse) —
its 237 is a demand story about Picasso, not a branding story. OriginalLunarPhase
sells one dated product with 13 years of reviews. Together they support only the
weaker, sufficient claim: **restraint is not a handicap.**

**What would have changed the answer, and why it could not be built.** A2/A3
needed a count showing register moving sales — light-ground shops out-selling
dark ones per listing. **There are no dark-ground shops in the sample at all**,
so that count is unconstructible from this data, and moving away from Qrchard
would have had to be argued from taste. §2.4 forbids that.

**The §2.1 invariant is satisfied, and nameably.** At A1 the lineage cue is the
badge itself: the Q-bowl and ring construction shared with Qrchard, differing
only in the tail — Qrchard is a Q masquerading as an **O**, Qhoto a Q
masquerading as a **P** (`assets/brand/badge.py` docstring). Someone who has
seen the parent catches it because it is the same ring, the same blade width,
the same dot size family.

## 3. The icon — keep GL-10a's, unchanged

`assets/brand/qhoto-shop-icon-500.png` — Bone badge on a **Pine ground**,
symbol only, no wordmark, 500 × 500, 12 KB, **8.7:1** contrast.

**The sweep independently confirmed a decision GL-10a had already made by
measurement.** GL-10a put the accent in the *ground* rather than the mark
because Pine-on-Ink measures 1.6:1 and collapses to an "O" below 40 px. This
sweep, judging ten competitor icons at true avatar size, found:

- **every** legible icon is symbol-led (LotusNurseryArt's bear, galerie61's
  `g61` monogram, BrightBlueStar's star, OriginalLunarPhase's moon) — 4/4;
- **every** illegible icon is wordmark-led — 6/6, including two Star Sellers
  with 20k+ sales.

**The live `shop_icon.jpg` is squarely in the 0/6 cell**: a monogram stacked
over a "Qhoto-Art" wordmark occupying the lower half.

**Action: upload `qhoto-shop-icon-500.png`. No rebuild. No code change.**

## 4. The banner — adjust, don't rebuild

### 4.1 What is wrong with the live one (four structural failures, measured)

`assets/brand/etsy-banner.png`, measured locally: **1600 × 896, 1,497.5 KB.**

1. **Promise mismatch.** Depicts framed *figurative portrait* works; the
   pipeline generates botanical / minimalist / celestial / abstract. The banner
   advertises a product line the shop does not sell.
2. **Visible generation artifact** — one framed poster carries garbled lettering
   ("O E M Y A I T"), in the largest brand surface on the page.
3. **1,497.5 KB** against Etsy's own *"Images larger than 1MB in file size may
   not finish uploading."*
4. **1600 × 896 matches no documented Etsy format** — not big (1600 × 400), not
   mini (1600 × 213), not carousel (1200 × 300), not collage. Etsy crops it and
   we do not control where.

None of these is aesthetic. All four survive the §2 filter regardless of D-A.

### 4.2 What changes in GL-10a's banner, and what does not

**Unchanged — this is why it is an adjustment inside A1 and not a move to A2:**
the Ink ground, Pine `#23402F`, Bone, Fraunces + Inter, the badge geometry, the
wordmark lockup, and every palette and geometry constant in `verify.py`.

**Changed — one thing.** The banner gains **a band of product imagery
composited from existing mockup renders**: real QhotoArt prints, in the existing
hand-authored scenes, sitting on the Ink ground beside the lockup.

**Why, in counts.** Type-led is a **1/10** minority treatment and the one shop
running it is confounded (§2). **8/10** carry framed-print imagery. And it
fixes failure 1 at its root: a banner built from actual listings cannot promise
a product line the shop does not sell.

**Why composited rather than generated.** The imagery is mockup renders. We
already produce those deterministically, at known crop, through
`pipeline/mockup_render.py` and the hand-authored scene bundles. A generative
model cannot hold an exact palette value, cannot reproduce a measured mark, and
cannot be regenerated identically later — the durable loss that halts role B,
and the reason role A is unnecessary here.

### 4.3 Target values for phase 7

| Property | Value | Source |
| --- | --- | --- |
| Big banner | **1600 × 400** | Etsy help, *Requirements and Best Practices for Images* |
| Mini banner (if the mini layout is used) | 1600 × 213 | same |
| Icon / logo | 500 × 500 | same |
| File size | **< 1 MB** | same, and **already asserted** by `verify.py` line 45 |
| Colour | **no alpha channel** | Etsy: *"transparent .png files are not supported… the transparent parts will appear black"* |
| Ground | Ink / Charcoal | Qrchard sheet, unchanged |
| Accent | Pine `#23402F` | GL-10a D1, unchanged |
| Badge geometry | `badge.GEOM["qhoto"] = (94.5, -0.15, 0.1625, 1.76, 1.575, 0.1815, -0.58)` | GL-10a D3, unchanged |
| Wordmark string | see §4.4 | Q8 |
| Imagery band | composited mockup renders of published listings | this decision |

**`verify.py` changes — one, not two.** I originally proposed two new
assertions; on reading the file, **the < 1 MB check already exists at line 45**,
so only one is new:

- **New:** assert **no alpha channel** on every emitted asset. Etsy renders
  transparency as black, and nothing currently catches it.
- **Extend, not replace:** the existing safe-zone assertions (lines 82–88 —
  content within 200–1400 px, optically centred at 800 ± 6, vertical 20–380)
  are written for a full-width type lockup. **The imagery band will move the
  lockup off centre**, so those assertions need re-parameterising to the new
  composition rather than deleting. **Losing the verifier is the actual risk of
  this change** (brief §7.4); the count of assertions should go up, not down.

### 4.4 The wordmark string — an open sub-decision, deliberately not settled here

Three spellings exist in the wild: the registered shop is **`QhotoArt`** (Q8),
GL-10a's wordmark sets **"Qhoto Art"**, the live icon reads **"Qhoto-Art"**.

**All copy uses `QhotoArt`** — About, policies, listing titles, tagline —
because that is what a buyer sees in the shop URL and the search row. That part
is settled and is applied in artefact 2.

**Whether the *wordmark* sets it as one word, two, or hyphenated is a design
question under D-A and may differ from the registered string.** GL-10a chose
"Qhoto Art" for the letterspacing; nothing in this sweep bears on it. **Left to
phase 7 to decide against the actual lockup**, and flagged so it is not
silently inherited.

## 5. Nano Banana Pro — role C, and the rule that produced it

§7.3's decision rule applied mechanically:

| Role | Trigger | Met? |
| --- | --- | --- |
| **A** — ground/texture plate | imagery-led or photographic in a clear majority **and** the imagery is atmospheric rather than product | **No.** First clause passes (8/10). **Second fails** — all eight are framed product in styled rooms. A mockup, not a texture plate |
| **B** — full generated banner | banners photographic and type-light such that a composited wordmark would read as pasted-on | **No**, and it halts by owner decision (Q5) regardless |
| **C** — concept exploration only | banners predominantly type-led, **or the field too varied to read a signal** | **Yes.** The field splits 4 imagery-only / 5 hybrid / 1 type-led — §7.3's own definition of too varied |

C is reached twice over: by A's second clause failing, and by the default rule
for a split signal. **Nothing generated ships.** SynthID and the 4:1 geometry-card
problem are moot at role C and are recorded here only so the reasoning is not
re-derived if the question reopens.

## 6. Sequencing — and the Etsy-Plus constraint on anything more ambitious

**Upload is manual, in Shop Manager.** Icon and banner are not API writes, so
nothing publishes without the owner doing it. Both replace the live off-system
pair.

**Do not read the sample's panelled banners as a target.** Etsy's own help page:
*"The carousel and collage banners are only available to sellers subscribed to
Etsy Plus."* Five of the ten sampled shops run one. **QhotoArt on the free tier
has exactly one option — a single static 1600 × 400 big banner** — so the honest
comparison set is the four imagery-only shops plus galerie61, and any future
"do what BrightBlueStar does" suggestion is covertly a recommendation to buy
Etsy Plus.

## 7. Definition of done for phase 7

- New banner emitted by `build_final.py`, 1600 × 400, no alpha, < 1 MB.
- `verify.py` passes with **more** assertions than it had, not fewer:
  existing palette/geometry/size checks intact, safe zones re-parameterised to
  the new composition, plus the new no-alpha check.
- Icon untouched and still passing.
- Owner uploads both in Shop Manager, replacing `etsy-banner.png` and
  `shop_icon.jpg`.
- `assets/brand/README.md` updated: the live pair is retired, and the reason
  (§4.1's four failures) recorded so it is not resurrected.
