# GL-6 attempt-2 solution plan — stop chasing photographed edges (2026-07-24)

Planning artifact (Cowork session). No code written, no assets touched.
Input: GL-19 status update, attempt-1 failure memory
(`project_gl6_scene_library_attempt1_failed.md`,
`feedback_verify_full_frame_not_just_crops.md`), full-frame review of the 4
draft composites in `outputs/gl19_m1/`, raw bundle assets, and
`pipeline/mockup_render.py` (frozen). Supersedes nothing — it feeds the next
**Claude Code** session that re-attempts GL-6-proper.

---

## 1. Root-cause reframe: attempt 1 failed structurally, not on execution

Every defect class from both failed passes is one problem wearing different
hats: **the warped art must exactly meet a soft, photographed boundary, and
that boundary is not a quad.**

Evidence (verified this session against the raw assets):

- FLUX paper edges are soft, tapered, and sometimes **curved** (attempt-1's
  "curved-paper-edge limitation"). A homography maps rectangle → quad; no
  amount of sub-pixel tracing makes a quad fit a curve.
- `lifestyle_sage_terracotta`'s raw background has a **nested boundary** (mat
  opening + a faint inner panel line) *and* a baked diagonal window-shadow
  crossing the blank insert. The "dash line that survived every fix" is that
  **photographed shadow showing on leftover white paper** wherever the art
  quad under-covers — it is in the background photo, not in the composite
  math. Tracing better can never remove it; only *covering all of the white
  paper exactly* can, which the soft/curved edge makes unwinnable.
- Occluders (clips, book spines) are photographed *overlapping* the paper, so
  edge-accurate art placement forces overlay re-painting of those pixels —
  the second fragile hand-authoring task (the α-172/187 defect, the
  black-blob regression when hardening tints).
- GL-19 confirmed `mockup_render.py` is correct: mid-artwork regions render
  clean in all scenes. Every needed lever is **bundle-side**: the quad,
  `overfill` (accepts `0.0` or negative → inward inset, no code change),
  `background.png`, `overlay.png` (straight alpha-over can encode any
  per-pixel darken/lighten relight: α = 1−gain, colour = offset/α).

Conclusion: attempt 2 must **change the authoring doctrine**, not sharpen the
tracing tools. Two prior sessions already proved edge-matching fails.

## 2. The doctrine that makes composites certain

> **The warped art must never touch a photographed edge.** Every visible
> art boundary is either (a) strictly interior to the photographed paper, or
> (b) fully synthetic. There is then no edge to mis-trace, no seam to leak,
> no occluder to repaint.

Two authoring modes, chosen per scene:

**Mode I — INSET.** Author the quad strictly *inside* the photographed
paper (2–6% margin; `overfill: 0.0`). The leftover blank paper reads as a
white margin / mat reveal — a standard poster-mockup look. The photographed
edge, curl, clips, books, frame, and baked shadows all stay 100% authentic
because they are untouched. Relight the art with a **gain-map derived from
the blank insert itself** (ratio of insert pixels to its estimated white →
overlay alpha; the prototype already proved this auto-derivation looks
right), so the scene's real window-shadows fall across the art. Defects
(b)(c)(d) vanish *by construction*: annotation tolerance goes from ±0.5px to
±5px, occluder opacity becomes irrelevant (art never passes under a clip),
frame-edge overlays become unnecessary.

**Mode O — OWN THE PAPER.** Cover the photographed paper *entirely*
(expand the quad 2–4% outward past the traced edge), then draw a **synthetic**
sharp paper edge + soft drop shadow in the overlay. Everything visible at the
boundary is generated, so it is exact by construction. Best on unframed flat
scenes with smooth wall behind; going forward, generate new flat scenes as
**empty walls/surfaces (no paper at all)** and place a fully synthetic print
— the "blank low-contrast insert" problem disappears from generation too.
(Attempt-1's frame-band backfire was a *partial* band on a photographed
paper; full synthetic ownership of the paper is the reliable version.)

**Honesty constraint (owner decision #1).** The product is full-bleed. The 3
*flat* gallery slots are the truthful product representation → at least the
flats should show true full-bleed (Mode O or synthetic-paper scenes).
Lifestyle scenes are styling context (frame/mat already a fiction, "frame not
included") → Mode I margins there are cosmetic, not misrepresentation.
Recommended split: **flats = Mode O / synthetic; lifestyle = Mode I.**

Per-scene calls for the existing 4:

| Scene | Mode | Notes |
|---|---|---|
| flat_clips_windowlight | O (per decision #1: flats full-bleed-true) | own the paper synthetically; redraw clips at α255 over the margin-free print, or regenerate as empty-wall + synthetic clips |
| flat_leaning_bookstack | O preferred (flat slot) / I fallback | full synthetic paper ending above the book line, or regenerate empty-wall; I acceptable only if this scene ships as lifestyle-ranked |
| lifestyle_sage_terracotta | I | inset inside the *inner* panel; baked shadow becomes a feature via gain-map; kills the unresolvable dash |
| lifestyle_bedroom_console | I | frame glow/corner blobs sit outside an inset quad |

## 3. Vetted proposals

### P1 — Refine current Pillow/OpenCV authoring with the doctrine above
**Verdict: CERTAIN. €0. Recommended — this is what unblocks PR #2.**
No new deps, no code change, keeps all 4 scene photos the owner liked.
Certainty argument: Mode I removes the entire failure surface (nothing to
match); Mode O's boundary is generated, not matched. The only remaining
quality variable is aesthetic (margin width, shadow softness) — an
owner-taste iteration, not a defect class. Tooling for the session: a tiny
annotate-at-zoom + full-frame-preview loop, a gain-map extractor
(~30 lines numpy), re-run `scripts/gl19_m1_render.py` after every change.

### P2 — PSD-based scene design (licensed mockup PSDs → offline bundle conversion)
**Verdict: WORKS, medium effort. Quality ceiling above P1. €0/publish, no
vendor in cron.** Buy poster-mockup PSDs (Envato Elements ≈ €16.50 for one
month, unlimited downloads; commercial use of listing images for your own
product is permitted — the POD restriction targets customizable end-products,
not marketing renders; register each use, keep the certificate). Convert
offline, once per scene: `psd-tools` exposes the smart object's
`transform_box` = the exact TL/TR/BR/BL quad (sub-pixel, by construction — no
tracing, ever); background = composite with the art layer hidden; overlay =
shadow/foreground layers, or exactly derived by rendering the PSD twice with
white/black marker art and per-pixel unmixing (gain/offset → α/colour).
Risks: psd-tools blend-mode fidelity varies per file (prefer simple
smart-object + multiply-shadow PSDs — most poster mockups); 10x24 panoramic
templates are scarce (keep P1 for that group); style cohesion limited to
what's purchasable (mitigate: one creator's series). Position: **v1.1 quality
upgrade or hero-lifestyle pilot — not the PR-#2 unblock.**

### P3 — Hosted render API per publish
**Verdict: WORKS, cheap in euros, structurally still wrong for the cron.**
Current floor is far below the €1.5 estimate: SudoMock Starter $25/mo = 5K
renders (~$0.005/render → **~$0.15 per publish** at 30 renders; supports
custom PSDs; 500 free one-time credits; renders retained 7 days — pipeline
already downloads immediately). Dynamic Mockups ≈ $1.53/publish (GL-4
numbers stand). But GL-4's structural objection is unchanged and decisive: a
vendor inside a twice-daily autonomous cron (downtime, limits, watermark/tier
gotchas, young-vendor risk), a $25/mo floor regardless of volume, and PSD
authoring required anyway. **Keep as documented escape hatch only.** One
legitimate niche use: the **two-marker-render trick via their API at
authoring time** (≈60 renders for a whole library, free tier / one paid
month) as the high-fidelity renderer for P2's conversion if psd-tools falls
short — vendor used once, offline, never in the cron.

### P4 — AI image-edit models compositing the mockup directly
**Verdict: REJECTED.** (a) Artwork fidelity is not guaranteeable — buyers
must see the exact print, and edit models subtly redraw fine botanical
detail; a critic-pass can reject but can't fix, burning attempts. (b)
License traps: FLUX Kontext [dev] is non-commercial (same trap as FLUX.1
[dev], explicitly flagged in CLAUDE.md); commercially-safe editors exist
(Apache-2.0 Qwen-Image-Edit) but don't fix (a). (c) ~$0.01–0.04/image × 30 ×
retries is not "≪ €1.5" with margin. (d) Non-deterministic renders inside an
unattended cron. Do not revisit.

### Comparison

| | Certainty | Cost | Per-publish | Vendor in cron | Unblocks PR #2 when |
|---|---|---|---|---|---|
| P1 doctrine (recommended) | High — removes the failure surface | €0 | €0 | No | Days (one session) |
| P2 PSD conversion | Medium-high (per-PSD variance) | ~€17 one-time | €0 | No | Weeks — don't gate on it |
| P3 hosted API | High (works today) | $25/mo floor | ~€0.14–1.53 | **Yes** | Days, at structural cost |
| P4 AI edit | Low | — | ~€0.3–1.2+ | Yes | Never reliably |

## 4. Recommended plan for the next coding session

**Base state:** branch `feat/gl6-scene-library` draft changes are flagged
untrustworthy — **discard them** (`git restore` / re-branch from
`feat/gl5-mockup-compositor`). Keep `outputs/gl6_debug/` learnings only as
reference. `scripts/gl6_trace_aperture.py` / `gl6_fix_overlay.py` are
attempt-1 tooling built for the edge-matching doctrine — treat as scrap.

**Phase A — rescue the 4 bundles with P1 (gates PR #2).** Per-scene modes
from §2 table. For each: author inset quad (or synthetic paper), derive
gain-map overlay, `overfill: 0.0` in meta, run `scripts/gl19_m1_render.py`
with master `39.png` (**never `31.png`**), review **full-frame first, then
corners** (the attempt-1 process lesson — zoomed crops alone signed off on
broken images). Stop for owner review with full-frame composites. DoD: 4/4
pass the B+ bar → PR #2 mergeable.

**Phase B — author the rest of the library** (primary +6, 5x7 set, 10x24
set) per the existing GL-6-proper brief phases, with two amendments:
1. **Scene-generation acceptance criteria** (new): a candidate scene photo is
   only accepted if the paper is planar and flat (no curl), *or* the scene is
   generated with an **empty wall/surface** for fully synthetic placement
   (preferred for flats). No nested mats unless the inner opening is the
   intended boundary. Occluders may only ever overlap the *margin*, never the
   art region.
2. **All bundles authored under the §2 doctrine** — criteria (b)(c)(d) become
   trivially satisfied instead of hand-fought.

**Phase C — P2 pilot: DEFERRED to v1.1 (owner decision #3).** When revisited:
one Envato month, 2–3 hero lifestyle PSDs → conversion script (`psd-tools`
`transform_box` + two-marker unmix) → compare against P1 scenes.

**Process safeguards (from attempt-1 memory, non-negotiable):** full-frame
gestalt check before any zoom verification; harness re-run after every bundle
edit; no sign-off from crops alone; commit per scene only after its
full-frame pass.

## 5. Decision points — RESOLVED by owner (2026-07-24, Cowork session)

1. **Margin honesty split: APPROVED as recommended.** Mode I margins in
   lifestyle scenes; flats stay full-bleed-true (Mode O / synthetic paper).
2. **Regeneration: APPROVED — regenerate freely.** The session may replace
   any of the 4 scenes with an empty-wall/empty-surface variant if it
   resists (FLUX schnell, near-zero cost). Prefer keeping a scene when Mode I
   lands cleanly, but don't fight one.
3. **P2 PSD pilot: DEFERRED to v1.1.** Phase C is out of the next session's
   scope; P1 is the whole session.

## Sources (external facts vetted 2026-07-24)

- SudoMock pricing/custom-PSD/free-credit terms: https://sudomock.com/pricing
- Envato Elements license & POD restriction scope:
  https://help.elements.envato.com/hc/en-us/articles/360000629346 ·
  https://help.elements.envato.com/hc/en-us/articles/360000621803 ·
  https://forums.envato.com/t/question-about-envato-elements-license-and-print-on-demand-products/367590
- psd-tools SmartObjectLayer `transform_box` (4-corner placed-layer quad):
  https://psd-tools.readthedocs.io/en/latest/reference/psd_tools.api.smart_object.html
- Photopea headless smart-object replacement: unreliable (open issues #1324,
  #5921) — excluded from P2 tooling.
- Dynamic Mockups figures: unchanged from GL-4
  (`docs/2026-07-22-compositor-approach-findings.md`).
