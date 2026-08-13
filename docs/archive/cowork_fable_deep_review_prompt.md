# Deep-review prompt pack: qhoto_printshop → first clean E2E live test

Two prompts, two tools, two sessions. Don't collapse them — the review needs
to stay read-only and skeptical; the implementation needs git/test discipline
Cowork doesn't have.

- **Part A** — paste into a **new Cowork session with Fable enabled**, this
  project folder mounted. Analysis only, no code changes.
- **Part B** — paste into **Claude Code** (not Cowork) once Part A's report
  is approved. Recommendation, not a preference: this is a multi-stage,
  test-gated coding job on a repo that already has 60+ modified files sitting
  uncommitted — that's exactly what Claude Code's git/test loop is for, and
  it's the tool the project's own SDD convention (`.superpowers/`,
  `progress.md`) already assumes.

---

## Part A — Cowork + Fable: deep review prompt

```
You're reviewing the qhoto_printshop codebase (mounted folder) before its
next live end-to-end test. Read-only session — do not edit pipeline code,
do not touch config, do not call any external API (Gelato/Etsy/Replicate/
Telegram/R2). If a check requires a live call, propose it and stop for
go-ahead instead of running it.

Context to read first, in this order:
1. CLAUDE.md (hard constraints — v4.11 architecture)
2. docs/SPEC_v4.11.md
3. docs/superpowers/specs/2026-07-16-live-test-fixes-brainstorm.md (11 known
   defects from live run #1, root-caused, most already fixed)
4. docs/cloudflare_1010_issue_investigation.md (the 1010 bot-block — a fix
   landed commits 70318a6/f2f2762, http.py rewritten on shared httpx client)
5. docs/CHANGELOG.md (tail) and .remember/today-2026-07-18.md for what's
   already been fixed today
6. `git log --oneline -30` and `git status` — there is a large uncommitted
   diff (60+ files, plus untracked .agents/.claude/) sitting on top of 17
   commits ahead of origin. Note this as a finding; don't decide for me
   whether to commit/stash/discard it.

Task: find what's still standing between here and one clean, unattended
end-to-end live run (generate → primary review → primary publish → 5x7/10x24
fan-out → their own review/publish), beyond what's already logged as fixed.
Specifically:

- Verify the 1010 fix's own claims against the actual code: is http.py really
  one shared keep-alive client, is the fake Mozilla UA really gone everywhere
  (grep all clients, not just gelato_client), does the 403/1010 backoff path
  have a test that would catch a regression, is poll_interval actually 10s+
  jitter in both group_product.py and primary_mockup.py.
- Re-check items 2, 3, 5 (Open Q5 unresolved), and 9 from the brainstorm doc —
  they were deferred/partial, not closed. Confirm whether anything committed
  since 2026-07-16 already resolves them.
- Idempotency sweep: every Gelato-create and Etsy-patch path — is there
  actually one shared create-or-reuse helper now, or still parallel paths
  that could re-diverge.
- Config/secrets sanity: confirm no real templateId/variantId is still a
  placeholder (would fail loudly per CLAUDE.md's policy, but verify the
  guard exists and is tested), confirm TELEGRAM_ADMIN_CHAT_ID is read from
  .env not hardcoded anywhere.
- Test suite: run the existing suite (pytest, no live calls) and report
  pass/fail count and anything skipped or newly broken by the uncommitted
  diff.
- Anything else that would make an unattended live run fail partway:
  error handling that swallows exceptions silently, missing retries,
  un-mocked assumptions, race conditions in the poll/backoff logic, DB
  migration gaps between schema.sql and the live db/qhoto.sqlite3.

Deliverables (write both to docs/):
1. `docs/live_test_readiness_review_2026-07-18.md` — every issue found,
   each with: root cause, evidence (file:line), severity, and a recommended
   fix (aligned with CLAUDE.md's hard constraints — flag explicitly if a
   recommendation would require changing one of them, don't just change it).
   Order by what blocks an E2E run vs. what's cosmetic/deferred-safe.
2. `docs/implementation_kickoff_prompt_2026-07-18.md` — a ready-to-paste
   prompt for a Claude Code session that will implement the fixes from (1)
   task-by-task, following this project's existing SDD convention (one
   commit per stage, test after each, final whole-diff review before
   merge — see .superpowers/sdd/progress.md for the pattern already used
   on the base-artwork-persistence branch). Sequence the fixes so nothing
   requires a live external call until the very end. Include: which issues
   are in scope, which are explicitly deferred and why, the reversibility
   rule (no real Etsy/Gelato/Telegram calls without explicit go-ahead), and
   the definition of done (one clean unattended E2E live run, per the
   review-flow steps in CLAUDE.md's aspect-ratio-group section).

Don't propose implementing anything yourself in this session — stop at the
two documents above.
```

---

## Part B — Claude Code: implementation kickoff prompt

Use the version Part A generates at
`docs/implementation_kickoff_prompt_2026-07-18.md` — it'll be scoped to the
actual findings, not written blind. If Part A hasn't run yet, don't
hand-write this one; a kickoff prompt written before the review is just
guessing at what's broken.

Once you have that file, open Claude Code in the project folder and paste
its contents as the first message, after you've read it yourself and
confirmed:
- it doesn't ask for anything that touches a real external account without
  flagging it first (per your standing reversibility rule),
- the sequencing looks right (code fixes → tests green → only then a real
  live call, with your explicit go-ahead at that boundary).

---

**Why two tools, not one:** Cowork/Fable is good at the wide, skeptical read
— pulling in every doc, cross-checking claims against code, no pressure to
start editing. Claude Code is better for what comes next — git discipline,
running the real test suite after every change, and the task-by-task
review loop this project is already using. Keeping them in separate
sessions also keeps the review honest: an agent that's about to fix code
tends to stop looking once it thinks it's found "enough."
