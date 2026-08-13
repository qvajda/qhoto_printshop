# GL-6-proper authoring brief — the real near-frontal scene library — 2026-07-23

Ready-to-paste prompt for a **Claude Code session** (needs the Replicate skills:
`find-models`, `compare-models`, `run-models`, `prompt-images`) started from the
`qhoto_printshop` repo root.

This is the **production scene library** the prototype (GL-6) and the compositor
(GL-5) were building toward. GL-2 already said **go, near-frontal**; GL-4
confirmed the compositor reads apertures from `meta.json` and kills seams with
over-fill **+ a frame edge baked into `overlay.png`**. **GL-19 (2026-07-24) then
proved the compositor code is correct but the 4 prototype bundles fail the
quality bar on two concrete authoring defects — so this session now owns BOTH
fixing those 4 existing bundles AND authoring the rest**, and it is the **sole
gate on merging PR #2** (the GL-5 compositor) as well as on **unblocking GL-13
Round 2** (whose secondary groups can't render until the 5x7/10x24 bundles
exist).

**Owner-in-the-loop, creative selection between phases** — this is not an
unattended batch. The *generation* runs through Replicate (FLUX.1 [schnell]);
the *choosing* is the owner's.

---

## PROMPT — paste from here down

You are authoring the **production near-frontal mockup scene library** for the
Etsy POD pipeline. The compositor already exists and is frozen — you are
producing **asset bundles it consumes**, not code. Optimize for scenes that
composite clean at the compositor's B+ bar, and for covering the aspect-ratio
groups Round 2 needs. Stop for owner selection between phases; do not run the
whole thing unattended.

### Read first, in this order
1. `CLAUDE.md` (root + repo) — hard constraints (v4.11). Especially: image-gen
   is **Replicate + FLUX.1 [schnell] only** (Apache-2.0; **never FLUX.1 [dev]**,
   non-commercial); generated scenes are **flat 2D empty-frame photographs**,
   and the *artwork* that goes into them stays flat full-bleed (no room/frame
   baked into the art — the frame belongs to the scene, not the print).
2. `docs/2026-07-24-gl19-m1-status-update.md` — **read this first of the
   findings docs.** It is the acceptance run that failed the 4 prototype bundles
   and localized exactly why. Your work is judged against re-running its harness
   (`scripts/gl19_m1_render.py`) on the same 4 scenes until they pass.
3. `docs/2026-07-22-compositor-approach-findings.md` — the acceptance facts you
   must author for: **(a)** the aperture is annotated by hand in `meta.json` (no
   runtime detection — a mis-annotated quad = a visible seam, so annotate
   carefully and verify with the quad overlaid); **(b)** framed scenes'
   `overlay.png` **MUST carry the opaque frame/mat inner edge as foreground**,
   or the compositor's ~1.5–2% over-fill spills visibly onto the mat.
   **GL-19 added two more, non-negotiable:** **(c)** aperture quads must be
   **perspective-accurate to the photographed paper edge** — the prototype's
   straight-line hand-traces sit *outside* the real tapered edge and produced
   the seam/dash lines; trace the actual edge and verify by overlaying the quad
   on the raw `background.png` at zoom before committing. **(d)** overlay
   foreground occluders (clips, book spines, frame/mat edges, any prop crossing
   the print) must be authored at **full alpha 255** where they occlude — the
   prototype overlays maxed at ~172–187, which is why clips/books rendered
   "see-through."
4. `docs/2026-07-22-gl5-compositor-implementation-plan.md` §3 (bundle format +
   the optional additive `overfill` field), §5 (`mockup_templates` config +
   ordering contract), §9 (the frame-edge + steep-angle watch-items).
5. `docs/SPEC_v4.10_addendum_custom_mockups.md` — the design of record (10
   scenes/set = 3 flat + 7 lifestyle; registry keyed by
   `(group_type, orientation)` matching `aspect_ratio_groups`).
6. `docs/mockup_generator_prototype_prompt.md` — the detailed creative reference
   (style-DNA extraction, scene prompting, ISO scale-reference). Reuse its craft;
   ignore its "throwaway" scoping.
7. Reference, do not re-derive: the **4 already-authored primary/portrait
   bundles** (`assets/mockups/primary/portrait/*`) + `assets/mockups/manifest.json`
   + the `mockup_templates` block in `config/static_config.json` (currently 4
   primary scenes, 5x7/10x24 empty). Preview with the **real** compositor,
   `pipeline/mockup_render.py` — not a throwaway spike.

### Base branch
Branch off **`feat/gl5-mockup-compositor`** (so you inherit `mockup_render.py`,
the 4 existing bundles, and the config accessor and can preview against the real
compositor): `feat/gl6-scene-library`. **PR #2 has NOT merged** and won't until
this session's re-authored bundles pass the GL-19 harness — so branch off
`feat/gl5-mockup-compositor`. GL-19 already ran and **failed all 4 existing
bundles**; fixing them (perspective apertures (c) + full-opacity occluders (d) +
frame-edge overlays (b)) is **the first block of work here**, not an optional
coordination.

### Hard rules (CLAUDE.md + reversibility)
- **Replicate + FLUX.1 [schnell] only.** State the interior/scene model + its
  licence before any batch; owner approves the batch before it fires. If you
  reach for any non-schnell model, stop and flag the licence.
- **No Etsy / Gelato / publish writes. Zero.** This is 100% offline authoring.
  The only external calls are owner-approved Replicate generations.
- **Original scenes only** — no imitation of a specific photographer or brand.
- **Near-frontal for v1.0.** Keep camera close to straight-on; a slight lean is
  fine, but heavily-angled lifestyle scenes are **deferred to v1.1** — if a
  strong scene idea is steep, author it but mark it `v1.1` and keep it **out** of
  the shipped `mockup_templates` list (it can't clear the bar reliably yet).
  Foreground objects may clip **<~15%** of the aperture (a corner/edge the
  overlay handles), never ~40% (the prototype's dropped monstera).
- **Bundle format unchanged** (plan §3): `background.png`, `overlay.png`,
  `meta.json` `{scene, group_type, orientation, aperture:[[TL],[TR],[BR],[BL]],
  size:[w,h], tag:"flat|lifestyle"}`, optional `overfill` (add per-scene only if
  a scene needs more than the ~1.8% default). Record `seed` + exact prompt for
  every kept scene (in the ledger, not necessarily in `meta.json`).

### Phases (stop for owner selection between each)

**Phase 0 — style DNA + the gap.** Confirm the approved test master with the
owner. **Use `db/base_artwork/39.png` (candidate 39 — approved + published, the
round-1 live-test candidate). Do NOT use `31.png`: GL-19 found candidate 31 is
stuck `pending_generation` and was never approved** — the old brief's default
was wrong. Establish/confirm the shop's scene style DNA from the 4 existing
primary bundles (lighting, palette, props, framing) so everything reads as one
coherent shop. State exactly what's missing per group: primary/portrait needs
**+6** (to reach 3 flat + 7 lifestyle; currently 2 flat + 2 lifestyle), 5x7 and
10x24 each need a full near-frontal set. Owner confirms target counts.

**Phase 1 — FIX the 4 existing primary/portrait bundles (the PR-#2 unblock, do
this BEFORE generating anything new).** GL-19 failed all four
(`flat_clips_windowlight`, `flat_leaning_bookstack`, `lifestyle_sage_terracotta`,
`lifestyle_bedroom_console`) on defects (c) + (d) — no new generation needed, the
scene photos are fine, the *bundle authoring* is not. For each:
- **Re-trace the aperture (c):** overlay the current `meta.json` quad on the raw
  `background.png` at zoom; where it's a straight line outside the real
  perspective-tapered paper edge, re-trace to the actual edge (all four corners,
  sub-pixel where you can). This is what removes the seam/dash lines.
- **Re-author the overlay (d):** set foreground occluders — clip bands, book
  spines, the frame/mat inner edge (b) — to **full alpha 255** where they cover
  the print (the current overlays max at ~172–187, so the art shows through).
  Keep the soft shadow/highlight layers as-is.
- **Re-verify with the harness:** run `scripts/gl19_m1_render.py` on the master
  and eyeball the 4 outputs in `outputs/gl19_m1/` at zoom — they must now clear
  the B+ bar (no seam, clips/books read opaque). **Stop and show the owner.**
Only when the existing 4 pass do you move on. This unblocks the PR-#2 merge on
its own, independent of the new scenes below.

**Phase 2 — complete the primary/portrait set (+6 near-frontal).** Generate
empty-frame scenes with `run-models`, staged at ISO **large/statement** apparent
scale, blank evenly-lit inserts (annotate the quad afterwards — don't prompt for
magenta). Present a labelled grid; owner picks the keepers. For each keeper,
apply **all four criteria (a–d) from the start** (don't repeat Phase 1's
mistakes): perspective-accurate aperture trace verified on the raw background
(c); `overlay.png` foreground — frame/mat inner edge + any occluder — at full
alpha 255 (b + d); baked shadow/highlight. Package the bundle and **preview it
through `mockup_render.render_scene` with the real master (`39.png`)** — confirm
no seam/staircase, opaque occluders, art bleeds under the frame edge. Show the
owner the composited preview, not just the empty scene.

**Phase 3 — 5x7 portrait set (unblocks Round 2).** Same loop, but the empty
frame must be **5x7-proportioned** (13×18 cm feel — a small tabletop/shelf
print, not a statement wall piece; `group_type:"5x7"`). Near-frontal set;
aim for the 3-flat + 7-lifestyle target but a smaller viable set is acceptable
if the owner signs off — the hard requirement is **at least enough that the 5x7
group renders instead of failing loud** in Round 2. Preview each through the
compositor.

**Phase 4 — 10x24 portrait set (unblocks Round 2).** Same, with a **tall
narrow/panoramic** frame (`group_type:"10x24"`). This is the group whose missing
crop caused the live-run white bars, so stage frames that read convincingly at
that ratio. Preview each through the compositor with the **10x24 cover-crop** of
the master (GL-14's crop), confirming the crop fills the frame.

**Phase 5 — wire + verify.** Update `config/static_config.json`
`mockup_templates` (3 flat IDs **before** the 7 lifestyle IDs per group — the
list order **is** the Etsy rank order) and `assets/mockups/manifest.json`.
Run the full suite (the placeholder fail-loud test should now pass with real
bundles where config lists them; any scene ID in config **must** have a bundle
on disk or it fails loud by design). Commit the bundles + config. Write
`docs/2026-07-24-gl6-proper-findings.md`: scenes kept per group (with seeds),
the model + licence used, composited previews, the Phase-1 before/after on the
existing 4, and an explicit note on whether each group's set is **Round-2-ready**
and whether **PR #2 is now mergeable** (the existing-4 harness pass is the
signal).

### Explicitly deferred — do NOT do here
- **Landscape** orientation scenes/wiring → **GL-18** (post-launch).
- **Heavily-angled v1.1 lifestyle scenes** — author-and-shelve at most; keep them
  out of the shipped `mockup_templates`.
- Any compositor code change (`mockup_render.py` is frozen), any Etsy/Gelato
  integration, the Gelato "mockups ready" poll (→ GL-20), and the live Round-2
  test itself (→ GL-13).

### Definition of done
- **The 4 existing primary bundles pass the `scripts/gl19_m1_render.py` harness
  at the B+ bar** (perspective apertures (c) + full-opacity occluders (d) +
  frame-edge overlays (b)) — this alone **unblocks the PR-#2 merge.**
- primary/portrait = full near-frontal set (target 3 flat + 7 lifestyle), every
  bundle previews clean through the **real compositor** with master `39.png`,
  all four criteria (a–d) met.
- 5x7 and 10x24 portrait sets exist and render (no fail-loud) — **Round 2's
  secondary-group slice is unblocked.**
- `mockup_templates` + manifest updated (correct flat-first ordering), suite
  green, findings doc written with per-group Round-2 readiness **and the PR-#2
  merge recommendation.** No live writes; FLUX.1 [schnell] only; seeds/prompts
  recorded.
