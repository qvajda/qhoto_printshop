# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

Planning artifact only — no code written in this pass. Counter-checks the
owner's mental milestone map against the actual repo/config state, then
sequences the remaining work to reach a public "go live" and lists every
open point classified by work-type.

Evidence base: SPEC_v4.11, SPEC_v4.10 Addendum A (custom mockups), CHANGELOG
(through 2026-07-20), round-3 validation results, remediation-plan-consolidated,
and a live audit of `pipeline/`, `config/static_config.json`, `.env`, git
branches/log.

---

## Part 1 — Where we actually are (owner's view vs. reality)

### Achieved milestones — counter-checked

**1. "Full pipeline works, end result = a design published on Etsy (some
test scenarios undone)." → TRUE, with one caveat that matters.**
All 13 stages exist as independently-testable modules and the **v4.11
re-architecture is in code**, not just spec: `publish_primary_group.py`
calls `group_product.patch_etsy_listing` (Gelato-pushes-we-patch), never
`create_draft_listing`; `create_or_reuse_group_product` is idempotent
(reuse-before-create, orphan-delete on retry); variant listings +
`group_product_variants` are implemented; `resolve_etsy_listing_id` maps
Gelato `externalId` → Etsy listing. The stale `build_size_listing_data`
create-path is gone (only a vestigial, unused `create_draft_listing` remains
in `etsy_client.py`).
**Caveat:** the *successful* end-to-end live publish was on the **v4.10**
mechanics. The v4.11 rework was built *after* that run, specifically to fix
what the run exposed (variant/listing split, duplicate gallery, Gelato/Etsy
push collision). The v4.11 publish path has **only unit tests — it has never
completed a live end-to-end run.** So "the pipeline publishes to Etsy" is
proven for the *old* architecture and *unproven live* for the current one.

**2. "Research component — deep-research (Cowork) vs. single research yield
different niches/briefs." → TRUE.**
Mode A (in-pipeline v3 brief-writer) and Mode B (owner's parallel Cowork
deep-research briefs, ingested via `pipeline.seed_mode_b`) both exist and
were run head-to-head in round 3. Mode B actually outscored Mode A
(5 good/0 refine vs 3 good/2 refine).

**3. "Art generation quality buffed to acceptable." → TRUE, but not yet on
`master`.**
Round-3 validation = **PASS / GO** (8 good / 2 refine / 0 reject; all defect
classes ≤1; backdrop usage in range). BUT this lives on branch
`fix/generation-quality-round3`, **10 commits ahead of `master`, 0 merged.**
The quality gains aren't in the mainline the runtime would deploy from.

### Missing-before-go-live — counter-checked

- **Lifestyle mockups (v4.10 Addendum A). → CONFIRMED NOT IMPLEMENTED.**
  No `pipeline/mockup_render.py`, no `assets/` scene library, no
  `mockup_templates` block in `static_config.json`. `primary_mockup.py` /
  `group_mockup.py` still consume Gelato's default gallery. The addendum is
  *fully specified and decided* (self-hosted Pillow+homography compositor,
  3 scene sets × 2 orientations × 10 scenes, Gelato gallery dropped with no
  fallback) but **zero code/assets exist.** This is the single biggest build
  chunk left. See scope note below — it may not be a *hard* blocker.
- **Etsy storefront design overhaul. → NOT STARTED** (manual; also the
  project's current Notion "Next Action").
- **Cron automation. → CONFIRMED NOT IMPLEMENTED.** No orchestrator/scheduler
  of any kind; the only entrypoint is `run_m1_live_test.py` (manual,
  one-stage-at-a-time driver). The two-cadence scheduled-function runtime the
  spec mandates does not exist yet.

### Open points the owner's list did NOT include (found in audit)

- **Merge round-3 quality branch → master** (housekeeping, but the runtime
  deploys from master).
- **Full v4.11 end-to-end *live* re-test** — the publish rework is unverified
  outside unit tests (see caveat above), and the M1 spec still has
  **un-exercised scenarios**: the Kill branch, a full 3-attempt critic-pass
  failure + confirmed Gelato `DELETE` cleanup, the full group flow (approve
  primary group + at least one 5x7/10x24 approve *and* one reject/abandon),
  and the allowlist-rejection test (command from a non-admin Telegram ID).
- **Revert Etsy Developer Mode** — the shop is in Developer Mode for testing;
  reverting is **not self-service** (email developer@etsy.com, wait for
  approval). This is an external-lead-time item that must be sequenced before
  a public go-live, and listing visibility observed now isn't representative.
- **Google Trends API alpha access** — standing zero-cost application, still
  open per spec §7.
- **Mockup scene *authoring*** — distinct from the compositor *code*: ~30–60
  scene bundles (background + shadow/highlight overlay + aperture corners)
  must be generated offline (FLUX.1 [schnell] only) and annotated. A content
  task, not just an engineering one.
- **Slow-loop performance monitor** (daily views/favorers/orders snapshot +
  deltas) — spec parks this at M3; treat as post-launch.

### Scope note / pushback worth a decision

The pipeline **can technically publish today using Gelato's default
mockups.** The Addendum's premise is quality/brand consistency, not
function. So **custom mockups are arguably a fast-follow, not a hard go-live
blocker** — launching on Gelato galleries first would let you go live weeks
sooner and validate the v4.11 publish path + unit economics on real traffic,
with the custom compositor shipping as v1.1. Recommend making this an
explicit go/no-go decision rather than defaulting to "mockups block launch."

### Verdict

Owner's self-assessment is **substantially accurate.** The one correction
that matters: milestone 1 is "code-complete at v4.11, live-proven only at
v4.10" — the live re-test is a real, non-optional gate, not a nice-to-have.
Everything else on the "achieved" list holds; the "missing" list is right and
gains four not-listed items (branch merge, live re-test, Dev-Mode revert
lead-time, scene authoring).

---

## Part 2 — Open points, classified by work-type

Types: **IR** implementation-research (→ plan + code-session starting prompt) ·
**R** research (→ findings for planning) · **C** coding & implementation
(→ code + commit/PR) · **M** manual action (→ state changed) · **T** test run
(→ pass/fail + feedback) · **D** decision/sign-off *(added type — PRD-gate
calls only the owner can make, per CLAUDE.md §2/§4)*.

### Go-live blockers

| ID | Type | Item | Input → Output |
|---|---|---|---|
| GL-1 | C | ~~Merge `fix/generation-quality-round3` → `master`~~ **✅ DONE 2026-07-22** — PR completed on remote, local caught up with master | — |
| GL-2 | D | Custom mockups before launch — **✅ RESOLVED 2026-07-22 (post-prototype): GO pre-launch, scoped to near-frontal scenes.** Even flawed composites clear the Gelato bar easily; the scenes themselves are high quality (owner: 4/5 samples strong). **Angled/leaning scenes → v1.1 fast-follow** (needs better corner-detection or the Dynamic Mockups escape hatch, Addendum §7). The compositor — not the scenes — is the risk (see GL-4). | — |
| GL-3 | D | Cron deployment target — **PRELIMINARY DECISION (2026-07-22): host locally on desktop for now.** Still run GL-8 to confirm/refine (reliability of a desktop always-on host, wake/sleep, vs. a cheap always-on option) | GL-8 findings → confirm or revise |
| GL-4 | R→IR | **Compositor approach research — REPRIORITIZED to the critical mockup risk (2026-07-22).** The prototype's throwaway compositor performed poorly on *every* axis (corner/edge detection, blank-canvas fill, self-artefact cleanup, partial foreground occlusion). Owner's steer: **find an existing library / OSS project** for poster-into-scene compositing (perspective warp + shadow/occlusion + robust aperture detection) rather than hand-roll Pillow+homography from scratch. Evaluate build-on-a-lib vs. **Dynamic Mockups** hosted API (Addendum §7 escape hatch) vs. thin homography. | briefing → library/approach recommendation + `mockup_render` impl plan |
| GL-5 | C | Build `pipeline/mockup_render.py` + `mockup_templates` config + rewire `primary_mockup`/`group_mockup` + Etsy upload order (Addendum A), on GL-4's chosen library. **v1.0 scope = near-frontal scenes only** (what the compositor handles reliably); angled-scene corner-detection is v1.1. | GL-4 recommendation → PR |
| GL-6 | IR+M | Scene-authoring — **prototype ✅ DONE 2026-07-22** (kickoff `docs/2026-07-22-gl6-mockup-prototype-kickoff.md`; scenes high quality, GL-2 = go). **Remaining: author the real library**, scoped near-frontal for v1.0 (defer heavily-angled lifestyle scenes to v1.1). Watch the 3-flat/7-lifestyle split — many lifestyle scenes are angled, so the v1.0 set may skew more frontal until GL-5's corner-detection improves (open question, flag in authoring). | → the finished near-frontal `assets/mockups/…` bundles |
| GL-7 | C | Cron orchestrator: two scheduled cadences (hourly Telegram poll, twice-daily batch) wiring the existing stages; one function per stage, not one loop | GL-3 decision + kickoff → PR |
| GL-8 | R | Where to host the scheduled functions (tool-fit: Cowork scheduled task vs. Claude Code cron vs. a real host — Fly/Render/Cloudflare/GitHub Actions), given cost, reliability, and the persistent-process ban | briefing → hosting recommendation w/ named option |
| GL-9 | T | **Round 1 live re-test — ✅ PASS/GO 2026-07-22, with residuals.** Proven live: S0 clean; S1 allowlist (synthetic non-admin callback discarded+logged); S2 Kill/hold (0 Replicate calls); S3 happy path end-to-end (after 2 retries) — primary published (4 variants, exact spec prices, all Etsy fields), 5x7 published (Small shipping, €19), 10x24 critic-rejected 3× + cleanly `DELETE`d (**proved S4 group-level for free**; dedicated S4 skipped by owner). 4 real Etsy drafts live, match DB, no orphans. **Residuals spun out → GL-15/16/17.** Guide: `docs/2026-07-22-v411-live-test-launch-guide.md`. | — |
| GL-13 | T | **Round 2 live re-test (post-mockup)** — the mockup-*dependent* slice that Addendum A rewrites: custom gallery uploaded via `uploadListingImage` in rank order, critic pass over the *custom* scenes, `mockup_failed` → retry path (no Gelato fallback), and the scene-ID placeholder fail-loud guard. Narrower than Round 1. **Fold in GL-14's real-crop check** (confirm the cover-cropped image actually reaches Gelato, no white bars). | delta launch guide → pass/fail |
| GL-14 | C | **Fix: group crop never sent to Gelato (found live, GL-9).** `group_product.py` sends only the Telegram-preview thumbnail cropped — Gelato gets an un-cropped image, reproducing the historical 10x24 white-bar defect. Blocker before 5x7/10x24 sell at real print. Writeup + fix shape: `docs/2026-07-22-group-crop-not-sent-to-gelato-bug.md`. | writeup → fix + commit |
| GL-15 | C | **Etsy OAuth auto-refresh in the pipeline (found live, GL-9).** Token expired mid-round; no in-pipeline refresh (`refresh_etsy_token.py` is a manual standalone). **Hard blocker before cron/unattended** — an expired token can't be hand-fixed at 2am. Wire refresh into the Etsy call path. | → refresh integrated + tested |
| GL-16 | IR→C | **Unattended-resilience hardening (found live, GL-9).** Live run showed material API flakiness — notably **retries failing fast right after a reject gate is hit** — and needed coding-session babysitting (e.g. hand-fixing a candidate's DB status after a failure). Unattended cron has no such support. Investigate the post-reject flakiness; add **retry-with-backoff + delay**, and **idempotent/self-healing state transitions** so a mid-run failure never strands a candidate. **Hard blocker before cron.** | briefing → resilience design → PR |
| GL-17 | T | **Residual live-scenario coverage (from GL-9).** The actual Telegram **Reject button** (human reject, vs. the auto critic-reject already proven) was never tapped; sweep any other un-hit interactions. Small targeted run — fold into GL-13 or the next live touch. | mini launch-guide → pass/fail |
| GL-10 | M | Etsy storefront overhaul — banner, sections, About, shop policies, SEO copy (Fable-assisted, owner-driven; one-way-valve safe: built from owner's framing + public sources) | how-to/checklist → live storefront updated |
| GL-11 | M | Revert Etsy Developer Mode (email developer@etsy.com; budget lead time) — sequence before public launch | how-to → Dev Mode off, confirmed |
| GL-12 | M | Apply for Google Trends API alpha access (zero cost, parallel) | how-to → application submitted |

### Post-launch backlog (owner's list 5–11, lightly classified)

| Type | Item |
|---|---|
| C | Telegram UX polish — richer inline buttons, edit-flow, digest legibility |
| C+R | Cost/sales dashboarding & reporting (slow-loop monitor first: daily views/favorers/orders snapshot + deltas → group → design roll-up; then a re-openable status view / **Cowork artifact** is a strong fit here) |
| IR+C | Landscape-vs-portrait handling + a dedicated narrow/long (10x24) Gelato template refinement |
| IR | Extension beyond posters (apparel, etc.) — new mini-spec per product class |
| R+C | New audience: FR/Wallonian prints (owner already has a researched candidate set) |
| IR | Generalize into a reusable pattern for sibling projects (faceless YouTube, CV-template shop, …) |
| M+C | Documentation polish — README, user guide, runbook |

---

## Part 3 — Proposed sequencing (implementation sessions)

Critical path to a public launch. Sessions are sized to roughly one sitting
each; parallelizable tracks noted.

**✅ Done 2026-07-22:** Session 1 (GL-1 merge), Round 1 live test (GL-9
PASS/GO), mockup prototype + GL-2 decision (go, near-frontal). The `max_tokens`
1024→2048 truncation bug found in GL-9 is **already fixed & committed to
master** (compliance_draft.py + critic_pass.py).

**Session 3 — live-findings fix cluster (C), do soon.** The three items GL-9
surfaced. GL-14 (group crop actually sent to Gelato) can pair with GL-15 (Etsy
auto-refresh) in one small branch. **GL-16 (resilience) is bigger — likely its
own IR→C branch**, and is the real long pole for going *unattended*.

**Track A — mockups (GL-2 = go, near-frontal for v1.0):**
- **Session 4a (R→IR):** GL-4 compositor-approach research — **now the critical
  mockup unknown** (the throwaway compositor failed on every axis). Find an
  existing library / OSS, or commit to Dynamic Mockups (Addendum §7). Output a
  recommendation + impl plan before any build.
- **Session 4b (C, PR):** GL-5 build `mockup_render` on the chosen library,
  near-frontal scope; rewire the two mockup stages + Etsy upload order.
- **Session 4c (M):** GL-6 author the real near-frontal scene library (scenes
  themselves are already proven high-quality).

**Track B — automation (parallel, but gated):**
- **Session 5 (R):** GL-8 confirm/refine the *local-desktop* host choice (GL-3).
- **Session 6 (C, PR):** GL-7 two-cadence orchestrator — **blocked by GL-15 +
  GL-16.** Do not switch to unattended cron until token auto-refresh and
  resilience hardening land, or the first overnight run strands on a flaky call
  or an expired token with no one to fix it.

**Track C — manual, parallel, owner-driven:** GL-10 storefront overhaul,
GL-12 Google Trends application now; **GL-11 Dev-Mode revert request** as soon
as a launch date is roughly known (external lead time).

**Session 7 — Round 2 + residuals live test (T).** GL-13 (mockup-dependent
slice) **+ GL-14's real-crop confirmation + GL-17 (human Reject button** and any
un-hit interactions). One live pass covering everything the fix cluster and
mockups touched.

**Go-live gate:** GL-9 ✅ **+** live-fix cluster landed (GL-14 crop, GL-15
token, GL-16 resilience) **+** mockups shipped near-frontal (GL-4→GL-5→GL-6)
**+** cron runnable & unattended-safe (GL-7, gated on GL-15/16) **+** storefront
(GL-10) **+** Round 2 + residuals clean (GL-13/14/17) **+** Etsy Developer Mode
reverted (GL-11).

### Tool-fit flags (CLAUDE.md §7)

- **Cron runtime is not a Cowork job.** The spec forbids a persistent
  service, but twice-daily + hourly scheduled functions still need a real
  always-available host (or a durable scheduler). Cowork/live-session is the
  wrong tool for the recurring runtime — decide GL-3 deliberately (GL-8).
- **Compositor build → Claude Code**, not Cowork: it's a multi-file,
  test-driven engineering task in the repo. Cowork is right for the planning,
  scene-authoring, storefront, and Notion work.
- **Post-launch cost/sales view → a Cowork live artifact** is a natural fit
  (re-openable, pulls fresh connector data) — flagged for that backlog item.

---

## Part 4 — Coding-session feedback log (2026-07-22)

Raw outcomes of the first two sessions, for traceability; actions are folded
into Part 2/3 above.

**Session A — mockup prototype (GL-6 prototype).**
- Session verdict: go pre-launch, scoped near-frontal; angled → v1.1 (better
  GL-5 corner-detection, or Dynamic Mockups escape hatch).
- Owner read: **scenes are high-quality (4/5 samples)** — full library likely
  smooth. **The throwaway compositor is the weak link** — poor on corner/edge
  detection, blank-canvas fill, self-artefact cleanup, and partial foreground
  occlusion. → **GL-4 reprioritized to library-first research**; GL-5 v1.0 =
  near-frontal only.

**Session B — v4.11 Round 1 live test (GL-9).**
- Verdict **GO**. S1 allowlist ✅, S2 Kill/hold ✅ (0 Replicate), S3 happy path
  ✅ (after 2 retries) — primary (4 variants, exact prices, all fields), 5x7
  (Small, €19), 10x24 critic-rejected 3× + clean `DELETE` (**S4 group-level
  proven for free**). 4 Etsy drafts live, match DB, no orphans.
- Bug **fixed on master:** `max_tokens` 1024→2048 (compliance_draft.py,
  critic_pass.py) — richer prompts were truncated.
- Bug **found, deferred → GL-14:** group cover-crop never sent to Gelato (only
  the Telegram preview is cropped) → 10x24 white-bar risk.
- Worked around → new items: **Etsy token expired mid-round (→ GL-15)**;
  branch mix-up fixed via cherry-pick, no data lost.
- Owner read: **not all scenarios hit** — human Telegram **Reject button**
  untapped (→ GL-17); and **material API flakiness** (esp. fast retry-failures
  right after a reject gate) means unattended running needs **retry/backoff +
  self-healing state** before cron (→ GL-16).
