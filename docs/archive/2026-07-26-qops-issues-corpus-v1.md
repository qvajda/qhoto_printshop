<!--
qops Phase 1 — issue corpus extracted from docs/2026-07-22-go-live-plan-of-attack.md
(431 lines, last updated 2026-07-26). This file is the SOURCE for the one-time
import; after `scripts/qops_phase1.py --execute` the GitHub issues are the source
of truth and this file becomes history.

Format: one block per issue, delimited by the qops comment markers. Everything
between the opening marker and </qops> is the issue body, verbatim.
Attributes: id, state (open|closed), type, milestone, labels (comma-separated),
epic (id of the parent epic issue, resolved to a number at import time).
-->

<!--qops id=EPIC-mockups state=open type=epic milestone=Go-live labels=epic,mission:mockups-->
# Mission — Custom mockup track (GL-2 = go, near-frontal v1.0)

The single biggest remaining build chunk. Self-hosted OpenCV compositor +
authored scene bundles replacing Gelato's default gallery.

**Critical path:** GL-21 (compositor) → GL-6 attempt 3 (bundles) → GL-19
(harness re-run) → GL-5 (PR #2 merge) → GL-13 (Round 2 live).

**Pre-committed fork — do not re-litigate when reached:**
if GL-6 attempt 3 fails its machine acceptance twice, fall back to the
**Dynamic Mockups escape hatch** (SPEC_v4.10 Addendum §7) — narrow scope, PSD
re-authoring, 24h link expiry, vendor-in-cron. Attempts 1 and 2 both failed;
a third failure is the trigger, not a surprise.

**Standing rule carried out of attempt 2:** never work around a compositor
defect in the assets. Flag the constraint, don't route around it.
<!--/qops-->

<!--qops id=EPIC-automation state=open type=epic milestone=Go-live labels=epic,mission:automation-->
# Mission — Unattended operation (cron + soak)

Two scheduled cadences (hourly Telegram poll, twice-daily batch) wiring the
existing 13 stages. Discrete scheduled functions — not a persistent service,
not one agent loop.

**Path:** GL-8 (host research, parallel) + GL-3 (host decision) → GL-7
(orchestrator) → overnight unattended soak.

**Pre-committed fork:** if the local-desktop host fails the soak on
wake/sleep or reliability, move to a cheap always-on host (Fly / Render /
Cloudflare / GitHub Actions) — GL-8 names the option in advance so the fork
costs a decision, not a research cycle.

**Gate:** GL-16's resilience work is proven in unit and scripted-interrupt
tests only. The **clean overnight soak is its real production proof** — do not
tick "unattended-safe" until it runs clean.
<!--/qops-->

<!--qops id=EPIC-launch state=open type=epic milestone=Go-live labels=epic,mission:launch-prep-->
# Mission — Launch prep (manual, owner-driven, parallel)

Track C from the plan of record. Runs alongside the two build missions and
blocks the public launch, not the code.

GL-10 storefront overhaul · GL-11 Etsy Developer Mode revert (external lead
time — start as soon as a launch date is roughly known).

GL-12 (Google Trends API alpha application) **deferred to Post-launch
2026-08-08** — registration needs a Google Cloud Console project set up
first, not a click-apply form, so it no longer runs in this parallel track.

None of these are auto-eligible: all touch external accounts.
<!--/qops-->

<!--qops id=GL-1 state=closed type=code milestone=Go-live labels=mission:mockups-->
# GL-1 — Merge fix/generation-quality-round3 → master

**Resolution (2026-07-22):** DONE. PR completed on remote; local caught up with
master. Round-3 validation was PASS/GO (8 good / 2 refine / 0 reject, all defect
classes ≤1) but had been sitting 10 commits ahead of master, i.e. the quality
gains were not in the mainline the runtime deploys from. Now they are.
<!--/qops-->

<!--qops id=GL-2 state=closed type=decision milestone=Go-live labels=mission:mockups-->
# GL-2 — Decision: custom mockups before launch?

**Resolution (2026-07-22, post-prototype): GO pre-launch, scoped to
near-frontal scenes.** Even flawed composites clear the Gelato bar easily, and
the scenes themselves are high quality (owner: 4/5 samples strong).

Angled/leaning scenes deferred to **v1.1 fast-follow** — they need better
corner detection or the Dynamic Mockups escape hatch (Addendum §7).

The compositor, not the scenes, was identified as the risk. That judgement was
half right — see GL-21.
<!--/qops-->

<!--qops id=GL-3 state=closed type=decision milestone=Go-live labels=mission:automation-->
# GL-3 — Decision: cron deployment target

**Resolution (2026-08-05, `docs/2026-08-05-gl7-cron-prd-and-kickoff.md` §0):
signed off as local desktop, with the VPS fallback pre-committed rather than
open.** Confirmed against GL-8's findings before the GL-7 build started.

**Open questions (resolved):** reliability of an always-on desktop host,
wake/sleep behaviour, versus a cheap always-on alternative — settled by
naming the fallback in advance rather than by ruling it out.

**Acceptance:** a named host with its failure modes written down, and the
fallback recorded in EPIC-automation as a pre-committed fork. Met.

**Depended on:** GL-8 findings — closed.
**Note:** kept as `revisit-after` in spirit — GL-7's soak (still running) is
what actually tests wake/sleep reliability; the pre-committed VPS fork stays
live until that soak proves the desktop clean.
<!--/qops-->

<!--qops id=GL-4 state=closed type=research milestone=Go-live labels=mission:mockups-->
# GL-4 — Research: compositor approach

**Resolution (2026-07-23): DONE.** Findings and implementation plan both
written (`docs/2026-07-22-compositor-approach-findings.md`,
`docs/2026-07-22-gl5-compositor-implementation-plan.md`).

**Key reframe:** the prototype's failures were *detection* failures, not warp
failures — and since the Addendum authors the aperture into `meta.json`,
runtime detection is deleted entirely.

**Recommendation adopted:** self-host on OpenCV
(`getPerspectiveTransform` + `warpPerspective`, 2× supersample, ~1.5–2% quad
over-fill, frame edge baked into `overlay.png`). A spike hit production-clean
near-frontal on the first pass. v1.0 and v1.1 (angled) are the same code path —
angled needs better *authoring* precision, not a new engine.

Dynamic Mockups retained as a narrow escape hatch only.
<!--/qops-->

<!--qops id=GL-5 state=open type=code milestone=Go-live labels=mission:mockups,go-live-blocker,state:blocked-->
# GL-5 — Build the mockup compositor + rewire the mockup stages

Branch `feat/gl5-mockup-compositor`, **PR #2 open**. Build complete and code
validated 2026-07-24, 504/504 green. **Not mergeable yet.**

**Shipped:** `pipeline/mockup_render.py`, `mockup_templates` static config +
accessor, rewired `primary_mockup` / `group_mockup`, Etsy upload order per
Addendum A, self-hosted gallery replacing Gelato's (fully discarded). Review
caught and fixed two bugs: empty-gallery infinite retry, PNG mis-tagged as JPEG.

**Correction (2026-07-26):** the earlier conclusion "the compositor code is
correct" was too strong. GL-19 proved it renders clean *mid-artwork*; the
artwork *border* carries a real bug. Fixed under GL-21, not by re-authoring.

**Merge gate:** GL-21 + GL-6 attempt 3 land → clean GL-19 harness re-run →
guarded upload. No live writes before that.

**Depends on:** GL-21, GL-6, GL-19.
<!--/qops-->

<!--qops id=GL-6 state=open type=manual milestone=Go-live labels=mission:mockups,go-live-blocker-->
# GL-6 — Scene authoring (attempt 3)

Prototype done 2026-07-22. **Attempt 1 discarded. Attempt 2 ran 2026-07-24
(5 commits, 504/504) → owner review 2026-07-26: 1 of 4 scenes accepted.**

`lifestyle_bedroom_console` passes. The other three fail on defects the
authoring doctrine could not express: a curled-paper silhouette versus a
4-point quad, axis-aligned occluder boxes cutting square notches, and an
over-inset quad inside the mat's own photographed panel line.

**Attempt 3 — scope changed on all three axes** (plan of record:
`docs/2026-07-26-gl6-attempt3-production-readiness-plan.md`, decisions §7
owner-approved):
1. **Compositing** → GL-21: per-pixel `matte.png` replaces quad-as-silhouette,
   occluder boxes, and attempt 2's repaint band.
2. **Generation** → scenes generated with a **solid key-colour print panel** so
   the matte extracts exactly and the drop shadow belongs to the real silhouette
   by construction. Machine-checked generation acceptance replaces prose criteria.
3. **Authoring** → `scripts/scene_author.py` **derives** matte/quad/gain/occluders
   from the image. **Zero per-scene constants in source** — attempt 2's four
   hand-read quads, margin tuples and occluder boxes are precisely what does not
   scale to the ~26 remaining bundles.

**Acceptance:** bundles pass `scripts/mockup_qa.py` and the GL-19 harness.
Attempt-2 criteria (c) and (d) are superseded — with a matte, sub-pixel tracing
and α-255 occluder stamping stop existing.

**Scope split:** P0–P3 (compositor + tooling + the 4 primary scenes) unblocks
PR #2. P4 (the ~26-bundle library scale-out, 3 flat + 7 lifestyle per group) is
a separate, largely automated session — the merge no longer waits on it.

**Not auto-eligible:** acceptance requires owner taste on the final scenes.
**Depends on:** GL-21.
<!--/qops-->

<!--qops id=GL-7 state=open type=code milestone=Go-live labels=mission:automation,go-live-blocker-->
# GL-7 — Cron orchestrator (two cadences)

Hourly Telegram poll + twice-daily batch, wiring the existing stages. **One
function per stage, not one loop** — hard constraint.

**Unblocked 2026-07-23:** both gates (GL-15, GL-16) landed on master.

**DoD must include an overnight unattended soak.** GL-16 is proven in unit and
scripted-interrupt tests only; the soak is its real production proof.

**Depends on:** GL-3 decision (host).
**Blocks:** the go-live gate's "cron runnable & unattended-safe" condition.
<!--/qops-->

<!--qops id=GL-8 state=closed type=research milestone=Go-live labels=mission:automation-->
# GL-8 — Research: where to host the scheduled functions

Tool-fit question: Cowork scheduled task vs Claude Code cron vs a real host
(Fly / Render / Cloudflare / GitHub Actions), given cost, reliability, and the
spec's persistent-process ban.

**Resolution (2026-08-05, `docs/2026-08-05-gl7-cron-prd-and-kickoff.md` §0):**
local desktop recommended, VPS named as the pre-committed fork. Fed directly
into GL-3's sign-off the same day; GL-7's build started immediately after.

**Acceptance:** a briefing that names one recommended option with its cost,
failure modes, and wake/sleep behaviour — plus the runner-up as the
pre-committed fork for EPIC-automation. Met.

Ran in parallel with GL-7 kickoff, as scoped.

**Auto-eligible:** research only, no code, no external write, no paid API call.
<!--/qops-->

<!--qops id=GL-9 state=closed type=test milestone=Go-live labels=mission:automation-->
# GL-9 — Round 1 live re-test

**Resolution (2026-07-22): PASS / GO, with residuals.**

Proven live: S0 clean · S1 allowlist (synthetic non-admin callback discarded and
logged) · S2 Kill/hold (0 Replicate calls) · S3 happy path end-to-end after 2
retries — primary published (4 variants, exact spec prices, all Etsy fields),
5x7 published (Small shipping, €19), 10x24 critic-rejected 3× and cleanly
`DELETE`d, which **proved S4 group-level for free** (dedicated S4 skipped by
owner).

4 real Etsy drafts live, matching the DB, no orphans.

**Residuals spun out →** GL-15, GL-16, GL-17. Also surfaced the `max_tokens`
1024→2048 truncation bug (since fixed on master).
<!--/qops-->

<!--qops id=GL-10 state=open type=manual milestone=Go-live labels=mission:launch-prep,go-live-blocker-->
# GL-10 — Etsy storefront overhaul

Banner, sections, About, shop policies, SEO copy. Fable-assisted, owner-driven.

**One-way-valve safe:** built from the owner's own framing plus public sources.

**Acceptance:** live storefront updated. Deliverable is a how-to / checklist,
then the owner executes.

**Not auto-eligible:** external account write.
<!--/qops-->

<!--qops id=GL-11 state=open type=manual milestone=Go-live labels=mission:launch-prep,go-live-blocker-->
# GL-11 — Revert Etsy Developer Mode

Email developer@etsy.com. **Not self-service — budget external lead time**, and
sequence before public launch.

Listing visibility observed while in Developer Mode is not representative, so
this also gates any conclusion drawn from pre-launch traffic.

**Trigger:** start as soon as a launch date is roughly known.
**Not auto-eligible:** external communication in the owner's name.
<!--/qops-->

<!--qops id=GL-12 state=open type=manual milestone=Post-launch labels=mission:launch-prep-->
# GL-12 — Apply for Google Trends API alpha access

Zero cost, runs in parallel, standing application still open per spec §7.

**Deferred to post-launch 2026-08-08 (owner).** Not the "zero cost, click
apply" item it was filed as: alpha registration sits behind standing up a
Google Cloud Console project (a GCP project, Workspace linkage, billing
attached to it) before the application itself can even be submitted. That's
setup cost, not urgency, so it no longer belongs on the go-live critical
path. Reopen post-launch as a small standalone session.

**Acceptance:** application submitted.
**Not auto-eligible:** external account action.
<!--/qops-->

<!--qops id=GL-13 state=open type=test milestone=Go-live labels=mission:mockups,go-live-blocker,state:blocked-->
# GL-13 — Round 2 live re-test (post-mockup)

The mockup-*dependent* slice that Addendum A rewrites — narrower than Round 1.

**Covers:** custom gallery uploaded via `uploadListingImage` in rank order ·
critic pass over the *custom* scenes · `mockup_failed` → retry path (no Gelato
fallback) · the scene-ID placeholder fail-loud guard.

**Fold in:** GL-14's real-crop check — confirm the cover-cropped image actually
reaches Gelato with no white bars. And GL-17's residuals.

**Depends on:** GL-6 attempt 3's secondary bundles.
**Not auto-eligible:** live external writes.
<!--/qops-->

<!--qops id=GL-14 state=closed type=code milestone=Go-live labels=mission:mockups-->
# GL-14 — Fix: group crop never sent to Gelato

**Resolution (2026-07-22): DONE, merged to master.**

Full-resolution cover-crop now hosted on R2 and sent to Gelato for 5x7 and
10x24. Unit-tested and **live-confirmed** — real Gelato products fill the frame
edge to edge, no white bars.
<!--/qops-->

<!--qops id=GL-15 state=closed type=code milestone=Go-live labels=mission:automation-->
# GL-15 — Etsy OAuth auto-refresh

**Resolution (2026-07-22): DONE, merged to master.**

401 → refresh → retry, no loop, no `urllib` in `pipeline/`. Unit-tested.
Real-token live smoke deliberately deferred to the next live pass.
<!--/qops-->

<!--qops id=GL-16 state=closed type=code milestone=Go-live labels=mission:automation-->
# GL-16 — Unattended-resilience hardening

**Resolution (2026-07-23): BUILT and MERGED** (`fix/resilience-hardening` →
master `56b4865`), 483/483 green. Design:
`docs/2026-07-22-resilience-design.md`.

**Shipped:** `http.py` transient backoff (5xx / timeout / reset / 429,
`Retry-After` honoured and capped, gated to idempotent GET/HEAD/PUT so POST and
PATCH are never blind-retried) · `critic_pass.py` classifies regen-burst faults
(vendor/network → leave the candidate for the next sweep, no abandon, no attempt
burned; real defects still abandon) · `cleanup.py` reclaims stranded `pending`
group_products · `test_resilience_interrupt.py` pull-the-plug acceptance test.

**Caveat carried to GL-7:** proven in unit and scripted tests only, NOT in
production. The overnight cron soak is its real proof.
<!--/qops-->

<!--qops id=GL-17 state=open type=test milestone=Go-live labels=mission:mockups-->
# GL-17 — Residual live-scenario coverage (from GL-9)

The actual Telegram **Reject button** (a human reject, as opposed to the auto
critic-reject already proven) was never tapped. Sweep any other un-hit
interactions.

Small targeted run — **fold into GL-13** or the next live touch rather than
running standalone.

**Not auto-eligible:** live external writes.
<!--/qops-->

<!--qops id=GL-18 state=open type=code milestone=Post-launch labels=mission:mockups-->
# GL-18 — Landscape orientation wiring for the compositor

GL-5 v1.0 shipped portrait-only; the landscape path is unwired in
`mockup_render`, config, and the stage rewiring.

Deferred with the v1.0 near-frontal scope. **Post-launch**, ties to the backlog
row "landscape-vs-portrait handling". Not a go-live blocker — portrait covers
the launch set.
<!--/qops-->

<!--qops id=GL-19 state=open type=test milestone=Go-live labels=mission:mockups,state:blocked-->
# GL-19 — Compositor M1 acceptance harness

**Ran 2026-07-24, STOPPED at Phase 1: gate FAILED — as intended. It caught a
real defect.**

Phase 0 clean (504/504). Phase 1 rendered the 4 real primary/portrait bundles
offline; **all 4 missed the B+ bar**, not just the anticipated steep scene.
Phase 2 live upload correctly not attempted.

**Root cause at the time recorded as authoring, not the compositor** — imprecise
hand-traced aperture quads causing seam/dash lines, and overlay occluders never
fully opaque (alpha maxing ~172–187). **Superseded 2026-07-26:** a real
compositor border bug was also present (→ GL-21).

**Doc drift caught:** `db/base_artwork/31.png` is NOT approved (candidate 31 is
stuck `pending_generation`); the approved master is candidate 39's `39.png`.

**Action:** re-run `scripts/gl19_m1_render.py` after GL-21 + GL-6 attempt 3,
before merge and before any real upload.
**Depends on:** GL-21, GL-6.
<!--/qops-->

<!--qops id=GL-20 state=open type=research milestone=Post-launch labels=mission:mockups,ready:auto-->
# GL-20 — Relax the Gelato "mockups ready" poll

Latent, low priority. Now that the self-hosted gallery fully replaces Gelato's,
the pipeline no longer needs to wait on Gelato's gallery being ready — the
readiness poll may be relaxable, for a latency win.

Addendum §5 flagged it as a separate, verify-first follow-up. Left untouched by
GL-5. Not a blocker.

**Acceptance:** verify first, then an optional poll change.
**Auto-eligible:** read-only verification, no external write.
<!--/qops-->

<!--qops id=GL-21 state=open type=code milestone=Go-live labels=mission:mockups,go-live-blocker,ready:auto-->
# GL-21 — Compositor hardening: border mode, per-pixel matte, aspect guard

**First half of the PR-#2 unblock. Precedes GL-6 attempt 3.**
`pipeline/mockup_render.py` is **explicitly unfrozen** (owner-approved) for three
additive changes:

- **C1 — `borderMode=BORDER_REPLICATE` on the colour warp only** (the mask warp
  stays `BORDER_CONSTANT`). Kills the black contamination measured at 710–1479
  border px per scene, mean ~120/255. Verified 246-vs-0 on a synthetic warp.
  `cv2.warpPerspective` defaults to `BORDER_CONSTANT`=0, which under
  `INTER_CUBIC` contaminates every partial-coverage border pixel toward black.
- **C2 — optional `matte.png` in the bundle**, warped-art alpha ×= matte. The
  new primitive. An absent file means today's behaviour byte-for-byte, so all
  504 tests and the existing bundles are unaffected.
- **C3 — load-time aspect guard.** Cover-crop the artwork to the quad's aspect,
  **fail loud above 2%**. Attempt 2 shipped quads at 0.63–0.70 against a 0.684
  master — up to 5% silent non-uniform stretch of the print a buyer pays for.

**Plus `scripts/mockup_qa.py`:** 6 automated defect detectors (fringe, key-spill,
distortion, coverage, occluder-opacity, silhouette-vs-shadow) + a contact-sheet
generator. **This is the machine gate that must pass before any owner review of
scenes.**

`overfill` stays in the schema for compatibility, authored 0.0. The pipeline
contract (`load_bundle` / `render_scene` / bundle-on-disk) and
`group_product.py` are unchanged.

**Base branch:** `feat/gl5-mockup-compositor` → `feat/gl21-matte-compositor`.
`feat/gl6-scene-library` is reference only — cherry-pick nothing but ideas.

**Acceptance:** C1–C3 implemented, QA harness in place, tests green.
**Auto-eligible:** fully machine-checkable gate (tests + synthetic warp
assertions + the QA detectors), no external write, no paid API call.
<!--/qops-->

<!--qops id=BL-1 state=open type=code milestone=Post-launch labels=state:triage-->
# Backlog — Telegram UX polish

Richer inline buttons, edit flow, digest legibility.
<!--/qops-->

<!--qops id=BL-2 state=open type=research milestone=Post-launch labels=state:triage-->
# Backlog — Cost/sales dashboarding and reporting

Slow-loop monitor first: daily views / favorers / orders snapshot + deltas →
group → design roll-up. Then a re-openable status view — **a Cowork artifact is
a strong fit here** (persists across sessions, pulls fresh data on open).

Spec parks the slow-loop monitor at M3; post-launch.
<!--/qops-->

<!--qops id=BL-3 state=open type=impl-research milestone=Post-launch labels=state:triage,mission:mockups-->
# Backlog — Landscape vs portrait handling + 10x24 template refinement

See GL-18 for the compositor landscape wiring. Also wants a dedicated
narrow/long (10x24) Gelato template refinement.
<!--/qops-->

<!--qops id=BL-4 state=open type=impl-research milestone=Post-launch labels=state:triage-->
# Backlog — Extension beyond posters

Apparel and other product classes. Needs a new mini-spec per product class.
<!--/qops-->

<!--qops id=BL-5 state=open type=research milestone=Post-launch labels=state:triage-->
# Backlog — New audience: FR/Wallonian prints

Owner already has a researched candidate set.
<!--/qops-->

<!--qops id=BL-6 state=open type=impl-research milestone=Post-launch labels=state:triage-->
# Backlog — Generalize into a reusable pattern for sibling projects

Faceless YouTube, CV-template shop, and similar. Note the overlap with the qops
plugin's own portability goal — the *ways of working* half is already being
built; this row is about the *pipeline* pattern.
<!--/qops-->

<!--qops id=BL-7 state=open type=manual milestone=Post-launch labels=state:triage-->
# Backlog — Documentation polish

README, user guide, runbook.
<!--/qops-->
