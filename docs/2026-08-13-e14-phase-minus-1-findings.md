# E14 Phase −1 — S1/S2 measured retroactively, and the scope decision they feed

**Date:** 2026-08-13 · **Session:** E14 · **Feeds:** PRD v3 §2.1, §5 E3, decision 30.
**Status:** measurement complete for S1 and S2. **The resume rate is not
retroactively measurable and is reported as such, not proxied.**

The retroactive route worked. `~/.claude/projects/` holds **95 JSONL transcripts**
for this repo across two project directories (the main tree and the
`.claude/worktrees/gl7-cron-orchestrator` tree), **88 of them started on or after
2026-07-14**. The prospective week in PRD §7 Phase −1 is **not needed for S1 or
S2**; it is still needed for one number, named in §3.

The analysis script is throwaway and **is not committed**, same rule as E13's
corpus extractor. `qops metrics` supersedes it in Phase 4. What has to survive is
the method below.

---

## 1. Method, stated so the numbers can be challenged

| Term | Definition used |
|---|---|
| Session | one `*.jsonl` transcript whose first `user`/`assistant` record is on or after 2026-07-14 |
| Main thread | records with `isSidechain` falsy. **Subagent traffic is excluded** — a subagent's reads are not the owner's re-orientation cost |
| Read | a `tool_use` block named `Read` or `NotebookRead` |
| Productive tool call | `Write` · `Edit` · `MultiEdit` · `NotebookEdit`, or a `Bash`/`PowerShell` command matching `git commit`, `pytest`, `-m pytest`, `-m unittest`, `npm test` |
| S1 | count of Reads strictly before the first productive call |
| >200-line read | a Read whose returned `file.content` carries more than 200 newlines, occurring before the first productive call |

Two conservative choices worth naming: `Bash` reads (`cat`, `sed -n`, `head`) are
**not** counted as reads, so S1 is a floor rather than a ceiling — and §1.1 of the
PRD records that the board specifically has to be read by `sed`, so the
undercount is concentrated exactly where the problem is worst. And a session with
no productive call at all is reported separately rather than scored as zero.

---

## 2. S1 — reads before the first productive tool call

**Main tree, 79 sessions since 2026-07-14. 71 reached a productive call; 8 (10%)
never did.**

| Statistic | Value |
|---|---|
| **Median** | **4 reads** |
| Mean | 4.90 |
| p25 / p75 | 1 / 7 |
| Range | 0 – 19 |

Distribution, which is the part a median hides:

| Reads before first productive call | Sessions | Share |
|---|---|---|
| 0 | 14 | 20% |
| 1–2 | 11 | 15% |
| 3–5 | 20 | 28% |
| 6–10 | 19 | 27% |
| 11–20 | 7 | 10% |

**43 of 71 sessions (61%) included at least one >200-line read before doing
anything productive.** That is the headline: the cost is not the count, it is that
a majority of sessions pay a large-file read to orient, and it is a floor because
`sed`-ranged board reads are not counted.

The worktree project directory (9 sessions, GL-7 cron work) is worse on both
axes — median 5, and **9 of 9** included a >200-line read — which is consistent
with a fresh tree having no accumulated context.

**Three shapes in that distribution, each meaning something different.**

1. **The 20% at zero reads** are mostly short sessions that opened by running a
   command or editing a file already named in the prompt. They are the existing
   best case and the brief cannot improve them.
2. **The 37% at 6+ reads** are the target. This is where a `SessionStart` brief
   replaces an orientation sweep.
3. **The 8 sessions with no productive call at all** are not noise. Over 31 days,
   10% of sessions read, discussed and ended without writing, editing, testing or
   committing anything. Some are legitimately research or review sessions; some
   are the failure mode this overhaul exists to remove. **This distinction is not
   recoverable from the transcripts** and is flagged rather than guessed at.

---

## 3. Sessions per day — measured, and it corrects §2.1 term A by 2.4×

| | PRD v3 §2.1 | **Measured** |
|---|---|---|
| Basis | 43 kickoff-class docs ÷ 31 days | 88 transcripts, 79 in the main tree |
| Sessions per **calendar** day | 1.39 | **2.55** (main tree) · 2.84 including the worktree |
| Sessions per **active** day | — | **3.29** (24 active days of 31) |

**The PRD's 1.39 is a proxy and it undercounts sessions by roughly 2×.** §0 of
this session flagged it as a proxy presented as a measurement; this is the size of
the error. It moves term A *up*, which is the favourable direction, and it is
recorded here with its command so it is not asserted again.

Per-day session counts (main tree) for the record: 07-14 **6**, 07-15 **8**, 07-16
1, 07-17 6, 07-18 5, 07-19 4, 07-21 4, 07-22 2, 07-23 4, 07-24 1, 07-25 1, 07-26 2,
07-28 3, 07-29 4, 07-30 3, 07-31 5, 08-01 4, 08-02 1, 08-04 2, 08-06 1, 08-10 5,
08-11 2, 08-12 3, 08-13 2. **Seven days of the 31 had no session at all.**

---

## 4. S2 — kickoff-class docs. **43 confirmed, not corrected**

```
git log --since=2026-07-14 --diff-filter=A --name-only --format= -- \
  'docs/*kickoff*' 'docs/*session-prompt*' 'docs/*launch*' 'docs/*brief*' 'docs/*runbook*' \
  | sort -u | grep -c .
→ 43
```

E13's figure reproduces exactly. Read against §3, its meaning changes: **43
kickoff-class docs against 88 sessions means roughly one session in two is
launched by a hand-written document.** That is a better statement of the
copy-paste ritual than the raw count, and it is the criterion S2 should be
measured against in Phase 4.

---

## 5. Resumes per day — **not retroactively measurable. Stated plainly.**

This is the number §2.1's largest term rests on, and **the transcripts do not
record it.** Three independent instruments were checked and all three fail:

| Instrument | Result |
|---|---|
| `entrypoint` field on every record | records the *host* — `sdk-cli` (17,785), `claude-desktop` (9,736), `cli` (81). **Never the resume flag** |
| Session forking | `--resume` **appends to the same `sessionId` file**. Verified: 27,608 record UUIDs across 95 files, **0 shared between files**. There is no second file to count |
| Compaction / continuation markers | `"isCompactSummary":true` → **0 occurrences**; "session is being continued from a previous conversation" → **0 files**; usage-limit strings → **0 files** |

`~/.claude.json` keeps only `lastSessionId` and `lastGracefulShutdown` — one
value, not a history. PowerShell's `ConsoleHost_history.txt` holds **24 `claude`
invocations total**, one of them with `--resume`, against 88 sessions; it is a
rolling capped buffer and most sessions launched from the desktop app never touch
it. **It is not a census and is not used as one.**

**A proxy exists and is deliberately not promoted to a measurement.** 44 of 79
transcripts contain at least one gap over 30 minutes between consecutive
main-thread messages, 98 such gaps in total (4.08 per active day). A gap is
equally consistent with a resume and with the owner walking away from a live
session; the two are indistinguishable in this data. **It is recorded as an upper
bound on resumes, nothing more.**

**What can honestly be said instead.** Term B prices *re-orientation*, and a
session start pays that whether it is a resume or a fresh start. Session starts
are measured: **3.29 per active day.** So the PRD's assumed 1.5 resumes/day is no
longer floating — it sits inside a measured envelope of 0 to 3.29, at about 46% of
session starts. That does not make it correct; it makes it bounded, and the bound
is what the scope decision needs.

---

## 6. §2.1 recomputed on measured inputs

Same divisor, same inherited 1,367 tok/min conversion rate (still the one input
that is neither measured nor sourced — PRD §2.1 defect 3, unchanged). Term A's
saving per session is unchanged at **3,541 tok** (24,582 B ÷ 4 = 6,146 tok today;
150-line cap → 2,604). Payback is stated in **active days**, since it only accrues
on days work happens, with the calendar-day equivalent at the measured 24-of-31
ratio.

| Scenario | Term A / active day | Term B / active day | Total | Reclaimed | Payback (8.25h) |
|---|---|---|---|---|---|
| **PRD v3 as written**, 1.5 resumes/day, mid | 3,541 × 3.29 = **11,650** | 12k–30k, mid 21,000 | **32,650** | 23.9 min = 0.398 h | **20.7 active days ≈ 27 calendar days ≈ 3.8 weeks** |
| **Worst case** — 1.0 resume/day, low end | 11,650 | 8,000 | 19,650 | 14.4 min = 0.240 h | **34.4 active days ≈ 44 calendar days ≈ 6.3 weeks** |
| **Floor** — term B is zero, brief saves nothing on resume | 11,650 | 0 | 11,650 | 8.5 min = 0.142 h | **58 active days ≈ 75 calendar days ≈ 10.7 weeks** |

**The measurement moved the number in one direction: better.** PRD v3 claimed 5.2
weeks central and 10.5 weeks worst. On measured session frequency the central case
is **3.8 weeks** and the worst realistic case is **6.3 weeks**. The 10.7-week floor
requires term B to be exactly zero — i.e. that a `SessionStart` brief saves nothing
at all on re-orientation — which §2's 61% >200-line-read figure contradicts
directly.

**Two things this does not fix.** Term B's rate is still not measured, only
bounded; and §2.1's failure mode 2 stands untouched — the 150-line cap has to be a
`groom.yml` check, because term A is now the *larger* half of the total and it goes
to zero within 20 days without enforcement. Term A being 11,650 of 32,650 rather
than 4,912 of 25,900 makes that check **more** load-bearing, not less.

---

## 7. What this says about scope — the owner's call

**The measurement does not veto the full build, and it does not merely fail to
veto it: it strengthens the case.** Decision 30 put the veto condition as "if it
comes back saying resumes are rare and cheap". Resumes could not be counted, but
the thing they were standing in for — how often the re-orientation cost is paid —
is **2.4× more frequent than the PRD assumed**, and 61% of sessions pay it with a
large-file read.

Recommendation, for the owner to take or reject: **full build**. Payback lands
between 3.8 and 6.3 weeks under every scenario in the measured envelope, against
the PRD's own stop-rule of four 5h windows. The substrate-only fallback (≈3h,
hooks + brief + resume + issues) remains the stop-rule if Phase 4 overruns; it does
not need to be chosen up front.

Three amendments this document asks the PRD to take:

1. **§2.1 term A's "1.39 sessions/day (measured)" is replaced by 3.29 per active
   day**, with the transcript count as its command. The kickoff-doc proxy is
   struck.
2. **§2.1 term B is restated as bounded, not assumed** — 0 to 3.29 re-orientations
   per active day, with 1.5 as the working point and the reason it cannot be
   measured retroactively recorded in §5 above, so a future session does not spend
   another hour rediscovering it.
3. **S1's Phase 4 definition adopts §1's method verbatim**, including the
   subagent exclusion and the `Bash`-reads-not-counted floor, so that `qops
   metrics` and this baseline measure the same thing. A baseline measured one way
   and re-measured another is not a baseline.

---

## 8. Reproduction

```bash
# S1, sessions/day  (throwaway; not committed)
python <analysis>.py   # walks ~/.claude/projects/*qhoto-printshop*/*.jsonl

# S2
git log --since=2026-07-14 --diff-filter=A --name-only --format= -- \
  'docs/*kickoff*' 'docs/*session-prompt*' 'docs/*launch*' 'docs/*brief*' 'docs/*runbook*' \
  | sort -u | grep -c .

# resume-rate instruments, all three negative
grep -c '"isCompactSummary":true' ~/.claude/projects/*qhoto-printshop/*.jsonl
grep -l "session is being continued from a previous conversation" ~/.claude/projects/*qhoto-printshop/*.jsonl
python -c "..."   # uuid set-intersection across files → 0
```

**measured-on: 2026-08-13, at board commit `17f35cf`, working tree dirty
(38 paths).**
