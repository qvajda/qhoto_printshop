# E15 launch prompt — qops Phase 4 and Phase 5

**Predecessor:** E14 shipped Phases −1, 1, 2 and 3. Board superseded by GitHub
Issues (`abd7aed`), 86 issues imported, 13 ADRs + 5 constraint records written,
89 docs archived, `docs/*.md` 107 → 22, branches 4 → 1, dirty paths 38 → 1.
**812 green. Everything pushed, all three `archive/*` tags on origin.**
**Findings:** `docs/2026-08-13-e14-phase-minus-1-findings.md`.
**PRD:** `docs/2026-08-13-qops-prd-v3.md` — decisions 30–40 all closed.

**Owner decisions taken since E14 closed, both in PRD §8.1:**
**40 — full build confirmed.** **39 — the Remember plugin is retired.**

Start the session with Remote Control on (decision 38 — this is now how approvals
reach the phone):

```bash
claude --remote-control "qops E15"
```

Then `/config` → enable **Push when actions required**.

---

You are running **E15**: PRD v3 **Phase 4** (the L0 substrate) and **Phase 5**
(qops tracks itself). This is the irreducible build — everything that could be
configured already was.

**Read first, and only these:**

1. `docs/2026-08-13-qops-prd-v3.md` — §3.2/§3.3 (what is build vs configure),
   §7 Phase 4, §8.1 decisions 30–40.
2. `docs/adr/0001-hook-spike.md` — **the hook semantics this whole phase is
   designed against.** If anything in Phase 4 contradicts it, the ADR wins until
   amended.
3. `CONTEXT.md` — the project's shared language, written in Phase 2.
4. `.qops/config.yml` — everything project-specific lives here.

**Do not read** `docs/archive/2026-07-22-go-live-plan-of-attack.md`. It is 401 KB,
it is superseded by the issues, and reading it is the tax this build exists to
remove. Use `gh issue list` / `gh issue view`.

## §0 — The Remember retirement (decision 39). Do this before building.

It is Phase 3 residue and it must not still be live when `qops ledger` and
`qops resume` exist, or the project has two memory systems writing overlapping
state — finding E5's failure in a second location.

**Order is the decision. Deleting first is a no-op, because a live plugin
recreates the directory.**

1. **The owner disables the Remember plugin.** This is a UI action; it is not
   yours. **Confirm it is off before step 2** — check that nothing under
   `.remember/` has been modified in the last few minutes.
2. **Re-snapshot `.remember/`**, excluding `tmp/`, using the same method as
   `docs/archive/2026-08-13-remember-sdd-snapshot-manifest.md` §2. The first
   snapshot was taken at midday and `.remember/` was written to afterwards, so it
   is incomplete.
3. **Verify the count both ways**, as the manifest did: files in the archive must
   equal `find .remember -type f ! -path '.remember/tmp/*' | wc -l`.
4. **Amend the manifest** with a new section recording the second archive's file
   count and `sha256`, stating that it supersedes the first for `.remember/` and
   that the first remains valid for `.superpowers/sdd/`. Hand the archive to the
   owner; do not save it inside the working tree.
5. **Then delete** `.remember/`, and write **`docs/adr/0014-retire-remember-plugin.md`**:
   context (the overlap with `qops ledger`), decision, consequences (what is lost —
   `now.md`, the narrative dailies — and what replaces it), `status`,
   `revisit-after`.

`.superpowers/` should already be gone; if it is not, `rm -rf .superpowers` is
authorised — static, untracked, covered by the manifest's 216-file archive.

**Stop and report after §0.** Do not start building until the manifest is amended.

## §1 — Phase 4, in this order. The order is not arbitrary.

**1. `.claude/settings.json` first.** It is the tree's last dirty path. E14
declined to commit the spike's version because it points at a git-ignored
throwaway through a hardcoded absolute Python path — write the real one, invoking
`qops <verb>` only, with every project specific in `.qops/config.yml`. **Only
after this may the dirty-tree rule be switched on** in `Stop` / `SessionStart`;
enabling it earlier trips on the file that fixes it.

**2. The `qops` CLI and the hooks**, wired per ADR-0001:
`brief` · `ledger` · `resume` · `guard` · `close` · `install` · `doctor` ·
`metrics`. Red-green-refactor via `/tdd`. Two contracts to honour exactly:

- **`qops brief` ≤ 400 tokens**, and it **leads with any dirty-tree violation**
  rather than papering over it.
- **`qops guard` hard-blocks**: commit/push to `master`, `push --force`,
  `reset --hard`, worktree sprawl, and the project tripwires
  (`create_draft_listing`, a non-mocked Gelato create carrying a placeholder
  template ID, `FLUX.1 [dev]`).

**3. `qops metrics`.** S1/S2/S4/S9/S10, plus `--state` for PRD §1.2.
**S1 must adopt the Phase −1 findings §1 method verbatim** — subagent traffic
excluded (`isSidechain` falsy only), `Bash` reads not counted, >200-line reads
flagged. **A baseline measured one way and re-measured another is not a
baseline**, and the whole point of Phase 6 is comparing against it.

**4. `.github/workflows/`, rendered by `qops install` from templates +
`.qops/config.yml`**, with `qops doctor` detecting drift. Five workflows: `test`,
`gate`, `guard`, `digest`, `groom`. Three specifics:

- **`groom.yml` enforces the CLAUDE.md ≤150-line cap.** This is load-bearing, not
  hygiene: term A is now **11,650 of 32,650 tokens/day** — the larger half of the
  saving — and CLAUDE.md grew +10 lines/day unenforced, so the cap is re-breached
  in ~20 days without a check. **If you build one workflow, build this one.**
- **`guard.yml` gets a doc-link check** (new, PRD §7 Phase 4). Every
  `docs/*.md` path cited from `pipeline/`, `scripts/` or `tests/` must resolve —
  15 today, all resolving. Phase 3 proved this breaks: archiving 89 docs broke 13
  citations and only a check caught it.
- **`digest.yml` runs with no LLM.** Renders open issues + CI status + pending
  approvals; posts to the **dev** Telegram bot and updates the pinned status issue.

**5. Slim `CLAUDE.md` to ≤150 lines.** Data (the Gelato/Etsy static table, prices,
taxonomy, shipping profile) → `docs/reference/static-config.md` +
`config/static_config.json`. Decisions → the 13 existing ADRs. External facts →
the 5 constraint records. **Preserve the old CLAUDE.md in `docs/archive/`.** The
two standing owner decisions (activation, no history rewrite) stay in CLAUDE.md —
they are constraints on every session, not reference material.

**6. `tests/fixtures/masters/`** — 3 downscaled masters (~1024px, one portrait,
one landscape, one deliberately awkward), and parameterise `gl19_m1_render.py` and
`mockup_qa.py` on the master path with the fixture as the CI default.
`tests/fixtures/` is **already tracked**, so v2's gitignore-narrowing step is
struck — do not re-add it.

**7. Six subagent definitions** for the §3.3 roster — planner, coder, reviewer,
scribe, triager, interactor — each with its `tools` allowlist, `model` and
`effort`. Per §3.4: scope-fencing language, a delegation cap, **no
"double-check your work" instructions**. The read-only review pass before a
commit stays, because it has a named incident behind it.

**8. Branch protection on `master` with "do not allow bypassing" enabled, plus a
non-admin `QOPS_AGENT_TOKEN`** (`Contents: write`, `Pull requests: write`,
`Issues: write`). **Both, or the protection is decorative** — finding B8. This
touches GitHub account settings: show the plan and get an explicit proceed.

**9. `pickup-loop` as a Desktop scheduled task, default OFF.** Create it, prove it
runs, leave it disabled.

**10. Loop Doctor over the five loop definitions**, once — `gate-loop`,
`review-loop`, `triage-loop`, `groom-loop`, `pickup-loop`. Fix only material
findings.

**Phase 4 gate, three tests, all with gates that exist today:** plant a
`FLUX.1 [dev]` string on a branch → `guard.yml` red → the PR cannot request
review; break one test deliberately → `test.yml` red → same; a green run permits
the request.

## §2 — Phase 5, and it is one line of policy

From here, **qops's own work lives as issues in the qops plugin repo**, not in
`qhoto_printshop` and not in a doc. `qhoto_printshop` issues track pipeline work
only. Write it down where a future session will trip over it, and move any
qops-related issue that is currently in this repo.

## Standing constraints

- **Activation is not a planning variable.** Everything stays a draft.
- **Git history is not rewritten.** Closed. Do not raise it under any framing.
- **No pipeline work.** **GL-63 is reserved as the Phase 6 acceptance sortie — do
  not fix it, that destroys the measurement.** GL-66, GL-67, GL-73 and GL-53's
  remaining stage loops are all out of scope. Parameterising the two render
  scripts on a master path (item 6) is the *only* sanctioned touch outside qops,
  and it is additive.
- **Verification conventions stand**, each with its incident: verify by
  measurement not status code (GL-22a); gate the side effect not the value
  (GL-48); an instruction in a prompt is a preference, not a control (GL-53) — so
  every rule this phase states in a prompt needs an assertion somewhere too.
- **Two hard stops:** after §0, and before item 8 touches GitHub settings.
- **Stop-rule.** If Phase 4 exceeds **four 5h windows**, stop and ship the
  substrate only — hooks, `brief`, `resume`, `guard`, issues — and report what was
  dropped. That is the fallback decision 40 kept in reserve; it does not need
  re-approval.
- **Scope fence.** Deliver what is asked at the scope intended. If the PRD looks
  wrong, say so in a sentence and continue as asked rather than quietly widening.
  Do not spawn subagents to verify your own work.
