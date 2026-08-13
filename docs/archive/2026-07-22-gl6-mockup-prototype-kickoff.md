# GL-6 kickoff — mockup-creation prototype (GL-2 decision gate) — 2026-07-22

Ready-to-paste prompt for a **Claude Code session** (has the Replicate skills:
`find-models`, `compare-models`, `run-models`, `prompt-images`).

**Supersedes `docs/mockup_generator_prototype_prompt.md` for the GL-6 purpose.**
That prior 3-phase prompt is the detailed creative reference for scene
authoring; this one re-scopes it to a **fast, throwaway prototype whose only
job is to let the owner make the GL-2 go/no-go** — *do custom lifestyle mockups
overhaul product quality enough to ship before launch, or fast-follow as v1.1?*
(see `docs/2026-07-22-go-live-plan-of-attack.md` GL-2). It is **not** the full
library build and **not** the production compositor (those are GL-4/GL-5, and
only if GL-2 says go).

The finalized design this must stay compatible with: **SPEC v4.10 Addendum A**
(self-hosted Pillow+homography compositor; asset bundles = background + overlay
+ aperture, not PSD; registry keyed by `(group_type, orientation)` matching
`aspect_ratio_groups`; 10 scenes/set = 3 flat + 7 lifestyle; Gelato gallery
dropped with no fallback; scene-ID placeholder must fail loud).

---

## PROMPT — paste from here down

You are building a **fast prototype** to answer one question for the owner:
*are custom lifestyle mockups clearly better than Gelato's default gallery —
enough to ship before launch?* Optimize for a **quick, eyeball-able answer**,
not completeness. Read first, in order: `CLAUDE.md` (hard constraints — v4.11),
`docs/SPEC_v4.10_addendum_custom_mockups.md` (the design you must stay
compatible with), and `docs/mockup_generator_prototype_prompt.md` (the creative
detail for scene authoring). Don't guess at behavior that's already specified.

### Method — lightweight exploratory prototype (not full SDD)

This is a spike, so it's lighter than the base-artwork/live-readiness branches,
but keep the project's spine:

- Work on a throwaway branch off master: `proto/mockup-scene-prototype`.
- **Stop for owner input between phases** (creative-selection convention from
  the prior prompt) — don't run the whole thing unattended.
- Any code you intend to *keep* (the asset bundles, the bundle-packaging
  script) gets committed; the minimal compositor in Phase 3 is explicitly a
  **throwaway spike** — mark it as such, don't invest in it, the real one is
  GL-5. If you write a reusable helper, give it a test; don't hold the spike to
  full-suite green.
- End with a findings doc + an explicit GL-2 recommendation (below).

### Hard rules (CLAUDE.md + reversibility)

- **Image generation runs through Replicate only**, via the installed skills.
  **License guardrail (hard):** these become commercial Etsy assets — FLUX.1
  [schnell] (Apache-2.0) only; **never FLUX.1 [dev]** (non-commercial). If you
  propose any non-schnell model, state its licence and stop for the owner.
- **No Etsy/Gelato writes.** This is 100% offline authoring — you never publish,
  never create a listing, never touch a Gelato product. The only external calls
  are Replicate generations (owner-approved before the batch fires) and one
  read to pull an existing Gelato mockup for comparison.
- **Original scenes only** — do not imitate a specific photographer or brand.
- Stay compatible with the Addendum asset-bundle format so kept output is
  reusable if GL-2 = go; don't invent a divergent format.

### Scope — phases (stop between each)

**Phase 0 — setup & the baseline to beat.**
- Pick **one real approved master** as the test artwork — a round-3 **Good**
  design from `db/base_artwork/` (e.g. one of candidates 25/26/30/31 per
  `docs/2026-07-21-generation-quality-round3-validation-results.md`). Confirm
  the choice with the owner.
- Pull the **current Gelato default gallery** for a comparable design (one read
  call, or reuse an image already on disk / a prior test listing) — this is the
  baseline the custom mockups must visibly beat. Show it to the owner.

**Phase 1 — style DNA.** If the owner provides example lifestyle images, extract
a compact "style DNA" from them (scene type, wall/surface, lighting direction +
warmth, palette, props, camera angle/distance, framing, mood) per the prior
prompt's Phase 1. If none are provided, propose 1–2 candidate directions and let
the owner pick. Stop for confirmation before generating anything.

**Phase 2 — one set, a few scenes (via Replicate).** Prove the concept on the
**ISO / `primary` set, `portrait` only** (highest-volume group — 8x12→A1). Pick
the interior/scene model with `find-models`/`compare-models` (state the choice +
licence), build prompts with `prompt-images`, batch-generate **4–6 empty-frame
scenes** (mix ~2 flat / straight-on + ~3 lifestyle / angled) with `run-models`.
Each scene: empty framed picture with a plain evenly-lit blank insert (detect
the quad afterwards — don't prompt for magenta); staged at ISO **large /
statement** apparent scale; record `seed` + exact prompt per kept scene. Present
a labelled grid; owner picks which to carry to Phase 3. **Do not** fan out to
5x7/panoramic or landscape yet — that's the full library (GL-6 proper), gated on
GL-2.

**Phase 3 — throwaway compositor spike + real composites.** Write a **minimal,
disposable** Pillow + homography warp (mark it throwaway — the production one is
GL-5): for each selected scene, detect the aperture quad, warp the **real
approved master** (not a placeholder) into it, paste over the background, and
composite a baked shadow/highlight overlay so it reads as a real print on the
wall. Package each kept scene as an Addendum-compatible bundle under
`assets/mockups/primary/portrait/<scene>/` — `background.png`, `overlay.png`,
`meta.json` (`{scene, group_type:"primary", orientation:"portrait", aperture:
[[TL],[TR],[BR],[BL]] px, size:[w,h], tag:"flat|lifestyle"}`), plus a
`preview.png` = the flattened composite with the **real master** in place. Show
the detected quad over each scene so the owner can correct it before you commit.

**Phase 4 — the comparison & the GL-2 call.** Assemble a **side-by-side**: the
custom composited previews vs. the Gelato default gallery for the same artwork.
Write `docs/2026-07-22-mockup-prototype-findings.md`: the style DNA, the model +
licence used, the scenes kept, the composited comparison, an honest read on
realism/effort (esp. how convincing the *angled* lifestyle composites are — the
Addendum's own escape-hatch risk, §6), and an **explicit GL-2 recommendation**:
*mockups pre-launch* or *fast-follow v1.1*, with the reasoning. If the angled
composites are a time-sink, say so and note the Dynamic Mockups escape hatch
(Addendum §7) as the fallback rather than forcing the self-host.

### Explicitly deferred — do NOT build here

- The **full scene library** (all 3 sets — primary/5x7/10x24 — × 2 orientations
  × 10 scenes = 3 flat + 7 lifestyle, + the ISO scale-reference image). That's
  GL-6-proper, only after GL-2 = go.
- The **production compositor** `pipeline/mockup_render.py` (GL-5), the
  `mockup_templates` static-config block + `get_mockup_templates()`, and the
  `primary_mockup`/`group_mockup` rewiring + Etsy `uploadListingImage` ordering.
  The Phase-3 spike is throwaway; do not promote it.
- Any pipeline/publish integration or the `mockup_failed` retry path.

### Definition of done

The owner can look at **real composited ISO-portrait previews of an approved
master, side by side with Gelato's default gallery**, plus a written
recommendation, and make the GL-2 go/no-go — having spent one small Replicate
batch and a throwaway warp, not a full library or the production compositor.
Kept asset bundles are in the Addendum-compatible format so nothing is wasted if
the call is go.
