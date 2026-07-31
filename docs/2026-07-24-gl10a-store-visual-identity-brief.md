# GL-10a brief — Qhoto Art store icon + banner (Qrchard sibling brand) — 2026-07-24

The **visual-identity slice of GL-10** (storefront overhaul). Scope is narrowed
here to the two brand-defining assets: the Etsy **shop icon** and **shop
banner**. The rest of GL-10 (About/sections/policies/SEO copy) stays a separate
task.

**Not a redesign — a brand application.** The uploaded `brand_sheet.pdf` already
defines the system: **Qrchard** is the umbrella brand; **Qhoto** ("Qhoto Art")
is a subsidiary venture. The sheet's own rule — *"System — built for siblings:
same badge geometry, same type — each venture gets its own accent hue"* — is the
whole job. We're producing Qhoto's icon + banner **inside** that system, not
inventing a look.

**One-way-valve:** clear. This is your own Qrchard/Qhoto venture; the output
travels to your Etsy shop, built from your own brand sheet + public Etsy specs.
Safe.

---

## 1. Problem / success criteria

Replace the current Qhoto Art store icon + banner with on-system assets that (a)
read unmistakably as a sibling of Qrchard, (b) carry Qhoto's own accent hue, and
(c) meet Etsy's current upload specs so they render crisp and uncropped.

Success:
1. **Icon** — the Qhoto badge (same magnifying-glass/handle geometry as
   Qrchard's Q-mark) in Qhoto's accent hue, centered with circle-safe margins,
   legible at avatar size.
2. **Banner** — dark-ground lockup echoing the sheet's Qrchard Etsy-banner
   application (wordmark centered + a small caps tagline strip), in the Qhoto
   accent, key content inside the central safe zone.
3. **Fidelity** — exact palette hexes, Fraunces + Inter type, badge geometry
   matched to the sheet (not re-approximated by eye).
4. **Spec-clean** — correct pixel dimensions, ≤1 MB each, no important content in
   the crop/circle-loss zones.

## 2. Brand system (from `brand_sheet.pdf` — the source of truth)

- **Palette:** Ink `#15120D` · Charcoal `#211C16` · Oxblood `#5C1A24`
  (Qrchard's accent) · Bone `#E7E0D1` · Stone `#8F8676`.
- **Type:** **Fraunces** (serif display — 400 / 500 italic / 600) for the
  wordmark; **Inter** (sans — 400 / 500 / 600) for taglines / caps strips.
- **Badge geometry:** the "Q" as a ring with a small angled handle/mallet + dot
  — used three ways (horizontal wordmark, stacked, icon-only). **Qhoto reuses
  this exact geometry**, swapping only the accent hue.
- **Voice / tagline vocabulary:** "Grown after dark." · "ART ·
  PRINTED TO ORDER." Ground = Ink/Charcoal (dark); text = Bone.
- **Product-line coherence:** the shop sells the FLUX poster line — the icon/
  banner should feel like the same hand that made the mockup scene DNA (calm,
  dark, gallery-ish), not a louder or lighter register. The shop also sells fine art print of user's photography.

## 3. Etsy specs (verified 2026-07 — see Sources)

- **Shop icon:** upload **500 × 500 px**. Displays as a **circle** — keep the
  badge centered with clear margin; nothing critical in the corners.
- **Big banner:** recommended **1600 × 400 px** (minimum 1200 × 300). Keep the
  wordmark + tagline in the **central horizontal band** (Etsy crops/overlays the
  edges across breakpoints).
- **Mini banner** (if you use the mini layout instead): **1600 × 213 px**.
- **File:** ≤ **1 MB** each; JPEG preferred, PNG fine if under 1 MB. Produce the
  big banner by default; add the mini only if you want that layout.

## 4. Open decisions — resolve before execution (don't self-approve)

- **D1 — Qhoto's exact accent hex.** The sheet shows Qhoto's badge in a green but
  gives **no hex** (only Qrchard's Oxblood `#5C1A24`). This must be locked so the
  green is reproducible and can be added to the brand sheet as Qhoto's official
  accent. To sit beside Oxblood as a true sibling (same depth/desaturation on the
  dark ground), a **deep pine/forest green** is the right family — proposed
  starting point **`#1E3B2F` (Pine)**, with **`#2E5D45` (Fern)** as a slightly
  brighter alternative. **Pick one (or give your own).**
- **D2 — exact shop wordmark.** Badge reads "Qhoto"; you call it "Qhoto Art."
  Confirm the banner wordmark: **"Qhoto"** alone (mirrors "Qrchard" as a single
  word) vs. **"Qhoto Art"**. Recommendation: **"Qhoto"** as the wordmark, with
  "Art" living in the tagline strip if wanted — keeps the sibling symmetry.
- **D3 — badge source.** Recommend **extracting the vector badge from
  `brand_sheet.pdf`** (it's vector inside the PDF) and recoloring it to the D1
  hue, rather than redrawing — guarantees geometry match. Fallback: redraw as SVG
  if extraction is messy.

## 5. Tool recommendation (you asked me to pick)

**Primary: the `canvas-design` skill (code/SVG-driven), executed in this Cowork
session.** Rationale:
- The deliverables are two exact-spec static images with **exact hexes, exact
  type, and a specific vector badge** to match — code/SVG nails all three
  deterministically and writes straight to the folder.
- It can **reuse the real badge geometry extracted from the PDF** (D3) instead of
  eyeballing it.
- **No dependency on the Canva connector, which has been flapping this session**
  (several of its tools disconnected mid-run).

**Alternative: Canva (brand kit + templates)** — worth it *only if* you want an
ongoing, hand-editable Qhoto Brand Kit + reusable templates for future assets
(social, listing inserts). Then: register a Qhoto Brand Kit (palette + Fraunces/
Inter + badge), build icon/banner as templates. Trade-off: rebuilding the badge
as a Canva element, plus the current connection instability. Reach for it later
if the asset set grows beyond icon + banner.

Either way this stays **in Cowork** — it's a creative/file-output task, a good
fit; no hand-off to Claude Code needed.

## 6. Plan / phases (canvas-design path)

1. **Inputs** — you upload the **current icon + banner** (the "before", for
   reference / any keepers); I extract the badge vector + confirmed palette from
   `brand_sheet.pdf`. Lock **D1/D2/D3**.
2. **Icon** — Qhoto badge in the D1 hue on Ink/Charcoal ground, 500×500,
   circle-safe. Render 2–3 variants (icon-only vs. tighter crop; ground shade).
3. **Banner** — 1600×400 dark lockup: centered Qhoto wordmark (Fraunces) + a
   Bone caps tagline strip (Inter — e.g. "AI-GENERATED ART · PRINTED TO ORDER"),
   Qhoto-green accent detail, content inside the central safe zone. Mini 1600×213
   only if you want it.
4. **Review** — you eyeball against the sheet's Qrchard application (does it read
   as a sibling? is the green right beside the oxblood?). Iterate.
5. **Package** — final PNG/JPEG at spec, ≤1 MB, plus the recolored badge SVG for
   reuse. **You upload them** in Shop Manager (icon/banner are manual, not API —
   no live-write risk; still your call to publish).

## 7. Definition of done

Icon + banner at Etsy spec, on-system (sibling badge, correct palette/type,
locked Qhoto green), reviewed by you against the Qrchard application, and handed
over as folder files ready to upload — plus a reusable recolored Qhoto badge
SVG. D1's chosen green noted so it can be added to the brand sheet as Qhoto's
official accent.

## 8. Deferred (not in GL-10a)
- The rest of GL-10: About text, shop sections, policies, SEO/listing copy
  (Fable-assisted, separate pass).
- A full Qhoto brand-sheet page / Canva Brand Kit (only if you go the Canva
  route or want the system documented for future siblings).
- Any listing-image / social templates.

## Sources
- [Etsy image sizes 2026 — imresizer](https://imresizer.com/blog/etsy-image-sizes-2026-complete-guide)
- [Etsy size guide — Linearity](https://www.linearity.io/blog/etsy-size-guide/)
- [Etsy shop banner & profile image optimization 2026 — imgseo](https://imgseo.io/blog/etsy-shop-banner-profile-image-optimization-2026)
- Local: `brand_sheet.pdf` (uploaded — Qrchard/Qhoto system of record)
