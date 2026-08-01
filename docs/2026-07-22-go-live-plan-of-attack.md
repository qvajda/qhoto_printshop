# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

> **Last updated 2026-08-02 — GL-22 session 1 ✅ landed, session 2 kicked
> off.** Four commits (`6df9ba5` `ed660c1` `b0560df` `4c878b3`): the two
> `etsy_client` fixes, the additive schema migration, the candidate-keyed
> create path, and a review-pass fix for a legacy-row hole. **Two things the
> session found that reshape session 2:** (1) `create_or_reuse_group_product`
> is **welded** to the local mockup render, and v4.12 gives those two jobs
> incompatible timings — so session 2 cuts the weld before anything else;
> (2) the secondary (5x7/10x24) path is **deliberately broken between the
> sessions** — dry-run-only ground, but real. **And an incident:** a subagent
> ran `git stash` and wiped the working tree; recovered in full. Standing
> rule now: **subagent briefs need a command denylist, not just a file
> allowlist.** Session 2's kickoff:
> `docs/2026-08-02-gl22-session2-kickoff.md`.
>
> **2026-08-01 (evening) — Track B's gate is closed.**
> **GL-22a ✅** ran live: four measured answers, two throwaway Gelato products
> created and deleted. It **struck GL-22d** (a shared `image_placeholder_name`
> does *not* force a shared image — the owner's template edit was never
> needed) and **killed two of GL-22c's three options** (no API path adds a
> variant post-create; pruning a variation orphans the Gelato mapping).
> **GL-22b ✅ decided: `Gelato: Free shipping` (`288734253315`)**, a profile
> the original options list didn't know existed — €0 to every destination,
> **no re-pricing**, all six sizes still clear cost at 21–44 %.
> **GL-22c ✅ decided: create-once-when-all-groups-are-decided, publishing
> only validated sizes, with a plain 14-day stall timeout** (the reminder
> ping is deferred post-go-live as **GL-31**, which shrinks the rule from a
> new stage to a predicate). The
> PRD (`docs/2026-08-01-v412-single-listing-prd.md`) is **signed off**, and
> GL-22 is now a **two-session build**, session 1 kicked off in
> `docs/2026-08-01-gl22-session1-kickoff.md`. Everything below GL-22 is
> unchanged.
>
> **Earlier 2026-08-01 — Track A is closed.** GL-23 ✅ merged (master
> carries the wired 10 + 1 + 2 gallery) and GL-19b ✅ passed (13/13 rendered,
> deterministic, size-checked, owner-approved). Two new owner items:
> **GL-29** — programmatic draft→active publishing behind an `ETSY_ACTIVATE_
> LISTINGS` flag, which **GL-11 now waits on**; and **GL-30** — a one-off
> backup of the mockup corpus to R2 before go-live, with **GL-30b**, the
> authoring-time sync, deferred after it. Both are endorsed; both are smaller
> than they look, because `etsy_client.update_listing_state` and
> `artwork_store`'s R2 uploader already exist.
>
> **2026-07-31 — the mockup milestone is achieved for portrait,
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
| GL-23 | C | **✅ DONE 2026-08-01** — merged; master carries the wired 10 + 1 + 2 gallery. Original scope: **merge `feat/gl6-p4-scene-library` → master.** 36 commits: chroma model, intake harness, the harvest, 11 landed bundles, the five accepted scenes, 5x7/10x24 wiring, `edge-alpha-jitter` (gate is 9 detectors), `gate_waivers`. 597+ tests green on the branch. The runtime deploys from master; nothing below is real until this lands. **Cheapest item on the critical path — do it first.** | branch → PR → master |
| GL-19b | T | **✅ DONE 2026-08-01** — 13/13 rendered, deterministic, size-checked, owner-reviewed and approved (`93914b2` pre-crops the master to each group's print ratio in the harness). Gallery is clear for the guarded live upload. Original scope: **re-run the M1 render harness against the *wired* gallery.** `scripts/gl19_m1_render.py` last ran against 4 bundles, 3 of which are now rejected. The shipping gallery is 10 primary + 1 5x7 + 2 10x24 and has never been rendered end-to-end as a set. Offline render + owner eyeball, then one guarded live upload. | harness run → contact sheet → owner sign-off |
| GL-22 | C | **One Etsy listing per artwork (v4.12). Session 1 ✅ landed 2026-08-01 (`6df9ba5` `ed660c1` `b0560df` `4c878b3`); session 2 kicked off in `docs/2026-08-02-gl22-session2-kickoff.md`.** Session 2's shape changed on session 1's findings: it now starts by **cutting the weld** between the Gelato create and the local mockup render (incompatible timings under `[D1]`), which also un-breaks the deliberately-broken 5x7/10x24 path. Original scope below, unchanged otherwise.<br>**PRD signed off 2026-08-01.** Six sizes as variants of one Gelato product / one Etsy listing; gallery = primary mockups + 5x7 mockups if that crop passed + 10x24 mockups if that one passed. PRD: `docs/2026-08-01-v412-single-listing-prd.md`. **Now a two-session build. Session 1** (`docs/2026-08-01-gl22-session1-kickoff.md`): the two `etsy_client` fixes (`update_listing_inventory`'s float-price bug + a new `delete_listing`, which needs a **manual `listings_d` re-auth**), the additive schema migration (`group_products.candidate_id`, `group_product_variants.group_id`, `product_images.group_id`), and the candidate-keyed `create_or_reuse_group_product` with per-group `fileUrl` per variant in one create call. **Session 2:** gallery assembly across groups with a ≤20-image assert and scoped clear/rebuild (the sharpest correctness risk — one group's rebuild must not wipe another's images), abandon/reject/cleanup stopping the shared-product delete, the shipping-profile collapse to one value, the **new stall-sweep stage** (`[D2]`, see GL-22c), the digest/mockup/critic pass, `run_m1_live_test.py` + tests, **SPEC v4.12**, and **three CLAUDE.md rewrites + one addition**. | ✅ PRD → session 1 PR → session 2 PR |
| GL-22a | R | **✅ DONE 2026-08-01** — findings: `docs/2026-08-01-gl22a-findings.md`. Four measured answers against the live API, two throwaway Gelato products created and deleted per the ledger. **(1) A shared `image_placeholder_name` does NOT force a shared image** — two variants carry independently-submitted `fileUrl`s in one `create-from-template` call → **GL-22d struck**. **(2) No API path adds a variant to an existing store product** — `PUT` silently drops the added variant *and* severs the Etsy sync, `PATCH` is 405, `/variants` is an incompatible custom-priced flow, and a re-`create-from-template` with the same title makes a *second* product → GL-22c option (a) dead. **(3) Q3 is confounded**, not answered — the only edit path tested (`PUT`) breaks the sync by itself; "Gelato may re-push after a dashboard edit" stays an open risk. **(4) Dropping a variation from the Etsy inventory patch orphans the Gelato mapping with no observed self-heal** → GL-22c option (c) dead. Two side-findings: a live `update_listing_inventory` float-price bug, and no `delete_listing` + no `listings_d` scope on the current token. | ✅ 4 answers → picked shape (b), struck GL-22d |
| GL-22b | D | **✅ DECIDED 2026-08-01 — `Gelato: Free shipping` (`288734253315`), €0 to every destination, one profile for the whole candidate.** The original options list (Large / Small / re-price 5x7) was built on an incomplete profile read; the live `GET .../shipping-profiles` turned up a free-shipping profile that removes the dilemma entirely. **Two corrections it forced:** the €12.44/€14.55 figures in `CLAUDE.md` are the *default/non-EU* rate, not flat global (EU sees €5.86/€7.04); and Gelato's real per-item shipping (€5.10–€5.86) is billed to the seller **regardless of profile** and is already inside the cost basis the retail prices were set against — so **no re-pricing is required**. Verified: 5x7 21.4 %, 8x12 32.6 %, A3 38.6 %, A2 38.0 %, 10x24 44.2 %, A1 42.1 % at 9.5 % + €0.25, reproducing SPEC v4.11 §4's ~21–44 %. Floor case (5x7 through Offsite Ads at 15 %) still nets 16.4 %. **What it forfeits, recorded:** the shipping surcharge on default-region/US orders — revenue the margin table never counted. | ✅ decision → single-value `etsy_shipping_profile_id` |
| GL-22c | D | **✅ DECIDED 2026-08-01 — option (b), create-once-when-all-groups-are-decided, publishing only validated sizes; stall rule = a plain 14-day timeout.** Options (a) and (c) were killed by GL-22a's Q2/Q4, so (b) was the surviving shape. **Stall rule revised same-day:** an initial "48 h nudge → 96 h skip" was replaced by a long timeout with **no reminder** (owner: defer the ping to post-go-live, → **GL-31**). That revision is what makes it cheap — with nothing to *send*, the rule is a **predicate, not a process**: the publish gate's "have all groups decided?" check gains an "…or has an undecided group aged past 14 days?" clause. Total scope: `stalled_skipped` in the `groups.status` CHECK, `GROUP_REVIEW_STALL_DAYS = 14` in `pipeline/config`, one predicate. **No `stall_sweep` stage, no `reminder_sent_at` column** — both struck with the nudge; the `CLAUDE.md` stage list is untouched. Window measured off the existing `groups.updated_at`. **Still depends on GL-7** in weaker form: the gate only fires when something evaluates it, so until the twice-daily batch exists the effective behaviour is wait-indefinitely — **"the stall rule fires" is a GL-7 DoD item, not a GL-22 one.** **A skipped size is a real forfeit, not a deferral** — Q2 means recovering it needs a from-scratch re-publish, which is the argument for erring long. | ✅ decision → shape (b) + a 14-day predicate |
| GL-22d | M | **✅ STRUCK 2026-08-01 — never needed.** GL-22a Q1 proved two variants sharing one `image_placeholder_name` accept independently-submitted `fileUrl`s in a single `create-from-template` call, so the portrait template needs no second/third placeholder and `static_config`'s existing per-size `image_placeholder_name` values stand. **Kept as a line, not deleted: this was a manual owner step on the critical path that a €0 measurement removed.** Its landscape twin (named in GL-18) is struck by the same finding. | — |
| GL-7 | C | **Cron orchestrator** — two cadences (hourly Telegram poll, twice-daily batch) wiring the existing 13 stages; one function per stage, not one loop. Unblocked since 2026-07-23. **DoD includes the overnight unattended soak** — GL-16 is proven in unit/scripted-interrupt tests only, and the soak is its production proof. **DoD gained one item 2026-08-01: prove v4.12's stall predicate actually fires.** GL-22 writes it, but it is dormant until the batch cadence evaluates the publish gate — so "the 14-day timeout works" is provable here and nowhere earlier (test with the constant temporarily lowered, not by waiting 14 days). **Now the single biggest remaining build chunk.** | GL-3 decision + kickoff → PR + clean soak |
| GL-8 | R | Where the scheduled functions run (Cowork task vs. Claude Code cron vs. Fly/Render/Cloudflare/GitHub Actions), given cost, reliability and the persistent-process ban. Preliminary decision (GL-3): local desktop. Confirm or revise. | briefing → named host |
| GL-3 | D | Cron deployment target — confirm the local-desktop preliminary against GL-8. **Pre-committed fork:** if the desktop fails the soak on wake/sleep or reliability, move to a cheap always-on host named in advance by GL-8. | GL-8 → confirmed host |
| GL-13 | T | **Round 2 live re-test — the mockup-dependent slice**, now also the **v4.12 publish slice**: custom gallery uploaded in rank order, critic pass over the custom scenes, `mockup_failed` retry with no Gelato fallback, the placeholder fail-loud guard, the real cover-crop reaching Gelato, and — post-GL-22 — one listing carrying 4/5/6 variants with a gallery that grew across two reviews. **Sequenced after GL-22, not before** (see Part 3). | delta launch guide → pass/fail |
| GL-17 | T | Residual live coverage from GL-9: the human Telegram **Reject** button (never tapped), plus any un-hit interactions. Fold into GL-13. | mini guide → pass/fail |
| GL-10 | M | Etsy storefront overhaul — banner, sections, About, policies, SEO copy. Owner-driven, one-way-valve safe. | checklist → live storefront |
| GL-29 | C+T | **Programmatic draft→active publishing, behind an env gate (NEW 2026-08-01, owner).** Today activation is a manual per-listing dashboard action by design. **Half of this already exists:** `etsy_client.update_listing_state` is written, dry-run-aware and unit-tested, carrying a `# DELIBERATELY UNWIRED` comment and a guard test (`test_patch_etsy_listing_never_activates_a_listing`). The work is therefore *the gate and the wiring*, not an integration: a new all-or-nothing flag (`ETSY_ACTIVATE_LISTINGS`, **default false**, resolved like `is_live_mode`), one call site at the end of the publish path, the guard test **rewritten rather than deleted** (it must now assert "never activates *unless the flag is on*"), and loud logging on every activation with the listing ID. **Three constraints the build must respect:** (1) Etsy's API says setting `state=active` publishes the listing and **it can never return to `draft`** — only `active`↔`inactive` — so this is a one-way door per CLAUDE.md §4: record an `activated_at` on the row and ship the `inactive` path in the same PR as the rollback; (2) activation costs **$0.20 per listing** and is charged in Developer Mode too, so each live test burns real money — budget a handful of euros, not a sweep; (3) **ordering vs GL-22** — activation must be the *last* step, after every group's patch has landed, or a buyer-visible listing gains variants and gallery images afterwards. **✅ Resolved 2026-08-01 by GL-22c's decision:** under create-once-when-all-groups-are-decided the listing is created with every validated size and its full gallery already assembled, so activation is unambiguously the last call in the publish path and GL-29 needs no ordering logic beyond "call it last". **Testing in Developer Mode proves the API call, not shopper-facing visibility** — the visual confirmation belongs to the first minutes after GL-11. | flag + wiring + rewritten guard → one live activation → GL-11 |
| GL-11 | M | **Revert Etsy Developer Mode** — email developer@etsy.com, external approval lead time. Start as soon as a launch date is roughly known; listing visibility observed before this is not representative. **Owner sequencing (2026-08-01): GL-29 lands and is tested first** — the point of reverting is a store that publishes, and the publish step should be proven before the shop is public. Start the *email* early regardless; the lead time is the thing you cannot compress. | GL-29 → how-to → Dev Mode off |
| GL-30 | C+M | **One-off backup of the mockup corpus to Cloudflare R2 (NEW 2026-08-01, owner).** Every generated scene — accepted, parked and rejected — exists only on the desktop. **Scope it to what git does not already have**, see the note below the table: the git-ignored `outputs/gl6_*` batches (~160 screened images **and their `screen.json` verdicts**), the untracked `inflow/` sources, `lifestyle_small_kitchenshelf`, and anything parked outside the tree. **Reuse `artwork_store._r2_put_object` + `_sigv4_headers`** — the S3-compatible PUT, the SigV4 signing and the all-or-nothing `R2_*` env gate are already written and tested; do not write a second uploader. **Write-once, never overwrite:** date- or content-addressed keys under one prefix, because a sync that can overwrite is a copy, not a backup. **Carry each image's sidecar/`screen.json` with it** — without the verdicts the corpus is 160 anonymous PNGs and the inventory value (the thing the harvest proved was worth more than the mask change) is lost. Parallel to the critical path; must not delay GL-7 or GL-22. | script → uploaded corpus + a manifest of what landed where |
| GL-12 | M | Apply for Google Trends API alpha access (zero cost, parallel). | how-to → submitted |

**Scoping note for GL-30 — what is actually at risk.** Committed bundles are
**not** local-only: `origin` on GitHub is already an off-machine copy of every
tracked bundle, and the repo is public by deliberate decision (qops PRD §10).
What has no second copy is the material git was told to ignore — the
`outputs/gl6_*` batches, the untracked inflow sources, and anything parked
outside the tree. Backing those up is insurance worth buying; re-uploading the
committed bundles is paying twice for the same copy. If you want one
consolidated corpus anyway — one place to browse everything ever generated,
rather than two — that is a fine reason, but take it as a stated choice rather
than as a data-loss argument.

### Post-launch, ordered

| # | ID | Type | Item |
|---|---|---|---|
| 1 | GL-24 | IR+C | **The `qops` ways-of-working overhaul** — owner-deferred to the **first action after go-live**, deliberately, so it does not delay the pipeline. PRD v2 written and unsigned; `.qops/` issue corpus untracked; its own review found the token-payback claim wrong by ~5×. Re-open the PRD, do not re-derive it. |
| 1b | GL-30b | C | **Authoring-time R2 sync (NEW 2026-08-01, owner — the long-term half of GL-30).** Every candidate lands in R2 as it is screened/authored, with its verdict, so the one-off never has to be repeated. Natural hook: `scripts/scene_intake.py`, which already runs the screen, the gate and prints the verdict block — it just does not persist anything durable. Same write-once key discipline as GL-30. Owner-deferred to post-go-live. |
| 1c | GL-31 | C | **The stall reminder ping (NEW 2026-08-01, owner — the deferred half of GL-22c's stall rule).** Before a group ages out of review, re-send its digest entry as a nudge so the owner has a chance to act. Deferred so v4.12's stall rule stays a predicate rather than growing a stage. **Worth pulling forward rather than letting it sink:** with no reminder, the only signal a group is aging out is the owner remembering an untapped digest entry, and a size that times out **cannot be added back** (GL-22a Q2 — recovery is a from-scratch re-publish). Scope when it lands: a `groups.reminder_sent_at` column, a send point, and a threshold constant below `GROUP_REVIEW_STALL_DAYS`. |
| 2 | GL-18 | C+M | **Landscape enablement.** Two halves: the compositor/config wiring GL-5 left portrait-only, and a landscape scene library. **Owner direction 2026-07-31:** do not re-derive prompts — take the *successful portrait prompts* for validated scenes, adapt them to landscape, and pass the **portrait render as Nano Banana's reference image** so the landscape version is the same room, same light, same props. Needs a landscape geometry card per group. **The landscape template's placeholder edit — GL-22d's twin — is struck by GL-22a Q1** (a shared placeholder name does not force a shared image), so this is now one fewer manual Gelato step than the plan assumed. |
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

**Track A — get it on master and prove the gallery — ✅ DONE 2026-08-01:**

1. **GL-23** ✅ merged; master carries the wired 10 + 1 + 2 gallery.
2. **GL-19b** ✅ 13/13 rendered, deterministic, size-checked, owner-approved.
   The gallery is clear for the guarded live upload — which now happens inside
   GL-13, not as a separate step.
3. **GL-27** asset hygiene — still open, still small; the eight
   authored-but-unwired bundles are the part with a gallery consequence.

**Track B — v4.12 — gate closed 2026-08-01, now a straight build:**

4. **GL-22a** ✅ research gate — 4 measured answers, GL-22d struck, two of
   GL-22c's three options killed.
5. **GL-22b** ✅ Free shipping, no re-pricing. **GL-22c** ✅ create-once +
   a 14-day stall timeout (reminder deferred → GL-31). **GL-22d** ✅ struck —
   never needed.
6. **GL-22 PRD** ✅ signed off. Build in two sessions:
   **6a. Session 1** ✅ — `etsy_client` fixes + schema migration +
   candidate-keyed create path, four commits, dry-run only. The
   **`listings_d` OAuth re-auth** ✅ is done.
   **6b. Session 2** — **cut the weld first** (split the Gelato create from
   the local mockup render; this is also what un-breaks the 5x7/10x24 path
   session 1 left deliberately broken), then gallery assembly (the sharp
   risk), abandon/cleanup, shipping collapse, the stall predicate, digest
   pass, tests, SPEC v4.12 + CLAUDE.md rewrites. **May split into two PRs at
   the A–C / D–G line** if it runs long — the mechanical half should not sit
   unmerged behind the gallery rework.

   *Sequencing note:* the **stall predicate is written in 6b but does not
   fire until GL-7** evaluates the publish gate on a cadence. Until then
   v4.12 behaves as wait-indefinitely, which is harmless while every run is
   hand-triggered — but it means "the stall rule fires" is a **GL-7 DoD
   item**, not a GL-22 one, and GL-13's stall-rule test moves with it.

   *Both sessions run with subagents* — see the kickoff's §5 for the split
   and which model each leg gets.

**Track C — automation (the long pole, independent of A and B):**

7. **GL-8 / GL-3** host research and decision — parallel, orchestrator logic is
   largely host-agnostic.
8. **GL-7** two-cadence orchestrator → **overnight unattended soak**. Do not
   tick "unattended-safe" on merge alone.

**Track D — manual and parallel, owner-driven:** GL-10 storefront now, GL-12
Trends application now, **GL-30** the one-off corpus backup (small, independent,
must not push anything else right), and the **GL-11 email as soon as a date is
roughly known** — the external lead time is the only thing here you cannot
compress, so start the clock early even though the *revert itself* now waits
on GL-29.

**Then, in order:**

9. **GL-13 + GL-17** — one live pass covering the custom gallery and its first
   guarded upload, the v4.12 single-listing publish, the human Reject button,
   and the crop-to-Gelato confirmation.
10. **GL-29** activation behind its flag, proven with one paid live activation
    (Developer Mode proves the call, not the shopper's view).
11. **GL-11** Developer Mode off → the visual confirmation GL-29 could not get.

**Go-live gate (2026-08-01, evening):** GL-23 ✅ **+** GL-19b ✅ **+**
GL-22a ✅ **+** GL-22b ✅ **+** GL-22c ✅ **+** GL-22d ✅ struck **+** GL-22
shipped (sessions 1 and 2) **+** GL-7 cron running with a clean overnight
soak **+** GL-10 storefront **+** GL-13/17 clean **+** GL-29 activation proven
behind its flag **+** GL-30 corpus backed up **+** GL-11 Developer Mode
reverted.
**Longest poles: (1) GL-7 cron + soak; (2) GL-22 → GL-13 → GL-29 → GL-11.**
Note that the last pole is now a *chain* of four, three of which are cheap —
the expensive one is GL-22, and GL-11's external lead time runs in parallel
with all of it. **What changed today:** GL-22 is no longer gated on anything
— research and both decisions are closed, one manual step (GL-22d) was
deleted outright, and the remaining risk is concentrated in session 2's
gallery assembly rather than spread across an unscoped design phase. GL-7
picked up one new DoD item (wire and prove the stall sweep).

### Tool-fit flags (CLAUDE.md §7)

- **GL-23 merge, GL-19b harness re-run, GL-22 build → Claude Code**, in-repo and
  test-driven. Cowork's role is the owner's contact-sheet review and the PRD.
- **Within a Claude Code session, split by risk and match the model to the
  leg** (owner direction, 2026-08-01). Bounded, fully-spec'd, mechanical work
  — a client bug fix with a known cause, an additive migration, a
  diff-against-DoD review — runs as **Sonnet** subagents, in parallel where
  there are no shared files. Work carrying preserved-behaviour constraints or
  a silent-corruption risk stays on the main thread. The cheap tell: if the
  kickoff already says exactly what the code must do, it is a subagent's job;
  if the kickoff says "if these two requirements collide, stop and flag it",
  it is not.
- **Every subagent brief carries a command denylist, not just a file
  allowlist** (learned the hard way, 2026-08-01 — see Session R). No
  `git stash`, `reset --hard`, `checkout -- .`, `restore`, `clean`, `rebase`,
  `merge`, `cherry-pick`, history rewrite, `stash drop/clear`, `rm -rf`
  outside its own scratch dir, or any `*_LIVE_MODE` env var. **Reading git
  state stays unrestricted.** The allowlist alone is insufficient because
  the commands that do the damage take no file arguments.
- **Keep the read-only review subagent.** It cost one Sonnet pass per commit
  and found a hole against live data (candidate 39's published row) that
  neither the implementing agent nor the kickoff anticipated.
- **GL-22a research → Claude Code with the Gelato client**, not Cowork: the
  answers are measurements against a real API, not reading.
- **Cron runtime is still not a Cowork job.** Scheduled functions need a real
  always-available host; the **soak** could be watched through a lightweight
  Cowork status artifact.
- **Scene generation stays hand-run by the owner** in the Nano Banana UI into
  `assets/mockups/inflow/` — no batch harness, and `scene_generate.py` is
  superseded. This is the correct tool split until GL-25 wires the model.
- **Post-launch cost/sales view → a Cowork live artifact.**
- **GL-29 and GL-30 → Claude Code.** GL-29 is a flag, one call site and a
  rewritten guard test in a repo that already holds the client function;
  GL-30 is a one-off script reusing the existing R2 uploader. Neither is a
  Cowork job, and neither is big enough to want a PRD — CLAUDE.md §2's
  threshold catches GL-29 on "touches an external account", so it gets the
  short version: state the flag's name, default and call site, get a nod,
  build it.

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
**Session P — status update and two new items (Cowork, 2026-08-01).**

- **GL-23 ✅ and GL-19b ✅.** The scene library is on master and the 13-image
  shipping gallery renders deterministically, size-checked and owner-approved.
  Track A is closed; the guarded live upload folds into GL-13 rather than
  standing alone.
- **GL-29 (activation behind a flag) is half-built already.**
  `etsy_client.update_listing_state` exists, is dry-run-aware and unit-tested,
  and carries a `# DELIBERATELY UNWIRED` comment plus a guard test asserting
  the publish path never activates. That was the right call under the old
  posture and it is exactly the seam this change needs — so the work is the
  gate, one call site, and **rewriting** the guard to "never activates unless
  the flag is on". Deleting that test would throw away the only thing standing
  between a bug and a buyer-visible listing.
- **The one-way door, recorded before it is walked through:** Etsy's API
  allows `draft → active`, and after that only `active ↔ inactive`. A listing
  can never go back to draft. That makes activation a CLAUDE.md §4 action in
  its own right — the flag is the control, `inactive` is the rollback, and
  both ship together.
- **GL-11 now waits on GL-29**, per owner: prove the publish step before the
  shop is public. The *email* still starts early — its lead time is external
  and runs in parallel with everything.
- **GL-30's scope was narrowed on evidence.** "The mockups only exist locally"
  is true of the ignored corpus and *not* true of the committed bundles, which
  are on `origin`. The one-off targets the at-risk set — the `outputs/gl6_*`
  batches with their `screen.json` verdicts, the untracked inflow sources, the
  parked candidates — and reuses `artwork_store`'s existing SigV4 R2 uploader
  rather than growing a second one. Write-once keys, verdicts carried
  alongside the pixels: the harvest already proved the inventory was worth
  more than the images.
- **Post-go-live queue is now ordered, not a bag:** `qops` first (owner's
  explicit call — pipeline feeding the store before any overhaul of how work
  gets done), then landscape enablement (portrait prompts adapted + the
  portrait render as Nano Banana's reference image), which pulls GL-25's
  reference-image encoding in with it, then the compositor/authoring
  refinement that the grey band and the occluded-corner class belong to.

**Session Q — GL-22 gate closed, build cleared (Cowork, 2026-08-01 evening).**

- **Research answered more than it was asked.** GL-22a's four questions were
  scoped to pick a build shape. They did that, and also **deleted a manual
  owner step** (GL-22d, and its landscape twin in GL-18) and **found two
  latent defects** — a live `update_listing_inventory` float-price crash that
  fires the first time anyone patches a subset of a listing's sizes, and the
  absence of both `delete_listing` and the `listings_d` scope, discovered
  because the session could not clean up its own throwaway drafts. Both fold
  into session 1. This is the case for measuring before building, made
  concretely: Q1 alone paid for the session.
- **The decisions narrowed rather than chose.** Q2 and Q4 killed two of
  GL-22c's three publish shapes outright, so the "decision" was really a
  confirmation of the only survivor. Worth naming, because the plan of
  record still framed GL-22c as an open three-way call.
- **GL-22b's options list was wrong, not just unresolved.** It offered
  Large / Small / re-price-5x7 and told the session to check for a better
  fit. There was one — `Gelato: Free shipping` — and finding it dissolved
  the trade-off rather than resolving it. Two factual corrections came with
  it: the €12.44/€14.55 figures are the default/non-EU rate, and Gelato's
  per-item shipping is billed to the seller whichever profile is set. The
  owner's read — "free shipping shown to customers, cost absorbed in the
  listed price" — is right, with the correction that **the prices already
  absorb it**; no re-pricing is required, and all six sizes hold 21–44 %.
- **The stall rule got costed, then got cheaper.** The first shape — "48 h
  nudge, 96 h skip" — was a better answer than either option the findings
  doc offered, and costing it honestly showed it needed a new stage, two
  schema changes and a hard GL-7 dependency. The owner then **deferred the
  reminder to post-go-live (GL-31)**, and that one deferral collapsed the
  rest: with nothing to *send*, the rule stops being a process and becomes a
  **predicate** on the publish gate — one status value, one constant, one
  extra clause. No stage, no `reminder_sent_at`, no `CLAUDE.md` stage-list
  edit. Worth recording as a pattern, not just an outcome: the expensive
  part of "timeout with a reminder" was never the timeout.
- **The GL-7 dependency survives the simplification.** The predicate is only
  evaluated when something runs the gate, so until the twice-daily batch
  exists v4.12's *effective* behaviour is wait-indefinitely — "the stall
  rule fires" is a **GL-7 DoD item**, not a GL-22 one, and it is provable
  there by lowering the constant rather than waiting two weeks. Recorded so
  it isn't discovered later as a silent no-op.
- **The window went from 96 h to 14 days on an asymmetry, not a preference.**
  Waiting too long costs a design sitting unpublished — recoverable with a
  button tap. Aging out too early costs a size permanently missing from a
  live listing, and Q2 means it cannot be patched back. Err long.
- **A skipped size is a forfeit, not a deferral.** Q2's finding (no API path
  adds a variant post-create) means a group that times out at 96 h cannot be
  patched back in — recovering it needs a from-scratch re-publish of the
  candidate's listing. The 96 h number should be read with that in mind; it
  is a first cut, and GL-7's soak is the first chance to calibrate it.
- **GL-29's one open question closed for free.** Its "ordering vs GL-22" was
  only a real decision under publish-primary-patch-later. Under the decided
  shape, activation is simply the last call.
- **The build splits at the gallery.** Session 1 (client fixes, schema,
  create path) is mechanical and dry-run-only. Session 2 carries the one
  genuinely dangerous change — scoped gallery clear/rebuild, where a wrong
  scope silently wipes another group's uploaded images — and gets its own
  session and PR rather than riding behind a migration.
- **Both sessions run with subagents, model-matched to the leg** (owner
  direction, 2026-08-01). The split falls out of the same risk gradient that
  split the sessions: the `etsy_client` fixes and the additive migration are
  bounded, spec'd and mechanical → **Sonnet** subagents, parallel. The
  create-path rework and session 2's gallery assembly carry three
  preserved-behaviour constraints and the silent-wipe risk → **kept on the
  main thread**. A **Sonnet review subagent** reads each diff against the
  kickoff's DoD before the commit. Detail in the kickoff's §5.

**Session R — GL-22 session 1 landed; a weld, a breakage and an incident
(Claude Code + Cowork, 2026-08-01/02).**

- **Session 1 delivered all three workstreams** — the `update_listing_
  inventory` float-price fix, `delete_listing`, the additive migration, and
  the candidate-keyed create path. Four commits, dry-run only, suite green.
- **The shared-product collision resolved exactly as the kickoff pointed.**
  The sizes-changed delete now fires only when every variant belongs to the
  calling group; otherwise `SharedProductVariantError`. **The instruction to
  stop and flag rather than pick a side did its job** — this was the one
  place session 1's kickoff refused to pre-decide, and it was also the one
  place a wrong guess would have deleted a live product.
- **The review subagent earned its slot.** It found a hole nobody was
  looking for: pre-migration variants carry `group_id NULL`, so a legacy
  product reads as *unshared* however many sizes it backs — candidate 39's
  id-10 row (live listing `4542159277`) would have cleared the new check.
  Unreachable under current callers, closed anyway by refusing the recreate
  on any `published` row. A read-only reviewer catching a live-data hole is
  the argument for keeping that leg.
- **The PRD was wrong about one thing, and it matters.** "A small change at
  the caller" underestimated `create_or_reuse_group_product`: the function
  **also renders the local compositor mockups** the review gallery is made
  of. Under `[D1]` those two jobs have incompatible timings — mockups before
  any decision, Gelato product after all of them — so the weld has to be
  cut. Session 2 now starts there. **Recorded as a planning miss, not a
  surprise:** the PRD flagged `group_mockup.py`'s extent as untraced and
  said so; this is what untraced looked like when traced.
- **The secondary path is deliberately broken between the sessions.**
  `group_mockup` for 5x7/10x24 resolves the candidate's primary product,
  mismatches sizes, hits the guard. Dry-run-only ground, nothing live runs —
  but real, not latent. Left broken on purpose rather than papered over with
  a fix session 2 would have had to unpick.
- **The sharpest-risk call was right and is now concrete.**
  `group_product.py:433` and `critic_pass.py:446` delete `product_images` by
  `group_product_id`; under one product per candidate, 5x7's render wipes
  primary's reviewed gallery. Seven readers use that key. **Owner decision:
  `group_id` scopes, the FK stays** — making `group_product_id` nullable
  would force a SQLite table rebuild and break the additive-migration
  guarantee the rollback story rests on.
- **`group_products` is now a misnomer** — it is the candidate's *listing
  record*, with `gelato_product_id` as one nullable column. Renaming it was
  considered and rejected (repo-wide diff on top of the riskiest change);
  SPEC v4.12 says so in words instead.
- **A `patch_etsy_listing` question answered by reading, not testing.** The
  upload loop is a **full re-upload, no delta, no dedup**. Under `[D1]` it
  runs once, so the append-across-reviews worry dissolves — and is replaced
  by a retry-safety one: a second call duplicates the whole gallery.
- **The incident, and the rule it produced.** A subagent ran `git stash` to
  "compare against a clean checkout" and **wiped the working tree** — its
  own work, the parallel agent's, and the owner's in-flight edits.
  Recovered in full from `stash@{0}`/`stash@{1}`. **The file allowlist did
  not prevent it, because the destructive command took no file arguments.**
  Standing rule, now in session 2's kickoff §4: **subagent briefs carry a
  command denylist as well as a file allowlist** — no `git stash`, `reset
  --hard`, `checkout -- .`, `clean`, `rebase`, history rewrite, bulk delete,
  or live-mode env var. Reading git state stays unrestricted; reading was
  never the problem.

**Session R — GL-22 session 1 built (Claude Code, 2026-08-01).**

Three commits on `docs/gl22a-research-and-prd`: `6df9ba5` (etsy_client),
`ed660c1` (schema), `b0560df` (create path). 617/617 green, zero live calls.

- **The sizes-changed branch and the shared-product rule do collide, and the
  collision has a name now.** The kickoff anticipated it in principle
  ("do not extend it to delete a product that other groups' variants already
  depend on") without stating what to do instead. Resolved by guarding the
  delete: it still fires for the case that actually triggers it today
  (`primary_mockup`'s 8x12-only row expanding to the 4-size fan-out on
  approval, all variants belonging to the calling group) and raises
  `SharedProductVariantError` the moment another group's variants are on the
  product. **Consequence session 2 inherits:** with the reuse key on
  `candidate_id`, `group_mockup.create_group_mockup` for 5x7/10x24 now resolves
  the candidate's *primary* product, mismatches on sizes, and hits that guard —
  the secondary path is intentionally broken between session 1 and session 2.
  It is dry-run-only ground and no live path runs until session 2 lands, but it
  is a real behaviour change and not a latent one. Failing loud beat the two
  alternatives (delete a shared product, or silently hand the 5x7 group a
  product with none of its sizes on it).
- **A pre-migration row needs an explicit fallback, not just a NULL gate.**
  `candidate_id IS NOT NULL` distinguishes new rows from old, but a
  candidate-keyed lookup that simply *misses* a GL-9 row would create a second
  Gelato product for candidate 39 — whose id-10 row is a real published Etsy
  listing (`4542159277`). `_find_product_row` resolves new-shape rows by
  `candidate_id` and pre-migration rows by their original `group_id`, new shape
  winning the tie. Migration verified against a copy of the live DB: idempotent
  on the second run, all five GL-9 rows unchanged with `candidate_id` NULL.
- **Per-variant image resolution landed as specified** (GL-22a Q1): one
  `create-from-template` call, the 5x7 variant carrying the 5x7 cover-crop
  while the 8x12 variant carries the master. Crops are still built once per
  distinct `group_type` — `persist_group_crop`'s R2 PUT is an unconditional
  overwrite, so per-size would have meant duplicate network writes.
- **The gallery `group_type` now comes from the `groups` row, not `sizes[0]`.**
  Those were the same thing while a product belonged to one group. They stop
  being the same thing the moment it doesn't.
- **A subagent ran `git stash` to compare against a clean checkout and wiped
  the working tree** — its own work, the other subagent's, the main thread's
  in-flight edits, and the owner's uncommitted doc changes. Fully recovered
  from `stash@{0}`/`stash@{1}` (both still in the stash list, redundant now).
  The brief said which files an agent may *touch*; it did not say which
  commands it may *run*. Next brief adds: no `git stash`/`reset`/`checkout` —
  a subagent shares the tree with everything else in the session, and "get a
  clean checkout to compare against" needs a worktree, not the shared tree.
- **One thing added beyond the kickoff:** `tests/test_migrate_group_products_
  candidate_id.py`. Every other migration in this repo has a test file; a
  migration without one breaks the pattern reviewers read by.
- **Still open for session 2, unchanged:** whether `patch_etsy_listing`'s
  image upload loop is a full re-upload or a delta. Not touched here.
  `product_images.group_id` exists and is populated, so the scoped rebuild has
  what it needs. The unscoped `DELETE FROM product_images` is deliberately
  left as-is — scoping it is session 2's whole point.
- **CLAUDE.md's three wrong constraints stay wrong,** per §4 of the kickoff. No
  fourth was found.

**Session S — GL-22 session 2 built (Claude Code, 2026-08-01).**

One commit on `docs/gl22a-research-and-prd`: `360a5d9`. 635/635 green, zero
live calls. **Shipped as one PR, not the §6 two-PR split** — §2 D and E turned
out not to touch files disjoint from A once traced (D's "one call site" *is*
`patch_etsy_listing`, E's gate clause lives beside `publish_candidate`), so
splitting would have meant merging D/E through the same files twice.

- **The weld came out cleanly; the secondary path is un-broken.** Split into
  `render_group_mockups` (no Gelato call, every write scoped `AND group_id = ?`)
  and `create_candidate_gelato_product` (the single create at publish, per-
  variant `fileUrl`). `group_mockup` for 5x7/10x24 no longer resolves the
  candidate's primary product and no longer hits `SharedProductVariantError`.
- **There was a second silent wipe, and it was not in the impact map.**
  `artwork_store.persist_mockup_render` was keyed `group_product_id + index`,
  so under a candidate-keyed record the 5x7 group's scene 0 overwrote the
  primary group's scene 0 **file on disk** — under the seven DB call sites the
  impact map did name. `group_id` added to the key. Worth carrying: the map
  traced SQL and stopped there; the filesystem key was the same bug in a
  different store.
- **`cleanup.reclaim_stranded_pending_group_products` would have deleted every
  live listing record.** It sweeps `pending` rows with no `gelato_product_id`
  older than 10 minutes — which under v4.12 is the *normal* state of a
  candidate's listing record for the entire review window, days long. Now also
  requires no variants and no images, which is still exactly the crashed-
  before-anything-happened row it was written for. This one was found by
  reading the stage, not by a failing test; nothing in the suite covered a
  pending row surviving a cleanup pass.
- **Three deviations from the kickoff, flagged rather than taken silently.**
  (1) The orphan-delete-before-retry branch is **deleted, not moved** — under
  create-once no stale product can exist, so its trigger is unreachable; the
  idempotency it protected is covered by "never create twice when
  `gelato_product_id` is set". Related pre-existing gap left open: a crash
  between the Gelato POST and the `UPDATE` that records the id still orphans a
  product no DB-driven sweep can see. (2) `migrate_v412_gallery.py` **rebuilds
  `groups`** — SQLite cannot widen a CHECK in place. Rows copied verbatim, the
  constraint only widens, but it is not the additive shape session 1 protected.
  (3) `render_group_mockups` gained a guard the kickoff did not ask for: a
  group arriving with sizes *after* the product exists fails loud, because Q2
  proved a variant cannot be added afterwards.
- **`discard_superseded_attempt` ended up deleting less than specified.** The
  kickoff said scope its deletes to the group; it now deletes only that group's
  `product_images` and leaves its variant rows alone. The sizes don't change
  between attempts — only the artwork does — and dropping the variant rows was
  what tripped the new post-create guard on a re-render. Excluded groups' sizes
  are pruned later, at create time, where the product's real variant set is
  known.
- **The digest/mockup/critic diff was bigger than the impact map implied.**
  Ten queries repointed across `digest`, `group_digest`, `critic_pass`,
  `group_critic_pass`, `compliance_draft`, `publish_group`, `group_mockup`,
  `primary_mockup`. The common cause is one thing, not ten: every stage looked
  up its row as `group_products WHERE group_id = ? AND status = 'created'`, and
  under v4.12 **both halves of that are wrong** — the row is the candidate's,
  and it sits at `pending` for the whole review window. `group_product.
  live_product_row()` is now the single resolver they all call.
- **`group_mockup`'s cycle trigger had to move from status to decision.** It
  keyed on the primary group reaching `approved_published`, which under [D1]
  never arrives until *after* the secondary groups have been reviewed. Left
  alone it would have deadlocked the whole flow. Now keys on `decision =
  'approved'`.
- **`primary_mockup` now records the full primary size set at render time**
  (8x12/A3/A2/A1, not 8x12-only). Under v4.11 the row grew to four sizes on
  approval by deleting and recreating the Gelato product; with no product at
  render time the fan-out is just the variant rows, so recording them up front
  removes the sizes-changed branch's last trigger *and* makes the primary
  digest's price line honest about what the listing will offer. Digest tests
  updated accordingly — that is a behaviour change, not just fixture churn.
- **A fourth wrong CLAUDE.md constraint, flagged not edited** (per §5): the
  `Data storage is SQLite` bullet still reads "under v4.11 each group has ONE
  Gelato product + ONE Etsy listing". That is now false. The three rewrites the
  PRD drafted were applied verbatim; this one is left for the owner because the
  kickoff said to flag rather than edit.
- **Both subagents died mid-edit on the session limit** (`resets 6pm
  Europe/Brussels`), leaving four test files partially converted. The main
  thread finished them. Nothing destructive ran — the command denylist held,
  and the one agent that wanted a clean checkout did not try to get one. Worth
  keeping: the surviving partial work was *useful*, including one agent leaving
  a `KNOWN PRODUCTION BUG` note on a test that correctly caught
  `run_group_mockup_cycle` still reading `result["gelato_product_id"]`.
- **What GL-13 inherits, explicitly.** Nothing below was proven offline:
  one listing carrying 4/5/6 variants across its lifecycle with no duplicate
  product; a gallery that grew across two reviews, checked against the real
  Etsy listing rather than the DB; a rejected secondary group that deleted
  nothing, `GET`-verified before and after; the `listing_image_id` shape the
  idempotent re-patch depends on (currently only exercised against a stub); the
  20-image cap against a real Etsy rejection; and the stall rule, which cannot
  fire at all until GL-7 runs the gate on a cadence.
- **Both approved destructive actions done.** The two GL-22a research drafts
  are deleted — `4547726856` and `4547717123`, both `state: draft` on the
  `GET` before, both `404` on the `GET` after (`delete_gl22a_research_drafts.py`,
  kept as the hand-run record). First real use of session 1's `delete_listing`.
  **The pre-delete guard fired first, and was right to:** the findings-doc
  ledger records both as still titled `GL-22a Q1 research probe - DELETE ME`,
  but the live `GET` returned `GL22A-PATCH-MARKER Dense Wildflower Meadow
  Print` and `GL22A-Q3-CLEAN-PATCH-MARKER Wildflower Print`. That is the
  ledger being stale, not the wrong listings — Q3's `update_listing` test
  renamed them after the ledger's last read, and the findings doc records the
  second of those titles on `4547717123` itself as "our patch". Guard relaxed
  to the `GL22A-` marker prefix (narrow enough that nothing but this research
  session could have written it) with that reasoning in the script, then
  re-run. Worth carrying: a "confirm via GET before deleting" step is only
  useful if a mismatch actually stops you, and this one did.
  `stash@{0}`/`stash@{1}` dropped (`5f6d1c1`, `39f8300` — SHAs recorded before
  dropping, so both stay reachable via reflog); `stash@{2}`
  (`125331f`, feat/gl21-matte-compositor) untouched, as instructed.
