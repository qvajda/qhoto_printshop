# Etsy AI POD pipeline

One shop selling AI-generated wall art as print-on-demand posters. A scheduled
pipeline researches a niche, generates one artwork, photographs it into mockups,
drafts the listing copy, asks the owner to approve it on Telegram, and publishes
it as a single Etsy listing whose sizes are variants.

Read on demand, not injected. `CLAUDE.md` holds the hard constraints; this file
holds the vocabulary. Where a word here disagrees with a name in the code, the
word here is the one to use in issues, commits and prose.

## The work item

**Candidate**:
One artwork idea, from research through to a published listing. The unit that
owns a base image, a Gelato product and an Etsy listing.
_Avoid_: design (ambiguous — see below), item, product

**Design**:
The visual result a buyer sees. Informal; use **candidate** for the tracked
object and **artwork** for the file.
_Avoid_: using it as a synonym for candidate in code or issue titles

**Artwork**:
The flat, full-bleed 2D image that gets printed. Never a poster-in-a-room render.
_Avoid_: image, picture, render

**Master**:
The single generated artwork file a candidate is built from, at full resolution.
A candidate is image-generated **once**; every size and crop derives from its
master.
_Avoid_: original, source image

**Niche**:
The subject-and-style brief injected into the generation prompt. Subject and
style only — never scene words like "wall poster", and never a dated event.
_Avoid_: theme, topic, trend

## Sizes and grouping

**Aspect-ratio group**:
A set of print sizes that share a proportion closely enough to share one
composition. There are exactly three: **primary** (8x12 + A3 + A2 + A1), **5x7**,
and **10x24**. Each carries its own decision and its own critic-pass history.
_Avoid_: size group, ratio bucket

**Primary size**:
21x29.7cm / 8x12″. The only size that is generated and reviewed first; the rest
of the primary group publishes with it, unreviewed, because the difference is a
small crop rather than a re-composition.
_Avoid_: default size, main size

**Variant**:
One size of one Etsy listing, at its own price. All validated sizes are variants
of **one** listing per candidate (v4.12).
_Avoid_: option, SKU

**Cover-crop**:
Filling a target rectangle by cropping the master, never by letterboxing. Budget:
**2%**, measured against the ratios the group actually *prints*, not against the
master.
_Avoid_: fit, resize, letterbox

## Mockups

**Scene**:
A photograph of a room with a blank print in it, authored offline. Listing
photography, never a printed product — which is why it is not bound to the
generator licence the artwork is.
_Avoid_: background, template, room shot

**Bundle**:
A scene on disk: `background.png`, `meta.json`, optional `overlay.png` and
`matte.png`. What `load_bundle` reads and `render_scene` composites.
_Avoid_: mockup folder, asset pack

**Quad**:
The four corners in a scene that the artwork is projected onto. Decides *where*
the art goes.
_Avoid_: frame, placement box

**Matte**:
A per-pixel mask deciding what of the projected artwork is *visible*. Absent means
pre-GL-21 behaviour. The quad places, the matte reveals — they are not the same
control.
_Avoid_: mask, alpha

**Geometry card**:
A reference image at a group's midpoint print ratio, passed to the scene
generator because no image model converts "A1" or "2:3" into a rendered rectangle
reliably.
_Avoid_: aspect hint, ratio guide

**In-flow**:
`assets/mockups/inflow/` — hand-run scene generations awaiting a screen. Owner
territory; there is no batch harness and it does not need one.
_Avoid_: inbox, staging

## The review loop

**Critic pass**:
The automated check of a group's rendered mockups before the owner sees them.
Capped at **3 attempts per group**, then that group alone is abandoned.
_Avoid_: QA, validation

**Digest**:
One Telegram gallery plus one separate message with buttons, per entry. Up to
three entries per candidate — one per aspect-ratio group.
_Avoid_: notification, alert, message

**Gate**:
The thing that decides whether work is done. Exactly two classes: **machine** (a
script says so) and **taste** (an owner's eye says so). A gate of neither class is
not a gate.
_Avoid_: check, approval, sign-off

## Ways of working

**qops**:
The per-project ways-of-working layer — hooks, a CLI, an issue-backed state
model. Named by the project convention: replace the leading letter with `q`.

**Sortie**:
One issue, sized to fit inside a single session, with acceptance criteria and a
named gate.
_Avoid_: task, ticket, story

**Mission**:
Work larger than one session, held as a milestone plus a `mission:` label rather
than as a document.
_Avoid_: epic (reserved for `type:epic`), project, initiative

**Brief**:
What a session is given at `SessionStart` instead of reading its way in. Replaces
the hand-written kickoff document.
_Avoid_: kickoff, prompt, handoff (banned — it names four different things)
