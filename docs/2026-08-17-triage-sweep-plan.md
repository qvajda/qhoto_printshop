# Triage sweep plan — 2026-08-17

A reviewable list of proposed label changes across every open issue. **Nothing
here has been applied.** Apply order and the dry-run command are at the bottom;
they need an explicit "proceed".

**This sweep blocks Phase 8's P8.5** (added 2026-08-17). The #49 retype below
moves an issue into `mission:qops`, changing the extraction's migration set from
12 to 13. P8.5 re-runs `gh issue list --label mission:qops --state all` rather
than trusting a count, but it must run *after* this sweep — otherwise #49 stays
here while its cohort leaves, and both trackers believe they own it. Sequencing
is therefore triage first, Phase 8 second; see
`docs/2026-08-17-qops-phase8-extraction-prd.md` §Plan.

## Why the automated runs are starving

Not because the backlog is untriaged in spirit — because two mechanical rules
are unmet:

- `.qops/config.yml` says `gate:none` "blocks `ready:auto` until it is filled in
  when the sortie is planned". **20 of 42 open issues carry `gate:none`.** They
  are structurally unpickable.
- Exactly **two** issues carry `ready:auto` today: #115 (already merged in
  `583fbbf`) and #136. So the pickup loop has a queue of one.

One issue (#108) carries **no labels at all**, which violates
`validate.require_on_open: [type, state, gate]`.

**Audit coverage:** 36 of 42 open issues were read directly. Six could not be
retrieved (GitHub API responses truncate at ~85 KB and `gh` is unavailable from
the Cowork sandbox). The rules below cover them; resolve them by inspection when
the sweep runs.

## The rules

| # | Rule |
|---|---|
| R1 | Close what is finished. A `state:done` issue that is still open is a lie in the queue. |
| R2 | Every open issue gets exactly one `type:`, one `state:`, one `gate:`. No exceptions, no `gate:none` survivors. |
| R3 | `gate:machine` = the finish line is checkable by tests or CI. `gate:taste` = the finish line is a judgement call (visual, commercial, brand, legal). When unsure, `gate:taste` — a wrong `machine` label produces an autonomous sortie that ships a taste decision. |
| R4 | `type:research` and `type:decision` are `gate:taste` by construction: their output is a finding for the owner, not a passing test. |
| R5 | `type:manual` never gets `ready:auto`, whatever its gate. If an issue is scriptable, retype it to `type:code` instead of relabelling around it. |
| R6 | No `ready:auto` on anything whose completion path calls Etsy publish, Gelato product-create or Replicate generation — CLAUDE.md forbids those without explicit go-ahead, so the sortie cannot finish unattended by definition. |
| R7 | `ready:auto` requires `state:planned`. Triage alone cannot fill the auto queue (see the sting in the tail). |

## R1 — close these two

| Issue | Why |
|---|---|
| #130 | `state:done`, `go-live-blocker`. The fix merged in `0ad16b6` (#138). Still open. |
| #112 | Phase 7 decision. ADRs 0016–0020 all exist on disk and `docs/2026-08-15-phase7-owner-signoff.md` is the sign-off. Close referencing both. |

## R2 — label the unlabelled

| Issue | Proposed |
|---|---|
| #108 — wayfinder references a `/research` subagent that doesn't exist | `type:code`, `state:triage`, `mission:qops`, `gate:machine` |

## R3/R4 — resolve the 20 `gate:none`

| Issue | Title (short) | Proposed gate | Other changes |
|---|---|---|---|
| #28 | GL-10c listing-copy template build | `gate:taste` | — |
| #31 | GL-12 deferred manual item | `gate:taste` | — |
| #37 | GL-18 landscape template inherited defect | `gate:machine` | no `ready:auto` (R6 — Gelato template) |
| #40 | GL-20 Gelato "mockups ready" poll relaxation | `gate:taste` | R4 |
| #49 | GL-24 qops ways-of-working overhaul | `gate:taste` | **`mission:qops`** (currently `post-launch`; it is qops work and therefore a Phase 8 migration item) |
| #50 | GL-25 wire Nano Banana Pro into `replicate_client` | `gate:machine` | no `ready:auto` (R6 — Replicate spend) |
| #51 | GL-26 mockup/compositor refinement | `gate:taste` | R4 |
| #52 | GL-27 asset and doc hygiene | `gate:machine` | retype `type:manual` → `type:code` (R5); `ready:auto` candidate |
| #53 | GL-28 SynthID disclosure | `gate:taste` | — |
| #55 | GL-29b programmatic activation, parked | `gate:taste` | add **`no-auto`** — activation is an owner decision and must never be raised as a prompt; `no-auto` is what stops a sortie asking |
| #57 | GL-30b cheaper now than when filed | `gate:machine` | `ready:auto` candidate |
| #58 | GL-31 stall reminder ping | `gate:machine` | `ready:auto` candidate, but blocked until the Telegram ack path is healthy |
| #59 | GL-32 the orphan gap | `gate:machine` | `ready:auto` candidate |
| #67 | GL-40 sets / bundle products | `gate:taste` | R4 |
| #68 | GL-41 listing URL frozen to Gelato's title | `gate:taste` | R4 |
| #69 | GL-42 About section media slots | `gate:taste` | — |
| #71 | GL-44 modifier-class schema change | `gate:machine` | `ready:auto` candidate |
| #90 | GL-63 subject repetition vs `brief_lint` | `gate:machine` | carries `no-auto` — see the conflict below |
| #93 | GL-66 two stranded drafts | `gate:taste` | — |
| #94 | GL-67 bringing an existing design up to standard | `gate:taste` | R4 |

## One conflict worth resolving before the acceptance run

The Phase 7 sign-off names the acceptance run subject as "a small open issue that
is pure local code (**GL-63 class**)". GL-63 is #90, and #90 carries `no-auto` —
so the named candidate is excluded by its own label.

Recommendation: **use #136 instead** (`digest.yml` fails daily because the
`qops:status` label doesn't exist). It is already `gate:machine` + `ready:auto`,
it is pure local, it is small, and it fixes a workflow that has been failing
every morning at 06:00 UTC. Leave #90's `no-auto` alone rather than clearing a
flag to make a plan fit.

## The sting in the tail

R7 means this sweep does **not** fill the auto queue. `ready:auto` needs
`state:planned`, and planning is a per-issue act of judgement — that is the work,
and it is not label surgery. Five `ready:auto` candidates fall out of the table
above (#52, #57, #58, #59, #71).

Do not plan all five. Recommendation: **plan three at most** (#59, #57, #71 —
all pure-local, none touching a vendor endpoint), leave #52 until the doc-hygiene
scope is written down, and hold #58 until the Telegram ack path is verified. A
queue of three that all complete is worth more than twenty that reveal the
planning was the bottleneck.

## Applying it

Reversibility: label changes are individually reversible, closing an issue is
reversible, and this is a bulk operation over ~40 issues — so it runs dry first.

1. Dry run, from the repo (needs `gh`, so Claude Code or a terminal, **not**
   Cowork): print every proposed `gh issue edit` without executing.
2. Owner reads the printed diff.
3. Explicit "proceed" → apply in three batches: R1 closes, then R2/R3 labels,
   then the `state:planned` promotions.
4. `gh issue list --state open --json number,labels` afterwards; assert every
   open issue has one `type:`, one `state:`, one `gate:` and no `gate:none`. That
   assertion belongs in `qops doctor`, not in a human's eyes — file it.

The six unaudited issues get resolved by inspection at step 2.
