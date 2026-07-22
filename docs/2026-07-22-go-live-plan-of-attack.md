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
| GL-2 | D | Custom mockups before launch vs. v1.1 — **DECISION DEFERRED (2026-07-22):** build a fast mockup-creation prototype first; decide after seeing it. If the prototype clearly overhauls product quality, mockups move ahead of launch; else fast-follow. → drives GL-4/6 to run *before* the go/no-go | prototype (GL-6) → the decision |
| GL-3 | D | Cron deployment target — **PRELIMINARY DECISION (2026-07-22): host locally on desktop for now.** Still run GL-8 to confirm/refine (reliability of a desktop always-on host, wake/sleep, vs. a cheap always-on option) | GL-8 findings → confirm or revise |
| GL-4 | IR | Compositor design spike — nail Pillow+homography warp, overlay baking, aperture format, fixture tests (Addendum §5/§6 already decides the *what*; this de-risks the *how*) | briefing prompt → `mockup_render` impl plan + code-session prompt |
| GL-5 | C | Build `pipeline/mockup_render.py` + `mockup_templates` config + rewire `primary_mockup`/`group_mockup` + Etsy upload order (Addendum A) | GL-4 plan → PR |
| GL-6 | IR+M | Scene-authoring: **prototype first** (the GL-2 decision gate) — kickoff written: `docs/2026-07-22-gl6-mockup-prototype-kickoff.md` (one ISO-portrait set + throwaway composite vs. Gelato baseline → GL-2 call). Then, only if GL-2=go, author the real library (~10/set × 3 sets × 2 orientations) | kickoff prompt → composited comparison + GL-2 recommendation; then the finished `assets/mockups/…` bundles |
| GL-7 | C | Cron orchestrator: two scheduled cadences (hourly Telegram poll, twice-daily batch) wiring the existing stages; one function per stage, not one loop | GL-3 decision + kickoff → PR |
| GL-8 | R | Where to host the scheduled functions (tool-fit: Cowork scheduled task vs. Claude Code cron vs. a real host — Fly/Render/Cloudflare/GitHub Actions), given cost, reliability, and the persistent-process ban | briefing → hosting recommendation w/ named option |
| GL-9 | T | **Round 1 live re-test (pre-mockup)** — v4.11 publish path + the mockup-*independent* un-exercised M1 scenarios (Kill; 3-attempt critic fail + `DELETE` cleanup; full group flow approve *and* reject; allowlist rejection). **Launch guide written: `docs/2026-07-22-v411-live-test-launch-guide.md`.** Run **now**, ahead of the mockup change, for a clean isolated signal on the riskiest unproven code. | launch guide → pass/fail + feedback |
| GL-13 | T | **Round 2 live re-test (post-mockup)** — the mockup-*dependent* slice that Addendum A rewrites: custom gallery uploaded via `uploadListingImage` in rank order (3 flat + 7 lifestyle), critic pass over the *custom* scenes, `mockup_failed` → retry path (no Gelato fallback), and the scene-ID placeholder fail-loud guard. Narrower than Round 1 — the publish/decision/cleanup mechanics are already proven, so this only re-checks what the compositor touches. | delta launch guide (extends GL-9's) → pass/fail |
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

**Session 1 — mainline hygiene (C). ✅ DONE 2026-07-22.** GL-1 merged
round-3 → master; local caught up.

**Session 2 — Round 1 live test (T), NOW.** GL-9 per
`docs/2026-07-22-v411-live-test-launch-guide.md`: proves the v4.11 publish
rework + Kill / 3-attempt-fail+DELETE / group approve+reject / allowlist live,
*before* mockups. Deliberately sequenced ahead of Track A so the mockup change
lands as a small delta on a known-good base rather than two unproven things
stacked. A clean pass here retires the largest risk on the critical path.

**Track A — mockups (prototype-gated, GL-2 decision deferred):**
- **Session 3a (IR→M):** GL-6 fast scene-authoring prototype (the thing the
  GL-2 decision waits on) — if it clearly overhauls product quality, mockups
  go pre-launch; else fast-follow to v1.1.
- **Session 3b (IR):** GL-4 compositor spike → `mockup_render` impl plan.
- **Session 3c (C, PR):** GL-5 build compositor + rewire the two mockup stages.

**Track B — automation (parallel):**
- **Session 4 (R):** GL-8 confirm/refine the *local-desktop* host choice
  (GL-3 preliminary) — reliability, always-on/sleep behaviour, cheap
  always-on alternatives.
- **Session 5 (C, PR):** GL-7 build the two-cadence orchestrator for the
  chosen host.

**Track C — manual, parallel, owner-driven:** GL-10 storefront overhaul,
GL-12 Google Trends application now; **GL-11 Dev-Mode revert request** as soon
as a launch date is roughly known (external lead time).

**Session 6 — Round 2 live test (T), only if mockups ship pre-launch.** GL-13:
the narrow mockup-dependent re-test (custom gallery upload/order, critic over
custom scenes, `mockup_failed` retry, placeholder fail-loud). Skipped/deferred
if GL-2 lands on fast-follow.

**Go-live gate:** Round 1 (GL-9) clean **+** cron runnable (GL-7) **+**
storefront done (GL-10) **+** (if mockups pre-launch) Round 2 (GL-13) clean
**+** Etsy Developer Mode reverted (GL-11).

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
