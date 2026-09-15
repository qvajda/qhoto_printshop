# GL-27 ask — 8 unwired bundles + 1 unbundled inflow source

Refs #52. This doc is the ask only — it does not wire, delete, or edit any
asset. It puts each row's evidence in front of the owner so a verdict can be
recorded. Gate results below were re-measured today (2026-09-15) with
`python scripts/mockup_qa.py check`; contact sheets were generated locally
with `python scripts/mockup_qa.py sheet` (not committed — paths are on this
machine). `background.png` links are the committed asset on GitHub
(`master` @ `4830c9e`).

**Ask per row: wire, delete, or keep unwired with the reason recorded** (for
the kitchenshelf and sideboard rows: delete, regenerate (paid), or record
reason).

| Scene | Group | Gate | Recorded evidence | Contact sheet (local) | GitHub |
|---|---|---|---|---|---|
| `lifestyle_studio_held` | primary | PASS 9/9 | **Rejected.** `primary/portrait/lifestyle_held_greytee/meta.json` notes it as "Replacement for the rejected lifestyle_studio_held" — the studio dressing implied hand-painted art. | `outputs/mockup_qa/lifestyle_studio_held.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/lifestyle_studio_held/background.png) |
| `lifestyle_held_greytee` | primary | PASS 9/9 | Take 1 of 2 of the studio_held replacement. Take 2, `lifestyle_held_creamtee`, is wired. No verdict recorded on take 1. | `outputs/mockup_qa/lifestyle_held_greytee.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/lifestyle_held_greytee/background.png) |
| `lifestyle_framed_wall_plant` | primary | PASS 9/9 | Pre-pivot. `meta.json` notes: "kept here only so its source survives". No verdict recorded. | `outputs/mockup_qa/lifestyle_framed_wall_plant.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/lifestyle_framed_wall_plant/background.png) |
| `lifestyle_shelf_books` | primary | PASS 9/9 | Pre-pivot. `meta.json` notes: "kept here only so its source survives". No verdict recorded. | `outputs/mockup_qa/lifestyle_shelf_books.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/lifestyle_shelf_books/background.png) |
| `flat_leaning_bookstack` | primary | PASS 9/9 | Seeded from a photograph, pre-pivot. No verdict recorded. | `outputs/mockup_qa/flat_leaning_bookstack.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/flat_leaning_bookstack/background.png) |
| `flat_pegs_windowsill` | primary | PASS 9/9 | Landed in the 2026-07-30 re-screen (chroma plan §4.3), never wired in P4c. No verdict recorded. | `outputs/mockup_qa/flat_pegs_windowsill.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/flat_pegs_windowsill/background.png) |
| `lifestyle_console_pampas` | primary | PASS 9/9 | Landed in the 2026-07-30 re-screen (chroma plan §4.3), never wired in P4c. No verdict recorded. | `outputs/mockup_qa/lifestyle_console_pampas.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/primary/portrait/lifestyle_console_pampas/background.png) |
| `lifestyle_small_bookstack` | **5x7** | PASS 9/9 (distortion 1.94%, limit 2%, aspect 0.7284) | Chroma plan: "awaiting an owner verdict". **The shipping 5x7 gallery has exactly one image** — this is the strongest 5x7 asset in the repo and the row that matters most. | `outputs/mockup_qa/lifestyle_small_bookstack.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/5x7/portrait/lifestyle_small_bookstack/background.png) |
| `lifestyle_small_kitchenshelf` | 5x7 | **FAIL** distortion 2.26% (limit 2%, aspect 0.7308) | Untracked at filing, now committed (`b8f80cc`). Chroma plan: "a regenerate, not a re-author" — it fails the gate as-authored and cannot be fixed by re-cropping. | `outputs/mockup_qa/lifestyle_small_kitchenshelf.png` | [background.png](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/5x7/portrait/lifestyle_small_kitchenshelf/background.png) |
| `lifestyle_sideboard_leaning` | primary (inflow only, no bundle) | n/a — never authored into a bundle | Reason recorded in `docs/2026-07-29-gl6-chroma-model-plan.md` §6: occluded corner, screen FAIL on `no-outside` and `frontal`. Reason exists but sits in a plan doc, not beside the asset. | — | [inflow source](https://github.com/qvajda/qhoto_printshop/blob/master/assets/mockups/inflow/primary/lifestyle_sideboard_leaning.png) |

## Already resolved since filing (2026-09-15, no action needed)

- `assets/mockups/manifest.json` — deleted.
- `inflow/**/replicate-prediction-*` and `desktop.ini` — gitignored (`b8f80cc`).
- Missing `key_rgb` on inflow sidecars — every keyed bundle's `scene.json` carries
  `key_rgb: [0, 177, 64]`; `reauthor` reads provenance from `scene.json`, not the
  sidecar, so a re-`extract` no longer silently drops `d_key_spill`.

## Owner: reply per row

State one of {wire, delete, keep unwired — reason} per scene (kitchenshelf/
sideboard: {delete, regenerate, record reason}) on this PR or on #52. A
follow-on `type:code` / `gate:machine` sortie will apply the verdicts.
