# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

> **Last updated 2026-07-31 — the mockup milestone is achieved for portrait,
> and a new pre-launch scope item lands on top of it.** GL-21 (compositor) and
> GL-6 (scene library) are **done for portrait**: 17 primary bundles authored,
> **10 wired**, plus 1 wired at 5x7 and 2 at 10x24 — the two secondary groups
> stop shipping an empty gallery (`83544b7`). The library target formally
> **diverges from 10/10/10**: primary gets the full set, 5x7 and 10x24 get
> reduced sets (owner decision, recorded as GL-6a below). New scope
> **GL-22 — one Etsy listing per artwork (v4.12)**: all six sizes become
> variants of a single Gelato product / single Etsy listing, with the gallery
> growing as each crop passes review. It carries a **research gate** (Gelato
> API), two **owner decisions** (shipping profile, publish timing) and two
> **CLAUDE.md hard-constraint rewrites**, so it is planned, not started.
> Everything on `feat/gl6-p4-scene-library` (36 commits) is **not on master**.
> Earlier: 2026-07-26 added GL-21 and re-scoped GL-6 to attempt 3; 2026-07-24
> folded in GL-5 build + GL-16 + GL-4; the live-fix cluster is closed.

Planning artifact only — no code written in this pass. Counter-checks the
owner's mental milestone map against the actual repo/config state, then
sequences the remaining work to reach a public "go live" and lists every
open point classified by work-type.

Evidence base: SPEC_v4.11, SPEC_v4.10 Addendum A (custom mockups), the GL-6
chroma-model plan (§7–§9 + Part 4 harvest), the P4b scene-generation pivot,
`config/static_config.json`, `db/schema.sql`, `pipeline/group_product.py`, and
a live audit of the working tree and git log through `83544b7` (2026-07-31).

---

## Part 1 — Where we actually are (2026-07-31)

### The mockup track — done for portrait, and it changed shape

**Library, measured on disk and in config:**

| group | bundles authored | wired in `mockup_templates` | original target |
|---|---|---|---|
| primary/portrait | 17 | **10** (4 flat + 6 lifestyle) | 10 — **met** |
| 5x7/portrait | 2 committed (+1 untracked) | **1** *(bookstack authored, 8/8, unwired — GL-27)* | 10 — **deliberately not met** |
| 10x24/portrait | 2 | **2** | 10 — **deliberately not met** |
| any/landscape | 0 | 0 | 10 per group — post-launch |

**The divergence is a decision, not a shortfall (GL-6a).** Reduced secondary
sets are correct for three independent reasons, and the plan now says so:
(1) a 5x7 or 10x24 mockup only ever appears on a listing whose *crop passed
review* — it is a supplement to the primary gallery, not a gallery of its own;
(2) under GL-22 all of these images share **one** Etsy listing, and Etsy's
limit is 20 photos, so 10 + 1 + 2 = 13 fits with headroom that 10 + 10 + 10
would blow through by 10; (3) 10x24 at 0.4167 is the hardest aspect to
generate — schnell could not reach it at all (0/18, minimum gap 0.20 against a
0.02 budget) and even Nano Banana spends attempts on it. **Standing target,
revised: primary 10, secondary 2–4 each, landscape post-launch.**

**What is still open on the mockup track** (none of it blocks the compositor,
all of it is listed in Part 2): `lifestyle_small_kitchenshelf` is untracked and
fails `distortion` at 2.26 % — a regenerate, not a re-author; the "grey band"
the owner saw on the two held 5x7 portraits is undiagnosed; §6's occluded-corner
extrapolation, §4.4's `gain_map` single-hotspot reference, and the dead
`assets/mockups/manifest.json` are all recorded and untouched.

### The thing that has not happened: none of it is on master

`feat/gl6-p4-scene-library` is **36 commits ahead of master**. Master's tip is
`22a7c14` (PR #2: GL-5 + GL-21 + the first scene library). Every bundle landed
since — the chroma model, the harvest, the 11-bundle review, the five accepted
scenes, the 5x7/10x24 wiring — lives on a branch. **The runtime deploys from
master**, so this is the same class of item GL-1 was, and it is now the
cheapest thing on the critical path (GL-23).

### New scope: one Etsy listing per artwork (GL-22, "v4.12")

Owner direction, 2026-07-31. Today a design publishes as **three** Etsy
listings (primary / 5x7 / 10x24), one per aspect-ratio group — v4.11's
"one listing per group, sizes are variants". The target is **one listing per
artwork**, all six sizes as variants of it, gallery = primary mockups always,
plus the 5x7 mockups if that crop passed review, plus the 10x24 mockups if
that one did. A buyer lands on one page and picks a size; a design ends up
offering 4, 5 or 6 sizes exactly as today, but in one place.

**What already supports this, and what does not** — audited, so the build is
not re-derived:

- ✅ **The Gelato create call is already per-variant.** `create_product_from_
  template` sends `variants[].imagePlaceholders[].fileUrl`, so different sizes
  can carry different crops in **one** call. Today `group_product.py` passes
  the same `image_url` to every variant in a group; varying it is a small
  change at the caller.
- ✅ **All six portrait sizes already share one `template_id`** in
  `static_config.json` (`23444c3a-…`), with a distinct `template_variant_id`
  per size. The config *shape* already has a per-size `image_placeholder_name`;
  only the values change after the owner's template edit.
- ❓ **Whether the template edit is even needed is the first thing to verify.**
  The API takes a per-variant `fileUrl` against a placeholder *name* — it is
  not obvious that two variants sharing a placeholder name are forced to share
  an image. If they are not, the owner's manual Gelato-dashboard step
  disappears. Cheap to measure; do it before doing the edit.
- ❌ **Adding a variant to an existing product is not a documented API
  operation.** Gelato's own support article describes it as a dashboard action
  ("Edit Design" → pick sizes → Publish) or an Etsy-side edit followed by a
  re-sync. This is the load-bearing unknown behind the chosen publish flow.
- ❌ **The data model is per-group.** `groups` → `group_products` →
  `group_product_variants` / `product_images` / `listing_metrics_snapshots`
  all hang off one product per group. Under v4.12 the *review* unit stays the
  group; the *product/listing* unit becomes the candidate. That is a schema
  migration, not a config change.
- ❌ **One listing gets one shipping profile.** Today: 5x7 → Small
  (`287910553824`, €12.44), primary + 10x24 → Large (`287910565714`, €14.55).
  Merged into one listing, one of those has to give (see GL-22b).
- ❌ **Two CLAUDE.md hard constraints are written against the old shape** —
  "one Etsy listing per aspect-ratio group" and "abandon that group only:
  DELETE that group's Gelato product(s)". Under one product, abandoning 5x7
  must *not* delete anything. Both need rewriting as part of GL-22, flagged
  here rather than silently overwritten.

**Pushback, stated once:** GL-22 is a merchandising improvement, not a
functional blocker — three listings publish and sell today. It earns its
pre-launch slot because fixing it *after* listings are live means editing or
re-creating live listings, and because three near-identical listings per
design cannibalise their own search placement. But it must not become the
reason go-live slips again: hence the pre-committed fork in GL-22a.

### Everything else, unchanged from the 2026-07-26 read

- **Cron automation still does not exist** (GL-7). The only entrypoint is
  `run_m1_live_test.py`. This is now the single biggest remaining build chunk,
  and its DoD still includes the **overnight unattended soak** that is GL-16's
  only real production proof.
- **The v4.11 publish path has never completed a live end-to-end run** — and
  GL-22 will change it again before it does. Sequencing consequence in Part 3.
- **Etsy Developer Mode is still on** (GL-11) and reverting it is not
  self-service — external lead time, start it as soon as a date is roughly known.
- Storefront overhaul (GL-10) and the Google Trends application (GL-12) are
  untouched, manual, and parallel.
- The **ways-of-working overhaul (`qops`)** is owner-deferred to the **first
  action after go-live** — deliberately, to stop it delaying the pipeline. Its
  PRD v2 is written and unsigned; `.qops/` holds an untracked issue corpus.

### Verdict

The mockup track — three failed attempts, a compositor unfreeze, a chroma
model and ~160 screened images — **has landed for portrait**, and the owner's
read that only primary needs a full set is right for reasons the plan can now
state. Two things stand between here and a public store: **GL-7 (cron + soak)**
and **GL-13/17 (the live re-test)**. GL-22 inserts itself *before* the live
re-test, which is the whole sequencing question this revision answers.

---

## Part 2 — Open points, classified by work-type

Types: **IR** implementation-research (→ plan + code-session starting prompt) ·
**R** research (→ findings for planning) · **C** coding & implementation
(→ code + commit/PR) · **M** manual action (→ state changed) · **T** test run
(→ pass/fail + feedback) · **D** decision/sign-off.

### Closed — kept as one line each for traceability

**GL-6a (D, 2026-07-31) — library target revised: primary 10, secondary 2–4
each, landscape post-launch.** Reasons in Part 1; this supersedes the
Addendum's "3 flat + 7 lifestyle per group × 3 groups".

GL-1 merge round-3 ✅ · GL-2 custom mockups pre-launch = GO ✅ · GL-4 compositor
research ✅ · GL-5 compositor build + PR #2 merged (`22a7c14`) ✅ · GL-9 Round 1
live re-test PASS/GO ✅ · GL-14 group crop → Gelato ✅ · GL-15 Etsy OAuth
auto-refresh ✅ · GL-16 resilience hardening ✅ *(production-unproven — see
GL-7)* · GL-19 compositor M1 acceptance ✅ *(failed correctly, re-run pending —
see GL-19b)* · GL-21 compositor unfreeze + matte + aspect guard ✅ · GL-6
attempt 3 / scene library, portrait ✅.

### Go-live blockers

| ID | Type | Item | Input → Output |
|---|---|---|---|
| GL-23 | C | **Merge `feat/gl6-p4-scene-library` → master.** 36 commits: chroma model, intake harness, the harvest, 11 landed bundles, the five accepted scenes, 5x7/10x24 wiring, `edge-alpha-jitter` (gate is 9 detectors), `gate_waivers`. 597+ tests green on the branch. The runtime deploys from master; nothing below is real until this lands. **Cheapest item on the critical path — do it first.** | branch → PR → master |
| GL-19b | T | **Re-run the M1 render harness against the *wired* gallery.** `scripts/gl19_m1_render.py` last ran against 4 bundles, 3 of which are now rejected. The shipping gallery is 10 primary + 1 5x7 + 2 10x24 and has never been rendered end-to-end as a set. Offline render + owner eyeball, then one guarded live upload. | harness run → contact sheet → owner sign-off |
| GL-22 | R→D→IR→C | **One Etsy listing per artwork (v4.12).** Six sizes as variants of one Gelato product / one Etsy listing; gallery = primary mockups + 5x7 mockups if that crop passed + 10x24 mockups if that one passed. **Gated on GL-22a (research) and GL-22b/c (decisions) before any PRD or code.** Known scope: `group_products` becomes candidate-level (schema migration + backfill), per-variant `fileUrl` at create, one shipping profile, gallery assembly across groups with a ≤20-image assert, critic-pass abandon must stop deleting the shared product, `cleanup.py` / `discard_superseded_attempt` / `publish_group.py` / `run_m1_live_test.py` all touched, plus **SPEC v4.12** and **two CLAUDE.md hard-constraint rewrites**. | GL-22a/b/c → PRD → sign-off → build |
| GL-22a | R | **Gelato API research gate.** Four questions, each with a measurement: (1) do two variants sharing one `image_placeholder_name` accept different `fileUrl`s in one create — i.e. **is the owner's template edit necessary at all?** (2) is there any API path to **add a variant** to an existing store product, or is it dashboard-only as the support docs suggest? (3) does Gelato **re-push and overwrite** our Etsy patch after a product edit? (4) what happens to the Gelato↔Etsy variant mapping when we remove a variation from the Etsy listing inventory. Answer against the sandbox/dry-run first; one throwaway live product if needed. | 4 measured answers → picks the GL-22 build shape |
| GL-22b | D | **Shipping profile for a merged listing.** One listing = one profile. Options: Large for everything (5x7 buyer pays €14.55 instead of €12.44 — €2.11 against a €19 entry price), Small for everything (under-charges on A1 — do not), re-price 5x7 to absorb it, or hunt for a better fit among the ~49 Gelato-created profiles. **Owner call, needed before the PRD** — it moves a price. | decision → `static_config` shape |
| GL-22c | D | **Publish timing.** Owner's preference (2026-07-31): **publish the listing on primary approval, patch 5x7/10x24 variants + their mockups in as each passes.** Depends entirely on GL-22a question (2). **Pre-committed fork — do not re-litigate when reached:** if there is no API path to add a variant post-create, fall back to **create-once-when-all-groups-are-decided** (all three digest entries already go out in the same evening run; the cost is that the listing waits for two more button taps, plus a stall rule for a decision that never arrives). Second fallback, if that is unacceptable: create all six variants up front and remove rejected sizes from the Etsy inventory patch — cleanest publish, but leaves an unmapped Gelato variant, which only matters if it is orderable. | GL-22a → confirmed flow |
| GL-22d | M | **Gelato template edit** — a second/third image placeholder on the portrait template so 5x7 and 10x24 variants address their own crop. **Do not start until GL-22a question (1) is answered** — it may be unnecessary. If it is needed, re-resolve `image_placeholder_name` per size in `static_config.json` afterwards (config shape already supports it). | GL-22a → edited template + real IDs |
| GL-7 | C | **Cron orchestrator** — two cadences (hourly Telegram poll, twice-daily batch) wiring the existing 13 stages; one function per stage, not one loop. Unblocked since 2026-07-23. **DoD includes the overnight unattended soak** — GL-16 is proven in unit/scripted-interrupt tests only, and the soak is its production proof. **Now the single biggest remaining build chunk.** | GL-3 decision + kickoff → PR + clean soak |
| GL-8 | R | Where the scheduled functions run (Cowork task vs. Claude Code cron vs. Fly/Render/Cloudflare/GitHub Actions), given cost, reliability and the persistent-process ban. Preliminary decision (GL-3): local desktop. Confirm or revise. | briefing → named host |
| GL-3 | D | Cron deployment target — confirm the local-desktop preliminary against GL-8. **Pre-committed fork:** if the desktop fails the soak on wake/sleep or reliability, move to a cheap always-on host named in advance by GL-8. | GL-8 → confirmed host |
| GL-13 | T | **Round 2 live re-test — the mockup-dependent slice**, now also the **v4.12 publish slice**: custom gallery uploaded in rank order, critic pass over the custom scenes, `mockup_failed` retry with no Gelato fallback, the placeholder fail-loud guard, the real cover-crop reaching Gelato, and — post-GL-22 — one listing carrying 4/5/6 variants with a gallery that grew across two reviews. **Sequenced after GL-22, not before** (see Part 3). | delta launch guide → pass/fail |
| GL-17 | T | Residual live coverage from GL-9: the human Telegram **Reject** button (never tapped), plus any un-hit interactions. Fold into GL-13. | mini guide → pass/fail |
| GL-10 | M | Etsy storefront overhaul — banner, sections, About, policies, SEO copy. Owner-driven, one-way-valve safe. | checklist → live storefront |
| GL-11 | M | **Revert Etsy Developer Mode** — email developer@etsy.com, external approval lead time. Start as soon as a launch date is roughly known; listing visibility observed before this is not representative. | how-to → Dev Mode off |
| GL-12 | M | Apply for Google Trends API alpha access (zero cost, parallel). | how-to → submitted |

### Post-launch, ordered

| # | ID | Type | Item |
|---|---|---|---|
| 1 | GL-24 | IR+C | **The `qops` ways-of-working overhaul** — owner-deferred to the **first action after go-live**, deliberately, so it does not delay the pipeline. PRD v2 written and unsigned; `.qops/` issue corpus untracked; its own review found the token-payback claim wrong by ~5×. Re-open the PRD, do not re-derive it. |
| 2 | GL-18 | C+M | **Landscape enablement.** Two halves: the compositor/config wiring GL-5 left portrait-only, and a landscape scene library. **Owner direction 2026-07-31:** do not re-derive prompts — take the *successful portrait prompts* for validated scenes, adapt them to landscape, and pass the **portrait render as Nano Banana's reference image** so the landscape version is the same room, same light, same props. Needs a landscape geometry card per group and the landscape Gelato template's placeholder edit (GL-22d's twin). |
| 3 | GL-25 | C | **Wire Nano Banana Pro into `replicate_client`.** Deferred, not rejected — `_predict(model, input_body, …)` is already model-generic, so the work is a model constant, an input body, **reference-image encoding** (which GL-18 needs anyway), per-scene provenance, and a polling fallback for the 60 s `Prefer: wait` window that cost 11 of 72 images in P4b1. Direct dependency of GL-18. |
| 4 | GL-26 | IR+C | **Mockup authoring / compositor refinement** so fewer technical defects reach the owner's eye. Named contents: the **grey band on the two held 5x7 portraits** (undiagnosed); `flat_leaning_bookstack`'s "stairs-effect", explicitly *not* explained by `de79795`; §6's **occluded-corner extrapolation** (fit the four edges, intersect them — currently a scene class is unauthorable and the workaround is "no props at corners"); §4.4's `gain_map` reference = a single 99th-percentile hotspot, which reads as a dull print; and `scene_intake`'s hard stop on any screen failure when the screen is stricter than the gate. |
| 5 | GL-20 | R→C | Gelato "mockups ready" poll relaxation — the self-hosted gallery replaced Gelato's, so the readiness poll may be shortenable. Verify first; latency win only. |
| 6 | — | C+R | Cost/sales dashboarding — slow-loop monitor (daily views/favorers/orders + deltas) then a **Cowork live artifact**. Simplified by v4.12: one listing per design instead of three. |
| 7 | — | C | Telegram UX polish — richer inline buttons, edit flow, digest legibility. |
| 8 | — | IR | Extension beyond posters (apparel, …) — new mini-spec per product class. |
| 9 | — | R+C | New audience: FR/Wallonian prints (candidate set already researched). |
| 10 | — | IR | Generalise into a reusable pattern for sibling projects. |
| 11 | — | M+C | Documentation polish — README, user guide, runbook. |

### Housekeeping — small, real, and currently invisible

| ID | Type | Item |
|---|---|---|
| GL-27 | M+C | **Asset and doc hygiene, in one pass with GL-23.** **Eight committed bundles are not wired** — seven at primary (`flat_leaning_bookstack`, `flat_pegs_windowsill`, `lifestyle_console_pampas`, `lifestyle_framed_wall_plant`, `lifestyle_held_greytee`, `lifestyle_shelf_books`, `lifestyle_studio_held`) and `lifestyle_small_bookstack` at 5x7, which passes 8/8 at aspect 0.7285 and is the strongest 5x7 asset the repo has. Each is either owner-rejected (keep, but say so in the bundle) or an oversight (wire it) — right now "have 17, ship 10" is indistinguishable from a bug. The 5x7 one matters most: the shipping gallery has exactly **one** 5x7 image. `lifestyle_small_kitchenshelf` is untracked and fails `distortion` 2.26 % → regenerate or drop, don't re-author. Untracked inflow sources for 10x24/5x7/primary → commit with sidecars or delete (a bundle must stay a pure function of source + tool). Three inflow sidecars carry **no `key_rgb`**, so a re-`extract` silently switches `d_key_spill` off — normalise them. `lifestyle_sideboard_leaning` sits in inflow with no bundle and no recorded reason. `assets/mockups/manifest.json` is **dead and lying** (nothing reads it; it omits seven bundles) → delete it or make something read it. A `desktop.ini` is tracked-adjacent in `inflow/5x7/`. |
| GL-28 | M | **SynthID.** Every Nano Banana output carries an invisible watermark, and the store's photography is now all Nano Banana. Not an Etsy problem — the artwork is disclosed via `who_made: i_did` — but it should be a **recorded, conscious choice** rather than a thing discovered later. |

---

## Part 3 — Sequencing

Critical path to a public launch. The one change this revision makes to the
order is **GL-22 before GL-13**.

**Why GL-22 goes before the live re-test.** GL-13 exists to prove the publish
path live. v4.11's publish path has never had a clean live end-to-end run, and
v4.12 rewrites the product/listing shape of that same path. Running Round 2
first means paying for a full live test of mechanics that are about to be
replaced, then paying again. The counter-argument — that GL-22 is unscoped and
could slip — is real, which is why GL-22a is a **timeboxed research gate with
a pre-committed fallback** (GL-22c) rather than an open-ended design phase. If
GL-22a's answers make the change big, take the second fallback shape, not a
schedule slip.

**Track A — get it on master and prove the gallery (do first, it is small):**

1. **GL-23** merge the scene library → master. Blocking everything.
2. **GL-27** asset hygiene, same pass.
3. **GL-19b** re-run the M1 harness on the 13-image shipping gallery →
   owner eyeball → one guarded live upload.

**Track B — v4.12 (starts in parallel with A, gated on its own research):**

4. **GL-22a** research gate (4 measured answers) — the only item that can start
   today with zero dependencies.
5. **GL-22b / GL-22c** owner decisions off the back of it. **GL-22d** template
   edit *only if* GL-22a says it is needed.
6. **GL-22** PRD → owner sign-off (CLAUDE.md §2: external system + >1 sitting)
   → build → SPEC v4.12 + CLAUDE.md constraint rewrites in the same PR.

**Track C — automation (the long pole, independent of A and B):**

7. **GL-8 / GL-3** host research and decision — parallel, orchestrator logic is
   largely host-agnostic.
8. **GL-7** two-cadence orchestrator → **overnight unattended soak**. Do not
   tick "unattended-safe" on merge alone.

**Track D — manual, parallel, owner-driven:** GL-10 storefront now, GL-12
Trends application now, **GL-11 Developer-Mode revert as soon as a date is
roughly known** (external lead time is the only thing here you cannot compress).

**Then:** 9. **GL-13 + GL-17** — one live pass covering the custom gallery, the
v4.12 single-listing publish, the human Reject button, and the crop-to-Gelato
confirmation.

**Go-live gate (2026-07-31):** GL-23 merged **+** GL-19b gallery approved **+**
GL-22 shipped (or its fallback shape) **+** GL-7 cron running with a clean
overnight soak **+** GL-10 storefront **+** GL-13/17 clean **+** GL-11 Developer
Mode reverted. **Longest poles: (1) GL-7 cron + soak; (2) GL-22 → GL-13.**

### Tool-fit flags (CLAUDE.md §7)

- **GL-23 merge, GL-19b harness re-run, GL-22 build → Claude Code**, in-repo and
  test-driven. Cowork's role is the owner's contact-sheet review and the PRD.
- **GL-22a research → Claude Code with the Gelato client**, not Cowork: the
  answers are measurements against a real API, not reading.
- **Cron runtime is still not a Cowork job.** Scheduled functions need a real
  always-available host; the **soak** could be watched through a lightweight
  Cowork status artifact.
- **Scene generation stays hand-run by the owner** in the Nano Banana UI into
  `assets/mockups/inflow/` — no batch harness, and `scene_generate.py` is
  superseded. This is the correct tool split until GL-25 wires the model.
- **Post-launch cost/sales view → a Cowork live artifact.**

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

---

## Part 4 (cont.) — Session log (2026-07-29 → 2026-07-31)

**Session H — the chroma model** (`docs/2026-07-29-gl6-chroma-model-plan.md`
§7). The matte decided coverage from a pixel's Lab a/b distance to a *fixed*
key reference, so a shadowed key — still 100 % key — drifted into the ramp and
printed half-transparent: 5532 px at alpha 0.87 under a vase's shadow, 847 px
at 0.61 under a hand's grip, while a genuine prop sat at distance 76 against
the shadow's 20–31. Fixed by fitting the key's **locus** through (L, a, b) per
image and measuring deviation from that curve. All eight acceptance criteria
met; the documented `MATTE_LO = 0.85` fallback was **not** used. The owner
directive behind it — *buyers expect golden hour and real shadows, not flat
light* — retired the "flat, even, no gradient" prompt clause that had survived
as cargo cult into every later prompt.

**Session I — the harvest** (same doc, Part 4). The model changed the mask, so
every scene the *old* screen rejected had been judged by a measurement that no
longer existed. Re-screening 116 already-paid-for images moved the primary
library **6 → 11 at zero generation spend**. The finding worth carrying: of the
12 scenes then passing, **10 had never been authored** — six were passing the
old screen too and were simply never picked up. The backlog's value was the
inventory, not the mask change.

**Session J — the owner review of 11 primary bundles** (§9). Five accepted, six
rejected — three of them scenes that had been shipping since PR #2, so the
gallery changed composition, not just size. **Four of the rejections were one
defect**: `soft_matte`'s ramp had no spatial term, so a source edge sharper
than the ramp put one noisy pixel per row inside it and its alpha jittered
0.34 → 0.84 → 0.48 — the "dotted line" in four separate review notes, on four
bundles that all passed the gate 8/8. Fixed with a banded blur; **new detector
`edge-alpha-jitter`** takes the gate to nine. A tempting alternative (use the
quad's analytic coverage near an edge) was built, measured, and **refuted** —
recorded so it is not proposed a fourth time.

**Sessions K–N — the library to shipping shape.** Five more primary scenes
landed (17 bundles, 10 wired), the first 5x7 and the first two 10x24 bundles
landed, and `gate_waivers` was added: a waived detector still runs and still
prints its measurement, prefixed `WAIVED`; only whether it blocks changes.
That keeps "switch a detector off across the corpus" a change to the detector,
with a measurement behind it, while a waiver stays a statement about one
photograph. `83544b7` wired the five accepted scenes and closed the hole where
a 5x7 or 10x24 listing could publish with **zero images and nothing failed** —
two tests had been pinning exactly that state.

**Session O — this plan revision (Cowork, 2026-07-31).**

- **The library divergence is now a decision (GL-6a), with three reasons** —
  secondary mockups only ever appear on a listing whose crop passed review;
  Etsy's 20-photo cap makes 10/10/10 impossible on a merged listing while
  10/1/2 fits; and 10x24's 0.4167 is the hardest aspect to generate.
- **GL-22 (v4.12) is planned, not started**, behind a research gate. The audit
  found the good news and the bad news together: the Gelato create call is
  *already* per-variant and all six portrait sizes *already* share one
  `template_id`, so the create side is a small change — but adding a variant to
  an existing product is a **dashboard** action in Gelato's own docs, which is
  precisely the operation the owner's preferred publish flow needs. Hence
  GL-22a, and a pre-committed fallback in GL-22c.
- **A manual step may be avoidable.** GL-22a's first question asks whether two
  variants sharing an `image_placeholder_name` can carry different `fileUrl`s.
  If they can, the owner's Gelato template edit is unnecessary. Measure before
  editing.
- **Two consequences of GL-22 that are easy to miss and change money or
  behaviour:** one listing gets **one shipping profile**, so the 5x7's €12.44
  Small tier and the primary's €14.55 Large tier cannot both survive (GL-22b);
  and the CLAUDE.md constraint "abandon that group only — DELETE that group's
  Gelato product" becomes actively wrong when three groups share one product.
- **Etsy's photo limit is 20, not 10** (raised August 2025). 10 + 1 + 2 = 13
  fits with headroom; the build should assert it rather than assume it, and
  the API is known to be fussy about image `rank` near the cap.
- **`feat/gl6-p4-scene-library` is 36 commits ahead of master** and none of the
  above is deployable until GL-23 merges it. Same class of item as GL-1, and
  the cheapest thing on the critical path.
- **Post-go-live queue is now ordered, not a bag:** `qops` first (owner's
  explicit call — pipeline feeding the store before any overhaul of how work
  gets done), then landscape enablement (portrait prompts adapted + the
  portrait render as Nano Banana's reference image), which pulls GL-25's
  reference-image encoding in with it, then the compositor/authoring
  refinement that the grey band and the occluded-corner class belong to.
