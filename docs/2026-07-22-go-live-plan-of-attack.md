# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

> **Last updated 2026-08-09 (late) — GL-38 DONE (`master` = `80ce9fd`, pushed,
> 709 green, PR #7 merged, one DB, one tree — full account in its row, which
> is more accurate than the kickoff that preceded it). Gate: sixteen of
> twenty-two.** Two defects filed out of it → **GL-50** (`migrate.py --check`
> opens an empty database named `--check` and raises a false stale-schema
> alarm) and **GL-51** (the near-miss: 289 git-ignored artefacts existing
> nowhere else, and 24 rows holding absolute paths into a directory that was
> about to be deleted).
>
> **⭐ The item that reorders the board came from the owner's manual check, not
> from the merge: the Gelato portrait template was defective and has been
> fixed at source.** It carried **one** image placeholder shared by all six
> size variants; it now carries **three** — separate images for the primary,
> 5x7 and 10x24 variants.
>
> **This is strong corroboration of GL-48's leading hypothesis, and it
> partially un-strikes GL-22d.** GL-22a Q1 retired GL-22d on the finding that
> a shared `image_placeholder_name` does not force a shared *image*. Q1 was
> correct and was answering the wrong question: a shared placeholder does not
> force a shared image, but it does force a shared **fit** — and at 10x24
> (0.4167 against a placeholder authored for a 0.684 photograph) that fit *is*
> the white-bar defect. Worth recording as a reasoning failure rather than a
> fact update: **Q1's experiment compared 8x12 to 5x7, two ratios within ~4 %
> of each other, and was therefore structurally incapable of detecting a
> fit-versus-fill difference.** A probe that cannot fail in the interesting
> direction is not evidence, and this one closed a plan item for eight days.
>
> **The operational consequence is why GL-48 now goes first, ahead of GL-45:
> `config/static_config.json` is stale as of this change.** All twelve entries
> still name the two old placeholders, so the live config no longer describes
> the live template, and **the next `create-from-template` call would be made
> against placeholder names that may no longer exist.** Nothing is running —
> the three tasks are Disabled — so this is contained rather than urgent, but
> it is a **half-applied fix, which is the worst state to leave a live
> integration in**, and it gates GL-45's test run: `run_hourly.py` reaches the
> publish gate, and the publish gate reaches Gelato. Sequencing and brief:
> **Part 3 Track E (revised)** and
> `docs/2026-08-09-gl48-crop-and-template-brief.md`.
>
> **One thing not to lose in the good news: the template fix does not prove
> the pipeline half is correct.** It explains the defect; it does not
> establish that we were sending the right file. The one read-only `GET` in
> GL-48 §3 still discriminates one bug from two, and it is cheaper to run it
> now than to discover a second bug after the config change makes the first
> one invisible.

> **Last updated 2026-08-09 — the soak is PAUSED, not passed, and it ended
> with seven findings instead of a verdict. Gate: fifteen of twenty-two.**
> Findings: `docs/2026-08-08-gl7-soak-findings.md` — *currently only in the
> GL-7 worktree, so it travels with GL-38's merge or it is lost, exactly like
> GL-37's findings.* **Four of the seven become blocker rows** — **GL-45**
> (Telegram button taps silently dropped), **GL-46** (per-candidate `generate`
> failures swallowed, now systemic), **GL-47** (event-lookahead niches have no
> "too early" gate and no dedup), **GL-48** (the 10x24 print still arrives at
> Gelato letterboxed) — **and one becomes housekeeping**, **GL-49** (three
> candidates frozen as dry-run stubs by the live-mode flip).
>
> **Owner decision 2026-08-09: stop the soak rather than extend it, and this
> is a pass/fail statement about the *method*, not about GL-7's code.** The
> soak did its job — seven findings in two nights is a good yield — but the
> yield curve has inverted: items 3/6 now fire on *every* candidate in a batch
> (8 of 8 on 08-09), and item 7 means the candidates being burned are
> premature seasonal content nobody would have published anyway. With live
> mode armed, each further night spends real Replicate and Anthropic money to
> re-observe defects that are already characterised. **Continuing would buy
> repetition, not information.**
>
> **The honest re-read of the gate this forces.** Since 2026-08-08 this
> document has said "the code is done and we are waiting." That was true of
> the *build* and is no longer a fair summary of the *state*: four real
> defects are open, two of them (GL-45, GL-48) touch decision integrity and
> what a buyer actually receives, and both were invisible to every check that
> preceded them. The corrected statement is: **the build is done, the
> operation is not proven, and four sessions stand between here and a shop
> that can be left alone.** None of the four is large — the largest is a day —
> but none is optional either.
>
> **Two structural lessons, worth more than the four rows.** **(1) The soak
> could not have caught GL-48, by construction.** `group_product._image_url_for`
> gates the print-crop URL on `config.is_live_mode("GELATO")` and otherwise
> falls back to the uncropped master, so **the crop path does not execute in a
> dry run at all** — night 1 was structurally blind to the exact field under
> suspicion. A dry-run mode that takes a *different branch* from live is not a
> rehearsal, it is a different program; the gate belongs on whether the URL is
> fetchable (`config.is_r2_configured()`), not on live mode. **(2) Three of
> the seven findings are the same failure — an exception caught and
> discarded.** GL-46 is the explicit case; GL-45 is the suspected one; the
> `generate`-stuck-`pending` state is indistinguishable from "has not run yet"
> for the same reason. **GL-7's per-stage isolation was built to stop one
> stage's crash killing a run; the residual risk it created is that a failure
> inside a stage's own per-item loop is now invisible at both levels.** Worth
> a standing convention, not four separate fixes: a swallowed per-item
> exception must always leave a state change behind.
>
> **On the merge (GL-38): the pause makes it cleanly available and it should
> go first, before any of GL-45 – GL-48 is written.** The soak was the only
> reason the worktree had to stay live; with it stopped, the "do not run
> anything from the main checkout" rule can be retired instead of endured, and
> the four fix sessions can be branched off master like normal work. Doing the
> fixes on the worktree first would make this the *fifth* occurrence of the
> merge pattern (GL-1, GL-23, GL-23b, GL-38) and would pile four more commits
> onto a branch already carrying GL-30, GL-35, GL-36 and GL-37's findings.
> **The full sequence is in Part 3, Track E.**

> **Last updated 2026-08-08 (evening) — the storefront is finished. GL-10d
> shipped and its banner upload closed the last item on GL-10b's checklist,
> so GL-10 and GL-10d ticked together; GL-39 was belatedly marked done (it
> has been a live scheduled task since 08-06). Gate: fourteen of eighteen.
> **GL-30 is also done** — it ran as a parallel code session inside the GL-7
> worktree and was already committed there (`34a8b15`) before this document
> caught up: 443 files, 381.5 MB, all uploaded. Gate: **fifteen of eighteen.**
> The three that remain are the soak, GL-38's merge (which carries GL-30 onto
> master) and GL-11 — **none of them is a build, and two are on someone else's
> clock.** GL-43 applied and committed the same evening.**
>
> Earlier 2026-08-08 — **GL-10b IS DONE, and it turned the storefront
> from "owner-driven, unspecified" into paste-ready copy plus one small
> coding session.** Five artefacts, from an n=10 competitor sweep (458,802
> combined sales, every shop reached by ranking rather than by looking good):
> `docs/2026-08-07-gl10b-findings.md` (15 rules), `-storefront-checklist.md`
> (paste-ready, owner executes), `-listing-copy-spec.md` (spec only, build is
> GL-10c), `-banner-icon-decision.md` (D-A resolved, phase-7 handoff),
> `-keyword-delta.md` (**proposed, not applied**).
>
> **Three decisions were ratified by the owner 2026-08-07:** **D-A = A1**,
> Qrchard's system to the letter — reached because register does **not**
> correlate with sales in the sample (calm and shouty interleave across
> sales/listing), which §2.4 had pre-committed to resolving as A1;
> **retire the live banner/icon pair, keep GL-10a's icon unchanged, adjust
> GL-10a's banner**; and **Nano Banana Pro = role C**, concept exploration
> only, nothing generated ships.
>
> **What actually changes on this board, in order of consequence:**
> **(1) GL-10 splits.** The owner-manual half (tagline, section rename,
> About, policies) is paste-ready today and gated on nothing. The build half
> is new: **GL-10d**, the banner rebuild — 1600 × 400, no alpha, < 1 MB, a
> band of composited mockup renders, and `verify.py` gaining assertions
> rather than losing them. **It joins the go-live gate** (owner, 2026-08-08),
> because the live banner fails on four *structural* counts — it advertises
> framed figurative portraits the pipeline does not make, carries a visible
> garbled-text generation artifact, is 1,497.5 KB against Etsy's 1 MB
> warning, and is 1600 × 896, which matches no documented Etsy format.
> **(2) A sixth copy surface exists that the brief never listed** — the
> 55-character shop tagline, indexed, free, and currently empty (R12).
> **(3) One live-input file is now known to be wrong:** `moon phase print` is
> in `safe_evergreen_bucket.md` and its SERP is owned by dated 2026/2027
> calendars — evergreen as a *term*, seasonal as a *market*. The bucket was
> validated on terms and never against who ranks for them. **Nothing is
> applied**; the whole delta is one owner decision → **GL-43**.
> **(4) Three findings had no home and now have rows:** set/bundle products
> (**GL-40**, the one mechanism every high-volume shop in the sample uses to
> raise order value, and QhotoArt has no path to it), the permanently frozen
> listing URL slug that Gelato's title dictates (**GL-41**), and the About
> section's unused 5-images-and-a-video trust surface (**GL-42**).
>
> **Two limits travel with every conclusion above, and should not be dropped
> in the retelling.** Etsy no longer exposes listing **tags** to buyers
> anywhere, so the keyword work is built from *title tokens*, not from
> competitors' tag lists — a weaker instrument than the brief assumed. And
> the register-vs-sales null result rests on two confounded outliers
> (galerie61 sells public-domain Picasso; OriginalLunarPhase sells one dated
> product with 13 years of reviews), so it supports only the weaker,
> sufficient claim: **restraint is not a handicap.** The sweep's own
> verification pass found and fixed **six errors in its own drafts**,
> including a proposed `verify.py` assertion that already existed — listed
> in the findings rather than quietly corrected.
>
> **What GL-10b explicitly did not touch:** no pipeline code, no live shop
> write (every Etsy interaction was a `GET`, signed out throughout), no hard
> constraint. R15 — that 8/10 shops lead with a framed in-room first image,
> and that scene *consistency* beats scene variety — is **routed to
> GL-6/GL-21 as a scene-authoring note**, not built here.
>
> **Previously, 2026-08-06 — GL-7 IS BUILT and the two-night soak is
> RUNNING. Night 1 is dry-run and ticking: heartbeats at 10:13 (hourly, ok)
> and 10:07 (batch, ok) local, `ETSY_LIVE_MODE`/`GELATO_LIVE_MODE` both
> `FALSE`.** 15 commits on `worktree-gl7-cron-orchestrator`, ~3.4k lines,
> eight new test files. **Everything the PRD asked for exists:**
> `run_hourly.py` and `run_batch.py` (all 12 stages sequenced, per-stage
> isolation, no stage logic moved into the runner); **GL-35** — a
> `schema_version` table and an ordered idempotent `migrate.py` with a
> read-only `--check` fail-fast wired into both entrypoints; **GL-36** —
> `pipeline/reconcile.py` (age-out + Etsy-404 drift) plus a
> `listing_missing` status; a crash-safe single-instance lock with
> Windows-correct PID liveness and a bounded stale-lock reclaim; a
> `heartbeats` table so a run that never happened is detectable; Telegram
> surfacing on the missing-env and stale-schema paths; and the
> **stall-predicate proof driven through `run_batch.main`**, not just the
> unit. Plan: `docs/superpowers/plans/2026-08-05-gl7-cron-orchestrator.md`.
> **The build closed the PRD's §2 items 1–7 and 9. Item 8 — the soak — is
> what is happening now, and it is the gate.**
> **⚠️ NEW BLOCKER, filed the same day → GL-38: none of this is on master,
> and the soak is running out of an agent worktree.** `master` is still at
> `14a2d10`; `run_batch.py` does not exist there. The soak therefore runs
> from `.claude/worktrees/gl7-cron-orchestrator`, which carries **its own
> `db/qhoto.sqlite3`** (450 KB, migrated to `schema_version` 7, actively
> written) while the canonical `db/qhoto.sqlite3` at the repo root sits at
> 434 KB, **untouched since 2026-08-04 and with no `schema_version` table
> at all**. Two live states, one bot token. **This is the fourth occurrence
> of the merge pattern** (GL-1, GL-23, GL-23b, now this) and the first one
> where it is not merely a delay — see the GL-38 row for the Telegram
> single-consumer hazard, which the new lock does *not* protect against
> because the lock is per-tree.
> **Nothing about this invalidates the soak** — it is testing scheduling,
> the lock, the schema guard and the heartbeats, and it is testing them
> honestly. **Owner decision 2026-08-06: the soak finishes on the worktree
> as-is, and the merge follows it** — restarting a running soak to fix its
> provenance would spend the only resource here that is actually scarce.
> The consequence, carried in the GL-38 row: a five-step post-soak sequence
> (merge → reconcile the two DBs → re-point the scheduled tasks → verify by
> heartbeat → retire the worktree), and **the soak's result stays
> provisional until it is done** — a pass on the branch is evidence about
> the code, not about the deployment.
> **✅ GL-37 ANSWERED 2026-08-06 — and the answer has a sting the question
> did not.** Neither Creativity Standards field is settable through the v3
> API: proven by a **full raw response dump** of two live listings (not a
> field-name grep — the method that makes this immune to GL-34's
> read-side/write-side trap, since there is no read-side field at all), by
> enumerating all 15 taxonomy properties for `taxonomy_id` 1027, and by a
> `GET /shops/{id}` that shows **no shop-level default either**. Etsy's own
> dev channel carries an **open, unactioned feature request for exactly
> these two fields (Discussion #1630, 2026-06-22)** — which is proof the
> field does not exist, not a hint that it might.
> **The sting: the only place to set them is the web listing editor, and the
> editor's sole save action is "Activate with changes" — there is no
> draft-save.** So the disclosure tick *is* an activation. **That collides
> with GL-29** rather than merely gating it: a human visit takes the listing
> live, so GL-29's programmatic activation never gets to be the thing that
> activates a properly-disclosed listing, and its remaining value is
> "activate at scale with the two fields left blank" — a merchandising and
> compliance choice, not a technical one. Flagged in the GL-29 row rather
> than quietly re-scoped (CLAUDE.md §3); **an owner decision is now needed
> on *whether*, not *when*.**
> **Decision recorded: accept the manual per-listing step**, exactly as
> listing activation already is, and file the re-check as a standing
> quarterly item → **GL-39**, tracking Discussion #1630. **The quarterly
> check is now a live Cowork scheduled task** (`gl39-etsy-creativity-
> standards-api-check`, first run 1 Nov 2026, then Feb/May/Aug/Nov).
> **Three owner decisions followed the same day, and together they make one
> coherent position rather than three patches:** (1) **the prose disclosure
> is gone from listing descriptions** — `compliance_draft.DISCLOSURE_TEXT`
> is now `""` and the draft prompt actively forbids the model reintroducing
> one; both facts it carried are disclosed structurally instead (the AI tick
> by hand, the production partner by the patch); (2) **the owner is the
> publish gatekeeper** — he ticks "an AI generator" and publishes in a
> single editor save; (3) **GL-29 is cancelled** and struck from the
> go-live gate, parked as GL-29b. **The dependency runs in that order and
> is worth stating: (1) is only safe because of (2), and (2) is only stable
> because of (3).** Automating activation later without restoring a
> disclosure would produce a live listing carrying neither — which is why
> the reasoning sits in a code comment on the removed constant, not only
> here. **This is the one
> remaining hole in GL-7's unattended premise, and it is now a known,
> bounded, tracked hole rather than an open question.**
> Findings: `docs/2026-08-06-gl37-findings.md` — **which currently exists
> only in the GL-7 worktree and must travel with GL-38's merge.**
>
> **Owner-manual items are now the parallel track, and the first one is
> done: ✅ the GL-11 email went out 2026-08-06** (draft:
> `docs/2026-08-06-gl11-developer-mode-email-draft.md`). That was the last
> item on the board waiting on an external party — **everything remaining is
> work done here.** Still parallel-able beside the soak: GL-37's API
> re-check, GL-10 storefront. Candidate 42's draft listing stays alive until
> after the soak's live night — it is GL-36's negative control.
>
> **Previously, 2026-08-05 — GL-33 SHIPPED and GL-34 CLOSED. Both
> blockers off the board; master carries them (`14a2d10`, PR #6).**
> **GL-33** — `patch_etsy_listing` now reconciles the gallery: a new
> `get_listing_images`/`delete_listing_image` pair in `etsy_client` (both
> dry-run-aware), and a delete pass that removes every listing image not
> **positively matched** to the candidate's own `product_images`
> (`etsy_listing_image_id`, scoped by `group_product_id`). Positive-match-only
> is the correct polarity and was chosen deliberately: a "delete anything that
> looks like Gelato's" heuristic would eventually eat a real composite. The
> delete runs *after* the upload loop and *before* `update_listing`, so the
> listing is never briefly imageless. 7 new tests (4 client, 3 patch-step,
> idempotency covered). **Proven live** on candidate 42's real listing
> (`4549960823`): 19 images → 13, the 6 Gelato ghosts gone, a second patch
> changed nothing, variant mapping and per-variant pricing intact.
> **GL-34 — closed with no code change, and it was never a defect.** The
> write field is `production_partner_ids` (list of ints); the read field is
> `production_partners` (list of objects). GL-13's check read the *write*
> name off a *read* response, which returns "missing" on every listing
> forever, regardless of state. GL-9's control listing (`4542159277`) shows
> `who_made: i_did` **and** the partner, live. Written up in
> `docs/2026-08-04-gl34-findings.md`. **That is the third finding in this
> project traceable to reading an API echo as ground truth** — after GL-22a's
> confounded Q3 and GL-34's own original filing. It is now a named failure
> mode; the dashboard or a fresh `GET` is the ground truth, the response echo
> is not.
> **Found and flagged rather than worked around:** GL-13's R3/R5 listings were
> already deleted live with the DB rows left `published`, so the planned
> control was unreadable and a fresh candidate (42) was substituted with owner
> sign-off. **That drift is now folded into GL-36** (owner, 2026-08-05) —
> one "DB vs live state" item covering both stranded `generating` rows and
> terminal rows pointing at dead external ids.
> **Three things left open for the owner, all owner-only:** candidate 42's
> draft listing `4549960823` is live and unactivated (delete when ready);
> `.env`'s `*_LIVE_MODE` flags were already true before the session and were
> left as-is (Claude cannot touch `.env`) — **anything hand-run now hits the
> real APIs by default**; and candidates 40/41's rows still claim `published`
> against dead ids.
> **What this unblocks: GL-29.** Its two gates were GL-33 and GL-34; both are
> satisfied. **Owner sequencing 2026-08-05: GL-7 goes next anyway** — see
> Part 3 step 8d for the reasoning. **GL-7 is now the only expensive item
> between here and go-live.**
>
> **Previously, 2026-08-03 (late) — GL-13/GL-17 PASSED. R0–R5 all green,
> 635/635 throughout, and it is on master (`a2aff96`, PR #5).**
> The v4.12 publish path is now proven live: one listing, created exactly
> once, the validated sizes as variants, the gallery assembled once, a
> rejected group that deleted nothing, and the Reject button tapped for the
> first time since GL-9. **Four real defects were found and fixed in-flight**
> (see Session T in Part 4): an unmigrated DB, a seed check that permanently
> blocked fresh candidates, a `max_tokens` truncation on a 10-image gallery,
> and Telegram's server-side fetch failing on R2 URLs.
> **Two gaps were filed rather than fixed, per owner direction — and both are
> now go-live blockers, not housekeeping:** **GL-33**, Gelato's own
> auto-push leaves 5–6 untracked preview images in the listing gallery
> alongside our composites (the self-hosted-gallery contract is the reason
> the entire GL-6/GL-21 mockup track exists); and **GL-34**, `who_made: i_did`
> appearing to drop `production_partner_ids` on the patch.
> **GL-34 corrected 2026-08-04 — owner produced a dashboard screenshot from
> the GL-9 (v4.11) round showing `Who made it? = I did` **and** `Production
> partners: Gelato, Brussels — appears on listing as "A print shop"` on the
> same live listing.** The two are **not** mutually exclusive, `CLAUDE.md`'s
> "verified" line stands, and there is no policy exposure and no
> disclosure-strategy decision to take. What survives is narrower and still
> real: something in the v4.12 patch path either drops the field or only
> appears to, and **GL-9's listing is a known-good control** for diagnosing
> which. GL-33 remains blocker-class and unchanged.
> **A different gap surfaced from the same screenshot → GL-37:** two Etsy
> *Creativity Standards* fields — "How does your shop produce this item?" and
> "What tools are used to make this item?" (which is where **"An AI
> generator"** lives) — are **blank on every listing** and were never
> settable through the API. That is the AI disclosure Etsy actually reads,
> and it is a **manual dashboard step per listing**, which is a direct
> problem for GL-7's unattended premise.
> **What GL-13's pass unlocks: the GL-11 email.** Its gate was "GL-13
> passes" and that gate is now satisfied. From here GL-11 is the only
> critical-path item on a clock the owner does not control — every day it is
> not sent is a day of external lead time spent for nothing.
>
> **Previously, 2026-08-02 (late) — GL-22 is BUILT. 635/635 green.**
> Session 2 shipped as one PR, not two: `D` and `E` turned out not to be
> disjoint from `A` once traced (D's "one call site" *is* `patch_etsy_
> listing`). SPEC v4.12 written, three CLAUDE.md constraints rewritten, a
> fourth flagged and now fixed. Both approved deletions done.
> ~~The single most important fact right now: none of it is on master.~~
> **✅ Resolved — GL-23b merged 2026-08-02 (`7cbaee7`), and PR #5 (`a2aff96`)
> landed GL-13's live fixes on top. Master is current.**
> **Session 2 found three things no impact map caught** (a second silent
> wipe on the *filesystem* key, a reclaim sweep that would have deleted
> every live listing record, and a cycle trigger that deadlocked under
> `[D1]`) — all three by *reading stages*, not by running tests. See
> Session S. **GL-13's delta grew accordingly.**
>
> **2026-08-02 — GL-22 session 1 ✅ landed, session 2 kicked
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
attempt 3 / scene library, portrait ✅ · GL-8 host research ✅ · GL-3 host
decision signed off, local desktop + pre-committed VPS fork ✅.

### Go-live blockers

| ID | Type | Item | Input → Output |
|---|---|---|---|
| GL-23 | C | **✅ DONE 2026-08-01** — merged; master carries the wired 10 + 1 + 2 gallery. Original scope: **merge `feat/gl6-p4-scene-library` → master.** 36 commits: chroma model, intake harness, the harvest, 11 landed bundles, the five accepted scenes, 5x7/10x24 wiring, `edge-alpha-jitter` (gate is 9 detectors), `gate_waivers`. 597+ tests green on the branch. The runtime deploys from master; nothing below is real until this lands. **Cheapest item on the critical path — do it first.** | branch → PR → master |
| GL-19b | T | **✅ DONE 2026-08-01** — 13/13 rendered, deterministic, size-checked, owner-reviewed and approved (`93914b2` pre-crops the master to each group's print ratio in the harness). Gallery is clear for the guarded live upload. Original scope: **re-run the M1 render harness against the *wired* gallery.** `scripts/gl19_m1_render.py` last ran against 4 bundles, 3 of which are now rejected. The shipping gallery is 10 primary + 1 5x7 + 2 10x24 and has never been rendered end-to-end as a set. Offline render + owner eyeball, then one guarded live upload. | harness run → contact sheet → owner sign-off |
| GL-23b | C | **✅ DONE 2026-08-02 — merged as PR #4 (`7cbaee7`); master carries v4.12. Row reconciled 2026-08-05: it landed the day it was filed but was only ever marked done in the header prose, never in this table — three subsequent revisions read past it.** *(Two riders worth keeping with the row: the non-additive `groups` rebuild in `migrate_v412_gallery.py` was supposed to run as part of this merge and **did not** — nothing in the repo runs migrations at all, which is what GL-13's R0 walked into → **GL-35**. And PR #5 (`a2aff96`) landed GL-13's live fixes on top the following day.)* Original scope: **merge `docs/gl22a-research-and-prd` → master (NEW 2026-08-02).** 9 commits: GL-22a's findings + PRD, both build sessions, SPEC v4.12, the CLAUDE.md rewrites, the destructive-action log. 635/635 green on the branch. **The runtime deploys from master; nothing in v4.12 is real until this lands, and GL-13 cannot start against a branch.** Exactly the GL-1/GL-23 pattern, third time. **Cheapest item on the critical path — do it first.** | branch → PR → master |
| GL-22 | C | **✅ DONE 2026-08-02 — one Etsy listing per artwork (v4.12), 635/635 green.** Session 1 (`6df9ba5` `ed660c1` `b0560df` `4c878b3`): `etsy_client` fixes, additive schema, candidate-keyed create path. Session 2 (`360a5d9` `b9b69a6` `3c525c0`): the render/Gelato **weld cut**, gallery scoped by `group_id`, `GalleryTooLargeError` at the 20-cap, `patch_etsy_listing` made idempotent via `product_images.etsy_listing_image_id`, reject/abandon deleting nothing, shipping collapsed to `288734253315`, the stall predicate, SPEC v4.12 and three CLAUDE.md rewrites. **Three deviations, stated not smuggled:** the orphan-delete branch was *removed* rather than moved (unreachable under create-once — but a pre-existing gap survives, see GL-32); `migrate_v412_gallery.py` **rebuilds `groups`** because SQLite cannot widen a CHECK in place (the first non-additive migration in this plan — the rollback story in the PRD needs reading with that in mind); and `discard_superseded_attempt` deletes less than specified (images only — dropping variant rows tripped the new post-create guard on re-render). | ✅ merged into GL-23b | Six sizes as variants of one Gelato product / one Etsy listing; gallery = primary mockups + 5x7 mockups if that crop passed + 10x24 mockups if that one passed. PRD: `docs/2026-08-01-v412-single-listing-prd.md`. **Now a two-session build. Session 1** (`docs/2026-08-01-gl22-session1-kickoff.md`): the two `etsy_client` fixes (`update_listing_inventory`'s float-price bug + a new `delete_listing`, which needs a **manual `listings_d` re-auth**), the additive schema migration (`group_products.candidate_id`, `group_product_variants.group_id`, `product_images.group_id`), and the candidate-keyed `create_or_reuse_group_product` with per-group `fileUrl` per variant in one create call. **Session 2:** gallery assembly across groups with a ≤20-image assert and scoped clear/rebuild (the sharpest correctness risk — one group's rebuild must not wipe another's images), abandon/reject/cleanup stopping the shared-product delete, the shipping-profile collapse to one value, the **new stall-sweep stage** (`[D2]`, see GL-22c), the digest/mockup/critic pass, `run_m1_live_test.py` + tests, **SPEC v4.12**, and **three CLAUDE.md rewrites + one addition**. | ✅ PRD → session 1 PR → session 2 PR |
| GL-22a | R | **✅ DONE 2026-08-01** — findings: `docs/2026-08-01-gl22a-findings.md`. Four measured answers against the live API, two throwaway Gelato products created and deleted per the ledger. **(1) A shared `image_placeholder_name` does NOT force a shared image** — two variants carry independently-submitted `fileUrl`s in one `create-from-template` call → **GL-22d struck**. **(2) No API path adds a variant to an existing store product** — `PUT` silently drops the added variant *and* severs the Etsy sync, `PATCH` is 405, `/variants` is an incompatible custom-priced flow, and a re-`create-from-template` with the same title makes a *second* product → GL-22c option (a) dead. **(3) Q3 is confounded**, not answered — the only edit path tested (`PUT`) breaks the sync by itself; "Gelato may re-push after a dashboard edit" stays an open risk. **(4) Dropping a variation from the Etsy inventory patch orphans the Gelato mapping with no observed self-heal** → GL-22c option (c) dead. Two side-findings: a live `update_listing_inventory` float-price bug, and no `delete_listing` + no `listings_d` scope on the current token. | ✅ 4 answers → picked shape (b), struck GL-22d |
| GL-22b | D | **✅ DECIDED 2026-08-01 — `Gelato: Free shipping` (`288734253315`), €0 to every destination, one profile for the whole candidate.** The original options list (Large / Small / re-price 5x7) was built on an incomplete profile read; the live `GET .../shipping-profiles` turned up a free-shipping profile that removes the dilemma entirely. **Two corrections it forced:** the €12.44/€14.55 figures in `CLAUDE.md` are the *default/non-EU* rate, not flat global (EU sees €5.86/€7.04); and Gelato's real per-item shipping (€5.10–€5.86) is billed to the seller **regardless of profile** and is already inside the cost basis the retail prices were set against — so **no re-pricing is required**. Verified: 5x7 21.4 %, 8x12 32.6 %, A3 38.6 %, A2 38.0 %, 10x24 44.2 %, A1 42.1 % at 9.5 % + €0.25, reproducing SPEC v4.11 §4's ~21–44 %. Floor case (5x7 through Offsite Ads at 15 %) still nets 16.4 %. **What it forfeits, recorded:** the shipping surcharge on default-region/US orders — revenue the margin table never counted. | ✅ decision → single-value `etsy_shipping_profile_id` |
| GL-22c | D | **✅ DECIDED 2026-08-01 — option (b), create-once-when-all-groups-are-decided, publishing only validated sizes; stall rule = a plain 14-day timeout.** Options (a) and (c) were killed by GL-22a's Q2/Q4, so (b) was the surviving shape. **Stall rule revised same-day:** an initial "48 h nudge → 96 h skip" was replaced by a long timeout with **no reminder** (owner: defer the ping to post-go-live, → **GL-31**). That revision is what makes it cheap — with nothing to *send*, the rule is a **predicate, not a process**: the publish gate's "have all groups decided?" check gains an "…or has an undecided group aged past 14 days?" clause. Total scope: `stalled_skipped` in the `groups.status` CHECK, `GROUP_REVIEW_STALL_DAYS = 14` in `pipeline/config`, one predicate. **No `stall_sweep` stage, no `reminder_sent_at` column** — both struck with the nudge; the `CLAUDE.md` stage list is untouched. Window measured off the existing `groups.updated_at`. **Still depends on GL-7** in weaker form: the gate only fires when something evaluates it, so until the twice-daily batch exists the effective behaviour is wait-indefinitely — **"the stall rule fires" is a GL-7 DoD item, not a GL-22 one.** **A skipped size is a real forfeit, not a deferral** — Q2 means recovering it needs a from-scratch re-publish, which is the argument for erring long. | ✅ decision → shape (b) + a 14-day predicate |
| GL-22d | M | **✅ DONE 2026-08-09 (portrait) — UN-STRUCK, then completed by the owner's manual template edit. The 2026-08-01 strike was wrong, and why it was wrong is worth more than the row.** The portrait template now carries **three** placeholders (`003_flower_in_stream_madeira_color.JPG` for 8x12/A3/A2/A1, `011_mt_sunday_brook.JPG` for 5x7, `004_doorframe_bottles_madeira_color.JPG` for 10x24) and `static_config.json` names them, verified against the live API (GL-48 §4). **Q1 did not bear on this question.** A shared placeholder name does not force a shared *image* — true, and the wrong question; it forces a shared **fit**, a saved scale and position authored against one photograph. Q1 tested 8x12 (0.667) against 5x7 (0.714), ratios within ~4 % of each other, where fit and fill are visually identical: **the experiment could not have failed in the interesting direction.** A probe whose negative result is guaranteed by its design is not evidence, and this one closed the item for eight days. **The landscape twin is NOT struck and is NOT done:** all six landscape variants still share `009_boat_serene_bnw_scotland.JPG` (measured 2026-08-09) — the same three-placeholder edit is owed there, and it is now GL-18's inherited task. Previously: **✅ STRUCK 2026-08-01 — never needed.** GL-22a Q1 proved two variants sharing one `image_placeholder_name` accept independently-submitted `fileUrl`s in a single `create-from-template` call, so the portrait template needs no second/third placeholder and `static_config`'s existing per-size `image_placeholder_name` values stand. **Kept as a line, not deleted: this was a manual owner step on the critical path that a €0 measurement removed.** Its landscape twin (named in GL-18) is struck by the same finding. | — |
| GL-7 | C | **🔴 SOAK PAUSED 2026-08-09 (owner) — seven findings, no verdict; GL-7 stays unticked and now carries four dependent rows (GL-45–GL-48).** The soak proved the *scheduling* layer honestly — the lock, the schema guard, the heartbeats and the stall predicate all behaved — and then spent its second half discovering that the stages it was orchestrating have their own defects. **The pause is a yield judgement, not a failure judgement:** items 3/6 went from occasional to 8-of-8 in one batch, item 7 means the burned candidates were out-of-season anyway, and with live mode armed every further night costs real API spend to re-observe characterised defects. **GL-7's remaining DoD is unchanged and still unproven in three places** (PRD §6): the schema guard against a deliberately stale DB, the injected-failure→Telegram path, and GL-36's 404 reconcile — the last of which **still cannot fire in dry-run**, and whose falsifiable live test (flip 40 and 41, leave 42 alone) has therefore still not been run. **When the soak restarts it should be a short, targeted live night after GL-45–GL-48 land, not another open-ended two-nighter** — the open-ended format has now returned everything it is going to return. Previously: **🟡 BUILT 2026-08-05, SOAK RUNNING 2026-08-06 — not done until the soak passes and it is on master.** 15 commits on `worktree-gl7-cron-orchestrator` (`6b14688`…`bc229e9`), 19 files, ~3.4k lines, eight new test files, no existing `*_cycle` module modified. **What landed:** `run_hourly.py` (lock → schema guard → `run_publish_primary_group_cycle` → heartbeat) and `run_batch.py` (all 12 stages, per-stage isolation, missing env vars a controlled `exit(1)` rather than an uncaught crash); the lock, with **Windows-correct PID liveness, atomic acquire, unlink-only-own-pid and a bounded retry that fails *closed* on a contested stale-lock reclaim** — the right polarity, since a wedged pipeline is recoverable and two concurrent batches are not; the `heartbeats` table; Telegram surfacing on the two silent-failure paths (missing env, stale schema), skipped sensibly when the missing var *is* a Telegram credential; `heartbeat_status.py` as the one-command "did it run?"; and reconcile's drift summary folded into the batch heartbeat's `detail` rather than discarded. **Soak status:** night 1 dry-run, both flags `FALSE`, hourly and batch heartbeats `ok`. **Three things the soak still owes** (PRD §6): the schema guard exercised against a deliberately stale DB, the injected-failure→Telegram path, and — night 2 only — **GL-36's 404 reconcile, which cannot fire in dry-run at all.** Original scope: **two cadences (hourly Telegram poll, twice-daily batch) wiring the existing 13 stages; one function per stage, not one loop. Unblocked since 2026-07-23. **DoD includes the overnight unattended soak** — GL-16 is proven in unit/scripted-interrupt tests only, and the soak is its production proof. **DoD gained one item 2026-08-01: prove v4.12's stall predicate actually fires.** GL-22 writes it, but it is dormant until the batch cadence evaluates the publish gate — so "the 14-day timeout works" is provable here and nowhere earlier (test with the constant temporarily lowered, not by waiting 14 days). **Now the single biggest remaining build chunk.** | GL-3 decision + kickoff → PR + clean soak |
| GL-8 | R | **✅ DONE 2026-08-05** — briefing in `docs/2026-08-05-gl7-cron-prd-and-kickoff.md` §0: local desktop recommended, VPS named as the pre-committed fork. Fed straight into GL-3's sign-off the same day. Original scope: where the scheduled functions run (Cowork task vs. Claude Code cron vs. Fly/Render/Cloudflare/GitHub Actions), given cost, reliability and the persistent-process ban. Preliminary decision (GL-3): local desktop. Confirm or revise. | ✅ briefing → named host |
| GL-3 | D | **✅ SIGNED OFF 2026-08-05** (`docs/2026-08-05-gl7-cron-prd-and-kickoff.md` §0, "GL-3 signed off. No code.") — local desktop confirmed against GL-8's findings, VPS fallback pre-committed rather than open. GL-7's build started the same day on that basis. **The fallback stays live, not closed out:** it's exercised only if GL-7's still-running soak fails wake/sleep or reliability. Original scope: cron deployment target — confirm the local-desktop preliminary against GL-8. **Pre-committed fork:** if the desktop fails the soak on wake/sleep or reliability, move to a cheap always-on host named in advance by GL-8. | ✅ GL-8 → confirmed host |
| GL-13 | T | **✅ PASSED 2026-08-03 — R0–R5 all green, 635/635 throughout, fixes merged as PR #5 (`a2aff96`).** What it proved live, against the real APIs: the placeholder fail-loud guard (R1), `mockup_failed` retry with no Gelato fallback (R2), the 6/6 happy path — **one listing, created exactly once, exactly the validated sizes, no duplicate product, the gallery assembled once in rank order** (R3), re-patch idempotency against the real `listing_image_id` payload (R4), and a rejected group that **deleted nothing**, `GET`-verified either side (R5). **Four real defects found and fixed in-flight:** (1) the **DB had never been migrated to the v4.12 schema** — `group_products.candidate_id` and `product_images.group_id` were missing, and nothing in the repo runs a migration or checks schema version (→ **GL-35**); (2) `run_m1_live_test.py`'s seed check treated **any** historical candidates row as "already seeded", permanently blocking a fresh candidate on a DB with history — now checks for a *non-terminal* row, matching `research.trigger_fallback_if_needed`; (3) `critic_pass.py` truncated at `max_tokens=2048` on a 10-image gallery (the 7-criterion rubric genuinely needs the room) → 4096 — **the same defect class as GL-9's 1024→2048, second occurrence**; (4) `telegram_client.send_media_group` passed R2 URLs and relied on Telegram's own server-side fetch, which failed `WEBPAGE_CURL_FAILED` on 5–7.5 MB gallery images → now always downloads and multipart-uploads, the path local images already used. **Two gaps filed not fixed, per owner direction → GL-33 and GL-34, both promoted to blockers.** Original scope, for traceability: **Round 2 live re-test — the mockup-dependent slice + the v4.12 publish slice. Now the biggest remaining risk concentration outside GL-7.** Original: custom gallery in rank order, critic pass over custom scenes, `mockup_failed` retry with no Gelato fallback, the placeholder fail-loud guard, the real cover-crop reaching Gelato. **Session 2 handed over six things provable only live** (its own list, verbatim in intent): (1) **4→5→6 variants across one listing's lifecycle with no duplicate product** — the highest-value item, because Q2 proved a title collision silently creates a second product; (2) a **gallery grown across two reviews**, checked against the real listing, not the DB; (3) a **rejected group that deleted nothing**, `GET`-verified before and after; (4) the **real `listing_image_id` shape** the idempotent re-patch depends on — dry-run could only assert the mechanism, not the payload; (5) the **20-cap against a real Etsy rejection**, not just `GalleryTooLargeError`; (6) the **stall rule**, which **cannot fire until GL-7 runs the gate on a cadence** — so it moves to GL-7's DoD, not this one. **GL-23b ✅ merged (`7cbaee7`); guide written: `docs/2026-08-02-gl13-round2-delta-launch-guide.md`** — R0 pre-flight, R1 placeholder guard, R2 `mockup_failed` retry, R3 the 6/6 happy path, R4 re-patch idempotency, R5 reject + the never-tapped Reject button. **Two of the six handover items were stale and are corrected in the guide:** "4→5→6 variants across a lifecycle" and "a gallery grown across two reviews" both describe the publish-primary-patch-later shape `[D1]` killed — under create-once the listing is born at its final size and the gallery is assembled once. Replaced by "created exactly once, exactly the validated sizes, no duplicate product" and "the assembled gallery is complete and correctly ordered". **The 20-cap item is descoped with reasoning** (`GalleryTooLargeError` raises before any upload, so Etsy never sees a 21st image; proving Etsy's rejection would mean bypassing our own guard). | ✅ delta launch guide → pass/fail |
| GL-17 | T | **✅ PASSED 2026-08-03, folded into GL-13's R5.** The human Telegram **Reject** button was tapped for the first time since GL-9 and the reject path behaved to v4.12 spec — group marked rejected, its images excluded, **the shared product and listing untouched**. Residual live coverage from GL-9 is now closed. | ✅ pass |
| GL-33 | C+T | **✅ DONE 2026-08-04 — shipped and proven live (`47aa034`, PR #6 `14a2d10`).** `etsy_client` gained `get_listing_images` + `delete_listing_image` (dry-run-aware, 4 tests); `group_product.patch_etsy_listing` gained a reconcile pass (3 tests, idempotency covered) that deletes every listing image **not positively matched** to this candidate's `product_images.etsy_listing_image_id`, scoped by `group_product_id`, running after the upload loop and before `update_listing` so the listing is never briefly imageless. **Positive-match-only rather than pattern-matching Gelato's images** — a "delete what looks like a ghost" rule would eventually eat a real composite, and the DB already knows exactly which images are ours. **Live proof on candidate 42's listing `4549960823`:** 19 → 13 images, 6 Gelato ghosts deleted, 13 ours remaining, a second patch changed nothing, and the Gelato↔Etsy variant mapping and per-variant pricing both survived — which also **answers GL-22a's confounded Q3 in the narrow case that matters**: deleting a Gelato-owned *image* does not sever the sync the way `PUT`-ing the product did. Original scope: **Gelato's auto-push contaminates the listing gallery (NEW 2026-08-03, GL-13 finding). Blocker-class.** Gelato's product-creation push creates the Etsy listing *with its own preview images* — 5 or 6 of them, one per variant — and our patch then adds the tracked composites **alongside** them rather than instead of them. The result is a gallery that mixes Gelato's generic renders with the scenes GL-6/GL-21 spent four attempts authoring, in an order nobody chose. **This voids the self-hosted-gallery contract that is the entire justification for the mockup track** — and it is invisible today only because every listing so far is a draft. **Not a cosmetic item:** it is the first thing a buyer sees, and the 20-image cap is measured against the contaminated total, so six ghosts also eat six real slots. Likely shape (verify, don't assume): a `delete_listing_image` in `etsy_client` — which **does not exist yet**, `upload_listing_image` is the only image call in that module — plus a reconcile step in `group_product.patch_etsy_listing` that lists the listing's current images, deletes anything absent from `product_images`, and *then* uploads in rank order. **Two things to measure before building:** whether Gelato re-pushes previews after our delete (GL-22a Q3 is confounded on exactly this — the only edit path tested severed the sync), and whether deleting a Gelato-owned image breaks the Gelato↔Etsy mapping the way dropping a variation did (Q4). | measure → patch-step reconcile → live verify |
| GL-34 | T→C | **✅ CLOSED 2026-08-04 — no defect, no code change. It was a read-side field-name error, not a regression.** Findings: `docs/2026-08-04-gl34-findings.md`. The PATCH **request** takes `production_partner_ids` (list of ints); the listing **GET response** never echoes that key — it returns `production_partners` (list of `{production_partner_id, partner_name, location}`). A check reading the write-side name off a read-side response reports "missing" on **every** listing forever, independent of actual state. **Control confirmed live:** GL-9's listing `4542159277` returns `who_made: i_did` together with `production_partners: [{5717252, 'A print shop', 'Brussels, Belgium'}]`, matching the owner's dashboard screenshot exactly. The subject listing could not be read — GL-13's R3/R5 were already deleted live (→ GL-36), so candidate 42 was substituted with owner sign-off. **`CLAUDE.md`'s `who_made: i_did` + `production_partner_ids` lines both stand; the §3 contradiction flag is withdrawn; `someone_else`/`collective` stay off the table.** **The lesson, third occurrence: an API response echo is not listing state.** Original scope: **`production_partner_ids` appears to drop on the v4.12 patch (NEW 2026-08-03; SCOPE CORRECTED 2026-08-04). No longer a policy item, no longer a decision — a narrow diagnosis with a known-good control.** The original filing read the GL-13 observation as "`i_did` and `production_partner_ids` are mutually exclusive on Etsy", and concluded from that a mandatory-disclosure risk and a `who_made` change. **Owner evidence 2026-08-04 kills that reading:** a dashboard screenshot from the **GL-9 (v4.11) round** shows, on one live listing, `Who made it? = I did` **together with** `Production partners for this listing: Gelato, Brussels, Belgium — Appears on listing as "A print shop"`. They coexist. **Three consequences, stated plainly:** (1) there is **no policy exposure** — the disclosure was present on the listings that had it; (2) `CLAUDE.md`'s "verified" `who_made: i_did` line **stands and needs no correction** — the §3 contradiction flag raised against it on 2026-08-03 is **withdrawn**; (3) `someone_else`/`collective` are **off the table** — moving to them would be *less* accurate (the design genuinely is the seller's) and would forfeit the "designed by a seller" label for nothing. **What actually remains:** GL-9's patch sent `production_partner_ids=[5717252]` with `who_made: i_did` (see `docs/2026-07-22-v411-live-test-launch-guide.md`) and the partner landed; GL-13's patch appeared not to. Either the v4.12 patch path regressed, or the GL-13 observation read the **API response echo** rather than the listing's actual state. Diagnosis, not research: reproduce, then `GET` the listing *and* look at the dashboard, with GL-9's listing as the control. **Only weakly blocks GL-29** — confirm the field is present on the listing before activating, but the shop-suspension framing was wrong. | reproduce → `GET` + dashboard vs GL-9 control → fix or close as observation artifact |
| GL-37 | M+R | **✅ ANSWERED 2026-08-06 — neither field is API-settable, at either level, and the decision is to accept the manual per-listing step.** Findings: `docs/2026-08-06-gl37-findings.md` *(currently only in the GL-7 worktree — it must travel with GL-38's merge or it is lost).* **What was actually checked, and why the answer is trustworthy this time:** (1) a **full raw response dump** of `GET /listings/{id}` on two live listings (`4549960823`, `4542159277`) — every field enumerated, not a field-name grep, which is what makes this immune to the read-side/write-side aliasing that produced GL-34's false alarm: *there is no read-side field to alias to*; (2) all **15 taxonomy properties for `taxonomy_id` 1027** enumerated — `Craft type, Material multi, Primary/Secondary color, Width/Height/Depth, Sustainability, Home style, Occasion, Holiday, Room, Custom1–3` — killing the "it's hiding as a listing property" theory; (3) `GET /shops/{shop_id}` dumped — **no shop-level default exists**, so the hoped-for "tick it once, ever" is not available; (4) the dev-relations channel, where **Discussion #1630 (opened 2026-06-22)** is an open, unactioned feature request asking for exactly these two fields under exactly the names one would guess (`production_process`, `tools_used`). **A feature request is proof the field does not exist, not evidence it might.** One reply, no Etsy staff response, no PR, no changelog entry. **⚠️ The finding with teeth, which is not the "no API" part:** the only place to set these is the web listing editor, and **the editor's sole save action is "Activate with changes" — there is no draft-save.** So the disclosure tick *is* an activation. See the GL-29 row: this collides with the activation policy and changes GL-29's shape rather than merely gating it. **Recurring re-check filed post-launch as GL-39.** Original filing: **The Creativity Standards fields are blank on every listing, and that is where Etsy's AI disclosure actually lives (NEW 2026-08-04, from the same screenshot).** Two listing questions are unanswered on every listing the pipeline has produced: **"How does your shop produce this item?"** (made from scratch / assembled / altered / curated / natural material — all five radios empty) and **"What tools are used to make this item?"** (handheld / computerized / **an AI generator** / none — all four boxes empty). **`CLAUDE.md` already records that the tools question is not API-settable** and that the AI disclosure therefore lives in the description text. The screenshot confirms that and adds the produce-method field, which was not previously noted. **Why this is worth its own line rather than a footnote:** "An AI generator" is the checkbox Etsy's own Creativity Standards point at, and a description sentence is a *weaker* substitute than the structured field, not an equivalent one. **And the automation consequence is the sharp part:** if these can only be set by hand in Shop Manager, then every listing needs a human dashboard visit before it is compliant — which is a per-listing manual step sitting inside a pipeline whose entire premise (GL-7) is unattended operation. Scope: (1) re-check whether the v3 API has since exposed either field — this was established some time ago and Etsy has been actively shipping Creativity Standards changes; (2) if not, decide whether the manual tick is acceptable per listing, batched, or whether a shop-level default exists; (3) record the answer where GL-28 and the description-disclosure text can both point at it. **Not a GL-33/34 session item** — it is owner-manual and research, and folding it in would blur a clean coding session. | API re-check → owner decision on the manual step → recorded |
| GL-10 | M | **✅ DONE 2026-08-08 — every item on the checklist tackled in Shop Manager; the GL-10d banner upload was the last one.** Item 5 (the structured "an AI generator" tick) remains the per-listing publish action it always was — closing GL-10 does **not** close that, because it is a property of each listing, not of the storefront (see GL-37). Item 4.2's returns wording was a view the owner took, not a paste; if it was left on Etsy's default, say so here before GL-11 rather than after. Previously: **🟢 RESEARCHED AND SPECIFIED 2026-08-07 (GL-10b) — reduced to a paste-and-click list; nothing here is blocked by anything.** Artefact: `docs/2026-08-07-gl10b-storefront-checklist.md`, seven items, six of them safe in any order. **What to actually do:** (1) paste the **shop tagline** — `AI-made botanical & minimalist art prints, unframed`, 51 of 55 chars — a **surface the original brief did not know existed** (R12), indexed by Google, currently empty; (2) **rename section 59380312** "Posters" → **`Unframed Art Prints`** (19 chars) — chosen because it completes the `[product-form qualifier] + [medium]` pair with the existing "Framed Photography", which is exactly how GateOfDesign (the sample's only other two-fulfilment shop) splits its catalogue, and because **0 of 10 sampled shops use the bare word "Posters"**; (3) paste the **About** text — ~120 words, and the AI statement is a **paragraph, not a footnote**, because under GL-37 `DISCLOSURE_TEXT = ""` makes this the only *written* disclosure anywhere in the shop; (4) **policies** — 4.1–4.4 drafted with `[[ ]]` placeholders left **deliberately unfilled** (they are facts about the Gelato account and shipping profile `288734253315`; guessing them puts wrong information in front of a buyer), 4.5 uses Etsy's own privacy template; (6) announcement stays off (Q3 unchanged — only 1 of 10 shops ran one and it was inert since April 2025). **Two things that are not clerical.** ⚠️ **Item 5, the structured "an AI generator" tick, is not a quick pre-launch tick — it *is* the publish action.** Etsy's web editor has no draft-save; its only save is "Activate with changes" (GL-37). Sequence it with GL-11, and never do it on a listing you are not ready to make live. ⚠️ **Item 4.2's returns wording needs a view taken, not a paste.** EU distance-selling gives a 14-day right of withdrawal with an exemption for goods "made to the consumer's specifications or clearly personalised"; whether a standard-size POD poster sits inside that exemption is **genuinely arguable** — the design is not personalised, only the timing of manufacture is. The competitor sample is no help (TheWorldGallery, also POD and also UK/EU, simply accepts 14-day returns). The artefact says plainly it is not legal advice and that **the safe default is to accept returns**. **Two things are explicitly NOT in this row:** a subject taxonomy (Botanical/Celestial/Minimalist sections) — that means the publish path stops reading a single `etsy_shop_section_id`, which is code, deferred with GL-10c; and the banner rebuild → **GL-10d**. **Renaming is free and reversible** (R11): section URLs are `?section_id=<numeric>`, the name is not in the URL, and `static_config.json` is unaffected — so get it right because it is a browse and relevance surface, **not** because it is a one-way door. Original scope: Etsy storefront overhaul — banner, sections, About, policies, SEO copy. Owner-driven, one-way-valve safe. | ~~checklist~~ ✅ → **owner executes in Shop Manager** |
| GL-10d | C+M | **✅ DONE 2026-08-08 — banner rebuilt, `verify.py` green, both banner and icon uploaded to the shop.** The upload also closed the last open item on GL-10b's storefront checklist, so this row and GL-10 ticked together. Filed the same day it was created — the shortest-lived row on the board. Original scope: **the banner rebuild, promoted to a go-live gate item (owner).** Decision document, deliberately self-contained for a cold Claude Code session: `docs/2026-08-07-gl10b-banner-icon-decision.md` §4 and §7. **The icon needs no build at all** — `assets/brand/qhoto-shop-icon-500.png` (Bone badge on Pine, symbol only, 8.7:1) is already correct; **just upload it**. The sweep confirmed by measurement what GL-10a had already reasoned to: judged at true 74 px avatar size, **symbol-led icons are legible 4/4 and wordmark-led icons 0/6**, no exceptions in either cell, including two Star Sellers with 20k+ sales. The live `shop_icon.jpg` — monogram over a "Qhoto-Art" wordmark filling the lower half — is squarely in the 0/6 cell. **The banner is an adjustment inside A1, not a rebuild and not a move to A2:** the Ink ground, Pine `#23402F`, Bone, Fraunces + Inter, the badge geometry and every palette/geometry constant in `verify.py` are **unchanged**. **One thing changes** — the banner gains a band of **product imagery composited from existing mockup renders**: real QhotoArt prints, in the existing hand-authored scenes, on the Ink ground. **Why composited rather than generated, stated so it is not relitigated:** we already produce those renders deterministically at a known crop through `pipeline/mockup_render.py`; a generative model cannot hold an exact palette value, cannot reproduce a measured mark, and cannot be regenerated identically later. That is also why **Nano Banana Pro is role C** — role A needs the field's imagery to be *atmospheric*, and all 8 of the 8 imagery-carrying banners are framed product in styled rooms, which is a mockup, not a texture plate. **Why it is on the gate rather than post-launch:** the four failures of the live banner (§4.1) are structural, not aesthetic, and survive any D-A outcome — promise mismatch (it advertises framed figurative portraits the pipeline does not make), a **visible garbled-text generation artifact** in the largest brand surface on the page, 1,497.5 KB against Etsy's stated 1 MB upload warning, and 1600 × 896 matching **no documented Etsy format**, so Etsy crops it wherever it likes. **DoD:** emitted by `build_final.py` at 1600 × 400, no alpha, < 1 MB; **`verify.py` passes with MORE assertions than it had, not fewer** — new no-alpha check (Etsy renders transparency as black and nothing currently catches it), safe zones at lines 82–88 **re-parameterised** to the off-centre lockup rather than deleted, existing palette/geometry/size checks intact (**the < 1 MB check already exists at line 45** — an earlier draft proposed adding it); icon untouched and still passing; `assets/brand/README.md` records that the live pair is retired **and why**, so it cannot be resurrected; owner uploads both in Shop Manager. **Losing the verifier is the actual risk of this change.** **One sub-decision is deliberately left open:** whether the *wordmark* sets "QhotoArt", "Qhoto Art" or "Qhoto-Art" — all copy uses `QhotoArt` (that is what a buyer sees in the URL and the search row) but the lockup is a design question for phase 7, flagged so it is not silently inherited. **Do not read the sample's panelled/carousel banners as a target** — Etsy restricts those to Etsy Plus; on the free tier there is exactly one option, a single static 1600 × 400. | decision doc ✅ → Claude Code session → `verify.py` green → owner uploads |
| GL-38 | C+M | **✅ DONE 2026-08-09 — master is `46c7ba6`, carries all 22 commits, 709 tests green, and PR #7 is MERGED on the remote.** Executed in the order the kickoff specified. **What the kickoff got wrong, in descending order of usefulness: (1) there was no conflict at all.** `tests/test_research.py` auto-merged — GL-43's guards and the soak's `sort_on` regression sit in different regions of the file. Both were verified present *by content* (lines 38–47 and 136–149) and the file re-run at 22/22, because a clean merge exit is not evidence that both additions survived. **(2) There is no PR-less local merge here — PR #7 was open and the kickoff never mentioned it.** Pushing branch then master let GitHub close it as merged (17:26Z); a purely local merge would have left it open indefinitely. **(3) Five uncommitted files on master, not four** — `docs/2026-07-22-go-live-plan-of-attack.md` (+199/−21, this board) was also dirty. **(4) `docs/2026-08-06-gl37-findings.md` was untracked in the *worktree*,** not the root, and would have died with it exactly as the soak findings nearly did — committed on the branch as `4d2648f` before merging. **(5) Three scheduled tasks, not two** (`qhoto-hourly`, `qhoto-batch-morning`, `qhoto-batch-evening`), all already Disabled, so nothing could race the swap. **Two defects found while executing, both filed rather than fixed here: `migrate.py` treats `argv[1]` as the DB path unconditionally, so `migrate.py --check` opens a *new empty database literally named `--check`* and reports `schema_version is 0` — a stale-schema false alarm on a correct DB, and it silently litters the repo root; the correct invocation is `migrate.py db/qhoto.sqlite3 --check`, which returns `schema_version=7, up to date`. And all three scheduled tasks had an empty `WorkingDirectory`,** so a cron-launched run inherited `C:\Windows\System32` — harmless only because every path resolves off `__file__`; now set to the repo root. **Deviation from the procedure, owner-approved: Phase D's hand-run heartbeat verification (step 13) was SKIPPED.** With live mode armed, `run_hourly.py` would action real Telegram callbacks against GL-45's unfixed drop bug and `run_batch.py` would spend Replicate/Anthropic money re-observing GL-46 — the brief asked for a live run to prove a path resolution that is `__file__`-relative and provable by reading. **So the deployment is re-pointed but has never executed from the root; the first real heartbeat there is still owed, and lands free with the first GL-45 test run.** DB: promote-and-swap done, `schema_version` 7, `integrity_check ok`, candidates 1–86, `telegram_offset` 475586404, both heartbeat rows, 85 groups / 39 products / 187 images; **both pre-swap files retained as `db/qhoto.sqlite3.bak-2026-08-09-root` (the only undo) and `.bak-2026-08-09-worktree`.** Six stale worktrees removed after confirming each was clean with zero unmerged commits; their `worktree-agent-*` branch refs are left in place, harmless. The branch is preserved as `gl7-soak-archive`. **⚠️ The sharpest finding came last, and it is the one to carry into any future worktree retirement: removing the GL-7 worktree would have silently orphaned the promoted database.** Its `db/` held **1.6 GB of git-ignored artefacts, 289 files of which existed nowhere else** — the base artwork and mockups for candidates 43–86, i.e. exactly the rows the promoted DB references — and **24 candidate rows stored *absolute* `base_image_local_path` values pointing into the worktree.** `git worktree remove` would have reported success and left a canonical DB referencing deleted files. Fixed in that order: robocopy the 289 missing files to `db/base_artwork` (no-overwrite, byte-identical, root now 408 files), then rewrite the 24 paths to the root prefix after verifying every target existed — **0 unresolvable paths across all 62 candidates with artwork**, confirmed before the removal. **The general rule: a worktree's git status says nothing about the git-ignored artefacts a database points at, and "no unmerged commits" is not the same as "nothing to lose."** The empty worktree directory itself survived deletion (the session's own shell held it open on Windows); it holds nothing and can be `rmdir`'d. **Left untracked deliberately:** `assets/mockups/5x7/portrait/lifestyle_small_kitchenshelf/` (fails `distortion` 2.26 %, GL-27 says regenerate-or-drop, already in R2 via GL-30) and `assets/brand/etsy-banner.png` + `shop_icon.jpg` (Nov-2025 source inputs, not in the R2 corpus — **the one remaining un-backed-up artefact, worth a line in GL-27**). Previously: **🟢 UNBLOCKED 2026-08-09, and SURVEYED the same day — kickoff: `docs/2026-08-09-gl38-merge-kickoff.md`. The survey is the news: this is not the clean fast-forward every previous revision of this row assumed.** One real conflict (`tests/test_research.py`, both sides added tests, both must survive), one untracked file that will refuse the checkout outright, **GL-37’s `DISCLOSURE_TEXT = ""` change uncommitted on master since 08-06 and touching the live publish path**, and ~11 board-cited docs still untracked. **The database, conversely, stopped being a question:** the worktree copy is a **proven strict superset** (eight tables compared row-by-row, zero missing, zero differing), so it is a promote-and-swap with nothing to reconcile. Previously: **🟢 UNBLOCKED 2026-08-09 — the soak is stopped, so the merge is available now and should go FIRST, ahead of GL-45–GL-48.** The soak was the only reason the worktree had to stay live; with it paused, the standing "run nothing from the main checkout" rule can be **retired rather than endured**, and the four fix sessions branch off master like normal work. **The argument for merging before fixing, not after:** four more commits on that branch would make this the *fifth* occurrence of the merge pattern (GL-1, GL-23, GL-23b, GL-38) on a branch already carrying GL-30, GL-35, GL-36 and GL-37's findings — and GL-49's row repair would be done against a database that is about to be superseded. **The five-step sequence below is unchanged and is now the head of the critical path**; the full ordering, including what to do about the two databases, is in Part 3, Track E. Previously: **OWNER DECISION 2026-08-06: let the soak finish on the worktree as-is; merge afterwards, then re-point the scheduled tasks.** Endorsed — restarting a running soak to fix its provenance would throw away the one thing that costs wall-clock time, and the divergence is understood rather than surprising. **What that decision buys and what it costs, stated so neither is a surprise later:** it buys two uninterrupted nights; it costs a **post-merge sequence that is now mandatory, not optional**, and it means **the soak's result is provisional until that sequence is done** — a pass on the worktree is evidence about the code, not about the deployment. **The post-soak sequence, in order:** (1) merge the branch to master; (2) **reconcile the two databases into one, canonical DB backed up first** — decide deliberately which is authoritative rather than defaulting to the newer file (CLAUDE.md §4: this is destructive, show the plan and wait for "proceed"); (3) re-point both Windows scheduled tasks at the repo root and **verify by heartbeat**, not by assumption — `heartbeat_status.py` against the canonical DB should show a fresh run after the switch; (4) confirm `db/gl7.lock` now lives beside the canonical DB and that the worktree's copies are out of the picture; (5) **prune or lock the worktree** so nothing can invoke it again. **The standing hazard until step 3 completes is unchanged and is the thing to actually watch: one bot token, one `getUpdates` cursor, two trees, and a lock that is keyed per-tree so it does not arbitrate between them.** Nothing may be run from the main checkout while the soak is up — and after the switch, nothing from the worktree. **The token-scoped guard (below) is worth building even after the merge**, because this failure mode is a property of the design, not of this week's accident. Original filing: **The soak is running from an unmerged agent worktree, against a forked database (NEW 2026-08-06). Blocker-class, and cheap.** `master` is at `14a2d10` and does not contain `run_batch.py`, so the scheduled tasks are invoking `.claude/worktrees/gl7-cron-orchestrator/`. Both entrypoints resolve `DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"` — **relative to the script**, which is correct code and exactly why the fork happened silently. **Three distinct problems, in increasing order of sharpness:** **(1) The merge, fourth occurrence.** GL-1, GL-23, GL-23b and now this. The runtime deploys from master; a soak that passes on a branch has proven something about a tree nobody will run. It should stop being written as a per-item note and start being a **standing definition-of-done**: a build is not done until master carries it. **(2) Two databases.** The worktree's is migrated (`schema_version` 7, 450 KB, actively written); the canonical one is 434 KB, last touched 2026-08-04, with no `schema_version` table. Soak state — heartbeats, aged-out rows, any candidate the batch creates — accrues to the copy. Somebody has to decide which is canonical **before the live night**, and the answer is not automatically "the newer one". **(3) The Telegram single-consumer hazard, which is the genuinely dangerous one.** `getUpdates` has one cursor per bot token, and each tree keeps its own `telegram_offset` row. If anything is run from the main checkout while the soak is up — `run_m1_live_test.py` still exists there and still works — **the two trees eat each other's updates, and an owner tap can be consumed by the tree that cannot act on it, then acknowledged and gone.** The new lock does **not** cover this: it is a file lock at `<tree>/db/gl7.lock`, so the two trees take two different locks and both proceed. This is PRD §2 item 3's property being satisfied *within* a tree and violated *between* trees. **Fix shape (small):** land the branch on master, point the scheduled tasks at the repo root, reconcile the two DBs into one with a backup first, and — the part worth keeping — make the single-consumer property enforceable rather than conventional, e.g. a lock keyed on the bot token or the DB's identity rather than on the script's directory. **Until it lands, the operational rule is: do not run anything from the main checkout while the soak is up.** | merge + one DB + a token-scoped guard |
| GL-29 | C+T | **❌ CANCELLED as a go-live item 2026-08-06 (owner) — struck from the go-live gate, re-filed post-launch as GL-29b. This row is kept, not deleted, because the reasoning is worth more than the row.** GL-37 established that the AI-disclosure tick lives only in the web listing editor and that the editor's only save action activates the listing. **The owner is therefore the publish gatekeeper by Etsy's design: he ticks "an AI generator" and publishes in one action.** Programmatic activation would race that step, not save it — it would produce a live listing that is *less* disclosed than the manual path, for €0.20, through a door that only opens one way. **What makes the cancellation clean rather than a deferral:** the code already exists and is already safe. `etsy_client.update_listing_state` stays written, dry-run-aware, unit-tested and **`# DELIBERATELY UNWIRED`**, and `test_patch_etsy_listing_never_activates_a_listing` stays exactly as it is — the guard test that was going to be *rewritten* by this item now simply keeps doing its job. **Nothing to build, nothing to undo.** **Reopen when, and only when:** Discussion #1630 ships (→ GL-39) so the disclosure becomes API-settable, **or** listing volume makes a per-listing dashboard visit the actual bottleneck. Until one of those is true this is a cost with no benefit. Original scope, for traceability: **Programmatic draft→active publishing, behind an env gate (NEW 2026-08-01, owner).** Today activation is a manual per-listing dashboard action by design. **Half of this already exists:** `etsy_client.update_listing_state` is written, dry-run-aware and unit-tested, carrying a `# DELIBERATELY UNWIRED` comment and a guard test (`test_patch_etsy_listing_never_activates_a_listing`). The work is therefore *the gate and the wiring*, not an integration: a new all-or-nothing flag (`ETSY_ACTIVATE_LISTINGS`, **default false**, resolved like `is_live_mode`), one call site at the end of the publish path, the guard test **rewritten rather than deleted** (it must now assert "never activates *unless the flag is on*"), and loud logging on every activation with the listing ID. **Three constraints the build must respect:** (1) Etsy's API says setting `state=active` publishes the listing and **it can never return to `draft`** — only `active`↔`inactive` — so this is a one-way door per CLAUDE.md §4: record an `activated_at` on the row and ship the `inactive` path in the same PR as the rollback; (2) activation costs **$0.20 per listing** and is charged in Developer Mode too, so each live test burns real money — budget a handful of euros, not a sweep; (3) **ordering vs GL-22** — activation must be the *last* step, after every group's patch has landed, or a buyer-visible listing gains variants and gallery images afterwards. **✅ Resolved 2026-08-01 by GL-22c's decision:** under create-once-when-all-groups-are-decided the listing is created with every validated size and its full gallery already assembled, so activation is unambiguously the last call in the publish path and GL-29 needs no ordering logic beyond "call it last". **Testing in Developer Mode proves the API call, not shopper-facing visibility** — the visual confirmation belongs to the first minutes after GL-11. ~~**Blocked as of 2026-08-03 by GL-33, and weakly by GL-34.**~~ **✅ Both gates cleared 2026-08-04 — GL-33 shipped, GL-34 closed as a non-defect. GL-29 is unblocked and is now the cheapest remaining blocker on the board.** Kept for the reasoning: activation is the one-way door that makes the gallery and the disclosure buyer-visible, and `active` can never return to `draft`, so the only remedy for publishing a known defect is `inactive`. ~~**One gate does remain, and it is GL-37**~~ — **GL-37 answered 2026-08-06, and it does not gate GL-29 so much as partially collide with it. Flagging this rather than quietly re-scoping (CLAUDE.md §3).** GL-37 established that the two Creativity Standards fields can only be set in the web listing editor, and that **the editor's only save action activates the listing** — there is no draft-save. Consequences for this row, in order: **(1) the manual disclosure step is itself an activation**, so for any listing you intend to disclose properly, a human visit to the editor is what takes it live — and GL-29's programmatic call never gets to be the thing that activates it. **(2) GL-29's remaining value is therefore narrower and should be stated honestly:** it activates *at scale, without a dashboard visit*, which is only useful if you accept the two fields staying blank on those listings. That is a real merchandising/compliance choice, not a technical detail. **(3) The €0.20 and the one-way door are unchanged**, but the ordering question flips — the cheapest correct path today may be "no GL-29 at all for the first listings", tick-and-activate by hand, and revisit when Discussion #1630 ships (→ GL-39). **Owner decision needed before this is built, and it is no longer "when", it is "whether, and for which listings".** **Owner sequencing 2026-08-05: GL-7 runs first anyway** — GL-29 is a session that will still be a session later, and it costs real money each time it is exercised. | ~~GL-33 + GL-34~~ ✅ → GL-37 decision → flag + wiring + rewritten guard → one live activation → GL-11 |
| GL-11 | M | **🟡 EMAIL SENT 2026-08-06 — the clock is started and now runs in the background.** Draft used: `docs/2026-08-06-gl11-developer-mode-email-draft.md`. **What this changes about the plan's shape: nothing on the board is waiting on anyone external any more.** Since 2026-08-03 this row has been the one item on a clock the owner does not control, and every revision since said so; it is now spending that lead time in parallel with the GL-7 soak, which is the best available use of it. **What is still owed here:** Etsy's reply and the actual mode change — the item is not ✅ until the shop is out of Developer Mode. **Two follow-ups worth not dropping:** (1) if there is no reply in ~10 business days, reply in the same thread rather than opening a new one; (2) the sent email's "test listings have been deleted" line — candidate 42's draft `4549960823` was still live at send time and is deliberately being kept alive as GL-36's negative control for the soak's live night. Delete it after that run, so the statement becomes true rather than staying approximately true. Original scope: **Revert Etsy Developer Mode** — email developer@etsy.com, external approval lead time. Listing visibility observed before this is not representative. **Owner sequencing (2026-08-01): GL-29 lands and is tested first** — the point of reverting is a store that publishes. **Owner decision 2026-08-02: the email waits for GL-13 to pass**, rather than going out immediately. Deliberate trade — it spends lead time that cannot be recovered, in exchange for not opening an external conversation about a shop whose publish path is still unproven. **Consequence to watch: from GL-13's pass, GL-11 becomes the only item on the critical path with a clock you do not control.** If GL-13 slips, this slips with it one-for-one. **✅ 2026-08-03 — the gate is satisfied. GL-13 passed, so the email is unblocked and is now the single highest-leverage action available: it costs ~10 minutes, it is owner-only, it needs no code, and every day it is not sent is external lead time burned for nothing.** Send it in parallel with the GL-33/34 session — nothing about those two changes what the email says. | ~~GL-13 pass~~ ✅ → **email (send now)** → GL-29 → Dev Mode off |
| GL-30 | C+M | **✅ DONE 2026-08-08 — `34a8b15 feat(gl30)`, on the GL-7 soak branch, reaching master with GL-38's merge.** **443 files, 381.5 MB, every one `status: uploaded`, `dry_run: false`** — all thirteen `outputs/gl6_*` batches plus the 20 untracked files in `assets/mockups/inflow/`; **209 of the 443 carry a `verdict_key`**, which is the half that makes the corpus an inventory rather than 443 anonymous PNGs. Built as specified: `scripts/corpus_backup.py` + `tests/test_corpus_backup.py`, reusing `artwork_store._r2_put_object` rather than writing a second uploader, sha256 content-addressed under `mockup-corpus/`, write-once. Manifest: `docs/data/2026-08-08-mockup-corpus-manifest.json` (3,551 lines) — **that file, not this row, is the durable record**; anyone looking for a specific image starts there. ⚠️ **A process note worth more than the row itself: this was invisible from master for most of a day.** It was built in a *locked worktree*, so `git status` on master showed nothing, and a GL-30 kickoff document was written on 08-08 for work that was already underway — see `docs/2026-08-08-gl30-kickoff.md`, superseded by the manifest and safe to delete (still on disk, untracked, pending the owner's word). **Parallel worktrees hide completed work from every check that looks at the main checkout.** When the board says an item is open, confirm against `git log --oneline master..<worktree-branch>` before scoping a session for it. Original scope: **One-off backup of the mockup corpus to Cloudflare R2 (NEW 2026-08-01, owner).** Every generated scene — accepted, parked and rejected — exists only on the desktop. **Scope it to what git does not already have**, see the note below the table: the git-ignored `outputs/gl6_*` batches (~160 screened images **and their `screen.json` verdicts**), the untracked `inflow/` sources, `lifestyle_small_kitchenshelf`, and anything parked outside the tree. **Reuse `artwork_store._r2_put_object` + `_sigv4_headers`** — the S3-compatible PUT, the SigV4 signing and the all-or-nothing `R2_*` env gate are already written and tested; do not write a second uploader. **Write-once, never overwrite:** date- or content-addressed keys under one prefix, because a sync that can overwrite is a copy, not a backup. **Carry each image's sidecar/`screen.json` with it** — without the verdicts the corpus is 160 anonymous PNGs and the inventory value (the thing the harvest proved was worth more than the mask change) is lost. Parallel to the critical path; must not delay GL-7 or GL-22. | script → uploaded corpus + a manifest of what landed where |
| GL-12 | M | **🔴 DEFERRED TO POST-LAUNCH 2026-08-08 (owner) — not the zero-cost item it was filed as.** Alpha registration turns out to require standing up a Google Cloud Console project first (GCP project, Workspace linkage, billing attached) before the application can even be submitted — real setup cost, not a "click apply" parallel task. Moved off the go-live board; see the Post-launch table. Original scope: Apply for Google Trends API alpha access (zero cost, parallel). | how-to → submitted |
| GL-45 | C+R | **🟡 H1 ELIMINATED 2026-08-09, and the likely cause is now named: a second consumer of the bot token — specifically, the throwaway-DB test runs that the soak findings cited as *ruling interference out*.** `getWebhookInfo` returned `url: ""` and **no `allowed_updates` field** (never set ⇒ default, which includes `callback_query`), so neither half of H1 survives. **The decisive new fact is `pending_update_count: 0`:** Telegram holds an unconsumed update for 24 h, the 08-09 taps were today, and all three tasks have been Disabled since GL-38 — so unread updates would still be queued. **They are not, therefore something consumed them.** Confirmed retrospectively from the stored `raw_payload`s: **19 `update_id`s exist that never produced a row** (362–363, 375–380, 383–390, 398–400), clustering exactly on the reported drop windows. **The mechanism: the Telegram cursor is per-token and global; `telegram_offset` is per-database-file.** A `run_hourly.py` against a throwaway copy polls with *that copy's* offset, receives the real updates, **confirms them (deleting them for every consumer)** and writes the result into the throwaway — a perfect silent drop, no row, no discard. **GL-38 framed this hazard as “one token, two trees”; it is “one token, any number of processes”, and the per-directory lock cannot see any of them.** **Two corrections to the original finding:** groups 53/55/59 carry `decision='approved'` with `status='pending_review'`, which is the **correct v4.12 intermediate state**, not a drop — the genuinely lost taps are the *secondary* groups (76–81, 84) at `decision=NULL`, so diagnose from `groups.decision`; and update_ids 365/366/367 each appear **twice** ten minutes apart, which is a run killed mid-publish before `set_telegram_offset` — the safe direction of the same weakness. **Next: grep the throwaway copies for the 19 ids (case closed if found), then build a token-keyed lock plus a canonical-DB assertion, and ship the tap acknowledgement regardless.** Previously: **🆕🔴 Telegram button taps are silently dropped — CONFIRMED RECURRING, and the only open item that corrupts *decisions* rather than plumbing (soak finding 4).** 2026-08-08: the owner tapped approve/reject on 7 `pending_review` primary groups (48, 49, 55, 57, 58, 59, 60); **3** produced a `telegram_events_log` row. The remaining 4 were re-tapped and only the **third** attempt was captured. 2026-08-09: **recurred with no manual-run interference anywhere near the window** — all four secondary-group taps (candidates 49, 55, 60, 66) left zero trace. **Do not re-run the "they probably weren't actually tapped" explanation; the owner has directly contradicted it, twice.** Code review is exhausted and found nothing: `set_telegram_offset` only advances past `update_id`s the loop iterated, and `resolve_callback` returns an unlogged `None` **only** for updates with no `callback_query` at all — which a real tap always has. Every other path logs an explicit row, including "discarded". So the update never reached `resolve_callback`. **Why this is blocker-class and not a UX annoyance:** a dropped *approve* is indistinguishable from an unreviewed group and self-heals when re-tapped; a dropped **reject** leaves a group looking undecided until `GROUP_REVIEW_STALL_DAYS` ages it out — and under GL-22a Q2 a skipped size is a **permanent forfeit**, not a deferral. Under live mode this is the difference between a listing that ships what the owner approved and one that ships what he ignored. **The one check nobody has made, and it should be made before a single line of instrumentation is written: `getWebhookInfo`.** One unauthenticated-shaped GET on the bot token, ~10 seconds. If a webhook URL is set, `getUpdates` is starved and every symptom follows immediately — including "zero trace, not even a discarded row" and "the manual run happened to catch it". It also returns the **sticky `allowed_updates` list**, which persists from whatever was last passed to `setWebhook`/`getUpdates` and which this codebase never sets (`telegram_client.get_updates` sends only `timeout` and `offset`). Second cheap hypothesis, same class: **another consumer of the same token** — a stale Windows Task Scheduler entry, a dev shell, or the second tree GL-38 describes. **Only if both are clean** does this become an instrumentation job: log the raw `getUpdates` response body verbatim, before `resolve_callback` sees it, and correlate against `update_id` gaps. **A separate, real, and cheaper-to-fix gap found alongside it:** inline buttons never change appearance after a tap — no `answerCallbackQuery` toast, no `editMessageReplyMarkup` — so the owner cannot tell a dropped tap from a slow one. That is **not** the cause (the DB proves the update never arrived) but it is why the defect went unnoticed for two days, and the fix is one call at the point the callback is resolved. | `getWebhookInfo` + token-consumer audit → raw-`getUpdates` instrumentation only if needed → fix + tap acknowledgement |
| GL-46 | C | **🆕🔴 Per-candidate `generate` failures are swallowed, and 2026-08-09 proved it systemic rather than flaky (soak findings 3 + 6).** `pipeline/generate.py:262-264`, inside `run_generate_cycle`: a bare `except Exception: … continue`. The candidate's status is never set to `failed`, and because the exception dies there it never reaches `run_batch.py`'s `_run_stage` outer catch either — **so no Telegram notification fires and the row is indistinguishable from "hasn't run yet"**. 08-08: candidate 45 stuck `pending`, generated cleanly on a manual retry with no code change. 08-09: **8 of 8** new `go` candidates (76–81, 83, 84) stuck at `pending`, zero reached `generate`; candidate 76 reproduced cleanly by hand. Plausible-not-confirmed cause: `generate.py`'s own Replicate rate-cap pacing tripping across an unusually large queue (11 candidates plus other stages' Replicate/upscale calls in the same batch). **Transient failures self-heal for free** — the next run re-queries `WHERE status = 'pending'` — which is exactly what makes this dangerous: it looks benign right up until a persistent failure (bad prompt, expired token, real outage) parks a candidate forever. **And the self-healing is slower than it sounds:** `generate` runs on the batch cadence only, so a fully-stuck batch waits **12 hours**, which under live mode is real delay on dated seasonal content. **Fix shape, deliberately small:** set `status='failed'` (with the reason) on the exception, let it propagate to `_run_stage` so the existing Telegram surfacing fires, and add a retry counter so a genuinely transient failure still self-heals instead of being condemned on first error. **The general form is worth stating in `CLAUDE.md`, not just fixing here:** a swallowed per-item exception must always leave a state change behind — GL-7's per-stage isolation stops a stage's crash killing a run, and in exchange made per-item failures invisible at *both* levels. Owner decision 2026-08-08 was "known gap, don't fix before merge"; 08-09's 8-of-8 supersedes that. | one `except` block → `failed` status + notification + retry count |
| GL-47 | C | **🆕 Event-lookahead niches have a "too late" gate and no "too early" one, so seasonal content generates all year (soak finding 7).** `research._classify_by_timing` checks only `days_until_close >= MIN_EVENT_LEAD_DAYS` (14). There is no check on how far **before** a window it still makes sense to generate, so every one of the 6 fixed `EVENT_WINDOWS_2026` entries (`fall_cozy_aesthetic`, `holiday_peak`, `diwali`, `black_friday_cyber_monday`, `engagement_season`, `new_year_refresh`) classifies `go` for essentially the whole year — which is why holiday and fall candidates were generating in August. **Compounded by a second gap in the same function:** `research.collect_event_lookahead()` returns the same fixed set on every call with **no check against already-active candidates for the same niche**, so two batch runs close together produced near-duplicate candidates across all 6 event niches. **Together these two are a money leak, not a tidiness issue:** the same premature niches regenerate every batch, burning Replicate and Anthropic spend, and under live mode they can reach real listings. Fix: a lead-time window (`go` only within N days *before* `window_start`, alongside the existing lead before `window_end`) plus a dedup pass against non-terminal candidates for the same niche. **Do this before GL-46**, or at least in the same session — GL-46 makes stuck batches loud, and there is no point being loudly told about candidates that should never have been created. | two predicates in `research.py` → tests → no out-of-season `go` |
| GL-48 | M+C | **🟡 ANSWERED AND FIXED IN-REPO 2026-08-09 — one bug, not two; the live create (§7) is the only item left and it is owner-gated.** Findings: `docs/2026-08-09-gl48-findings.md`, branch `gl48-crop-and-template`. **§3's verdict: the pipeline half was already correct.** We sent the cover crop; the shared placeholder transform letterboxed it. **The brief's measurement method could not work as written, and that is the reusable part:** `productImages[]` are **1000×1000 square scene previews, not the submitted print file** — six identical dimensions, zero information about the file's aspect. What *is* readable is the rectangle the artwork occupies on the paper inside the preview: on candidate 42 the primary sizes place at 0.709 in 0.708 paper and 5x7 at 0.725 in 0.725 (both fill), while **10x24 places at 0.651 inside 0.420 paper** — the signature of a transform authored for 0.684. Which file was submitted was then settled by *content*, not shape: the warm-toned arc spans 0.175→0.815 of the master and 0.000→0.998 of the crop, and the placed region reads **0.024→0.983** ⇒ the crop. **§4: all twelve `templateVariantId`s are unchanged** (verified against the live API, not assumed) and **exactly two `static_config.json` entries were stale** — `5x7_portrait` → `011_mt_sunday_brook.JPG`, `10x24_portrait` → `004_doorframe_bottles_madeira_color.JPG`; both corrected. **The landscape template still has the one-placeholder defect** — all six variants share `009_boat_serene_bnw_scotland.JPG` — recorded, not built, and inherited by GL-18. **§5 shipped, with one deliberate deviation from the brief:** the crop URL gate was *removed* rather than repointed at `is_r2_configured()`, because that swap would have regressed `test_real_create_fails_loud_for_secondary_group_when_r2_not_configured` — with R2 absent it falls back to the uncropped master, which is exactly what that test exists to forbid on a live call. Returning the crop's `durable_url` unconditionally keeps live+R2, live-without-R2 (fails loud) and dry-run+R2 (the fix) all on **one branch**. Regression test `test_dry_run_create_sends_the_same_hosted_print_crop_as_a_live_one`, confirmed to fail against the old gate. **§6 not investigated** — §3 says one bug, so the reuse branch is not implicated; it is still wrong (the `wanted <= existing` guard compares the DB to itself and never to Gelato) and moves to GL-50/GL-51's session. **What is owed:** one owner-supervised live create, verified by `python scripts/gelato_template_check.py <product_id>` — pass condition is the 10x24 variant's placed aspect landing near **0.42**, not 0.65. **Candidate 42's listing `4549960823` was deliberately left alone** (GL-36's negative control). Two standing principles added to `CLAUDE.md`: *dry-run changes what a call does, never which code path reaches it*, and *verify this integration by measurement, not by status code*. Previously: **🟢 ROOT CAUSE FOUND 2026-08-09 by the owner’s manual check, and half-fixed at source — which makes finishing it the most urgent item on the board.** The Gelato **portrait template carried one image placeholder shared by all six size variants**; it now carries **three** (primary / 5x7 / 10x24). That is the fit-versus-fill mechanism this row hypothesised, confirmed from the dashboard rather than from the API. **It also partially un-strikes GL-22d** and exposes why GL-22a Q1 got it wrong: Q1 compared 8x12 (0.667) to 5x7 (0.714) and **could not have detected a fit difference at those ratios** — it proved a shared placeholder does not force a shared *image*, which is true and was the wrong question. **What is now owed, and it is not optional: `config/static_config.json` is stale.** All twelve entries still name the two old placeholders, so the live config no longer describes the live template and **the next `create-from-template` call would use placeholder names that may no longer exist.** Contained only because the three scheduled tasks are Disabled. **Do not guess the new names — re-resolve them from the template**, and **do not treat a `200` as proof**: GL-22a Q2 already established that Gelato returns `200` for changes it silently drops. Brief: `docs/2026-08-09-gl48-crop-and-template-brief.md`. **The diagnostic `GET` in the original filing is still worth running, and now more than before** — it discriminates *one* bug from *two*, and after the config change a surviving code-side bug becomes much harder to see. Original filing below. Previously: **🆕🔴 The 10x24 (and by inference 5x7) print still arrives at Gelato letterboxed — and the leading hypothesis says this is a *template-authoring* defect, not a pipeline one.** Owner evidence 2026-08-09: the Gelato dashboard for candidate 42's product (`5e15c0b4-…`, Etsy `4549960823`, "Mid-Century Line Art Botanical Poster…", updated 08-04) shows the 25x60 / 10x24″ variant with the artwork **fitted inside white bars**, which is the same visual defect the first live run produced and which GL-14 was supposed to have closed. **What was verified in the repo, and it exonerates the obvious suspects:** `db/base_artwork/42_10x24_crop.png` is **4053×9728 = 0.4166** (10/24 = 0.4167) and `42_5x7_crop.png` is 0.7143 — the crop maths is correct and the file is correct on disk; the 10x24 group was approved with a variant row (id 32) so it was in the create payload; `create_candidate_gelato_product` does resolve a per-variant `image_url`; `gelato_client` does send one `imagePlaceholders[{name, fileUrl}]` per variant; and there is already a regression test asserting exactly this (`test_real_create_sends_hosted_print_crop_not_raw_master_for_10x24`). **So either the right URL was sent and Gelato is not honouring it, or it never got sent — and GL-22a Q1 does not settle which.** Q1 proved two variants sharing an `image_placeholder_name` accept *different* `fileUrl`s; it tested 8x12 (0.667) against 5x7 (0.714), **both within ~4 % of the master's 0.684**. That experiment cannot distinguish "Gelato fills the placeholder with your file" from "Gelato **fits** your file into the placeholder transform saved in the template" — at 5x7 the two are visually identical. At 10x24 (0.4167 vs 0.684) a fit produces exactly the observed bars. All six portrait variants share one template *and* one placeholder name, and that placeholder's saved scale/position was authored against `003_flower_in_stream_madeira_color.JPG` — an ordinary portrait photograph, not a 1:2.4 panel. **The decisive test is one read-only call**, and it splits the item cleanly: `GET /v1/stores/{storeId}/products/5e15c0b4-…`, then per `productImages[]` entry download the signed `fileUrl` and measure its pixel aspect. **10x24 image reads 0.4167 → we sent the right file and Gelato letterboxed it** ⇒ this is **M**, a Gelato dashboard fix: the 25x60 variant's placeholder needs its own authored fill, and possibly its own placeholder name — **which would partially un-strike GL-22d**, retired on Q1's evidence. **10x24 image reads 0.684 → we sent the master** ⇒ this is **C**, and the first place to look is the `if product_row["gelato_product_id"]:` reuse branch, which builds no crops, sends no `fileUrl`s, and whose `wanted <= existing` guard compares the DB **to itself** and never to Gelato — a product created early with only the primary group's four sizes passes that check silently. **One fix owed regardless of which branch wins:** `_image_url_for` gates the crop URL on `config.is_live_mode("GELATO")` and otherwise returns the uncropped master, so **the crop path never executes in a dry run** — the gate belongs on `config.is_r2_configured()` (is the URL fetchable?), not on live mode, and until it moves, no dry run can ever rehearse this. **Blocker because it is the one open defect the buyer receives**; a letterboxed 10x24 is a refund and a review, not a log line. | one live `GET` + aspect measurement → M (re-author the template placeholder) **or** C (fix the reuse branch) → the dry-run gate fix either way |


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
| 1b | GL-30b | C | **🟢 CHEAPER NOW THAN WHEN IT WAS FILED — GL-30 shipped the parts it was going to need.** `scripts/corpus_backup.py` already owns the key scheme, the sha256 addressing, the write-once discipline and the manifest format; GL-30b is the *hook*, not the plumbing — persist one file plus its verdict at intake instead of 443 in a sweep. **The reason it still matters after GL-30:** the one-off is a snapshot with a date on it, and everything authored after 2026-08-08 is unbacked again the moment it lands. Original scope: **Authoring-time R2 sync (NEW 2026-08-01, owner — the long-term half of GL-30).** Every candidate lands in R2 as it is screened/authored, with its verdict, so the one-off never has to be repeated. Natural hook: `scripts/scene_intake.py`, which already runs the screen, the gate and prints the verdict block — it just does not persist anything durable. Same write-once key discipline as GL-30. Owner-deferred to post-go-live. |
| 1c | GL-31 | C | **The stall reminder ping (NEW 2026-08-01, owner — the deferred half of GL-22c's stall rule).** Before a group ages out of review, re-send its digest entry as a nudge so the owner has a chance to act. Deferred so v4.12's stall rule stays a predicate rather than growing a stage. **Worth pulling forward rather than letting it sink:** with no reminder, the only signal a group is aging out is the owner remembering an untapped digest entry, and a size that times out **cannot be added back** (GL-22a Q2 — recovery is a from-scratch re-publish). Scope when it lands: a `groups.reminder_sent_at` column, a send point, and a threshold constant below `GROUP_REVIEW_STALL_DAYS`. |
| 1d | GL-39 | R (recurring) | **✅ SET UP 2026-08-06 — this is live as a Cowork scheduled task and needs no further action; it is listed here for traceability, not as work.** Task id `gl39-etsy-creativity-standards-api-check`, cron `0 9 1 2,5,8,11 *` (09:00 on the 1st of Feb/May/Aug/Nov), enabled, first run 2026-08-06, next 2026-11-01. **It was never ticked in this document, which is the small failure worth recording:** a recurring item that is genuinely done can sit on a board looking open indefinitely, because nothing about it ever changes state again. Prompt lives at `C:\Users\QVajd\Claude\Scheduled\gl39-etsy-creativity-standards-api-check\SKILL.md` — edit there, not here. Original scope: **The Creativity Standards API re-check — a standing quarterly item (NEW 2026-08-06, from GL-37's answer).** GL-37 established that `production_process` and `tools_used` are settable **only** in the web listing editor, and that the editor's only save action activates the listing. **That is a fact with a shelf life**, and the tracking artefact already exists: **`etsy/open-api` GitHub Discussion #1630**, opened 2026-06-22, unactioned as of 2026-08-06. **Scope of each check (~10 minutes, no code):** re-read Discussion #1630 for an Etsy staff reply, a linked PR or a changelog entry; if it looks shipped, confirm against a **full raw `GET /listings/{id}` dump** rather than a field-name grep — GL-37's own method, and the thing that makes the answer trustworthy. **Cadence: quarterly**, or immediately on any Etsy API changelog entry mentioning listing create/update. **Why this is worth a numbered row rather than a mental note:** the manual per-listing tick is the single remaining hole in GL-7's unattended premise, it collides with GL-29 (see that row), and the day it closes is the day both problems disappear at once — but nobody will notice that day unless someone is looking. **Candidate for a Cowork scheduled task** rather than a memory: it is exactly the shape — recurring, small, external-source-driven. |
| 1e | GL-29b | C+T | **Programmatic activation, parked (was GL-29, cancelled from the go-live gate 2026-08-06).** Reopen only on one of two triggers: **(a)** GL-39 reports Discussion #1630 shipped, so the AI-disclosure tick becomes API-settable and programmatic activation stops being *less* compliant than the manual path; or **(b)** listing volume makes the per-listing dashboard visit the real bottleneck. **The build is small and stays small** — `etsy_client.update_listing_state` is already written, dry-run-aware, unit-tested and deliberately unwired; the work is the `ETSY_ACTIVATE_LISTINGS` flag (default false), one call site at the end of the publish path, rewriting the guard test to "never activates *unless the flag is on*", loud logging with the listing id, an `activated_at` column, and the `inactive` rollback shipped in the same PR (Etsy's `active` can never return to `draft`). €0.20 per activation, charged in Developer Mode too. |
| 1f | GL-43 | D | **✅ DECIDED AND PARTLY APPLIED 2026-08-08 — owner agreed with the findings; the doc-only half is live in `safe_evergreen_bucket.md` v2, the rest is now GL-44.** **What went in:** 9 subject-seed additions (`vintage botanical print`, `antique botanical illustration`, `wildflower print`, `bauhaus print`, `bauhaus poster`, `art deco poster`, and a new Japanese/East-Asian bucket), 3 BLOCKED removals (`moon phase print`, `single line drawing art`, `continuous line illustration`), and 2 at-risk flags kept in the list but annotated (`star chart poster`, `lunar cycle art`). Bucket goes 38 → 44 terms. **What did NOT go in, and this is the important half:** the colour-family and room/placement modifier buckets — **the delta's own highest-value finding** — because this file is a flat list feeding *both* `research.py` and `art_brief.py`, so appending `bedroom wall art` sends a room word into the art brief, which is the exact leakage that made the first live run print lifestyle mockups as the artwork. Also held back: tag-safe short forms (8 terms over Etsy's 20-char cap) and the seasonal windows (`EVENT_WINDOWS_2026` is code). **Two new tests guard the split** — one asserts the three BLOCKED terms stay out, one asserts no room or colour word ever appears in the bucket, so a future flat append fails loudly instead of quietly poisoning the prompts. One existing test changed: it asserted `moon phase print` was present. Original scope: **The GL-10b keyword delta — one owner decision, and it is the only GL-10b artefact that touches what the pipeline *makes*.** Proposal: `docs/2026-08-07-gl10b-keyword-delta.md`. **Nothing is applied**, deliberately: `docs/safe_evergreen_bucket.md` is `research.py`'s live input and carries an owner-approval note in its header, and `EVENT_WINDOWS_2026` is code. **What is proposed.** *Additions:* two entirely new **modifier** buckets — **colour-family** (neutral, beige, sage green, terracotta, dusty pink, navy blue, black and white, pastel…) and **room/placement** (bedroom, kitchen, nursery, living room, hallway, entryway, office, bathroom) — plus additions to the mid-century, botanical and a new Japanese/East-Asian bucket. This is **the highest-leverage, lowest-risk finding in the sweep** (R3): it is a large, cheap, entirely missing axis, it recurs in every niche SERP and in Bestseller-badged titles, 6 of 10 shops run room sections, and **it changes nothing about what the art looks like**. *Removals:* **`moon phase print` — BLOCKED**, its SERP is 4/10 dated 2026/2027 calendars and 4/10 personalised, anchored by a 3-listing shop whose single section is literally named `2026`; and `single line drawing art` / `continuous line illustration` — BLOCKED by personalisation occupancy. **The delta adds a third tag the bucket never had — BLOCKED** — for terms that pass the flat-volume test but whose SERP is owned by a product the pipeline physically cannot make. The bucket was validated on *terms* and never against *who ranks for them*; this is the first time it has been, and one entry fails. **Two things make this a decision rather than a paste.** (a) Colour and room words are **modifiers, not seed terms** — "beige" alone is not a niche — so the value is in *combination*, which makes it as much a change to how `art_brief.py` and the title formula consume the bucket as to the bucket itself (Part D). (b) **Room words are exactly where scene-word leakage will happen** — "bedroom wall art" is one careless hop from the scene words that made the first live run print lifestyle mockups *as* the artwork. The delta routes them **away from `art_brief.py`** for that reason, and any implementation must keep them there. **Two caveats carried honestly:** `sage green` and `terracotta` are proposed evergreen on the strength of *current* occupancy and are flagged for re-check, not asserted as permanent; and the whole delta is built from **title tokens, because Etsy no longer exposes tags to buyers at all**. |
| 1f-bis | GL-44 | C | **🆕 The modifier-class schema change — GL-43's deferred half, and it carries GL-43's best finding.** `safe_evergreen_bucket.md` becomes classed rather than flat: **subject seeds** (research + art brief), **style modifiers** (research + art brief — `vintage`, `neutral`, `black and white`), **placement modifiers** (research + listing copy only, **never `art_brief.py`**), and **tag-safe short forms** (tag generator only). Then `load_safe_evergreen_terms()` gains a class filter and each consumer asks for what it is allowed to see. **The value is real and was measured:** colour and room words are a large, cheap, entirely missing axis — they recur in every niche SERP and in Bestseller-badged titles, 6 of 10 sampled shops run room sections, and **they change nothing about what the art looks like.** **The risk is equally real and is the whole reason this is code:** the safety property is currently enforced by absence (the words simply are not in the file, and two tests keep it that way); after GL-44 it is enforced by routing, which is a stronger claim needing stronger tests. Do it **with or just before GL-10c** — the tag-safe short forms exist only to serve GL-10c's tag generator, and building that generator first means inventing truncations at draft time, which the spec forbids. Also re-check `sage green` and `terracotta` when it lands: they were admitted on *current* occupancy, flagged as a 2020s palette moment rather than a permanent one. |
| 1g | GL-10c | C | **🆕 The listing-copy template build — spec written, build post-launch.** Spec: `docs/2026-08-07-gl10b-listing-copy-spec.md`, targeting `compliance_draft.DRAFT_TEXT_PROMPT_TEMPLATE`. **Title:** five comma-separated slots, subject front-loaded, brand name never, 15-word ceiling, no word more than twice. **Tags: the hard constraint is 20 characters each**, and that **disqualifies five terms already in `safe_evergreen_bucket.md`** outright (`mid century modern wall art` 27, `continuous line illustration` 28, `minimalist landscape print` 26, `geometric shapes wall art` 25, `single line drawing art` 23). The length budget must be a **first-class generation constraint, not a post-hoc trim** — long phrases route to the *title*, which has no cap, while their short heads go to tags. **GL-10c's first task is plumbing, not prompting:** the title formula needs the artwork's colour and the niche's room word threaded through to draft time, and they are not there today; a fallback that drops those slots must exist for old rows. **Two things this spec deliberately does NOT do:** it does **not** reintroduce a prose AI disclosure (`DISCLOSURE_TEXT` stays `""` per GL-37 — and the spec says why in the spec, so a future session cannot restore it by accident), and it does not attempt head terms. **R1 is the reason:** sorted by reviews with digital downloads excluded, **9 of 9** non-ad results for `wall art print` are personalised or customer-supplied-file products — custom lyrics, pet portraits, photo canvases. **The head of "wall art" is a personalisation market and the pipeline cannot enter it**, so the ranking strategy is long-tail aesthetic descriptor, full stop. Depends on GL-43 for the lexicon. |
| 1h | GL-40 | IR+C | **🆕 Set / bundle products — the basket-size lever, and QhotoArt has no path to it (R4).** **This is a finding with a size, not a nice-to-have:** it is the single mechanism by which every high-volume shop in the sample raises order value. **7 of 7** gallery-wall results and 4 of 8 botanical results sell a multi-print set, with the quantity stated **numerically in the title** ("Set of 3", "4 Piece"); **6 of 10** shops run a set/bundle section; TheWorldGallery's `SETS OF 3` section alone holds **1,369 listings**; LotusNurseryArt productises it further with `CREATE YOUR SET` and `MIX & MATCH`. **Why it is post-launch and not a gate item:** it is a Gelato product-shape change, not a copy change — a set is a different product with different variants and different pricing, and v4.12's one-listing-per-artwork model has no representation for "three artworks, one listing". Filed as its own row rather than implied by GL-10c precisely so its size is visible. |
| 1i | GL-41 | note→IR | **🆕 Every listing's URL is permanently frozen to Gelato's auto-generated title (R13). Flagged, unsolved, deliberately not fixed here.** Etsy, verbatim: *"Your listing's URL is based on the title you enter when you first publish the listing. Once it's published, the URL won't change again, even if [the title changes]."* Under the Gelato-pushes-we-patch architecture, Gelato creates the listing and the pipeline PATCHes the title afterwards — **so the patched title never reaches the slug.** **The cost is bounded and worth stating precisely: Google SEO only.** Etsy's *internal* search reads the title field, not the slug, so nothing about ranking inside Etsy is affected. **The reason it is a row and not a fix:** the only remedies are architectural — take listing creation back from Gelato (which collided with Gelato's push in the live run, the exact reason the current design exists) or influence Gelato's product title at create time. Both are real projects. Re-open alongside GL-29b/GL-11 if Google traffic ever matters. |
| 1j | GL-42 | M | **🆕 The About section's unused media slots (R12).** Etsy's About accepts **up to 5 images and a video**, and QhotoArt uses none. **For an AI-art shop specifically, this is the strongest available trust surface** — process shots, the print in hand, packaging — because it is the one place a buyer can see that a physical object with real production standards sits behind a generated image. Cheap, owner-manual, no code, no dependency. Out of GL-10b's scope by its own admission; worth doing once there are real prints to photograph. |
| 1k | GL-12 | M | **🔴 MOVED from the go-live board 2026-08-08 (owner) — turned out not to be a zero-cost parallel task.** Google Trends API alpha registration requires a Google Cloud Console project first (GCP project, Workspace linkage, billing attached) before the application itself can be submitted. That's real setup, not a "how-to → submitted" afternoon item, so it no longer belongs on the critical path. Original scope unchanged: apply for alpha access, zero direct cost, runs in parallel with everything else once picked up. |
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
| GL-32 | C | **The orphan gap session 2 could not close (NEW 2026-08-02).** With create-once, the orphan-delete-before-retry branch became unreachable and was **removed**; idempotency now rests on "never create twice when `gelato_product_id` is set". **That leaves one hole, pre-existing and now the only one:** a crash between the Gelato `POST` returning and the id-recording `UPDATE` committing orphans a real Gelato product **no DB sweep can see** — there is no row pointing at it. Cheap mitigations to weigh (do not build blind): write an intent row *before* the POST and reconcile after, or a periodic list-products-vs-DB reconciliation. **Also folded in:** `discard_superseded_attempt` now deletes images but leaves `group_product_variants` rows behind (dropping them tripped the new post-create guard on re-render) — decide whether that residue is harmless or wants a scoped cleanup. Small, real, and invisible until it bites. |
| GL-35 | C | **✅ BUILT 2026-08-05 inside GL-7 (`7e82444`, `f153266`, `bc229e9`) — pending the same merge as its parent.** `db/schema.sql` gained a `schema_version` table; `migrate.py` chains the six existing root-level `migrate_*.py` scripts plus the new `migrate_gl36_listing_missing.py` in order and records progress; `--check` is **genuinely read-only** (that took its own commit) and is called at the top of both entrypoints, so a stale schema is a clean refusal rather than a crash three stages deep. **One real bootstrap defect found and fixed in-flight:** the production DB had never been through `init_db` — only the individual migrate scripts — so `schema_version`/`heartbeats` did not exist and `check()` leaked a raw `OperationalError`; `migrate()` now calls `init_db` first and a missing table is read as version 0. **That is the same class of finding as GL-13's R0**: the code was right about a database that had never actually been operated on. The worktree DB is now at version 7; **the canonical repo DB has no `schema_version` table at all** → GL-38. Original scope: **Nothing runs the migrations (NEW 2026-08-03, GL-13 finding — the first thing R0 hit).** Six `migrate_*.py` scripts sit at the repo root and **not one is referenced by any code, test, doc or runbook** — `grep migrate_ pipeline/ README.md` returns nothing. The live DB was still on the pre-v4.12 schema; GL-13 stalled until both were run by hand. **This is a deploy-hygiene gap that gets worse, not better, with GL-7:** a scheduled function on a host has no operator standing by to notice a missing column at 03:00, and the failure mode is a mid-run crash, not a clean refusal. Cheap shape: a `schema_version` row, one idempotent `migrate.py` that applies pending scripts in order, and a **fail-fast check at pipeline start** that refuses to run against a stale schema rather than discovering it three stages in. **Fold into GL-7's kickoff** — it is a soak prerequisite, not an independent project. Note `migrate_v412_gallery.py` **rebuilds `groups`** (SQLite cannot widen a CHECK in place), so "idempotent" here has to mean *actually* idempotent, not "safe to re-run by inspection". |
| GL-36 | C | **🟡 CODE BUILT 2026-08-05 inside GL-7 (`d79c6d7`, `d3c77a7`); the proof is night 2's, and the repair has not happened.** `pipeline/reconcile.py` ages out stranded `generating` candidates and marks `published` rows whose Etsy listing 404s as `listing_missing` (a widened `group_products.status` CHECK, migrated). **Positive matching only, as briefed:** a definitive 404 marks the row; timeouts, 401s and 5xxs are skipped and logged, so a bad afternoon at Etsy cannot mark the shop dead. **What is not done:** the reconcile calls Etsy, so it **cannot fire on a dry-run night** — night 1 proves nothing here. Candidates **40 and 41 still read `published`** against `4548623111`/`4548892148`, both of which 404; candidate 42's row also still reads `published` against `4549960823`, which is still a live draft. Confirmed in both DBs 2026-08-06. **The night-2 checklist item is therefore concrete:** with live mode on, the reconcile should flip exactly 40 and 41 and leave 42 alone — three rows that make a clean, falsifiable test the plan did not have before. Original scope: **Rescoped 2026-08-05 (owner) — one item: the DB and the live world drift apart, in both directions.** The original half is below. **The second half, found by GL-33/34:** candidates 40/41 (GL-13's R3/R5) still carry `published` rows with `etsy_listing_id`s that **404 live** — the listings were deleted during that session's documented cleanup, and the cleanup instructions never touch the DB. That is a *deliberate* desync, not a bug, which is exactly why it wants an item: it cost the GL-34 session its planned control listing and forced a fresh live candidate. **Both halves are the same failure:** a row asserting something about the world that stopped being true, with nothing that notices. Cheap shape to weigh together — a reconcile pass (`GET` each non-terminal/published row's external id; mark `listing_missing` on a 404) plus an age-out for `generating`, and cleanup runbook steps that update the DB in the same breath as the live delete. **Unrepaired right now:** candidates 40/41's rows, and candidate 42's listing `4549960823` still live as a draft. **Folded into GL-7's DoD** alongside the stall-predicate proof. Original scope: **Stranded `generating` candidates have no recovery path (NEW 2026-08-03).** 29 candidates (ids 5–34) sat in `generating` from earlier test rounds and were cleared **by hand** with a recovery note; the DB backup holds them. Nothing sweeps or ages out a row that entered `generating` and never came back — which is exactly the state a crash, a Replicate timeout or a killed process leaves behind. GL-16's resilience work covers interrupted *stages*; this is the residue when the process itself dies between them. Same argument as GL-35: harmless while a human runs each round, a slow leak once GL-7 runs unattended. **Fold into GL-7's DoD** alongside the stall-predicate proof. |
| GL-49 | M+C | **🆕 Three candidates are frozen as dry-run stubs and will never become real listings (soak finding 5).** Candidates **44, 47 and 48** were fully approved and "published" with `gelato_product_id='DRY_RUN_PRODUCT_ID'` / `etsy_listing_id='DRY_RUN_ETSY_LISTING_ID'` *before* `GELATO_LIVE_MODE`/`ETSY_LIVE_MODE` were flipped to `true`. `group_products.status = 'published'` is terminal — only `publish_failed` is retried, by `retry_publish_failed_groups` — so nothing will ever revisit them. **The manual repair is small** (clear both id columns, set the status back to a re-publishable state, per candidate, against a backed-up DB per CLAUDE.md §4) **and the code fix probably should not be built**: "a dry-run success that predates the live flip" is a one-off state, and a general redo-for-real path is more machinery than the situation deserves. **The cheap durable fix is a guard, not a recovery path** — refuse to write a terminal `published` row whose ids are the dry-run sentinels, or tag those rows `published_dry_run` so they are visibly not real. Do the manual repair **after** GL-38's merge and DB reconciliation, not before: repairing rows in a database that is about to be superseded is work done twice. |
| GL-50 | C | **🆕 `migrate.py --check` is neither read-only nor correct from the CLI (GL-38 finding, 2026-08-09).** `main()` does `db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH` **unconditionally**, so `--check` is consumed as the database path: `sqlite3.connect` then **creates an empty file literally named `--check`** in the repo root, `_current_version` reads 0, and it raises `schema_version is 0, expected 7` — **a stale-schema false alarm against a perfectly good database, plus a littered file.** The correct invocation is `migrate.py db/qhoto.sqlite3 --check`, which returns `schema_version=7, up to date`. **Two reasons this is worth a row rather than a one-line fix in passing.** (1) **It directly contradicts a commit that exists to prevent it** — `f153266 fix(gl35): make migrate.check() genuinely read-only` made the *function* read-only, and nobody checked the *entry point*, which is the only half an operator ever touches. (2) **It fails in the alarming direction on the one command a human runs when something is already wrong**, i.e. during an incident, when a false "your schema is stale" is at its most expensive. The library path is unaffected — `run_hourly.py:72` and `run_batch.py:116` call `migrate.check(db_path)` directly — so **the fail-fast guard itself is sound**; this is purely CLI argument handling. Fix: parse flags properly (`--check` is a flag, not a path), refuse to create a database that does not already exist on the check path, and add the two-line test that would have caught it. **Note it also means the kickoff's own Phase C step 10 verification was misleading** — a procedure that tells you to run a broken command is worse than one that omits it. | argv parsing + a no-create guard + one test |
| GL-51 | C+M | **🆕 The DB references artefacts by absolute path into a git-ignored directory, and nothing detects it when they vanish (GL-38 near-miss, 2026-08-09).** Retiring the GL-7 worktree would have **succeeded silently and orphaned the freshly promoted database.** Its `db/` held **1.6 GB of git-ignored artefacts, 289 files of which existed nowhere else** — the base artwork and mockups for candidates 43–86, i.e. exactly the rows the promoted DB references — and **24 candidate rows stored *absolute* `base_image_local_path` values pointing into it**. `git worktree remove` reports success either way. It was caught and repaired (robocopy the 289, rewrite the 24 paths, verify every target exists — **0 unresolvable paths across all 62 candidates**), but **only because someone thought to look.** **The defect is not the worktree; it is the two properties that made the worktree dangerous, and both survive the repair.** (1) **Absolute paths in a portable database.** `base_image_local_path` is machine-specific, which makes the DB non-portable by construction — and **GL-3 has a pre-committed VPS fork**, so this will recur the first time the pipeline moves host, with no worktree involved. Store paths relative to a configured artefact root and resolve at read time. (2) **No integrity check exists that reads the DB and asks whether the files are there.** `PRAGMA integrity_check` validates SQLite's own structure and says nothing about the filesystem the rows point at. A `--check`-style artefact sweep (every `base_image_local_path`, every `product_images` local row, count resolvable vs missing) is perhaps forty lines and turns a silent catastrophe into a startup refusal — and it is the natural companion to GL-35's schema guard, which already refuses to run against a database in the wrong *shape*. **The relationship to GL-30/GL-30b is worth stating so this is not mistaken for a duplicate:** GL-30 backed up the *mockup corpus*, and R2 holds the base artwork when configured, so the *bytes* are largely recoverable. **What is not recoverable is the mapping** — which row points at which file — and that is precisely what the 24 rewritten paths were. |
| GL-28 | M | **SynthID.** Every Nano Banana output carries an invisible watermark, and the store's photography is now all Nano Banana. Not an Etsy problem — the artwork is disclosed via `who_made: i_did` — but it should be a **recorded, conscious choice** rather than a thing discovered later. **2026-08-03: that reasoning now depends on GL-34.** If the disclosure moves off `i_did`, re-read this line before relying on it; the description-text disclosure is the part that survives either way. |

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
6. **GL-22** ✅ **BUILT 2026-08-02**, 635/635 green — but on a branch.
   **→ GL-23b (merge to master) is now the head of the critical path**, and
   GL-13 cannot start until it lands. PRD ✅ signed off; built in two
   sessions:
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

**Track D — manual and parallel, owner-driven:** GL-10 storefront now,
**GL-30** the one-off corpus backup (small, independent,
must not push anything else right). **The GL-11 email now waits for GL-13 to
pass** (owner, 2026-08-02) — a deliberate spend of uncompressible lead time to
avoid opening an external conversation about an unproven publish path. From
GL-13's pass onward it is the only critical-path item on someone else's clock.

**Then, in order (owner sequencing confirmed 2026-08-02; revised 2026-08-03
after GL-13's pass):**

8b. **GL-23b** ✅ merged (`7cbaee7`). **The non-additive `groups` rebuild in
    `migrate_v412_gallery.py` runs as part of this** — back the DB up first.
    *(Post-hoc: it was not run as part of it. Nothing runs migrations at all
    — GL-13's R0 found the live DB still on the old schema. → GL-35.)*

8c. **GL-33 + GL-34** ✅ **DONE 2026-08-04** (`14a2d10`, PR #6). GL-33 shipped
    with live proof on candidate 42; GL-34 closed as a read-side field-name
    artifact, no code. Kickoff/PRD: `docs/2026-08-04-gl33-gl34-kickoff.md`;
    findings: `docs/2026-08-04-gl34-findings.md`. **The session's own
    judgement call is worth recording:** it hit a blocked control (R3/R5
    deleted live, DB stale), and it **stopped and asked** rather than
    inventing a substitute — the substitution to candidate 42 carries owner
    sign-off. That is the behaviour the plan wants from a live session.

8d. **GL-7 + GL-8/GL-3 — the chosen next track (owner, 2026-08-05).**
    Chosen over GL-29 even though GL-29 is now unblocked and much cheaper.
    **The reasoning, stated because it looks backwards:** GL-29 is a flag,
    one call site and a rewritten guard test — it will cost the same session
    in three weeks as it costs today, and each live exercise of it burns
    €0.20 and one irreversible listing. GL-7 is the *only* item left whose
    duration is uncertain, it is the only one with an unattended soak that
    cannot be compressed, and it carries two riders (GL-35, GL-36) that make
    every subsequent live run cheaper. Spending the next session on the cheap
    item would be optimising the wrong end of the schedule. **GL-29 also has
    one gate left that GL-33/34 did not clear — GL-37** — so pulling it
    forward would mean either taking GL-37's decision under time pressure or
    activating with it open. Kickoff/PRD: `docs/2026-08-05-gl7-cron-prd-and-
    kickoff.md`. **GL-8/GL-3 (host research + decision) is section 0 of that
    document, not a separate track** — it was always GL-7's first gate and
    has been open since 2026-07-22. **Owner-manual items run in parallel and
    cost no build time:** the GL-11 email (still the only clock you do not
    control), GL-37's dashboard/API re-check, deleting candidate 42's draft
    listing, and repairing 40/41's rows.

9. **GL-13 + GL-17** ✅ **PASSED 2026-08-03.** One live pass
   covering the custom gallery and its first guarded upload, the v4.12
   single-listing publish, the human Reject button, the crop-to-Gelato
   confirmation, and session 2's six live-only handovers. Chosen over
   starting GL-7 first, on the reasoning that debugging a freshly-rewritten
   publish path inside an unattended overnight soak is the expensive way to
   find v4.12's bugs. **GL-8/GL-3 (host decision) can run in parallel** to
   keep the long pole moving while GL-13 waits on owner availability.
10. **GL-29** activation behind its flag, proven with one paid live activation
    (Developer Mode proves the call, not the shopper's view). ~~**Now gated on
    GL-33 + GL-34**~~ — ✅ both cleared 2026-08-04. **The remaining gate is
    GL-37's decision**, and the remaining sequencing constraint is that it
    runs after GL-7 by owner choice (8d), not by dependency.
11. **GL-11** Developer Mode off → the visual confirmation GL-29 could not
    get. **The email itself no longer waits for step 10; only the Dev-Mode-off
    confirmation does.**
12. **GL-7 + GL-8/GL-3 — the long pole, and after 8c the only substantial
    build left.** Its kickoff now carries two riders GL-13 produced:
    **GL-35** (a migration runner and a fail-fast schema check — a soak
    prerequisite, because an unattended host has no operator to notice a
    missing column) and **GL-36** (stranded `generating` recovery). Neither
    is big; both are the kind of thing that only bites unattended.

**Parallel track while the soak runs (2026-08-06).** The soak occupies two
nights of wall-clock and **zero hours of anyone's attention** — it is the
first item on this plan that advances while you do something else, so the
question is what to put beside it. In descending order of value per minute:

1. ~~**The GL-11 email — send it today.**~~ ✅ **SENT 2026-08-06.** Draft:
   `docs/2026-08-06-gl11-developer-mode-email-draft.md`. Its lead time now
   runs in parallel with the soak, which is exactly what it was for.
   **Consequence worth stating: the plan no longer has a single item waiting
   on an external party.** Everything left is work someone here does. Next
   action on this row is a reply from Etsy, or a same-thread nudge at ~10
   business days.
2. ~~**GL-37 — the API re-check.**~~ ✅ **ANSWERED 2026-08-06.** Not
   settable, no shop-level default, tracked upstream as Discussion #1630.
   **It resolved in the direction that adds a permanent manual step rather
   than a code change** — and it did the useful thing a research item can do:
   it changed GL-29 from "cheap and unblocked" to "needs a decision about
   whether to build it at all". Recurring re-check → GL-39.
3. ~~**GL-10 — the storefront.**~~ ✅ **RESEARCHED AND SPECIFIED 2026-08-07
   (GL-10b).** It was the single largest block of parallelisable work on the
   board; it is now **two much smaller things**, and the split is the useful
   part.
   **3a. The paste-and-click half — do this next, it is the highest value
   per minute left on the board.** Tagline, section rename, About, policies:
   `docs/2026-08-07-gl10b-storefront-checklist.md`, ~30 minutes in Shop
   Manager, blocked by nothing, touching no code and no live listing.
   **Two items inside it are not clerical and should not be batched with the
   rest:** the returns wording needs a view taken on EU distance-selling law
   (the artefact recommends simply accepting 14-day returns and says plainly
   it is not legal advice), and **the "an AI generator" tick is the publish
   action, not a pre-flight tick** — it belongs with GL-11, not with this.
   **3b. GL-10d — the banner rebuild.** A small Claude Code session against
   a self-contained decision document. **The icon half is free: upload
   `qhoto-shop-icon-500.png` and stop** — no rebuild, no code. **The same
   caveat as GL-30 applies to the build half:** it is a coding session while
   two live trees exist, so either wait for GL-38's merge or keep it strictly
   to `assets/brand/` (which, conveniently, is exactly where it lives —
   `build_final.py` and `verify.py` and nothing else). Doing it *before* the
   merge is defensible for that reason; doing it in the same session as
   anything touching `pipeline/` is not.
   **3c. GL-43 — the keyword delta.** ✅ **DECIDED, APPLIED AND COMMITTED
   2026-08-08.** The reasoning below is why it was worth taking before
   go-live rather than after, and it held: `moon phase print` is live input to
   `research.py` today and its market is dated calendars, so every day it
   stays in the bucket is a day the pipeline can spend a generation on a
   niche it cannot win.
4. **Delete candidate 42's draft listing** (`4549960823`) — one minute, and it
   removes the last live artifact from the GL-33 session. **Do it after the
   soak's live night**, not before: GL-36's reconcile wants 42 alive as the
   negative control (see the GL-36 row).
5. ~~**GL-30 — the corpus backup.**~~ **✅ DONE 2026-08-08 (`34a8b15`).** It
   took the second option in its own caveat — built strictly as a new script
   inside the soak's tree, touching nothing that already existed except by
   importing it. **That is why it was safe to run against two live trees, and
   also why nobody on master could see it.** Both halves of that sentence are
   the lesson.

**What not to start:** GL-29. It is cheap, it is unblocked apart from GL-37,
and it is still wrong to begin — it is the one-way door, and the soak may yet
produce findings that change the publish path it activates.

**Go-live gate (2026-08-06, GL-38 added):** GL-23 ✅ **+** GL-19b ✅ **+**
GL-22a ✅ **+** GL-22b ✅ **+** GL-22c ✅ **+** GL-22d ✅ struck **+**
GL-22 ✅ built **+** GL-23b ✅ merged **+** GL-13/17 ✅ clean **+**
GL-33 ✅ gallery de-contaminated, proven live **+** GL-34 ✅ partner field
confirmed present (the "missing" read was the wrong field name) **+**
GL-37 ✅ answered 2026-08-06 (not API-settable at any level; **the manual
per-listing step is consciously accepted**, and the recurring re-check is
filed as GL-39) **+** GL-38 the soak's tree merged and the scheduled tasks
re-pointed **+** GL-7 cron running with a clean
overnight soak (carrying GL-35 + GL-36) **+** GL-10 storefront
**✅ DONE 2026-08-08 — every item on
`docs/2026-08-07-gl10b-storefront-checklist.md` tackled, closed by the banner
upload** **+** **GL-10d ✅ DONE 2026-08-08 — banner rebuilt and uploaded
(the live banner's four failures were structural, not aesthetic)** **+**
~~GL-29 activation proven behind its flag~~ **struck 2026-08-06 — publishing
is a deliberate manual act by the owner, and GL-37 made that Etsy's design
rather than a limitation of ours** (parked as GL-29b) **+** GL-30 ✅ corpus
backed up 2026-08-08 (443 files / 381.5 MB, `34a8b15`, arrives on master with
GL-38) **+** GL-11 Developer Mode reverted.
**Fifteen of eighteen ticked (2026-08-08, latest)** — GL-10 and GL-10d both
ticked the same day: the banner upload was simultaneously GL-10d's last step
and the last open item on GL-10b's storefront checklist, so one action closed
two gate rows. Earlier that day GL-10d had joined the gate unticked, which is
why the denominator is eighteen. GL-37 ✅ joined the ticked side on 08-06,
GL-29 left the gate entirely, GL-38 joined it unticked, and GL-7 stays
unticked until the soak passes *and* master carries it.
**What is left is exactly three things: finish the soak, merge it (GL-38),
and wait for Etsy's reply (GL-11).** **None of them is a build.** GL-30 was
the last one, and it closed the same day it was scoped. Two of the three sit
on someone else's clock — the soak's and Etsy's — so the honest statement of
where this project stands is: **the code is done and we are waiting.** The
only work anyone can pull forward now is post-launch (GL-27, GL-44, GL-12),
and the one *sequencing* question left is whether GL-38's merge waits for the
soak to finish or lands as soon as it is green.
**GL-10b's honest effect on the gate: it did not remove an item, it
converted one.** GL-10 went from an unspecified owner-driven overhaul to a
30-minute paste plus a bounded coding session — which is a real reduction in
*uncertainty* even though the count moved the wrong way. That is the trade
research is supposed to make, and it is worth naming rather than hiding
inside a number. Recounted 2026-08-05; the previous
"eight of fifteen" and its predecessors were miscounts against this same
list, which is worth noting only because a gate you cannot count is a gate
you are not really using. What remains is **one substantial build (GL-7,
carrying GL-35 + GL-36)**, two cheap builds (GL-29, GL-30), one research +
owner decision (GL-37), and two owner-manual items (GL-10 storefront, GL-11
Developer Mode — whose email should already have gone out). **Nothing left
on the board is both uncertain and expensive except GL-7** — which is the
whole argument for 8d.
**Longest poles: (1) GL-7 cron + soak; (2) GL-22 → GL-13 → GL-29 → GL-11.**
Note that the last pole is now a *chain* of four, three of which are cheap —
the expensive one is GL-22, and GL-11's external lead time runs in parallel
with all of it. **What changed 2026-08-02:** GL-22 is **built** — the
expensive pole is spent, and what replaces it on the chain is
**GL-23b → GL-13 → GL-29 → GL-11**, of which only GL-13 is substantial.
GL-7 remains the long pole and is now unambiguously **the** long pole; it
picked up one new DoD item (prove the stall predicate fires, by lowering
the constant). GL-13's delta grew by six live-only items handed over from
session 2.
**What changed 2026-08-03:** GL-13 passed, so the second pole collapses to
**GL-33/34 → GL-29 → GL-11**, all three cheap. **GL-7 is now the only
expensive item between here and go-live** — every other open blocker is a
session or an email. The plan's shape has inverted from "one big build after
another" to "one big build, and a to-do list": if GL-7 slips, go-live slips;
nothing else on the board can say that, with the single exception of GL-11's
external lead time, which is why the email should not wait another day.
**What changed 2026-08-05:** the second pole collapses again, to
**GL-37 → GL-29 → GL-11**, and only GL-11's lead time is uncompressible.
**There is no longer a second pole in any meaningful sense — there is GL-7,
and there is a to-do list.** The one thing that can still surprise this plan
is the soak, which is precisely the thing that has never been run. Note also
that the email is now *two days* older than the sentence above complaining
about it; if it has not gone out, that is the single cheapest correction
available on the whole board.

**Track E — the soak's residue: merge cleanly first, then fix (2026-08-09):**

The soak's pause changes the order of everything left. Merge first, fix on
master, re-soak short and targeted. The reasoning for each step is in its row;
this is the order and the rationale for the order.

**E0. GL-38 — land the branch.** Head of the critical path. **Full
procedure: `docs/2026-08-09-gl38-merge-kickoff.md`** — written 2026-08-09
because the five steps below turned out to describe a merge that does not
exist. **What the survey found that this sequence assumed away:** the branch is
21 ahead **and 2 behind** (GL-10d and GL-43 landed during the soak); there is
**one real conflict**, `tests/test_research.py`, where both sides added tests
and **both additions must survive**; **one untracked file
(`docs/superpowers/plans/2026-08-05-gl7-cron-orchestrator.md`) will refuse the
checkout** outright; **GL-37's `compliance_draft.DISCLOSURE_TEXT = ""` change
has been sitting uncommitted on master since 08-06** and must be committed on
its own before the merge, not into it; and **~11 docs the board cites as
evidence are untracked**, so one `git clean -fd` during cleanup would delete
the documentary record for GL-10b, GL-11, GL-30 and GL-7's own PRD.
**And the database question is settled rather than open** — see step 2. Five
steps, in order, and step 2 is destructive so it stops and waits
(CLAUDE.md §4):

  1. **Merge `worktree-gl7-cron-orchestrator` → master.** It carries GL-7,
     GL-30 (`34a8b15`), GL-35, GL-36, `docs/2026-08-06-gl37-findings.md` and
     `docs/2026-08-08-gl7-soak-findings.md`. **The two findings docs exist
     nowhere else** — if the branch is ever abandoned rather than merged, copy
     them out first.
  2. **Promote the worktree database — this is a swap, not a reconciliation,
     and it is settled by measurement rather than by judgement.** Every shared
     content table was compared row-by-row on 2026-08-09 (`candidates`,
     `groups`, `group_products`, `group_product_variants`, `product_images`,
     `listing_texts`, `telegram_events_log`, `group_messages`): **zero rows
     missing from the worktree copy, zero rows differing.** The worktree DB is
     a **strict superset** of the root one — it was forked by copy and grown,
     the two never lived parallel lives — so there is nothing to merge and no
     decision about whose candidate 42 is real. Root: 434 KB, 12 tables, **no
     `schema_version` at all**, candidates 1–42. Worktree: 913 KB, 14 tables,
     `schema_version` 7, candidates 1–86. Back up **both** with dated names,
     then copy the worktree file over `db/qhoto.sqlite3`. **Two details worth
     carrying:** the root DB's `telegram_offset` is **37 updates behind**
     (475586367 vs 475586404), which is the single-consumer hazard made
     concrete and a reason to swap the file rather than migrate the root one
     in place; and `heartbeats` is a **2-row upserted latest-state table, not
     a log**, so it answers "did it run?" and not "how often did it fail" —
     do not expect history from it during GL-45's investigation. **GL-45
     cannot be investigated against the root DB** — the dropped-tap evidence
     and the live cursor are both in the worktree copy.
  3. **Re-point both Windows scheduled tasks at the repo root**, and **verify
     by heartbeat, not by assumption** — `heartbeat_status.py` against the
     canonical DB should show a fresh run after the switch. Leave them
     **paused** afterwards: nothing should run unattended until GL-45–GL-48
     land.
  4. **Confirm `db/gl7.lock` now lives beside the canonical DB** and the
     worktree's copies are out of the picture.
  5. **Prune or lock the worktree** so nothing can invoke it again. Note there
     are six other `agent-*` worktrees in `.claude/worktrees/`; this is the
     moment to check whether any of them also holds a live DB or a
     `run_*.py`, because the single-consumer hazard is a property of *any*
     second tree, not of this one specifically.

  **The token-scoped guard is still worth building after the merge**, and
  GL-45 may make it mandatory rather than merely tidy: the lock is keyed on
  the *script's directory*, so two trees take two different locks and both
  proceed against one `getUpdates` cursor. If GL-45's `getWebhookInfo` check
  comes back clean, "a second consumer of the token" is the next hypothesis
  in line — and a lock keyed on the bot token or the DB identity is both the
  diagnostic and the fix.

**E0 is DONE (2026-08-09).** `master` = `80ce9fd`. The remaining order below
was revised the same evening — **GL-48 and GL-45 swap places.**

**E1. GL-48 — finish the template fix.** Promoted ahead of GL-45 for one
reason: the owner's template edit left the system **half-fixed**, and a live
integration whose config no longer describes its remote template is a worse
state than the defect it replaced. It also **gates E2**: `run_hourly.py`
reaches the publish gate and the publish gate reaches Gelato, so GL-45's test
run cannot safely happen first. Brief:
`docs/2026-08-09-gl48-crop-and-template-brief.md`.

**E2. GL-45 — the Telegram drops.** Still the only open item that corrupts
decisions, and still the one whose cheapest hypothesis costs ten seconds —
**run the `getWebhookInfo` check now, in parallel with E1**, since it needs no
code, no run and no session, and a positive result rewrites the brief.
Brief: `docs/2026-08-09-gl45-telegram-drops-brief.md`. **Its first run also
discharges GL-38's skipped step 13** — the root tree has still never executed,
so check the heartbeat explicitly rather than letting it pass unobserved.

**E3. GL-47 then GL-46, in that order or the same session.** GL-47 stops the
pipeline creating candidates it should never create; GL-46 makes it loud when
a candidate fails. Doing GL-46 first means building a notification channel
whose first job is to tell you about out-of-season candidates you did not
want. Both are small; together they are one session.

**E4. GL-50 and GL-51 — the two GL-38 defects.** Small, and both belong with a session that is already in the repo rather than as their own. Original E3 (GL-48) is now E1. Superseded text: One read-only `GET` decides whether this is a
Gelato dashboard job (owner, manual) or a code fix, so it starts as research
and only then becomes a session. The dry-run gate fix (`is_live_mode` →
`is_r2_configured`) ships either way, and should ship with a test that fails
if the crop path is ever bypassed in dry-run again.

**E5. GL-49 — repair candidates 44, 47, 48**, after E0's DB reconciliation,
never before.

**E6. Re-soak — short, live, targeted.** Not another open-ended two-nighter:
that format has returned everything it is going to return. The specific
things still owed are GL-7's three unproven DoD items — the stale-schema
refusal, the injected-failure→Telegram path, and GL-36's 404 reconcile with
its falsifiable test (flip candidates 40 and 41, leave 42 alone) — plus one
clean end-to-end candidate that exercises the fixed paths. **That is a
checklist, not a vigil**, and it should be run as one.

**What this does to the gate: fifteen of twenty-two, and the "we are waiting"
framing retires.** Two of the three remaining items were on someone else's
clock; now four of the seven are on ours, and all four are sessions rather
than builds. GL-11 (Etsy's reply) is still the only thing genuinely outside
our control, and it continues to run in parallel with all of the above —
which is the one piece of good news in this revision.


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

**Session T — reviewing GL-22 session 1; a weld, a breakage and an incident
(Cowork, 2026-08-01/02).** *(Planning read of the coding session logged below
as "Session R — GL-22 session 1 built". Cowork planning entries use T/U;
Claude Code build entries use R/S.)*

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

**Session U — GL-22 built; three bugs no impact map caught (Cowork,
2026-08-02).** *(Planning read of "Session S — GL-22 session 2 built" below.)*

- **v4.12 is built and green (635/635)**, shipped as **one PR, not the two
  §6 offered.** The split line was wrong on inspection: `D` (shipping
  collapse) and `E` (stall predicate) are not disjoint from `A`, because
  D's "one call site" *is* `patch_etsy_listing`. **Good deviation** — the
  kickoff's split was a guess made before the code was traced, and the
  session corrected it rather than honouring a stale instruction.
- **Three real bugs, all found by reading stages rather than running
  tests.** This is the finding, not the bug count:
  1. **A second silent wipe, on the filesystem — outside the impact map.**
     `persist_mockup_render` was keyed `group_product_id + index`, so 5x7's
     scene 0 overwrote primary's scene 0 **on disk**. The impact map traced
     SQL and stopped there.
  2. **`reclaim_stranded_pending_group_products` would have deleted every
     live listing record.** It sweeps `pending` rows with no product id
     after 10 minutes — which under v4.12 is the *normal* state for the
     entire multi-day review window. **No test covered it.**
  3. **`group_mockup`'s cycle trigger would have deadlocked the flow.** It
     waited for the primary group to reach `approved_published`, which under
     `[D1]` never arrives until *after* the secondaries are reviewed. Now
     keys on `decision`.
  **Lesson for the next impact map:** tracing SQL call sites is not tracing
  impact. Three classes were missed — **filesystem keys, sweep/reclaim jobs
  whose "abnormal state" definition the change inverts, and cycle triggers
  whose preconditions the change reorders.** Any future map over this
  pipeline should walk those three explicitly.
- **The first non-additive migration in the plan, stated plainly.**
  `migrate_v412_gallery.py` **rebuilds `groups`** — SQLite cannot widen a
  CHECK constraint in place. The PRD's "rollback is stop calling the new
  path, not a down-migration" was written on an additive assumption that no
  longer fully holds. Not a problem to fix now; a sentence to read before
  anyone relies on that rollback story.
- **The `GET`-before-delete guard did its job by refusing.** On the first
  run it declined both Etsy deletions: the findings-doc ledger's titles were
  **stale**, because Q3's own patch test had renamed both drafts. Verified
  against the same doc, narrowed to the `GL22A-` marker prefix, re-ran, both
  now 404. **A destructive guard that fires on a false positive is working
  as designed** — the failure mode worth fearing was the other one. Stash
  SHAs recorded before dropping (`5f6d1c1`/`39f8300` stay reflog-reachable);
  `stash@{2}` untouched, as instructed.
- **A fourth CLAUDE.md constraint was flagged, not edited** — per §5's
  instruction — and has now been fixed: the `Data storage is SQLite` bullet
  still described the v4.11 per-group product/listing. Its replacement also
  records the two things that bit session 2: that a NULL `gelato_product_id`
  is *normal* for the whole review window, and that every delete against
  `product_images`/`group_product_variants` must scope by `group_id`.
- **What is not closed:** the orphan gap (→ **GL-32**). Removing the
  orphan-delete branch was correct under create-once, but a crash between
  the Gelato `POST` and the id-recording `UPDATE` still orphans a product no
  sweep can see. Pre-existing, now the only such path, and worth a cheap
  reconciliation rather than a clever one.


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

---

## Part 4 (cont.) — Session log (2026-08-03)

**Session V — GL-13/GL-17 round 2, live (Claude Code, 2026-08-03).**

**Verdict: PASS.** R0–R5 all green, suite 635/635 throughout, fixes merged as
PR #5 (`a2aff96`). The v4.12 publish path is proven against the real APIs:
one listing created exactly once with exactly the validated sizes and no
duplicate product; the gallery assembled once, in rank order; the re-patch
idempotent against the real `listing_image_id` payload; a rejected group that
deleted nothing, `GET`-verified either side; and the Telegram **Reject**
button tapped for the first time since GL-9 (GL-17 closed).

**Four defects found live and fixed in-flight:**

1. **The DB had never been migrated to v4.12** — `group_products.candidate_id`
   and `product_images.group_id` missing. The two existing migration scripts
   were run by hand. Root cause is not the missing columns: **nothing in the
   repo runs, orders, records or checks migrations.** → **GL-35**.
2. **`run_m1_live_test.py`'s seed check** treated any historical `candidates`
   row as "already seeded", permanently blocking a fresh candidate on a DB
   with history. Now checks for a *non-terminal* row — the definition
   `research.trigger_fallback_if_needed` already used. A harness-only bug, but
   it cost a debugging cycle before the round could start at all.
3. **`critic_pass.py` truncated at `max_tokens=2048`** on a 10-image gallery →
   4096. **This is the second occurrence of the same defect class** — GL-9
   raised the same constant 1024→2048 for the same reason. Twice is a pattern:
   the limit is set against today's prompt and silently invalidated the next
   time the gallery or the rubric grows, with truncation presenting as a
   content failure rather than a size failure. Worth a guard rather than a
   third raise.
4. **`telegram_client.send_media_group` passed R2 URLs** and relied on
   Telegram's own server-side fetch, which failed `WEBPAGE_CURL_FAILED` on
   gallery images in the 5–7.5 MB range. Now always downloads and
   multipart-uploads — the path local images already took. Note the shape:
   the code had a working path and a convenient path, and the convenient one
   was chosen for the case with the larger payloads.

**Two gaps filed rather than fixed, per owner direction — both promoted to
go-live blockers here, which is a deviation from "known gaps" and is stated
rather than smuggled:**

- **GL-33** — Gelato's product-creation auto-push leaves 5–6 untracked preview
  images on the Etsy gallery alongside our tracked composites. The
  self-hosted-gallery contract is the *reason the GL-6/GL-21 mockup track
  exists*; a gallery that opens on Gelato's generic renders spends four
  authoring attempts and buys nothing. It is invisible today only because
  every listing is a draft, which is exactly why it is cheap to fix now.
- **GL-34** — `production_partner_ids` appeared to drop when `who_made:
  i_did` was set. ~~Mutually exclusive; contradicts a "verified" `CLAUDE.md`
  line; mandatory-disclosure risk.~~ **Corrected 2026-08-04 — see the
  addendum below. That reading was wrong.**

**Addendum, 2026-08-04 — GL-34 re-scoped, and one item added.** The owner
produced a Shop Manager screenshot from the **GL-9 (v4.11)** round showing
`Who made it? = I did` and `Production partners: Gelato, Brussels — appears
on listing as "A print shop"` **on the same listing**. The two coexist, so:
the mutual-exclusivity claim is false, the mandatory-disclosure risk does not
exist, the `CLAUDE.md` contradiction flag is **withdrawn**, and the
`someone_else`/`collective` branch is dropped as *less* accurate rather than
more. **What is left is a diagnosis with a control:** GL-9's patch sent the
same `who_made` + partner pair and it landed; GL-13's appeared not to, so
either v4.12 regressed the patch path or the observation read the API
response echo rather than the listing. Either way it is one `GET` and a
dashboard look, not a decision.

**The lesson worth keeping, since this is the second time:** the original
filing reasoned from an API observation to a *policy* conclusion in one step,
with no dashboard check — the same move that made GL-22a's Q3 "confounded".
The dashboard is the ground truth for anything a shopper or Etsy's own
review sees; the API response is not, and treating a `GET` echo as
listing state is now a named failure mode in this project.

**Added from the same screenshot — GL-37.** "How does your shop produce this
item?" and "What tools are used to make this item?" are blank on every
listing, and the second is where **"An AI generator"** lives. `CLAUDE.md`
already knew the tools question was not API-settable; the produce-method
field is new information. The automation consequence is the sharp part: a
per-listing manual dashboard step inside a pipeline whose premise is
unattended operation.

**Housekeeping done:** 29 stale `generating` candidates (ids 5–34) from
earlier rounds marked `failed` with a recovery note; DB backed up first. The
underlying gap — nothing recovers a row stranded in `generating` — is
**GL-36**, and like GL-35 it is harmless while a human runs each round and a
leak once GL-7 runs unattended.

**Reading across the four fixes and the two riders:** none of them was a
v4.12 logic error. Every one was an *operational* defect — schema not
applied, harness state check wrong, a limit outgrown, a transport assumption
— in a codebase whose business logic passed 635/635 the whole time. That is
the profile of a system that has been carefully tested and never actually
operated, and it is a direct argument for GL-7's soak being a real gate
rather than a formality.

---

## Part 4 (cont.) — Session log (2026-08-04 → 2026-08-05)

**Session W — GL-33 shipped, GL-34 closed (Claude Code, 2026-08-04).**

**Verdict: both blockers off the board.** One PR (#6, `14a2d10`, commit
`47aa034`), 7 new tests, live proof against a real listing.

**GL-33 — built and proven.** `etsy_client` gained `get_listing_images` and
`delete_listing_image` (dry-run-aware, 4 tests). `group_product.
patch_etsy_listing` gained a reconcile pass (3 tests, idempotency covered):
after the upload loop and before `update_listing`, delete every image on the
listing whose `listing_image_id` is **not** present in this candidate's
`product_images.etsy_listing_image_id`, scoped by `group_product_id`.

Three design points, each of which could have gone the other way:

1. **Positive-match-only deletes.** The rule is "delete what we cannot prove
   is ours", not "delete what looks like Gelato's". The negative form is the
   tempting one — Gelato's previews are recognisable — and it is the one that
   eventually deletes an authored composite after some future rename. The DB
   already knows precisely which images are ours; the heuristic was never
   needed.
2. **Delete after upload, not before.** The listing is never briefly
   imageless, which matters because it is a live resource with a third party
   (Gelato) syncing against it.
3. **Scoped by `group_product_id`.** Same discipline the v4.12 gallery rework
   established — one candidate's reconcile must not reach another's images.

**Live result (candidate 42, listing `4549960823`):** 19 images → 13. Six
Gelato ghosts deleted, thirteen of ours remaining, a second patch changed
nothing, and the variant mapping and per-variant pricing both survived.
**That last part quietly answers GL-22a's Q3 in the case that matters** — Q3
was confounded because the only edit path ever tested (`PUT` on the product)
severed the Gelato↔Etsy sync by itself. Deleting a Gelato-owned *image* does
not. The general question ("can Gelato re-push after any edit") is still
open; the specific one this pipeline depends on is now measured.

**GL-34 — closed with no code change, and it was never a defect.** The PATCH
request field is `production_partner_ids` (list of ints); the GET response
field is `production_partners` (list of `{production_partner_id,
partner_name, location}`). GL-13's check read the write-side name off a
read-side response — which returns "missing" on every listing that has ever
existed, regardless of state. GL-9's control (`4542159277`) shows `who_made:
i_did` **and** the partner, live, matching the dashboard exactly. Written up
in `docs/2026-08-04-gl34-findings.md`.

**This is the third finding in this project traceable to the same move:**
GL-22a's Q3, GL-34's original filing (API observation → policy conclusion in
one step), and now GL-34's root cause. The pattern is not "we read the wrong
field once" — it is **treating an API response echo as the state of the
world**. The dashboard, or a fresh `GET` of the resource itself, is ground
truth. Worth more than a lesson: any future check that asserts a field is
missing should name which side of the request/response boundary it read.

**Found and flagged, not worked around.** The kickoff's §4 said to reuse
GL-13's R3 listing. R3 and R5 were both already deleted live — their
`group_products` rows still say `published` against ids that 404. The
session stopped, reported it, and substituted a fresh candidate (42) **with
owner sign-off** rather than inventing a control. That is the intended
behaviour and it is the reason this entry can be trusted; a session that had
quietly picked its own substitute would have produced the same PR and a
weaker record.

**Open, owner-only, carried out of the session:**

- Candidate 42's draft listing `4549960823` is live and unactivated — delete
  it like the other test listings whenever convenient.
- **`.env`'s `*_LIVE_MODE` flags were already true before the session and
  were left as-is** (Claude cannot edit `.env`). Stated because it is a live
  hazard rather than a loose end: **anything hand-run from this working tree
  now hits the real APIs by default**, including anything run to "just check
  something". Flip them off between live rounds.
- Candidates 40/41 still carry `published` rows against dead listing ids —
  **folded into GL-36** (owner, 2026-08-05), which is now one item covering
  drift in both directions rather than stranded `generating` rows alone.

**Reading it against Session V.** GL-13's four defects were all operational
— schema, harness state, a limit outgrown, a transport assumption. GL-33's
was different in kind: a **contract** defect. The pipeline believed
`product_images` described the listing, and it did not, because a third
party was writing to the same resource. Nothing in the test suite could have
caught it, because the suite's model of the world was the same wrong one.
The general form — *we are not the only writer to this resource* — is worth
carrying into GL-7, where the same assumption underpins every stage that
reads a row, acts, and writes it back on a cadence.

**Plan hygiene done in the same pass (Cowork, 2026-08-05).** **GL-23b was
reconciled**: it merged on 2026-08-02 as PR #4 (`7cbaee7`) and was recorded
in the header prose the same day, but its blocker-table row was never
ticked, and three subsequent revisions read past it. No consequence — GL-13
ran against master and passed — but a plan whose table and prose disagree is
a plan that gets read selectively. The row now carries the merge, the
migration rider (→ GL-35) and the PR #5 follow-on.

---

## Part 4 (cont.) — Session log (2026-08-05 → 2026-08-06)

**Session X — GL-7 built; soak night 1 running (Claude Code, 2026-08-05).**

**Verdict: the build did what the PRD asked, and it did it without touching a
single stage.** 15 commits on `worktree-gl7-cron-orchestrator`, 19 files,
~3.4k lines, eight new test files, and — the constraint that mattered most —
**no existing `pipeline/*_cycle` module modified.** The runner sequences; it
does not absorb. The implementation plan
(`docs/superpowers/plans/2026-08-05-gl7-cron-orchestrator.md`) was written
first and worked task-by-task, which is why this entry is short on surprises.

**What the commit sequence shows, which is more interesting than the file
list.** Four of the fifteen commits are the author correcting their own work
before anyone reviewed it:

- `74c8bb5` adds the lock; `5904f6d` then fixes **Windows-correct PID
  liveness, atomic acquire and unlink-only-own-pid**; `fb64e4f` then makes a
  contested stale-lock reclaim **fail closed** rather than race. That is the
  correct polarity and worth stating plainly: **a wedged pipeline is
  recoverable by a human; two concurrent batch runs against one SQLite file
  are not.** Failing closed on ambiguity is the same instinct as GL-33's
  positive-match-only deletes and GL-36's 404-only marking. Three items, three
  sessions, one rule: *when unsure, do less.*
- `d4f6620` turns a missing env var from an uncaught crash into a controlled
  `exit(1)`; `35b5c88` then threads the real credentials into both entrypoints
  with a regression test. The first commit is the one that matters — an
  unattended job that dies on a `KeyError` at 03:00 leaves a stack trace on a
  console nobody is reading.

**One real defect found against the production database**, and it is the
same shape as GL-13's R0. `migrate.check()` leaked a raw `OperationalError`
because the live DB **had never been through `init_db`** — it had only ever
had the individual `migrate_*.py` scripts run against it by hand, so
`schema_version` and `heartbeats` did not exist as tables at all, and "table
missing" is not the same error as "table empty". `bc229e9` makes `migrate()`
bootstrap via `init_db` first and reads a missing table as version 0, while
keeping `check()` read-only. **Third instance of the pattern:** the code was
correct about a database that had never actually been *operated*.

**Also in `bc229e9`, and easy to skim past:** `run_batch`'s `_run_stage` now
returns the stage's result, so reconcile's drift summary lands in the batch
heartbeat's `detail` field instead of being computed and dropped. A sweep
whose findings go nowhere is a sweep that will be believed and never read.

**Soak status at time of writing (2026-08-06, morning).** Night 1 is
**dry-run** — `ETSY_LIVE_MODE` and `GELATO_LIVE_MODE` both `FALSE` in the
soak tree's `.env`, per PRD §4 and the owner's Q2 answer. Heartbeats:
`hourly` ok, `batch` ok, both within the last cadence. Schema at version 7.
No stranded `generating` rows. **The soak is doing real work and the four
things it has proven so far are all real** — the scheduler fires, the lock
does not wedge, the schema guard passes a migrated DB, and the heartbeats
make "did it run?" a one-command question (`heartbeat_status.py`).

**Three of PRD §6's pass conditions are still outstanding**, and one of them
is structurally impossible on night 1:

1. The schema guard has not been exercised against a *deliberately stale* DB
   — it has only ever seen a good one.
2. The injected-failure→Telegram path has not been fired.
3. **GL-36's reconcile cannot run in dry-run at all** — it needs live Etsy
   `GET`s to find a 404. Night 2 owns this, and it now has a clean,
   falsifiable test the plan did not previously have: **candidates 40 and 41
   should flip to `listing_missing`, and 42 should not**, because 42's draft
   listing is still alive. Do not delete 42's listing before that run.

**The finding this session did not produce, which someone had to → GL-38.**
None of the above is on master. `master` is at `14a2d10` and has no
`run_batch.py`, so the scheduled tasks necessarily invoke the worktree at
`.claude/worktrees/gl7-cron-orchestrator`. Both entrypoints resolve their DB
path relative to `__file__` — correct code, and precisely why the divergence
is silent: the worktree now carries **its own migrated 450 KB database**
while the canonical one sits at 434 KB, untouched since 2026-08-04, with no
`schema_version` table.

**The part that is a hazard rather than an inconvenience:** one bot token has
one `getUpdates` cursor, and each tree keeps its own `telegram_offset`. The
lock does not help — it is keyed on the script's own directory, so two trees
take two locks and both proceed. **PRD §2 item 3 is satisfied within a tree
and violated between trees.** If anything is run from the main checkout while
the soak is up (`run_m1_live_test.py` is still there and still works), an
owner tap can be swallowed by the tree that cannot act on it, acknowledged,
and lost. **Operational rule until the merge lands: nothing runs from the
main checkout while the soak is up.**

**Fourth occurrence of the merge pattern** — GL-1, GL-23, GL-23b, GL-7. It
has been written four times as a per-item note and should be promoted to a
standing definition-of-done: *a build is not done until master carries it.*
Worth noting what is different this time: the previous three cost delay. This
one produced a second database and a shared-cursor hazard, because the branch
was not merely unmerged — it was **being run**.

**Owner-facing, unchanged from the PRD's "not in this plan":** the Task
Scheduler wiring and the soak itself are operator steps, and they are the two
things now in flight.

---

## Part 4 (cont.) — Session log (2026-08-06)

**Session Y — GL-37, the Creativity Standards re-check (Claude Code,
read-only, 2026-08-06).** Findings:
`docs/2026-08-06-gl37-findings.md` *(in the GL-7 worktree only — carry it
through GL-38's merge)*.

**Verdict: not settable, at any level, by any endpoint. Decision: accept the
manual per-listing step. Recurring re-check filed as GL-39.**

**The method is the reason to believe it**, and it was chosen deliberately
against this project's own history:

- **A full raw response dump** of `GET /listings/{id}` on two live listings,
  every field enumerated rather than looked up by name. This is the direct
  answer to GL-34, where a field-name grep against the wrong side of the
  request/response boundary produced a confident wrong answer. Here there is
  no read-side field to alias to — the dump shows the absence, rather than a
  lookup failing to show a presence.
- **All 15 taxonomy properties for `taxonomy_id` 1027** enumerated, killing
  the "maybe it is a listing property" theory outright rather than by
  inference.
- **`GET /shops/{shop_id}`** dumped, which retired question 3 (shop-level
  default vs per-listing) as moot rather than answering it: there is nothing
  to default at either level.
- **Discussion #1630** (2026-06-22), an open feature request naming exactly
  the two fields, with exactly the names one would guess. **Correctly read as
  proof of absence, not as a hint of presence** — a distinction the write-up
  makes explicitly, and one that a less careful session would have gotten
  backwards.

**The finding that matters is not "no API".** It is that the **only** place
to set these fields is the web listing editor, and **the editor's sole save
action is "Activate with changes"** — no draft-save exists. Three
consequences, none of which were visible when GL-37 was filed:

1. **The disclosure tick is an activation.** You cannot pre-fill disclosure
   on a draft and activate later; the two are one action.
2. **This collides with GL-29** rather than gating it. GL-29 buys
   programmatic activation; but for any listing you intend to disclose
   properly, a human is already in the editor and the save takes it live. So
   GL-29's real value narrows to "activate at scale with both fields left
   blank" — which is a compliance and merchandising choice, not a technical
   one. **Raised in the GL-29 row rather than silently re-scoped, per
   CLAUDE.md §3.** The owner decision is no longer *when* to build GL-29 but
   *whether*, and for which listings.
3. **GL-7's unattended premise now has one named, bounded hole.** Everything
   up to a draft listing runs unattended; the last inch is manual, forever,
   until Etsy ships #1630. That is a materially different statement from "the
   pipeline is unattended", and the plan should stop making the shorter
   claim.

**Why GL-39 is a numbered row and not a note.** The day #1630 ships is the
day two problems close simultaneously — the manual step and GL-29's
ambiguity. Nobody notices that day without looking. Quarterly, ten minutes,
and the first thing to check is the discussion, not the API. **Good
candidate for a Cowork scheduled task**, which is exactly the shape:
recurring, small, driven by an external source that changes without telling
you.

**Reading it against Sessions W and X.** Three consecutive sessions have now
turned on the same axis: *what is the ground truth, and did we actually look
at it?* GL-34 read an echo for state. GL-33 discovered a second writer to a
resource we assumed we owned. GL-37 dumped the whole response instead of
grepping, and got a durable answer. The pattern worth keeping is not
"be careful with APIs" — it is that **every one of these was cheap to do
correctly and expensive to do by inference.**

**Session Y addendum — three decisions off the back of GL-37 (Cowork,
2026-08-06).**

**1. The quarterly re-check is wired, not remembered.** Cowork scheduled task
`gl39-etsy-creativity-standards-api-check`, cron `0 9 1 2,5,8,11 *` — first
run 1 Nov 2026. Its prompt is deliberately self-contained (each run starts
cold): it carries the settled background so no run re-derives GL-37, and it
carries the **confirmation standard** — if #1630 looks shipped, a changelog
line is not enough; a full raw `GET /listings/{id}` dump is. That is GL-34's
lesson written into a recurring job rather than into a document nobody
re-reads. Caveat recorded: scheduled tasks only fire while the desktop app is
open, otherwise on next launch.

**2. The prose disclosure is removed from listing descriptions.**
`compliance_draft.DISCLOSURE_TEXT` is now `""`, the draft prompt **actively
instructs the writer not to add one** (silence would let the model
reintroduce it unbidden — the old text creeping back without anyone deciding
to bring it back), and `listing_texts.disclosure_text` is retained `NOT NULL`
and written empty rather than migrated away. Both facts the sentence carried
are disclosed structurally: the AI tick by hand at publish, the production
partner via `production_partner_ids` on the patch (verified live, GL-34).
Tests updated; the write-path test now asserts `== ""` rather than asserting
against the constant, so a reintroduced disclosure **fails loudly** instead of
silently satisfying an equality. 132 tests green across every module that
touches `disclosure_text` (`compliance_draft`, `digest`, `critic_pass`,
`cleanup`, `group_digest`, `group_critic_pass`); the full suite was not run
to completion in this environment and should be before the commit.

**Worth stating plainly, since this removes a compliance artefact:** the
critic rubric never checked for the disclosure sentence, so nothing was
enforcing it anyway — its removal changes what a listing *says*, not what any
gate *checks*. The real enforcement was always going to be the structured
field.

**3. GL-29 is cancelled, and this is the interesting one.** Not deferred for
cost or time — **cancelled because GL-37 revealed it would make things
worse.** Programmatic activation produces a live listing with the disclosure
tick unset; the manual path produces one with it set, because in Etsy's
editor the tick and the publish are the same save. So the automated route is
strictly *less* compliant than the human one, for €0.20, through a one-way
door. The code stays exactly where it is — written, tested,
`# DELIBERATELY UNWIRED`, with its guard test unchanged rather than rewritten.
**Nothing to build and nothing to undo**, which is the cheapest possible
shape for a cancelled item. Parked as **GL-29b** with two explicit reopen
triggers: #1630 ships, or volume makes the dashboard visit the bottleneck.

**The three decisions are one position, and the order matters:** removing the
prose disclosure is safe *only because* the owner publishes by hand, and
publishing by hand stays true *only because* GL-29 is not built. That chain
is recorded as a comment on the removed constant in `compliance_draft.py`, not
just here — a future session wiring up activation will read the code, not this
plan.
