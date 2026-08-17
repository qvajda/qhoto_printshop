---
status: accepted
revisit-after: 2027-02-01
---

# The runtime is discrete scheduled functions, not a persistent agent loop

Twelve stages, one function each, on two cron cadences — an hourly Telegram poll
and a twice-daily batch. Not a long-running service, and explicitly not one agent
loop that reasons about the whole pipeline.

Chosen because each stage is then independently testable and independently
restartable, and because a crash in one stage cannot take the run with it.

**The cost, and it is real:** per-stage isolation made per-item failures
invisible at both levels — a `try/except: continue` inside a stage loop leaves
the row looking like it never ran, while the stage still reports success. GL-46
sat 8 of 8 candidates at `pending` overnight with nothing anywhere saying so. The
standing rule that pays for this decision: **a swallowed per-item exception must
always leave a state change behind**, and the stage must still fail once at the
end.

## Amendment, 2026-08-17 — the Telegram acknowledgement is exempt (GL-130)

**One seam is carved out: reading Telegram updates and acknowledging a tap may run
as an always-on long-poll listener. Everything else stays on cron.**

The decision above is about *stages*. It was silently also deciding the latency of
the owner's own button, and that is a different problem with a different clock. A
`callback_query_id` expires in seconds; a cron poll answers in minutes. Every
`answerCallbackQuery` this pipeline has ever sent for a real tap has been rejected
with `query is too old and response timeout expired` — GL-45 worked around that by
making the keyboard edit the acknowledgement instead of the toast, which is correct
but still only as fast as the next poll.

GL-130 is what the workaround costs. The Task Scheduler trigger reverted PT5M → PT1H
on 2026-08-12T13:06 and no tap gave feedback for five days; the button was reported
dead. The pipeline could not tell, because on a cron poll a slow tap and a lost tap
are the same observation. And the cursor is global: `getUpdates` hands an update to
exactly one reader, so **any** other reader — a diagnostic probe, a second checkout,
anything holding the token — silently consumes a decision, and 288 short-lived
invocations a day is 288 chances to race one.

A listener fixes both by construction: sub-second ack, so the toast works and a tap
looks like it landed; and one process owning the cursor for its lifetime instead of
288 windows a day where something else can take it.

**The boundary, and it is the whole point of the amendment.** The listener owns
exactly four things: `getUpdates`, the admin check, recording the decision, and the
acknowledgement (`answerCallbackQuery` + the keyboard edit). It **never** calls
Gelato or Etsy, never generates, never publishes. It writes the decision and goes
back to polling. Every slow, failure-prone stage stays a discrete scheduled function
where the reasoning above still holds in full — the ADR is narrowed, not reversed.

**What this decision buys, and what it costs.** It buys an owner-facing control that
responds like a control. It costs a process that must stay up, and a new failure mode
— a listener that dies silently stops every decision — which is why it needs the same
heartbeat treatment every other job has, and why the scheduled poll is **kept** as a
backstop rather than deleted: if the listener is down, taps are still collected late
rather than lost. Two readers of one cursor is exactly the hazard named above, so
they must never poll concurrently — the existing token lock (`lock.token_lock_path`)
is the mechanism, and the backstop must lose to a live listener.

Executed by issue #139.
