# GL-45 — Telegram button taps silently dropped: investigation brief

**Filed:** 2026-08-09 · **Type:** R → C · **Blocker** · **Prerequisite:**
GL-38 step 2 (the canonical DB must be the worktree's — see below)

---

---

## 0. UPDATE 2026-08-09 — H1 eliminated, and the answer is probably H2

**`getWebhookInfo` returned:**

```json
{"ok":true,"result":{"url":"","has_custom_certificate":false,"pending_update_count":0}}
```

**H1 is dead, both halves.** `url` is empty, so no webhook is starving
`getUpdates`. And `allowed_updates` is **absent from the response**, which
means it has never been set — so the default set applies, and the default set
**includes `callback_query`**. Neither sub-hypothesis survives.

### The sharp part is `pending_update_count: 0`

Telegram retains an unconsumed update for **24 hours**. The 08-09 taps happened
today, and all three scheduled tasks have been **Disabled since GL-38**, so
nothing of ours has polled since. If those updates had merely gone unread,
they would still be queued right now.

**They are not queued. So something consumed them.** That converts H2 from
"the next hypothesis" into the remaining explanation.

### The `update_id` gaps confirm it retrospectively

`update_id` is sequential per bot. Reading the stored `raw_payload` of all 54
`telegram_events_log` rows in the promoted DB gives four gaps — **19 update_ids
that existed for this bot and never produced a row**:

| Gap | Missing ids | Count | Logged either side at |
|---|---|---|---|
| 361 → 364 | 362–363 | 2 | 2026-08-04 19:18 / 20:26 |
| 374 → 381 | 375–380 | 6 | 2026-08-08 07:32 / 10:00 |
| 382 → 391 | 383–390 | 8 | 2026-08-08 10:00 / 18:35 |
| 397 → 401 | 398–400 | 3 | 2026-08-08 19:24 / 19:30 |

The gaps cluster exactly on the reported drop windows. The §3 instrumentation
this brief asked for has, in effect, already run — the evidence was sitting in
`raw_payload` all along.

### The likely second consumer is the thing that was used to rule interference out

The soak findings record that 08-08's only manual runs were *"against throwaway
DB copies for the schema-guard/stall-predicate soak checks, not the real DB"*,
and cite that as ruling out the racing theory.

**It does the opposite, and this is the crux of the whole investigation:**

- The **Telegram cursor is per-bot-token and global.** One cursor, server-side.
- The **offset row is per-database-file.** `telegram_offset` lives in whichever
  SQLite file the process was pointed at.

So a `run_hourly.py` executed against a **throwaway copy** polls with *that
copy's* offset, receives the real pending updates, **confirms them — which
deletes them for every consumer** — and writes the results into the throwaway.
From the real database's point of view that is a perfect silent drop: no
processed row, no `discarded` row, and the update gone from Telegram's queue.

It explains every observation without remainder, including
`pending_update_count: 0` and including why a third tap "worked" (it landed in
a window with no throwaway run in flight).

**GL-38's framing of this hazard was too narrow.** It was written as *one
token, two trees*. It is **one token, any number of processes** — including
runs against disposable databases, test copies, and anything else that loads
`.env`. The lock cannot see any of them: it is keyed on the script's directory,
and a throwaway-DB run in the same tree takes the *same* lock, so even a
same-tree run is only serialised, never prevented from consuming.

### Two things this reframes, before anyone re-reads the finding

**(1) Part of the "7 taps, 3 landed" report is not a drop at all.** Groups 53,
55 and 59 (candidates 49, 55, 60) carry `decision='approved'` with
`status='pending_review'`. That is the **correct v4.12 intermediate state** — an
approved primary waits for its 5x7/10x24 decisions before anything publishes.
Those taps landed. The genuinely lost ones are the **secondary** groups
(76–81, and 84 for candidate 66), which carry `decision=NULL`. Diagnose from
`groups.decision`, not from the digest looking unchanged.

**(2) Runs do die mid-cycle, and there is separate evidence.** update_ids
`365`, `366` and `367` each appear **twice**, ten minutes apart, the second time
as `error: Gelato product …`. `set_telegram_offset` runs after the loop, so a
run killed during a long publish re-delivers what it already processed. That is
the *safe* direction of the same weakness, and it is worth fixing alongside —
but it is not the drop.

### Revised next actions

1. **Find the throwaway DB copies and grep their `telegram_events_log` for the
   19 missing `update_id`s.** They are not under `db/` (only the eight dated
   `.bak` files are, and none holds them). If they turn up there, **the case is
   closed with no pipeline bug at all** — the code is correct and the operating
   practice was wrong.
2. **Build the guard, regardless of whether step 1 confirms it.** A lock keyed
   on the **bot token** rather than on the script's directory, so any process
   using that token serialises against every other. Plus a **canonical-DB
   assertion**: record a database identity and refuse to poll Telegram from a
   file that is not the canonical one unless explicitly overridden. A test copy
   should be *unable* to eat production's updates.
3. **Ship the tap acknowledgement anyway** (§5 below). If the root cause is
   operational, the acknowledgement is the only thing that would have made it
   visible on day one instead of day three.
4. **Only if step 1 comes back empty** does H3's raw-`getUpdates`
   instrumentation become necessary.

**What this does to §4 below:** H1 is answered, H2 is promoted and sharpened,
H3 is now a fallback rather than a plan. The rest of the brief stands.

---

## 1. Problem

Owner taps on the inline Approve/Edit/Reject buttons do not reliably reach the
pipeline. They leave **no trace at all** — not a processed row, not a
`discarded` row — in `telegram_events_log`.

**Evidence, two independent occurrences:**

| Date | Taps made | Rows in `telegram_events_log` | Notes |
|---|---|---|---|
| 2026-08-08 | 7 primary groups (candidates 48, 49, 55, 57, 58, 59, 60) | 3 (48, 49, 55) | The other 4 were re-tapped; only the **third** attempt registered — one via a manual `run_hourly.py`, three via a second manual invocation |
| 2026-08-09 | 4 secondary-group reviews (candidates 49, 55, 60, 66) | 0 | **No manual runs anywhere near this window** |

The 08-09 recurrence is what makes this a defect rather than an anecdote: the
"a manual `run_hourly.py` raced the scheduled one" theory was the leading
explanation on 08-08, and 08-09 has no manual runs against the real DB to
blame. (The only manual runs that day were against throwaway DB copies for the
schema-guard and stall-predicate checks.)

**Do not re-derive the "they probably weren't actually tapped" explanation.**
The owner has directly contradicted it twice, and the second occurrence was
deliberately performed as a test.

## 2. Why this is blocker-class

A dropped **approve** is recoverable — it looks like an unreviewed group and
self-heals on a re-tap. A dropped **reject** is not: the group sits looking
undecided until `GROUP_REVIEW_STALL_DAYS` (14) ages it out, and under GL-22a
Q2 **a skipped size is a permanent forfeit** — recovering it needs a
from-scratch re-publish, because there is no API path to add a variant to an
existing Gelato product.

With live mode armed, that is the difference between a listing that ships what
the owner approved and one that ships what he never saw. Every other open
finding costs money or time; this one costs correctness.

## 3. What has already been ruled out

Code review of the callback path is **exhausted** and found no explanation.
Specifically confirmed:

- `set_telegram_offset` only advances past `update_id`s the loop actually
  iterated — it cannot skip an unprocessed update.
- `resolve_callback` returns a silent, unlogged `None` **only** for updates
  carrying no `callback_query` at all. A real button tap always carries one.
- Every other path logs an explicit row: wrong admin id, stale message match,
  processing exception. There is no code path that discards a real tap
  silently.

**Conclusion: the update never reached `resolve_callback`.** Either Telegram
never delivered it to `getUpdates`, or something outside the reviewed code
consumed it first. Do not spend the session re-reading `telegram_client.py` —
that ground is covered.

## 4. Hypotheses, in the order they should be tested

### H1 — A webhook is set on the bot token (cost: ~10 seconds)

**Test this first, before writing any instrumentation.**

```
GET https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

If `url` is non-empty, Telegram is delivering updates to that webhook and
`getUpdates` is starved. This explains **every** symptom without remainder:
zero trace (the update never enters our process), no `discarded` row, and the
apparent randomness (whichever consumer wins).

The same response also returns **`allowed_updates`**, which is worth reading
carefully even if `url` is empty. Telegram makes this list **sticky** — it
persists from whatever was last passed to `setWebhook` or `getUpdates`, across
restarts, until explicitly changed. `pipeline/telegram_client.get_updates`
sends only `timeout` and `offset` and **has never passed `allowed_updates`**,
so if that list was ever narrowed by anything — a tutorial snippet, an earlier
prototype, a third-party tool — the narrowing is still in force today and
`callback_query` may simply not be in it.

**If `allowed_updates` is anything other than empty/default, that is the bug.**
Fix: pass an explicit `allowed_updates=["message","callback_query"]` on every
`getUpdates` call, so the property is asserted by our code rather than
inherited from Telegram's memory of something we did not do.

### H2 — A second consumer of the same bot token (cost: ~10 minutes)

`getUpdates` has exactly **one cursor per bot token**. Any second poller eats
updates the first will never see, and acknowledges them.

Audit for:

- Stale **Windows Task Scheduler** entries pointing at
  `.claude/worktrees/gl7-cron-orchestrator/` (or any other worktree) after
  GL-38's re-point. There are **six other `agent-*` worktrees** in
  `.claude/worktrees/` — check each for a `run_hourly.py` and a `db/`.
- A dev shell or IDE run configuration left running.
- `run_m1_live_test.py` in the main checkout, which still exists and still
  works.

Note that GL-7's process lock **does not protect against this**: it is a file
lock at `<tree>/db/gl7.lock`, so two trees take two different locks and both
proceed. This is PRD §2 item 3's property being satisfied *within* a tree and
violated *between* trees.

### H3 — Something else (cost: a real session)

**Only if H1 and H2 both come back clean.** Then it becomes an instrumentation
job:

1. Log the **raw `getUpdates` response body, verbatim**, at the point
   `telegram_client.get_updates` returns and *before* `resolve_callback` sees
   it — to a file, not to the DB, so a DB-write failure cannot hide it.
2. Log the `offset` sent with each call and the `update_id` range received.
3. Reproduce: send a digest entry, tap it, and diff. **`update_id` is
   sequential per bot** — a gap in the received sequence proves Telegram
   delivered an update we never saw; no gap proves Telegram never sent it.

That single measurement discriminates "Telegram didn't send it" from "we lost
it", which is the fork the entire investigation currently cannot resolve.

## 5. A separate, real gap to fix in the same session

Inline buttons **never change appearance after a tap** — no
`answerCallbackQuery` toast, no `editMessageReplyMarkup` to grey out or mark
the chosen option.

This is **not the cause** — the DB evidence shows the update genuinely never
arrived, not that it merely looked unconfirmed — but it is why the defect went
unnoticed for two days, and it is why the owner could not tell a dropped tap
from a slow one. `telegram_client.answer_callback_query` **already exists**;
the work is calling it at the point the callback resolves, plus an
`editMessageReplyMarkup` (or an edited message caption) so the acknowledgement
survives the toast disappearing.

Ship this **regardless of what H1–H3 return.** If the root cause turns out to
be environmental and unfixable in our code, the acknowledgement is the only
thing standing between the owner and a silent forfeit.

## 6. Prerequisite, and it is not optional

**GL-38 step 2 must land first, and the worktree's database must be the
canonical one.**

The evidence this investigation depends on — the `telegram_events_log` rows,
the absent rows, and the `telegram_offset` cursor itself — lives in
`.claude/worktrees/gl7-cron-orchestrator/db/qhoto.sqlite3`. The root
`db/qhoto.sqlite3` is untouched since 2026-08-04 and has no `schema_version`
table. Investigating against the root DB would be investigating a database
that was not present for either occurrence.

Back both up before promoting either (CLAUDE.md §4 — destructive, show the
plan, wait for "proceed").

## 7. Definition of done

- [ ] `getWebhookInfo` run and its full response recorded in a findings doc —
      including `allowed_updates`, whatever it says.
- [ ] Token-consumer audit complete: every worktree and every scheduled task
      accounted for, with a written statement of what is and is not polling.
- [ ] Root cause **either identified with evidence, or explicitly recorded as
      not-yet-reproducible** with the instrumentation left in place. A second
      "code review found nothing" is not an acceptable outcome.
- [ ] `allowed_updates` passed explicitly on every `getUpdates` call,
      regardless of what the check returned — the property should be asserted
      by our code, not inherited.
- [ ] Tap acknowledgement shipped (`answerCallbackQuery` +
      `editMessageReplyMarkup`), with a test.
- [ ] Findings written to `docs/2026-08-09-gl45-findings.md`, and the GL-45
      row in the go-live plan updated with the answer rather than the search.

## 8. Scope boundaries

- **Not in scope:** any change to the digest's content, layout or button
  structure beyond acknowledgement. GL-31 (the stall reminder) and the
  post-launch Telegram UX polish item stay where they are.
- **Not in scope:** rewriting the polling model (webhook instead of
  `getUpdates`). If H1 finds a webhook, the fix is to *remove* it, not to
  adopt it — a webhook needs a public endpoint, which this deployment does not
  have.
- **No live Etsy or Gelato calls.** This is entirely a Telegram-side
  investigation; the pipeline stages stay untouched.

## 9. Tool fit (CLAUDE.md §7)

**Claude Code, in-repo.** It is instrumentation plus a small fix plus tests —
exactly the shape that wants a test-driven session in the repo. Cowork's role
is this brief and the reading of the findings.

**One exception worth noting:** step H1 is a single HTTP GET the owner can run
himself in a browser or with `curl` in under a minute, and it may end the
entire investigation. **Do that before opening a session at all** — there is
no point scoping a coding session for a problem that a webhook removal solves.
