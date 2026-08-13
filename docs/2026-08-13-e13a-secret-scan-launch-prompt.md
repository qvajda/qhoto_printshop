# E13a launch prompt — secret scan of git history (Claude Code, standalone)

**How to use:** open Claude Code in `qhoto_printshop` on `master`, and paste
everything below the line as the first message. Owner decision 2026-08-13: this
runs as its own short session, split out of `docs/2026-08-13-e13-kickoff.md` §7a.

---

You are running **E13a**, a standalone short session with exactly one job: a
one-time secret scan of this repository's full git history. This is Phase 0's
last outstanding item from `docs/2026-07-26-ways-of-working-overhaul-prd-v2.md`,
open since 2026-07-26, and the PRD calls it the highest-value item in the whole
plan. Full context: `docs/2026-08-13-e13-kickoff.md` §7a — read it before you
start, then read `CLAUDE.md` §4 (reversibility), which governs step 4 below.

**Why it matters here specifically:** the repo is **public**
(`github.com/qvajda/qhoto_printshop`). `HEAD` is clean — only `.env.example` and
a token-refresh *script* are tracked, `.env` and `.env.*` are gitignored — but
live Etsy OAuth, Gelato, Replicate and Telegram credentials have moved through
this project's working life across ~392 commits, 12 remote branches and ~20
`pre-qops-2026-07-26-*` tags. The scan is about history, not about `HEAD`.

## Scope

**In:** scan every reachable object in history, triage any hits, report the
result either way, and — only on an owner "proceed" — assist with rotation.

**Out, and do not drift into these:**

- **History rewriting is not in this session.** `filter-repo`, `filter-branch`,
  BFG, force-pushes: none of them. A public repo's history may already be
  cloned, forked or cached by third parties, so a rewrite does not un-leak
  anything — it only changes who can find it easily. Report, rotate, *then*
  decide, in a separate session.
- **No qops work.** Corpus re-extraction, the references research pass and the
  orchard runtime decision are E13, not E13a. If you find yourself editing
  `.qops/`, stop.
- **No pipeline work.** GL-53's stage loops, GL-66/67/73, GL-65 — all carried
  backlog, none of it belongs here.
- **Nothing touching activation or publishing** (standing owner decision,
  `CLAUDE.md`).

## Steps

1. **Get complete history first, or the scan is partial and you won't know it.**
   `git fetch --all --tags --prune` before scanning. Local refs alone miss
   commits reachable only from origin branches, and the `pre-qops-*` tags exist
   precisely because several branches were never merged. State in the report how
   many refs and commits the scan actually covered — a scan whose coverage is
   unstated is not evidence.
2. **Run `gitleaks detect` over full history** (`--redact`, report to a file in
   `outputs/`, do not paste raw secret values into the transcript or into any
   committed document). If `gitleaks` is not on PATH, install it or use an
   equivalent full-history scanner — say which you used and why. Then do a
   **second, independent pass** with a targeted `git log -pS` / `git grep`
   sweep over the credential names this project actually uses, because a
   scanner's ruleset is not the same instrument as a known-key search:
   `ETSY_API_KEY`, `ETSY_API_SECRET`, `ETSY_ACCESS_TOKEN`, `ETSY_REFRESH_TOKEN`,
   `GELATO_API_KEY`, `GELATO_STORE_ID`, `REPLICATE_API_TOKEN`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`, `ALLOWED_TELEGRAM_USER_ID`,
   `ANTHROPIC_API_KEY`, plus any `R2_*` keys. Two instruments, because
   `CLAUDE.md`'s standing lesson is that a clean status code from one tool is
   not a measurement.
   **Treat `TELEGRAM_ADMIN_CHAT_ID` / `ALLOWED_TELEGRAM_USER_ID` as
   credentials, not config** — `CLAUDE.md` is explicit that the admin chat ID is
   the bot's only access-control layer and gets the same care as an API key.
3. **Triage every hit into one of three buckets, with the commit SHA, path and
   date for each:** (a) a real live credential, (b) a revoked/rotated or
   sandbox/test value, (c) a false positive (placeholder, `.env.example` line,
   fixture, hash that looks like a key). Say which bucket and why. Do not
   collapse (b) into (a) — the response differs — and do not assume (c) without
   checking what the value was at the time.
4. **If and only if bucket (a) is non-empty: stop and report before doing
   anything.** Rotation is an action against live external accounts, so
   `CLAUDE.md` §4 applies — show the plan, name the specific credential and
   provider, flag what is irreversible, and wait for an explicit "proceed". Do
   not bundle rotation into this session's go-ahead; the go-ahead you have
   covers scanning only. When a proceed comes: **rotate first, before anything
   else is considered**, and note that rotating `ETSY_*` invalidates the current
   OAuth token pair (`refresh_etsy_token.py`, `etsy_oauth_authorize.py` /
   `etsy_oauth_exchange.py` are the re-auth path) and that a rotated
   `TELEGRAM_BOT_TOKEN` silently kills the digest until `.env` is updated.
5. **Write the result down either way.** `docs/2026-08-13-e13a-findings.md`,
   redacted: what was scanned (refs, commits, tools, ruleset), what was found by
   bucket, what was rotated if anything, and what is explicitly deferred
   (history rewriting). **A clean scan is a finding and gets recorded** — if it
   isn't written down, this row reopens in three weeks and someone pays for it
   again.
6. **Close the loop on the board and the PRD.** Mark PRD v2 Phase 0's secret-scan
   item done in `docs/2026-08-13-e13-kickoff.md` §7a (leave §7b, the
   `.remember/` + `.superpowers/sdd/` snapshot, open — it is not this session's
   job), and add a dated line to the planner block in
   `docs/2026-07-22-go-live-plan-of-attack.md`. Commit the findings doc; **do
   not commit the raw scan output.**

## Done when

Coverage stated, two independent passes run, every hit triaged into a bucket
with evidence, findings doc committed redacted, and either bucket (a) is empty
or an owner proceed has been requested for a named credential. **No history
rewritten. No rotation without an explicit proceed.**

If the scan is clean and you finish early, **stop** — do not pick up §7b or any
E13 work to fill the time. One session, one observable.
