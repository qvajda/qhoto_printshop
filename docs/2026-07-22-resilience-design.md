# GL-16 resilience design — unattended-safe HTTP + state (2026-07-22)

Phase 1 output per `docs/2026-07-22-gl16-resilience-hardening-stub.md`. Investigation only, no code changed. Grounded in `pipeline/http.py`, `pipeline/critic_pass.py`, `pipeline/generate.py`, `pipeline/group_product.py`, `db/schema.sql`, `docs/cloudflare_1010_issue_investigation.md`, and the GL-9 live-test incident log (`.remember/today-2026-07-22.done.md`).

## 1. Fault taxonomy

GL-9's actual live faults (not hypothetical):

| Fault | Where it hit | Evidence |
|---|---|---|
| Replicate HTTP 404 "No adapter found" on a correction-regen call | `critic_pass.py` attempt-3 regen, seconds after an identical call succeeded | GL-9 candidate 38 |
| Etsy access token expired (401) mid-round | both `process_update` and the publish retry | GL-9 candidate 39 — GL-15 already fixes this |
| Cloudflare 1010 (403) | Gelato + Replicate, intermittent, sometimes call #1 | `cloudflare_1010_issue_investigation.md` — already handled |

Code inventory of what `pipeline/http.py._request` currently does with each class:

| Class | Current behavior | Transient or terminal | Proposed |
|---|---|---|---|
| CF 1010 (403 + body contains "1010") | retried, 60/120/240 backoff | transient (vendor WAF blip) | unchanged |
| Other 403 (not 1010) | raises immediately | terminal (auth/permission, won't self-heal) | unchanged — don't lump with 1010 |
| 401 | raises immediately | GL-15's (token refresh happens one layer up, in `etsy_auth.py`) | out of scope, unchanged |
| 429 | raises immediately at the `http.py` layer; `replicate_client.py` catches the resulting `HTTPError` and re-raises typed `ReplicateThrottledError(retry_after)` — but nothing currently *waits* on `retry_after`, callers just fail the candidate and let the next cron cycle retry from scratch | transient, has an explicit wait hint | retry with the given `retry_after` (or a default) at the http layer, not push it up as a typed exception that nobody backs off on |
| 5xx | raises immediately | transient (vendor-side, self-heals) | retry, exponential backoff + jitter |
| `httpx.ConnectError` / `httpx.ReadTimeout` / connection reset | raises immediately (not even wrapped as `HTTPError` — a raw httpx exception) | transient (network blip) | retry, exponential backoff + jitter |
| 4xx other than 401/403/429 (400, 404, 422) | raises immediately | terminal (bad request/payload — retrying won't fix it; the Replicate 404 above was a vendor-side model-routing fluke, not a client bug, but a blind retry-forever on 404 risks masking real payload bugs) | unchanged — but see budget guard below for a *bounded* retry, since GL-9's 404 was empirically transient |

401 confirmed out of scope (GL-15 owns it — `etsy_auth.py` wraps calls with its own refresh-and-retry, doesn't go through this backoff layer).

## 2. Retry-with-backoff layer

Add a second backoff table in `pipeline/http.py`, alongside the existing CF-1010 one, for the general transient class (5xx, `ConnectError`, `ReadTimeout`, and 429 without special-casing since `Retry-After` covers it):

```python
_TRANSIENT_BACKOFFS = (2, 5, 10)  # + jitter, seconds — short, this is a network blip not a WAF ban
```

- On 429: sleep for `Retry-After` (header, seconds or HTTP-date) if present, else fall back to `_TRANSIENT_BACKOFFS`.
- On 5xx / `ConnectError` / `ReadTimeout`: `_TRANSIENT_BACKOFFS` with the same jitter convention `group_product._jittered` already uses (±20%).
- Same `sleep_fn` injection convention as the CF-1010 loop — one retry loop in `_request`, two backoff tables it chooses between by fault class.
- 404/400/422 get **one bounded retry** (single retry, `_TRANSIENT_BACKOFFS[0]` only) rather than zero or unlimited — GL-9's Replicate 404 was empirically a vendor-side blip on an identical call that worked seconds later, but blind infinite-retry on a genuine 404 (typo'd URL, deleted resource) would hide a real bug. One retry catches the observed case without masking a hard failure past a single cron tick.

**Idempotency hazard.** `_request` is generic — it does not know if the caller's operation is safe to blind-retry. Splitting by HTTP method is not enough either (a POST to Gelato's `create-from-template` is a POST, but so is a Gelato `poll`-adjacent status GET that's always safe). Resolve explicitly at the call-site, not in `http.py`:

- **Safe to blind-retry in `http.py` itself:** all GET/HEAD (`fetch_bytes`, `head`, Gelato/Etsy status polls), and PUT to a pre-signed R2 URL (`put_bytes` — R2 PUT-with-key is idempotent, same bytes same key). These already flow through `_request` uniformly — the new backoff applies to them for free, no call-site change needed.
- **Never blind-retried in `http.py`:** POST/PATCH bodies that create or mutate server state (Gelato `create-from-template`, Etsy `updateListing`/`updateListingInventory`, Replicate prediction-create, Anthropic completion). For these, `_request` still raises immediately past the CF-1010/transient backoff table on a genuine failure — **no retry loop wraps the write itself.** Safety instead comes from the caller's own idempotency:
  - Gelato creates already route through `create_or_reuse_group_product` (reuse-before-create, orphan-delete) — a caller-level retry (next cron cycle re-invoking the same stage) is safe *because* that function is idempotent, not because `http.py` retried the POST.
  - Etsy patches (`updateListing`) are naturally idempotent (same fields, same listing id) — safe for the *caller* to retry, still not blind-retried inside `http.py`.
  - Replicate prediction-create and Anthropic completion are **not** idempotent (each call spends money and can produce a different result) — these must never be blind-retried at any layer. A failure here surfaces to the calling stage, which decides (see §3) whether to treat it as transient-retry-later or a real failure.

So `http.py`'s new backoff table only ever fires on GET/HEAD/pre-signed-PUT and on the *connection-level* fault classes (timeout/reset/5xx/429) for POST/PATCH — i.e. it retries "the request never got a state-changing response back" cases, not "the request succeeded/failed and we're retrying anyway" cases. A 5xx or timeout on a POST *before* any response is observed is safe to retry (the server either didn't apply it or applying-twice is what the caller's own idempotent design already tolerates); a clean 4xx/2xx response is never retried.

## 3. Don't burn the reject budget on transients

Today, `critic_pass.py:502-519` wraps the attempt-3-retry regen burst (`generate_for_candidate` → `create_primary_mockup` → `build_compliance_draft`) in one `except Exception` that calls `abandon_candidate(..., "retry regeneration failed: {exc}")` regardless of *why* it failed — a rubric reject and a Replicate 404 both land here identically. This is GL-9's exact symptom.

Fix: classify the exception before deciding what it means.

```python
TRANSIENT_EXC_TYPES = (http.HTTPError, httpx.ConnectError, httpx.ReadTimeout, ReplicateThrottledError)

try:
    generate.generate_for_candidate(...)
    primary_mockup.create_primary_mockup(...)
    compliance_draft.build_compliance_draft(...)
except TRANSIENT_EXC_TYPES as exc:
    # A vendor blip during the regen burst — not a verdict on the art. Leave the
    # candidate exactly where it is (still 'generating', same attempt_number,
    # no critic_pass_attempts row written for this failed regen) so the next
    # cron cycle's run_critic_pass_cycle sweep picks it back up and retries the
    # SAME attempt — doesn't consume one of the 3 abandon-budget slots.
    logger.warning("transient fault during regen for candidate %s: %s", candidate_id, exc)
    return {"candidate_id": candidate_id, "passed": False, "attempts": attempt_number, "transient": True}
except Exception as exc:
    # A real code/data defect (malformed JSON, DB constraint, etc) - still abandon,
    # this is not something a retry will fix.
    abandon_candidate(conn, candidate_id, state["group_id"], f"retry regeneration failed: {exc}", now=now)
    raise
```

Note `http.HTTPError` catches the *already-exhausted* case (e.g. a 5xx that used up all `_TRANSIENT_BACKOFFS` retries and still failed, or a terminal 4xx) too — at this layer we can't tell "http.py already retried and gave up" from "never got a chance to retry" apart, and both are still not a verdict on the art, so both stay transient here. The distinction that matters for the abandon budget is exception *type* (network/vendor fault vs. our own code raising `ValueError` on malformed JSON, a DB `IntegrityError`, etc.), not retry count.

`attempt_number` does not increment on the transient path — the next `run_critic_pass_cycle` sweep re-enters `run_critic_pass` for this candidate, `max_attempt_row` still reads the same `attempt_number` (no new `critic_pass_attempts` row was written for the failed regen), so it retries the identical attempt. Real rejects still count normally.

This is the single highest-value fix per the stub — it directly stops GL-9's repro.

## 4. Crash-safe / self-healing state

Audited every "in-progress" window against what a hard kill (not a Python exception — SIGKILL, power loss) leaves behind:

**Already self-healing (verified, no change needed):**
- `candidates.status = 'pending'` → `generate_for_candidate` only writes `status = 'generating'` in its single terminal UPDATE; a kill mid-function leaves the row at `'pending'`, and `run_generate_cycle` re-selects all `status = 'pending'` rows every cycle. Retry is naturally idempotent (art_brief is reused if already written, prompt/prediction are re-attempted fresh).
- `candidates.status = 'generating'` → `run_critic_pass_cycle`'s sweep (`WHERE c.status = 'generating' AND group not already passed`) re-enters *any* generating candidate every cycle, not just ones a live session is watching. This is already the resumable design; §3 stops it from being short-circuited into `'failed'` by a transient fault.
- `groups.status = 'publish_failed'` → `retry_publish_failed_groups()` already exists (GL-9/H1) and re-drives the publish step, re-doing the Gelato create-or-reuse from scratch (confirmed live: candidate 39's expired-token failure recovered this way with zero orphans).
- `group_products` `mockup_failed` → reused by `create_or_reuse_group_product` if a `gelato_product_id` was actually assigned before the fault (only re-polls, doesn't re-create); deleted-and-recreated if the create itself never got an id. Already exactly the resumable/idempotent shape §2 relies on.

**Gap found (new):** `group_products.status = 'pending'` — inserted (committed) right before the `try` block that wraps the actual Gelato create call. A kill in that narrow window (row committed, Gelato call never made) leaves a row that `create_or_reuse_group_product`'s own lookups don't recognize: the "live" check only matches `('created','published')`, the "stale, reusable/deletable" check only matches `('mockup_failed','publish_failed')`. A `'pending'` row matches neither — invisible. The next cron cycle's call to the same function inserts a **second** row instead of reclaiming the first, and the orphaned first row lingers forever (not deleted, not reused — a silent DB leak, not a duplicate Gelato product since no Gelato call ever happened for it).

Fix: extend `cleanup.py`'s existing sweep (it already deletes orphaned Gelato products / stale rows post-launch per the stage-12 design) to also reclaim `group_products` rows stuck at `status = 'pending'` past a short age threshold (e.g. >10 minutes — long enough that it's not just a normal in-flight create, short enough to reclaim well within one cron cadence): delete the row (no Gelato product exists to clean up), so the next `create_or_reuse_group_product` call for that group starts clean instead of leaking a phantom row every crashed attempt.

No new "processing" status enum is needed elsewhere — `'pending'` (candidates) and `'generating'` already function as the resumable in-progress marker and are already swept unconditionally every cycle. The one real gap is the un-reclaimed `group_products.pending` row above.

## 5. Scope + budget guards

- **`_TRANSIENT_BACKOFFS = (2, 5, 10)`** per call, same shape as the existing CF-1010 table — worst case ~17s + jitter added latency per call before it either succeeds or falls through to the caller. Small relative to the twice-daily/hourly cadence.
- **429 `Retry-After` is honored as-is, uncapped by our own table, but capped at a ceiling** (e.g. 120s) — a vendor asking for a absurd multi-minute wait shouldn't stall a whole batch; past the ceiling, treat it as exhausted and let it surface to the caller (§3's transient path) rather than sleep-blocking the process.
- **The regen-burst transient path (§3) does not add its own retry loop** — it relies entirely on the *next scheduled cron cycle* to retry, not a tight in-process loop. This bounds worst-case cost to "one skipped cron tick," not unbounded spend within a single run if a vendor is down for hours.
- **`group_products.pending` reclaim threshold: 10 minutes** (cleanup.py sweep, run each cycle) — matches the existing `poll_timeout=300s`(5 min) Gelato readiness window with margin, so a still-legitimately-in-flight create is never reclaimed out from under itself.
- No change to the critic-pass **3-attempt abandon cap** — §3 only changes what counts toward it.

## Proposed task list (Phase 2, pending sign-off)

Branch `fix/resilience-hardening` off master, one task = one commit, SDD convention:

1. `pipeline/http.py`: add `_TRANSIENT_BACKOFFS` + 429 `Retry-After` handling (capped) to `_request`, distinct from the CF-1010 table. Unit tests with `sleep_fn` injection, no live calls.
2. `pipeline/critic_pass.py`: classify the regen-burst exception (transient vs. real failure) per §3; transient path returns without abandoning, doesn't write a new `critic_pass_attempts` row, doesn't increment `attempt_number`. Unit tests: simulate a transient exception mid-burst, assert candidate stays `'generating'`, same attempt count, no Gelato DELETE fired; simulate a non-transient exception, assert `abandon_candidate` still fires as today.
3. `cleanup.py`: reclaim `group_products` rows stuck at `status = 'pending'` past the 10-minute threshold. Unit test: seed an aged pending row with no `gelato_product_id`, assert it's deleted and a subsequent `create_or_reuse_group_product` call creates cleanly (no duplicate/leak).
4. Interrupt-and-resume test: a scripted "kill mid-stage" test (raise inside a monkeypatched stage call partway through a multi-stage cycle) proving the *next* cycle invocation completes the candidate/group with no manual DB edit — the stub's explicit "pull the plug" acceptance test.
5. Whole-branch review, full suite green, merge to master.

No CLAUDE.md hard constraint needs changing — idempotency, the 3-attempt cap, and the http.py choke point are all preserved, extended not replaced.

---

**STOP for sign-off** per the stub. Awaiting go-ahead before Phase 2.
