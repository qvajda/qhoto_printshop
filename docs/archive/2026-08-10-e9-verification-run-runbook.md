# E9 — the verification run (runbook)

**Type:** M + T · **Who:** owner · **Not a coding session** — nothing needs
writing, and a session that starts by reading code will start changing it.
**Cost:** one Replicate generation + one live Gelato create + one Etsy listing.
**Gated on:** GL-54 landing first (see §0).

Companion to `docs/2026-08-10-e2-live-reproduction-runbook.md`, which this
follows in shape deliberately.

---

## 0. ✅ GL-54 is done — this run is unblocked

Merged 2026-08-10 as PR #11 (`3a5cb72`), 744 green. **Seven loops now raise
instead of swallowing**, so a per-item failure anywhere in this run reaches
`_run_stage` and fires a Telegram notification instead of leaving a row that
reads "hasn't run yet".

**What that changes about how to read this run:** a stage completing silently
now genuinely means it worked. Before GL-54 it meant nothing. That is the
difference between this run and the 08-08 soak.

**Two deliberate exceptions to know about before you interpret a quiet
digest:** `digest` and `group_digest` raise but do **not** mark the row — the
group stays `pending_review` on purpose and the next cycle re-sends. So a
digest that fails and then arrives late is expected behaviour, not a defect.
Reasoning is in `DigestCycleError`'s docstring.

Alt texts are now inside `check_forbidden_terms` too, so §3 step 3's copy check
covers them.

## 1. What is actually being tested

Four claims, three of them currently unverified by anything:

| # | Claim | How it passes | How it could silently look like a pass |
|---|---|---|---|
| a | **GL-53** produces clean copy in production, not just in tests | a real draft with no forbidden term, written by the new prompt | the guardrail *starves* the candidate — 3 rejected attempts, `compliance_failed` — and you read "no bad copy" as success |
| b | **GL-52** — the repaired template no longer re-crops | fresh product's 10x24 measured at ~0.4167 **and the Design editor shows the whole flower and stem** | the aspect measures right and nobody opens the editor. **This is the exact failure that created GL-52.** |
| c | **§3c rider** — `get_product` echoes `fileUrl` per variant | `gelato_template_check.py <product_id>` prints a submitted file, not "not returned by the API" | the line prints the graceful-degradation message and gets skimmed |
| d | GL-7 DoD items (optional) | only carry what you will watch | all three, watched as a group, ticked as a group |

**(a) is the one nobody has thought about.** GL-53 was measured against 27
*existing* drafts, all of which it correctly rejects. It has never been observed
accepting one. A guardrail that rejects everything passes every test written so
far.

## 2. Pre-flight

1. `git log --oneline -1` → GL-54's merge. Confirm master, not a branch.
2. `python scripts/gelato_template_check.py` (no args, read-only). **Expect
   twelve `ok`.** If anything MISMATCHes, stop — the template moved again since
   the 2026-08-10 resync and the run is invalid before it starts.
3. ✅ `config/static_config.json`'s two repaired entries are committed
   (`0a4d908`): `55_5x7_crop.png`, `65_10x24_crop.png`. Nothing to do — kept
   here so the check is on the list rather than in someone's memory.
4. `python heartbeat_status.py` (or equivalent) against `db/qhoto.sqlite3` —
   know the last-run state before you start, so a stale row is not read as a
   fresh one.
5. Back up the DB with a dated name.
6. Note the current max `candidate_id` and max `listing_texts.candidate_id`.
   You need to know which rows this run created.

## 3. The run

1. **Enable the batch tasks.** They have been Disabled since the soak paused;
   GL-53's hold is lifted and GL-46/GL-47 are fixed, so the reasons for the
   hold are all discharged. Enable `qhoto-hourly` too — the review buttons need
   it.
2. Let one batch cycle produce a candidate. **Watch `research` first:** GL-47
   is live now, so an out-of-season event niche should be *held*, not
   generated. If the cycle produces nothing because everything was held or
   deduped, that is GL-47 working — re-run or wait, do not force it.
3. **At the compliance-draft stage, stop and read the draft.** This is claim
   (a) and it is five minutes. Check `listing_texts` for the new candidate:
   - no `AI` / `printable` / `digital download` / `gelato` / `production
     partner` anywhere in title, tags, description **or alt texts**;
   - and — separately, because the guardrail cannot check it — **is the copy
     any good?** A prompt rewritten to avoid words can produce bland copy. The
     validator has no opinion on that; you do.
   - If the candidate reached `compliance_failed` after 3 attempts, **that is
     claim (a) failing**, and it is a more important result than anything else
     in this run. Record the attempts and stop.
4. Approve through the Telegram digest as normal — primary group first, then
   the 5x7 and 10x24 follow-ups.
5. Let the publish stage fire the live Gelato create.

## 4. Verification — measurement *and* eyes, in that order

1. `PYTHONIOENCODING=utf-8 python scripts/gelato_template_check.py <product_id>`
   - 10x24 placed aspect ≈ **0.4167**, 5x7 ≈ **0.7143**.
   - **Read the submitted-file line** (claim c). If it says "not returned by the
     API for this variant", record that — the rider is then unverified, not
     broken, and it becomes a note on GL-52 rather than a tick.
2. **Open the Gelato Design editor and look at all six variants.** Specifically
   10x24 and 5x7: is the whole subject inside the printable area, top and
   bottom? **This step is not optional and it is not covered by step 1.**
   Screenshot each.
3. Etsy: confirm exactly **one** listing, six variants, prices 19/24/35/39/45/49
   EUR, and the patched title/tags/description are the clean ones.
4. Confirm no duplicate Gelato product (create-once).

## 5. Teardown

1. Set the batch tasks back to Disabled unless you intend to keep running.
2. **Decide candidate 49's listing `4553104678`** — it carries `AI Generated
   Art` and `Printable Download`. Once this run has produced a fresh product,
   49 is no longer needed as a GL-52 control. Delete it.
3. Delete or keep the E9 listing deliberately, and say which in the findings.
4. Write `docs/2026-08-10-e9-findings.md`: one section per claim (a)–(d), each
   ending in **pass / fail / unverified**. **"Unverified" is a legitimate and
   expected outcome for (c)** — do not let it round up to pass.

## 6. The standing warning, repeated because it has been earned twice

**A measurement that answers a narrower question than the one you care about is
not a pass, it is a scope statement.** GL-48's aspect check was blind to GL-52
by construction. GL-53's term list would have been blind to the very sentence it
was written for. Both were caught by a human looking at the actual artefact.
**Look at the print. Read the copy.**
