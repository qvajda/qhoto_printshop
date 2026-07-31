# qops Phase 0 — branch inventory and keep/merge/delete calls

**Generated:** 2026-07-26 · **Verified against:** `master` @ `56b4865`
**Status:** recommendations pre-drafted, awaiting owner confirmation.
**Nothing in this document has been executed.** Deletion is Phase 4 and needs its
own explicit "proceed".

Run `python scripts/qops_phase0.py` (dry run) then `--execute` to create the
safety tags and push. The script never deletes anything.

---

## 1. Credential scan — the actual point of Phase 0

The repo is **public** (anonymous `git ls-remote origin` succeeds). Every text
blob that has ever existed in history — 1,408 unique blobs across 1,446 objects —
was scanned for Anthropic / Replicate / Telegram / Etsy / Gelato / R2 / AWS
credential shapes and private-key blocks.

**Result: clean. No credential of yours is in this repository's history.**

Six raw matches were investigated and all six are benign:

| Match | Verdict |
|---|---|
| `AKIAIOSFODNN7EXAMPLE` ×5, in `tests/test_artwork_store.py` fixtures | The canonical **AWS documentation example key**. Not a credential. Pinned to the script's allowlist. |
| `AKIA3QM3COBP5QN4IUGA` in `scratch_gelato_baseline/product.json` | **Gelato's own** access key id, embedded in an `X-Amz-Credential=` presigned S3 URL returned by their API and saved to a scratch file. An access key id is an identifier, not a secret — the signature grants access, and this one carried `X-Amz-Expires=86400` from `20260722`, so it expired on 2026-07-23. Not tracked at `HEAD`; reachable only from commit `584ed9e` on `proto/mockup-scene-prototype`. **No action.** |

Both classes are now allowlisted **with their reason recorded**, so re-runs stay
quiet. The rule behind that: a scanner that cries wolf gets ignored, which is
worse than not scanning.

`HEAD` is clean too — the only credential-adjacent tracked files are
`.env.example` (a template) and `refresh_etsy_token.py` (a script). `.env` and
`.env.bak-*` have never been committed.

> Note for later: the Phase 4 safety tag on `proto/mockup-scene-prototype` will
> keep commit `584ed9e` — and therefore that expired presigned URL — reachable
> after the branch is deleted. Harmless, but it is why the branch content does not
> truly vanish at Phase 4. If you ever *do* want a blob gone from a public repo,
> that is a history rewrite, which is a separate decision.

---

## 2. Correction to the PRD's risk claim

The PRD first said "20 of 24 branches exist nowhere but the desktop." True of
branch *refs*, misleading about *work*: **20 of the 24 are already merged into
`master`**, which is on origin, so their content was never at risk.

Real unpushed work, measured:

| Branch | Commits not on origin |
|---|---|
| `feat/gl6-scene-library` | **12** |
| `proto/mockup-scene-prototype` | **2** |
| `feat/gl5-mockup-compositor` | **1** |

15 commits total. Worth pushing today; not the emergency implied.

---

## 3. Merged into `master` — 20 branches, all delete candidates

Fully contained in `master @ 56b4865`. Zero unique content. Safety-tagged, then
deleted in Phase 4.

**`fix/*` — 11 branches** (the S4/S5/remediation/resilience series, all landed):

`fix/finding-3-error-handling` · `fix/generation-quality-round2` ·
`fix/generation-quality-round3` · `fix/live-test-readiness` ·
`fix/remediation-steps-1-4` · `fix/resilience-hardening` ·
`fix/s4b-art-brief-scaffold` · `fix/s4d-critic-telemetry` ·
`fix/s5a-brief-critic-v2` · `fix/s5b-provenance-throttle` ·
`fix/s5c-mode-b-ingest-seam`

**`worktree-agent-*` — 9 branches**, all still pointing at `b2a3fe9` or older —
the residue of agent worktrees whose worktree directories are gone or stale.
Pure noise, and the strongest single argument for §3.5's rule that a branch name
must carry its issue number:

`worktree-agent-a2dc853ec5346ffb3` · `a6545c077c7b64192` · `a7020f7ac1dccc0d6` ·
`a7670f12b1b5c8fc4` · `aa54e1a88273f4111` · `abdd0bbdb0f6ff76a` ·
`abfcf07ab94a2c119` · `ac63ad2f50715f072` · `acc6d9e0d9fc17382`

**Recommendation: DELETE all 20 locally in Phase 4**, after safety tags exist.
Three of them (`generation-quality-round2`, `round3`, `resilience-hardening`)
also exist on origin — deleting the remote copies is optional and can wait; they
are merged, so they cost nothing but list noise.

---

## 4. Unmerged — 3 branches, individual calls

### `feat/gl5-mockup-compositor` — **KEEP** (active)
- `+7` vs master · **1 commit unpushed** (`72eb78a`, a GL-19 status doc) · on origin
- The live compositor branch: PR #2 open, `mockup_render.py`, the 4 bundles, the
  config accessor, 504 tests. GL-21 branches **off this**.
- **Action:** push the missing commit. Becomes the base for the GL-21 sortie in
  Phase 5. Maps to issues GL-5 and GL-21.

### `feat/gl6-scene-library` — **PUSH, TAG, THEN RETIRE**
- `+12` vs master · **12 commits unpushed** · not on origin · last commit 2026-07-25
- GL-6 **attempt 2**: 5 authoring commits, `scripts/gl6_author.py` (259 lines),
  re-authored bundles, and the `outputs/gl19_m1/*.png` renders. Owner-reviewed
  2026-07-26: **1 of 4 scenes accepted**. Your own plan of record marks it
  "reference only — do not build on it; cherry-pick nothing but ideas," while
  wanting its renders kept as the *before* side of the comparison.
- **Action:** push to origin, tag `ref/gl6-attempt2`, then delete the branch in
  Phase 4. The tag is what preserves the renders — the branch adds nothing.
- **Confirm:** is retiring the branch (keeping the tag) the call you want, or do
  you want it kept as a live branch until GL-6 attempt 3 has shipped?

### `proto/mockup-scene-prototype` — **VERIFY, THEN RETIRE**
- `+2` vs master · **2 commits unpushed** · not on origin · last commit 2026-07-22
- The pre-GL-5 prototype era. Diffed against master it *removes* ~1,480 lines
  including seven whole test files (`test_http.py`, `test_etsy_client.py`,
  `test_resilience_interrupt.py`, …) — it predates the GL-16 resilience work, so
  merging it would be a regression. Contains the scratch Gelato baseline from §1.
- Its one possibly-unique change is `fix: raise Anthropic max_tokens cap in
  compliance_draft + critic_pass`. **Verified, not assumed:** the script checks
  `master` directly and confirms `compliance_draft.py=2048, critic_pass.py=2048`.
  The branch holds nothing unique.
- **Action:** push + tag `ref/mockup-scene-prototype`, delete in Phase 4. The
  script re-runs the `max_tokens` check every time and will tell you to
  cherry-pick first if that ever stops being true.

---

## 5. Worktrees — 6, all prune candidates

Six under `.claude/worktrees/agent-*`, plus the main tree (7 `git worktree list`
entries). None correspond to an open piece of work; three still contain a
`.superpowers/` directory from an interrupted session. **Recommendation: prune
all 6 in Phase 4**, then adopt `.qops/wt/<issue#>` per §3.5.

---

## 6. Also snapshotted in Phase 0

- `.remember/` — 19 daily files, 349 lines. Superseded by `.qops/ledger.jsonl` +
  `resume.md`; archived, not deleted.
- `.superpowers/sdd/` — 40+ brief/report/progress/diff files. Archived.
- 13 untracked docs in `docs/` and the untracked `assets/brand/`,
  `outputs/gl6_*`, `outputs/gl19_m1/_dbg_*.png` debug renders — classified in
  Phase 4 (commit vs archive vs delete), not touched now.

---

## 7. Owner confirmation checklist

- [ ] §1 credential scan result accepted (clean; two benign classes allowlisted)
- [ ] §3 — delete all 20 merged branches locally in Phase 4, after tagging
- [ ] §4 — `feat/gl5-mockup-compositor` kept as the GL-21 base
- [ ] §4 — `feat/gl6-scene-library` retired to a `ref/gl6-attempt2` tag *(or: keep live — your call)*
- [ ] §4 — `proto/mockup-scene-prototype` retired once the `max_tokens` fix is confirmed on master
- [ ] §5 — prune all 6 agent worktrees in Phase 4
- [ ] Understood: Phase 4 deletion is requested separately with an explicit irreversibility flag
