# GL-7 — the two-cadence orchestrator: PRD and coding-session kickoff (2026-08-05)

**Target tool: Claude Code, in-repo**, with **one section that is not a coding
task at all** — §0, the host decision (GL-8 research + GL-3 sign-off), which is
owner-facing and has been open since 2026-07-22. Cowork's role is this document
and, later, a status artifact to watch the soak.

**This is a full PRD per CLAUDE.md §2** — it touches external systems (every
API the pipeline speaks to, unattended), and it is by a wide margin more than
one sitting. **Nothing gets built until the owner signs off at §9.**

**Why this is next (owner, 2026-08-05).** GL-29 is unblocked and cheaper, and
was deliberately *not* chosen. GL-29 is a flag, one call site and a rewritten
guard test — it costs the same session in three weeks as it costs today, and
each live exercise burns €0.20 on an irreversible listing. GL-7 is the only
remaining item whose **duration is uncertain**, the only one with a soak that
cannot be compressed, and it carries two riders (GL-35, GL-36) that make every
future live run cheaper. Ten of fifteen go-live gate items are ticked; of the
five left, four are a session or an email.

---

## 0. GL-8 / GL-3 — where this runs. **Decide this first; everything else is
downstream of it.**

The preliminary decision on record (GL-3, 2026-07-22) is **local desktop**,
never confirmed. It should be confirmed or overturned before a line of
orchestrator code is written, because the host determines the process model,
where the SQLite file lives, how secrets are supplied, and what "the soak
passed" even means.

### What the workload actually is

Measured from the repo, not assumed:

- **Hourly:** one `getUpdates` call plus, at most, decision handling. Already
  implemented — `publish_primary_group.run_publish_primary_group_cycle` polls,
  checks the admin ID, dispatches to both the primary and group decision
  handlers, advances a persisted `telegram_offset`, and retries
  `publish_failed` groups. Typically seconds; can run long when a tap triggers
  a publish.
- **Twice daily:** the heavy batch — Replicate generation, local compositing
  (OpenCV/PIL), Anthropic critic passes, Gelato, Etsy, Telegram media uploads.
  Minutes, with multi-MB images in memory and on disk.
- **State:** a **local SQLite file** (`db/qhoto.sqlite3`), plus artwork in R2
  and a mockup corpus on disk. Etsy's OAuth refresh (GL-15) **writes tokens
  back**, so the host needs durable, writable storage — this is not a stateless
  workload and any host that pretends otherwise imports a database migration
  into GL-7's scope.

**That last point disqualifies more options than cost does.** Anything
ephemeral (GitHub Actions runners, Cloudflare Workers, most function
runtimes) means moving SQLite to Turso/Postgres/R2 first. That is a real
project, and it is not this one.

### Options

| Host | ~Cost/mo | Fits the state model? | The real argument |
|---|---|---|---|
| **Local desktop** (Windows Task Scheduler) | €0 | ✅ natively — it is where the DB, the corpus and `.env` already are | **Zero migration, zero new secrets surface, and the mockup corpus is already here.** Against it: sleep/wake, reboots, and "the machine was off" are silent failures; a missed hourly poll is invisible, and Telegram's `getUpdates` backlog is finite. Whether that is disqualifying is exactly what the soak measures. |
| **Small VPS** (Hetzner CX22, 2 vCPU / 4 GB / 40 GB) | **€3.79–~€4.35** ([Hetzner](https://www.hetzner.com/pressroom/new-cx-plans/), [pricing 2026](https://vpsfor.dev/posts/hetzner-cx22-pricing-2026/)) | ✅ persistent disk, plain `cron`, same Linux the code is tested on | The boring, correct answer if the desktop fails the soak. 4 GB comfortably holds the compositing step. Costs: one `.env` copy onto a machine you administer, one corpus sync, and you now own a server. **Note the April 2026 Hetzner price adjustment** — confirm the live price at checkout rather than trusting this table. |
| **Fly.io machine + volume** | ~$5.70 machine + $0.15/GB volume ([Fly docs](https://fly.io/docs/about/pricing/)) | ⚠️ possible, with a volume | Comparable cost, more moving parts than a VPS for a workload with no scaling story. Volumes bill even when the machine is stopped. |
| **GitHub Actions cron** | €0 within the private-repo minutes allowance | ❌ ephemeral runners | Attractive until you notice there is nowhere to keep SQLite, and that scheduled workflows are best-effort (delays under load) and get **auto-disabled after prolonged repo inactivity** — verify the current rule before relying on it either way. Wrong tool. |
| **Cowork scheduled task** | included | ❌ | Ruled out already and still ruled out — Part 3's tool-fit flags say the cron runtime is not a Cowork job. |

### Recommendation (mine, for the owner to accept or overturn)

**Confirm local desktop for the soak, with Hetzner CX22 as the pre-committed
fallback named now** — which is exactly the fork GL-3 already wrote, so this
recommendation is "keep the plan", not a new proposal. What it adds is a
**decision rule so the fallback is not a judgement call at 2 a.m.**:

> Move to the VPS if the soak shows **either** a missed batch run that the
> host itself caused (asleep, off, rebooted mid-run), **or** more than one
> missed hourly poll in the soak window.

The case for starting local is that it costs nothing and imports no new
secrets surface — a `.env` with a live Etsy token and a Telegram bot token
stays on one machine you physically control, which fits CLAUDE.md's posture
better than copying it to a rented box. The case against is that a personal
desktop is not an always-on host and everyone knows it; the soak is the
cheapest way to convert that intuition into a measurement instead of an
argument.

**Owner decision needed (GL-3):** confirm desktop-with-fallback, or go
straight to the VPS and skip the desktop soak entirely. Going straight to the
VPS costs ~€4/month and a day of setup, and buys a soak result that
generalises to the thing you will actually run on.

---

## 1. Problem

Every pipeline stage exists, is unit-tested, and has been proven live end to
end (GL-13). **Nothing runs it on a schedule.** `run_m1_live_test.py` calls
the stages in order, by hand, and the docstring says so. Until a scheduler
drives it, the shop cannot produce a listing without the owner sitting down and
running a script — which is the negation of the project's premise.

Two things GL-13 exposed make this more than wiring:

1. **Nothing runs migrations** (GL-35). The live DB was on a stale schema and
   the failure presented as a mid-run crash three stages deep. With a human at
   the keyboard that costs a debugging cycle; at 03:00 unattended it costs a
   silent half-finished run against real APIs.
2. **Nothing reconciles the DB with the world** (GL-36, rescoped 2026-08-05).
   Rows strand in `generating`; rows claim `published` against listings that
   404. Both are harmless while a human runs each round and both are leaks
   once nobody is watching.

And Session W added a third, more general one: **the pipeline is not the only
writer to the resources it tracks.** Gelato writes to the same Etsy listing.
That assumption is baked into more than the gallery.

## 2. Success criteria

1. Two schedulable entrypoints exist — an hourly poll and a twice-daily batch
   — each a single command the host's scheduler can invoke, each exiting with
   a meaningful status code.
2. Each of the twelve stages remains **independently callable**; the
   orchestrator sequences them, it does not absorb them. No stage's logic
   moves into the runner.
3. **The two cadences cannot corrupt each other.** A batch run and a poll must
   not interleave writes to one SQLite file, and **only one process may ever
   call `getUpdates`** — Telegram's offset is a single consumer's cursor, and
   a second reader silently eats the first one's updates.
4. **GL-35:** a `schema_version`, one idempotent `migrate.py` that applies
   pending scripts in order, and a **fail-fast check at start** that refuses to
   run on a stale schema rather than discovering it mid-run. "Idempotent" must
   mean *actually* re-runnable — `migrate_v412_gallery.py` rebuilds `groups`.
5. **GL-36:** stranded `generating` rows age out, and a reconcile pass marks
   rows whose external ids no longer exist. Candidates 40/41 are repaired as
   part of proving it.
6. **The stall predicate fires** — provable only here, by temporarily lowering
   `GROUP_REVIEW_STALL_DAYS`, never by waiting 14 days.
7. **A failure is visible without an operator.** Any unhandled stage failure
   reaches the owner on Telegram, and a run that does not happen is
   detectable. This is a new DoD item and it is the difference between an
   unattended pipeline and an unobserved one.
8. **A clean overnight unattended soak** — see §6. This is the gate, not the
   merge.
9. Suite green throughout, including new tests for the runner, the lock, the
   migration runner and the reconcile pass.

## 3. Scope

**In:** the two entrypoints; the single-instance lock; stage sequencing and
per-stage error isolation; GL-35's migration runner and schema guard; GL-36's
age-out and reconcile; Telegram error surfacing; the stall-predicate proof;
host setup for whichever host §0 names; the soak and its log; tests.

**Out:**
- **GL-29 activation.** Do not wire it, do not set the flag. Listings stay
  drafts through the soak — a soak that publishes live listings is not a test,
  it is a launch.
- **GL-37.** Owner-manual and research; it does not belong in a coding session
  and it is not a runner concern.
- Any change to stage *logic*. If a stage is wrong, that is a finding to
  report, not a fix to smuggle into the orchestrator PR.
- Rewriting `run_m1_live_test.py` out of existence — it stays as the manual
  path, and it is the reference for what "in order" means.
- Landscape (GL-18), the corpus backup (GL-30), asset hygiene (GL-27).
- **Moving off SQLite.** If a host option seems to require it, that host is
  the wrong host — see §0.

## 4. Constraints

- **Live mode stays off until the soak explicitly needs it, and the soak's
  live segment is owner-approved separately.** Note the current hazard:
  `.env`'s `*_LIVE_MODE` flags are **true right now** (Session W), so anything
  run from this tree hits real APIs by default. **Flip them off before this
  session starts** — that is an owner action, Claude cannot edit `.env`.
- **CLAUDE.md §4 applies to the migration runner.** It rebuilds a table. Back
  the DB up first, show the plan, wait for an explicit "proceed".
- **One function per stage; discrete scheduled functions, not one agent
  loop.** This is a hard constraint in CLAUDE.md, not a preference.
- **The Telegram admin ID is the only access-control layer.** The runner must
  not widen it, log it, or bypass the check on any path.
- **Subagent briefs carry the command denylist**, not just a file allowlist
  (Part 3's tool-fit flags — no `git stash`, `reset --hard`, `checkout -- .`,
  `restore`, `clean`, `rebase`, `merge`, `cherry-pick`, history rewrite,
  `rm -rf` outside scratch, or any `*_LIVE_MODE` env var). Reading git state
  stays unrestricted.
- **If a constraint blocks the correct fix, stop and flag it.** The standing
  rule from GL-21, and Session W honoured it when the control listing turned
  out to be deleted — that is the bar.

## 5. Build plan

**Phase 0 — host (owner + §0).** GL-3 signed off. No code.

**Phase 1 — GL-35, the migration runner.** Standalone, mechanical, fully
specified: `schema_version`, an ordered idempotent runner, a fail-fast guard
called at the top of both entrypoints. **Do this first** because every later
phase runs against a DB and the guard is what makes "it ran" mean something.
*Subagent-suitable (Sonnet).*

**Phase 2 — the two entrypoints and the lock.** The hourly poll is largely
assembly: `run_publish_primary_group_cycle` already polls, authorises,
dispatches and advances the offset. The batch entrypoint sequences the morning
and evening stage sets. **The lock is the sharp part** — single-instance,
crash-safe (a stale lock from a killed process must not wedge the pipeline
forever), and it must guarantee the single-`getUpdates`-consumer property.
*Main thread, not a subagent — this is the correctness risk in the phase.*

**Phase 3 — GL-36, drift.** Age-out for `generating`; a reconcile pass for
rows pointing at external ids that 404; repair candidates 40/41. Note the
polarity lesson from GL-33: **positive matching only** — mark a row
`listing_missing` on a definitive 404, never on a timeout or an auth error, or
a bad afternoon at Etsy will mark the whole shop dead. *Subagent-suitable
(Sonnet) with that rule stated in the brief.*

**Phase 4 — observability.** Unhandled stage failure → Telegram, with the
stage name and the candidate id. A heartbeat or last-run record so a run that
never happened is detectable. Small, and the thing that makes the soak
readable.

**Phase 5 — the stall-predicate proof.** Lower the constant, drive a group
past the window, assert `stalled_skipped`, restore the constant. A test, then
once inside the soak.

**Phase 6 — the soak.** §6.

**Model split** per Part 3: bounded, fully-spec'd legs (1, 3, 4) run as Sonnet
subagents in parallel where files do not overlap; phase 2 stays on the main
thread. **Keep the read-only review subagent** — it has now found holes twice
that neither the implementer nor the kickoff anticipated.

## 6. The soak — what "clean" means

**Duration:** at least one full overnight covering **both** batch runs and the
hourly polls between them; ideally two nights. Live mode off unless §4's
separate approval is given.

**Pass conditions:**

1. Every scheduled invocation actually fired, at the scheduled time.
2. No run left a stage half-applied — a crash resumes or refuses, it does not
   continue from a corrupted middle (GL-16's resilience work is
   production-unproven; **this is its production proof**).
3. The lock held: no interleaved poll and batch, no double `getUpdates`
   consumption, no wedged stale lock.
4. The schema guard was exercised at least once against a deliberately stale
   DB and **refused to run**.
5. The stall predicate fired with the constant lowered.
6. A deliberately injected stage failure reached Telegram.
7. Suite green after.

**On the desktop specifically:** the soak is also testing the *machine*. Do
not disable sleep to help it pass — a soak that only passes with the power
settings changed has told you the answer is the VPS.

**Failure is information, not a setback.** GL-19 "failed correctly" and that
was recorded as a pass of the process. The same standard here: a soak that
surfaces two host defects on night one is the soak working.

## 7. Open questions for the owner

1. **GL-3:** desktop-with-fallback, or straight to the VPS? (§0)
2. **Live or dry-run soak?** Dry-run proves the scheduling and the plumbing;
   live proves the thing that has never run unattended. My read: **dry-run the
   first night, live the second**, with the live night approved separately —
   but it is your money and your listings.
3. **Soak length** — one night or two?
4. **Telegram error channel:** the same admin chat as the digests, or a
   separate one so operational noise does not sit in the review thread?

## 8. What this does *not* solve, stated so it is not discovered later

- **GL-37 still gates GL-29**, which still gates GL-11's confirmation. A clean
  soak does not make the shop publishable.
- **The unattended premise has a hole GL-37 named:** if the Creativity
  Standards fields can only be ticked by hand, every listing needs a dashboard
  visit no cron can perform. GL-7 makes the pipeline run itself; it does not
  make it *compliant* by itself. Worth resolving GL-37 before the soak's
  result gets read as "we are ready".
- **GL-32's orphan window** (a crash between Gelato's `POST` returning and the
  id being recorded) is untouched and becomes marginally more likely once runs
  are unattended.

## 9. Sign-off

- [ ] **GL-3 host decision** (§0) — desktop-with-fallback / VPS now / other
- [ ] Q2 live-or-dry soak, Q3 length, Q4 error channel (§7)
- [ ] `*_LIVE_MODE` flags set appropriately in `.env` before the session
- [ ] DB backed up before the migration runner touches it (§4)
- [ ] PRD approved — build may start

**Owner signature / date:**
