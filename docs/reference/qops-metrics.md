# qops metrics — what each figure means

`python -m qops metrics [--since DATE] [--until DATE] [--json]`. Payback-weeks
is not a headline here — these measure whether the thing gets used, not a
projected saving. Issue #115.

| Key | Means | Bad value looks like |
|---|---|---|
| `S1_resume_cost` | Reads before the first productive call, per session | `median_reads` climbing session over session — resume context isn't landing |
| `S2_kickoff_docs` | Kickoff-class docs (`kickoff`/`session-prompt`/`launch`/`brief`/`runbook`) added since `--since` | Nonzero and growing — planning prose instead of issues |
| `S4_review_before_gate` | PRs where review was requested before the gate check went green | `requests_without_green_gate` nonempty — review is being asked for on red |
| `S9_planned_to_working` | Issues currently `state:building` | A long-stuck list — sorties opened but not moving |
| `S10_hot_path` | `CLAUDE.md` size vs its 150-line cap, and the brief's token cost | `within_cap: false`, or `brief_tokens` creeping up |
| `S11_owner_minutes_per_merged_pr` | Ledger `session_start`→`stop`/`session_end` minutes, summed and divided by merged PRs in the window | High and rising — sessions cost more time per unit of delivered work |
| `S12_full_flow_share` | Share of merged PRs whose branch matched `<type>/<issue>-<slug>`, whose gate ran green, and whose branch was deleted post-merge — the direct read on ADR-0019 | Low `pct` — the enforced flow isn't the common path, `no-issue/` escapes or manual branch cleanup are |
| `S13_owner_interruptions_per_sortie` | Extra ledger `session_start`s on the same branch beyond the first, averaged per branch | `per_sortie` above 0 on `gate:machine` work — ADR-0017 wants this at zero, one owner touch at review only |

`S1`/`S10` are unchanged from Phase −1 and Phase 6 — they're the numbers that
rejected the qops rollback. `S11`–`S13` are additive, from #115.
