"""GL-6 attempt-3 P0: keyed scene generation (authoring-time only, throwaway).

Generates mockup *scenes* - not artwork - whose print area is a solid flat
key-colour panel, so the matte extracts exactly (including curl and every
overlapping prop) and the drop shadow FLUX renders belongs to the silhouette the
art will actually occupy. Plan §3.2; the 2026-07-23 brief's "do not prompt for a
keyed insert" is deliberately reversed.

Model: black-forest-labs/flux-schnell (Apache-2.0 weights, the only image model
this project may use - never flux-dev). aspect_ratio 3:4 @ 1 megapixel gives
896x1152, exactly the existing bundles' size.

    scene_generate.py plan            # prompts + cost, no API call (default)
    scene_generate.py fire [--seeds N] [--only clips,leaning,framed,shelf]
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
    "framed": [
        "A slim black portrait frame hanging on a warm sage plaster wall above a "
        "terracotta pot, lit softly from the left. The frame's opening is filled corner "
        "to corner by one solid panel of {key} meeting the frame's inner edge "
        "directly. " + COMMON,
        "A thin natural oak portrait frame on a pale cream wall in a bright living room, "
        "a rattan pendant lamp out of focus behind. The frame's opening is filled corner "
        "to corner by one solid panel of {key} meeting the frame's inner edge "
        "directly. " + COMMON,
        "A slender white portrait frame on a soft clay-pink wall, a small brass sconce "
        "casting warm light across it. The frame's opening is filled corner to corner by "
        "one solid panel of {key} meeting the frame's inner edge directly. " + COMMON,
    ],
    "shelf": [
        "A portrait panel standing upright on a walnut console table against a warm beige "
        "bedroom wall, a small ceramic lamp glowing to its right and a trailing plant to "
        "its left. The panel's face is one solid panel of {key}. " + COMMON,
        "A portrait panel resting on a floating oak shelf against a pale limewash wall, a "
        "stack of two books and a small brass candlestick beside it. The panel's face is "
        "one solid panel of {key}. " + COMMON,
        "A portrait panel standing on a marble sideboard against a soft white wall, a "
        "glass vase with dried grasses to one side, late daylight from a window off "
        "frame. The panel's face is one solid panel of {key}. " + COMMON,
    ],
}


def jobs(only=None, seeds=SEEDS):
    for scene_type, variants in PROMPTS.items():
        if only and scene_type not in only:
            continue
        for vi, template in enumerate(variants):
            for key_name, key in KEYS.items():
                for seed in seeds:
                    yield dict(
                        name=f"{scene_type}_v{vi + 1}_{key_name}_s{seed}",
                        scene_type=scene_type, variant=vi + 1, key=key_name,
                        key_rgb=key["rgb"], seed=seed,
                        prompt=template.format(key=key["words"]),
                    )


def plan(only=None, seeds=SEEDS):
    js = list(jobs(only, seeds))
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
          f"({len(PROMPTS if not only else only)} scene types x 3 variants x "
          f"{len(KEYS)} keys x {len(seeds)} seeds)")
    print(f"cost       {len(js)} x ${COST_PER_IMAGE:.3f} = ${len(js) * COST_PER_IMAGE:.2f}")


def fire(only=None, seeds=SEEDS):
    config.load_env()
    token = config.require_env("REPLICATE_API_TOKEN")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, spent = [], 0.0
    for i, job in enumerate(list(jobs(only, seeds)), 1):
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
    seeds = SEEDS
    if "--seeds" in argv:
        seeds = tuple(range(11, 11 + 11 * int(argv[argv.index("--seeds") + 1]), 11))
    (fire if cmd == "fire" else plan)(only, seeds)
