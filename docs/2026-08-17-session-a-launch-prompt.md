# Session A launch prompt — triage sweep, three planned issues, acceptance run

**Run this in Claude Code, in a terminal, at the repo root. Not in Cowork.**
Everything below needs `gh`, and `gh` is unavailable from the Cowork sandbox —
that limitation is the whole reason the sweep was written as a plan rather than
applied when it was authored.

**Predecessor:** the Telegram ack listener shipped (#142 → `92317ca`, `b7af88e`,
`f674812`). Two untracked docs are the only dirty paths:
`docs/2026-08-17-triage-sweep-plan.md` and
`docs/2026-08-17-qops-phase8-extraction-prd.md`, both amended 2026-08-17.

**Sequencing decision (owner, 2026-08-17):** this session runs **before** Phase 8.
The sweep retypes #49 into `mission:qops`, which changes Phase 8's migration set;
running P8.5 first strands it. Do not start Phase 8 work here.

```bash
claude --remote-control "qops triage sweep + acceptance run"
```

Then `/config` → enable **Push when actions required**. Steps 2, 4 and 6 below
all stop for the owner, and the phone is how those stops reach them.

---

You are running **Session A**. Three objectives, strictly ordered, each ending in
a checkable state. Objective 3 is the one that matters — the first two exist to
make it possible.

**Read first, and only these:**

1. `docs/2026-08-17-triage-sweep-plan.md` — the proposed changes and the seven
   rules. **This is the specification. Do not re-derive it**, and do not re-audit
   the backlog to satisfy yourself; the audit is done and re-doing it is how this
   session becomes a research project instead of a sweep.
2. `.qops/config.yml` — the label taxonomy under `labels:` and `validate:`. The
   file runs; the plan describes.
3. `docs/reference/loops.md` §`pickup-loop` and §`automerge-loop` — the eligibility
   conditions and what each loop may and may not do.
4. `CLAUDE.md` §"Standing owner decisions" — in particular: **activation is never
   raised as a question, recommendation or reminder.** Several issues in the sweep
   touch listing state. None of them is an invitation to ask about publishing.

**Do not read** the archived plans under `docs/archive/`. The issues are the
source of truth.

## §0 — Commit the two docs first

They are untracked, and Phase 8's P8.0 gate is "the tree is clean". A sweep that
modifies 40 issues while its own specification is uncommitted has no recoverable
before-state.

```bash
git add docs/2026-08-17-triage-sweep-plan.md docs/2026-08-17-qops-phase8-extraction-prd.md
git commit -m "docs: triage sweep plan and Phase 8 extraction PRD"
```

Then confirm `#142` is closed. If it is not, close it referencing the three
commits above.

## §1 — Objective 1: apply the sweep

Follow §Applying it in the plan, exactly, including the dry run. Four points
where an agent typically goes wrong here:

- **The dry run is not a formality.** Print every `gh issue edit` you intend to
  run, as text, and stop. The owner reads the printed diff before anything
  executes. This is a bulk operation over ~40 issues and CLAUDE.md §4 requires
  the plan shown first.
- **Six issues could not be retrieved when the plan was written** (the GitHub API
  truncates at ~85 KB). You have `gh` and can read them individually. Resolve
  them by inspection against rules R1–R7 and **include them in the printed dry
  run as a clearly marked separate block** — they are the part the owner has not
  seen a proposal for.
- **`ready:auto` is yours to propose and never to apply.** `.claude/agents/triager.md`
  forbids it and `scripts/qops_pickup.py`'s docstring names the owner as the only
  grantor. It reaches an issue in §2, by the owner's word, not as part of label
  hygiene.
- **Do not clear #90's `no-auto`** to make the Phase 7 sign-off's named candidate
  fit. The plan resolves that conflict by changing the candidate to #136 instead.
  Leaving a flag alone is the correct move.

Apply in the plan's three batches once the owner says proceed. Then run the
plan's step 4 assertion and **file it as an issue against `qops doctor`** — every
open issue carrying exactly one `type:`, one `state:`, one `gate:` and no
`gate:none` is a machine check, and the plan is explicit that it does not belong
in a human's eyes.

## §2 — Objective 2: plan three issues, no more

`ready:auto` requires `state:planned`, and planning is per-issue judgement, not
label surgery. The plan recommends **#59, #57, #71** — all pure-local, none
touching Etsy, Gelato or Replicate (R6). Hold #52 until doc-hygiene scope exists,
hold #58 until the Telegram ack path is verified.

For each of the three: write the plan **into the issue** — what done looks like,
which files, which test proves it. An unattended sortie reads the issue and
nothing else, so an issue that says "fix the orphan gap" and no more produces a
session that invents a definition of done. This is the actual work of this
objective; the label is the trivial part.

Then, and only then, ask the owner to grant `ready:auto` on the three. Report the
queue state before stopping.

## §3 — Objective 3: the acceptance run

**Subject: #136** (`digest.yml` fails daily because the `qops:status` label does
not exist). It is already `gate:machine` + `ready:auto`, it is pure local, it is
small, and it repairs a workflow failing every morning at 06:00 UTC.

The run is hands-off. That is the entire point, and the failure mode to avoid is
an agent helping.

1. Prove the wiring without spending anything first:
   `python scripts/qops_pickup.py` with **no** `--launch`. It prints what it would
   pick and starts nothing.
2. Confirm it picks #136 (least-recently-updated eligible issue — if it picks one
   of the three from §2 instead, that is correct behaviour and you should let it;
   note it and proceed).
3. Then `--launch`, and **do not intervene.** No hand-holding, no fixing its
   branch name, no writing `Closes #136` for it.
4. Observe: does it claim the issue (`state:planned` → `state:building`) *before*
   launching? Does it branch, commit, open a PR, request review, and stop? Does
   `automerge-loop` enable native auto-merge? Does the merge set `state:done` and
   drop `ready:auto`?

**Record what actually happened**, including anything that worked by accident,
in `docs/2026-08-17-acceptance-run-findings.md`. Every prior loop finding in
`docs/reference/loops.md` §Audit came from writing the observation down rather
than fixing it in passing; three of them were invisible until someone did.

If the run fails: **do not repair it inside this session.** File what broke, one
issue per finding, and stop. A repaired-in-flight loop has no observation behind
it, and the next unattended run is the one that pays.

## §4 — Close out

`python -m qops close` per the CLI, then:

- `python -m qops metrics --state` — the S-series numbers after the sweep.
- `python -m qops doctor` — clean.
- A checkpoint in the ledger usable as a handoff into Session B: what the sweep
  changed, the queue's state, what the acceptance run proved or failed to.

**Explicitly out of scope for this session:** creating `qvajda/qops`, touching
`qops/` source, migrating any issue, and any question about activating a listing.
