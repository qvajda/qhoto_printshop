# GL-16 stub — unattended-resilience hardening (investigate → design → build)

Starting prompt for a **Claude Code session**. GL-16 is the last hard blocker
before cron/unattended (see `docs/2026-07-22-go-live-plan-of-attack.md` GL-16,
and Part 4's Session-B feedback). It is **IR→C**: the design isn't known yet, so
**Phase 1 investigates + proposes and STOPS for sign-off**, then Phase 2 builds.
This is a stub, not a task list — the task list is a Phase-1 deliverable.

Why it matters: Round-1 (GL-9) ran with a coding session babysitting it —
hand-fixing DB status after a fault, re-running stranded stages. Unattended cron
has none of that. A transient blip must self-recover, and a fault must never
strand a candidate in an in-progress status no scheduled run will pick up.

## What's already known (don't re-derive — verify, then build on)

- **`pipeline/http.py._request` retries ONLY Cloudflare 1010** (403 + "1010",
  backoffs 60/120/240). **Everything else raises `HTTPError` immediately** —
  read timeouts, connection resets, 5xx, 429 — with no backoff, no retry. This
  is the prime suspect for the owner's "retries quickly fail" symptom.
- **Transient faults are conflated with real rejects.** After a critic reject,
  the regeneration burst fires several API calls quickly; a transient fault in
  that burst hits
  `critic_pass.py:519 abandon_candidate(... "retry regeneration failed")`,
  **burning the 3-attempt abandon budget on a network blip** — matches "happens
  a lot right after a reject gate."
- Partial resilience already exists and should be the pattern to extend, not
  replace: typed `ReplicateThrottledError` (429), `anthropic_client` ValueError
  retry loops, `group_product` jittered polling, `_generate_cycle_pacing`. All
  inject `sleep_fn` for testability — keep that convention.
- `create_or_reuse_group_product` is idempotent (reuse-before-create,
  orphan-delete) — this is what makes retrying a Gelato create *safe*, and any
  new retry layer must preserve/rely on it.

## Phase 1 — investigate + design (then STOP for sign-off)

Read first: `CLAUDE.md` (hard constraints), `pipeline/http.py`,
`pipeline/critic_pass.py` (the reject→regenerate→abandon path),
`docs/cloudflare_1010_issue_investigation.md`, and the GL-9 incident notes in
`.remember/` (the actual live faults — ground the design in what really failed,
not hypotheticals).

Answer, in a design doc `docs/2026-07-22-resilience-design.md`:

1. **Fault taxonomy.** From the GL-9 incident notes + code, classify what
   actually goes wrong: which calls, which error classes (httpx
   `ConnectError`/`ReadTimeout`, 5xx, 429-with/without `Retry-After`, other
   403s), and which are transient (retry) vs. terminal (fail fast). 401 is
   **out of scope — GL-15 already owns token refresh**; don't double-handle it.
2. **Retry-with-backoff layer.** Propose exponential backoff + jitter in the
   http layer for the transient classes, honoring `Retry-After` on 429.
   **Hazard to resolve explicitly:** auto-retrying non-idempotent POSTs (Gelato
   create) risks duplicate products — state which methods/endpoints are safe to
   blind-retry vs. which must defer to a stage's own idempotency
   (`create_or_reuse`). Don't widen retries somewhere that creates duplicates.
3. **Don't burn the reject budget on transients.** Separate "regeneration failed
   because the art was rejected again" (counts toward the 3-attempt cap) from
   "regeneration failed because an API blipped" (retry, don't abandon). This is
   likely the single highest-value fix.
4. **Crash-safe / self-healing state.** Define how a stage that dies mid-run
   leaves a **resumable** status the next scheduled run reclaims, rather than a
   stranded in-progress row. Consider a "processing → transient-failed
   (resumable)" vs. "failed (abandoned)" distinction, idempotent stage entry,
   and/or a reclaim/sweep step. The test: pull the plug at any point and the
   next cron cycle recovers without a human touching the DB.
5. **Scope + budget guards.** Retries cost real API calls (Replicate, Gelato) —
   cap attempts and total added latency so a flaky vendor can't run the batch
   for hours or rack up spend. Name the caps.

**STOP** at the end of Phase 1 and present the design + a proposed task list for
sign-off (PRD threshold — this touches reliability broadly and is >30 min).
Don't start Phase 2 without explicit approval.

## Phase 2 — implement (after sign-off)

SDD, same convention as the base-artwork / live-findings branches: branch
`fix/resilience-hardening` off master; one task = one commit; task brief +
report + `.superpowers/sdd/` ledger; full suite green after every task; final
whole-branch review before merge.

### Hard rules (CLAUDE.md + reversibility)

- **No live external calls without explicit go-ahead** — all dev on
  `sleep_fn`-injected unit tests + mocks (the existing retry code shows the
  pattern; no real backoff waits or live faults in the suite).
- **Idempotency is sacred:** all Gelato creates stay routed through
  `create_or_reuse_group_product`; a retry must never create a duplicate
  product or a duplicate Etsy listing.
- Don't widen the critic **3-attempt abandon cap** — the point is to stop
  *transients* from consuming it, not to add regeneration attempts.
- 401/token refresh stays GL-15's; don't re-implement it here.
- No `urllib` in `pipeline/` (grep-test); route all HTTP through
  `pipeline/http.py`. `TELEGRAM_ADMIN_CHAT_ID` stays env-only.
- If a fix seems to need changing a CLAUDE.md hard constraint, **stop and
  raise it**.

### Definition of done

A transient fault (timeout / 5xx / 429 / connection reset) is retried with
backoff + jitter and honors `Retry-After`; a blip during post-reject
regeneration no longer abandons the candidate or burns the 3-attempt cap; a
stage killed mid-run leaves a resumable state the next cron cycle reclaims with
zero human DB edits (proven by a test that interrupts and resumes); retry
attempts and added latency/spend are capped; suite green; whole-branch review
clean. **This is the gate that lets GL-7 (cron) switch to unattended.**

## Explicitly deferred

- GL-7 cron orchestrator itself (separate branch; GL-16 unblocks it, doesn't
  build it).
- Any mockup/compositor work (GL-4/GL-5).
- Broader observability/alerting (a Telegram "batch errored" heads-up is a
  reasonable *small* include if it falls out of the state work — but a full
  monitoring stack is post-launch).
