# qops cheatsheet — which command, when

**Cold storage.** Not loaded into any session. Read it when you need it; it is
here so you never have to guess which skill to type.

**If you only remember one thing:** start work by reading the brief and the issue.
Everything below is for when that isn't enough.

```bash
claude --remote-control "<what you're doing>"   # then /config → Push when actions required
python -m qops brief                            # where you are, ≤400 tokens
gh issue list --state open                       # what's open
gh issue view <n>                                # the plan lives in the issue body
```

---

## Which command, when

**Lost? `/ask-matt`.** It routes you to the right skill for your situation. Use it
instead of reading this table.

| You want to… | Type this |
|---|---|
| Decide *what* to build, when the design isn't settled | `/grill-me` — interviews you until every branch is resolved |
| Same, and the project needs new vocabulary or an ADR out of it | `/grill-with-docs` — grills, then updates `CONTEXT.md` and `docs/adr/` inline |
| Write up what you just decided, onto the issue tracker | `/to-spec` — no interview, synthesises the conversation and publishes |
| Split a plan into several dependent tickets | `/to-tickets` — writes native blocking links between them |
| Plan something bigger than one session | `/wayfinder` — decision tickets you resolve one at a time |
| Build the thing | `/tdd` — red, green, refactor, one vertical slice |
| Review a diff before merging | `/code-review` — two axes, standards and spec, in parallel |
| Work out why something is broken | `/diagnosing-bugs` if installed, else `/grill-me` |
| Sort out labels and stale issues | `/triage` |
| Audit or repair one of the five loops | `/loopy` → Loop Doctor |
| Sharpen a term the project keeps fumbling | `/domain-modeling` |

**A normal sortie is two skills:** `/grill-me` → `/to-spec` to plan it, then `/tdd`
→ `/code-review` to build it. If you are reaching for a third, ask whether the
ticket is too big.

---

## The labels a sortie moves through

```
triage → planned → building → gate → review → done
```

- `state:planned` is the starting gun. **Applying it starts the S9 clock**, so
  apply it when the issue is genuinely ready to build, not while you are still
  thinking.
- `gate:machine` = tests or a script decide. `gate:taste` = you decide.
  `gate:none` = the gate hasn't been named yet, and that blocks auto-eligibility.
- `no-auto` means never auto-eligible, whatever the derivation says.
- Every open issue carries exactly one `type:`, one `state:` and one `gate:`.

Branch names carry the issue number: `<type>/<issue#>-<slug>`.

---

## When something goes wrong

| Symptom | What to do |
|---|---|
| A gate is red | Read the gate output, not the diff. `guard.yml` red means a tripwire matched — a `FLUX.1 [dev]` string, a `create_draft_listing` call, a placeholder template id |
| `qops guard` blocked a command | It is meant to. Committing to `master`, `push --force`, `reset --hard` are hard-blocked. If it blocked something legitimate, that is a qops bug — file it, don't work around it |
| The brief looks stale after a crash | `python -m qops resume --write` rebuilds it from the ledger. The ledger is the durable record; `resume.md` is a view of it |
| `qops doctor` reports drift | A rendered workflow no longer matches its template plus config. Re-run `python -m qops install` |
| A doc link broke | `qops doctor` checks every `docs/*.md` path cited from `pipeline/`, `scripts/` and `tests/`. Fix the citation, or move the doc back |
| You want to know what changed | `python -m qops metrics` — and read the window it reports before comparing anything |

---

## Where things live, so you don't search

| Looking for | It's in |
|---|---|
| What's open, and the plan for each | GitHub Issues. **Not** a doc |
| The project's vocabulary | `CONTEXT.md` |
| Why a choice was made | `docs/adr/` — each with a `revisit-after` |
| A limit imposed from outside | `docs/constraints/` — each with a `verify-by` |
| The five loops and their caps | `docs/reference/loops.md` |
| Prices, taxonomy ids, shipping | `docs/reference/static-config.md` + `config/static_config.json` |
| Everything project-specific qops reads | `.qops/config.yml` |
| History before the issue tracker | `docs/archive/` |

**Hard constraints and the two standing owner decisions stay in `CLAUDE.md`**,
capped at 150 lines and enforced by `groom.yml`. Nothing else goes there — a
lesson costs at most 3 lines, and it goes to a skill, an ADR, a constraint record
or a CI check instead.

---

**Status:** first draft, written 2026-08-14 before Phase 7. It is deliberately a
one-pager rather than a manual. Phase 7 revises it by installing qops into a
second project and finding out which lines were wrong — a guide nobody has
followed is a spec, not a guide.
