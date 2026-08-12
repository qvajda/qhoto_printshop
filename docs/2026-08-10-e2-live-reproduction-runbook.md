# E2 — the GL-45 reproduction run (owner-manual runbook)

**Date written:** 2026-08-10 · **Depends on:** GL-45 on master (PR #8,
`c17b869`) · **Board rows discharged:** GL-45 (the test half), GL-38 Phase D
step 13, GL-48 §7 · **Type:** M (owner, manual). No code is written here.

---

## 0. What this run is for, stated precisely

GL-45 shipped a fix without proving a root cause. **That is two different
outcomes, and the run has to be able to tell them apart**, so decide in advance
what each result means:

| Observation | Reading |
|---|---|
| Tap → a row in `telegram_events_log`, and the raw log shows the same `update_id` | The path works. **Root cause still unproven** — nothing was dropped, so nothing was diagnosed. |
| Raw log shows the `update_id`, no row in `telegram_events_log` | **We lose it.** A pipeline bug, now localised to between the poll and the log — which is a handful of lines. |
| Tap → nothing in the raw log at all | **Telegram never sent it to us**, i.e. another consumer, or a delivery problem. This is the 08-09 morning window's shape, and it is the only reading that reopens the second-consumer hypothesis. |

Write down which of the three you got. **A green run is not a closed row** —
tick GL-45's *test* half and say plainly in the row that the root cause was
never reproduced.

The 08-09 morning window is the one thing still unexplained (offset
`475586404`, last logged event `2026-08-08T19:30`, i.e. the polls returned
nothing at all). If it does not recur, it stays unexplained; do not retro-fit
an explanation onto a clean run.

---

## 1. Pre-flight (5 min)

Everything is run from the repo root, `C:\Users\QVajd\Documents\claude\qhoto_printshop`.

1. **Confirm the deployment is the thing you think it is.**
   ```
   git -C . log --oneline -1        # expect 6ccd69f / c17b869 lineage, master
   python migrate.py db/qhoto.sqlite3 --check
   ```
   The second command must report `schema_version=8` (migration 8 is GL-45's
   `db_identity`) and must **not** create a file named `--check` in the repo
   root. If it does, GL-50's fix did not land — stop and say so.

2. **Confirm the DB identity blessing points at the canonical file.** GL-45's
   guard refuses to poll from a non-canonical database. It was blessed live on
   08-09 against `db/qhoto.sqlite3` in the repo root. If it refuses, the fix is
   `python migrate.py db/qhoto.sqlite3 --bless` — but **read why it refused
   first**; a refusal here is the guard doing its job and is itself information.

3. **Back up the database** before anything writes to it:
   `copy db\qhoto.sqlite3 db\qhoto.sqlite3.bak-2026-08-10-pre-e2`

4. **Scheduled tasks: `qhoto-hourly` ENABLED, `qhoto-batch-morning` and
   `qhoto-batch-evening` stay DISABLED.** Non-negotiable and not about
   Telegram: `run_batch` is what manufactures out-of-season candidates (GL-47)
   and swallows their failures (GL-46). Spending Replicate money re-observing
   two characterised defects in order to test a Telegram fix is exactly the
   trade the soak was paused to stop making.

5. **Confirm live flags.** Both are currently `FALSE`:
   ```
   GELATO_LIVE_MODE=FALSE
   ETSY_LIVE_MODE=FALSE
   ```
   **Phase A runs with them FALSE.** Do not flip them yet — see §3.

---

## 2. Phase A — the Telegram test, zero spend, zero live risk (~1 h wall clock, ~10 min of attention)

**Tap target: group 76 — candidate 49's 5x7 group, digest message id 286, sent
2026-08-08T19:29.** The old digest message is still in the chat and its
keyboard is still live; there is **no need to send a fresh digest**, and doing
so would only add a variable.

**Why that specific group, and why exactly one tap.** Candidate 49's primary
(group 53) is already `approved`; its 5x7 (76) and 10x24 (77) are both
undecided. Deciding **one** of them leaves the candidate short of the publish
gate, so `candidate_publish_plan` returns not-ready and **nothing reaches
Gelato or Etsy**. Deciding both would fire the create — in dry-run — and that
is the GL-49 trap: a dry-run publish writes `DRY_RUN_PRODUCT_ID` /
`DRY_RUN_ETSY_LISTING_ID` into a `published` row, `published` is terminal, only
`publish_failed` is ever retried, and the candidate is frozen as a stub
forever. **Candidates 44, 47 and 48 are already in that state. Do not make a
fourth.**

Group 76 is also one of the *specific* taps reported lost on 08-09, which makes
it the best available reproduction target rather than merely a safe one.

**Steps.**

1. Note the wall-clock time. Tap **Approve** on the group-76 digest message.
2. Watch the client for the two GL-45 behaviours, and note each independently:
   - a **toast** appears ("Got it — approve…") — this now fires *before*
     dispatch, so it should be near-instant rather than arriving minutes later;
   - the **keyboard is replaced** by a single non-tappable `✅ Approved`.
   The second one is `editMessageReplyMarkup`; it is best-effort and failures
   are only `print`ed, so absence is a finding, not a crash.
3. **Tap the `✅ Approved` label once.** Expected: a toast reading "Already
   decided", and **no second decision** — the label carries `noop:76`. This is
   the re-tap guard and it has never been exercised against a real client.
4. Wait for the top of the next hour (or run the task manually via Task
   Scheduler → Run — that is the same code path, and this is the run that
   consumes the tap).
5. Read the three sources, in this order:
   ```
   type logs\telegram_getupdates.log        # raw getUpdates bodies (GL-45, new)
   python heartbeat_status.py               # did the hourly run, and against which DB
   ```
   and then the database:
   ```
   python -c "import sqlite3;c=sqlite3.connect('db/qhoto.sqlite3');c.row_factory=sqlite3.Row;[print(dict(r)) for r in c.execute('select id,received_at,accepted,action_taken from telegram_events_log order by id desc limit 5')]"
   python -c "import sqlite3;c=sqlite3.connect('db/qhoto.sqlite3');c.row_factory=sqlite3.Row;[print(dict(r)) for r in c.execute('select id,decision,status,decided_at from groups where id=76')]"
   ```

**Pass conditions for Phase A:**

- the raw log contains an `update_id` for your tap, **and** `telegram_events_log`
  contains a matching accepted row with `action_taken='approve'`;
- `groups.id=76` reads `decision='approved'`;
- `heartbeats` shows a fresh `hourly` row **in `db/qhoto.sqlite3` at the repo
  root** — that is **GL-38's skipped Phase D step 13**, discharged here. The
  root tree has never executed a scheduled run; this is the first one, so treat
  it as a real check rather than a formality;
- the re-tap logged `ignored: already decided` and changed nothing;
- **no unexplained `update_id` gap** in the raw log. Non-callback updates are
  now logged too, so from this run onward a gap is proof rather than ambiguity.

**Free evidence worth collecting deliberately (see the plan's Track E note):**
if an E3 coding session is running in parallel, its pytest suite is hammering a
thousand throwaway databases — the exact second-consumer shape that was the
leading suspect. A clean Phase A while that is happening is real evidence the
`sha256(bot_token)` lock and the `db_identity` guard hold. Note whether E3 was
running, and when.

---

## 3. Phase B — the live Gelato create (GL-48 §7). Separate decision, separate go-ahead.

**Do not run Phase B on the same impulse as Phase A.** It creates a real Gelato
product and a real Etsy listing, and per CLAUDE.md §4 it wants an explicit
"proceed" of its own. It is also worth doing only if Phase A came back clean —
debugging a Telegram defect and a print-file defect in the same run is how the
first live run produced findings nobody could attribute.

**What it proves.** GL-48 established by measurement that the 10x24 letterbox
was a template-authoring defect, fixed the two stale `static_config.json`
placeholder names, and removed the dry-run crop gate. **The remaining claim is
unverified against a live create**, and GL-22a Q2 already established that
Gelato returns `200` for changes it silently drops — so this is verified by
measurement, not by status code.

**Steps.**

1. Refresh the Etsy token if needed (`python refresh_etsy_token.py`) — the
   access token is short-lived and a stale one fails at the patch, after the
   Gelato product exists.
2. Set `GELATO_LIVE_MODE=TRUE` and `ETSY_LIVE_MODE=TRUE`.
3. Tap **Approve** on **group 77** (candidate 49's 10x24, message id 289).
   Approving the 10x24 is what puts a 10x24 variant in the create payload — the
   whole point. That completes candidate 49's three groups, so the next hourly
   run fires the single create.
4. After the run, get the product id from `group_products` for candidate 49 and
   measure:
   ```
   python scripts/gelato_template_check.py <product_id>
   ```
   **Pass condition: the 10x24 variant's placed artwork aspect reads near
   `0.42`, not `0.65`.** 0.65 means the placeholder transform is still fitting
   an image authored for 0.684 — the original defect, unfixed.
5. Confirm exactly **one** Gelato product exists for candidate 49 (create-once)
   and that the Etsy listing carries six variants at the v4.11 §4 prices.
6. Set both flags back to `FALSE` when done.

**Leave candidate 42's listing `4549960823` alone** — it is GL-36's negative
control for the re-soak (E6), where the reconcile must flip 40 and 41 and leave
42 untouched.

**Not in scope here:** the structured "an AI generator" tick. Etsy's editor has
no draft-save, so ticking it activates the listing (GL-37). The listing created
by Phase B is a draft and should stay one until you are deliberately
publishing.

---

## 4. After the run — what to write down

Update three places, not one:

1. **`docs/2026-07-22-go-live-plan-of-attack.md`** — GL-45's row (which of the
   three readings in §0), GL-38's Phase D step 13, GL-48's §7. Each explicitly;
   free riders are the ones that get ticked unchecked.
2. **A findings note** if anything was dropped or unexplained. If everything was
   clean, a paragraph in the plan's session log is enough — do not manufacture a
   findings document for a clean run.
3. **The scheduled tasks** — put `qhoto-hourly` back to Disabled unless you are
   deliberately starting the re-soak (E6), and confirm the batch tasks are still
   Disabled.
