"""GL-6 attempt-3 P0: keyed scene generation (authoring-time only, throwaway).

SUPERSEDED for scene generation (2026-07-29): mockup scenes are now hand-run
through Nano Banana Pro (google/nano-banana-pro) straight into
assets/mockups/inflow/, not batch-fired here. See
docs/2026-07-29-p4b-scene-generation-pivot.md - P4b1's 61 delivered images
scored 0/20 primary and 0/18 10x24 on `aspect` (schnell can't hold a stated
opening size, and 10x24's 0.4167 sits outside its distribution entirely), while
the shared negation-heavy prompt tail summoned the mat/glazing it forbade.
Nano Banana passed 9/9 on the first geometry-carded attempt. This module is
kept as the schnell batch harness and as historical provenance for the four
bundles that *were* authored from its output (see §2 of the pivot doc) - their
scene.json still points at outputs/gl6_*, and this file is what produced those
pixels.

Generates mockup *scenes* - not artwork - whose print area is a solid flat
key-colour panel, so the matte extracts exactly (including curl and every
overlapping prop) and the drop shadow FLUX renders belongs to the silhouette the
art will actually occupy. Plan §3.2; the 2026-07-23 brief's "do not prompt for a
keyed insert" is deliberately reversed.

Model: black-forest-labs/flux-schnell (Apache-2.0 weights) - this script's own
choice, unchanged and not up for revisiting here. The "only image model this
project may use" rule now lives with pipeline/generate.py: it governs the
printed artefact a buyer pays for (the licence is the whole point), not scene
photography, which CLAUDE.md's 2026-07-29 scene-generation constraint carves
out separately. aspect_ratio 3:4 @ 1 megapixel gives 896x1152, exactly the
existing bundles' size.

    scene_generate.py plan            # prompts + cost, no API call (default)
    scene_generate.py fire [--seeds N] [--only clips,leaning,framed,shelf]
                          [--key emerald] [--out gl6_p4a]
"""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pipeline.config as config          # noqa: E402
import pipeline.replicate_client as rc    # noqa: E402

OUT = ROOT / "outputs" / "gl6_keyed"
COST_PER_IMAGE = 0.003                    # schnell, 1MP (SPEC_v4.11 §617)
PACING_SECONDS = 11.0                     # same cap generate.py paces for: granted-credit
                                          # accounts are capped at 6 requests/minute
SEEDS = (11, 22)

KEYS = {
    # saturated, unambiguous, and far from anything a poster room contains
    "emerald": dict(rgb=(0, 177, 64), words="vivid emerald green"),
    "magenta": dict(rgb=(255, 0, 255), words="vivid magenta"),
}

# One line per scene type x prompt variant. {key} is substituted per key colour.
# Every prompt has to earn the machine screen: one panel, flat, straight-on,
# no inner mat line, props overlapping but not burying it.
COMMON = ("Straight-on frontal photograph, the panel rectangular and square to the "
          "camera, its surface one unbroken sheet of flat matte {key} paint, the same "
          "colour edge to edge, ending exactly at the panel's own outline. Natural "
          "daylight rakes across the whole scene. Photographic, 50mm, sharp, minimal "
          "styling.")


def _framed(w_cm, h_cm):
    """P4a's proven framed tail: dimensioned opening, glass and mat named and
    forbidden (§10.1). Only the opening's size varies per group."""
    return (f"The frame is a plain flat profile 12mm wide with no mount and no glass. "
            f"Its opening measures {w_cm}cm wide by {h_cm}cm tall and is filled corner "
            f"to corner by one solid panel of {{key}}, which meets the frame's inner "
            f"edge as a hard crisp painted line. No glazing, no glass, no reflection, "
            f"no white mat, no mount board, no second border inside the frame. ") + COMMON


def _sheet(w_cm, h_cm):
    """The thin-sheet tail (§10.3), dimensioned per group. Hanging only - a sheet
    standing on furniture is 0/21."""
    return (f"The paper is 0.2mm thin, {w_cm}cm wide by {h_cm}cm tall, its cut edge "
            f"visible as the edge of a sheet of paper. Not a mounted board, not a "
            f"canvas, not foam board, no backing panel, no frame, no thick slab. The "
            f"sheet is one solid panel of {{key}}. ") + COMMON


PROMPTS = {
    "clips": [
        "A single portrait sheet of poster paper hanging from two small black bulldog "
        "clips on a thin wire against a pale plaster wall, its lower corners curling "
        "slightly forward, casting a soft shadow on the wall behind it. The sheet is "
        "one solid panel of {key}. " + COMMON,
        "A portrait poster sheet clipped to a slim brass rail with two wooden pegs, "
        "hanging against a warm off-white wall beside a window, soft daylight raking "
        "across it. The sheet is one solid panel of {key}. " + COMMON,
        "A large portrait sheet of paper pinned flat to a pale studio wall with four "
        "small matte-black clips, a faint shadow under its edges. The sheet is one "
        "solid panel of {key}. " + COMMON,
    ],
    "leaning": [
        "A portrait board leaning against a pale plaster wall on a light oak floor, a "
        "small stack of hardback books resting against its lower left corner and a "
        "ceramic vase to its right, soft afternoon light. The board's face is one solid "
        "panel of {key}. " + COMMON,
        "A portrait panel leaning against a whitewashed brick wall on a concrete floor, "
        "a rolled linen throw and two books at its base, morning light from the left. "
        "The panel's face is one solid panel of {key}. " + COMMON,
        "A thin portrait board propped against a warm grey wall on pale timber "
        "floorboards, a trailing plant in a terracotta pot beside it. The board's face "
        "is one solid panel of {key}. " + COMMON,
    ],
    # P4a rewrite. v1-v3 (kept below as `framed_v1`) produced 18 candidates and
    # not one passed the screen: 9 failed `sharp` at 2.3-4.8 against a 3.0 limit,
    # the rest `aspect`. A soft key edge in a *frame* is glazing - FLUX renders
    # glass, and glass puts a reflection gradient and a bevel shadow across the
    # panel's own boundary, which is exactly the edge the matte has to cut. So:
    # name the glass and forbid it, forbid the mat, and give the opening real
    # dimensions instead of the ratio words it kept ignoring.
    "framed": [
        "A slim matte-black portrait picture frame hanging flat on a warm sage plaster "
        "wall above a terracotta pot, lit softly from the left. The frame is a plain flat "
        "profile 12mm wide with no mount and no glass. Its opening measures 20cm wide by "
        "30cm tall and is filled corner to corner by one solid panel of {key}, which meets "
        "the frame's inner edge as a hard crisp painted line. No glazing, no glass, no "
        "reflection, no white mat, no mount board, no second border inside the frame. "
        + COMMON,
        "A thin natural oak portrait picture frame on a pale cream wall in a bright living "
        "room, a rattan pendant lamp out of focus behind. The frame is a plain flat profile "
        "12mm wide with no mount and no glass. Its opening measures 20cm wide by 30cm tall "
        "and is filled corner to corner by one solid panel of {key}, which meets the "
        "frame's inner edge as a hard crisp painted line. No glazing, no glass, no "
        "reflection, no white mat, no mount board, no second border inside the frame. "
        + COMMON,
        "A slender white portrait picture frame on a soft clay-pink wall, a small brass "
        "sconce casting warm light across it. The frame is a plain flat profile 12mm wide "
        "with no mount and no glass. Its opening measures 20cm wide by 30cm tall and is "
        "filled corner to corner by one solid panel of {key}, which meets the frame's "
        "inner edge as a hard crisp painted line. No glazing, no glass, no reflection, no "
        "white mat, no mount board, no second border inside the frame. " + COMMON,
    ],
    # P4a, the backing-slab fix. §8.1 showed most of the "mounted board" look was
    # the overlay wash, now gone - but a residual slab is real on both keyed
    # scenes: FLUX reads "panel"/"board" as a thick mounted substrate. These name
    # the paper's own thinness and forbid every substrate word.
    "clipsheet": [
        "A single unframed sheet of thin matte poster paper hanging from two small black "
        "bulldog clips on a thin wire against a pale plaster wall, casting a soft shadow "
        "behind it. The paper is 0.2mm thin, its cut edge visible as the edge of a sheet "
        "of paper and slightly wavy under its own weight. Not a mounted board, not a "
        "canvas, not foam board, no backing panel, no frame, no thick slab. The sheet is "
        "one solid panel of {key}. " + COMMON,
        "A single unframed sheet of thin matte poster paper clipped to a slim brass rail "
        "with two wooden pegs against a warm off-white wall beside a window, daylight "
        "raking across it. The paper is 0.2mm thin, its cut edge visible as the edge of a "
        "sheet of paper. Not a mounted board, not a canvas, not foam board, no backing "
        "panel, no frame, no thick slab. The sheet is one solid panel of {key}. " + COMMON,
    ],
    "shelfsheet": [
        "A single unframed sheet of thin matte poster paper with sharp square corners "
        "leaning against a pale limewash wall on a floating oak shelf, a stack of two "
        "books and a small brass candlestick beside it. The paper is 0.2mm thin and its "
        "cut edge reads as the edge of a sheet of paper, curving very slightly where it "
        "leans. Not a mounted board, not a canvas, not foam board, no backing panel, no "
        "frame, no thick slab. The sheet is one solid panel of {key}. " + COMMON,
        "A single unframed sheet of thin matte poster paper with sharp square corners "
        "standing upright on a walnut console table against a warm beige wall, a small "
        "ceramic lamp glowing to its right and a trailing plant to its left. The paper is "
        "0.2mm thin and its cut edge reads as the edge of a sheet of paper. Not a mounted "
        "board, not a canvas, not foam board, no backing panel, no frame, no thick slab. "
        "The sheet is one solid panel of {key}. " + COMMON,
    ],
    # v4-v6: "portrait panel" made FLUX render a thick board with rounded corners
    # and the key inset on its face, which composites as a print mounted on an
    # oversized white slab. Ask for a single thin sheet with square corners.
    "shelf": [
        "A single thin sheet of poster paper with sharp square corners standing upright "
        "against a warm beige bedroom wall on a walnut console table, its bottom edge "
        "resting on the wood, a small ceramic lamp glowing to its right and a trailing "
        "plant to its left. The sheet is one solid panel of {key} from corner to corner, "
        "its four edges straight and its paper thin enough to see it is a single sheet. "
        + COMMON,
        "A single thin sheet of poster paper with sharp square corners leaning against a "
        "pale limewash wall on a floating oak shelf, a stack of two books and a small "
        "brass candlestick beside it. The sheet is one solid panel of {key} from corner "
        "to corner, its four edges straight and its paper thin enough to see it is a "
        "single sheet. " + COMMON,
        "A single thin sheet of poster paper with sharp square corners standing on a "
        "marble sideboard against a soft white wall, a glass vase with dried grasses to "
        "one side, late daylight from a window off frame. The sheet is one solid panel of "
        "{key} from corner to corner, its four edges straight and its paper thin enough "
        "to see it is a single sheet. " + COMMON,
    ],

    # ---- P4b wide probe (2026-07-29) -------------------------------------
    # One composition per family, 4 seeds each: probe wide once, then buy seeds
    # only on families that land (owner, 2026-07-29). Framed everywhere it can
    # be - it is the one lifestyle branch P4a proved - and hanging sheets only.
    # `pri_` = primary (opening 20x30), `s57_` = 5x7 (13x18), `t24_` = 10x24
    # (25x60). Screen each with the matching --group.

    "pri_sofa": ["A slim matte-black portrait picture frame hanging on a pale greige "
                 "living-room wall above a low linen sofa, a cushion and a folded throw "
                 "below it, soft daylight from the right. " + _framed(20, 30)],
    "pri_bed": ["A thin natural oak portrait picture frame hanging on a warm white "
                "bedroom wall above a linen headboard, a bedside table with a small lamp "
                "beneath it. " + _framed(20, 30)],
    "pri_hallway": ["A slender white portrait picture frame on a pale hallway wall above "
                    "a narrow oak bench, a pair of shoes and a woven basket below, light "
                    "from a door out of frame. " + _framed(20, 30)],
    "pri_desk": ["A slim black portrait picture frame standing upright on a walnut desk "
                 "against a pale plaster wall, a ceramic mug and two closed notebooks "
                 "beside it, morning light from the left. " + _framed(20, 30)],
    "pri_kitchen": ["A thin oak portrait picture frame leaning against a whitewashed "
                    "kitchen wall on a wide floating shelf, two stoneware jars and a "
                    "small olive plant beside it. " + _framed(20, 30)],
    "pri_easel": ["A slim matte-black portrait picture frame resting on a pale wooden "
                  "floor easel against a warm plaster wall, a trailing plant in a "
                  "terracotta pot to one side. " + _framed(20, 30)],

    "s57_nightstand": ["A small 13 by 18 centimetre portrait picture frame in slim black "
                       "standing on an oak nightstand beside a small ceramic lamp and a "
                       "hardback book, warm bedroom light. The frame is small enough that "
                       "the lamp beside it is taller. " + _framed(13, 18)],
    "s57_desk": ["A small 13 by 18 centimetre portrait picture frame in pale oak standing "
                 "on a wooden desk beside a ceramic coffee mug and a pair of reading "
                 "glasses, daylight from a window off frame. The mug reaches halfway up "
                 "the frame. " + _framed(13, 18)],
    "s57_kitchenshelf": ["A small 13 by 18 centimetre portrait picture frame in slim "
                         "white standing on a floating kitchen shelf between two small "
                         "stoneware cups and a tiny potted herb, soft daylight. The cups "
                         "are half the frame's height. " + _framed(13, 18)],
    "s57_easel": ["A small 13 by 18 centimetre portrait print held in a little brass "
                  "tabletop easel on a marble console, a folded linen napkin and a small "
                  "glass vase beside it. " + _framed(13, 18)],
    "s57_books": ["A small 13 by 18 centimetre portrait picture frame in slim black "
                  "propped on a stack of three hardback books on a side table, a small "
                  "brass candlestick beside it, late afternoon light. " + _framed(13, 18)],
    "s57_windowsill": ["A small 13 by 18 centimetre portrait picture frame in natural oak "
                       "standing on a deep painted windowsill beside a small potted "
                       "succulent, bright diffuse daylight. " + _framed(13, 18)],

    "t24_doors": ["A very tall narrow portrait picture frame in slim matte black hanging "
                  "on a pale plaster wall in the space between two doorways, the frame "
                  "two and a half times taller than it is wide. " + _framed(25, 60)],
    "t24_console": ["A very tall narrow portrait picture frame in thin oak hanging on a "
                    "warm white wall above a narrow console table holding a small vase, "
                    "the frame two and a half times taller than it is wide. "
                    + _framed(25, 60)],
    "t24_stairwell": ["A very tall narrow portrait picture frame in slim white hanging on "
                      "a stairwell wall beside a plain handrail, the frame two and a half "
                      "times taller than it is wide. " + _framed(25, 60)],
    "t24_floorlean": ["A very tall narrow portrait picture frame in slim black leaning "
                      "against a warm plaster wall on a pale oak floor, a trailing plant "
                      "in a terracotta pot beside it, the frame two and a half times "
                      "taller than it is wide. " + _framed(25, 60)],
    "t24_hanger": ["A very tall narrow unframed sheet of thin matte poster paper held top "
                   "and bottom in slim wooden magnetic poster hangers, hanging flat on a "
                   "pale plaster wall, the sheet two and a half times taller than it is "
                   "wide. " + _sheet(25, 60)],
    "t24_clips": ["A very tall narrow unframed sheet of thin matte poster paper hanging "
                  "from two small black bulldog clips on a thin wire against a warm "
                  "off-white wall, a soft shadow behind it, the sheet two and a half "
                  "times taller than it is wide. " + _sheet(25, 60)],
}


def jobs(only=None, seeds=SEEDS, variant=None):
    for scene_type, variants in PROMPTS.items():
        if only and scene_type not in only:
            continue
        for vi, template in enumerate(variants):
            if variant and vi + 1 != variant:
                continue
            for key_name, key in KEYS.items():
                for seed in seeds:
                    yield dict(
                        name=f"{scene_type}_v{vi + 1}_{key_name}_s{seed}",
                        scene_type=scene_type, variant=vi + 1, key=key_name,
                        key_rgb=key["rgb"], seed=seed,
                        prompt=template.format(key=key["words"]),
                    )


def plan(only=None, seeds=SEEDS, variant=None):
    js = list(jobs(only, seeds, variant))
    for scene_type, variants in PROMPTS.items():
        if only and scene_type not in only:
            continue
        print(f"\n=== {scene_type} ===")
        for vi, t in enumerate(variants):
            print(f"  v{vi + 1}: {t.format(key='<KEY>')}\n")
    print(f"model      {rc.FLUX_SCHNELL_MODEL} (Apache-2.0, never flux-dev)")
    print(f"params     aspect_ratio=3:4, megapixels=1 -> 896x1152; seeds {list(seeds)}")
    print(f"keys       " + ", ".join(f"{k} rgb{v['rgb']}" for k, v in KEYS.items()))
    print(f"batch      {len(js)} images "
          f"({len({j['scene_type'] for j in js})} scene types, "
          f"{len({(j['scene_type'], j['variant']) for j in js})} variants x "
          f"{len(KEYS)} keys x {len(seeds)} seeds)")
    print(f"cost       {len(js)} x ${COST_PER_IMAGE:.3f} = ${len(js) * COST_PER_IMAGE:.2f}")


def fire(only=None, seeds=SEEDS, out=None, variant=None):
    # A batch gets its own directory: scene_screen reads the manifest beside the
    # PNGs, and a re-run into a shared directory leaves stale images from an
    # earlier prompt revision to be screened under the new run's provenance.
    OUT = out or globals()["OUT"]
    config.load_env()
    token = config.require_env("REPLICATE_API_TOKEN")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, spent = [], 0.0
    for i, job in enumerate(list(jobs(only, seeds, variant)), 1):
        if i > 1:
            time.sleep(PACING_SECONDS)
        t0 = time.time()
        try:
            res = rc._predict(rc.FLUX_SCHNELL_MODEL, {
                "prompt": job["prompt"], "aspect_ratio": "3:4",
                "megapixels": "1", "seed": job["seed"], "output_format": "png",
            }, api_token=token)
        except Exception as e:                       # one bad prompt must not lose the batch
            print(f"[{i:3d}] {job['name']:34} FAILED {type(e).__name__}: {e}")
            manifest.append({**job, "error": str(e)})
            continue
        path = OUT / f"{job['name']}.png"
        path.write_bytes(httpx.get(res["image_url"], timeout=60, follow_redirects=True).content)
        spent += COST_PER_IMAGE
        manifest.append({**job, "prediction_id": res["prediction_id"], "path": str(path)})
        print(f"[{i:3d}] {job['name']:34} {time.time() - t0:5.1f}s -> {path.name}")
    (OUT / "manifest.json").write_text(json.dumps(
        {"model": rc.FLUX_SCHNELL_MODEL, "licence": "Apache-2.0 (flux-schnell)",
         "aspect_ratio": "3:4", "megapixels": "1", "cost_usd": round(spent, 3),
         "jobs": manifest}, indent=2) + "\n")
    print(f"\n{len([m for m in manifest if 'path' in m])} images, ${spent:.2f}, "
          f"manifest -> {OUT / 'manifest.json'}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "plan"
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    if "--key" in argv:
        for k in [k for k in KEYS if k != argv[argv.index("--key") + 1]]:
            del KEYS[k]
    seeds = SEEDS
    if "--seeds" in argv:
        # --seed-start so a follow-up batch draws *new* seeds: re-running the same
        # ones just re-renders images you have already screened.
        start = int(argv[argv.index("--seed-start") + 1]) if "--seed-start" in argv else 11
        seeds = tuple(range(start, start + 11 * int(argv[argv.index("--seeds") + 1]), 11))
    variant = int(argv[argv.index("--variant") + 1]) if "--variant" in argv else None
    if cmd == "fire":
        out = ROOT / "outputs" / argv[argv.index("--out") + 1] if "--out" in argv else None
        fire(only, seeds, out, variant)
    else:
        plan(only, seeds, variant)
