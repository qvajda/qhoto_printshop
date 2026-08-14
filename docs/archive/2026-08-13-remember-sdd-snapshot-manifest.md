# Snapshot manifest — `.remember/` and `.superpowers/sdd/` (2026-08-13)

**This file is the artefact PRD v2 Phase 3's prerequisite resolves to.** Phase 3
is the first destructive phase; its prerequisite must point at something on disk,
not at a memory that a session once did this. Finding **C3** is closed by this
manifest, not by the archive — the archive lives outside the repo and could be
moved; the manifest is committed and citable.

Closes: PRD v2 §7 Phase 0's second outstanding item · review finding **C3** ·
E13 kickoff §7b. **Phase 0 is now complete** (§7a closed 2026-08-13 as E13a).

---

## 1. The decision that was actually taken

The kickoff offered three readings of the word "snapshot". **Reading (i),
out-of-repo archive, is what was done**, for the reason stated there: it
satisfies Phase 3's prerequisite, adds nothing to a public repo, and is
reversible.

Reading (ii) — committing ~216 never-committed files into a public repository,
permanently — was rejected. E13a scanned committed history and all 1357
*reachable* blobs; this content has never been committed, so it was never in that
scan's scope. Reading (ii) would introduce unscanned material into a public repo,
and the pre-scan below is a screen, not a substitute for the three-instrument
sweep E13a ran.

Reading (iii), a private off-repo backup, is **available and is the owner's
call** — the archive was handed to the owner rather than written anywhere inside
the working tree, precisely so that choosing (iii) is a matter of where he saves
the file. See §5.

## 2. The archive

| | |
|---|---|
| Filename | `qhoto_printshop-remember-sdd-snapshot-2026-08-13.tar.gz` |
| Size | **837,002 bytes** (817 KB) |
| `sha256` | `49a397267833d64e515a22f851c763c6e838039fbf8ce2cf2c3df7d5c6fd6996` |
| Entries | 220 (216 files + 4 directories) |
| Paths | intact and repo-relative — extracts to `.remember/` and `.superpowers/sdd/` |
| Committed? | **No, deliberately.** Reading (i). This manifest is the committed half |
| Custodian | **the owner — saved off-repo as a backup, 2026-08-13, confirmed by the owner.** The exact location is deliberately not written into a public repository; the owner knows it, and §6's condition is discharged |

**Count verification, run rather than asserted:** the archive holds **216
files**; the source trees hold **64** files under `.remember/` excluding `tmp/`
plus **152** under `.superpowers/sdd/` = **216**. In and out agree.

## 2b. Second archive — `.remember/` only, 2026-08-13 23:5x (supersedes §2 for `.remember/`)

§2's archive was taken at midday **while the Remember plugin was still running**,
and `.remember/` was written to repeatedly afterwards (last write 23:47:00). It is
therefore incomplete for that tree. This second archive was taken **after the owner
disabled the plugin** — quiescence confirmed two ways: no file under `.remember/`
modified for ~5 minutes, and tool calls made during that window produced no
post-tool hook write.

| | |
|---|---|
| Filename | `qhoto_printshop-remember-snapshot-2-2026-08-13.tar.gz` |
| Size | **463,211 bytes** |
| `sha256` | `d86d38f59f7f62ed49752f118149b7a0a2d5e6ae968324542e9166f34c71b521` |
| Entries | 65 (**62 files** + 3 directories) |
| Scope | `.remember/` only, excluding `.remember/tmp/` — same method and same prune as §2/§5 |
| Committed? | **No.** Handed to the owner, same as §2 |

**Count verification, run rather than asserted:** archive holds **62** files;
`find .remember -type f ! -path '.remember/tmp/*' \| wc -l` = **62**. In and out agree.

**Precedence:** this archive **supersedes §2 for `.remember/`**. §2 remains the
valid and only archive of **`.superpowers/sdd/`** — that tree was static, was
already deleted from the working tree, and is not re-snapshotted here.

**Delta against §2 (64 → 62 files under `.remember/`), recorded not explained
away:** between the two snapshots the plugin rotated its daily logs — the
`memory-2026-08-0[1-4].log` dailies are gone and the `logs-2026-08-part*.tar.gz`
set grew — and `tmp/save-session.pid` and `.remember/.gitignore` are no longer
present. The second archive is the authoritative one regardless: it is the state
that actually existed at deletion time.

**Consequence:** `.remember/` was deleted from the working tree immediately after
this archive was verified. See `docs/adr/0014-retire-remember-plugin.md`.

## 3. Measured inventory — and three corrections to the kickoff's figures

The kickoff's numbers were close but wrong in three places, and one of them moves
a risk argument rather than a count.

| Tree | Kickoff said | Measured 2026-08-13 |
|---|---|---|
| `.remember/` | 1.3 MB, 41 top-level entries: 39 `.md` + `logs/` (22 items incl. 3 `.tar.gz`) + `tmp/` | 1.3 MB, **87 files total**: 40 `.md`, 13 `.log`, **11 `.tar.gz`**, 1 `.ts`, 1 `.pid`, 1 `.json`, 1 `.gitignore`, plus 23 files under `tmp/` |
| `.superpowers/sdd/` | 2.1 MB, 151 files — 89 `.diff`, **13 `.log`**, rest `.md` | 2.1 MB, **152 files** — 89 `.diff`, **54 `.md`**, 8 `.py`, 1 `.gitignore`, and **zero `.log`** |

**The correction that matters is the third.** The kickoff placed 13 `.log` files
in `.superpowers/sdd/` and built its credential-risk argument on them ("exactly
the shape of artefact that captures environment variables in a traceback"). Those
13 `.log` files are in **`.remember/logs/`**, not in `sdd/`. The argument is not
weaker for being relocated — it is stronger: `.remember/logs/` holds
`hook-errors.log`, 9 `memory-*.log` dailies, and **11 `.tar.gz` archives of
further logs**, which is a larger and less legible surface than the kickoff
assumed. Anyone re-reading §7b's risk paragraph should read it against
`.remember/logs/`.

## 4. Pre-scan — extended past the kickoff's, because the kickoff's had a hole

The kickoff recorded a verbatim sweep of the live `.env` values across both
trees, 0 hits. **That sweep could not have seen inside the 11 `.tar.gz` files**,
and log tarballs are the single most likely place for a traceback to have
captured an environment variable. Re-run here with decompression:

- **21 `.env` keys** carrying a value of ≥8 characters were used as needles
  (values below that length are too short to be a credential and too common to
  be a signal).
- **298 files scanned**, of which **11 tarballs were opened and every member
  inside them read**.
- **0 of 21 values appear anywhere**, plain or inside an archive.

This is a screen against *this* project's current live credentials. It is not a
generic secret scan and does not supersede E13a. **If reading (ii) is ever
chosen, re-run the full E13a instrument set at that moment** rather than citing
this paragraph.

The three `AKIA` matches the kickoff noted (in `artwork-task-2-report.md` and two
`review-*.diff` files) are unchanged and are the same c1/c2 classes E13a
triaged — Gelato's expired presigned-URL key id, and the canonical AWS
documentation example. Neither is a live credential.

## 5. Prunes — one taken, one measured and rejected

**Taken: `.remember/tmp/` is excluded.** 23 files of live runtime state —
`session-slug`, `last-save-ts`, `post-tool-ran`, `capture-alive`,
`save-session.pid`. No archival value, and it was being written *while* the copy
ran, which is its own reason not to copy it.

**Rejected, and rejected on a measurement rather than a preference: the 89
`.diff` files are kept.** The kickoff's case for dropping them is sound in
principle — they are review diffs of code git already holds, and they are the
bulk of the 2.1 MB. So the question is what excluding them actually buys:

| Archive | Compressed size |
|---|---|
| Excluding `*.diff` | 573,472 bytes |
| **Including `*.diff` (shipped)** | **837,002 bytes** |
| Difference | **263,530 bytes — 258 KB** |

258 KB is not worth a judgement call that could turn out wrong. Exclusion is
irreversible the moment the working tree is cleaned; inclusion costs a quarter of
a megabyte, once. **Decided explicitly, as the kickoff asked, and decided the
other way.**

## 6. What the owner has to do, and it is one thing

The archive was written to this session's outputs folder and handed over rather
than saved into the working tree. That is deliberate: a git-ignored tarball
sitting inside the repo is exactly the failure GL-51 documents — a file with no
second copy in a directory that tooling is entitled to delete.

**✅ DONE 2026-08-13 — the owner confirmed the tarball is saved as a backup
outside the repo.** §2's Custodian row records it. Nothing downstream reads the
archive; Phase 3 reads this manifest. The location itself is deliberately not
written here — this file is committed to a public repository, and "where the
owner's backups live" is not something a public repo should say.

**Phase 3 is therefore unblocked.** It may delete `.remember/` and
`.superpowers/sdd/` from the working tree when it runs.

## 7. Consequence for PRD v2 Phase 3

Phase 3's line "**Prerequisite: Phase 0's outstanding snapshot is done**" now
resolves to this file. The amendment is applied in
`docs/2026-07-26-ways-of-working-overhaul-prd-v2.md` Phase 3, and PRD v3 carries
it forward. Phase 3 may delete `.remember/` and `.superpowers/sdd/` from the
working tree once the Custodian row is filled in — **not before**, because until
then the only copy is in an outputs folder that does not survive the session.
