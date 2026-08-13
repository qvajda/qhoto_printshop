# GL-5 kickoff — implement `pipeline/mockup_render.py` (self-hosted compositor)

Ready-to-paste prompt for a **fresh Claude Code session** started from the
`qhoto_printshop` repo root. Subagent-driven (SDD), commit-per-stage, ends in a
PR to `master`. This is a **build** task against an approved plan — not a
redesign.

---

## PROMPT — paste from here down

You are implementing the **GL-5 mockup compositor** in this repo, subagent-driven,
stage by stage, ending with a pull request to `master`. Build what the plan
specifies — do not redesign it.

### Read first, in this order
1. `docs/2026-07-22-gl5-compositor-implementation-plan.md` — the plan you are
   building. Follow §4 (module shape), §5 (config), §6 (rewiring), §7 (tests),
   §8 (build order), §9 (risks). This is the source of truth.
2. `docs/2026-07-22-compositor-approach-findings.md` — why (Q1 no runtime
   detection; the over-fill + supersample + frame-in-overlay seam fix; the
   dependency decision and its Pillow-only fallback).
3. `docs/SPEC_v4.10_addendum_custom_mockups.md` — the design of record (§2, §4,
   §5, §6).
4. `CLAUDE.md` (root + repo) and `docs/SPEC_v4.11.md` §3–4 — the hard constraints
   below come from here.
5. Reference only, do **not** promote: `scripts/proto_mockup_compositor.py` and
   the bundles under `assets/mockups/primary/portrait/*` on branch
   `proto/mockup-scene-prototype`. Existing stages you'll rewire:
   `pipeline/primary_mockup.py`, `pipeline/group_mockup.py`, and their specs in
   `docs/superpowers/specs/2026-07-09-primary-mockup-stage-design.md` /
   `2026-07-12-group-mockup-design.md`.

### Non-negotiable constraints (violating any is a bug)
- **No runtime aperture detection.** Read the four corners from `meta.json`. Do
  not port the prototype's flood-fill / `detect_aperture_quad` — it's deleted by
  design (findings Q1).
- **Asset-bundle format unchanged.** `background.png` + `overlay.png` +
  `meta.json` (Addendum §4). The only allowed change is the *optional, additive,
  defaulted* `overfill` field in `meta.json` (plan §3). Do not invent a new
  format.
- **Fail loud on placeholders.** A scene ID in config with no complete bundle on
  disk must raise `MockupRenderError` and surface as `status='mockup_failed'` —
  never silently skip, never fall back to a Gelato image (Addendum §4/§5).
- **Pure core.** `render_scene(artwork, bundle)` does no I/O and is
  deterministic (same bytes every run). `load_bundle`/`render_scenes` are the
  only disk seam.
- **Static config, resolved once.** `mockup_templates` lives in
  `config/static_config.json`; never discover scenes at runtime (same rule as
  the Gelato template IDs).
- **Dry-run for anything external.** Do **not** call Etsy `uploadListingImage` or
  Gelato create against real endpoints while iterating — use dry-run/fixtures.
  Live calls only on my explicit go-ahead (reversibility rule).
- **Secrets from `.env` only.** Nothing hardcoded, nothing committed.
- **One module per stage, independently testable. Commit after each stage passes
  its tests. Keep the full suite green** (it's currently all-green — keep it that
  way; report the N/N count each stage).
- **Minimal code (Ponytail ethos).** Smallest correct change; no speculative
  abstraction. The whole compositor core is ~40 lines — keep it that way.

### Open decision — resolve with me BEFORE Stage 2 (do not self-approve)
The plan recommends adding **`opencv-python-headless`** (+ declaring `numpy`).
This **conflicts with the house "zero new runtime dependencies, stdlib-only"
standard** (the reason we hand-rolled SigV4 instead of boto3). Flag it to me
explicitly and wait for a decision:
- **Option A (plan's recommendation):** add `opencv-python-headless`; cleaner
  anti-aliased edges, ~40-line core, needed for clean v1.1 angled warps.
- **Option B (zero-new-dep):** Pillow-only supersampled warp + supersampled
  alpha mask (findings Q6 fallback); +30–40 lines, slower, no new dependency.
Do not add any package until I pick. If I'm unavailable, default to **Option B**
and leave a clear TODO — never add a dependency unilaterally.

### Workflow — subagent-driven (match the repo's SDD convention)
Use the existing `.superpowers/sdd/` pattern:
1. **Branch** off `master`: `feat/gl5-mockup-compositor`. Keep a progress ledger
   at `.superpowers/sdd/gl5-compositor-progress.md` (mirror the format of the
   existing `progress.md`: plan/branch/base-commit header, one entry per task
   with commit range, test counts, findings, decisions).
2. **Per task**, run the loop:
   - Write a short task brief (`.superpowers/sdd/gl5-task-N-brief.md`).
   - **Spawn an implementer subagent** with the brief; it writes code + tests for
     that task only, runs the suite, commits.
   - **Spawn a separate reviewer subagent (use the strongest model, e.g. opus)**
     on that task's diff; save the diff as
     `.superpowers/sdd/review-<base>..<head>.diff` and address findings in a
     fix commit before moving on. Record the outcome in the ledger + a
     `gl5-task-N-report.md`.
   - Do not start task N+1 until N's review is approved and the suite is green.
3. **Final whole-branch review:** after the last task, spawn one opus reviewer
   over the entire `master..HEAD` range; fix any Critical/Important findings
   (the per-task reviews miss integration-boundary bugs — that's expected).

### Tasks (from plan §8; keep each a single stage + commit)
- **Task 1 —** `pipeline/mockup_render.py` (plan §4) + `tests/test_mockup_render.py`
  (plan §7): golden-image test on a checked-in fixture bundle, `MockupRenderError`
  on missing dir / missing overlay / malformed aperture, order preservation,
  determinism, purity. *(Gate: dependency decision resolved first.)*
- **Task 2 —** `mockup_templates` block in `config/static_config.json` +
  `config.get_mockup_templates(group_type, orientation)` + scene-ID→bundle-dir
  resolver (plan §5). Test the placeholder fail-loud path.
- **Task 3 —** rewire `pipeline/primary_mockup.py` (stage 3): render via the
  compositor instead of consuming Gelato's gallery; write `product_images` with
  the existing ordering + `image_type` (3 `flat_mockup`, then `lifestyle`);
  render failure → `mockup_failed`; Gelato create still runs for fulfilment,
  its gallery discarded; **do not** touch the Gelato "mockups ready" poll (plan
  §6 flags it as a separate, verify-first follow-up). Dry-run tests only.
- **Task 4 —** rewire `pipeline/group_mockup.py` (stage 8): same, keyed by the
  group under review, using that group's re-crop.
- **Task 5 —** Etsy publish (stages 7/11): `uploadListingImage` in list/rank
  order (flat first), behind the existing dry-run flag. No live upload.
- **Task 6 —** fixtures/bundles: decide with me which bundles are canonical
  (bring the approved `proto/mockup-scene-prototype` bundles onto this branch, or
  wait for GL-6-proper — ask, don't assume) and add a small test fixture bundle
  under `tests/fixtures/`.
- **Task 7 —** docs: update `CHANGELOG.md` and the relevant SPEC section; confirm
  the full suite green. Manual M1 (render the real master into the real
  primary/portrait bundles, eyeball vs. the findings' spike bar) **only on my
  go-ahead**; no live Etsy/Gelato writes.

### Watch-items (plan §9)
- Over-fill needs framed scenes' `overlay.png` to carry the opaque frame/mat
  inner edge — the prototype overlays are lighting-only. If a fixture scene
  lacks it, note it as an authoring gap (GL-6-proper), don't hack around it.
- Use `opencv-python-headless` (not `opencv-python`) if Option A — no X11 in the
  cron. Confirm the wheel fits the scheduled-function image budget.
- Pin opencv/numpy versions and keep the golden test tolerant to minor version
  drift.

### Finish — open a PR to `master` (do not merge)
When the final review is clean and the suite is green:
1. Push `feat/gl5-mockup-compositor`.
2. Open a PR to `master` (`gh pr create` if `gh` is available; otherwise push and
   give me the compare URL for `github.com/qvajda/qhoto_printshop`). PR body:
   summary, the tasks/commits, the dependency decision taken, test count, what's
   dry-run vs. verified, and the explicit note that **no live Etsy/Gelato writes
   were performed**.
3. **Do not merge** — leave it for my review (reversibility rule). List anything
   still needing a live M1 before merge.
