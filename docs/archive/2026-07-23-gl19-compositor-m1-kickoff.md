# GL-19 kickoff — compositor M1 acceptance + one guarded live upload

> **✅ EXECUTED 2026-07-24 — see `docs/2026-07-24-gl19-m1-status-update.md`.**
> Stopped at Phase 1: gate failed on authoring (not code); fix routed to
> GL-6-proper; re-run this run's harness after. **Correction:** the master named
> below (`db/base_artwork/31.png`) is **not approved** — use **`39.png`** (the
> approved/published candidate). This doc is kept as the run's reference.

Ready-to-paste prompt for a **fresh Claude Code session** started from the
`qhoto_printshop` repo root, **on branch `feat/gl5-mockup-compositor` (PR #2)**.
This is the **acceptance gate for PR #2** — not a build task. It proves the
GL-5 compositor produces a *good-looking* gallery (which the 504 unit tests
cannot judge) and lands exactly **one** guarded live Etsy upload, then hands
back to the owner for the merge decision.

Method = SDD-lite (this is a test/acceptance run, not a multi-stage build): a
short offline render harness, an owner eyeball STOP-gate, then a single
named-and-gated live call. Extends the Round-1 launch guide's per-call
STOP-gate discipline (`docs/2026-07-22-v411-live-test-launch-guide.md`).

---

## PROMPT — paste from here down

You are running the **GL-19 compositor M1 acceptance** on branch
`feat/gl5-mockup-compositor`. Your job is to render the real approved master
into the real scene bundles, produce sample images for my eyeball review, and —
only after I approve those samples — perform **one** guarded live Etsy image
upload. You are **not** changing the compositor's design or adding scenes; if
you find a real defect, report it and STOP rather than redesigning.

### Read first, in this order
1. `docs/2026-07-22-compositor-approach-findings.md` — the quality bar. Your
   samples must reach the spike's **"B+" bar**: no staircase aliasing on the
   aperture edge, no dark gap/seam line, art bleeds *under* the frame edge
   (over-fill), overlay shadows/highlights read as a real print. The two
   original prototype seams must be absent.
2. `docs/2026-07-22-gl5-compositor-implementation-plan.md` §1 (success
   criteria), §4 (`render_scene` / `render_scenes` signatures), §6 (how the
   stages consume it), §8 step 8 (this M1 step).
3. `docs/2026-07-22-v411-live-test-launch-guide.md` — reuse its **Ground rules**
   and **Failure protocol** verbatim for the live-upload phase.
4. `CLAUDE.md` (root + repo) — hard constraints. Note especially:
   image-gen is **never** re-run here (M1 reuses an already-approved master);
   `TELEGRAM_ADMIN_CHAT_ID` and all tokens come from `.env`, never hardcoded.
5. Reference only: `pipeline/mockup_render.py` (the compositor under test),
   `pipeline/group_product.py` + `pipeline/etsy_client.py` (the
   `uploadListingImage` path you will exercise once, live).

### Non-negotiable constraints (violating any is a bug)
- **No new generation.** M1 reuses an existing approved master
  (`db/base_artwork/31.png` unless I name another). Zero Replicate calls.
- **Offline-first.** Phases 0–1 make **no network calls at all**. Rendering is a
  pure function of `(artwork, bundle)` — keep it that way.
- **`ETSY_LIVE_MODE` / `GELATO_LIVE_MODE` stay `false`** until the single live
  call in Phase 2, which runs **only after I approve the Phase-1 samples** and
  **only after I give a per-call go-ahead** for that exact call. Name the call
  before it fires (Round-1 launch-guide discipline).
- **One upload, one target.** Phase 2 uploads to **one** existing Dev-Mode
  **draft** listing. Never activate a listing (`update_listing_state` is
  off-limits). Never touch Gelato in this run (no create, no delete — there is
  nothing to create; a live Gelato write is out of scope for GL-19).
- **Fail loud, don't paper over.** If a bundle is a placeholder or a render
  raises `MockupRenderError`, surface it and STOP — do not skip the scene or
  fall back to a Gelato image (that's the whole point of the fail-loud contract).
- **Read-only to master.** Do not merge PR #2, do not rebase, do not force-push.
  You may add the render harness + sample outputs as a commit **on the branch**
  if useful, but the compositor code and tests are frozen for this run.
- **Secrets from `.env` only.** Nothing hardcoded, nothing committed. Back up the
  DB before any live phase: `cp db/qhoto.sqlite3 db/qhoto.sqlite3.bak-2026-07-23-pre-gl19`.

### Phase 0 — pre-flight (read-only, LIVE_MODE off)
Hypothesis: the branch is in a clean, testable state before we render.
- Confirm current branch is `feat/gl5-mockup-compositor` and the **full suite is
  green** — report the N/N count (expect **504/504**). If it's not green, STOP.
- Confirm the four real bundles resolve and are complete (background+overlay+meta,
  aperture is 4×2): `assets/mockups/primary/portrait/{flat_clips_windowlight,
  flat_leaning_bookstack,lifestyle_bedroom_console,lifestyle_sage_terracotta}`.
- Confirm the chosen master exists and is the approved one
  (`db/base_artwork/31.png`); report its dimensions and that it's flat
  full-bleed art (no frame/room/mockup baked in — the spec's cardinal rule).
- **Pass:** branch clean, suite green, 4 bundles + master present. No network hit.

### Phase 1 — offline M1 render + eyeball STOP-gate (no network)
Hypothesis: the compositor produces production-clean composites at the B+ bar.
- Write a **throwaway** harness (`scripts/gl19_m1_render.py`, do not promote it
  into `pipeline/`) that calls `mockup_render.render_scenes(master, [the 4 bundle
  dirs])` and writes the ordered PNGs to `outputs/gl19_m1/` — flat scenes first,
  then lifestyle (the Etsy rank order).
- For each output assert: size == `meta.json` `size`; the render is deterministic
  (run twice, identical bytes — success criterion 1); no exception raised.
- Produce a small **contact sheet** (or the 4 PNGs plus a one-line note each)
  for my review, calling out the seam-prone spots: aperture edges on the
  near-frontal `flat_clips_windowlight` and the steep `lifestyle_sage_terracotta`
  (the scene that reproduced both original seams — this is the acceptance-critical
  one).
- **STOP and hand me the samples.** Do **not** proceed to Phase 2 until I reply
  with an explicit approval of the images. If any scene shows a seam / staircase
  / gap line or the over-fill spills onto the mat, flag it as an authoring gap
  (likely a missing frame-edge in `overlay.png` — GL-6-proper) or a compositor
  regression, and STOP. Note which it is; do not hack the overlay to hide it.

### Phase 2 — one guarded live Etsy upload (only on my go-ahead)
Hypothesis: the approved composites upload to a real Etsy draft in rank order,
tagged as the correct image type, without disturbing anything else.
- Pick **one** existing Dev-Mode **draft** listing as the target; confirm its
  `listing_id` with me before anything fires.
- **Named live call (single):** Etsy `uploadListingImage` for the approved
  Phase-1 PNGs, in rank order (flat first, then lifestyle), via the branch's
  `group_product`/`etsy_client` path with `ETSY_LIVE_MODE=true` **for this call
  only**. Confirm the PNG-vs-JPEG mime fix (one of the two bugs the PR review
  caught) actually sends `image/png`.
- **Pass:** the images appear on the draft in the intended order; the listing
  stays a **draft** (never activated); nothing else on the shop changed; the DB
  reflects the uploaded refs. Flip `ETSY_LIVE_MODE` back to `false` immediately
  after.
- If the upload errors, follow the launch guide's **Failure protocol** (incident
  note to `.remember/` first, then a resume note), and STOP.

### Definition of done
- Phase 0 clean; Phase 1 samples produced and **approved by me**; exactly **one**
  live Etsy upload performed, verified, listing left as a draft, `LIVE_MODE`
  back off, DB `.bak` retained.
- A short handoff at the end: the sample verdict (B+ met? per-scene notes), the
  live-upload result, **the explicit recommendation on whether PR #2 is now
  mergeable** (and if not, exactly what's blocking — e.g. a frame-edge overlay
  gap that GL-6-proper must close first).
- No generation ran; no Gelato write; no merge; no activation. All of that is
  stated explicitly in the handoff.

### Deferred (explicitly NOT in GL-19)
- Authoring the frame-edge into framed-scene overlays, and the 5x7/10x24 +
  landscape bundles → **GL-6-proper / GL-18**.
- The Round-2 mockup-dependent live slice (custom-gallery critic pass,
  `mockup_failed` retry path, secondary-group galleries) → **GL-13**.
- Any Gelato "mockups ready" poll change → **GL-20**.
