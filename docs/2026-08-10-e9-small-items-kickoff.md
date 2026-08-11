# E9 small-items kickoff — GL-57 to GL-62, GL-65

**Type:** C (mostly) · **Tool:** Claude Code, in-repo · **PRD:** not required —
every item here is well under one sitting and only GL-57 touches an external
system, under the standing owner-gated live-call rule. **This document is the
sign-off artefact** (CLAUDE.md §2).

Board rows: `docs/2026-07-22-go-live-plan-of-attack.md` **GL-57** (blockers),
**GL-58, GL-59, GL-60, GL-61, GL-62, GL-65** (housekeeping). Evidence:
`docs/2026-08-10-e9-findings.md`. The rows are authoritative if this document
disagrees with them.

**Two corrections to the E9 digest, applied throughout below.** (1) The
`SharedProductVariantError` handler *does* leave a trace — GL-54 gave it a
`failed_reason`; the defect is the retry classification, not the logging.
(2) The digest's line numbers for `publish_primary_group.py` and
`group_mockup.py` have drifted since GL-54 — the behaviours are as described,
the citations are not. Re-locate by symbol, not by line.

## Suggested batching

| Session | Items | Why together |
|---|---|---|
| **S1 — the featured image** | GL-57 | The only one with a live-call verification step and the only one that changes what a buyer sees. Keep it alone so its live read-back is not entangled with anything. |
| **S2 — the failure-handling pass** | GL-58, GL-59, GL-60 | All three are "an error is handled at the wrong level of permanence or capacity". One reviewer's mindset, one test file neighbourhood. |
| **S3 — the operability pass** | GL-61, GL-62 | Both are config/observability, both touch entrypoints, neither touches pipeline logic. |
| **S4 — not a coding session** | GL-65 | R, and deliberately not a fix. See §7. |

---

## §1. GL-57 — the featured image is the 10x24 mockup on every listing

**The one-sentence problem:** `group_product.py` computes the correct
gallery order and `etsy_client` never tells Etsy about it.

**Verified in code, not inferred.** `etsy_client.upload_listing_image`
(`pipeline/etsy_client.py`) builds a multipart body containing exactly one
part — `name="image"` — and posts it to
`/shops/{shop_id}/listings/{listing_id}/images`. **There is no `rank` on any
call path**, live or dry-run. Meanwhile `group_product.py`'s `_GROUP_RANK_SQL`
already orders its upload loop primary-first, then 5x7, then 10x24. The
intent exists; it never leaves the process.

**Reproduced 2/2** on the two candidates that reached a published listing on
2026-08-10 (84 and 87): the 10x24 mockup — last uploaded — is the featured
image. The owner's manually-corrected reference ordering is in the E9
hand-off screenshot.

**Scope.** Add an optional `rank` parameter to `upload_listing_image`, send it
as an additional multipart field, and pass it from the caller using the order
`_GROUP_RANK_SQL` already produces.

**Two things this session must not do.**

1. **Do not assume Etsy's default-ordering rule.** What is confirmed is the
   missing parameter. "Etsy defaults to last-uploaded-first" is an inference
   from n=2. Send explicit ranks for the **whole** sequence rather than only
   `rank=1` on the first image — that way the outcome does not depend on a
   default nobody has verified.
2. **Do not verify by status code.** GL-22a established that these APIs
   return success for changes they drop. Verify with
   `get_listing_images` (already exists, added in GL-33) and assert the
   returned order — read-back, not response code.

**Live-call gate.** The read-back verification needs one owner-supervised run
against a real listing. Candidate 87's listing (`4553335845`) is live and is
the obvious subject; changing its image order is reversible from the Etsy
dashboard, which makes it a safe target — but it is still a live mutation, so
per CLAUDE.md §4 it waits for an explicit go-ahead, separately from this
document's sign-off.

**Done when:** ranks are sent on every upload; a read-back on a live listing
shows a primary-group mockup first; a regression test asserts the outbound
body carries the rank field in the `_GROUP_RANK_SQL` order.

---

## §2. GL-58 — a permanent error is being retried forever

**The one-sentence problem:** the codebase has no way to say "this error can
never succeed", so a structurally-impossible operation is handed back to the
retry loop on every cycle.

Candidates **1** and **39** have 5x7 groups whose Gelato products predate
v4.12. `group_product.py` correctly raises `SharedProductVariantError` —
adding a variant to an existing Gelato product has no API path, settled by
GL-22a Q2 and not in question. `group_mockup`'s per-item handler then treats
it like any transient failure: writes `failed_reason =
'gl54_group_mockup_failed: ...'`, leaves the group at `pending_generation`,
comment says "retryable next cycle". **It will re-fail and re-alert Telegram
on every batch cycle indefinitely.** Currently masked only because all three
scheduled tasks are Disabled.

**Scope, and the design call worth making deliberately.** The tempting fix is
an `isinstance(exc, SharedProductVariantError)` check at this one call site.
Prefer making permanence a **property of the exception** — e.g. a marker base
class or a `permanent = True` attribute the handler reads — because (a) this
is plainly not the last member of its class, and (b) the same per-item handler
pattern now exists in six-plus loops after GL-54, and they should all learn
this once rather than six times. If that turns out bigger than a short session,
do the narrow fix, and file the general one rather than pretending it is done.

**The M half, and it is required.** Candidates 1 and 39's two 5x7 groups need
marking `failed_abandoned` by hand — the code fix stops *future* alerts; it
does not clear these two. Per CLAUDE.md §4, show the exact rows and the exact
UPDATE before running it, and take the DB backup first.

**Do not** let this become a Gelato-side repair of the two legacy products.
That is a different, larger question and nobody has asked it.

**Done when:** a permanent error marks the group `failed_abandoned` and alerts
once; a test asserts a permanent error does not leave a retryable row; the two
legacy groups are marked; the stage still fails once at the end of the loop
(CLAUDE.md's swallowed-exception rule is not weakened by this change).

---

## §3. GL-59 — Replicate's 60s wait produces false timeouts under burst

**The one-sentence problem:** the client gives up while the job is still
queued, then the job succeeds in three seconds and nobody is listening.

Candidates 78 and 83 raised `ReplicatePredictionTimeoutError` — "did not
complete within the 60s synchronous wait window" — while Replicate's own
dashboard showed those same predictions completing in **2.8s and 3.7s
execution time**. `replicate_client.py`'s existing comment already names the
assumption (the `Prefer: wait` window was sized for schnell's 1–2s latency and
assumes near-zero queue time) and already names the fix (async submit + poll).
E9's contribution is showing it hit `generate_image`, not just the
`upscale_image` cold-boot case the comment anticipated — under the ordinary
shape of a batch run: nine candidates firing back-to-back at an account capped
at 6 req/min with no payment method on file.

**Read the row's disagreement note before scoping.** This is filed as
housekeeping on the owner's classification, and the board row argues it should
be a blocker: it silently costs candidates and scales with batch size. If the
owner sustains the non-blocker call, take the **cheap mitigation** in this
session and leave the real fix filed: cap or stagger per-cycle generate calls
(GL-61's candidates-per-batch knob is the same lever, which is why S3 may want
to come first).

**Full fix scope:** replace synchronous `Prefer: wait` with submit + poll in
`_predict`, with a bounded overall timeout and backoff that respects the
existing `ReplicateThrottledError` / 429 path. Keep the distinction the current
error text is careful about — a rate-cap 429 is not a timeout — because the
next reader will need it.

**Done when:** a queued-then-fast prediction completes successfully rather than
raising; the 429 path is unchanged and still tested; the error message for a
genuine timeout still says something true.

---

## §4. GL-60 — `max_tokens=200` on the art-brief writer

One line: `pipeline/art_brief.py`, the `anthropic_client.complete(...,
max_tokens=200, model=HAIKU_MODEL)` call. Candidate 81 hit
`TruncatedResponseError` live and succeeded on retry, so today's cost is a
wasted attempt against the retry budget.

**Do the audit, not just the line.** This is the third instance of the same
class — `compliance_draft` 1024→2048, `critic_pass` 2048→4096, now this. Read
every `max_tokens` in `pipeline/` in one pass and size each against what its
prompt actually asks for. That is what stops a fourth.

Note the two library defaults (`complete` at 1024, `complete_with_images` at
1024) are *defaults*, not per-call caps — raising a default silently changes
every non-overriding caller. Prefer explicit per-call values.

**Done when:** the art-brief call has a cap sized to its output; the audit's
findings are written on the GL-60 row even where nothing changed.

---

## §5. GL-61 — three missing config knobs

Add to `.env` / config resolution, following CLAUDE.md's static-config rule
(resolved once, never discovered at runtime):

1. **Candidates per batch cycle.** Second customer: GL-59's cheap mitigation.
2. **Telegram error-message verbosity.** Low stakes, do it last.
3. **Research mode** — `always` / `consume-pending-only` / `if-nothing-pending`.
   **This is the one with teeth.** Recovering the good-design/bad-copy backlog
   via GL-56 means running batches that must not pile new candidates on top,
   and there is currently no way to ask for that.

Sensible defaults must reproduce today's behaviour exactly, so that an
unconfigured `.env` is not a behaviour change.

**Done when:** each knob has a default matching current behaviour, a test that
the default path is unchanged, and one line in the README or runbook — an
undocumented knob is a knob nobody turns.

---

## §6. GL-62 — the scheduled tasks capture no output

`qhoto-batch-morning` / `-evening` / `qhoto-hourly` redirect no stdout or
stderr. E9 spent real time guessing whether the batch was working or hung and
settled it by CPU-time and DB polling.

**Two options; the second is recommended.** Redirecting in the Task Scheduler
action is five minutes of M work, machine-local, and lost on any
re-registration. A file handler in `run_batch.py` / `run_hourly.py` is C work,
travels with the repo, is testable, and survives the host move that GL-3's
pre-committed VPS fork makes non-hypothetical.

Rotate or cap the log — an unbounded log on the owner's desktop is a slower
version of the same problem. Do not log anything credential-shaped: the
`TELEGRAM_ADMIN_CHAT_ID` is treated as a credential (CLAUDE.md), so it must
not land in a log line.

**Done when:** a run leaves a readable log file; the log has a size bound; no
secrets in it.

---

## §7. GL-65 — the Telegram tap-drop, and why this section is not a fix

**Do not open this as a coding session.** It is R, and the single most
important thing about it is that **there is no evidence left to investigate,
twice over.**

What happened: the owner tapped approve/reject on candidates 80/84/87/88/90;
a **raw, no-offset `getUpdates` query against Telegram's own API, bypassing
this app's stored cursor entirely**, showed the bot's server-side queue held
zero trace. A re-tap minutes later landed cleanly with fresh `update_id`s.
That independently rules out offset consumption inside `publish_primary_group`
and places the loss at or before Telegram's own queue — outside anything this
pipeline logs. Second occurrence; first was candidates 57-60 on 2026-08-08.

**How this sits against GL-45, because both rows are true.** GL-45 tested the
tap path clean and its row is deliberately written as "tested, not diagnosed".
E9 is the counter-observation that keeps the question open. Neither supersedes
the other, and any session that starts by trying to reconcile them into one
verdict is doing the wrong work.

**The only tractable move is to instrument for the next occurrence.** Two
directions, both cheap, neither a root-cause investigation:

- **Client-side capture** on the owner's Telegram app — so a tap has a record
  that does not depend on the bot receiving it.
- **A "did my tap register?" signal.** GL-45 established that several minutes
  of silence after a tap is the *designed* behaviour (the toast and keyboard
  collapse land when the hourly poll dispatches, not at tap time) — which is
  exactly what makes a real drop invisible to the person tapping. Anything
  that shortens that feedback loop converts a silent loss into a visible one.

**Tool-fit flag (CLAUDE.md §7):** the second direction is arguably not a
pipeline change at all. If taps keep going missing at Telegram's delivery
layer, the right answer may be a different confirmation channel rather than
more instrumentation on a queue we do not own. Worth ten minutes of thought
before any code.

**Done when:** a decision is recorded on GL-65 about what will be captured
next time — not when a root cause is found. A found root cause would be a
bonus and is not the deliverable.
