# GL-53 kickoff — the listing-copy guardrail (E7)

**Type:** C (coding) · **Tool:** Claude Code, in-repo · **Live API calls:** none
· **Size:** one short session · **PRD:** not required (CLAUDE.md §2 — no external
system touched, well under one sitting; this document is the sign-off artefact)

Read `docs/2026-07-22-go-live-plan-of-attack.md` row **GL-53** first. This
kickoff is the how; the row is the why, and the row is authoritative if they
disagree.

---

## 0. The one-sentence problem

`compliance_draft` asks a language model not to write certain things, and
nothing checks whether it complied — so three shipped decisions have been
resting on a preference rather than a control, and all three are being
violated in production data today.

## 1. The evidence, so the session does not re-derive it

Audit of all 27 rows in `listing_texts` on the canonical DB
(`db/qhoto.sqlite3`), 2026-08-10:

| Class | Count | What it looks like |
|---|---|---|
| (a) prose AI disclosure in `description` | **27 / 27** | *"This design was created using AI image generation from the seller's own prompts, then selected, edited, and prepared for print by the seller."* |
| (b) AI disclosure in `title` or `tags` | **10 / 27** | `…, AI Generated Art, Modern Home Decor` in the title; `"AI generated art"` occupying one of thirteen tag slots |
| (c) digital-download wording for a physical product | **25 / 27** | `Printable Download`, `Instant Digital Download`, `printable wall art`, `printable art` |

**(a) includes drafts written on 2026-08-08 and 2026-08-09** — i.e. *after*
GL-37 set `DISCLOSURE_TEXT = ""` on 08-06. Emptying the constant removed our
sentence. It did not remove the behaviour.

**Reproduce it in one command** (do this first, to confirm the audit against
whatever the DB holds when the session runs):

```bash
python - <<'EOF'
import sqlite3, re, json
c = sqlite3.connect('db/qhoto.sqlite3')
rows = list(c.execute('select candidate_id,title,tags,description from listing_texts'))
ai   = re.compile(r'\bAI\b|artificial intelligence', re.I)
digi = re.compile(r'printable|digital download|instant download', re.I)
print('total', len(rows))
print('(a) desc AI  ', sum(1 for r in rows if ai.search(r[3] or '')))
print('(b) title/tag', sum(1 for r in rows if ai.search((r[1] or '') + (r[2] or ''))))
print('(c) digital  ', sum(1 for r in rows if digi.search((r[1] or '') + (r[2] or ''))))
EOF
```

## 2. Why (c) is the most serious, and why it is not a disclosure question

(a) and (b) are compliance drift against a decision we made. **(c) is a listing
that advertises a product the shop does not sell.** Every size ships as a
physical Gelato-printed poster, `when_made: "made_to_order"`,
`is_supply: false`. A title promising `Instant Digital Download` reaches a
buyer complaint long before it reaches Etsy's attention, and it is the kind of
mismatch that a shop with no order history cannot absorb.

Nobody was looking for (c). It turned up because the audit for (a) read the
whole column. Worth noting in the session's findings: **the cheapest thing that
happened this week was reading the actual data rather than the field we were
asked about.**

## 3. Scope — two halves, one commit, and neither is sufficient alone

### 3a. The prompt (the cheap half)

`pipeline/compliance_draft.py`, `DRAFT_TEXT_PROMPT_TEMPLATE`.

- **Remove "AI-generated" from the framing.** The template's first line reads
  *"You are writing an Etsy listing draft for an AI-generated botanical/
  minimalist wall art poster print…"* and a later line asks the model not to
  mention AI. The opening hands it the vocabulary; the instruction asks it not
  to use the word it was just given. Describe the artwork without the
  provenance — the provenance is not the model's business at draft time.
- **State the product positively and physically**: a made-to-order poster,
  printed on premium matte paper and shipped, *not* a digital file, *not* a
  printable, *not* a download. A negative instruction alone ("do not say
  printable") is weaker than a positive frame plus the negative.
- Keep the existing "no AI-disclosure or production-partner sentence in the
  description" instruction. It is not doing the work, but it costs nothing and
  it documents intent at the call site.

### 3b. The assertion (the half that actually matters)

`validate_listing_text` currently checks title length, tag count and tag
length. Extend it — or add a sibling it calls — to reject a draft carrying a
forbidden term in **title, tags, or description**.

Requirements:

- **Fails loud.** Raise, with the offending term and the field named, in the
  same shape as the existing `ValueError`s. Do not sanitise, do not strip, do
  not silently rewrite: a draft that violated the rule is a draft whose whole
  framing came out wrong, and a scrubbed title is worse copy than a regenerated
  one.
- **Feeds the existing retry.** `generate_draft_text` already takes
  `retry_feedback`, and `run_compliance_draft_cycle` already retries with it
  (around line 180 — read it before assuming). The natural behaviour is:
  validation fails → the failure message becomes the retry feedback → the model
  gets one or two more attempts → then the candidate fails with a reason.
  **Do not build a new retry mechanism**; wire into the one that exists.
- **Per CLAUDE.md's swallowed-exception rule (GL-46, added this week):** if a
  candidate exhausts its attempts, the row must carry a status *and a reason*,
  and the stage must still fail once at the end of the loop rather than
  `continue`-ing silently. Check whether `compliance_draft`'s loop has the same
  shape GL-46 just fixed in `generate` — **if it does, that is a second
  instance of a rule we just wrote down, and it should be fixed here rather
  than filed.**
- **The term list lives next to GL-37's comment block**, not in a config file.
  It is short, it is load-bearing, and its correctness depends on the reasoning
  in that comment. Give it a comment that says: *this list is the mechanism
  that keeps GL-37's decision true; if it is emptied, the decision is
  unenforced again.*

Starting list (extend if the audit turns up more; keep it case-insensitive and
substring-based, and prefer over-matching to under-matching since a false
positive costs one regeneration):

- AI provenance: `ai generated`, `ai-generated`, `ai art`, `artificial
  intelligence`, `midjourney`, `dall-e`, `stable diffusion`, `generated with ai`
- Digital-product wording: `printable`, `digital download`, `instant download`,
  `instant digital`, `digital file`, `pdf download`, `jpg download`,
  `svg`, `print at home`

**Judgement call the session must make and record, not paper over:** a bare
`\bAI\b` regex over the description will fire on legitimate prose. Decide
whether the description gets the same list as title/tags or a narrower one, and
write the reasoning beside the code. Over-strict on title and tags is cheap
(regenerate); over-strict on a 200-word description could loop. **If the two
need different lists, that is a fine answer — just say so in the comment.**

### 3c. The rider from GL-52 (small, related, do it here)

GL-52's evidence shows the pipeline has **no way to observe a template-side
re-crop**: `scripts/gelato_template_check.py` measures the placed *rectangle*,
and nothing ever compares the submitted file's content to what the template
does with it. That is the same failure shape as GL-53 — a decision with no
assertion behind it.

**Scope here is deliberately minimal: extend `gelato_template_check.py` to
print, per variant, the submitted crop's own dimensions and aspect alongside
the measured placed aspect**, so a mismatch between "what we sent" and "what
the template placed" is visible in one line of output instead of requiring a
human to open the Design editor. **Do not attempt to detect the crop-within-rect
defect itself** — that needs the dashboard answer first (see the GL-52
kickoff). This is an observability rider, not a fix.

If this makes the session long, **drop 3c and say so**. 3a and 3b are the
blocker; 3c is opportunistic.

## 4. Explicitly out of scope

- **GL-10c**, the full listing-copy template build (five title slots, tag
  strategy, the 20-char constraint). Spec exists:
  `docs/2026-08-07-gl10b-listing-copy-spec.md`. It stays post-launch. GL-53 is
  the guardrail subset and **does not consume it** — do not start implementing
  the template because the file is open.
- **Backfilling the 27 existing drafts.** They are unpublished except candidate
  49 (owner action, below). Regenerating them costs Anthropic calls for rows
  that may never publish. If the session wants to argue for it, argue in the
  findings; do not do it.
- **Re-enabling either batch task.** They stay Disabled until this lands.

## 5. Definition of done

1. Both halves of §3 in one commit; the prompt change alone is not done.
2. Tests: at least one per drift class (a/b/c) asserting the validator rejects,
   one asserting a clean draft passes, one asserting the retry path receives
   the failure as feedback. Existing `tests/test_compliance_draft.py` is the
   home.
3. Full suite green (`733` was the count after PR #9 — expect it to grow).
4. The GL-37 comment block in `compliance_draft.py` cross-references the new
   check by name, and the new check's comment cross-references GL-37. **Both
   directions**, because the whole failure was that one end of that decision
   moved and the other end did not know.
5. A short findings note if anything surprised you — especially if the
   `compliance_draft` loop turned out to have the GL-46 shape.
6. PR opened; do not merge without the owner.

## 6. Owner action, separate from this session

Candidate 49's live Etsy listing **`4553104678`** carries a non-compliant title
today (`…, AI Generated Art, …, Printable Download`). Decide **delete or
retitle**. It is a test listing so deleting is the cheap option — **but check
first that it is not wanted as a control for GL-52**, which is looking at the
same product's 10x24 variant.
