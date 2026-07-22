# Bug: group cover-crop never reaches Gelato (10x24 white bars reproduced) — 2026-07-22

Found live during v4.11 round-1 test (GL-9), S3 step 5 (group_mockup for
candidate 39's 5x7/10x24 groups). Deferred to a follow-up session per owner
decision; round 1 continued to S4 treating this as a known go-live blocker.

## What's wrong

`pipeline/group_product.py`, `create_or_reuse_group_product()`, the
`create_product_from_template` call (~line 262-270):

```python
response = gelato_client.create_product_from_template(
    template_id,
    [
        {"template_variant_id": t["template_variant_id"], "image_placeholder_name": t["image_placeholder_name"],
         "image_url": candidate["base_image_url"]}
        for t in templates
    ],
    title, store_id=store_id, api_key=api_key,
)
```

`candidate["base_image_url"]` is the **full, uncropped master** (whatever
aspect ratio FLUX/ESRGAN produced it at — ~0.684 for the current pipeline).
This is sent to Gelato for **every** group type (primary, 5x7, 10x24) with
no per-group cropping. Gelato's own template then fits/letterboxes the
source into the target aspect ratio — reproducing the **exact white-bars
defect** that the v4.10 Addendum / v4.11 group-flow rework was designed to
eliminate (CLAUDE.md: "their own cover-crop of the approved artwork (a real
crop that fills the frame, never a fit/letterbox — the live run's 10x24
white bars were a missing crop)").

`pipeline/image_crop.py`'s `cover_crop()` / `crop_for_group()` are correct
(verified: proper "cover" crop math, crops the long axis down to hit the
target ratio, no letterboxing) — but per their own docstring/comment
(image_crop.py:46-49), they're used **only** to build the local Telegram
digest preview thumbnail (`db/group_preview_images/{group_product_id}.jpg`),
never wired into what's actually submitted to Gelato for print.

## Live evidence (2026-07-22, candidate 39, group 39 / group_product 12)

Gelato's own hosted preview for the 10x24 product (fetched live via the
`product_images` row's S3 URL) shows the wildflower-meadow artwork centered
in a narrow vertical strip with large white margins top/bottom/left/right —
a letterboxed fit, not a fill. Saved locally at
`db/group_preview_images/12_10x24_check.jpg` for reference.

The 5x7 group (group_product 11) happened to look acceptable in its preview
(`db/group_preview_images/11.jpg`) only because that preview file *is* the
locally cover-cropped Telegram thumbnail, not what Gelato actually printed
from — it does not prove the 5x7 Gelato product is correctly cropped either.
**Both 5x7 and 10x24 groups need re-verification once this is fixed**, not
just 10x24.

## Fix shape (not yet implemented)

1. In `create_or_reuse_group_product`, for `5x7`/`10x24` group types, produce
   a cover-cropped, full-resolution (print-DPI, not the Telegram-preview's
   downsized `PREVIEW_MAX_EDGE` thumbnail) version of the master before
   calling `create_product_from_template`.
2. That cropped image needs to be hosted at a URL Gelato can fetch (the R2
   durable-URL infra already exists for base artwork — reuse it, e.g.
   `base/{candidate_id}_{group_type}_crop.png`).
3. Pass that URL as `image_url` instead of `candidate["base_image_url"]` for
   non-primary group types. Primary group (8x12/A3/A2/A1, same ISO A-series
   ratio family) can likely keep using the raw master per CLAUDE.md's
   framing ("same composition, just scaled... a small crop, not a
   re-composition") — confirm this doesn't also need a real crop before
   assuming it's fine as-is.
4. `image_crop.py`'s existing `cover_crop()`/`target_ratio_for_group_type()`
   are reusable as-is for the print-resolution crop; only the "downsize +
   save locally for Telegram" part of `crop_for_group()` needs to stay
   preview-only.
5. Re-verify live: re-run group_mockup for a fresh candidate's 5x7/10x24 (or
   re-create candidate 39's, since its current Gelato products are still
   live/uncropped) and visually confirm both crops fill frame with no white
   bars, at both the Gelato-preview level and (if feasible) by inspecting
   the actual submitted image dimensions/ratio.

## State left behind

- Candidate 39's group_products 11 (5x7, `gelato_product_id
  1bc0abf3-45f0-4989-838b-bad677b33576`) and 12 (10x24,
  `gelato_product_id 5c9be5ec-0414-4cfb-9e55-42b665f155f8`) are live on
  Gelato, status `created` (not yet critic-passed/approved/published) —
  affected by this bug, will need to be deleted and recreated once fixed.
- Primary group product (id 10, `49f115f2...`) is `published`, Etsy listing
  `4542159277` (draft) — NOT affected by this bug per the framing above, but
  worth double-checking once the fix lands.
