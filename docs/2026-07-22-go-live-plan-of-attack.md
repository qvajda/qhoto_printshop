# Go-live plan of attack — Etsy AI POD pipeline (2026-07-22)

> **Last updated 2026-08-11 — seven rows closed in two sessions and the critical
> path did not move, because it was never those rows. Gate: twenty-four of
> twenty-seven. Three open: GL-7, GL-11, GL-52.** Closed: **GL-55** and **GL-56**
> (PR #12, branch `gl56-gl55-copy-redo-seasonal`, 763 green) and **GL-57**
> (including the owner-supervised live read-back on listing `4553335845`),
> **GL-58** (both halves — groups 2 and 38 marked after a DB backup), **GL-59**,
> **GL-60**, **GL-61**, **GL-62** (PR #13, 786 green).
>
> **The denominator moved on 08-10 and nothing said so.** The previous count
> ("twenty-one of twenty-four") was written *before* the E9 triage added GL-55,
> GL-56 and GL-57 to the blocker table; the triage filed the rows and never
> restated the count. Adding those three to both sides gives **24/27** — and
> since all three have now shipped, **the open set is identical to 08-10's.**
> That is the number worth looking at: the last three weeks of work has been
> everything *except* the critical path, and the critical path is still one live
> night and one email.
>
> **What the two sessions actually bought is that the night is now worth
> running.** Before GL-59 it would have lost candidates to false Replicate
> timeouts; before GL-62 it would have been unobservable; before GL-55/56 it
> would have manufactured more copy to repair by hand. None of that closed a gate
> row and all of it changes the expected yield of the run that does.
>
> **Next: E10, in three parts, in order —
> `docs/2026-08-11-e10-kickoff.md`.** **E10a** GL-65 item 2, now owner-approved,
> **plus the correction it needs** (see the GL-65 row: at an hourly cadence the
> ack cannot arrive in seconds and probably is not arriving at all — the lever is
> the poll cadence, and the ack is the rider). **E10b** the GL-56 backlog
> recovery of candidates 77/78/79/81, which carries a prerequisite nobody had
> recorded: all four groups already hold a `group_messages` row, so
> `run_digest_cycle` will not re-send them and the four live keyboards are
> pre-GL-56 three-button ones — a tap on `✏️ Edit` there regenerates the artwork,
> the exact loss GL-56 exists to prevent. **E10c** the one live night.
>
> **The sequencing insight, because it removes a cost from the board: E10b is
> E10c's fuel.** GL-52 needs one fresh Gelato create from the repaired template;
> under v4.12 a create happens when a candidate's three groups are all decided;
> so driving **one recovered candidate** through publish produces that create.
> **No candidate needs to be generated to close GL-52, and no Replicate money is
> spent to close GL-7.**
>
> **Two rows filed from the owner's 08-11 observation, both post-launch: GL-66**
> (two good designs still sitting as drafts with Gelato's default mockups and
> pre-GL-53 copy — one of them as two listings) and **GL-67** (a general
> migrate-a-design-to-current-standards path, no image generation). The scoping
> answer is on the rows: for pre-v4.12 designs, migration is **republish as one
> new listing and delete the old drafts**, not a patch — GL-22a Q2 is settled and
> no API path adds a variant to an existing Gelato product.
>
> **The three scheduled tasks are still Disabled, and that is now a decision
> rather than a dependency** — GL-58 was the reason they were masked, and both its
> halves have landed.

> **Last updated 2026-08-10 (evening) — E2 and E3 both done; four rows closed
> in one day, two new blockers opened, and the board is down to four open
> items. Gate: twenty of twenty-four.** Closed: **GL-45** (tested clean — the
> tap path works end to end; **the root cause of the 08-09 loss is still
> unproven and the row says so**), **GL-48** (live create measured, 10x24
> placed aspect 0.4176 against a ~0.42 target), **GL-46** and **GL-47** (built,
> merged, PR #9 `4f85ec9`, 733 green). **GL-38's Phase D step 13 is discharged
> too** — a heartbeat finally landed in the root DB, so the root tree has now
> executed rather than merely been inspected.
>
> **The two new rows are the point of this revision, and they are the same
> lesson wearing different clothes: a check that cannot see the failure mode is
> not a check.**
>
> **GL-52 — the 10x24 artwork is cropped past the frame edge on the live
> product, and the measurement that closed GL-48 was structurally incapable of
> seeing it.** The placement *rectangle* is correct (0.4176, measured). The crop
> applied to the artwork *inside* that rectangle is not: top of the flower and
> bottom of the stem are cut off. It was found by the owner opening the Gelato
> Design editor and looking — not by any instrument this project owns. **Filed
> as GL-52, not GL-51 as the findings doc proposed; GL-51 is taken.**
>
> **GL-53 — the listing copy has never complied with the GL-37 decision, and
> nothing was ever going to notice.** The owner spotted `AI Generated Art` in
> the live title; the audit found **27 of 27 descriptions still carrying a prose
> AI disclosure** (including drafts written *after* `DISCLOSURE_TEXT` was
> emptied on 08-06), **10 of 27 with the disclosure in title or tags**, and —
> worse, and not a disclosure question at all — **25 of 27 advertising
> `printable` / `Instant Digital Download` for a physical made-to-order
> poster.** Emptying the constant removed our sentence; the model writes its
> own, because the prompt's own opening line hands it the words. `validate_
> listing_text` checks title length and tag count and nothing else. **GL-37's
> decision has been resting on an instruction to an LLM, which is a preference,
> not a control.**
>
> **Next: E7 (GL-53) and E8 (GL-52), in parallel** — disjoint files, disjoint
> runtimes, neither writes to a live API. Kickoffs:
> `docs/2026-08-10-gl53-listing-copy-guardrail-kickoff.md` and
> `docs/2026-08-10-gl52-10x24-crop-kickoff.md`. **E8 is gated on five minutes of
> owner evidence before any session starts** (a Design-editor screenshot per
> variant plus the archived submitted 10x24 file), because that evidence decides
> whether it is a code fix or a dashboard job — and GL-48 already taught what it
> costs to answer that question by reading code first. **Both batch tasks stay
> Disabled until GL-53 lands:** the reason has changed (GL-46/47 are fixed, so
> it is no longer about Replicate spend) but `run_batch` still runs
> `compliance_draft`, so every cycle until then manufactures more copy that has
> to be repaired by hand.
>
> **What is genuinely left: GL-7's targeted re-soak, GL-11's reply from Etsy,
> GL-52, GL-53.** One diagnosis, one guardrail, one short checklist re-soak, one
> email.

> **Last updated 2026-08-09 (latest) — GL-48 fixed in-repo; only the
> owner-gated live create is outstanding. Gate: sixteen-and-a-half of
> twenty-two.** Details in the row, which is more accurate than the brief that
> preceded it. **Three corrections that brief earned, recorded because a brief
> nobody audits is a brief nobody should trust:** **(1) its §3 measurement
> method could not work** — `productImages[]` are 1000×1000 square scene
> previews, not the submitted print file, so they carry no aspect information;
> what settled it was the *placed rectangle* inside the preview plus a
> content-based check on the artwork's warm arc. **(2) Its §5 fix was wrong in
> the safe direction:** repointing the crop gate at `is_r2_configured()` would
> have regressed the test that forbids falling back to the uncropped master on
> a live call. Removing the gate outright is correct and leaves live+R2,
> live-without-R2 (fails loud) and dry-run+R2 on **one branch** — which was
> the actual goal. **(3) §6 was never needed**, because §3 answered "one bug,
> not two".
>
> **The verdict, stated precisely: the crop maths, the archived file and the
> upload were all already correct. The white bars came entirely from the
> Gelato template, and the owner's dashboard fix was the real fix.** Exactly
> two `static_config.json` entries were stale (`5x7_portrait`,
> `10x24_portrait`); all twelve `templateVariantId`s were verified unchanged
> against the live API rather than assumed.
>
> **What that licenses, and what it does not.** One *external* root cause was
> confirmed — **and two real latent code defects were found alongside it,
> neither of which was the white bars**: the stale placeholder config (a
> guaranteed failure on the next live create) and the dry-run divergence,
> which is *why* two nights of soak never saw the defect — **the test run was
> not executing the code that had the bug.** A root cause being external is
> not evidence the code is fine; it is evidence the code was never tested
> against the thing that was broken.
>
> **Two items carried forward, both deliberately.** The **landscape template
> has the same one-placeholder defect** — recorded, not built, **inherited by
> GL-18**. And **one owner-supervised live create is owed**, verified by
> `scripts/gelato_template_check.py`. **That verification needs no session of
> its own: it arrives free inside GL-45's test run**, which has to drive a
> candidate through the publish gate anyway.
>
> **Next: GL-45 (Track E, E2). Its brief exists and already carries the
> `getWebhookInfo` result and the revised hypothesis.** One operational
> instruction attached: **enable only the hourly task for that test — the two
> batch tasks stay Disabled until GL-47 and GL-46 land.** `run_batch` is what
> manufactures out-of-season candidates and swallows their failures; there is
> no reason to spend Replicate money re-observing two characterised defects in
> order to test a Telegram fix. **That single run now discharges three
> outstanding items at once:** GL-45's own test, GL-38's skipped step-13
> heartbeat (the root tree has still never executed), and GL-48's live create.
> Watch all three deliberately — riders that arrive free are the ones that get
> marked done without being checked.

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
| GL-38 | C+M | **✅ FULLY DISCHARGED 2026-08-10 — Phase D step 13, the one step the merge skipped, is now closed.** E2's run wrote a fresh `hourly` row to `heartbeats` in `db/qhoto.sqlite3` at the repo root, so **the root tree has now actually executed** — until 2026-08-10 it never had, and the merge was therefore verified by inspection rather than by execution. Verified by heartbeat, per the step's own instruction, not by assumption. Previous status: **✅ DONE 2026-08-09 — master is `46c7ba6`, carries all 22 commits, 709 tests green, and PR #7 is MERGED on the remote.** Executed in the order the kickoff specified. **What the kickoff got wrong, in descending order of usefulness: (1) there was no conflict at all.** `tests/test_research.py` auto-merged — GL-43's guards and the soak's `sort_on` regression sit in different regions of the file. Both were verified present *by content* (lines 38–47 and 136–149) and the file re-run at 22/22, because a clean merge exit is not evidence that both additions survived. **(2) There is no PR-less local merge here — PR #7 was open and the kickoff never mentioned it.** Pushing branch then master let GitHub close it as merged (17:26Z); a purely local merge would have left it open indefinitely. **(3) Five uncommitted files on master, not four** — `docs/2026-07-22-go-live-plan-of-attack.md` (+199/−21, this board) was also dirty. **(4) `docs/2026-08-06-gl37-findings.md` was untracked in the *worktree*,** not the root, and would have died with it exactly as the soak findings nearly did — committed on the branch as `4d2648f` before merging. **(5) Three scheduled tasks, not two** (`qhoto-hourly`, `qhoto-batch-morning`, `qhoto-batch-evening`), all already Disabled, so nothing could race the swap. **Two defects found while executing, both filed rather than fixed here: `migrate.py` treats `argv[1]` as the DB path unconditionally, so `migrate.py --check` opens a *new empty database literally named `--check`* and reports `schema_version is 0` — a stale-schema false alarm on a correct DB, and it silently litters the repo root; the correct invocation is `migrate.py db/qhoto.sqlite3 --check`, which returns `schema_version=7, up to date`. And all three scheduled tasks had an empty `WorkingDirectory`,** so a cron-launched run inherited `C:\Windows\System32` — harmless only because every path resolves off `__file__`; now set to the repo root. **Deviation from the procedure, owner-approved: Phase D's hand-run heartbeat verification (step 13) was SKIPPED.** With live mode armed, `run_hourly.py` would action real Telegram callbacks against GL-45's unfixed drop bug and `run_batch.py` would spend Replicate/Anthropic money re-observing GL-46 — the brief asked for a live run to prove a path resolution that is `__file__`-relative and provable by reading. **So the deployment is re-pointed but has never executed from the root; the first real heartbeat there is still owed, and lands free with the first GL-45 test run.** DB: promote-and-swap done, `schema_version` 7, `integrity_check ok`, candidates 1–86, `telegram_offset` 475586404, both heartbeat rows, 85 groups / 39 products / 187 images; **both pre-swap files retained as `db/qhoto.sqlite3.bak-2026-08-09-root` (the only undo) and `.bak-2026-08-09-worktree`.** Six stale worktrees removed after confirming each was clean with zero unmerged commits; their `worktree-agent-*` branch refs are left in place, harmless. The branch is preserved as `gl7-soak-archive`. **⚠️ The sharpest finding came last, and it is the one to carry into any future worktree retirement: removing the GL-7 worktree would have silently orphaned the promoted database.** Its `db/` held **1.6 GB of git-ignored artefacts, 289 files of which existed nowhere else** — the base artwork and mockups for candidates 43–86, i.e. exactly the rows the promoted DB references — and **24 candidate rows stored *absolute* `base_image_local_path` values pointing into the worktree.** `git worktree remove` would have reported success and left a canonical DB referencing deleted files. Fixed in that order: robocopy the 289 missing files to `db/base_artwork` (no-overwrite, byte-identical, root now 408 files), then rewrite the 24 paths to the root prefix after verifying every target existed — **0 unresolvable paths across all 62 candidates with artwork**, confirmed before the removal. **The general rule: a worktree's git status says nothing about the git-ignored artefacts a database points at, and "no unmerged commits" is not the same as "nothing to lose."** The empty worktree directory itself survived deletion (the session's own shell held it open on Windows); it holds nothing and can be `rmdir`'d. **Left untracked deliberately:** `assets/mockups/5x7/portrait/lifestyle_small_kitchenshelf/` (fails `distortion` 2.26 %, GL-27 says regenerate-or-drop, already in R2 via GL-30) and `assets/brand/etsy-banner.png` + `shop_icon.jpg` (Nov-2025 source inputs, not in the R2 corpus — **the one remaining un-backed-up artefact, worth a line in GL-27**). Previously: **🟢 UNBLOCKED 2026-08-09, and SURVEYED the same day — kickoff: `docs/2026-08-09-gl38-merge-kickoff.md`. The survey is the news: this is not the clean fast-forward every previous revision of this row assumed.** One real conflict (`tests/test_research.py`, both sides added tests, both must survive), one untracked file that will refuse the checkout outright, **GL-37’s `DISCLOSURE_TEXT = ""` change uncommitted on master since 08-06 and touching the live publish path**, and ~11 board-cited docs still untracked. **The database, conversely, stopped being a question:** the worktree copy is a **proven strict superset** (eight tables compared row-by-row, zero missing, zero differing), so it is a promote-and-swap with nothing to reconcile. Previously: **🟢 UNBLOCKED 2026-08-09 — the soak is stopped, so the merge is available now and should go FIRST, ahead of GL-45–GL-48.** The soak was the only reason the worktree had to stay live; with it paused, the standing "run nothing from the main checkout" rule can be **retired rather than endured**, and the four fix sessions branch off master like normal work. **The argument for merging before fixing, not after:** four more commits on that branch would make this the *fifth* occurrence of the merge pattern (GL-1, GL-23, GL-23b, GL-38) on a branch already carrying GL-30, GL-35, GL-36 and GL-37's findings — and GL-49's row repair would be done against a database that is about to be superseded. **The five-step sequence below is unchanged and is now the head of the critical path**; the full ordering, including what to do about the two databases, is in Part 3, Track E. Previously: **OWNER DECISION 2026-08-06: let the soak finish on the worktree as-is; merge afterwards, then re-point the scheduled tasks.** Endorsed — restarting a running soak to fix its provenance would throw away the one thing that costs wall-clock time, and the divergence is understood rather than surprising. **What that decision buys and what it costs, stated so neither is a surprise later:** it buys two uninterrupted nights; it costs a **post-merge sequence that is now mandatory, not optional**, and it means **the soak's result is provisional until that sequence is done** — a pass on the worktree is evidence about the code, not about the deployment. **The post-soak sequence, in order:** (1) merge the branch to master; (2) **reconcile the two databases into one, canonical DB backed up first** — decide deliberately which is authoritative rather than defaulting to the newer file (CLAUDE.md §4: this is destructive, show the plan and wait for "proceed"); (3) re-point both Windows scheduled tasks at the repo root and **verify by heartbeat**, not by assumption — `heartbeat_status.py` against the canonical DB should show a fresh run after the switch; (4) confirm `db/gl7.lock` now lives beside the canonical DB and that the worktree's copies are out of the picture; (5) **prune or lock the worktree** so nothing can invoke it again. **The standing hazard until step 3 completes is unchanged and is the thing to actually watch: one bot token, one `getUpdates` cursor, two trees, and a lock that is keyed per-tree so it does not arbitrate between them.** Nothing may be run from the main checkout while the soak is up — and after the switch, nothing from the worktree. **The token-scoped guard (below) is worth building even after the merge**, because this failure mode is a property of the design, not of this week's accident. Original filing: **The soak is running from an unmerged agent worktree, against a forked database (NEW 2026-08-06). Blocker-class, and cheap.** `master` is at `14a2d10` and does not contain `run_batch.py`, so the scheduled tasks are invoking `.claude/worktrees/gl7-cron-orchestrator/`. Both entrypoints resolve `DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"` — **relative to the script**, which is correct code and exactly why the fork happened silently. **Three distinct problems, in increasing order of sharpness:** **(1) The merge, fourth occurrence.** GL-1, GL-23, GL-23b and now this. The runtime deploys from master; a soak that passes on a branch has proven something about a tree nobody will run. It should stop being written as a per-item note and start being a **standing definition-of-done**: a build is not done until master carries it. **(2) Two databases.** The worktree's is migrated (`schema_version` 7, 450 KB, actively written); the canonical one is 434 KB, last touched 2026-08-04, with no `schema_version` table. Soak state — heartbeats, aged-out rows, any candidate the batch creates — accrues to the copy. Somebody has to decide which is canonical **before the live night**, and the answer is not automatically "the newer one". **(3) The Telegram single-consumer hazard, which is the genuinely dangerous one.** `getUpdates` has one cursor per bot token, and each tree keeps its own `telegram_offset` row. If anything is run from the main checkout while the soak is up — `run_m1_live_test.py` still exists there and still works — **the two trees eat each other's updates, and an owner tap can be consumed by the tree that cannot act on it, then acknowledged and gone.** The new lock does **not** cover this: it is a file lock at `<tree>/db/gl7.lock`, so the two trees take two different locks and both proceed. This is PRD §2 item 3's property being satisfied *within* a tree and violated *between* trees. **Fix shape (small):** land the branch on master, point the scheduled tasks at the repo root, reconcile the two DBs into one with a backup first, and — the part worth keeping — make the single-consumer property enforceable rather than conventional, e.g. a lock keyed on the bot token or the DB's identity rather than on the script's directory. **Until it lands, the operational rule is: do not run anything from the main checkout while the soak is up.** | merge + one DB + a token-scoped guard |
| GL-29 | C+T | **❌ CANCELLED as a go-live item 2026-08-06 (owner) — struck from the go-live gate, re-filed post-launch as GL-29b. This row is kept, not deleted, because the reasoning is worth more than the row.** GL-37 established that the AI-disclosure tick lives only in the web listing editor and that the editor's only save action activates the listing. **The owner is therefore the publish gatekeeper by Etsy's design: he ticks "an AI generator" and publishes in one action.** Programmatic activation would race that step, not save it — it would produce a live listing that is *less* disclosed than the manual path, for €0.20, through a door that only opens one way. **What makes the cancellation clean rather than a deferral:** the code already exists and is already safe. `etsy_client.update_listing_state` stays written, dry-run-aware, unit-tested and **`# DELIBERATELY UNWIRED`**, and `test_patch_etsy_listing_never_activates_a_listing` stays exactly as it is — the guard test that was going to be *rewritten* by this item now simply keeps doing its job. **Nothing to build, nothing to undo.** **Reopen when, and only when:** Discussion #1630 ships (→ GL-39) so the disclosure becomes API-settable, **or** listing volume makes a per-listing dashboard visit the actual bottleneck. Until one of those is true this is a cost with no benefit. Original scope, for traceability: **Programmatic draft→active publishing, behind an env gate (NEW 2026-08-01, owner).** Today activation is a manual per-listing dashboard action by design. **Half of this already exists:** `etsy_client.update_listing_state` is written, dry-run-aware and unit-tested, carrying a `# DELIBERATELY UNWIRED` comment and a guard test (`test_patch_etsy_listing_never_activates_a_listing`). The work is therefore *the gate and the wiring*, not an integration: a new all-or-nothing flag (`ETSY_ACTIVATE_LISTINGS`, **default false**, resolved like `is_live_mode`), one call site at the end of the publish path, the guard test **rewritten rather than deleted** (it must now assert "never activates *unless the flag is on*"), and loud logging on every activation with the listing ID. **Three constraints the build must respect:** (1) Etsy's API says setting `state=active` publishes the listing and **it can never return to `draft`** — only `active`↔`inactive` — so this is a one-way door per CLAUDE.md §4: record an `activated_at` on the row and ship the `inactive` path in the same PR as the rollback; (2) activation costs **$0.20 per listing** and is charged in Developer Mode too, so each live test burns real money — budget a handful of euros, not a sweep; (3) **ordering vs GL-22** — activation must be the *last* step, after every group's patch has landed, or a buyer-visible listing gains variants and gallery images afterwards. **✅ Resolved 2026-08-01 by GL-22c's decision:** under create-once-when-all-groups-are-decided the listing is created with every validated size and its full gallery already assembled, so activation is unambiguously the last call in the publish path and GL-29 needs no ordering logic beyond "call it last". **Testing in Developer Mode proves the API call, not shopper-facing visibility** — the visual confirmation belongs to the first minutes after GL-11. ~~**Blocked as of 2026-08-03 by GL-33, and weakly by GL-34.**~~ **✅ Both gates cleared 2026-08-04 — GL-33 shipped, GL-34 closed as a non-defect. GL-29 is unblocked and is now the cheapest remaining blocker on the board.** Kept for the reasoning: activation is the one-way door that makes the gallery and the disclosure buyer-visible, and `active` can never return to `draft`, so the only remedy for publishing a known defect is `inactive`. ~~**One gate does remain, and it is GL-37**~~ — **GL-37 answered 2026-08-06, and it does not gate GL-29 so much as partially collide with it. Flagging this rather than quietly re-scoping (CLAUDE.md §3).** GL-37 established that the two Creativity Standards fields can only be set in the web listing editor, and that **the editor's only save action activates the listing** — there is no draft-save. Consequences for this row, in order: **(1) the manual disclosure step is itself an activation**, so for any listing you intend to disclose properly, a human visit to the editor is what takes it live — and GL-29's programmatic call never gets to be the thing that activates it. **(2) GL-29's remaining value is therefore narrower and should be stated honestly:** it activates *at scale, without a dashboard visit*, which is only useful if you accept the two fields staying blank on those listings. That is a real merchandising/compliance choice, not a technical detail. **(3) The €0.20 and the one-way door are unchanged**, but the ordering question flips — the cheapest correct path today may be "no GL-29 at all for the first listings", tick-and-activate by hand, and revisit when Discussion #1630 ships (→ GL-39). **Owner decision needed before this is built, and it is no longer "when", it is "whether, and for which listings".** **Owner sequencing 2026-08-05: GL-7 runs first anyway** — GL-29 is a session that will still be a session later, and it costs real money each time it is exercised. | ~~GL-33 + GL-34~~ ✅ → GL-37 decision → flag + wiring + rewritten guard → one live activation → GL-11 |
| GL-11 | M | **🟡 EMAIL SENT 2026-08-06 — the clock is started and now runs in the background.** Draft used: `docs/2026-08-06-gl11-developer-mode-email-draft.md`. **What this changes about the plan's shape: nothing on the board is waiting on anyone external any more.** Since 2026-08-03 this row has been the one item on a clock the owner does not control, and every revision since said so; it is now spending that lead time in parallel with the GL-7 soak, which is the best available use of it. **What is still owed here:** Etsy's reply and the actual mode change — the item is not ✅ until the shop is out of Developer Mode. **Two follow-ups worth not dropping:** (1) if there is no reply in ~10 business days, reply in the same thread rather than opening a new one; (2) the sent email's "test listings have been deleted" line — candidate 42's draft `4549960823` was still live at send time and is deliberately being kept alive as GL-36's negative control for the soak's live night. Delete it after that run, so the statement becomes true rather than staying approximately true. Original scope: **Revert Etsy Developer Mode** — email developer@etsy.com, external approval lead time. Listing visibility observed before this is not representative. **Owner sequencing (2026-08-01): GL-29 lands and is tested first** — the point of reverting is a store that publishes. **Owner decision 2026-08-02: the email waits for GL-13 to pass**, rather than going out immediately. Deliberate trade — it spends lead time that cannot be recovered, in exchange for not opening an external conversation about a shop whose publish path is still unproven. **Consequence to watch: from GL-13's pass, GL-11 becomes the only item on the critical path with a clock you do not control.** If GL-13 slips, this slips with it one-for-one. **✅ 2026-08-03 — the gate is satisfied. GL-13 passed, so the email is unblocked and is now the single highest-leverage action available: it costs ~10 minutes, it is owner-only, it needs no code, and every day it is not sent is external lead time burned for nothing.** Send it in parallel with the GL-33/34 session — nothing about those two changes what the email says. | ~~GL-13 pass~~ ✅ → **email (send now)** → GL-29 → Dev Mode off |
| GL-30 | C+M | **✅ DONE 2026-08-08 — `34a8b15 feat(gl30)`, on the GL-7 soak branch, reaching master with GL-38's merge.** **443 files, 381.5 MB, every one `status: uploaded`, `dry_run: false`** — all thirteen `outputs/gl6_*` batches plus the 20 untracked files in `assets/mockups/inflow/`; **209 of the 443 carry a `verdict_key`**, which is the half that makes the corpus an inventory rather than 443 anonymous PNGs. Built as specified: `scripts/corpus_backup.py` + `tests/test_corpus_backup.py`, reusing `artwork_store._r2_put_object` rather than writing a second uploader, sha256 content-addressed under `mockup-corpus/`, write-once. Manifest: `docs/data/2026-08-08-mockup-corpus-manifest.json` (3,551 lines) — **that file, not this row, is the durable record**; anyone looking for a specific image starts there. ⚠️ **A process note worth more than the row itself: this was invisible from master for most of a day.** It was built in a *locked worktree*, so `git status` on master showed nothing, and a GL-30 kickoff document was written on 08-08 for work that was already underway — see `docs/2026-08-08-gl30-kickoff.md`, superseded by the manifest and safe to delete (still on disk, untracked, pending the owner's word). **Parallel worktrees hide completed work from every check that looks at the main checkout.** When the board says an item is open, confirm against `git log --oneline master..<worktree-branch>` before scoping a session for it. Original scope: **One-off backup of the mockup corpus to Cloudflare R2 (NEW 2026-08-01, owner).** Every generated scene — accepted, parked and rejected — exists only on the desktop. **Scope it to what git does not already have**, see the note below the table: the git-ignored `outputs/gl6_*` batches (~160 screened images **and their `screen.json` verdicts**), the untracked `inflow/` sources, `lifestyle_small_kitchenshelf`, and anything parked outside the tree. **Reuse `artwork_store._r2_put_object` + `_sigv4_headers`** — the S3-compatible PUT, the SigV4 signing and the all-or-nothing `R2_*` env gate are already written and tested; do not write a second uploader. **Write-once, never overwrite:** date- or content-addressed keys under one prefix, because a sync that can overwrite is a copy, not a backup. **Carry each image's sidecar/`screen.json` with it** — without the verdicts the corpus is 160 anonymous PNGs and the inventory value (the thing the harvest proved was worth more than the mask change) is lost. Parallel to the critical path; must not delay GL-7 or GL-22. | script → uploaded corpus + a manifest of what landed where |
| GL-12 | M | **🔴 DEFERRED TO POST-LAUNCH 2026-08-08 (owner) — not the zero-cost item it was filed as.** Alpha registration turns out to require standing up a Google Cloud Console project first (GCP project, Workspace linkage, billing attached) before the application can even be submitted — real setup cost, not a "click apply" parallel task. Moved off the go-live board; see the Post-launch table. Original scope: Apply for Google Trends API alpha access (zero cost, parallel). | how-to → submitted |
| GL-45 | C+R | **✅ TESTED 2026-08-10 (E2) — THE PATH IS PROVEN; THE ROOT CAUSE IS NOT. READ THIS ROW AS "TESTED CLEAN", NEVER AS "DIAGNOSED".** Findings: `docs/2026-08-10-e2-findings.md` §A. The tap on group 76 (candidate 49, 5x7, message 286, `update_id 475586414`) travelled end to end: raw `logs\telegram_getupdates.log` → `telegram_events_log` id 55 (`accepted=1, action_taken='approve'`) → `groups.id=76 decision='approved'`, sequential update_ids, no gap. The re-tap guard was exercised in the same run: a second tap on the collapsed `✅ Approved` label produced id 56, `accepted=0, action_taken='ignored: already decided'`, and the group row did not move. **Runbook §0 row 1: the path works and the tap was not dropped — the 08-09 loss did not recur, so this is a clean run and not a diagnosis.** The second-consumer hypothesis is *supported but still unproven*: see the concurrent-pressure observation folded into this row below. **One expected behaviour, written down so a future reader does not file it as a defect:** the toast (`answerCallbackQuery`) and the keyboard collapse (`editMessageReplyMarkup`) land when the **hourly poll dispatches** the update, not at tap time — the bot has no persistent listener, so a several-minute delay between tap and visible feedback is the design, not a drop. **Free rider collected:** post-launch item 7's "does the edit actually render on the owner's client" is answered yes. **The E2/E3 parallel experiment paid out:** E2's three real hourly entries (08:41:01, 08:43:07, 08:46:25 UTC) sit inside the window E3's pytest run was hammering ~1000+ throwaway DBs (08:38–08:55 UTC), and the raw log across that window is **clean — sequential offsets and update_ids, no gaps, no duplicates, no foreign entries.** That is affirmative evidence the `sha256(bot_token)` lock and the `db_identity` guard hold under exactly the concurrent shape that was the leading suspect. It does not retroactively explain 08-09; it does mean the shape can no longer recur. Previous status: **🟢 ON MASTER 2026-08-10 — PR #8 merged (`c17b869`, code `26db7bb`), 724 green. THE BUILD IS DONE; WHAT REMAINS IS ONE TEST, AND THE ITEM SHOULD NOW BE READ AS A TEST ROW, NOT A BUILD ROW.** Everything in the 08-09 entry below shipped and is now the deployed behaviour. **Three things this changes about the board that are easy to miss.** (1) **GL-50 is closed for free** — `migrate.py` parses flags before paths, so `--check` no longer creates an empty database named `--check`; strike it from Housekeeping rather than scheduling E4 for it, and E4 collapses to GL-51 alone. (2) **The Telegram tap-feedback UX item is already built, not pending.** `publish_primary_group._ack` + `_mark_decided` fire on every accepted tap and both discard paths; the keyboard is replaced with a single non-actionable `✅ Approved` / `✏️ Edit requested` / `🚫 Rejected` label carrying `noop:<group_id>`, and a re-tap is answered "Already decided". Nine tests cover it (`tests/test_publish_primary_group.py` incl. the `noop` re-tap and the "ack never raises" path, `tests/test_telegram_client.py:166`). **The post-launch row "Telegram UX polish" no longer contains the visual-feedback half** — see the 2026-08-10 session log for what is genuinely left there (roughly two hours of optional polish, none of it load-bearing). (3) **The parallel-work rule that has governed every session since GL-38 is retired by the token-scoped lock and the canonical-DB guard.** "Do not run anything from another tree/DB while the pipeline is live" was a convention enforced by nobody; it is now enforced by `sha256(bot_token)` in the system temp dir and by migration 8's `db_identity`. A coding session may therefore run in parallel with a live hourly task — and doing so is itself a cheap test of the guard. **What is still owed, and it is exactly one run:** enable only `qhoto-hourly`, send a digest, tap, then diff `logs/telegram_getupdates.log` against `telegram_events_log`. That single read discriminates "Telegram never sent it" from "we lost it" and is the only thing that can close the **08-09 morning window**, still unexplained (offset 475586404, last row 08-08 19:30 ⇒ the polls returned nothing at all). Runbook: `docs/2026-08-10-e2-live-reproduction-runbook.md`. **Do not tick this row on a green run alone** — a green run with no dropped tap proves the fix works, not that the root cause is understood; say which of the two you got. Previously: **🟡 FIXED AND GUARDED 2026-08-09 (late), ROOT CAUSE NOT PROVEN — findings: `docs/2026-08-09-gl45-findings.md`. 724 tests green.** The brief's step 1 came back **empty**: every SQLite file on the machine carrying a `telegram_events_log` was searched for the 19 missing ids — the canonical DB, all eight dated `.bak`s, the four surviving `%TEMP%` soak copies (dated **08-05**, ending at id 367, never written during the drop windows) and 1,119 pytest databases. **Zero hits.** **And the inference that promoted H2 does not hold:** it assumed every update seen produces a row, but `process_update` returned a silent unlogged `None` for any update with no `callback_query` — an ordinary message consumed an id and left no trace. Gaps of the same shape exist on **07-22 and 08-03/04**, before any reported drop. So a gap proved nothing; it does now, because non-callback updates are logged. **What IS proven is that the hazard fired today:** the canonical heartbeat stops at `hourly 15:00:01` while Task Scheduler records `qhoto-hourly` running at **16:00 and 17:00, exit 0** — two successful runs that polled the single cursor and wrote into the worktree DB that GL-38 Phase D then deleted. That also explains `pending_update_count: 0` without any tap having been dropped. **It does not explain the 08-09 morning window**, where the offset (475586404) and last row (08-08 19:30) show the polls returned nothing at all — still open, now instrumented. **Shipped regardless, per the brief's steps 2-4:** a **canonical-DB guard** (migration 8 `db_identity` records the absolute path the DB lives at, so a copy is detectable; `run_publish_primary_group_cycle` — the one point that consumes the cursor — refuses to poll from a non-canonical file; `migrate.py <db> --bless` re-points it after a deliberate swap; applied live, backup `db/qhoto.sqlite3.bak-2026-08-09-pre-gl45`); a **token-scoped lock** (`sha256(bot_token)` in the system temp dir, replacing `<tree>/db/gl7.lock` — one token, any number of processes); **explicit `allowed_updates`** on every call; **raw `getUpdates` logging** to `logs/telegram_getupdates.log` (a file, not the DB); **tap acknowledgement** — `answerCallbackQuery` now fires **before** `handle_decision` rather than after (a decision spending minutes in Gelato/Etsy answered an already-expired callback, which is exactly why a tap that landed still looked dropped), plus `editMessageReplyMarkup` replacing the keyboard with a `✅ Approved`/`✏️ Edit requested`/`🚫 Rejected` label, a `noop:` re-tap answered "Already decided", and both discard paths answered too; and a **per-update offset advance**, closing the mid-publish re-delivery (ids 365-367 logged twice). **Free side effect: GL-50 is closed** — `migrate.py` now parses flags separately from the path, so `--check` no longer opens an empty database named `--check`. **Next: the live reproduction** — enable only `qhoto-hourly`, send a digest, tap, then diff the raw log against `telegram_events_log`; that single read discriminates "Telegram never sent it" from "we lost it". Previously: **🟡 H1 ELIMINATED 2026-08-09, and the likely cause is now named: a second consumer of the bot token — specifically, the throwaway-DB test runs that the soak findings cited as *ruling interference out*.** `getWebhookInfo` returned `url: ""` and **no `allowed_updates` field** (never set ⇒ default, which includes `callback_query`), so neither half of H1 survives. **The decisive new fact is `pending_update_count: 0`:** Telegram holds an unconsumed update for 24 h, the 08-09 taps were today, and all three tasks have been Disabled since GL-38 — so unread updates would still be queued. **They are not, therefore something consumed them.** Confirmed retrospectively from the stored `raw_payload`s: **19 `update_id`s exist that never produced a row** (362–363, 375–380, 383–390, 398–400), clustering exactly on the reported drop windows. **The mechanism: the Telegram cursor is per-token and global; `telegram_offset` is per-database-file.** A `run_hourly.py` against a throwaway copy polls with *that copy's* offset, receives the real updates, **confirms them (deleting them for every consumer)** and writes the result into the throwaway — a perfect silent drop, no row, no discard. **GL-38 framed this hazard as “one token, two trees”; it is “one token, any number of processes”, and the per-directory lock cannot see any of them.** **Two corrections to the original finding:** groups 53/55/59 carry `decision='approved'` with `status='pending_review'`, which is the **correct v4.12 intermediate state**, not a drop — the genuinely lost taps are the *secondary* groups (76–81, 84) at `decision=NULL`, so diagnose from `groups.decision`; and update_ids 365/366/367 each appear **twice** ten minutes apart, which is a run killed mid-publish before `set_telegram_offset` — the safe direction of the same weakness. **Next: grep the throwaway copies for the 19 ids (case closed if found), then build a token-keyed lock plus a canonical-DB assertion, and ship the tap acknowledgement regardless.** Previously: **🆕🔴 Telegram button taps are silently dropped — CONFIRMED RECURRING, and the only open item that corrupts *decisions* rather than plumbing (soak finding 4).** 2026-08-08: the owner tapped approve/reject on 7 `pending_review` primary groups (48, 49, 55, 57, 58, 59, 60); **3** produced a `telegram_events_log` row. The remaining 4 were re-tapped and only the **third** attempt was captured. 2026-08-09: **recurred with no manual-run interference anywhere near the window** — all four secondary-group taps (candidates 49, 55, 60, 66) left zero trace. **Do not re-run the "they probably weren't actually tapped" explanation; the owner has directly contradicted it, twice.** Code review is exhausted and found nothing: `set_telegram_offset` only advances past `update_id`s the loop iterated, and `resolve_callback` returns an unlogged `None` **only** for updates with no `callback_query` at all — which a real tap always has. Every other path logs an explicit row, including "discarded". So the update never reached `resolve_callback`. **Why this is blocker-class and not a UX annoyance:** a dropped *approve* is indistinguishable from an unreviewed group and self-heals when re-tapped; a dropped **reject** leaves a group looking undecided until `GROUP_REVIEW_STALL_DAYS` ages it out — and under GL-22a Q2 a skipped size is a **permanent forfeit**, not a deferral. Under live mode this is the difference between a listing that ships what the owner approved and one that ships what he ignored. **The one check nobody has made, and it should be made before a single line of instrumentation is written: `getWebhookInfo`.** One unauthenticated-shaped GET on the bot token, ~10 seconds. If a webhook URL is set, `getUpdates` is starved and every symptom follows immediately — including "zero trace, not even a discarded row" and "the manual run happened to catch it". It also returns the **sticky `allowed_updates` list**, which persists from whatever was last passed to `setWebhook`/`getUpdates` and which this codebase never sets (`telegram_client.get_updates` sends only `timeout` and `offset`). Second cheap hypothesis, same class: **another consumer of the same token** — a stale Windows Task Scheduler entry, a dev shell, or the second tree GL-38 describes. **Only if both are clean** does this become an instrumentation job: log the raw `getUpdates` response body verbatim, before `resolve_callback` sees it, and correlate against `update_id` gaps. **A separate, real, and cheaper-to-fix gap found alongside it:** inline buttons never change appearance after a tap — no `answerCallbackQuery` toast, no `editMessageReplyMarkup` — so the owner cannot tell a dropped tap from a slow one. That is **not** the cause (the DB proves the update never arrived) but it is why the defect went unnoticed for two days, and the fix is one call at the point the callback is resolved. | `getWebhookInfo` + token-consumer audit → raw-`getUpdates` instrumentation only if needed → fix + tap acknowledgement |
| GL-46 | C | **✅ DONE 2026-08-10 — `95105c1`, merged in PR #9 (`4f85ec9`), 733 green (master collected 724).** `run_generate_cycle` now marks the row `failed` **with a reason**, finishes the loop so the other candidates still get their turn, and raises `GenerateCycleError` once at the end — which reaches `_run_stage`'s existing Telegram path. No schema change (`schema_version` stays 8); the retry budget reads `generation_attempts`. **Two findings the session surfaced that are worth more than the fix:** (1) a **pre-FLUX failure logs no attempt at all** (the art-brief writer runs before any generation row exists), so the budget would never count down — handled with a marker row; and (2) **nothing reads `failed` except `cleanup.prune_stale_candidates`'s 30-day purge.** There is no recovery or age-out pass, and the session correctly did **not** invent one — that is GL-36-shaped and a separate decision. **The general rule went into CLAUDE.md**, which is the durable half of this row: a swallowed per-item exception must always leave a state change behind. Original scope: **Per-candidate `generate` failures are swallowed, and 2026-08-09 proved it systemic rather than flaky (soak findings 3 + 6).** `pipeline/generate.py:262-264`, inside `run_generate_cycle`: a bare `except Exception: … continue`. The candidate's status is never set to `failed`, and because the exception dies there it never reaches `run_batch.py`'s `_run_stage` outer catch either — **so no Telegram notification fires and the row is indistinguishable from "hasn't run yet"**. 08-08: candidate 45 stuck `pending`, generated cleanly on a manual retry with no code change. 08-09: **8 of 8** new `go` candidates (76–81, 83, 84) stuck at `pending`, zero reached `generate`; candidate 76 reproduced cleanly by hand. Plausible-not-confirmed cause: `generate.py`'s own Replicate rate-cap pacing tripping across an unusually large queue (11 candidates plus other stages' Replicate/upscale calls in the same batch). **Transient failures self-heal for free** — the next run re-queries `WHERE status = 'pending'` — which is exactly what makes this dangerous: it looks benign right up until a persistent failure (bad prompt, expired token, real outage) parks a candidate forever. **And the self-healing is slower than it sounds:** `generate` runs on the batch cadence only, so a fully-stuck batch waits **12 hours**, which under live mode is real delay on dated seasonal content. **Fix shape, deliberately small:** set `status='failed'` (with the reason) on the exception, let it propagate to `_run_stage` so the existing Telegram surfacing fires, and add a retry counter so a genuinely transient failure still self-heals instead of being condemned on first error. **The general form is worth stating in `CLAUDE.md`, not just fixing here:** a swallowed per-item exception must always leave a state change behind — GL-7's per-stage isolation stops a stage's crash killing a run, and in exchange made per-item failures invisible at *both* levels. Owner decision 2026-08-08 was "known gap, don't fix before merge"; 08-09's 8-of-8 supersedes that. | one `except` block → `failed` status + notification + retry count |
| GL-47 | C | **✅ DONE 2026-08-10 — `e194155`, merged in PR #9 (`4f85ec9`).** `MAX_EVENT_LEAD_DAYS = 45`, with the reasoning beside the constant rather than in a commit message: pipeline latency (a multi-day loop, a twice-daily cadence, two owner reviews) plus listing runway before the window opens. **Deliberately not 14** — the too-late gate answers a different question and was left untouched. Built as **two independent predicates rather than one range test**, which is what makes it correct for `engagement_season` (11-21 → 02-14, a window that wraps the year); an already-open window still goes, via a signed compare with no `abs()`. A too-early hold rechecks at `window_start - 45d`. **Dedup lives in `run_research_cycle`, not in the collector** — collectors stay pure, and trending-now/on-demand inherit the same protection; the key is `trend_source`, not free-text niche; an all-deduped cycle does **not** fire the safe-evergreen fallback on top of live work. The six-window table frozen at 2026-08-10 is a test asserting exactly one go. GL-43's two guards untouched. Original scope: **Event-lookahead niches have a "too late" gate and no "too early" one, so seasonal content generates all year (soak finding 7).** `research._classify_by_timing` checks only `days_until_close >= MIN_EVENT_LEAD_DAYS` (14). There is no check on how far **before** a window it still makes sense to generate, so every one of the 6 fixed `EVENT_WINDOWS_2026` entries (`fall_cozy_aesthetic`, `holiday_peak`, `diwali`, `black_friday_cyber_monday`, `engagement_season`, `new_year_refresh`) classifies `go` for essentially the whole year — which is why holiday and fall candidates were generating in August. **Compounded by a second gap in the same function:** `research.collect_event_lookahead()` returns the same fixed set on every call with **no check against already-active candidates for the same niche**, so two batch runs close together produced near-duplicate candidates across all 6 event niches. **Together these two are a money leak, not a tidiness issue:** the same premature niches regenerate every batch, burning Replicate and Anthropic spend, and under live mode they can reach real listings. Fix: a lead-time window (`go` only within N days *before* `window_start`, alongside the existing lead before `window_end`) plus a dedup pass against non-terminal candidates for the same niche. **Do this before GL-46**, or at least in the same session — GL-46 makes stuck batches loud, and there is no point being loudly told about candidates that should never have been created. | two predicates in `research.py` → tests → no out-of-season `go` |
| GL-54 | C | **✅ DONE 2026-08-10 — `1d3ef89`, PR #11 MERGED (`3a5cb72`), 744 green.** Six loops fixed, as the kickoff's corrected inventory predicted — **plus a seventh the kickoff also missed: a second outer swallow in `publish_primary_group.retry_publish_failed_groups`'s caller**, which was on neither the findings' list nor the brief's. **That is now three consecutive documents that undercounted this defect** (findings said four, the kickoff said six and named the group-level stages, the sweep found seven) — and each correction came from reading the code rather than the previous document. **The lesson is not "count better", it is that an inventory assembled from prior write-ups inherits their blind spots; the only reliable inventory is the grep.** `publish_group.py` turned out to have no loop at all — nothing to sweep, which is worth recording so the next reader does not go looking. `publish_primary_group.py:445` was left alone as briefed. **`digest` and `group_digest` deliberately skip clause (a)**, with the reasoning in `DigestCycleError`'s docstring where the next reader will actually hit it — the group stays legitimately `pending_review`, `groups.status` has no value meaning "could not tell you about this", `failed_abandoned` would be a lie that costs a real design, and the next cycle's re-send *is* the retry. **Alt-text rider done, and the feared term-list conflict does not exist** — nothing an honest mockup alt text needs is on the forbidden list, so listing copy is now guarded across title, tags, description and alt texts. Original scope: **🆕 Kickoff: `docs/2026-08-10-gl54-swallowed-failure-sweep-kickoff.md`. **The inventory was checked against the code while writing it and the findings' count is wrong in both directions: it is SIX loops, not four, and one of the two it named is already compliant.** Unnamed and affected: `group_mockup`, `group_critic_pass`, `group_digest` — the group-level stages are exact copies of the primary ones and were simply not looked at. **Already compliant and must be left alone: `publish_primary_group.py:445`** — GL-45 deliberately made that catch write `log_telegram_event(..., accepted=True, "error: …")` so a dropped tap leaves a durable trace. **Sweeping it blindly would be a regression dressed as a fix**, which is the standing hazard of a mechanical sweep and the reason this one gets a brief. **The real judgement call is `digest`: it has nowhere to write clause (a).** `groups.status`'s CHECK has no value meaning "I could not tell you about this" — `failed_abandoned` would be a lie that costs a real design — so the likely answer is clause (b) only, raising after the loop and letting the still-`pending_review` group re-send next cycle. **That exception must carry its own reasoning in the code, because an exception to a rule that does not say why it is an exception is indistinguishable from the bug the rule exists to prevent.** Original scope: **Four more stage loops still have the GL-46 shape, and the reason they were found is the reason to sweep them (GL-53 findings §4, 2026-08-10).** `primary_mockup`, `critic_pass`, `digest` and both `publish_*` cycles carry the same catch-print-`continue` loop that GL-46 fixed in `generate` and GL-53 fixed in `compliance_draft` — a per-item failure leaves the row reading "hasn't run yet" and the stage returns success, so no Telegram notification fires. **Neither instance was found by looking for the shape. GL-46 was found by a soak losing 8 candidates overnight; GL-53's was found only because its kickoff contained the sentence "check whether this loop has the same shape".** Two data points is a pattern and the rule is four hours old, so the sweep is cheap now and gets expensive the moment an unattended run depends on it. **~10 minutes plus tests per stage; do it before any live run that costs money, because four of the stages such a run passes through can currently fail silently and a live run you cannot observe is a live run you pay for twice.** **Rider, same session, one line: extend `check_forbidden_terms` to alt texts** — they are model output, they go live on the listing, and GL-53 scoped them out only because its kickoff said title/tags/description. The decision needed is whether alt text is listing copy; it is. |
| GL-52 | R+C | **🆕🔴 The 10x24 variant's artwork is cropped past the frame edge in the live product (E2, 2026-08-10) — and this is NOT a GL-48 recurrence.** Manual inspection of candidate 49's product in Gelato's Design editor: **the top of the flower and the bottom of the stem both fall outside the printable area.** The measured placed-artwork aspect for that same variant is **0.4176 — correct**. So the *rectangle the artwork is placed into* is right and **the crop applied to the artwork within that rectangle is wrong**; the image reads as over-zoomed. Different mechanism from GL-48, same size class, same product, **and by construction invisible to the aspect measurement that closed GL-48** — the metric and the defect are orthogonal. Not investigated: E2 was scope-locked to manual observation ("Type: M … no code is written here"), and that limit was respected, which is why this row exists instead of a half-diagnosis. **The first question a session must settle, before touching anything, is whose crop it is:** ours (`image_crop`'s cover-crop centring, or the source ratio it crops against) or Gelato's (the 10x24 template variant's saved fit re-cropping a file that was already correct — which is exactly the class of fault GL-48 turned out to be, and the owner's dashboard edit was the fix). **CONFIRMED AND REPAIRED 2026-08-10 (evening) — the predicted stale-config breakage was real, and it was exactly the two variants the owner edited.** `scripts/gelato_template_check.py` (templates-only, read-only): `MISMATCH 5x7_portrait: placeholder '011_mt_sunday_brook.JPG' not in live ['55_5x7_crop.png']` and `MISMATCH 10x24_portrait: '004_doorframe_bottles_madeira_color.JPG' not in live ['65_10x24_crop.png']`; the other ten keys `ok`. **`static_config.json` updated to the live names (2-line diff).** **Three things this run establishes beyond the repair.** (1) **All twelve `template_variant_id`s survived the edit** — the check MISMATCHes on a missing variant id before it ever reaches the placeholder name, and it did not, so the dashboard edit replaced images without renumbering variants. That is the difference between a 2-line fix and a re-resolution of the whole table. (2) **The new authoring images are pipeline-produced crops and measurably on-ratio**: `55_5x7_crop.png` is 6656×9318 = **0.7143**, exactly 5/7; `65_10x24_crop.png` is 4053×9728 = **0.4166** against 10/24 = 0.4167. So the fix is not merely plausible, the inputs to it are verified — the saved transform now has nothing to re-crop. (3) **The eight-day GL-48 stale-config outage would have been a two-minute one if this check had existed then, and it now has a second confirmed catch.** The standing rule earns its place in CLAUDE.md: **any Gelato dashboard edit is followed immediately by `python scripts/gelato_template_check.py` with no arguments** — the edit and the check are one action, not two. **What is still NOT verified, and the row stays open on it: no product has been created from the repaired template.** Product `3e7abdce-...` snapshots the old placement and cannot answer this. The pass condition is unchanged — one fresh create, `gelato_template_check.py <product_id>` **and** an eye on the Design editor, because the aspect number is blind to the crop-within-rect defect by construction. **OWNER ACTION 2026-08-10 (evening), AND IT IS UNVERIFIED — the template was edited again, this time so the placeholders carry images already cropped to each variant's aspect ratio.** The mechanism is sound and matches GL-48's established root cause exactly: Gelato saves a *placement transform* derived from the image the placeholder was authored with, so authoring 10x24 with a 0.6842 image and then submitting a 0.4167 file is what produces a transform that re-crops a correct file. Author it at 0.4167 and the transform has nothing left to do. **Three things that edit does NOT do, all of which have bitten this project before.** (1) **It does not fix product `3e7abdce-...`.** A Gelato product snapshots the placement at create time; editing the template afterwards changes future creates only — which is why GL-48 needed a fresh live create to verify and this does too. (2) **It very probably makes `static_config.json` stale, and that is the highest-probability breakage on the board right now.** `image_placeholder_name` holds the placeholder's *name*, and this template's placeholder names are the image filenames (`003_flower_in_stream_madeira_color.JPG`, `011_mt_sunday_brook.JPG`, `004_doorframe_bottles_madeira_color.JPG` — GL-48's row). **Swapping the images renames the placeholders.** GL-48 already lost eight days to exactly this, from exactly this cause: an owner dashboard edit that nothing re-read. **First action is `python scripts/gelato_template_check.py` with no arguments** — the templates-only mode exists for this, is read-only, and diffs all twelve config entries against the live template. Run it before anything else. (3) **It does not make the fix tested.** A hand edit is a hypothesis; GL-22a Q2 proved Gelato returns `200` for changes it silently drops. **Verification requires one fresh create measured with `gelato_template_check.py <product_id>` plus an eye on the Design editor** — the aspect number alone is blind to this defect, which is the whole reason GL-52 exists. Apply the same edit to **5x7** (its crop genuinely loses 410px of height, so a template over-zoom there would compound) and record that **GL-18/landscape still carries the untouched original defect.** **MEASURED THE SAME EVENING, BEFORE ANY SESSION WAS BOOKED — AND THE ANSWER IS THAT THE LOSS IS ALMOST CERTAINLY NOT OURS.** The archived submitted file `db/base_artwork/49_10x24_crop.png` is **4053×9728 px, aspect 0.4166** against the 10/24 = 0.4167 target, and the master `49.png` is 6656×9728 — **identical height.** `image_crop.cover_crop` on a 0.6842 master against a 0.4167 target takes the `current_ratio > target_ratio` branch, which crops **width only and preserves every row of pixels.** Visual inspection of the submitted crop confirms it: the whole thistle head, the ladybird, the full stem and generous margins top and bottom. **Our pipeline cannot have cut the top of the flower or the bottom of the stem — it is arithmetically incapable of removing vertical content on this path.** That leaves the Gelato side: the 10x24 template variant's **saved placeholder fit/zoom** re-cropping a file that arrived correct. **Which is precisely the GL-48 verdict repeating** — pipeline correct, template wrong, owner's dashboard edit is the fix — and GL-48's own row already warns that the portrait template's placeholders were hand-edited on 08-09 and that the landscape one still carries the same defect (GL-18). **So E8 is now an owner dashboard check first and a code session only if that check surprises us.** The remaining code-side question is a smaller and better one: **nothing in the pipeline can currently observe this class of fault**, because `gelato_template_check.py` measures the placed *rectangle* and the submitted file's own content is never compared to what the template does with it. That gap is worth a row whether or not the dashboard fixes the print. Superseded first-question text: That is settled by **comparing the submitted print file against the editor's placement**, not by re-reading either one alone — and note `productImages[]` cannot answer it (1000×1000 scene previews, GL-22a). **Evidence to capture first, by the owner, before any code: a Design-editor screenshot per variant of product `3e7abdce-c055-4609-ae68-aab19868c5a0`, plus the archived submitted 10x24 file for candidate 49** — five minutes that decide whether this is a session at all. **Filed as GL-52, not GL-51 as the E2 findings doc proposed: GL-51 is taken** (the absolute-path / artefact-integrity row). Detail: `docs/2026-08-10-e2-findings.md`, "New defect". |
| GL-53 | C | **✅ DONE 2026-08-10 — `1373978`, PR #10 MERGED (`ed41f97`), 742 green (733 before). Both halves shipped in one commit, plus the GL-52 rider.** Findings: `docs/2026-08-10-gl53-findings.md`. `check_forbidden_terms` (`pipeline/compliance_draft.py:58`) runs over **title, tags and description**, raises into the existing retry, and is cross-referenced in both directions with GL-37's comment block. The prompt drops the "AI-generated" framing and states the physical made-to-order poster positively. **The finding that mattered, and it is the reason this row is worth reading rather than ticking: the kickoff's own starting term list would have missed the defect it was written to catch.** The shipped sentence is *"created using **AI image generation**"* — which matches none of `ai generated` / `ai-generated` / `ai art` / `generated with ai`. **A list built from drift we had already named would have shipped green tests and left 27 of 27 unfixed.** The session added a bare `\bai\b` word-boundary rule, which both closes that hole and settles the kickoff's open judgement call — **one list, three fields, no split**: a word-boundary `ai` cannot match inside `air`/`detail`/`paint`/`chair`, so the feared false positives do not exist, and 2 of the 27 are caught **only** by that rule. **A fourth drift class turned up in the same sentence block and was folded in:** 27 of 27 also ended *"Printed and shipped by our production partner, Gelato."* → `production partner` and `gelato` added, covered by the same GL-37 reasoning. **Measured, not assumed: all 27 existing drafts are rejected** (`Printable` 12, `AI Generated` 8, `AI-Generated` 3, `AI` 2, `Instant Digital` 1, `printable` 1). **Correction to this row's own numbers: class (b) is 13 of 27, not 10** — the kickoff's figure was either taken before the last drafts landed or transcribed wrong; recorded so the count is not quietly wrong. **`compliance_draft` did have the GL-46 shape — half of it — and it was fixed here rather than filed:** the row was already marked `compliance_failed` with a reason, but `run_compliance_draft_cycle` caught-printed-`continue`d, so the stage returned success and `_run_stage` never fired its Telegram notification. Now raises `ComplianceDraftCycleError` after the loop; no re-queue (the row is terminal at this stage and the retry budget lives inside `build_compliance_draft`). **Two existing tests asserted the swallow and had to be rewritten — the tests were part of what kept the defect in place.** **Residual, deliberately not done and each with a reason:** no backfill of the 27 drafts (unpublished except 49, and a fresh cycle cannot produce this copy); GL-10c untouched; **alt texts are not checked, and they are model output that goes live on the listing** — one line to add, needs a decision, carried on GL-54. §3c rider shipped but **unverified live** — whether Gelato's `get_product` echoes `fileUrl` per variant was never called, so the script degrades gracefully and **the next live create tests the rider as well as the template.** Original scope: **🆕🔴 Listing copy does not comply with the GL-37 decision, and never did — the constant was removed, the model was not (owner spot-check + full `listing_texts` audit, 2026-08-10).** The owner noticed `AI Generated Art` sitting in candidate 49's **live title**, which contradicts the shipped position that AI disclosure lives only in the structured publish-time tick. Auditing all 27 drafts turned up **three drift classes, one cause**. **(a) 27 of 27 descriptions still carry a prose AI disclosure** — verbatim, *"This design was created using AI image generation from the seller's own prompts, then selected, edited, and prepared for print by the seller."* — **including drafts written on 08-08 and 08-09, i.e. after GL-37 set `DISCLOSURE_TEXT = ""`.** Removing the appended constant removed *our* sentence; the model writes its own, and `DRAFT_TEXT_PROMPT_TEMPLATE`'s opening line (*"an AI-generated botanical/minimalist wall art poster print"*) hands it the vocabulary while the next paragraph asks it not to use it. **(b) 10 of 27 put `AI Generated Art` in the title or in a tag** — one of thirteen tag slots spent on a disclosure rather than a search term. **(c) 25 of 27 say `printable` / `Instant Digital Download` / `Printable Download` in the title or tags for a physical, made-to-order, Gelato-shipped poster.** **(c) is the most serious of the three and is not a disclosure question at all:** it advertises a product we do not sell, against `when_made: made_to_order` and `is_supply: false`, and that mismatch reaches a buyer complaint before it reaches Etsy. **The structural fault is common to all three and is the part worth fixing: `validate_listing_text` checks title length and tag count/length and nothing else.** There is no forbidden-term check anywhere, so a sentence in a prompt is the only control — and **an instruction to an LLM is not a control, it is a preference.** GL-37's decision has been resting on one ever since. **The fix is one small session, and it is two halves that must ship together:** tighten the prompt (drop "AI-generated" from the framing; describe the product as a physical made-to-order print explicitly) **and** add the assertion — a forbidden-substring check across title, tags and description that **fails the draft loud**, cross-referenced from GL-37's comment block as the mechanism that keeps that decision true. **Relationship to GL-10c:** GL-10c is the full listing-copy template build and stays post-launch; GL-53 is the pre-launch guardrail subset and does not consume it. **Why it is a blocker and not housekeeping: the alternative is hand-repairing every title in the web editor at publish time — and the publish editor is already the one manual step this project consciously accepted (GL-37). Adding copy repair to it is how an accepted manual step becomes a manual pipeline.** **Owner action, separate and immediate:** candidate 49's live listing `4553104678` carries a non-compliant title today; decide delete-or-retitle (it is a test listing, so deleting is the cheap option — but check it is not wanted as a GL-52 control first). |
| GL-48 | M+C | **✅ CLOSED 2026-08-10 — §7's owner-gated live create is done, and the fix is confirmed by measurement rather than by status code, which is the standard this project set itself after GL-22a.** Candidate 49: exactly one Gelato product (`3e7abdce-c055-4609-ae68-aab19868c5a0`, `etsy_listing_id 4553104678`) — create-once held — six `group_product_variants` priced exactly to v4.11 §4, candidate 42 (GL-36's negative control) untouched, both `*_LIVE_MODE` flags reset after the run. `scripts/gelato_template_check.py` measured the **10x24 placed-artwork aspect at 0.4176** against the ~0.42 target; the pre-fix defect measured 0.65. **The placement-rect fix is proven live. Two riders leave with it.** (1) **The row closes and immediately spawns GL-52** — a *different* 10x24 defect, on this very product, that this measurement is structurally incapable of seeing: the rect is right, the crop inside the rect is not. That is the third time on this board a probe has returned a clean result it was guaranteed to return (GL-48's own dry-run divergence, the soak citing throwaway-DB runs as ruling interference out, and now this) — **a measurement that answers a narrower question than the one you care about is not a pass, it is a scope statement.** (2) A tooling nit worth one line: `gelato_template_check.py` crashes on the `″` character under the default Windows cp1252 console encoding; run it with `PYTHONIOENCODING=utf-8`. Pre-existing, unrelated to the fix, not worth its own row. Previous status: **🟡 ANSWERED AND FIXED IN-REPO 2026-08-09 — one bug, not two; the live create (§7) is the only item left and it is owner-gated.** Findings: `docs/2026-08-09-gl48-findings.md`, branch `gl48-crop-and-template`. **§3's verdict: the pipeline half was already correct.** We sent the cover crop; the shared placeholder transform letterboxed it. **The brief's measurement method could not work as written, and that is the reusable part:** `productImages[]` are **1000×1000 square scene previews, not the submitted print file** — six identical dimensions, zero information about the file's aspect. What *is* readable is the rectangle the artwork occupies on the paper inside the preview: on candidate 42 the primary sizes place at 0.709 in 0.708 paper and 5x7 at 0.725 in 0.725 (both fill), while **10x24 places at 0.651 inside 0.420 paper** — the signature of a transform authored for 0.684. Which file was submitted was then settled by *content*, not shape: the warm-toned arc spans 0.175→0.815 of the master and 0.000→0.998 of the crop, and the placed region reads **0.024→0.983** ⇒ the crop. **§4: all twelve `templateVariantId`s are unchanged** (verified against the live API, not assumed) and **exactly two `static_config.json` entries were stale** — `5x7_portrait` → `011_mt_sunday_brook.JPG`, `10x24_portrait` → `004_doorframe_bottles_madeira_color.JPG`; both corrected. **The landscape template still has the one-placeholder defect** — all six variants share `009_boat_serene_bnw_scotland.JPG` — recorded, not built, and inherited by GL-18. **§5 shipped, with one deliberate deviation from the brief:** the crop URL gate was *removed* rather than repointed at `is_r2_configured()`, because that swap would have regressed `test_real_create_fails_loud_for_secondary_group_when_r2_not_configured` — with R2 absent it falls back to the uncropped master, which is exactly what that test exists to forbid on a live call. Returning the crop's `durable_url` unconditionally keeps live+R2, live-without-R2 (fails loud) and dry-run+R2 (the fix) all on **one branch**. Regression test `test_dry_run_create_sends_the_same_hosted_print_crop_as_a_live_one`, confirmed to fail against the old gate. **§6 not investigated** — §3 says one bug, so the reuse branch is not implicated; it is still wrong (the `wanted <= existing` guard compares the DB to itself and never to Gelato) and moves to GL-50/GL-51's session. **What is owed:** one owner-supervised live create, verified by `python scripts/gelato_template_check.py <product_id>` — pass condition is the 10x24 variant's placed aspect landing near **0.42**, not 0.65. **Candidate 42's listing `4549960823` was deliberately left alone** (GL-36's negative control). Two standing principles added to `CLAUDE.md`: *dry-run changes what a call does, never which code path reaches it*, and *verify this integration by measurement, not by status code*. Previously: **🟢 ROOT CAUSE FOUND 2026-08-09 by the owner’s manual check, and half-fixed at source — which makes finishing it the most urgent item on the board.** The Gelato **portrait template carried one image placeholder shared by all six size variants**; it now carries **three** (primary / 5x7 / 10x24). That is the fit-versus-fill mechanism this row hypothesised, confirmed from the dashboard rather than from the API. **It also partially un-strikes GL-22d** and exposes why GL-22a Q1 got it wrong: Q1 compared 8x12 (0.667) to 5x7 (0.714) and **could not have detected a fit difference at those ratios** — it proved a shared placeholder does not force a shared *image*, which is true and was the wrong question. **What is now owed, and it is not optional: `config/static_config.json` is stale.** All twelve entries still name the two old placeholders, so the live config no longer describes the live template and **the next `create-from-template` call would use placeholder names that may no longer exist.** Contained only because the three scheduled tasks are Disabled. **Do not guess the new names — re-resolve them from the template**, and **do not treat a `200` as proof**: GL-22a Q2 already established that Gelato returns `200` for changes it silently drops. Brief: `docs/2026-08-09-gl48-crop-and-template-brief.md`. **The diagnostic `GET` in the original filing is still worth running, and now more than before** — it discriminates *one* bug from *two*, and after the config change a surviving code-side bug becomes much harder to see. Original filing below. Previously: **🆕🔴 The 10x24 (and by inference 5x7) print still arrives at Gelato letterboxed — and the leading hypothesis says this is a *template-authoring* defect, not a pipeline one.** Owner evidence 2026-08-09: the Gelato dashboard for candidate 42's product (`5e15c0b4-…`, Etsy `4549960823`, "Mid-Century Line Art Botanical Poster…", updated 08-04) shows the 25x60 / 10x24″ variant with the artwork **fitted inside white bars**, which is the same visual defect the first live run produced and which GL-14 was supposed to have closed. **What was verified in the repo, and it exonerates the obvious suspects:** `db/base_artwork/42_10x24_crop.png` is **4053×9728 = 0.4166** (10/24 = 0.4167) and `42_5x7_crop.png` is 0.7143 — the crop maths is correct and the file is correct on disk; the 10x24 group was approved with a variant row (id 32) so it was in the create payload; `create_candidate_gelato_product` does resolve a per-variant `image_url`; `gelato_client` does send one `imagePlaceholders[{name, fileUrl}]` per variant; and there is already a regression test asserting exactly this (`test_real_create_sends_hosted_print_crop_not_raw_master_for_10x24`). **So either the right URL was sent and Gelato is not honouring it, or it never got sent — and GL-22a Q1 does not settle which.** Q1 proved two variants sharing an `image_placeholder_name` accept *different* `fileUrl`s; it tested 8x12 (0.667) against 5x7 (0.714), **both within ~4 % of the master's 0.684**. That experiment cannot distinguish "Gelato fills the placeholder with your file" from "Gelato **fits** your file into the placeholder transform saved in the template" — at 5x7 the two are visually identical. At 10x24 (0.4167 vs 0.684) a fit produces exactly the observed bars. All six portrait variants share one template *and* one placeholder name, and that placeholder's saved scale/position was authored against `003_flower_in_stream_madeira_color.JPG` — an ordinary portrait photograph, not a 1:2.4 panel. **The decisive test is one read-only call**, and it splits the item cleanly: `GET /v1/stores/{storeId}/products/5e15c0b4-…`, then per `productImages[]` entry download the signed `fileUrl` and measure its pixel aspect. **10x24 image reads 0.4167 → we sent the right file and Gelato letterboxed it** ⇒ this is **M**, a Gelato dashboard fix: the 25x60 variant's placeholder needs its own authored fill, and possibly its own placeholder name — **which would partially un-strike GL-22d**, retired on Q1's evidence. **10x24 image reads 0.684 → we sent the master** ⇒ this is **C**, and the first place to look is the `if product_row["gelato_product_id"]:` reuse branch, which builds no crops, sends no `fileUrl`s, and whose `wanted <= existing` guard compares the DB **to itself** and never to Gelato — a product created early with only the primary group's four sizes passes that check silently. **One fix owed regardless of which branch wins:** `_image_url_for` gates the crop URL on `config.is_live_mode("GELATO")` and otherwise returns the uncropped master, so **the crop path never executes in a dry run** — the gate belongs on `config.is_r2_configured()` (is the URL fetchable?), not on live mode, and until it moves, no dry run can ever rehearse this. **Blocker because it is the one open defect the buyer receives**; a letterboxed 10x24 is a refund and a review, not a log line. | one live `GET` + aspect measurement → M (re-author the template placeholder) **or** C (fix the reuse branch) → the dry-run gate fix either way |
| GL-55 | C | **🆕🔴 Seasonal/holiday niches reach the owner's review queue as fully-drafted bad copy, and nothing between research and digest can see it (E9, 2026-08-10).** Findings: `docs/2026-08-10-e9-findings.md` §Claim (a). Four candidates in one run — **77** (`holiday_peak`), **78** (`diwali`), **79** (`black_friday_cyber_monday`), **81** (`new_year_refresh`) — carried the event straight into the description ("for the holidays", "Black Friday Cyber Monday Sale", "Welcome to the new year") on top of good artwork. **Read the provenance correctly or this row gets mis-scoped: all five (80, `engagement_season`, was rejected earlier) were created 2026-08-09T07:00:02Z, *before* GL-47 shipped, and today's live research cycle produced zero seasonal niches. GL-47 works. This is not a GL-47 regression.** What is real is the gap behind it: `compliance_draft.DRAFT_TEXT_PROMPT_TEMPLATE` interpolates `candidate['niche']` verbatim (line 39, `niche: {niche}`) and neither `FORBIDDEN_TERMS`/`FORBIDDEN_WORDS` nor `critic_pass` carries any seasonal awareness — so a seasonal niche from *any* source (GL-47 gap, future bug, or re-surfaced backlog, which is what happened here) becomes a bad draft with no gate in the way. **Owner call, GO-Live blocker until resolved one way or the other:** the target is a proper fix (event context either informs tasteful evergreen copy or is filtered before drafting); the fallback, if the fix is not ready by GO-Live, is a pipeline-wide strip of seasonal/holiday wording. A working proper fix relaxes this blocker on its own. **The GL-53 lesson applies directly and is not optional here: whatever is decided, a prompt instruction is a preference — the decision needs an assertion in code, next to it, that fails loud.** PRD: `docs/2026-08-10-gl55-gl56-prd.md` (signed 2026-08-10). **✅ SHIPPED 2026-08-10, branch `gl56-gl55-copy-redo-seasonal` — option (a), owner-signed.** `compliance_draft.SEASONAL_TERMS` is used at **both** ends in one commit: `sanitize_niche` strips event vocabulary out of the niche *before* the prompt interpolates it, and `check_seasonal_terms` — wired into `validate_listing_text`, so the existing 3-attempt draft retry loop feeds the failure back as correction text — raises on the model's output. The stated principle (§6.2, owner-chosen), which matters more than the entries: **a calendar date or a named festival/retail moment is blocked; atmospheric words for a season of *nature* ('autumnal', 'wintry') stay allowed**, because a design's subject may legitimately be seasonal without its copy being so. That line is why `new year` is on the list and `winter` is not. Option (c) — event context producing genuinely good seasonal copy — is recorded as the eventual target and stays with GL-10c, post-launch, so the stopgap is not mistaken for the destination. Fixtures are the four E9 niches. The list will have gaps; the claim is only that it fails loud when it matches and is one line to extend when it misses. | PRD sign-off → C in `compliance_draft` (+ the seasonal-source decision) → assertion + tests |
| GL-56 | C | **🆕🔴 There is no way to keep a good design and redraft only its copy — which is what is blocking recovery of a growing good-design/bad-copy backlog (E9, 2026-08-10).** Confirmed in code, not inferred: Telegram's `✏️ Edit` (`callback_data` `edit:{group_id}`, `digest.py:91`) lands in `publish_primary_group.handle_decision`'s `action == "edit"` branch, which deletes `critic_pass_attempts` + `listing_texts` + `group_messages`, discards the group contribution, **and then calls `generate.generate_for_candidate(..., correction_note=decision_notes)`** — a fresh FLUX generation that can return a visibly different design. Edit is therefore "redo the artwork", with no copy-only sibling. Four candidates from this run alone (77/78/79/81) are good-design/bad-copy and unrecoverable without it, and they sit on top of the older backlog. **Scope note that decides the shape of the work: this is a new action, not a change to Edit** — Edit's image-redo behaviour is wanted and has users. The new path redrafts `compliance_draft` + `critic_pass` only and must leave `base_image_*` untouched. **The hard constraint in CLAUDE.md is a free win here, not an obstacle:** a design is only ever image-generated once, so a copy-only redo is the option that *honours* it. PRD: `docs/2026-08-10-gl55-gl56-prd.md` (signed 2026-08-10). **✅ SHIPPED 2026-08-10, same branch.** New action `redraft:{group_id}` on a **second keyboard row** (`📝 Redo copy only`) — four buttons side by side truncate every label on a phone — and a `handle_decision` branch that clears `listing_texts` / `critic_pass_attempts` / `group_messages`, sets the candidate back to `generating` (so a crash mid-run is re-entered by the ordinary cycles rather than stranding it at `primary_review` with no copy), re-runs `compliance_draft`, then `critic_pass.run_critic_pass(copy_only=True)`. **That flag is the load-bearing part:** inside the critic retry loop it suppresses both the regen *and* `discard_superseded_attempt`, so the no-new-generation guarantee holds on a critic *failure* too, not only on the happy path — and the gallery survives, which it must, since nothing on this path re-renders it. Decision value reuses `'edited'` (it already means "redo this one, not terminal"); a new value would need a table rebuild for `groups.decision`'s CHECK and would behave identically — `decision_notes` carries the distinction. **Retry budget: RESET** (owner, §6.3): the attempts rows are deleted, and the owner is the gatekeeper on this path so there is no unattended loop to bound. `✏️ Edit` is untouched. Acceptance test asserts the artwork bytes on disk and `base_image_*` are identical across the call, and that `generate`/`primary_mockup` were never called. Backlog recovery of 77/78/79/81 stays a separate operational step behind GL-61's research-mode toggle, per §6.5. | PRD sign-off → C: new callback action + handler branch + digest button → tests |
| GL-57 | C | **🆕🟡 Every published listing shows the 10x24 mockup as its featured image, because `rank` is never sent to Etsy. Filed here rather than in housekeeping on the owner's own "could be elevated" note — and the recommendation is: elevate it.** Confirmed in code: `etsy_client.upload_listing_image` (`pipeline/etsy_client.py:69`) builds its multipart body with an `image` part and nothing else — **no `rank` field on any call path** — while `group_product.py`'s `_GROUP_RANK_SQL` already computes the correct primary-first / 5x7 / 10x24 order for its own upload loop. So the ordering intent exists, it just never leaves the machine, and Etsy defaults to last-uploaded-first. Reproduced **2/2** on the two candidates that reached a published listing on 2026-08-10 (84 and 87). Owner's manually-corrected reference order is attached to the E9 hand-off. **Why elevate:** the featured image is the entire click-through decision on an Etsy search grid, the fix is one parameter on one function, and every listing published before it ships is wrong in the one place that matters most. **What is *not* established and should not be assumed by the session:** Etsy's own default-ordering rule was not verified against live docs — the confirmed fact is the missing parameter, not the mechanism. Send `rank` explicitly for the whole sequence rather than only `rank=1` on the first image, and verify by reading the listing's images back, not by the upload's status code (GL-22a standard). Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §1. **SHIPPED 2026-08-11 (branch `e9-small-items-gl57-gl62`), live read-back still owed.** `upload_listing_image` takes an optional `rank` and sends it as a second multipart field; `patch_etsy_listing` passes the 1-based position from the `_GROUP_RANK_SQL` order, counted over the whole ordered list (including already-uploaded rows that the loop skips), so a resumed upload lands in the slot it would have on a clean run. Ranks go on **every** image, not just the first - no default-ordering rule is assumed. Tests assert the outbound body carries `name="rank"` with a well-formed boundary, that omitting it sends no field, and that the rank sequence is 1..n in group-rank order with `primary` first. **Not done:** the read-back verification on listing `4553335845`, which is a live mutation and waits on an explicit owner go-ahead (verify with `get_listing_images`, never by status code). **LIVE READ-BACK PASSED 2026-08-11 (owner-supervised, listing `4553335845`).** Pre-fix state confirmed on live data first: rank 1 was `8412127983`, candidate 87's **10x24** mockup - the last image uploaded - with the ten primary mockups sitting at ranks 5-13. Then the fix was exercised end to end: one primary mockup re-uploaded through `upload_listing_image(..., rank=1)`, read back with `get_listing_images`, and it was **position 0 of 14**. Temp image deleted afterwards; gallery back to its original 13 in the original order, nothing else touched. **One thing for the next reader: assert the POSITION, not the returned `rank` field.** The read-back transiently reported `rank=1` on two different images at once (the new one and the old rank-1) while ordering correctly - Etsy's own `rank` value lags the reordering, so a test that trusts that field will flake. **Still open, and buyer-facing:** listing `4553335845` (and any other listing published before this fix) still shows the 10x24 as its featured image. Correcting an already-published gallery means deleting and re-uploading all 13 images with ranks and rewriting `product_images.etsy_listing_image_id` - a separate operational step, not part of this fix. **✅ ROW CLOSED 2026-08-11 — the owner's manual dashboard pass fixed the featured-image order on all four drafts that carry the clean mockups, so the code fix and the existing-listing repair are both discharged for everything with a current gallery.** What that pass *also* returned is worth more than the fix, and it is now GL-66/GL-67: two good designs (*"Dense Wildflower Meadow Botanical Print…"*, *"Mid-Century Modern Botanical Poster…"*) are still drafts carrying **Gelato's default mockups and pre-GL-53 copy**, the second one as **two listings** (primary + 5x7) — which is the pre-v4.12 shape, not a bug in anything shipped. Any *published* pre-GL-57 listing still needs the delete-and-re-upload treatment described above; that is not GL-57's work and it travels with GL-67, where the same operation is already needed. | C: pass `rank` in `upload_listing_image` + caller → live re-verify by read-back |


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
| 1l | GL-66 | M+C | **🆕 Two good designs are stranded as drafts with Gelato's default mockups and pre-GL-53 copy (owner observation, 2026-08-11).** *"Dense Wildflower Meadow Botanical Print, Full Bleed Minimalist Wall Art, AI Generated Floral Poster, Printable Nature Decor"* and *"Mid-Century Modern Botanical Poster, Bold Abstract Leaves Print, Warm Muted Foliage Wall Art, Dense Retro Nature Decor"* — the second one as **two** listings (one primary, one 5x7 variant). Found during the GL-57 manual featured-image pass, which is the point: the four drafts with current galleries were fixed in seconds, and these two could not be, because the gallery is not the only thing out of date. **Both titles are self-evidently pre-GL-53** — `AI Generated`, `Printable` on a physical made-to-order poster — which is drift class (c), the most serious of the three GL-53 found. **The artwork is good and must not be regenerated** (CLAUDE.md: a design is only ever image-generated once). **Two listings for one design is the pre-v4.12 shape, not a defect in anything shipped** — same vintage as GL-58's candidates 1 and 39. Scope: the smallest possible instance of GL-67, and worth doing *as* the first instance of it rather than by hand, so the path gets exercised on two designs the owner already wants. Post-launch by the owner's own call; deliberately **not** a go-live blocker, since drafts are invisible to buyers. |
| 1m | GL-67 | IR+C | **🆕 There is no way to bring an existing design up to current standards without regenerating it (owner proposal, 2026-08-11).** The ask: point a script at a design, **skip image generation entirely**, re-derive the copy from the artwork, re-render the mockups, and update or republish the Etsy listing. **Most of it already exists** — `handle_decision(..., "redraft")` for the copy (GL-56), the compositor and gallery for the mockups, ranked upload (GL-57), create-or-reuse for the product. What does not exist is the entry point: "take this artwork, skip generation, rebuild everything downstream." That is one script over shipped stages, not new machinery. **The scoping answer that must not be rediscovered, because getting it wrong is expensive: for a pre-v4.12 design, migration cannot be a patch.** GL-22a Q2 is settled — no API path adds a variant to an existing Gelato product — so the operation is **republish as one new v4.12 listing, then delete the old one(s).** That is cheap on a *draft* (no reviews, no favourites, no ranking history, and GL-41's permanent-URL freeze does not bite on something that was never public) and a materially worse trade on a *published* listing, which loses its URL, its age and its stats. **The script must therefore state which of the two cases it is in and refuse to guess.** Second customer already waiting: correcting the gallery of any listing published before GL-57 needs exactly the same delete-and-re-upload-with-ranks step, so it belongs here rather than as its own row. First instance: GL-66. |
| 2 | GL-18 | C+M | **⚠️ INHERITED A KNOWN DEFECT 2026-08-09 (from GL-48): the landscape template has the same one-placeholder problem the portrait one had** — all six variants share `009_boat_serene_bnw_scotland.JPG`, so every size prints at that placeholder’s saved fit and **10x24 would letterbox exactly as portrait did.** Not urgent (landscape is not live) and now a **known** defect rather than a lurking one. Fix is the same shape as the portrait one: an owner-side dashboard edit adding per-group placeholders, then two `static_config.json` entries, then `python scripts/gelato_template_check.py <product_id>` to verify by measurement. **Do the dashboard half before any landscape build starts**, or the build is tested against a broken template — which is precisely how the portrait defect survived a two-night soak. **Landscape enablement.** Two halves: the compositor/config wiring GL-5 left portrait-only, and a landscape scene library. **Owner direction 2026-07-31:** do not re-derive prompts — take the *successful portrait prompts* for validated scenes, adapt them to landscape, and pass the **portrait render as Nano Banana's reference image** so the landscape version is the same room, same light, same props. Needs a landscape geometry card per group. **The landscape template's placeholder edit — GL-22d's twin — is struck by GL-22a Q1** (a shared placeholder name does not force a shared image), so this is now one fewer manual Gelato step than the plan assumed. |
| 3 | GL-25 | C | **Wire Nano Banana Pro into `replicate_client`.** Deferred, not rejected — `_predict(model, input_body, …)` is already model-generic, so the work is a model constant, an input body, **reference-image encoding** (which GL-18 needs anyway), per-scene provenance, and a polling fallback for the 60 s `Prefer: wait` window that cost 11 of 72 images in P4b1. Direct dependency of GL-18. |
| 4 | GL-26 | IR+C | **Mockup authoring / compositor refinement** so fewer technical defects reach the owner's eye. Named contents: the **grey band on the two held 5x7 portraits** (undiagnosed); `flat_leaning_bookstack`'s "stairs-effect", explicitly *not* explained by `de79795`; §6's **occluded-corner extrapolation** (fit the four edges, intersect them — currently a scene class is unauthorable and the workaround is "no props at corners"); §4.4's `gain_map` reference = a single 99th-percentile hotspot, which reads as a dull print; and `scene_intake`'s hard stop on any screen failure when the screen is stricter than the gate. |
| 4b | GL-63 | C | **🆕 Subject-level repetition is not what `brief_lint` measures.** Across E9's reviewed batch, a butterfly/dragonfly/insect subject appeared on nearly every design. The existing brief-diversity lint (R2-e) evidently keys on something other than subject, so a batch can pass it and still read as one design shown six times — which is a shop-level problem, not a per-listing one: the storefront grid is where a buyer sees them side by side. Not urgent, and worth doing before the library gets big enough that the repetition is baked in. Recorded alongside, not filed: candidate 80's dragonfly artefact (two tails, mismatched wing angles) was caught only by owner eyes at digest stage — no automated detection exists and none is proposed here. |
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
| GL-50 | C | **✅ CLOSED 2026-08-09 by GL-45, as a free side effect (confirmed on master 2026-08-10, `26db7bb`).** `migrate.py` now parses flags separately from the database path, so `migrate.py --check` no longer consumes `--check` as a path, no longer creates an empty file of that name, and no longer raises a false stale-schema alarm. **The row is kept for its second reason, which the fix does not retire:** a commit whose whole purpose was to make `check()` read-only (`f153266`) left the *entry point* — the only half an operator ever touches — broken for four days. **Verify the DoD before ticking anything downstream:** the fix arrived as a side effect of another item, so nobody has confirmed the no-create guard or the two-line regression test the row asked for. Check both during E4; if they are absent, that is ten minutes, not a session. Original filing: **`migrate.py --check` is neither read-only nor correct from the CLI (GL-38 finding, 2026-08-09).** `main()` does `db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH` **unconditionally**, so `--check` is consumed as the database path: `sqlite3.connect` then **creates an empty file literally named `--check`** in the repo root, `_current_version` reads 0, and it raises `schema_version is 0, expected 7` — **a stale-schema false alarm against a perfectly good database, plus a littered file.** The correct invocation is `migrate.py db/qhoto.sqlite3 --check`, which returns `schema_version=7, up to date`. **Two reasons this is worth a row rather than a one-line fix in passing.** (1) **It directly contradicts a commit that exists to prevent it** — `f153266 fix(gl35): make migrate.check() genuinely read-only` made the *function* read-only, and nobody checked the *entry point*, which is the only half an operator ever touches. (2) **It fails in the alarming direction on the one command a human runs when something is already wrong**, i.e. during an incident, when a false "your schema is stale" is at its most expensive. The library path is unaffected — `run_hourly.py:72` and `run_batch.py:116` call `migrate.check(db_path)` directly — so **the fail-fast guard itself is sound**; this is purely CLI argument handling. Fix: parse flags properly (`--check` is a flag, not a path), refuse to create a database that does not already exist on the check path, and add the two-line test that would have caught it. **Note it also means the kickoff's own Phase C step 10 verification was misleading** — a procedure that tells you to run a broken command is worse than one that omits it. | argv parsing + a no-create guard + one test |
| GL-51 | C+M | **🆕 The DB references artefacts by absolute path into a git-ignored directory, and nothing detects it when they vanish (GL-38 near-miss, 2026-08-09).** Retiring the GL-7 worktree would have **succeeded silently and orphaned the freshly promoted database.** Its `db/` held **1.6 GB of git-ignored artefacts, 289 files of which existed nowhere else** — the base artwork and mockups for candidates 43–86, i.e. exactly the rows the promoted DB references — and **24 candidate rows stored *absolute* `base_image_local_path` values pointing into it**. `git worktree remove` reports success either way. It was caught and repaired (robocopy the 289, rewrite the 24 paths, verify every target exists — **0 unresolvable paths across all 62 candidates**), but **only because someone thought to look.** **The defect is not the worktree; it is the two properties that made the worktree dangerous, and both survive the repair.** (1) **Absolute paths in a portable database.** `base_image_local_path` is machine-specific, which makes the DB non-portable by construction — and **GL-3 has a pre-committed VPS fork**, so this will recur the first time the pipeline moves host, with no worktree involved. Store paths relative to a configured artefact root and resolve at read time. (2) **No integrity check exists that reads the DB and asks whether the files are there.** `PRAGMA integrity_check` validates SQLite's own structure and says nothing about the filesystem the rows point at. A `--check`-style artefact sweep (every `base_image_local_path`, every `product_images` local row, count resolvable vs missing) is perhaps forty lines and turns a silent catastrophe into a startup refusal — and it is the natural companion to GL-35's schema guard, which already refuses to run against a database in the wrong *shape*. **The relationship to GL-30/GL-30b is worth stating so this is not mistaken for a duplicate:** GL-30 backed up the *mockup corpus*, and R2 holds the base artwork when configured, so the *bytes* are largely recoverable. **What is not recoverable is the mapping** — which row points at which file — and that is precisely what the 24 rewritten paths were. |
| GL-28 | M | **SynthID.** Every Nano Banana output carries an invisible watermark, and the store's photography is now all Nano Banana. Not an Etsy problem — the artwork is disclosed via `who_made: i_did` — but it should be a **recorded, conscious choice** rather than a thing discovered later. **2026-08-03: that reasoning now depends on GL-34.** If the disclosure moves off `i_did`, re-read this line before relying on it; the description-text disclosure is the part that survives either way. |
| GL-58 | C+M | **🆕 `SharedProductVariantError` is treated as retryable when it is structurally permanent — it will re-alert Telegram on every batch cycle, forever (E9, 2026-08-10).** Candidates **1** and **39** have 5x7 groups whose Gelato products predate v4.12, so `group_product.py` correctly refuses to add a variant (GL-22a Q2: no API path exists, and this is settled). `group_mockup.run_*`'s per-item handler then treats it like any other failure: it writes `failed_reason = 'gl54_group_mockup_failed: ...'` and leaves the group at `pending_generation`, commented "retryable next cycle". It can never succeed. **One correction to the E9 digest, worth carrying: the digest says the handler leaves no trace — it does, GL-54 gave it one.** The defect is narrower and entirely real: a durable reason is written, and the row is still handed back to the retry loop. **The fix is a permanence distinction the codebase does not currently have:** a structurally-unrecoverable error marks the group `failed_abandoned` immediately and alerts once; a transient one retries. `SharedProductVariantError` is the first member of that class and almost certainly not the last, so the classification wants to be a property of the exception, not an `isinstance` check at one call site. **Plus an M:** candidates 1 and 39's two groups need marking by hand, or the fix has nothing to stop alerting about. Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §2. **SHIPPED 2026-08-11 (C half), M half prepared and not run.** Permanence is a property of the exception, not an `isinstance` at a call site: `SharedProductVariantError.permanent = True`, read duck-typed via `getattr(exc, 'permanent', False)`. The two group-level per-item handlers (`group_mockup`, `primary_mockup`) now route through one shared `group_product.record_group_failure`, which marks the group `failed_abandoned` with a `(permanent)` reason instead of leaving it retryable. The stage still collects the failure and still fails once at the end of the loop - CLAUDE.md's swallowed-exception rule is untouched. **M half outstanding:** groups 2 (candidate 1) and 38 (candidate 39) need marking by hand; the exact rows and UPDATE are in the PR description, awaiting owner go-ahead plus a DB backup. **M HALF DONE 2026-08-11 (owner-supervised).** DB backed up to `db/qhoto.sqlite3.bak-2026-08-11-pre-gl58` first. Groups **2** (candidate 1) and **38** (candidate 39), both 5x7, both carrying the `gl54_group_mockup_failed` reason, marked `status='failed_abandoned'` with `failed_reason='gl58_permanent: pre-v4.12 Gelato product cannot take a 5x7 variant (GL-22a Q2)'`; 2 rows changed, verified by read-back. Checked before running: neither group owns any `product_images` or `group_product_variants` row, so excluding them takes nothing away from a published listing. `create_group_mockup`'s terminal guard skips `failed_abandoned`, so the every-cycle re-fail and re-alert stops here. No Gelato-side repair of the two legacy products - out of scope, nobody asked. |
| GL-59 | C | **🆕 Replicate's 60s synchronous wait produces false timeouts under batch bursts — candidates fail `generate` on jobs that succeeded in under four seconds (E9, 2026-08-10). Owner filed this as non-blocking; the recommendation on this row is to reconsider that before GO-Live.** Candidates 78 and 83 raised `ReplicatePredictionTimeoutError` while Replicate's dashboard showed the same predictions completing in **2.8s and 3.7s execution**. Not a contradiction: `replicate_client.py`'s own comment (lines 79-83) already states the `Prefer: wait` window assumes near-zero queue time, and firing nine candidates back-to-back at an account capped at 6 req/min (no payment method on file) queues them server-side past the client's window — the job then runs fast once its turn comes. The code names its own fix: **async submit + poll instead of synchronous wait.** The comment scoped that risk to `upscale_image`'s cold boot; E9 shows it landing on `generate_image` (flux-schnell) under burst load, which is the ordinary shape of a batch run. **Why it is arguably a blocker:** it silently costs real candidates at exactly the moment throughput starts mattering, and it scales *with* batch size — the thing GO-Live increases. Cheap mitigation if the full fix is deferred: stagger or cap per-cycle generate calls (see GL-61's candidates-per-batch knob). Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §3. **SHIPPED 2026-08-11 (full fix, not the mitigation).** `_predict` submits without `Prefer: wait` and polls the prediction's own `urls.get` until a terminal status, bounded at 600s with a 2s interval - queue time no longer counts against a latency budget. The 429 path is unchanged and still tested (a rate cap is not a timeout); a Replicate-side `failed`/`canceled` now raises the new `ReplicatePredictionFailedError` rather than being mislabelled a timeout; the timeout text now says "still queued/processing after Ns", which is true. Test covers the actual defect: a queued-then-fast prediction succeeds where it previously raised. GL-61's `CANDIDATES_PER_BATCH` shipped alongside as the queue-depth lever. |
| GL-60 | C | **🆕 `art_brief`'s Anthropic call is capped at `max_tokens=200` and truncates live — the same class of bug already fixed once for `critic_pass` (E9, 2026-08-10).** Candidate 81 failed `generate` attempt 1 with `TruncatedResponseError` ("truncated at max_tokens=200; raise the cap") and succeeded on retry, so the cost is a wasted attempt against the retry budget rather than a lost candidate — today. One call site: `pipeline/art_brief.py:194`, `max_tokens=200` on the Haiku model. Precedent: `compliance_draft` 1024→2048 (2026-07-23) and `critic_pass` 2048→4096 (2026-08-03), both after the same live symptom. **This is a one-line change and should ride along with whatever session is open** — it earns a row only because the class has now recurred three times, which is the argument for auditing every `max_tokens` in `pipeline/` in the same pass rather than raising this one and waiting for the fourth. Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §4. **SHIPPED 2026-08-11, audit included.** `art_brief` 200 -> 600 (a 75-word brief is ~110 tokens; the word cap is enforced by the prompt and `brief_lint`, never by `max_tokens`). **Audit of every `max_tokens` in `pipeline/`, five call sites:** `compliance_draft` 2048 and `critic_pass` gallery 4096 - unchanged, both already sized after the same symptom; `research_web_search` 4096 - unchanged, no truncation observed; `critic_pass`'s master-sanity vision call was riding the library default - **changed to an explicit 1024** with no behaviour change, because a raised default must never silently resize a caller. The two library defaults stay 1024 and remain defaults, not caps. |
| GL-61 | C | **🆕 Three operational knobs that do not exist, and their absence was felt during E9 (2026-08-10).** No `.env`/config control over (a) **candidates generated per batch cycle** — which is also GL-59's cheap mitigation, so this one has a second customer; (b) **error-message verbosity** in Telegram notifications; (c) a **research-mode toggle** — always-research / consume-pending-only / research-only-if-nothing-pending — to separate "make new candidates" from "process the approval backlog". (c) is the one with teeth: recovering the good-design/bad-copy backlog (GL-56) means running batches that must *not* pile new candidates on top. Follows CLAUDE.md's static-config rule — resolved once from config, never discovered at runtime. Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §5. **SHIPPED 2026-08-11, all three knobs, defaults reproduce today's behaviour exactly.** `RESEARCH_MODE` (`always` default / `consume-pending-only` / `if-nothing-pending`; an unknown value raises rather than being ignored; the safe-evergreen starvation fallback is gated too, since it is an automatic source; an on-demand topic is always honoured and in a non-`always` mode runs alone), `CANDIDATES_PER_BATCH` (unset = uncapped; the overflow is deferred, never dropped), `TELEGRAM_ERROR_VERBOSITY` (`full` default / `brief`). Documented in `docs/2026-08-11-e9-operability-runbook.md`. |
| GL-62 | C+M | **🆕 The three scheduled tasks capture no stdout/stderr, so a live run is only observable by polling the DB (E9, 2026-08-10).** `qhoto-batch-morning` / `-evening` / `qhoto-hourly` redirect nothing in their Task Scheduler actions. E9 spent real time guessing whether the batch process was working or hung, and settled it by CPU-time and DB polling rather than by reading a log. Two candidate fixes, and the second is the better one: redirect in the Task Scheduler action (M, five minutes, machine-local and lost on any re-registration) **or** add a file handler in the entrypoints themselves (C, travels with the repo, testable, survives a host move — which the VPS fork in GL-3 makes non-hypothetical). Cheap, and it is the difference between diagnosing the next live run and re-running it. Kickoff: `docs/2026-08-10-e9-small-items-kickoff.md` §6. **SHIPPED 2026-08-11 as the C option (`pipeline/runlog.py`).** Both entrypoints tee stdout and stderr into `logs/<job>.log` - only under `__main__`, so importing `main()` in a test writes nothing. Bounded at 5 MB with one rotation kept (10 MB ceiling). `redact` scrubs `TELEGRAM_ADMIN_CHAT_ID` (a credential per CLAUDE.md), the bot token and the four API keys before anything is written; adding a new credential env var means adding it to `_SECRET_ENV_VARS`. No Task Scheduler change needed. Tests cover the tee, the redaction and the rotation. |
| GL-64 | M | **🆕 One Gelato-dashboard thumbnail anomaly, recorded and not investigated (E9, 2026-08-10).** Candidate 84's listing ("Sage Green Branches Wall Art Print…") shows one of our own mockup images as its Gelato-side thumbnail, inconsistent with every other listing in the batch. No known buyer-facing consequence — the Etsy gallery is what a buyer sees, and that is GL-57's territory. Filed so that if it recurs there is a first sighting to date it from. |
| GL-65 | R | **🆕🔴 The Telegram tap-drop recurred live, and this time it was caught with an instrument — which is exactly why it now needs its own row rather than a line on GL-45 (E9, 2026-08-10).** Owner tapped approve/reject on candidates 80/84/87/88/90 with certainty; a **raw, no-offset `getUpdates` query against Telegram's own API, bypassing this app's stored cursor entirely**, showed the bot's server-side queue held **zero trace** of those taps. A re-tap minutes later landed cleanly with fresh `update_id`s. That rules out offset consumption inside `publish_primary_group` — independently — and places the loss at or before Telegram's own queue, outside anything this pipeline logs. **Second occurrence: candidates 57-60, 2026-08-08.** **How to read this against GL-45, because the two rows say different things and both are true:** GL-45 tested the path clean and its row is deliberately written as "tested, not diagnosed". E9 is the counter-observation that keeps the question open. **What must not happen next is another after-the-fact investigation — there is no evidence left to find, twice over.** The only tractable move is to instrument for the *next* occurrence: capture on the Telegram-app side (the owner's client), and/or a user-facing "did my tap register?" signal so a drop is visible in seconds instead of at the next hourly poll — noting GL-45's own finding that several minutes of silence after a tap is the *designed* behaviour, which is precisely what makes a real drop invisible. Brief: `docs/2026-08-10-e9-small-items-kickoff.md` §7. **DECISION RECORDED 2026-08-11: `docs/2026-08-11-gl65-tap-drop-instrumentation-decision.md`.** No code in the E9 small-items branch, by design. Recommended and awaiting the owner's yes: (1) client-side capture on the owner's phone until the next occurrence, (2) an `answerCallbackQuery` acknowledgement at receipt so a dropped tap is visible in seconds instead of at the next hourly poll - scoped as an acknowledgement only, not an early dispatch, and touching nothing in the cursor handling GL-45 already tested clean. Explicitly not doing: retrospective log-diffing, reproduction attempts, offset-logic changes. **✅ OWNER APPROVED item 2, 2026-08-11 — and the planning pass that received the approval owes it a correction, because as scoped item 2 cannot deliver what it promises and may deliver nothing at all.** Two facts the decision doc had separately and never put together. **(1) The ack already exists:** `publish_primary_group._ack` (line 47) already calls `answer_callback_query` on every dispatched decision, and the client function has existed since GL-45 — moving it to receipt removes only `handle_decision`'s own runtime from the latency. **(2) The dominant term is the cadence, not the dispatch point:** the poll is **hourly**, so tap→toast is up to ~60 minutes at either end of `process_update`, and Telegram rejects a stale `callback_query_id` ("query is too old…") on a bound that is minutes, not an hour. `_ack`'s own docstring — "a stale/expired callback query is a lost spinner, not a lost decision" — is correct and also means **the ack we already ship is probably failing in production nearly every time.** **So the lever is the poll cadence (hourly → 5 minutes) and the receipt-ack is the cheap rider that makes it useful.** Checked before recommending: `getUpdates` costs nothing and `run_hourly` adds no Replicate/Anthropic/Gelato/Etsy call; a collision with a batch raises `lock.LockHeldError` → exit 2, **no Telegram alert and no heartbeat row**, so 12× the cadence adds no noise and a skipped poll retries in 5 minutes instead of 60; `heartbeat_status.py` has no hardcoded staleness window, so it cannot be made to lie; `JOB_NAME = "hourly"` **stays** (renaming churns `heartbeats.job_name`, `heartbeat_status.JOB_NAMES`, the log filename and the task name for zero gain — record the misnomer, do not rename). **And the whole thing has a free falsification that should run first: `grep "answer_callback_query failed" logs/hourly.log` after the next scheduled run.** If the acks are failing, that is the evidence for the cadence change; if they are landing, the expiry reasoning is wrong and §1 of the kickoff gets rewritten instead of built. GL-62 shipped the log that makes this one command. Kickoff: `docs/2026-08-11-e10-kickoff.md` §1. **✅ E10a SHIPPED 2026-08-11 (branch `e10a-ack-and-cadence`), and it is smaller than scoped because two of the three scope items were already in the tree.** **The falsification could not run: `logs/hourly.log` does not exist yet** — GL-62 wired the log but no scheduled hourly run has happened since, so the grep returns nothing and that is an absent instrument, *not* evidence the acks are landing. Run it after the first 5-minute-cadence run; `logs/telegram_getupdates.log` meanwhile shows taps reaching the poll ~7 minutes after the message timestamp, consistent with the expiry reasoning. **Scope item 1 was already done:** the `_ack` in `process_update` has sat *above* the `handle_decision` dispatch since GL-45 (its own comment says so), so 'ack at receipt' was shipped behaviour and reshuffling it a few local-SQLite statements earlier buys zero latency — not done, deliberately. **Scope item 3's ordering half was also already covered** by `test_process_update_acknowledges_before_dispatching_the_decision`. **What actually shipped:** the missing other half — `test_process_update_records_the_decision_even_when_the_ack_fails` (a raised *'query is too old'* still dispatches, still returns, still logs the event accepted), so `_ack`'s swallowing is now asserted rather than assumed; plus the cadence, misnomer and rejected-alternatives record in `run_hourly.py`'s docstring and `docs/2026-08-11-e9-operability-runbook.md`. 787 green. **The remaining half of E10a is manual and unblocks E10b/E10c: the owner edits the Task Scheduler trigger to repeat every 5 minutes and re-enables the hourly task.** |

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
**Twenty-one of twenty-four ticked, and every remaining code-side unknown now sits inside ONE run (2026-08-10, latest).** GL-54 merged (PR #11, `3a5cb72`, 744 green) — it was housekeeping, not a gate row, so the count is unchanged; what changed is that **nothing is left between here and E9.** The three open gate rows are **GL-7** (targeted re-soak), **GL-11** (Etsy's reply — still the only clock outside our control) and **GL-52** (verification only: template repaired, config resynced and committed at `0a4d908`, nothing yet created from it). **E9 discharges GL-52 outright and takes a real bite out of GL-7** — its three unproven DoD items are all observable in a live run, and two of them (the injected-failure→Telegram path, the stale-schema refusal) are *more* observable now that seven loops actually raise. **The honest statement of where this project stands: one live run and one email.** *Superseded count:* **Twenty-one of twenty-four ticked (2026-08-10, late) — GL-53 merged (PR #10, `ed41f97`, 742 green), leaving three: GL-7, GL-11, GL-52.** GL-52 is open on verification only: the template is repaired and its config resynced, but nothing has been created from it. **All three of the remaining code-side unknowns now collapse into a single live run** — a candidate drafted after GL-53 (proves the guardrail in production), published to a fresh Gelato product from the repaired template (proves GL-52), with the §3c `fileUrl` rider tested for free along the way. That run is E9. **One thing goes first and it is not the run: GL-54**, the ten-minute sweep of the four remaining GL-46-shaped loops — because E9 costs Replicate money and owner attention and passes through every one of them. *Superseded count:* **Twenty of twenty-four ticked (2026-08-10) — and the four that are open are nameable in one line each, which is the first time that has been true since the soak paused.** E2 + E3 closed four rows in a day: GL-45 (tested clean), GL-48 (live create measured), GL-46 and GL-47 (built and merged, PR #9). That takes the ticked side from sixteen-and-a-half to twenty. **Two new blockers join the denominator, which is why the gate moves from twenty-two to twenty-four: GL-52** (the 10x24 crop-within-rect defect, found by eye in the same run that measured the rect as correct) **and GL-53** (listing copy carrying an AI disclosure and digital-download wording that the shipped decisions say it must not carry). **The four open items: GL-7** (the targeted re-soak and its verdict — still the only substantial one), **GL-11** (Etsy's reply, still the only clock we do not control), **GL-52**, **GL-53**. **Both new rows are the same lesson in different costume, and it is the lesson this project keeps re-learning: a check that cannot see the failure mode is not a check.** GL-48's aspect measurement was blind to GL-52 by construction; `validate_listing_text` was blind to GL-53 by omission. Neither was a surprise to the code — both were surprises to us. **Two of the four are now sessions of a few hours, and they are parallelisable** (disjoint files, no live API writes), so the honest statement is: the project is one diagnosis, one guardrail, one short re-soak and one email from launch. *Superseded count:* **Fifteen of eighteen ticked (2026-08-08)** — GL-10 and GL-10d both
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

**E1. GL-48 — ✅ DONE 2026-08-09 in-repo; one owner-gated live create
outstanding, and it rides along with E2 rather than needing its own run.**
Original entry: **GL-48 — finish the template fix.** Promoted ahead of GL-45 for one
reason: the owner's template edit left the system **half-fixed**, and a live
integration whose config no longer describes its remote template is a worse
state than the defect it replaced. It also **gates E2**: `run_hourly.py`
reaches the publish gate and the publish gate reaches Gelato, so GL-45's test
run cannot safely happen first. Brief:
`docs/2026-08-09-gl48-crop-and-template-brief.md`.

**Track E, revised 2026-08-10 — the shape changed: E2 and E3 are now
parallel, not sequential.** GL-45's build is on master (PR #8), which turns E2
from a build into a single test run, and — the part that actually unlocks the
parallelism — replaces the *convention* "never run a second process against
this bot token" with two enforced guards (a `sha256(bot_token)` lock in the
system temp dir, and migration 8's `db_identity` refusing a poll from a
non-canonical DB). **That convention was the only reason E3 had to wait for
E2.** It no longer holds, so:

- **E2 (owner, manual, ~45 min of wall clock, most of it waiting)** — the live
  reproduction run. Runbook: `docs/2026-08-10-e2-live-reproduction-runbook.md`.
- **E3 (Claude Code session, code only, no live API calls)** — GL-47 then
  GL-46. Kickoff: `docs/2026-08-10-gl47-gl46-kickoff.md`.

**They touch disjoint files** (`publish_primary_group` / `telegram_client` /
Task Scheduler vs `research.py` / `generate.py`) and disjoint runtimes (the
hourly task vs pytest). **Running them together is also the cheapest available
test of the GL-45 guards**: an E3 session runs pytest against 1,000+ throwaway
databases, which is precisely the second-consumer shape that was the leading
suspect. If the guards work, E2's log stays clean while E3 hammers. Record
that as an observation either way — it is free evidence about the one
hypothesis that is still open.

**One ordering constraint survives, and it is a money constraint, not a
correctness one: both batch tasks stay Disabled until E3 lands.** E2 enables
`qhoto-hourly` only. `run_batch` is what manufactures out-of-season candidates
(GL-47) and swallows their failures (GL-46).

**E2 ✅ RUN 2026-08-10 — clean, and it discharged all three riders it was
built to carry: GL-45's reproduction (row 1 — path works, root cause
unproven), GL-38's Phase D step 13 (heartbeat landed in the root DB), and
GL-48's live create (10x24 placed aspect 0.4176). **It also found what it was
not looking for — GL-52 — by the owner opening the Gelato Design editor and
looking at the print.** Findings: `docs/2026-08-10-e2-findings.md`. Scheduled
tasks restored: `qhoto-hourly` back to Disabled, both batch tasks Disabled
throughout. Original entry: **E2. GL-45 — the Telegram drops. Build ✅ on master; the test is what is
left.** Brief:
`docs/2026-08-09-gl45-telegram-drops-brief.md`, already updated with §0 —
`getWebhookInfo` came back clean (`url: ""`, no `allowed_updates`), which
**eliminates H1 entirely** and promotes the second-consumer hypothesis, now
supported by `pending_update_count: 0` and by **19 `update_id`s missing from
`telegram_events_log`**. First action is not code: **grep the throwaway DB
copies for those 19 ids.** If they are there, the case closes with no pipeline
bug — correct code, wrong operating practice — and the work becomes the guard
(a lock keyed on the **bot token**, not the script directory) plus the tap
acknowledgement.

**Operational instruction for E2's test run, and it is not optional: enable
ONLY the hourly task. Both batch tasks stay Disabled until E3 lands.**
`run_batch` is what manufactures out-of-season candidates (GL-47) and swallows
their failures (GL-46); spending Replicate money re-observing two characterised
defects in order to test a Telegram fix is exactly the trade the soak was
paused to stop making.

**That one run discharges three outstanding items — watch all three
deliberately, because free riders are the ones that get ticked unchecked:**
(a) GL-45's own reproduction; (b) **GL-38's skipped Phase D step 13** — the
root tree has still never executed, so confirm the heartbeat lands in the
canonical DB; (c) **GL-48's owner-gated live create**, verified by
`python scripts/gelato_template_check.py <product_id>`, pass condition being
the 10x24 variant's placed aspect.

**E3 ✅ DONE 2026-08-10 — one session, both rows, PR #9 merged (`4f85ec9`),
733 green. The parallel-with-E2 bet paid twice:** it saved a session's
wall-clock *and* its pytest churn became the free concurrent-pressure test of
GL-45's guards, which E2's log passed clean. Original entry: **E3. GL-47 then GL-46 — now runnable in parallel with E2 (see the revision
note above), one session.** GL-47 stops the
pipeline creating candidates it should never create; GL-46 makes it loud when
a candidate fails. Doing GL-46 first means building a notification channel
whose first job is to tell you about out-of-season candidates you did not
want. Both are small; together they are one session.

**Track E, revised again 2026-08-10 (evening) — E2 and E3 are both done, and
the two rows they produced are the new head of the track. E7 and E8 are
parallel for the same reason E2 and E3 were: disjoint files, disjoint
runtimes, and neither writes to a live API.**

**E7. GL-53 — the listing-copy guardrail. Claude Code, code only, no live
calls, small.** Kickoff: `docs/2026-08-10-gl53-listing-copy-guardrail-kickoff.md`.
Touches `pipeline/compliance_draft.py` and its tests and nothing else. **Do
this one first if only one session is available**, because it is the one of the
two whose cost is known, and because every draft written between now and the
fix is another one that has to be repaired by hand at publish time.

**E8. GL-52 — and the shape changed within hours of filing it, because the
five minutes of evidence got taken instead of scheduled.** Kickoff:
`docs/2026-08-10-gl52-10x24-crop-kickoff.md`. **The submitted file was measured
and looked at: 4053×9728, full master height, whole flower, whole stem. Our
crop removes width only — it is arithmetically incapable of the loss the owner
saw.** So E8 is **not a coding session**: it is (1) an **owner dashboard check**
on the 10x24 portrait template variant's saved fit, ~10 minutes, the same
action that fixed GL-48; and (2) a **small code rider worth doing regardless** —
the pipeline has no way to observe this class of fault, since
`gelato_template_check.py` measures the placed rectangle and nothing ever
compares the submitted file's content to what the template does with it.
**Rider (2) belongs with E7's session, not its own** — both are "add the
assertion the decision was resting on".

**E8 status 2026-08-10 (late): fix applied, config repaired, verification
still owed.** Both edited variants MISMATCHed as predicted; `static_config.json`
now names `55_5x7_crop.png` and `65_10x24_crop.png`, both measured on-ratio.
All twelve variant ids survived. **The row stays open on one thing only: no
product has been created from the repaired template**, so the next real create
is the test — measured *and* looked at. Superseded: **the owner applied the fix before the check
was run — template placeholders re-authored with correctly-cropped images.
Mechanism sound, verification outstanding, and the row now carries a
higher-probability *new* risk than the one it was filed for: the placeholder
names are the image filenames, so `static_config.json` may be stale as of
this edit. `python scripts/gelato_template_check.py` (no arguments,
read-only) is the first action of the next session or sitting, ahead of
everything else on this track.**

**E7 ✅ DONE 2026-08-10 — GL-53 merged, PR #10 (`ed41f97`), 742 green.** The
batch-task hold it imposed is **lifted**: `compliance_draft` can no longer
produce the copy the hold existed to prevent.

**E9. The verification run — one live candidate, and it discharges everything
that is left on the code side.** Runbook:
`docs/2026-08-10-e9-verification-run-runbook.md`. **Type M+T, owner-driven, not
a coding session** — nothing needs writing; what is needed is one candidate
taken end to end and *looked at*. Four things ride on it, and E2's lesson
applies verbatim: **riders that arrive free are the ones that get ticked
unchecked.** (a) **GL-53 in production** — does a real cycle now emit clean copy,
or does the guardrail reject every attempt and starve the candidate? Both
outcomes are informative and the second is the one nobody has tested. (b)
**GL-52** — a fresh Gelato product from the repaired template, measured **and
opened in the Design editor**, because the aspect number is blind to
crop-within-rect by construction. (c) **The §3c rider** — whether
`get_product` echoes `fileUrl` per variant was never called live. (d)
optionally one or two of **GL-7's three unproven DoD items**, but only the ones
you will actually watch.

**E9 does not go first. GL-54 does** — the ten-minute sweep of the four
remaining GL-46-shaped loops. E9 costs Replicate money and passes through
`primary_mockup`, `critic_pass`, `digest` and both `publish_*` cycles, **every
one of which can currently fail per-item in silence.** Paying for a live run
through stages that cannot report their own failures is how a soak spends two
nights proving nothing — which this project has already done once.

**E4. GL-51 only — GL-50 closed itself inside GL-45 (2026-08-10).** What is
left of E4 is the absolute-path/artefact-integrity defect, plus a ten-minute
audit of whether GL-50's fix arrived with the no-create guard and the
regression test the row asked for (it arrived as a side effect, so nobody
checked). Previously: **GL-50 and GL-51 — the two GL-38 defects.** Small, and both belong with a session that is already in the repo rather than as their own. Original E3 (GL-48) is now E1. Superseded text: One read-only `GET` decides whether this is a
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

---

## Part 4 (cont.) — Session log (2026-08-10)

**GL-45 is on master (PR #8, `c17b869`; code `26db7bb`; 724 green), and the
board changes shape more than the row does.** The row itself moves from a
build to a test: everything the brief asked for shipped, the root cause did
not get proven, and one live run is what separates those two states. What is
worth writing down is the **three second-order effects**, because each of them
retires something the plan has been carrying for days.

**1. The parallel-work ban is retired by construction, not by judgement.**
Since GL-38 the standing operational rule has been "one bot token, one cursor,
so do not run anything else". That rule was enforced by nobody — it was a
sentence in a document, and the leading hypothesis for the drops is that it was
broken by pytest, silently, a thousand times. GL-45 replaced it with two
mechanisms: a lock keyed on `sha256(bot_token)` in the system temp dir (one
token, any number of processes, any number of trees) and migration 8's
`db_identity`, which makes `run_publish_primary_group_cycle` refuse to poll the
cursor from a database that is not the canonical file. **A convention that is
violated silently is worth less than no convention at all**, because it
produces confident reasoning about a property nothing checks — which is
precisely how the soak findings cited the throwaway-DB runs as *ruling
interference out*. That is the general lesson, and it is the same one GL-48
taught in a different costume (a probe whose negative result is guaranteed by
its design is not evidence).

**Concretely: E2 and E3 can now run at the same time**, and doing so is the
cheapest test of the guards that exists. E3 is a pytest-heavy session against
throwaway databases — the exact second-consumer shape under suspicion. If E2's
`logs/telegram_getupdates.log` stays clean while E3 runs, that is free evidence
on the one open hypothesis. Watch it deliberately; do not let it be a free
rider that gets ticked unchecked.

**2. GL-50 closed itself.** `migrate.py` now parses flags before paths as a
side effect of GL-45's work, so E4 collapses to GL-51 alone. **Ten minutes of
audit is still owed** — the row asked for a no-create guard and a two-line
regression test, and a fix that arrives as somebody else's side effect has
nobody attesting to its DoD.

**3. The Telegram tap-feedback UX item was already built, and the post-launch
row that supposedly holds it is now misleading.** This was an explicit question
this session, and the answer is worth recording because it is the opposite of
what the board implies. Post-launch item 7 reads "Telegram UX polish — richer
inline buttons, edit flow, digest legibility", and the natural reading after
GL-45's ambiguity is that a dropped tap is still visually indistinguishable
from a slow one. **It is not.** `publish_primary_group._ack` fires
`answerCallbackQuery` *before* dispatch, and `_mark_decided` replaces the whole
keyboard with a single non-actionable label — `✅ Approved`, `✏️ Edit
requested`, `🚫 Rejected` — carrying `noop:<group_id>`, so a re-tap is answered
"Already decided" rather than re-deciding. Both discard paths (not-admin,
untracked message) are answered too. Nine tests cover it, including the
never-raises property, which matters: the decision is durably recorded before
the acknowledgement is attempted, so a failed edit costs a spinner and not a
decision.

**What is genuinely left in item 7, sized rather than described** (this is an
estimate, not a PRD, and none of it is load-bearing):

| Item | Size | Worth doing? |
|---|---|---|
| Live confirmation that the edit actually renders on the owner's client | 0 — rides on E2 | Yes, free |
| Strip the button off the *superseded* message when a group is re-rendered after `edit` (today the old message keeps a live keyboard; the tap is correctly refused as untracked, but it looks tappable) | ~1 h | The one real gap |
| Decision timestamp/author in the label (`✅ Approved 19:42`) | ~20 min | Cosmetic |
| Surface a failed `editMessageReplyMarkup` beyond a `print` | ~30 min | Only if E2 shows it failing |
| Richer digest legibility, edit-note flow | unestimated | Post-launch, unchanged |

**The honest read: the expensive half of item 7 was paid for inside GL-45, and
the remaining hour is optional.** The reason to note it precisely rather than
leave it as "polish" is that the *rationale* for the UX work was diagnostic —
"the owner cannot tell a dropped tap from a slow one" — and that rationale is
discharged. If the item is ever re-scoped, it should be re-scoped as UX, not as
observability.

**Two documents written this session, both deliberately self-contained for a
cold session:** `docs/2026-08-10-e2-live-reproduction-runbook.md` (owner,
manual, discharges three items in one run) and
`docs/2026-08-10-gl47-gl46-kickoff.md` (Claude Code, code only, no live API
calls).


## Part 4 (cont.) — Session log (2026-08-10, evening — E2 + E3 outcomes)

**Four rows closed, two opened, and the two that opened were both found by a
human looking at the product rather than by anything the pipeline measures.**
That is the sentence worth carrying out of this day.

**What the parallel bet returned.** E2 and E3 ran at the same time on the
strength of GL-45's guards replacing a convention nobody enforced. Both
completed, neither interfered, and the interference test came free: E2's three
real hourly log entries fall inside the window E3's pytest run was hammering
~1000+ throwaway databases, and the raw Telegram log across that window is
clean — sequential offsets and update_ids, no gaps, no duplicates, no foreign
entries. **The `sha256(bot_token)` lock and the `db_identity` guard hold under
exactly the shape that was the leading suspect for the 08-09 loss.** That is
affirmative evidence, and it is the strongest thing anyone got this week. It
still does not explain 08-09 — it means the mechanism cannot recur, which is a
different and lesser claim, and GL-45's row is written to keep those two apart.

**GL-52: the instrument was pointed at the wrong question, again.**
`gelato_template_check.py` measured the 10x24 placed-artwork aspect at 0.4176.
That is correct, it closes GL-48, and it is also completely silent on whether
the artwork *inside* that rectangle is the right crop — which it is not. The
top of the flower and the bottom of the stem are cut off in the live product.
**Three times now this board has recorded a probe returning a clean result it
was guaranteed to return:** GL-48's dry-run divergence (the test run was not
executing the code with the bug), the soak citing throwaway-DB runs as ruling
interference out, and now an aspect measurement standing in for "the print
looks right". The general form is worth stating once: **a measurement that
answers a narrower question than the one you care about is not a pass, it is a
scope statement** — and it should be recorded with its scope attached, not with
a tick.

**GL-53: removing a constant is not the same as removing a behaviour.** On
2026-08-06 GL-37 concluded the AI disclosure belongs in the structured
publish-time tick and set `DISCLOSURE_TEXT = ""`, with a careful comment
explaining the precondition. What nobody checked is whether the *drafts*
stopped carrying one. They did not: 27 of 27 descriptions contain the sentence,
in drafts written on 08-08 and 08-09, because `DRAFT_TEXT_PROMPT_TEMPLATE`
opens by telling the model it is writing about "an AI-generated … poster" and
then asks it, two paragraphs later, not to say so. **The audit also turned up
something nobody was looking for and which is worse than the thing that
prompted it: 25 of 27 drafts sell a `printable` / `Instant Digital Download`
version of a physical made-to-order poster.** That is not a compliance nicety,
it is a listing that describes a product the shop does not sell.

**The structural read, which is the reason GL-53 is a blocker rather than a
copy edit:** `validate_listing_text` enforces title length and tag count and
length. Nothing else in the pipeline inspects generated copy at all. Every
copy-level decision this project has made — GL-37's disclosure position,
GL-43's keyword bucket, GL-10c's future template — has been enforced by
instructing a language model and hoping. **The fix is not the prompt; the fix
is that a decision the pipeline depends on gets an assertion that fails loud.**
The prompt change is the cheap half and it goes in the same commit.

**Process note, positive.** E2 was scoped "Type: M, no code is written here",
and it held that line even after finding GL-52 — it recorded the defect and
stopped rather than starting a diagnosis at 11pm. That is why GL-52 exists as a
clean row with an unbiased first question instead of a half-investigation
somebody has to unpick. Same shape as the GL-33/34 session stopping at a
blocked control. **Both times the discipline cost an hour and saved a day.**

---

## Part 4 (cont.) — Session log (2026-08-10, late — E9 triage)

**E9 passed on every claim it was written to test, and the eleven things it
returned are all things it was not looking for.** That is the shape of a good
verification run and it is worth saying plainly before the list of defects
below buries it: GL-53 was observed accepting a genuinely clean draft for the
first time (candidate 87), GL-52's 10x24 crop was confirmed clean by eyes on
the product, GL-53 and GL-47 both closed as intended, and candidate 87 is a
real, live, six-variant listing produced end-to-end by the pipeline.

**Eleven items triaged into the board: GL-55 through GL-65.** Two go-live
blockers by the owner's own call (GL-55 seasonal copy, GL-56 copy-only redo),
one filed as a blocker on the owner's "could be elevated" note (GL-57 the
featured image), five in housekeeping, one post-launch, one investigation
(GL-65 the tap-drop), one recorded-and-parked (GL-64).

**Two of the digest's claims did not survive a read of the code, and both
corrections make the underlying items smaller and clearer.** (1) The
`SharedProductVariantError` handler is *not* trace-free — GL-54 already gave
it a `failed_reason`; the real defect is narrower, that a durable reason is
written **and the row is still handed back to the retry loop**, so the fix is
a permanence distinction rather than a logging one (GL-58). (2) The
`publish_primary_group` and `group_mockup` line numbers in the digest have
drifted since GL-54; the behaviours are exactly as described, the citations
are not. Neither correction changes a priority. Both are the reason the
verify-before-filing step exists.

**Where this session disagrees with the owner's classification, stated once so
it can be overruled deliberately rather than by omission: GL-59 (Replicate's
false timeouts) belongs on the blocker list.** It silently costs real
candidates, and it scales with batch size — which is the one variable GO-Live
increases. It is filed in housekeeping as instructed, with the argument on the
row. GL-60 (`max_tokens=200`) is correctly non-blocking today only because the
retry absorbs it.

**The pattern across GL-55, GL-57 and GL-58 is one pattern, and it is the same
one GL-53 named:** in each case the pipeline already computes the right answer
internally and fails to enforce or transmit it. `_GROUP_RANK_SQL` knows the
correct gallery order and never sends `rank`. `group_product.py` knows the
variant can never be added and hands the row back to the retry loop anyway.
`compliance_draft` is told not to write seasonal copy and nothing checks. **The
recurring defect class in this project is not wrong logic — it is correct logic
that never reaches an assertion or an API call.** Worth carrying into all three
sessions as a review question rather than re-deriving it a fourth time.

**Deliverables from this triage:** PRD (unsigned, needs sign-off before any
code) `docs/2026-08-10-gl55-gl56-prd.md` for the two blockers; kickoff
`docs/2026-08-10-e9-small-items-kickoff.md` for GL-57 through GL-62 and GL-65.
Findings of record: `docs/2026-08-10-e9-findings.md`. All three scheduled tasks
are Disabled and two listings are deliberately live (candidates 49 and 87) —
re-read the findings doc's teardown section before the next run rather than
assuming a clean board.

---

## Part 4 (cont.) — Session log (2026-08-11 — planning pass, E9 integration → E10)

**Two code sessions landed and the board's open set is byte-identical to what it
was on 08-10.** GL-55, GL-56, GL-57, GL-58, GL-59, GL-60, GL-61, GL-62 all
closed; GL-7, GL-11 and GL-52 all still open. That is not a criticism of either
session — every one of those rows was real and GL-59 in particular would have
cost candidates on the very night that is left — but it is the fact a planning
pass exists to state plainly: **the last stretch of work has been everything
except the critical path, and the critical path is one live night and one
email.**

**The gate count was wrong and had to be re-derived, which is its own small
lesson.** The E9 triage added three rows to the blocker table and never touched
the denominator, so the standing count ("twenty-one of twenty-four") silently
described a smaller board than existed. Corrected to **twenty-four of
twenty-seven**, with the derivation written into the header so the next reader
audits it instead of trusting it. A count nobody re-derives is a count nobody
should trust — the same reasoning that got the 08-09 brief its three
corrections.

**Where this pass disagrees with a shipped decision, stated once: GL-65 item 2,
as approved, cannot do what it says.** The owner approved "an
`answerCallbackQuery` acknowledgement at receipt, so a dropped tap is visible in
seconds". Reading the code found two things the decision doc had separately and
never combined: the ack **already exists** at dispatch (`_ack`, line 47, since
GL-45), and the poll is **hourly** — so tap→toast is up to an hour at either end
of `process_update`, and Telegram rejects a stale `callback_query_id` on a bound
of minutes. The approved change moves a toast that is probably never arriving
from one place it cannot arrive to another. **The lever is the cadence; the ack
is the rider.** Recommended: hourly → 5 minutes, which was checked against lock
contention (fails closed, silent, no heartbeat, no alert), API spend (none —
`getUpdates` only), `heartbeat_status.py` (no hardcoded window) and the
`JOB_NAME` misnomer (keep it; renaming churns four things for zero gain). **And
it has a free falsification that runs first:** one `grep` of
`logs/hourly.log` for `answer_callback_query failed`. If the acks are landing,
this whole paragraph is wrong and the kickoff's §1 gets rewritten rather than
built. **That grep is only possible because GL-62 shipped yesterday** — the
first time an operability item paid for itself inside a day.

**The prerequisite the "operational run" framing hid.** The GL-56 backlog
recovery of candidates 77/78/79/81 was handed off as an operational step waiting
on GL-61's research-mode toggle. It needs one more thing that nothing had
recorded: **all four groups already hold a `group_messages` row**, and
`run_digest_cycle` excludes exactly those — so no re-send, and therefore **no
`📝 Redo copy only` button**, because those four messages were sent by pre-GL-56
code. Worse, their keyboards are still live: a tap on `✏️ Edit` there regenerates
the artwork, which is the precise loss GL-56 was built to prevent. Verified
against the live DB rather than inferred (message ids 328/397/339/408, groups
87/93/88/94, all `pending_review`, no decision). The recovery path that works is
`handle_decision(conn, candidate_id, group_id, "redraft", …)` called directly —
it clears `group_messages` itself, so the next digest cycle re-sends with the new
two-row keyboard. **A shipped feature reachable only through a button that does
not exist on the messages it needs to act on is not yet shipped for the case it
was built for.**

**The sequencing insight, and it removes a real cost from the board: the backlog
recovery is the live night's fuel.** GL-52 needs one fresh Gelato create from the
repaired template. Under v4.12 a create happens when a candidate's three groups
are all decided. So driving one *recovered* candidate through publish produces
that create — **GL-52 and GL-7 both close without generating a single new
candidate and without spending Replicate money.** Two rows that have each been
open for over a week turn out to be discharged by a run that was already going to
happen for a different reason.

**Owner actions integrated:** GL-65 item 2 approved (with the correction above);
the manual featured-image order fixed on all four current-gallery drafts, which
closes GL-57 outright; and the observation that pass produced — two good designs
stranded as drafts with Gelato's default mockups and pre-GL-53 copy, one of them
as two listings. Filed as **GL-66** (recover those two) and **GL-67** (the
general migrate-to-current-standards path). The scoping answer is on the rows so
no session re-derives it: for a pre-v4.12 design, migration is **republish as one
new listing and delete the old drafts**, not a patch — GL-22a Q2 settled that no
API path adds a variant to an existing Gelato product. Cheap on a draft, a bad
trade on a published listing (GL-41's frozen URL, plus age and stats), so the
script must say which case it is in and refuse to guess.

**One standing state change: the three scheduled tasks are a decision now, not a
dependency.** GL-58 was why they were masked; the C half shipped and groups 2
and 38 are marked, so the every-cycle re-fail cannot recur. Recommendation on
the kickoff: hourly on immediately (at the new cadence), the two batch tasks on
only for the night of E10c, with `RESEARCH_MODE=consume-pending-only`, and left
on afterwards only if the night passes.

**Deliverables from this pass:** `docs/2026-08-11-e10-kickoff.md` — E10a (GL-65
item 2 + the cadence), E10b (the backlog recovery, with the prerequisite and the
before/after artwork-hash check), E10c (the live night: GL-7's three DoD items,
GL-52's measured create, and the first production exercise of GL-55/56/57/GL-65).
It is the sign-off artefact for E10a and E10b; **E10c needs its own explicit
"proceed" per CLAUDE.md §4 and is not delegated to it.** Four open decisions are
listed in its §5, the first of which is the grep.
