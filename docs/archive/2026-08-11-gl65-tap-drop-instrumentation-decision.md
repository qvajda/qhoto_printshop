# GL-65 — what gets captured the next time a tap goes missing

Not a fix, and deliberately not an investigation: there is no evidence left
from either occurrence (candidates 57-60 on 2026-08-08, candidates 80/84/87/88/90
on 2026-08-10). A raw no-offset `getUpdates` — bypassing this app's cursor
entirely — showed Telegram's own server-side queue held zero trace, which places
the loss at or before a queue we do not own. GL-45 tested the tap path clean and
GL-45's row stays true; this row keeps the question open. Reconciling the two
into one verdict is the wrong work.

## The tool-fit question first (CLAUDE.md §7)

More instrumentation on a queue we do not own buys very little. The pipeline can
only ever observe *absence*, and absence is exactly what it already observed. So
the useful move is not "log more", it is **shorten the interval between the tap
and the owner knowing whether it landed** — GL-45 established that several
minutes of silence after a tap is the *designed* behaviour (the toast and
keyboard collapse land when the hourly poll dispatches), and that design is
precisely what makes a real drop indistinguishable from a normal wait.

## Decision (recommended; owner confirms)

1. **Client-side capture, owner's phone.** Screen-record or screenshot the tap
   when approving a batch, until the next occurrence is caught. Zero code, and
   it is the only record that does not depend on the bot receiving anything.
2. **Shorten the feedback loop, not the log.** The cheapest version that changes
   the ergonomics: an `answerCallbackQuery` acknowledgement at receipt — a toast
   within seconds of the tap. A tap that produces no toast is then a *visible*
   drop at tap time instead of an invisible one discovered an hour later.
   Deliberately scoped as an acknowledgement, not a dispatch: it does not move
   the hourly poll's work earlier and does not touch `publish_primary_group`'s
   cursor handling.
3. **Not doing:** any retrospective log-diffing, any attempt to reproduce, any
   change to the offset/cursor logic. Nothing there is implicated and GL-45
   already tested it clean.

If taps keep vanishing at Telegram's delivery layer after (2), the answer is a
different confirmation channel, not more instrumentation — record that as the
next decision point rather than iterating here.

**Status:** decision recorded per the kickoff's "done when". Item 2 is a code
change and is *not* in the E9 small-items branch — it is filed, awaiting the
owner's yes.
