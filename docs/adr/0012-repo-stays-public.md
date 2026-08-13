---
status: accepted
revisit-after: 2026-10-01
---

# The repository stays public

`qvajda/qhoto_printshop` remains a public repository. It buys free GitHub
Actions minutes, which the whole automation half of qops assumes, and it costs
disclosure of a pipeline whose value is in the shop, not in the code.

**Strengthened 2026-08-13 by E13a:** all 392 commits and 1,357 reachable blobs
were scanned with three independent instruments and no live credential of this
project was found in history. So the cost of being public is the **forward** one
only — what gets committed from here.

**The forward rule, which is the whole mitigation:** if a secret is ever found,
**rotate the credential first**, and treat rewriting history as a separate
decision even then. Rewriting is a closed question and does not reopen on a new
scanner or a new ruleset — only on a scan finding a real live credential.

**`revisit-after` is set to launch-adjacent** because the trade changes the day
the shop has revenue attached to it.
