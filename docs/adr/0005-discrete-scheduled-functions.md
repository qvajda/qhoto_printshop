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
