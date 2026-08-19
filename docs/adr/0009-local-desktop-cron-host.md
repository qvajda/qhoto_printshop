---
status: accepted
revisit-after: 2026-10-01
---

# The pipeline's cron runs on the local desktop, with a pre-committed fork

Scheduled tasks run on the owner's Windows desktop rather than on an always-on
host. Chosen for cost (zero) and for credential locality — the pipeline's Etsy,
Gelato and Replicate keys never leave the machine.

**The fork was named before it was needed, not after:** if the desktop fails on
wake/sleep or reliability, move to a cheap always-on host identified in advance.
Signed off 2026-08-05 on that basis; the fallback stays live rather than closed
out.

**Short `revisit-after` on purpose.** This is the ADR most likely to be wrong: it
is the only one whose failure mode is silent (a machine asleep produces no error,
just no run).

## Amended 2026-08-19 — the host now serves two repo roots

Phase 8 extracted the substrate into `qvajda/qops` (ADR-0023), so this one
machine runs scheduled work for **two** checkouts:

| root | what runs there |
|---|---|
| `…\claude\qhoto_printshop` | the pipeline's two cron cadences (ADR-0005), the Telegram listener, and its own `qops-pickup-loop` |
| `…\claude\qops` | the substrate's `qops-pickup-loop`, and nothing else |

**A scheduled task must name the root it operates on.** It used to be able to
derive one — `scripts/qops_pickup.py` rooted itself off `Path(__file__)` — and
that stopped being true when the script became part of an installable package,
where `__file__` is site-packages. The picker takes `--root` for exactly this.

This is not a hypothetical. The registered task carried an empty
`WorkingDirectory` and would have resolved its root from wherever the scheduler
started it; it was disabled, so nothing broke, and the breakage would have
stayed invisible until someone enabled it (#176). The registration is a machine
fact held nowhere in either repo, which is #124's complaint and is now doubled.

**The silent-failure warning in the paragraph above applies twice over.** A
machine asleep produces no error and no run; a machine awake with one task
pointed at the wrong root produces no error either, and a picker reporting
"nothing eligible" is indistinguishable from a healthy idle queue.
