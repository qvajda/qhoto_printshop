# GL-48 — finish the Gelato template fix: brief

**Filed:** 2026-08-09 · **Type:** M+C · **Blocker, now first in the queue
(Track E, E1)** · **Prerequisite:** GL-38 ✅ done (`master` = `80ce9fd`)

---

## 1. Where this stands

The owner's manual check found the root cause the API investigation had only
hypothesised: **the Gelato portrait template carried one image placeholder
shared by all six size variants.** It now carries **three** — separate images
for the primary, 5x7 and 10x24 variants.

That explains the defect completely. A single placeholder does not merely
share a *name*; it shares a **fit** — a saved scale and position authored
against `003_flower_in_stream_madeira_color.JPG`, an ordinary portrait
photograph. Submitting a correctly cover-cropped 10x24 file (0.4167) into a
transform built for 0.684 produces exactly the white bars in the dashboard
screenshot.

**GL-22a Q1 missed this, and the reason is worth carrying rather than
forgetting.** Q1 asked whether a shared placeholder name forces a shared
image, tested 8x12 (0.667) against 5x7 (0.714), and correctly answered "no".
At ratios within ~4 % of each other, fit and fill are visually identical — so
the experiment **could not have failed in the interesting direction.** It
closed a plan item (GL-22d) for eight days on evidence that never bore on the
question. When a probe's negative result is guaranteed by its design, it is
not evidence.

## 2. The problem this brief exists to solve

**The fix is half-applied, and that is a worse state than the defect.**

`config/static_config.json` still describes the *old* template. All twelve
entries carry the two original placeholder names:

```
5x7_portrait, 8x12_portrait, A3_portrait, A2_portrait,
10x24_portrait, A1_portrait   →  003_flower_in_stream_madeira_color.JPG
(all six landscape keys)      →  009_boat_serene_bnw_scotland.JPG
```

The live template now has three portrait placeholders. **The next
`create-from-template` call would name a placeholder that may no longer
exist.** Nothing is running — all three scheduled tasks are Disabled after
GL-38 — so this is contained, not urgent. But it is why this item goes ahead
of GL-45: `run_hourly.py` reaches the publish gate, and the publish gate
reaches Gelato.

## 3. Do the diagnostic `GET` first — it is still worth it

**The template fix explains the defect. It does not prove the pipeline half
was correct.** Those are different claims, and after the config change a
surviving code-side bug becomes much harder to see, because both bugs produce
the same symptom.

```
GET /v1/stores/{storeId}/products/5e15c0b4-dfa4-4e82-8c9a-1b0ec45b9d41
```

(Candidate 42, Etsy `4549960823`, created 08-04 from the **old** template.)
For each `productImages[]` entry, download the signed `fileUrl` and measure its
pixel aspect.

| Result | Meaning | Consequence |
|---|---|---|
| 10x24 image ≈ **0.4167** | We sent the right file; Gelato fitted it | **One bug.** Template fix is the whole fix. Proceed to §4. |
| 10x24 image ≈ **0.684** | We sent the uncropped master | **Two bugs.** The template fix hides the second one. Go to §6 before anything else. |

Known good reference values for that candidate, already measured on disk:
`42.png` = 6656×9728 (0.6842), `42_10x24_crop.png` = 4053×9728 (**0.4166**),
`42_5x7_crop.png` = 6656×9318 (0.7143). The crop maths is correct; the
question is only which file reached Gelato.

**Ten minutes, read-only, no live writes.** Do not skip it because the
dashboard already looks fixed.

## 4. Re-resolve the template — do not guess the names

Pull the template from the API and enumerate it. Guessing placeholder names
from the dashboard is how the config got stale in the first place.

- `GET` the portrait template (`23444c3a-…`) and the landscape one
  (`5a8ab628-…`).
- Record, per variant: `templateVariantId`, and **every** placeholder name it
  exposes.
- **Check whether `templateVariantId`s changed.** Adding placeholders should
  not renumber variants, but "should not" is not "did not", and all twelve are
  hardcoded in `static_config.json`.
- **Check the landscape template too.** GL-18 (landscape enablement) is
  post-launch, but if landscape has the same one-placeholder defect, record it
  now while the context is loaded — that is a free finding today and a
  rediscovery later.

Then update `config/static_config.json` so each of the twelve
`<size>_<orientation>` keys names its correct placeholder. Under the new
template the portrait keys collapse into three groups: the four primary sizes
(8x12, A3, A2, A1) share one, 5x7 has its own, 10x24 has its own — which
mirrors the aspect-ratio-group structure the pipeline already uses.

### The `200` is not proof

**GL-22a Q2 already established that Gelato returns `200` for changes it
silently drops** (the `PUT` that echoed back a third variant and never created
it). Assume the same is possible for an unrecognised placeholder name: the
create may succeed, the image may simply not land where you think.

Verification must therefore be **by measurement, not by status code** — poll
the product, download each variant's `productImages[]` file, and assert the
aspect. That is the same method as §3 and it should become the standard check
for this integration.

## 5. Fix the dry-run gate — ships regardless of everything above

`group_product._image_url_for`:

```python
crop = crops.get(row["group_type"])
if crop is not None and config.is_live_mode("GELATO"):
    return crop["durable_url"]
return candidate["base_image_url"]
```

The crop URL is gated on **live mode**, so in a dry run the function returns
the uncropped master and **the crop path never executes at all**. That is why
the two-night soak was structurally incapable of catching this class of
defect: night 1 was running a different program.

The gate is asking the wrong question. What it actually needs to know is
*"is this URL fetchable by Gelato?"*, which is `config.is_r2_configured()` —
the same all-or-nothing env check `artwork_store._r2_config` already uses, and
which correctly falls back to the master when R2 is absent and
`persist_group_crop` can only return a local filesystem path.

Ship with a test that fails if the crop path is ever bypassed in dry-run
again. There is already a live-shaped test to model it on:
`test_real_create_sends_hosted_print_crop_not_raw_master_for_10x24`.

**Standing principle worth adding to `CLAUDE.md` rather than just fixing
here:** a dry run that takes a *different branch* from live is not a
rehearsal, it is a different program. Dry-run should change what a call
*does*, never which code path reaches it.

## 6. Only if §3 says 0.684 — the code-side suspect

Look first at `create_candidate_gelato_product`'s reuse branch:

```python
if product_row["gelato_product_id"]:
    existing = {row["size"] for row in <group_product_variants>}
    wanted   = {row["size"] for row in variant_rows}
    if not wanted <= existing: raise SharedProductVariantError
```

Two properties to weigh:

- The branch **builds no crops and sends no `fileUrl`s at all** — it assumes
  the product already carries the right images.
- The guard compares the **DB to itself**, never to Gelato. A product created
  early with only the primary group's four sizes passes it silently, because
  the variant rows for 5x7 and 10x24 exist in the table whether or not they
  ever reached the API.

The honest fix is to compare against the live product (`GET` its variants)
rather than against our own table, and to fail loud on a mismatch — which is
what the exception's docstring already claims the check does.

## 7. Then verify live, once

One controlled end-to-end create against the new template, using an existing
approved candidate rather than a fresh generation.

- Confirm all six variants carry the correct per-variant image **by
  downloading and measuring**, per §4.
- **Clean up in the same breath as the delete** — GL-36's standing lesson:
  the previous cleanup deleted live listings and never touched the DB, which
  cost the GL-34 session its control listing. Update the rows.
- **Do not delete candidate 42's listing `4549960823` yet.** It is GL-36's
  negative control for the eventual re-soak and it is referenced in the GL-11
  email. Retire it deliberately, not as part of this cleanup.

## 8. Definition of done

- [ ] §3's diagnostic `GET` run and its measured aspects recorded — **one bug
      or two, stated explicitly.**
- [ ] Both templates re-resolved from the API; every `templateVariantId` and
      placeholder name in `static_config.json` verified against the live
      template, not assumed.
- [ ] Landscape template's placeholder structure recorded (finding only; GL-18
      stays post-launch).
- [ ] `_image_url_for` gated on `is_r2_configured()`, with a test that fails if
      the crop path is bypassed in dry-run.
- [ ] One live create verified **by downloaded pixel aspect per variant**, not
      by `200`.
- [ ] DB updated in the same operation as any live deletion.
- [ ] GL-22d's status corrected in the plan — it was struck on Q1's evidence
      and Q1 did not bear on this.
- [ ] Findings written to `docs/2026-08-09-gl48-findings.md`; the GL-48 row
      updated with the answer.

## 9. Out of scope

- **GL-45, GL-46, GL-47, GL-49.** GL-45's `getWebhookInfo` check can run in
  parallel — it needs no code and no session — but its investigation does not
  start here.
- **GL-18 / landscape enablement.** Record what the landscape template looks
  like; build nothing.
- **Re-authoring any scene bundle.** The compositor and the mockup gallery are
  not implicated: this is the *print* file submitted to Gelato, not the
  listing photography.

## 10. Tool fit (CLAUDE.md §7)

**Split, deliberately.** §3 and §4's API reads are a handful of authenticated
`GET`s and belong wherever they are quickest — the sandbox here cannot reach
`gelatoapis.com`, so they run on the desktop. §5 and §6 are **Claude Code,
in-repo, test-driven.** §7's live create is owner-supervised by policy
(CLAUDE.md: no live Gelato create without an explicit go-ahead).

**The template edit itself is already done and is owner-manual by nature** —
there is no API path to author a placeholder transform, which is precisely why
this defect could only ever be found by looking at the dashboard.
