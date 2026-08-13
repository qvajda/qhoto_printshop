# GL-38 — merge kickoff: land the soak branch on master, cleanly

**Filed:** 2026-08-09 · **Type:** C+M · **Blocker, head of the critical path**
· **Contains destructive steps — CLAUDE.md §4 applies: show the plan, wait for
an explicit "proceed".**

This supersedes the five-line sequence in the GL-38 row and in Part 3 Track E
of the go-live plan. That sequence was right about the *order* and wrong about
the *difficulty*: it assumed a clean fast-forward and a judgement call on the
database. Neither is true. The merge has one real conflict, one blocking
untracked file, and a pile of uncommitted work sitting on master that nobody
has noticed for three days. The database, by contrast, needs no judgement at
all — it is settled below by measurement.

---

## 1. State of the two trees, measured

| | master (repo root) | `worktree-gl7-cron-orchestrator` |
|---|---|---|
| HEAD | `c4c2cc5` | `d959d4c` |
| Commits ahead of the other | 2 | 21 |
| Files changed vs merge base | 12 | 27 (+7,545 / −3) |
| Worktree state | **dirty** — 4 modified, ~50 untracked | locked |

**The branch is 21 ahead and 2 behind.** Master moved during the soak
(`7bb70f8` GL-10d banner, `c4c2cc5` GL-43 keyword delta), which is what creates
the conflict in §3.

**Only 3 deletions across 7,545 insertions** — this is a near-pure addition.
That is the good news, and it is why the conflict surface is one file.

## 2. The database question is settled — it is not a judgement call

Track E said the worktree's DB was "almost certainly" canonical. It is
provably canonical, and the proof also means **there is nothing to
reconcile**.

Every shared content table was compared row-by-row (all shared columns,
hashed, keyed on `id`):

| Table | root rows | missing in worktree | differing |
|---|---|---|---|
| `candidates` | 42 | 0 | 0 |
| `groups` | 48 | 0 | 0 |
| `group_products` | 16 | 0 | 0 |
| `group_product_variants` | 31 | 0 | 0 |
| `product_images` | 46 | 0 | 0 |
| `listing_texts` | 6 | 0 | 0 |
| `telegram_events_log` | 34 | 0 | 0 |
| `group_messages` | 13 | 0 | 0 |

**The worktree DB is a strict superset of the root DB.** It was forked by copy
and grown; the two never lived parallel lives. So the operation is a
**promote-and-swap**, not a merge — no row-level reconciliation, no
cherry-picking, no decision about whose candidate 42 is real.

| | root | worktree |
|---|---|---|
| Size | 434,176 B | 913,408 B |
| Tables | 12 | 14 (`schema_version`, `heartbeats`) |
| `schema_version` | **absent** | 7 |
| Candidate ids | 1–42 | 1–86 |
| `telegram_offset` | 475586367 | 475586404 |

**Two details worth carrying forward:**

- **The root DB's Telegram cursor is 37 updates behind.** That is the
  single-consumer hazard made concrete rather than theoretical: any run from
  the main checkout would poll from a stale offset against a cursor the
  worktree has already advanced. It is also a reason to swap the file rather
  than migrate the root one in place — the offset must travel with the rest.
- **`heartbeats` holds 2 rows, one per task, upserted — it is a latest-state
  table, not a log.** Last hourly `2026-08-09T15:00:01`, last batch
  `2026-08-09T07:11:32`. "Did it run?" is answerable; "how often did it fail
  last week?" is not. Not a blocker, but do not expect history from it during
  GL-45's investigation.

## 3. What will actually go wrong, and the fix for each

### 3a. Conflict: `tests/test_research.py` — the only one

Both sides added tests to the same file since the fork:

- **master** (`c4c2cc5`, GL-43): +26 / −1 — the two bucket guards (BLOCKED
  terms stay out; no room or colour word ever appears), and the edit to the
  test that used to assert `moon phase print` was present.
- **branch** (`f90e8ad`, soak fix 2): +16 — the regression test for the
  `sort_on="favorites"` → `"score"` fix.

`pipeline/research.py` itself is **untouched on master**, so the source
conflict is zero — it is purely the test file.

**Resolution: keep both additions.** Neither is optional. Dropping GL-43's
guards re-opens the prompt-poisoning path; dropping the soak's guard re-opens
the `HTTP 400` that made every demand check fail silently for a day. Resolve
by union, then run the file and confirm all three new tests are collected —
**not** by taking one side wholesale.

### 3b. Blocker: an untracked file will refuse the checkout

`docs/superpowers/plans/2026-08-05-gl7-cron-orchestrator.md` exists **untracked
in the main checkout** and is **added by the branch**. `git merge` refuses to
overwrite untracked working-tree files, so the merge aborts before it starts.

Verified: the untracked copy is **byte-identical** to the branch's version.
Delete the untracked copy immediately before merging. (Confirm identity again
at the time rather than trusting this line — it costs one `diff`.)

### 3c. Uncommitted GL-37 work is sitting on master, and it touches the publish path

This is the one to be careful about. The main checkout has **four modified,
uncommitted files**:

```
 M CLAUDE.md                      (+33)   GL-37 re-verification block
 M docs/CHANGELOG.md              (+47)
 M pipeline/compliance_draft.py   (+31/-13)  DISCLOSURE_TEXT -> ""
 M tests/test_compliance_draft.py (+20)
```

That is **GL-37's decision implemented in code** — the prose AI disclosure
removed from listing descriptions — and it has been uncommitted since 08-06.
CLAUDE.md itself records that this change is only safe because the structured
tick happens at publish, and that it is load-bearing against GL-29's
cancellation.

**Commit it as its own commit before the merge, not into it.** Merging onto a
dirty tree that touches the live publish path is how a change like this gets
lost in a conflict resolution or reverted by an abort.

### 3d. ~50 untracked files, including 11 docs the go-live plan cites as if they exist

Untracked right now, and referenced by the board: the GL-10b artefacts
(findings, checklist, listing-copy spec, banner/icon decision, privacy
policy), the GL-11 email draft, the GL-13 delta launch guide, the GL-7 PRD and
kickoff, the GL-30 kickoff, `docs/data/`, and today's two additions (the GL-45
brief and this file).

**A single `git clean -fd` during merge cleanup would delete the project's
documentary record for four workstreams.** Commit the docs in the same pass.
The `outputs/gl6_*` directories and `assets/mockups/inflow/` are correctly
git-ignored/untracked and are already backed up by GL-30 — leave them, but
know the difference before running any clean.

### 3e. Six other worktrees, all prunable

`.claude/worktrees/` holds six `agent-*` worktrees besides the GL-7 one, all
reported **prunable** by `git worktree list`. None holds a live DB. Note that
**`fix/finding-3-error-handling` is 0 commits ahead of master** despite the
name — it is an empty stale branch, not a head start on GL-46. Do not mistake
it for existing work.

## 4. Procedure

Steps 3 and 5 are destructive. Stop at each and wait for an explicit
"proceed".

**Phase A — tidy master first (no merge yet)**

1. Commit the GL-37 code change (§3c) as its own commit:
   `pipeline/compliance_draft.py` + `tests/test_compliance_draft.py` +
   `CLAUDE.md` + `docs/CHANGELOG.md`. Run the compliance-draft tests first.
2. Commit the untracked docs (§3d), including this file and the GL-45 brief.
3. Confirm `git status` shows only intentionally-ignored material left.

**Phase B — the merge**

4. Back up the branch ref (`git branch gl7-soak-archive
   worktree-gl7-cron-orchestrator`) so nothing depends on the worktree
   surviving.
5. Delete the untracked `docs/superpowers/plans/2026-08-05-gl7-cron-orchestrator.md`
   after re-confirming it is identical to the branch copy (§3b).
6. Merge `worktree-gl7-cron-orchestrator` into master. Expect exactly one
   conflict, `tests/test_research.py`; resolve by union (§3a).
7. **Full test suite green on master before anything else happens.** The
   branch was last green in isolation; it has never been run against GL-43's
   and GL-10d's changes.

**Phase C — the database (destructive — show and wait)**

8. Back up **both** files with dated names — the root one especially, since it
   is the one being replaced and it is the only artefact that would let you
   undo this.
9. Copy the worktree DB over `db/qhoto.sqlite3`. It is a promote-and-swap
   (§2), not a merge.
10. Run `migrate.py --check` against the promoted file. It should report
    version 7 and refuse nothing.
11. Sanity-check: candidates 1–86 present, `telegram_offset` = 475586404,
    `heartbeats` carries both rows.

**Phase D — deployment**

12. Re-point both Windows scheduled tasks at the repo root, and **leave them
    disabled.** Nothing runs unattended until GL-45–GL-48 land.
13. Verify the re-point by running each entrypoint **once, by hand**, and
    confirm a fresh heartbeat appears in the **root** DB —
    `heartbeat_status.py`, not assumption. This is also the moment the root
    tree becomes the sole Telegram consumer.
14. Confirm `db/gl7.lock` now resolves beside the canonical DB.
15. Unlock and remove the GL-7 worktree; prune the six stale ones.

**Phase E — deferred, by design**

16. GL-49's row repair (candidates 44, 47, 48) happens **after** this, against
    the promoted DB. Doing it earlier means doing it twice.

## 5. Definition of done

- [ ] Master carries all 21 commits; `git log master..worktree-gl7-cron-orchestrator` is empty.
- [ ] Both `tests/test_research.py` additions survive and are collected.
- [ ] Full suite green **on master**, post-merge.
- [ ] GL-37's compliance_draft change is committed, not stashed or lost.
- [ ] The 11 untracked docs are tracked.
- [ ] `db/qhoto.sqlite3` is the promoted file, at `schema_version` 7, with both
      pre-swap backups retained.
- [ ] Both scheduled tasks point at the repo root, are **disabled**, and each
      has produced one hand-run heartbeat in the canonical DB.
- [ ] The GL-7 worktree is gone; the six stale ones are pruned.
- [ ] The GL-38 row is updated with what actually happened, including anything
      this brief got wrong.

## 6. Out of scope

- **Any of GL-45–GL-48.** This lands the branch; it fixes nothing. The
  temptation to "just fix the `except` block while I'm in here" is how a merge
  becomes a session.
- **The token-scoped lock.** Real, and filed in the GL-38 row, but it is a
  design change and belongs with GL-45 — which may prove it necessary rather
  than merely tidy.
- **Restarting the soak.** Track E step E5, after the fixes.

## 7. Tool fit (CLAUDE.md §7)

**Claude Code, in-repo, single session.** Conflict resolution, a test run and
file operations against a working tree — Cowork's sandbox cannot see the
Windows scheduled tasks or run the merge against the real checkout anyway.

**Phases C and D are owner-manual regardless of tool**: the DB swap wants a
human confirming the backups exist, and the Task Scheduler re-point cannot be
done from inside the repo at all.
