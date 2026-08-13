# GL-10b listing-copy template spec — the replacement for `DRAFT_TEXT_PROMPT_TEMPLATE`

**Artefact 3 of 5. Spec only.** The build is **GL-10c, post-launch and outside
GL-10** (brief §10). This file is written to be picked up cold by a later
Claude Code session; it assumes no conversational context.

**Target:** `pipeline/compliance_draft.py` — `DRAFT_TEXT_PROMPT_TEMPLATE` and
`build_draft_prompt()`.

---

## 0. What is there now, and what is wrong with it

```python
DRAFT_TEXT_PROMPT_TEMPLATE = (
    "You are writing an Etsy listing draft for an AI-generated botanical/minimalist wall "
    "art poster print, niche: {niche}. ..."
)
```

The **entire** brand and SEO strategy is that one hardcoded phrase. It has no
title formula, no tag strategy, no section awareness and no brand voice. Two
further problems the sweep exposed:

1. **`{niche}` is the only content input.** Everything the listing could say
   about *this specific design* — its colour family, its named art idiom, its
   ground — exists upstream in `art_brief.py` and is thrown away before the copy
   stage sees it.
2. **"botanical/minimalist" is hardcoded** into a shop that also generates
   celestial, mid-century, landscape and abstract work. Every listing is being
   told it is botanical.

### What is already right — do not "fix" these

- **`DISCLOSURE_TEXT = ""` and the prompt's explicit ban on an AI-disclosure or
  production-partner sentence are correct and load-bearing.** Brief §6.1 says
  the opposite; **the brief is stale and CLAUDE.md is authoritative** (GL-37,
  2026-08-06). The disclosure is structural: the "an AI generator" tick at
  publish, plus `production_partner_ids`. **Reintroducing prose disclosure means
  reopening GL-29 in the same change** — `etsy_client.update_listing_state` is
  `# DELIBERATELY UNWIRED` precisely because automated activation plus no prose
  disclosure would publish a listing with neither.
- **`validate_listing_text()` and the 3-attempt feedback retry loop.** LLMs
  don't obey character counts first time; the loop already handles it. The new
  template must keep every constraint expressible as a validation error so the
  feedback path keeps working.
- `MAX_TAGS = 13`, `MAX_TAG_LENGTH = 20`, `MAX_TITLE_LENGTH = 140` — all correct.
  Sources, since one of these was mis-cited in an earlier draft of the GL-10b
  reference material: the tag limits are on
  [How to Use Tags to Get Found in Search](https://help.etsy.com/hc/en-gb/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search);
  the **140-character title cap is on
  [How to Create a Listing](https://help.etsy.com/hc/en-gb/articles/115015628707-How-to-Create-a-Listing)**
  (*"A listing's title can be up to 140 characters long. Consider using less than
  15 words…"*), **not** on the SEO page — the SEO page carries the word-count
  advice and the 50–60-character Google-display figure only.

---

## 1. Title formula

### 1.1 The evidence

Coded from ten shops (`docs/data/gl10b-rubric.md`). Every ranking title is a
**stack of comma-separated keyword clauses with the subject front-loaded and no
brand name**. Observed patterns:

| Shop | Pattern | Example |
| --- | --- | --- |
| TheWorldGallery | 4 clauses, commas only, 138 chars | `Vintage Botanical Wall Art Set of 3, Cottagecore Floral Prints, Wildflower Botanical Poster Trio, Soft Earthy Nature Art for Home Decor` |
| LotusNurseryArt | 2 parts, colon | `Beige Botanical Line Art Print Set: Minimalist Floral Wall Decor` |
| MotherAndSunStudioUK | pipes + commas | `Vintage Botanical Floral Line Art Print \| Antique Wildflower Illustration, Cosy Cottagecore` |
| BrightBlueStar | **no separators at all** | `Bauhaus Print Orange Wall Art Bauhaus Poster Modern Art Minimalist Geometric Art Mid Century` |

Etsy's own guidance cuts against the longest of these: *"Consider using less
than 15 words"*, and *"search engines only show the first 50 to 60 characters
for a page title, so include the most important traits upfront, like your item's
colours, material, and size."*

### 1.2 The formula

**Five slots, comma-separated, subject first, brand name never.**

```
[1 Colour/tone] [2 Subject] [3 Idiom/style] Print,
[4 Medium synonym + form],
[5 Room or use],
[6 Aesthetic/mood phrase]
```

Worked example — **104 characters, 15 words**, no word repeated more than
twice, slots 1–3 inside the first 60:

> `Sage Green Fern Botanical Print, Minimalist Herbarium Wall Art, Bedroom
> Decor, Calm Neutral Nature Print`

*(An earlier draft of this example used "Line Art Print" in slot 3 and ran to
17 words with "Art" three times — i.e. it broke two of the rules directly
beneath it. Recorded because it is the exact failure mode the acceptance
criteria in §7 exist to catch, and because a formula whose own example
violates it is worthless.)*

**Rules:**

- **Slots 1–3 must fit inside the first 60 characters.** That is what Google
  shows and what Etsy's guidance names. Assert it.
- **Commas only.** No pipes, no colons, no em-dashes. Two of the four observed
  separator styles are worse (BrightBlueStar's run-on is unreadable;
  MotherAndSun mixes two). Commas are what the highest-volume shop uses and
  they degrade gracefully when truncated.
- **Target 100–135 chars and ≤ 15 words**, hard cap 140 chars
  (`MAX_TITLE_LENGTH`). The sample's ranking titles cluster at 90–140 chars;
  the 15-word ceiling is Etsy's own guidance and is the tighter of the two —
  **assert both**, because a 15-word title can still exceed 140 characters and
  a 140-character title can easily exceed 15 words.
- **No brand name, no shop name, no "Etsy".** 0/10 sampled titles carry one.
- **No size in the title.** Under v4.12 sizes are variants of one listing, so a
  size in the title would be wrong for five of the six variants. This is a
  change from the current code's behaviour, which v4.11 already began (title
  loses its per-size suffix) — the spec just makes it explicit.
- **No set quantity.** We do not sell sets yet (findings R4 is a roadmap item).
- **Never repeat a word more than twice.** WoodSagePrints says "Wall Prints"
  three times in one title; it ranks, but it reads as spam and Etsy's guidance
  asks for titles that *"sound natural."*

### 1.3 The input problem this creates

Slots **1 (colour)** and **3 (idiom)** are properties of the *artwork*, and the
copy stage cannot currently see them. They exist upstream:
`ART_BRIEF_PROMPT_TEMPLATE` already requires *"a NAMED art idiom (e.g.
'mid-century modern botanical', 'Bauhaus', 'Japanese woodblock', 'vintage
herbarium', 'Matisse cutout')"* and *"a ground: a warm cream, beige, or textured
background."*

**GL-10c's first task is therefore a plumbing task, not a prompt task:** thread
the art brief's **named idiom** and **dominant colour** through to
`build_draft_prompt()`. Two options, and the second is better:

| Option | How | Verdict |
| --- | --- | --- |
| A — parse them back out of the stored art brief text | regex/LLM over the brief prose | Fragile. The brief is free prose by design |
| **B — have `art_brief.py` emit them as structured fields** alongside the prose, and store them on the candidate | one added JSON key in the brief response, one migration | **Recommended.** The generator already *decides* both; it just doesn't record them |

Option B bumps `BRIEF_TEMPLATE_VERSION` (currently `"v2"` → `"v3"`), which is
what that constant is for.

**Fallback if the fields are absent** (old rows, or B not yet done): drop slots
1 and 3, run the formula on 2/4/5/6, and do **not** invent a colour. A wrong
colour word in a title is worse than a missing one — it is the first thing a
buyer checks against the image.

### 1.4 Slot 5 — room words, and the constraint that makes this delicate

Room words (`bedroom`, `kitchen`, `hallway`) are the highest-value discovered
keyword axis (findings R3, keyword delta A2) **and they are exactly what
`sanitize_niche()` and `SCENE_TOKENS` exist to strip.**

**The rule, stated so GL-10c cannot get it wrong:**

> **Room and placement words belong in the listing copy and never in the art
> brief.** They enter at the copy stage, from the *niche record*, and must not
> be written back into anything `generate.py` reads.

This is the same defect class that made the first live run print lifestyle
mockups as the artwork. `sanitize_niche()` runs on the way *into* the brief and
is unaffected — but if GL-10c adds a room field to the candidate row, it must be
a field the brief path does not consume.

---

## 2. Tag strategy

### 2.1 The hard constraint

**13 tags, 20 characters each** (Etsy, re-verified 2026-08-07). This
disqualifies a lot of the vocabulary the shop already uses: `mid century modern
wall art` (27), `continuous line illustration` (28), `minimalist landscape
print` (26), `celestial minimalist print` (26) **cannot be tags at all**
(findings R14).

**The length budget is a first-class generation constraint, not a post-hoc
trim.** The current code only *validates* length after the fact and feeds
failures back; that works, but it wastes retries on a problem the prompt can
prevent.

### 2.2 The 13 slots

Allocate by function, not by relevance ranking:

| Slots | Function | Example |
| --- | --- | --- |
| 1–3 | **Head**: subject + medium, the terms a buyer types | `botanical print`, `fern wall art`, `line art print` |
| 4–6 | **Long-tail**: colour + subject, idiom + medium | `sage green print`, `herbarium art`, `bauhaus poster` |
| 7–9 | **Room / placement** | `bedroom wall art`, `kitchen art`, `hallway decor` |
| 10–11 | **Aspirational / buyer-minded** — Etsy's guidance names this as tags' particular strength: *"great for aspirational or buyer-minded search terms (e.g. 'gift for her')"* | `housewarming gift`, `new home gift` |
| 12–13 | **Aesthetic / mood** | `calm neutral art`, `minimalist decor` |

**Rules:**

- **No tag may duplicate another tag's exact string**, and no more than **6** may
  repeat the title's head noun. Etsy asks for *"a diverse array of tags."*
- **Every tag ≤ 20 chars.** Generate against the budget; the validator stays as
  the backstop.
- **Where a good phrase is over 20 chars, put it in the title and its short head
  in tags.** `mid century modern wall art` → title carries it in full, tag reads
  `mid century art` (15).
- **Do not tag terms the pipeline cannot compete on** (findings R1): nothing
  personalised (`custom`, `personalised`, `name print`, `couple portrait`) and
  nothing dated (`2026`, `calendar`).

### 2.3 The tag-safe lexicon dependency

The clean version of this needs `docs/safe_evergreen_bucket.md` to record **a
tag-safe short form beside each long term** (keyword delta, part B3). That is a
schema change to the bucket file and it needs its own owner approval. **Until it
exists, GL-10c generates short forms at draft time and they will be
inconsistent between listings** — acceptable, and worth noting as a known
weakness rather than pretending otherwise.

---

## 3. Description skeleton

### 3.1 The evidence

TheWorldGallery's coded description — the highest-volume shop in the sample —
is **four blocks, ~90 words of prose**:

1. Benefit-led opening naming subject + tone — *"Bring timeless elegance to your
   space with this set of three vintage-style botanical prints…"*
2. Aesthetic/interior-context sentence — *"Perfect for a cottagecore interior or
   vintage-inspired home…"*
3. **Room-placement sentence** — *"Ideal for bedrooms, hallways, or cozy living
   spaces…"*
4. Postage/packaging block.

Materials sit in Etsy's **structured Highlights field**, not in prose. There is
no size chart in the text and no marketing padding.

### 3.2 The skeleton

**Six blocks. Blocks 1–3 are LLM-written per design; 4–6 are static boilerplate
and should be constants in the module, not model output.**

```
[1] Opening — one or two sentences. Names the subject, the named idiom, and the
    dominant colour. Benefit-led ("Bring…", "A calm…"), never spec-led.

[2] Interior context — one sentence. The aesthetic this belongs to.

[3] Placement — one sentence. Two or three rooms, named.

--- static from here down ---

[4] SIZES — the six sizes with cm and inches, and the note that they are
    standard frame sizes so a shop-bought frame fits. Sold unframed.

[5] PRINTING & DELIVERY — made to order, matte paper, weight, tube or flat,
    free delivery.

[6] A NOTE ON COLOUR — screens vary; matte paper reads softer than a backlit
    screen.
```

**Rules:**

- **Blocks 1–3: 80–110 words total.** The sample's ranking descriptions are
  short. Length is not a ranking factor and it costs the buyer attention.
- **No AI-disclosure or production-partner sentence.** §0. The current prompt
  already forbids this and the ban must survive the rewrite verbatim.
- **No size in blocks 1–3** — sizes are variants and block 4 owns them.
- **No discount or urgency language.** 3/10 sampled shops shout about discounts
  in the banner and their sales-per-listing is mid-table (findings R7). We have
  no discount to shout about and the prices are locked (SPEC_v4.11 §4).
- **Blocks 4–6 static.** They are identical for every listing, they contain
  facts, and an LLM regenerating them per listing is 100 % downside — drift,
  cost, and a chance of stating a wrong size.

---

## 4. Brand voice

Three lines, and they should go into the prompt as constraints rather than
adjectives:

1. **Plain and specific, not lyrical.** Name the plant, the idiom, the colour.
   "Bring timeless elegance to your space" is the register ceiling, not the
   floor.
2. **Calm, never urgent.** No exclamation marks, no "stunning", no "must-have",
   no emoji. This matches the A1 storefront and it is the one place the
   storefront's register reaches the listing.
3. **Honest about what it is.** The prose does not claim hand-drawing,
   hand-painting, or an artist's studio. It also does not apologise. The AI
   fact is disclosed structurally and in the About; the description simply must
   not contradict it.

**Assert 1 and 2 as a banned-token list** (`stunning`, `must-have`, `perfect
gift for anyone`, `!`, emoji, `hand-drawn`, `hand-painted`, `original
painting`). A banned list is testable; "write with a calm voice" is not.

---

## 5. Section awareness

The listing's section is `etsy_shop_section_id` from
`config/static_config.json`. Under v4.12 it is a **single value for every
generated listing**, and multi-section routing is deferred post-launch.

**So "section awareness" in GL-10c reduces to one thing: the copy must be
consistent with the section's name.** If the section is renamed to
`Unframed Art Prints` (storefront checklist item 2), then:

- **"unframed" should appear in the description** (block 4 already says it);
- **"framed" must never appear as a claim about the product** — it may appear
  only as "fits a standard shop-bought frame";
- the title's slot 4 medium synonym should prefer **"art print" / "wall art"**
  over "poster", matching both the section name and the sample's dominant
  vocabulary.

Real per-listing section awareness arrives only with multi-section routing.
**Do not build for it now.**

---

## 6. Alt texts — unchanged, with one addition

The current prompt's alt-text requirement is sound: one per gallery image, in
order, distinguishing a flat print shot from a lifestyle/room shot. Keep it.

**Add:** alt text is a genuine accessibility surface, so it should describe the
*image*, not repeat the title's keywords. `"Fern line art print in a sage green
frame on a cream bedroom wall"` — not `"botanical print bedroom wall art
minimalist"`.

---

## 7. Acceptance criteria for GL-10c

- [ ] Title matches the five-slot formula; slots 1–3 within the first 60 chars;
      commas only; **≤ 140 chars AND ≤ 15 words**; no brand name; no size;
      no repeated word > 2×.
- [ ] 13 tags, all ≤ 20 chars, allocated across the five functional bands, no
      duplicates, ≤ 6 sharing the title's head noun.
- [ ] Description has six blocks; 1–3 are generated and total 80–110 words;
      4–6 are module constants.
- [ ] Banned-token list enforced and unit-tested.
- [ ] `DISCLOSURE_TEXT` still `""`; no prose AI or production-partner sentence.
      **A test asserts this** — it is the tripwire that keeps GL-29's
      cancellation coherent.
- [ ] The 3-attempt validation-feedback retry loop still works: every new
      constraint above raises a `ValueError` that reads as actionable feedback.
- [ ] `"botanical/minimalist"` no longer hardcoded in the template.
- [ ] Colour and idiom threaded from `art_brief.py` (option B), with the
      graceful fallback of §1.3 when absent.

## 8. Explicitly out of scope for GL-10c

- **Multi-section routing** (same post-launch item, but a separate change).
- **The keyword delta.** Applying it edits `docs/safe_evergreen_bucket.md` and
  `collect_event_lookahead()`, which changes what the pipeline *makes*. Own
  approval, own change.
- **Set/bundle copy.** We don't sell sets (findings R4).
- **Anything touching prices.** SPEC_v4.11 §4, locked.
- **The listing URL slug problem** (findings R13). Etsy freezes the slug at the
  title Gelato first published with, and our patched title never reaches it.
  Real, bounded to Google SEO, and an architecture question for GL-29/GL-11 —
  **not** something a better title formula can fix.

---

## Sources

`docs/2026-08-07-gl10b-findings.md` (R1, R3, R4, R13, R14) ·
`docs/data/gl10b-rubric.md` (title patterns, description skeleton, Layer 2) ·
Etsy Help: [SEO for Shop and Listing Pages](https://help.etsy.com/hc/en-gb/articles/115015663987-Search-Engine-Optimisation-SEO-for-Shop-and-Listing-Pages),
[How to Use Tags to Get Found in Search](https://help.etsy.com/hc/en-gb/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search) ·
Code: `pipeline/compliance_draft.py`, `pipeline/art_brief.py` ·
`CLAUDE.md` (GL-37 block)
