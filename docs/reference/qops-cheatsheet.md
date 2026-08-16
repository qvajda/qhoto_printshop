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

**qops owns three skills and no more** (ADR-0018). They are the three that carry
sequencing and have to know *this* repo's taxonomy. Everything else is either
the substrate — a hook handing you the next step at the moment it matters — or a
skill your Claude install already carries, which this repo does not pin, ship or
maintain.

| You want to… | Type this | Whose |
|---|---|---|
| Decide *what* to build, when the design isn't settled | `/interview` — rounds of 3–6 questions, ending in an ADR, a constraint record or an issue | qops |
| Write up what you just decided, onto the issue tracker | `/spec-to-issue` — writes `.qops/config.yml`'s labels; the publish step waits for you | qops |
| Sort out labels and stale issues | `/triage` — the state machine, owner-invoked only | qops |
| Plan something bigger than one session | Nothing to type. An epic issue plus `qops brief`'s routing verdict (ADR-0017) is the whole mechanic |
| Build the thing | Your install's TDD skill — red, green, refactor, one vertical slice. The gate is `ci.gate_command` in `.qops/config.yml` | install |
| Review a diff before merging | Your install's `/code-review` | install |
| Work out why something is broken | Your install's systematic-debugging skill; if there isn't one, `/interview` the failure | install |
| Sharpen a term the project keeps fumbling | Your install's domain-modeling skill, then write it into `CONTEXT.md` | install |

**A normal sortie is two qops skills:** `/interview` → `/spec-to-issue` to plan
it, then build and review with whatever your install provides. If you are
reaching for a third qops skill, the ticket is too big.

**Why the list shrank from nineteen.** ADR-0013 installed eleven external skills
as editable copies and owed a displacement it never paid; the installed set
drifted to nineteen and nothing noticed, because the count was a mitigation a
human was asked to re-read. `qops doctor` now asserts the installed set equals
`.qops/config.yml`'s `skills:`, so it cannot drift again in silence.

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
| `qops doctor` reports a skill | An installed skill is not in `.qops/config.yml`'s `skills:`, a native one is missing, or an external pin has no upstream `ref`. Uninstall it, reinstall it, or declare it — do not widen the declared set to silence the check, which is how it reached nineteen |
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
