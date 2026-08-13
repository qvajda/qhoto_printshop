# Implementation kickoff prompt — live-test readiness fixes (2026-07-18, rev 2)

Ready-to-paste prompt for a Claude Code session. Source of truth for every
issue referenced below: `docs/live_test_readiness_review_2026-07-18.md`
**including its Addendum** (finding IDs B1-B5, H1-H5, M1-M4, C1-C3).
Rev 2 incorporates the owner's post-review feedback: drafts are the intended
Etsy state (B1 inverted), the DPI shortfall (B5), and the artwork-quality
findings (H5).

---

## PROMPT — paste from here down

You are implementing the fixes from
`docs/live_test_readiness_review_2026-07-18.md` (read the Addendum — it
supersedes parts of the original findings) in the qhoto_printshop repo.
Read, in this order, before writing any code: `CLAUDE.md` (hard constraints —
v4.11), the readiness review + Addendum, and the spec sections it cites in
`docs/SPEC_v4.11.md`. Do not guess at behavior that's already specified.

### Method — SDD, same convention as the base-artwork-persistence branch

Follow the pattern in `.superpowers/sdd/progress.md` exactly:

- Work on a branch off master (`fix/live-test-readiness`). **Precondition
  (Stage 0, before any code):** resolve the uncommitted state on master with
  the user — there is a 64-file pure line-ending diff (verified content-free
  via `git diff --ignore-all-space`), plus untracked `.agents/`, `.claude/`,
  db backups, and two docs. Ask the user whether to (a) commit the EOL
  normalization + a `.gitattributes` as its own commit, or (b) discard it and
  add `.gitattributes` to prevent recurrence. Do not branch on top of an
  undecided dirty tree. Also flag: master is 17 commits ahead of origin —
  recommend pushing before starting (user's call).
- One task = one commit. Write a task brief before, a task report after,
  append to a progress ledger (`.superpowers/sdd/` — new files, don't touch
  the base-artwork ones).
- Run the full test suite after every task; a task isn't complete below
  full green (baseline today: **316 passed, 0 skipped**).
- Final whole-branch review (fresh reviewer pass over the full diff range)
  before merge, findings fixed and re-reviewed — the base-artwork branch's
  final review caught 1 Critical the per-task reviews missed; keep that step.

### Hard rules (from CLAUDE.md + the user's reversibility policy)

- **No real external calls without explicit user go-ahead.** Every Gelato/
  Etsy/Telegram/Replicate/R2 touch during development runs against dry-run
  flags (`GELATO_LIVE_MODE`/`ETSY_LIVE_MODE` unset) or mocks. The sequence
  below needs no live call until Task 10, which is proposal-then-stop.
- **Etsy listings stay DRAFTS.** Activation costs $0.20/listing and is a
  manual dashboard decision by the owner. Nothing in the pipeline may call
  `update_listing_state("active")` or otherwise flip listing state — see
  Task 6, which makes this a tested invariant, not a convention.
- FLUX.1 [schnell] only; never substitute dev. One image-generation per
  design — group-level crop/retry reuses the base image. (Critic-fail
  regeneration, up to the existing 3-attempt cap, is the one specified
  exception; Tasks 8-9 work inside that cap, never around it.)
- Never call `create_draft_listing` — Gelato pushes, we patch.
- All Gelato creates stay routed through
  `group_product.create_or_reuse_group_product`; don't fork a second create
  path.
- `TELEGRAM_ADMIN_CHAT_ID` stays env-only. Placeholder IDs reaching a real
  call must keep failing loudly.
- If a fix seems to require changing a CLAUDE.md hard constraint, stop and
  raise it — don't edit the constraint.

### In scope — tasks, in order

**Task 1 — B3: fan-out poll interval (smallest, unblocks confidence).**
`pipeline/group_mockup.py:33` and `:85`: default `poll_interval` 3.0 → 10.0.
Add the H4 regression tests: assert `create_group_mockup` /
`run_group_mockup_cycle` pass ≥10s into `create_or_reuse_group_product` by
default, and assert `group_product._jittered` stays within ±20%.

**Task 2 — C1: declare runtime deps.**
Add `requirements.txt` (`httpx[http2]==0.28.1`, `pillow`); keep
`requirements-dev.txt` for pytest. Trivial, but do it early so every later
task's "fresh env would break" excuse is gone.

**Task 3 — H2: route the R2 PUT through the shared client.**
Add a raw-response helper to `pipeline/http.py` (e.g.
`put_bytes(url, data, headers) -> httpx.Response` via the existing
`_request`, so it inherits keep-alive, honest UA, and 1010 backoff). Repoint
`artwork_store._r2_put_object` to it. Preserve fail-loud non-2xx (the
`HTTPError` from `_request` already does). Tests: SigV4 headers pass through
untouched; non-2xx raises; no `urllib.request.urlopen` remains in
`pipeline/` (grep-test it — that's the claim that quietly regressed last
time).

**Task 4 — B5: print resolution ≥150 DPI for every offered size.**
Two halves, one commit each is fine if cleaner:
(a) **Bigger master.** Current chain (FLUX `megapixels: "1"` 2:3 = 832×1216,
ESRGAN `scale: 4` = 3328×4864) yields ~142 DPI at A1 vs. Gelato's stated
150 minimum / 300 ideal for posters. Raise the upscale so the master clears
**≥150 DPI at A1 with margin** (target ~284 DPI: ESRGAN `scale: 8` →
6656×9728, or a chained 4×→2× pass if a single scale=8 call fails
Replicate-side — output-size limits for `nightmareai/real-esrgan` at this
input size are unverified; the *code* ships with the chosen parameters and
Task 10 verifies live before the E2E). Update `replicate_client.py`'s
scale comment.
(b) **Fail-loud DPI guard.** In the create path (alongside the existing
placeholder/replicate-URL guards' pattern): given the master's pixel
dimensions and the group's largest size in inches (derive from the size
table / group_type — `image_crop.target_ratio_for_group_type` shows the
parsing convention), refuse a real (non-dry-run) Gelato create below
150 DPI, with the computed number in the error. Pixel dims come from the
local archive (`base_image_local_path`) via PIL — no network call.
(c) **Downstream size audit (same task, report-level):** bigger masters
inflate the local crop JPEGs (`image_crop.py` saves full-res JPEG q90) —
Telegram photo limits (~10MB multipart) were already bitten once (commit
b3977d1). Cap/resize the *preview* crop output (previews don't need print
resolution — 2000px long edge is plenty); note R2 object growth
(~4× bytes) in the report.

**Task 5 — H1: publish_failed is no longer a dead end.**
(a) `publish_group.handle_decision` approve path: retry the patch once
(mirror `publish_primary_group.py:94-98`). (b) Digest surfacing: at the end
of `digest.run_digest_cycle`, send one plain `sendMessage` listing any groups
at `status='publish_failed'` (group id, type, candidate, failure age) — spec
section 3 step 7's "surface the failure in the next digest". (c) The hourly
poll cycle re-attempts `patch_etsy_listing` for `publish_failed` groups whose
recorded decision is `approved`, at most once per run. Tests for all three,
including "approve tap consumed + patch fails twice → surfaced next digest,
retried next poll".

**Task 6 — B1 (inverted): drafts-stay-drafts, as a tested invariant.**
No activation wiring — the opposite. (a) Add a test asserting
`patch_etsy_listing` never calls `update_listing_state` / never sends a
`state` field (guards against a future "helpful" regression — the function
exists unwired, which is exactly one refactor away from an accidental $0.20-
per-listing surprise). (b) Comment `update_listing_state` itself: unused by
design during testing; activation is manual in the dashboard; activation
costs $0.20/listing. (c) Comment `isVisibleInTheOnlineStore: False` in
`gelato_client.py:113`: confirmed live 2026-07-18 to land listings as Etsy
drafts (pre-review leak defense + testing posture). (d) Propose (don't
apply — user sign-off) a short CLAUDE.md/SPEC amendment documenting: listings
publish as drafts; `group_products.status='published'` means
"patched draft"; owner activates manually per listing; auto-activation is a
deliberate non-feature until a production go-live decision.

**Task 7 — M1 + M3: digest race and sync-timeout margin.**
(a) `resolve_etsy_listing_id` default timeout 600 → 1200s (observed ~8min
typical lag; 600s is one slow sync from a false `publish_failed`).
(b) Digest duplicate-send guard: before `sendMediaGroup`, skip if a
`group_messages` row exists (both `digest.py` and `group_digest.py`); and
make `process_update`'s callback match accept any `group_messages` row for
the group rather than exactly the first (`publish_primary_group.py:222-230`),
keeping the chat-id check.

**Task 8 — H5 (prevent): generation prompt hardening.**
Rewrite `NICHE_STYLE_SCAFFOLD` (`generate.py:9-14`) against the five observed
failure modes (near-empty gradients ×2, too-sparse line art ×2, off-center +
incoherent subject ×1, floating/disconnected elements, smudged fine detail):
demand **one clear, coherent central subject** that occupies a substantial
share of the frame; centered/balanced composition; anatomically/botanically
coherent forms; crisp edges between color zones (the niche is flat
monocolor-zone art — smudging is conspicuous); keep the existing flat-art/
no-scene guardrails and `sanitize_niche` untouched. Keep it prompt-craft, not
a novel: FLUX schnell follows terse, concrete instructions better than long
prose. Add/extend the prompt-content test (a `build_prompt` assert exists —
`test_generate.py`) for the new guardrail phrases.

**Task 9 — H5 (detect): cheap local sanity gate + critic rubric extension.**
Both live inside the existing critic 3-attempt loop — no new retry budget:
(a) **Local gate, zero API cost.** In `run_critic_pass`, before the vision
call: load the master from `base_image_local_path` (PIL, already a dep) and
fail the attempt locally if it's near-empty — e.g. grayscale stddev below a
threshold and/or edge-pixel ratio (simple gradient magnitude) below a floor.
Candidates #2/#6 (flat cream gradients) must fail it; a normal botanical
print must pass. Calibrate the thresholds against the 7 archived masters in
`db/base_artwork/` — they are a labeled test set: {2,6} must fail, {1,5}
must pass; add a unit test doing exactly that against small synthetic images
(flat gradient vs. structured). A local fail records a critic attempt with a
canned reason ("near-empty image: stddev X, edge ratio Y") and triggers the
normal regeneration path — same counter, same cap, no Anthropic spend.
(b) **Rubric extension.** Extend `CRITIC_RUBRIC_PROMPT_TEMPLATE`
(`critic_pass.py:12-26`) with explicit criteria: subject presence (reject
near-empty/gradient-only), subject coherence (reject nonsensical hybrid
forms), composition (reject off-center subject or large dead zones unless
clearly intentional), detail quality (reject smudging/muddiness at zone
boundaries), and visual density appropriate for wall art (reject overly
sparse line work). Keep the pass/fail + reason output contract unchanged.
Note in the task report: the rubric has never run live (0 rows in
`critic_pass_attempts`), so Task 10's E2E is also the rubric's first live
exercise — expect calibration feedback.

**Task 10 — live verification (STOP — go-ahead gate), with failure protocol.**
No code beyond the runbook. Produce it, then wait for explicit user approval
per the reversibility rule; do not execute any step without it.

Runbook contents:
1. Pre-run manual items for the user: confirm the Gelato-dashboard 10x24
   placeholder fix (B2 — blocker for the 10x24 leg; if unconfirmed, run E2E
   with the 10x24 group expected-fail and queue the code-crop-with-R2-hosting
   fallback as a follow-up branch). DB triage: **all 7 queued candidates are
   condemned by the owner's artwork review — back up `db/qhoto.sqlite3`,
   prune all 7** (destructive → explicit user confirm), and let the run
   generate fresh candidates through the Task 4+8 pipeline.
2. B5 verify: one real ESRGAN call at the chosen scale — confirm Replicate
   accepts it and output dims match the DPI math, before burning a candidate.
3. H3 reconcile: `list_products` against the Gelato store; diff vs. DB ids;
   report orphans (delete only on user instruction); cross-check the Etsy
   Drafts tab count.
4. The E2E run: fresh single candidate, full flow, both fan-out groups, at
   least one approve and one reject across them (M1 matrix, SPEC section 5).
   Name every live call before making it. **Verify in the run report:** all
   resulting listings are drafts; no listing state ever changed; DPI shown in
   the Gelato dashboard ≥150 for every offered variant.

**Failure protocol (user-mandated).** If any step of Task 10 fails — or
succeeds partially:
- Write an incident note to memory before anything else: append to
  `.remember/today-<date>.md` (existing convention) a compact entry with:
  what failed, at which pipeline stage, the exact error/CF-Ray/API response,
  what was ruled out, and the state left behind (DB rows, Gelato products,
  Etsy drafts created — ids included).
- If the failure is diagnosable, also write a **start-up prompt** for the
  next session to `docs/` (e.g.
  `docs/e2e_retry_kickoff_prompt_<date>.md`): context in three sentences,
  the incident summary, what to fix or re-verify first, and how to resume
  the E2E without re-doing completed verifications.
- **Either way — success or failure — Task 10 ends the session** (context
  reset is planned). The final message must be a handoff: state of the
  branch (merged or not), state of external accounts, and the single next
  action.

### Explicitly deferred — do not build

- **Etsy activation flow:** deliberate non-feature until a production
  go-live decision (Task 6 documents this). Manual dashboard activation only.
- **B2 code-crop fallback** (crop-to-live-placeholder-ratio + R2 hosting):
  only if the dashboard fix is confirmed impossible. Gated on Task 10 step 1.
- **M2 crop variation / edit-note plumbing for secondary groups:** the
  original Task 8 (cap secondary critic attempts at 1) is dropped from this
  branch to make room for the H5 work — secondary-group critic behavior will
  produce real data in the E2E first; revisit with it.
- **M4 cron entrypoints** (hourly poll / twice-daily batch runners +
  scheduling): separate small branch after the E2E passes. Flag to the user
  that "unattended" in the DoD is satisfied per-stage, not per-calendar,
  until this lands.
- **C3 hygiene batch** (rename `run_m1_live_test.py` out of pytest's
  collection pattern, honest UA in `r2_healthcheck.py`, drop unused
  `ALLOWED_TELEGRAM_USER_ID` from `.env.example`): fold into Stage 0 or the
  final-review commit if trivial, else defer — none of it blocks the run.
- **C2 EOL normalization decision:** user decision at Stage 0, not a task.
- **1010 egress A/B test and vendor support tickets:** user-side actions.

### Definition of done

One clean end-to-end live run per CLAUDE.md's aspect-ratio-group flow:
fresh candidate → generate (flat art, no scene leak, passes the local sanity
gate, master ≥150 DPI at A1) → primary critic pass (extended rubric, first
live exercise) → primary digest → approve → primary group publishes as ONE
Gelato product / ONE Etsy listing, 4 size variants, fully patched
(title/description/tags/section/partner/who_made/per-variant price — meta
already confirmed working) and sitting as an Etsy **draft** → 5x7 and 10x24
groups each produce their own cover-cropped review entry in the same evening
run → their approve/reject each processed independently (at least one of
each across the two) → no duplicate Gelato products (DB product count ==
Gelato store count afterwards) → no group silently stalled
(`publish_failed` empty or surfaced in a digest) → **no listing activated**
(all drafts; owner activates manually if quality warrants) → Gelato
dashboard shows ≥150 DPI on every offered variant → full test suite green
throughout. Every live call individually pre-approved by the user; Task 10's
failure protocol and end-of-session handoff apply regardless of outcome.
