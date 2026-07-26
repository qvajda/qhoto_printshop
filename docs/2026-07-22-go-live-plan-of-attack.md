# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

> **Last updated 2026-07-26** — GL-6 **attempt 2 ran and was owner-reviewed:
> 3 of 4 scenes still defective.** Root cause is now understood one level deeper
> and it is *not* purely authoring: a real compositor bug (black border-mode
> contamination) was papered over bundle-side, and the quad-as-silhouette
> primitive cannot express curl / occluders / nested mat lines. **New scope
> GL-21 (compositor: unfreeze + per-pixel matte + aspect guard)** now precedes
> GL-6, and GL-6 attempt 3 moves to keyed generation + derived (not hand-read)
> authoring. Plan: `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md`
> (owner-approved decisions §7). Earlier: 2026-07-24 folded in GL-5 build +
> GL-16 (merged) + GL-4 (closed); added GL-18/19/20; live-fix cluster closed;
> GL-7 unblocked. See Part 4 (cont.).

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
| GL-4 | R→IR | **Compositor approach research — ✅ DONE 2026-07-23.** Findings + impl plan both written (`docs/2026-07-22-compositor-approach-findings.md`, `…-gl5-compositor-implementation-plan.md`). **Key reframe:** the prototype's failures were *detection* failures, not warp failures — and the Addendum authors the aperture into `meta.json`, so **runtime detection is deleted entirely**. Recommendation: **self-host on OpenCV** (`getPerspectiveTransform`+`warpPerspective`, 2× supersample, ~1.5–2% quad over-fill, frame-edge baked into `overlay.png`) — a spike hit production-clean near-frontal on the first pass. v1.0 and v1.1(angled) are the **same code path**; angled needs better *authoring* precision, not a new engine. Dynamic Mockups = narrow escape hatch only (PSD re-authoring, 24h link expiry, vendor-in-cron). | — |
| GL-5 | C | Build `pipeline/mockup_render.py` + `mockup_templates` config + rewire `primary_mockup`/`group_mockup` + Etsy upload order (Addendum A), self-hosted OpenCV per GL-4. **✅ BUILD COMPLETE + CODE VALIDATED, ⏳ NOT MERGEABLE yet 2026-07-24** — branch `feat/gl5-mockup-compositor`, 504/504, PR #2 open. **GL-19 confirmed the compositor code is correct** (mid-artwork areas render clean everywhere) — but its only real asset inputs (the 4 prototype bundles) fail the B+ bar on authoring defects, so it can't ship Etsy-facing images as-is. Gelato gallery fully discarded. Review earlier caught 2 bugs (empty-gallery infinite-retry; PNG mis-tagged JPEG). **Merge now gated on GL-21 (compositor fixes) + GL-6 attempt 3 (bundles)**, then a clean GL-19 harness re-run + guarded upload. No live writes yet. **Correction 2026-07-26: "the compositor code is correct" was too strong** — GL-19 proved it renders clean *mid-artwork*; the artwork *border* carries a real bug (`warpPerspective` defaults to `BORDER_CONSTANT`=black under `INTER_CUBIC`, contaminating 710–1479 partial-alpha border px per scene by ~120/255 mean). Fixed under GL-21, not by re-authoring. | GL-21 → GL-6 attempt 3 → GL-19 re-run → merge |
| GL-6 | IR+M | Scene-authoring — **prototype ✅ DONE 2026-07-22. Attempt 1 ✅ discarded. Attempt 2 ✅ RAN 2026-07-24 (5 commits `30124f1..00ac765`, 504/504) → ❌ owner review 2026-07-26: 1 of 4 scenes accepted.** `lifestyle_bedroom_console` passes; the other three fail on defects the *authoring doctrine could not express*: curled-paper silhouette vs. a 4-point quad (clips scene shadow mismatch), axis-aligned occluder boxes cutting square notches (bookstack), and an over-inset quad inside the mat's own photographed panel line (sage). **Attempt 3 OPEN — scope changed on all three axes** per `docs/2026-07-26-gl6-attempt3-production-readiness-plan.md`: **(1) compositing** → GL-21 (per-pixel `matte.png` replaces quad-as-silhouette + occluder boxes + the attempt-2 repaint band); **(2) generation** → scenes generated with a **solid key-colour print panel** so the matte extracts exactly and the drop shadow belongs to the real silhouette by construction (machine-checked generation acceptance replaces prose criteria); **(3) authoring** → `scripts/scene_author.py` **derives** matte/quad/gain/occluders from the image; **zero per-scene constants in source** (attempt 2's 4 hand-read quads + margin tuples + occluder boxes are the thing that does not scale to the ~26 remaining bundles). New standing rule: **no bundle-side workaround for a compositor defect.** Owner-approved decisions: keyed generation as Plan A; unfreeze the compositor; cover-crop ≤2 % + fail loud; library target confirmed at 3 flat + 7 lifestyle per group. Attempt-2 criteria (c)+(d) are **superseded** — with a matte, sub-pixel tracing and α-255 occluder stamping both stop existing. | plan ✅ → coding-session prompt → bundles passing `mockup_qa.py` + the GL-19 harness |
| GL-21 | C | **Compositor hardening — P1 ✅ SHIPPED 2026-07-26 on `feat/gl21-matte-compositor` (branched off `feat/gl5-mockup-compositor`); 517/517.** C1+C2+C3 in `pipeline/mockup_render.py` + 13 tests + `scripts/mockup_qa.py` (6 detectors, each demonstrated firing on a known defect, + contact sheets). C1 measured in isolation on the attempt-2 bundles: 947–1627 changed px per scene, **100 % inside the artwork-border band, 0 outside**. C3 refuses the four pre-attempt-3 bundles by design (quads 0.561–0.693 vs a 0.684 master); the 12 gallery-rendering tests moved to aspect-correct stub bundles (`tests/conftest.py`) and one new test asserts the real bundles now fail loud — flips back when GL-6 attempt 3 re-authors them. **The compositor freeze is lifted in CLAUDE.md + the Addendum.** Original scope: `pipeline/mockup_render.py` is **explicitly unfrozen** (owner-approved) for three additive changes: **C1** `borderMode=BORDER_REPLICATE` on the colour warp only (mask warp stays `BORDER_CONSTANT`) — kills the black contamination measured at 710–1479 border px/scene, mean ~120/255, verified 246-vs-0 on a synthetic warp; **C2** optional `matte.png` in the bundle, warped-art alpha ×= matte — the new primitive; absent file ⇒ today's behaviour byte-for-byte, so all 504 tests and existing bundles are unaffected; **C3** load-time aspect guard — cover-crop the artwork to the quad's aspect, **fail loud above 2 %** (attempt 2 found quads 0.63–0.70 against a 0.684 master = up to 5 % silent non-uniform stretch of the print a buyer pays for). Plus `scripts/mockup_qa.py`: 6 automated defect detectors (fringe, key-spill, distortion, coverage, occluder-opacity, silhouette-vs-shadow) + contact-sheet generator, gating owner review. `overfill` stays in the schema for compat, authored 0.0. Pipeline contract (`load_bundle`/`render_scene`/bundle-on-disk) and `group_product.py` unchanged. | plan ✅ → C1–C3 + QA harness + tests green |
| GL-7 | C | Cron orchestrator: two scheduled cadences (hourly Telegram poll, twice-daily batch) wiring the existing stages; one function per stage, not one loop. **✅ UNBLOCKED 2026-07-23** — its gates GL-15 + GL-16 both landed on master. **DoD must include an overnight unattended soak** (GL-16 is proven in unit/scripted-interrupt tests only — the soak is its real production proof; see pushback note). | GL-3 decision + kickoff → PR |
| GL-8 | R | Where to host the scheduled functions (tool-fit: Cowork scheduled task vs. Claude Code cron vs. a real host — Fly/Render/Cloudflare/GitHub Actions), given cost, reliability, and the persistent-process ban | briefing → hosting recommendation w/ named option |
| GL-9 | T | **Round 1 live re-test — ✅ PASS/GO 2026-07-22, with residuals.** Proven live: S0 clean; S1 allowlist (synthetic non-admin callback discarded+logged); S2 Kill/hold (0 Replicate calls); S3 happy path end-to-end (after 2 retries) — primary published (4 variants, exact spec prices, all Etsy fields), 5x7 published (Small shipping, €19), 10x24 critic-rejected 3× + cleanly `DELETE`d (**proved S4 group-level for free**; dedicated S4 skipped by owner). 4 real Etsy drafts live, match DB, no orphans. **Residuals spun out → GL-15/16/17.** Guide: `docs/2026-07-22-v411-live-test-launch-guide.md`. | — |
| GL-13 | T | **Round 2 live re-test (post-mockup)** — the mockup-*dependent* slice that Addendum A rewrites: custom gallery uploaded via `uploadListingImage` in rank order, critic pass over the *custom* scenes, `mockup_failed` → retry path (no Gelato fallback), and the scene-ID placeholder fail-loud guard. Narrower than Round 1. **Fold in GL-14's real-crop check** (confirm the cover-cropped image actually reaches Gelato, no white bars). | delta launch guide → pass/fail |
| GL-14 | C | **Fix: group crop never sent to Gelato — ✅ DONE 2026-07-22.** Full-res cover-crop now hosted on R2 + sent to Gelato for 5x7/10x24; unit-tested and **live-confirmed** (real Gelato products fill frame edge-to-edge, no white bars). Merged to master. | — |
| GL-15 | C | **Etsy OAuth auto-refresh — ✅ DONE 2026-07-22.** 401→refresh→retry, no loop, no `urllib` in `pipeline/`; unit-tested; merged to master. Real-token live smoke deferred to the next live pass (as planned). | — |
| GL-16 | IR→C | **Unattended-resilience hardening (found live, GL-9). ✅ BUILT/MERGED 2026-07-23** — design `docs/2026-07-22-resilience-design.md`; branch `fix/resilience-hardening` merged to master (`56b4865`), 483/483 green. Shipped: `http.py` transient backoff (5xx/timeout/reset/429, `Retry-After` honored+capped, gated to idempotent GET/HEAD/PUT so POST/PATCH are never blind-retried); `critic_pass.py` classifies regen-burst faults (vendor/network → leave candidate for next sweep, no abandon/no attempt burn; real defects still abandon); `cleanup.py` reclaims stranded `pending` group_products; `test_resilience_interrupt.py` pull-the-plug acceptance test. **Caveat: proven in unit/scripted tests only — NOT yet in production. The overnight cron soak (folded into GL-7 DoD) is its real proof; don't check "unattended-safe" off the gate until it runs clean.** | — |
| GL-17 | T | **Residual live-scenario coverage (from GL-9).** The actual Telegram **Reject button** (human reject, vs. the auto critic-reject already proven) was never tapped; sweep any other un-hit interactions. Small targeted run — fold into GL-13 or the next live touch. | mini launch-guide → pass/fail |
| GL-18 | C | **Landscape orientation wiring for the compositor (NEW 2026-07-23).** GL-5 v1.0 shipped portrait-only; landscape path is unwired in `mockup_render`/config/stage rewiring. Deferred with v1.0 near-frontal scope — **post-launch**, ties to the backlog "Landscape-vs-portrait handling" row. Not a go-live blocker (portrait covers the launch set). | → landscape wiring + landscape bundles |
| GL-19 | T | **Compositor M1 acceptance — ✅ RAN 2026-07-24, STOPPED at Phase 1: gate FAILED (as intended — caught a real defect).** Phase 0 clean (504/504). Phase 1 rendered the 4 real primary/portrait bundles offline — **all 4 miss the B+ bar**, not just the anticipated steep scene. **Root cause = authoring, not the compositor** (which is confirmed correct): (a) aperture quads are imprecise straight-line hand-traces, not perspective-accurate to the photographed paper edges → seam/dash lines; (b) overlay foreground occluders aren't fully opaque (alpha maxes ~172–187, never 255) → clips/books look see-through. Phase 2 live upload **not attempted** (correctly gated on Phase-1 approval). **Doc drift caught: `db/base_artwork/31.png` is NOT approved (cand. 31 stuck `pending_generation`) — the approved master is cand. 39's `39.png`.** Fix routed to GL-6-proper; **re-run the harness (`scripts/gl19_m1_render.py`) after re-authoring** before merge + a real upload. Status: `docs/2026-07-24-gl19-m1-status-update.md`. | done-as-scoped → re-run after GL-6-proper |
| GL-20 | R→C | **Gelato "mockups ready" poll relaxation (NEW 2026-07-23, latent/low).** Now that the self-hosted gallery fully replaces Gelato's, the pipeline no longer needs to wait on Gelato's gallery being ready — the readiness poll may be relaxable (latency win). Addendum §5 flagged it as a separate, verify-first follow-up. Left untouched by GL-5. Not a blocker. | verify → optional poll change |
| GL-10 | M | Etsy storefront overhaul — banner, sections, About, shop policies, SEO copy (Fable-assisted, owner-driven; one-way-valve safe: built from owner's framing + public sources) | how-to/checklist → live storefront updated |
| GL-11 | M | Revert Etsy Developer Mode (email developer@etsy.com; budget lead time) — sequence before public launch | how-to → Dev Mode off, confirmed |
| GL-12 | M | Apply for Google Trends API alpha access (zero cost, parallel) | how-to → application submitted |

### Post-launch backlog (owner's list 5–11, lightly classified)

| Type | Item |
|---|---|
| C | Telegram UX polish — richer inline buttons, edit-flow, digest legibility |
| C+R | Cost/sales dashboarding & reporting (slow-loop monitor first: daily views/favorers/orders snapshot + deltas → group → design roll-up; then a re-openable status view / **Cowork artifact** is a strong fit here) |
| IR+C | Landscape-vs-portrait handling (**see GL-18** — compositor landscape wiring) + a dedicated narrow/long (10x24) Gelato template refinement |
| IR | Extension beyond posters (apparel, etc.) — new mini-spec per product class |
| R+C | New audience: FR/Wallonian prints (owner already has a researched candidate set) |
| IR | Generalize into a reusable pattern for sibling projects (faceless YouTube, CV-template shop, …) |
| M+C | Documentation polish — README, user guide, runbook |

---

## Part 3 — Proposed sequencing (implementation sessions)

Critical path to a public launch. Sessions are sized to roughly one sitting
each; parallelizable tracks noted.

**✅ Done 2026-07-22/23:** Session 1 (GL-1 merge), Round 1 live test (GL-9
PASS/GO), mockup prototype + GL-2 decision (go, near-frontal), **the entire
live-fix cluster — GL-14 crop, GL-15 token, GL-16 resilience — all merged to
master**, and **GL-4 compositor research** (self-host OpenCV, detection
deleted). The `max_tokens` 1024→2048 truncation bug found in GL-9 is also fixed
on master.

**Where the fix cluster landed:** GL-14 + GL-15 shipped as small branches;
GL-16 shipped as its own `fix/resilience-hardening` branch (design →
Phase-2 build → merge). The live-fix cluster is **closed** — this was the long
pole for going *unattended* and it's now on master (with the production-soak
caveat below).

**Track A — mockups (GL-2 = go, near-frontal for v1.0) — IN FLIGHT:**
- **GL-4 (R→IR) ✅ done** — self-host OpenCV, runtime detection deleted.
- **GL-5 (C) ✅ build complete, ⏳ NOT mergeable yet.** 504/504. **Merge gated on
  GL-21 (compositor) + GL-6 attempt 3 (bundles)**, then a clean GL-19 re-run.
- **GL-19 (T) ✅ ran 2026-07-24** — failed the gate correctly, but its "compositor
  code is correct" conclusion was **half right**: clean mid-artwork, buggy at the
  artwork border (→ GL-21 C1). Re-run its harness after GL-21 + GL-6 attempt 3.
- **GL-21 (C) — NEW, OPEN, first half of the unblock.** Compositor unfrozen for
  C1 (border-mode fix) + C2 (per-pixel matte) + C3 (aspect guard) + the
  `mockup_qa.py` detector suite. Do this **before** re-authoring anything —
  attempt 2's central mistake was authoring around a compositor defect.
- **GL-6 attempt 3 (M) — OPEN, second half.** Keyed generation + derived
  authoring; 1 scene kept, 2 regenerated, 1 seeded-trial-then-regenerate. Then
  the ~26-bundle library scale-out (3 flat + 7 lifestyle per group, confirmed).
- **GL-18 (C) — landscape wiring, deferred post-launch.**

**Attempt-2 lesson worth carrying beyond mockups:** a constraint stated in a
handover ("`mockup_render.py` is frozen") was honoured over correctness, so a
12-character bug fix became a bundle-side repaint band that traded a dark
hairline for a bright one across every asset. **Flag the constraint, don't route
around it.** Now encoded as a standing rule in the attempt-3 plan §5.

**Track B — automation (now UNBLOCKED):**
- **Session 5 (R):** GL-8 confirm/refine the *local-desktop* host choice (GL-3)
  — run in parallel; GL-7's orchestrator logic is largely host-agnostic.
- **Session 6 (C, PR):** GL-7 two-cadence orchestrator — **no longer blocked**
  (GL-15 + GL-16 landed). Kickoff not yet written (owner deferred it this pass).
  **Its DoD must include the overnight unattended soak** that proves GL-16 in
  production.

**Track C — manual, parallel, owner-driven:** GL-10 storefront overhaul,
GL-12 Google Trends application now; **GL-11 Dev-Mode revert request** as soon
as a launch date is roughly known (external lead time).

**Session 7 — Round 2 + residuals live test (T).** GL-13 (mockup-dependent
slice, **needs GL-6-proper's secondary bundles**) **+ GL-14's real-crop
confirmation + GL-17 (human Reject button** and any un-hit interactions). One
live pass covering everything the fix cluster and mockups touched.

**Go-live gate (updated 2026-07-23):** GL-9 ✅ **+** live-fix cluster ✅ (GL-14
crop, GL-15 token, GL-16 resilience — all merged) **+** mockups shipped
near-frontal (GL-4 ✅ → **GL-21 compositor** → GL-6 attempt 3 authors bundles →
GL-19 harness re-run → GL-5 PR #2 merged) **+** cron
runnable & unattended-safe (GL-7 unblocked; gate needs a **clean overnight
soak**, not just merge) **+** storefront (GL-10) **+** Round 2 + residuals clean
(GL-13/14/17) **+** Etsy Developer Mode reverted (GL-11). **Two longest poles
now: (1) GL-21 + GL-6 attempt 3 → GL-13 Round 2; (2) GL-7 cron + soak.**
Note the shape change: attempt 3's P0–P3 (compositor + tooling + the 4 primary
scenes) unblocks PR #2, while P4 (the ~26-bundle library) is a *separate,
largely automated* session — the merge no longer waits on the full library.

### Tool-fit flags (CLAUDE.md §7)

- **Cron runtime is not a Cowork job.** The spec forbids a persistent
  service, but twice-daily + hourly scheduled functions still need a real
  always-available host (or a durable scheduler). Cowork/live-session is the
  wrong tool for the recurring runtime — decide GL-3 deliberately (GL-8).
- **Compositor build → Claude Code**, not Cowork: it's a multi-file,
  test-driven engineering task in the repo. Cowork is right for the planning,
  scene-authoring, storefront, and Notion work.
- **GL-19 compositor M1 render → Claude Code / in-repo bash**, not Cowork — a
  short guarded run producing sample PNGs; the *eyeball* is the owner's, in
  Cowork/preview.
- **GL-21 compositor + QA harness → Claude Code**, not Cowork: test-driven
  in-repo work (`mockup_render.py`, `mockup_qa.py`, ~8 new tests). Cowork's role
  is the owner's contact-sheet review at the end of each phase.
- **GL-6 attempt-3 scene authoring → Claude Code (Replicate skills), not
  Cowork/Fable.** Correction from the earlier read: the scene backgrounds are
  **FLUX.1 [schnell]** generations, so they run through the Replicate skills in
  a Claude Code session — with owner-in-the-loop *creative selection* between
  phases. Fable isn't the generator. Brief:
  `docs/2026-07-23-gl6-proper-authoring-brief.md`.
- **GL-7 cron runtime is not a Cowork job** (unchanged); the **overnight soak**
  could be observed via a lightweight Cowork status artifact.
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

---

## Part 4 (cont.) — Coding-session feedback log (2026-07-23)

**Session C — GL-5 mockup compositor build (Slot A).**
- Delivered on `feat/gl5-mockup-compositor` (6 commits, **504/504 green, PR #2
  to master, unmerged pending review**). `pipeline/mockup_render.py` = pure
  OpenCV compositor, **no runtime aperture detection** (reads `meta.json`),
  matching GL-4. Real prototype scene bundles (4 primary/portrait) brought over.
  `create_or_reuse_group_product` + `patch_etsy_listing` rewired to
  render/upload our own gallery; **Gelato gallery fully discarded, no fallback.**
- Final review caught + fixed **2 real bugs:** (1) 5x7/10x24 groups stuck in an
  **infinite retry loop on an empty gallery** — note this is resilience-adjacent
  and *only* surfaces because those scene bundles don't exist yet; (2) **PNG
  bytes uploaded to Etsy tagged as JPEG.**
- Known gaps left (not fixed here): **5x7/10x24 scene bundles don't exist**
  (→ GL-6-proper, blocks Round-2 secondary slice); **landscape unwired**
  (→ GL-18); Gelato readiness poll untouched (→ GL-20). **No live Etsy/Gelato
  writes** — all dry-run. M1 eyeball + one guarded live upload still open
  (→ GL-19).
- Owner question → resolved: the PR needs a "compositor *true* test" before
  accept. Framed as **GL-19** — unit tests can't judge composite *quality*;
  the acceptance is an M1 render-and-eyeball (sample PNGs committed for review)
  + one guarded live upload. Not a new build session, an acceptance run.

**Session D — GL-16 resilience hardening Phase 2 (Slot B).**
- Design `docs/2026-07-22-resilience-design.md` (Phase 1) → Phase 2 built on
  `fix/resilience-hardening` (4 task commits + gate), **483/483 green, merged +
  pushed to master (`56b4865`).**
- Shipped: `http.py` transient backoff (5xx/timeout/reset/429, `Retry-After`
  honored+capped, one bounded retry on 400/404/422), **gated to GET/HEAD/PUT so
  non-idempotent POST/PATCH are never blind-retried**; `critic_pass.py`
  regen-burst exception classified (vendor/network → untouched for next sweep,
  no abandon / no attempt-burn; real defects still abandon); `cleanup.py`
  reclaims `pending` group_products stranded past 10 min; `test_resilience_
  interrupt.py` = the pull-the-plug acceptance test (mid-generate and
  mid-create-or-reuse kills both recover next cycle, zero manual DB edits).
- **Pushback logged:** this is proven in **unit + scripted-interrupt tests
  only**, not in production. GL-16's real value (surviving real vendor flakiness
  overnight) is only proven by a live unattended cron soak → **folded into GL-7
  DoD.** Do not check "unattended-safe" off the go-live gate on merge alone.
- **Effect on critical path: GL-7 (cron) is now unblocked** — both its gates
  (GL-15 token, GL-16 resilience) are on master.

---

## Part 4 (cont.) — Coding-session feedback log (2026-07-24)

**Session E — GL-19 compositor M1 acceptance (`docs/2026-07-24-gl19-m1-status-update.md`).**
- Ran on `feat/gl5-mockup-compositor`. **Phase 0 clean (504/504). Phase 1
  offline render of the 4 real primary bundles → FAILED the B+ bar on all 4**
  (not just the anticipated steep scene). **Phase 2 live upload correctly not
  attempted** (gated on Phase-1 approval). **No live calls, no merge, no code
  changes** — the run did exactly what a gate should: caught the defect and
  stopped.
- **Fault localized to authoring, not the compositor** (verified against raw
  bundle assets): (c) **aperture quads are imprecise straight-line hand-traces**,
  not perspective-accurate to the photographed paper edges — the quad sits
  outside the real tapered edge → the seam/dash lines; (d) **overlay foreground
  occluders aren't fully opaque** (alpha maxes ~172–187, never 255) → clips/
  books render see-through. `mockup_render.py`'s warp + composite is **confirmed
  correct** — every scene's mid-artwork area renders clean.
- **Doc-drift caught + corrected:** the kickoff's named master
  `db/base_artwork/31.png` is **not approved** (cand. 31 is stuck
  `pending_generation`); the real approved master is **cand. 39's `39.png`**
  (the round-1 published candidate). Fixed in the GL-6-proper brief; flag if
  `31.png` appears elsewhere.
- **Actions:** GL-19's two findings become **GL-6-proper acceptance criteria
  (c) + (d)**, and GL-6-proper now also **fixes the 4 existing bundles**, not
  just authors new ones. **PR-#2 merge is now gated on GL-6-proper** (re-author →
  re-run `scripts/gl19_m1_render.py` → clean → merge + guarded upload), not on
  GL-19 alone. Reusable artifacts left on branch: `scripts/gl19_m1_render.py`,
  `outputs/gl19_m1/*.png`.
- **Read:** the compositor investment (GL-4→GL-5) holds — the risk was always
  the scenes, and it's now precisely characterized (two concrete, fixable
  authoring defects), not vague. Good outcome for a gate.
- **⚠ Superseded 2026-07-26 (see Session G):** "fault localized to authoring,
  not the compositor" was **half right**. Mid-artwork is clean; the artwork
  *border* carries a real compositor bug. Acting on the half-truth is what sent
  attempt 2 down a bundle-side workaround.

---

## Part 4 (cont.) — Coding-session feedback log (2026-07-26)

**Session F — GL-6 attempt 2 (5 commits `30124f1..00ac765`, `feat/gl6-scene-library`).**
- Re-cut clean off `feat/gl5-mockup-compositor` after discarding attempt 1.
  New tool `scripts/gl6_author.py` (hand-read paper quads + per-edge margins,
  gain-map extractor, overlay builder, selftest). 504/504, renders
  deterministic, `overfill: 0.0` everywhere, master `39.png`. Delivered on its
  own terms.
- **Owner review: 1 of 4 accepted.** `lifestyle_bedroom_console` ✅.
  `flat_clips_windowlight` — shadow still curved (photographed curl vs. a
  straight-edged print). `flat_leaning_bookstack` — square notches near the
  books. `lifestyle_sage_terracotta` — bright dotted lines at the art border and
  a double border (art inset *inside* the mat's own photographed panel line).
- **Two real findings the session did surface** and that attempt 3 keeps: the
  compositor **stretches** art onto the aperture (0.63–0.70 quads vs. a 0.684
  master = up to 5 % distortion), and occluder detection needs **chroma OR
  darkness as two tests**, never RGB distance alone.
- **The mistake:** it measured a genuine border-contamination defect, then
  honoured "`mockup_render.py` is frozen" over fixing it — repainting the
  photograph over the art's outer 3 px in every bundle. That swapped a dark
  hairline for a bright one (≈ +18 L on sage) and shipped it as a documented
  trade. **Flag the constraint, don't route around it.**

**Session G — attempt-3 planning (Cowork, this doc's update; plan =
`docs/2026-07-26-gl6-attempt3-production-readiness-plan.md`).**
- **Re-diagnosed all four defects to mechanism, with measurements**, not
  impressions: `warpPerspective`'s default `BORDER_CONSTANT`=black under
  `INTER_CUBIC` contaminates 710–1479 partial-alpha border px per scene by
  ~120/255 mean (fix verified: 246 vs. 0 with `BORDER_REPLICATE`); the curled
  paper's silhouette is unrepresentable as a quad; the bookstack notches are the
  literal borders of two axis-aligned occluder boxes; sage's mat carries a
  photographed inner panel line at L 179-vs-250, ~16 px inside the opening, with
  the quad a further ~62 px inside it, and an opening aspect of 0.59 against a
  0.684 master.
- **Structural conclusion:** attempt 2's *doctrine* ("the art must never have to
  meet a photographed edge") was right; its *primitives* — a 4-point quad plus
  rectangular patches — cannot express curl, soft taper, book spines, clip jaws
  or nested mat lines. Sharpening the tracing a third time would fail a third
  time. → **per-pixel `matte.png`** (GL-21 C2) + **keyed generation** so the
  matte is derived, never traced.
- **Scope split into GL-21 (compositor, first) + GL-6 attempt 3 (assets,
  second)** — deliberately in that order.
- **Owner decisions (all four, 2026-07-26):** keyed generation as Plan A;
  compositor unfrozen for C1–C3; cover-crop ≤2 % + fail loud; library target
  confirmed at 3 flat + 7 lifestyle per group.
- **Read:** the expensive lesson across three attempts is that **hand-authored
  per-scene constants were never going to reach 26 bundles.** Attempt 3's real
  deliverable is not four fixed images, it's a *derivation pipeline* plus an
  automated defect gate that makes the owner's eyeball the last check rather
  than the only one.
