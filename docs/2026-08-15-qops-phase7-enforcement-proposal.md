# Phase 7 proposal — make the workflow hold without the owner sequencing it

Status: **proposal**. Nothing here is built. Five decisions are requested at the
end; each names the ADR it becomes.

Where this lives: **this repo**, `docs/`. ADR-0015 says qops's own work moves to
the plugin repo, and the plugin repo does not exist — creating it is a separate
outward-facing act that was not authorised. The ADRs proposed here govern how
*this* repo is worked today, so they are written here and carry `mission:qops`,
which is already the migration query.

## 0. What the acceptance sortie proved, and what it did not

The substrate held. `qops guard` blocked a master push during this very session
(it blocked `git push origin --delete <merged-branch>` — a false positive, noted
in §1). `qops doctor` refused hand-edited YAML. The gate was green on 21 of 21
review requests, 0 without it. CLAUDE.md is 136 lines against a 150 cap.

The skill layer failed, three times, all from the same root: **`skills-lock.json`
records `source` and `computedHash` and no upstream ref.** There is no commit,
tag or date in the lock. Each `skills add` took whatever `main` was at that
minute, and nothing wrote down which minute. So:

- `grill-me` was pinned without `grilling`. `grill-me` is a six-line wrapper
  whose entire body is "Run a `/grilling` session."
- `tdd` referenced `codebase-design`; the local copy is still named
  `domain-modeling`, its pre-rename name.
- 19 skill directories are installed. ADR-0013 accepted **eleven** and said the
  count was the mitigation. The count has been breached and no check noticed.

Drift is not the problem. **Unobservable drift is.** A lock that cannot say what
it pinned cannot detect that upstream moved.

The sequencing failure is separate and is what §1 addresses: the flow is written
in skill bodies and in `docs/reference/qops-cheatsheet.md`, and nothing makes it
happen. CLAUDE.md already says why that never works: *an instruction in a prompt
is a preference, not a control.*

## 1. Enforcement

### 1a. Remove `disable-model-invocation` from `to-spec` and `triage`

**Split the answer.** These two are not the same risk.

`to-spec` — **remove it.** What it blocks today: the agent noticing a spec is
missing and writing one. That is the exact reflex we want. What it would let
through: `to-spec` does not only synthesise, it **publishes to the tracker**.
Model-invocable, it can open issues unprompted, mid-conversation, from a
half-formed discussion. Mitigation: allow the invocation, gate the publish —
the skill may draft, and the issue create stays an owner-confirmed step. That
keeps the reflex and drops the blast radius to zero.

`triage` — **keep it owner-only.** It walks a state machine over many issues and
relabels them in a batch. An agent that mis-reads the taxonomy relabels twenty
issues, and `gh issue list` is the source of truth, so a bad batch corrupts the
thing every future session reads first. The reflex we want ("a spec is missing")
is not what triage provides.

Also true and worth stating: seven skills carry this flag, including `wayfinder`
and `to-tickets`. Deciding it per-skill by hand is the sprawl. Under §3 option B
this becomes one qops-native rule instead of seven frontmatter lines.

### 1b. PreToolUse hook: block Edit/Write off a `<type>/<issue#>-<slug>` branch

Blocks: editing on `master`; editing on a branch with no issue behind it; the
"I'll just fix this quickly" path that produced the untracked work in three
past sessions.

**What it blocks by mistake — the part that matters:**

| Legitimate work | Why it trips |
|---|---|
| `docs/phase6-baseline`, `proto/mockup-scene-prototype`, `gl45-telegram-drops`, `worktree-gl7-cron-orchestrator` | Four of the 15 remote branch names in this repo carry no issue number. The convention is aspirational, not current. |
| Writing the spec that will *create* the issue | Chicken-and-egg. You cannot branch on an issue number you have not opened. |
| `.qops/` machine state, `scratchpad/`, generated assets | Hook fires on any Write. The hooks themselves write here. |
| Detached HEAD during a rebase, bisect or `gh pr checkout` | No branch name to match. |
| Live-run sessions that write `assets/mockups/inflow/` by hand | Owner-driven, not a code change. |
| A multi-issue branch — a sweep across four stage loops (GL-54 shape) | One branch, several issues; the pattern encodes exactly one. |

Recommendation: **build it, scoped, with an escape that is recorded rather than
silent.** Scope the block to tracked files under `pipeline/`, `scripts/`,
`qops/`, `tests/`. Exempt `docs/`, `.qops/`, untracked files and the scratchpad.
Accept a `no-issue/<slug>` branch prefix that passes the hook and writes a
ledger row, so the escape is countable. An escape hatch nobody can count is how
people learn to bypass guards; one that shows up in the brief is a nudge.

### 1c. Stop hook refusing to end on a dirty tree or an unmerged branch

**Recommend against, as specified.** Downgrade it from refuse to record.

What refusing blocks by mistake: work deliberately parked (this repo did it
twice — GL-6 attempt 1 was left uncommitted on purpose pending research);
sessions the owner interrupts; multi-session sorties where an open branch is the
correct state; live-run sessions holding generated assets; research sessions
whose output is notes. In every one of those the tree is *supposed* to be dirty,
and the hook's only move is to refuse to stop — which is not a nudge, it is a
session you cannot end. Stop hooks also re-enter themselves; the loop guard is
`stop_hook_active`, and a hook that must be defused to work is one the owner
will disable inside a week.

Cheaper and stronger: on Stop, write the unfinished state to the ledger
(branch, ahead/behind, dirty paths, open PR). The next `SessionStart` brief
**leads** with it. The brief is 83 tokens and is read every session; the nag
costs nothing and cannot strand anyone. Enforcement moves to the place that is
already always read.

## 2. Routing — when a human is required

Today every issue gets the same treatment regardless of its gate, which is how a
lint fix consumed an owner session. The labels to decide it already exist in
`.qops/config.yml` (`gate: [machine, taste, none]`, `mission:`, `ready:auto`).
Nothing reads them for routing.

**The rule.**

1. **Mission level** (`type:epic`, or any change to an ADR, a hard constraint,
   or the spec) — **interview.** Full grilling round, owner present, before any
   issue is written. A mission mis-set costs every sortie under it.
2. **Sortie level** (one issue, one session) — **propose-and-pick.** One round,
   at most four options, each with a recommendation. No interview. If the agent
   cannot write acceptance criteria without a second round, that is the signal
   the item is a mission, not a sortie — escalate to rule 1 rather than asking
   twice.
3. **`gate:machine`** — **no owner contact before review.** Plan, build, PR, CI.
   The owner meets it at review, once, green. This is the rule the lint fix
   needed.
4. **`gate:taste`** — the owner sees the artifact, not the diff. A digest entry,
   a render, a draft. Machine gate green first: a taste review is only
   legitimate once every machine-checkable precondition passes (already the
   stated design of `gate.yml`).
5. **Escalation is always allowed, downgrade is not.** An agent may promote
   `gate:machine` to `taste` if the work touches a constraint. It may never
   demote `taste` to `machine`.

Enforcement: `qops brief` prints the routing verdict for the active issue, and
`ready:auto` + `gate:machine` means proceed. `validate.require_on_open` already
forces a `gate:` label on every open issue, so the input exists.

→ **ADR-0017.**

## 3. Skills strategy

### The `grill-me` claim — checked, does not hold

Upstream's README lists `grill-me` as an active user-invoked skill and
`grilling` as the model-invoked engine behind `grill-me`, `grill-with-docs`,
`triage`, `wayfinder` and `improve-codebase-architecture`. Nothing deprecates or
discourages it. Search turns up recommendations *for* it and none against.

So the question "why does a core piece of the overhaul route through a skill its
author disowns" does not arise — but the better version does: **we do not route
through `grill-me` at all.** `grill-me` is a six-line wrapper. What the design
depends on is `grilling` — one interview procedure, a few dozen lines, which we
failed to install. We took a dependency on a shim and left the body behind. That
is an argument about packaging, and it points at option B.

### The three options, costed

**A. Keep adopting external skills as-is.**
Cost: an unbounded rename tax, paid at random, mid-session, by the owner. This
session paid it twice. The lock cannot detect it (no ref), the count is already
19 against ADR-0013's eleven, and nothing was displaced — ADR-0013 said
displacement was owed and it is still owed. Recurring, unpredictable, and it
lands on the scarce resource. **Reject.**

**B. qops-native equivalents, merely inspired.**
What the set must cover, from what is actually routed through today:
1. **Interview** (`grilling`) — the design-tree round mechanic.
2. **Spec synthesis → issue** (`to-spec`, `to-tickets`) — must write the qops
   label taxonomy, not a generic one.
3. **Triage state machine** (`triage`) — the taxonomy is already in
   `.qops/config.yml`; the external skill re-declares its own.
4. **TDD loop** (`tdd`) — must know `gate_command` and the M1 convention.
5. **Review** (`code-review`) — must read the gate, not re-derive it.
6. **Vocabulary and ADR discipline** (`domain-modeling`/`codebase-design`) —
   must know `docs/adr/` numbering and `CONTEXT.md`.
7. **Wayfinding** (`wayfinder`) — collapses into `qops brief` + §2 routing.
Cost: roughly six skill bodies, one-time, plus prose nothing tests. Benefit: they
read `.qops/config.yml`, write the ledger, and know the label vocabulary — which
an external skill structurally cannot. Seven `disable-model-invocation` lines
collapse into one rule. And the count becomes checkable: `qops doctor` can
assert the installed set equals the declared set.

**C. Delete the layer; substrate carries the workflow.** (incumbent)
Cost: near zero to execute. **The argument against, which it is owed:** a hook is
a gate, and a gate can only say no. It cannot say what to do next. The one
session where the flow held was the session where the owner supplied the
sequencing by hand; deleting the skill layer does not close that gap, it makes
the gap silent. The owner would go on typing the sequence, only now with nothing
written down to type.

But C is not as weak as that makes it sound, and the honest framing is not
"skills or no skills". Hooks can **inject context**, not only refuse — a
PreToolUse or SessionStart hook can hand the model the next step at the moment
it matters, which beats a library the model must first decide to consult. The
real axis is *instruction-at-the-moment* versus *instruction-in-a-library*, and
the substrate wins on the first.

**Recommendation: B, sized by C.** Write the three bodies that carry sequencing
and cannot be a one-line hook message — interview, spec→issue, triage. Let the
substrate carry the rest by injecting the next step. Uninstall everything not in
the declared set, and pay ADR-0013's outstanding displacement in the same pass.
Add a ref to `skills-lock.json` for whatever external skills survive (the
Replicate set is genuinely external domain knowledge and should stay), so drift
becomes detectable instead of discovered.

→ **ADR-0018**, superseding ADR-0013.

## 4. Output style — ASD-STE100

**Where it fits:** written artifacts. Commit messages, issue bodies, PR bodies,
ADR *Decision* sections, generated docs, the digest. These are read later, by
someone without the conversation, and that is exactly the readership STE was
designed for.

**Where it does not:** dialogue. STE has one meaning per word and no register for
uncertainty, and the §2 interview depends on hedging — "I think this is a
mission, not a sortie" is the sentence that saves an owner session. Also excluded:
code comments carrying reasoning (this repo's comments are load-bearing
explanatory prose — `.qops/config.yml` and the workflow templates are the house
style and STE would flatten them), and the ADR *Context* section, where nuance is
the payload.

**How it gets enforced rather than requested.** An output style is a file of
prose handed to the model. That is a preference, and this repo has already
learned what preferences are worth: `DISCLOSURE_TEXT` was emptied and 27 of 27
drafts kept the sentence. So the style file is the *statement*, and the control
is a check: `qops lint prose` in `gate.yml`, run over the commit messages on the
branch and the PR body.

What the check can enforce: sentence length cap, one topic per sentence, active
voice heuristic, a banned-word list (`simply`, `just`, `leverage`, `utilize`,
`should probably`, `basically`), no ambiguous pronoun openings.

What it cannot: **the ASD-STE100 approved dictionary is licensed by ASD and is
not redistributable.** This repo is public (ADR-0012). We implement the *rules*,
we do not vendor the vocabulary, and the style file says so — otherwise the
first contributor to read "ASD-STE100" will expect a dictionary that is not
there.

Lowest-value-first: ship the lint on commit and PR bodies only. If the owner
reads six weeks of them and the prose is better, extend to generated docs.

→ ADR only if the decision "prose is checked in CI" is accepted. The style file
itself is not an ADR.

## 5. Rollback, costed

**What reverting loses**, on figures:

| Measure | Value | Source |
|---|---|---|
| Resume cost, median file reads to re-orient | **5 → 1** | `metrics.s1`, pre ≤2026-08-12 (78 scored) vs ≥2026-08-13 (5 scored) |
| Sessions needing a large re-read | **60% → 20%** | same |
| CLAUDE.md, every session, unasked | **372 → 136 lines** (2156 tokens), cap enforced | S10 |
| Session brief | 83 tokens, replacing the 5-read resume | S10 |
| Review requests reaching the owner without a green gate | **0 of 21** | S4 |
| Broken doc citations caught | 13 of 15, by the check alone | guard.yml |
| Master commits and force-pushes blocked | working, incl. once this session | guard |
| CI per PR | 15.7 → 8.7 runner-minutes | PR #109 vs #111 |

**What reverting recovers:** the skill-layer maintenance surface, and nothing
else. That is the whole recovery. Note what it is *not*: the 89 archived docs
stay archived, the issues stay the source of truth, branch protection is a
GitHub setting and is independent.

**What the revert itself costs:** unwiring five hooks from `.claude/settings.json`,
deleting five workflows, restoring a 372-line CLAUDE.md, retracting ADRs
0013–0016, and re-learning root cause 1 — the planning document that reached
401 KB. The revert is a day, and the day buys back a maintenance surface that
option 3 removes for an hour.

**Decision: reject rollback. Adopt §3's deletion path instead.** The two are not
close. Every number above belongs to the substrate; the skill layer has no
number at all — not one metric moved because of it, in either direction. A
rollback would delete the half that measures and keep nothing. §3 deletes the
half that costs.

**Two honesty notes on the figures.**

- The post window is `n=5` scored sessions. That is a signal, not a
  result. Re-decide at `n ≥ 20`, which is roughly two more weeks.
- `qops metrics` **cannot produce this comparison from the command line.**
  `s1()` takes `since`/`until` (`qops/metrics.py:138`) but `main()` parses only
  `--state` and `--json` (`qops/metrics.py:261`), so the flags are unreachable.
  I called the function directly to get the table above. The instrument that
  decides whether to keep the overhaul cannot currently be pointed at a window —
  fix that before the `n ≥ 20` re-decision, or the re-decision will be an
  impression again. It is a one-line argparse fix and it is the first sortie
  I would file.

## Decisions requested

1. `to-spec` becomes model-invocable with the publish step owner-gated; `triage`
   stays owner-only. → part of ADR-0019.
2. Build the PreToolUse branch guard, scoped to `pipeline/ scripts/ qops/ tests/`,
   with a counted `no-issue/` escape. → ADR-0019.
3. Stop hook records unfinished state to the ledger and the brief leads with it.
   It does not refuse. → ADR-0019.
4. Adopt the routing rule. → **ADR-0017**.
5. Adopt option B sized by C; uninstall the undeclared skills; add a ref to the
   lock. → **ADR-0018**, superseding ADR-0013.
6. Rollback rejected on the figures; re-decide at `n ≥ 20`. → recorded on the
   Phase 6 issue and as `revisit-after` on ADR-0013, not a new ADR.
7. STE: accept "prose is checked in CI" or decline it. Style file either way is
   not an ADR.

Sortie to file first regardless of the above: wire `--since`/`--until` into
`qops metrics`. Everything in §5 depends on it.
