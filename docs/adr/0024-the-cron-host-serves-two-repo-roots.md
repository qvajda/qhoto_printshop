---
status: accepted
revisit-after: 2027-03-01
amends: 0005
---

# The cron host serves two repo roots, so every scheduled task names the root it operates on

**Date:** 2026-08-19 · **Recorded here:** 2026-09-28

## Why this is here and not in `CADR-0002`

This text was written as an amendment *inside*
`docs/adr/consumer/CADR-0002-local-desktop-cron-host.md` during the
`v0.2.0 → v0.3.1` pin bump (db4b8d0). That file is a **rendering** — it comes
from qops's templates and is rewritten every time `qops install` runs — so the
amendment was destined to be deleted by the next upgrade, and the `v0.5.0`
bump is where that happened. The content is this project's own record, not the
substrate's, so it lives in this project's own ADR sequence, where a render
cannot reach it.

The lesson generalises: a consumer's knowledge never goes in a `CADR-`, because
`CADR-`s are citations qops renders. It goes here.

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

**The silent-failure warning in `CADR-0002` applies twice over.** A machine
asleep produces no error and no run; a machine awake with one task pointed at
the wrong root produces no error either, and a picker reporting "nothing
eligible" is indistinguishable from a healthy idle queue.

## Note added 2026-09-28

`--root` is a flag on `scripts/qops_pickup.py`, **not** on `python -m qops
<verb>`. The CLI verbs find their root by walking up from cwd
(`config.find_root()`), and an unrecognised `--root` on a verb is accepted and
ignored — so `python -m qops doctor --root <other-root>` silently reports on
whichever root cwd sits in. On a host with two roots that reads as an
authoritative answer about the wrong repo. Filed against the substrate.
