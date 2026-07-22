"""Throwaway spike script: Phase 2 batch-generate empty-frame interior scenes via
Replicate FLUX.1 [schnell] (Apache-2.0, commercial-safe). Not part of the pipeline.
"""
import os
import json
import time
import random
import urllib.request

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
env = {}
with open(ENV_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
os.environ.update(env)
TOKEN = os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY")
UA = "curl/8.0"

SCENES = {
    "flat_clips_windowlight": {
        "tag": "flat",
        "prompt": (
            "A minimalist interior photograph of a warm off-white plaster wall in "
            "natural daylight. A single blank poster print hangs from two black "
            "metal binder clips attached to a thin black string, the paper unframed "
            "with a visible raw deckle edge, hanging flat and straight-on against "
            "the wall. The poster area is a plain, evenly lit blank white rectangle "
            "with no artwork, no texture, no gradient. Soft directional window light "
            "falls from the left, casting a faint soft shadow of the poster onto the "
            "wall behind it. Portrait orientation, medium shot, eye-level camera, "
            "shot on a 50mm lens, quiet Scandinavian minimalist mood, no other "
            "objects in frame."
        ),
    },
    "flat_leaning_bookstack": {
        "tag": "flat",
        "prompt": (
            "A photorealistic interior photograph of an unframed blank poster print "
            "leaning straight-on against a warm white plaster wall, resting on a "
            "pale oak wood floor. The poster's raw paper edge is visible, no frame, "
            "no mat. The poster surface is a plain, evenly lit blank white rectangle "
            "with no artwork. Beside it on the floor sits a small neat stack of "
            "three hardcover books in muted earth-tone covers. Soft warm daylight "
            "from a window out of frame lights the scene evenly from the "
            "front-left, gentle soft shadow beneath the poster where it meets the "
            "floor. Portrait orientation, eye-level medium shot, 35mm lens, calm "
            "editorial interior design photography mood."
        ),
    },
    "lifestyle_sage_terracotta": {
        "tag": "lifestyle",
        "prompt": (
            "A photorealistic lifestyle interior photograph of a large framed "
            "poster print leaning against a dusty sage-green plaster wall, resting "
            "on a terracotta tile floor. The frame is a thin light natural wood "
            "frame with a wide white matboard border. The print area inside the "
            "mat is a plain, evenly lit blank white rectangle with no artwork. The "
            "poster is staged large, statement-piece scale, roughly two-thirds the "
            "height of the wall visible in frame. Warm late-afternoon sunlight "
            "rakes in from the left at a low angle, casting a long soft diagonal "
            "shadow across the poster and floor. Beside the poster sits one small "
            "ceramic vase holding dried pampas grass. Camera positioned at a gentle "
            "15-degree angle to the wall, medium-close shot, shot on a 35mm lens, "
            "shallow depth of field, warm editorial interior photography mood."
        ),
    },
    "lifestyle_bedroom_console": {
        "tag": "lifestyle",
        "prompt": (
            "A photorealistic lifestyle interior photograph of a framed poster "
            "print hanging on a warm cream bedroom wall above a low mid-century "
            "wood console table. The frame is a black wood frame with a narrow "
            "white mat border. The print area is a plain, evenly lit blank white "
            "rectangle with no artwork. The poster is large, statement scale, "
            "centered above the console. A small warm-toned ceramic table lamp "
            "glows softly on the console below, its light casting a warm gradient "
            "up the lower portion of the wall and a soft highlight across the "
            "bottom of the poster. Linen bedding is visible at the edge of frame. "
            "Evening ambient light, cozy warm color temperature. Camera at a "
            "gentle 10-degree angle, medium shot, 50mm lens, shallow depth of "
            "field, quiet intimate mood."
        ),
    },
    "lifestyle_nook_monstera": {
        "tag": "lifestyle",
        "prompt": (
            "A photorealistic lifestyle interior photograph of a framed poster "
            "print leaning against a bright white wall in a sunlit reading nook, "
            "resting on a light wood floor next to a low stack of hardcover books. "
            "The frame is a slim black wood frame with a white mat border. The "
            "print area is a plain, evenly lit blank white rectangle with no "
            "artwork. The poster is staged large, statement scale. A large "
            "monstera leaf enters the frame from the bottom left corner, slightly "
            "overlapping the lower edge of the poster. Bright, soft midday "
            "daylight from a large window out of frame, crisp gentle shadows. "
            "Camera at a gentle 20-degree angle, medium shot, 35mm lens, fresh "
            "airy editorial mood."
        ),
    },
}


def api(method, path, body=None, retries=5):
    url = f"https://api.replicate.com/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "User-Agent": UA,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            r = urllib.request.urlopen(req, timeout=30)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            if e.code == 429 and attempt < retries - 1:
                try:
                    wait = json.loads(body_bytes).get("retry_after", 10)
                except Exception:
                    wait = 10
                print(f"429, waiting {wait}s...")
                time.sleep(wait + 1)
                continue
            print("HTTP ERROR", e.code, body_bytes[:500])
            raise


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "phase2_raw")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}

    predictions = {}
    for scene_id, spec in SCENES.items():
        seed = random.randint(1, 2**31 - 1)
        body = {
            "input": {
                "prompt": spec["prompt"],
                "aspect_ratio": "3:4",
                "megapixels": "1",
                "num_outputs": 1,
                "output_format": "png",
                "seed": seed,
                "go_fast": True,
            }
        }
        resp = api("POST", "/models/black-forest-labs/flux-schnell/predictions", body)
        predictions[scene_id] = resp["id"]
        manifest[scene_id] = {
            "tag": spec["tag"],
            "prompt": spec["prompt"],
            "seed": seed,
            "prediction_id": resp["id"],
        }
        print("submitted", scene_id, resp["id"])
        time.sleep(11)  # low-credit account: 6 req/min, burst 1

    # poll
    pending = dict(predictions)
    while pending:
        time.sleep(2)
        for scene_id, pred_id in list(pending.items()):
            resp = api("GET", f"/predictions/{pred_id}")
            status = resp["status"]
            if status == "succeeded":
                url = resp["output"][0] if isinstance(resp["output"], list) else resp["output"]
                fn = os.path.join(out_dir, f"{scene_id}.png")
                urllib.request.urlretrieve(url, fn)
                manifest[scene_id]["output_url"] = url
                manifest[scene_id]["local_path"] = fn
                manifest[scene_id]["status"] = "succeeded"
                print("done", scene_id)
                del pending[scene_id]
            elif status == "failed":
                manifest[scene_id]["status"] = "failed"
                manifest[scene_id]["error"] = resp.get("error")
                print("FAILED", scene_id, resp.get("error"))
                del pending[scene_id]
            elif status == "canceled":
                manifest[scene_id]["status"] = "canceled"
                del pending[scene_id]

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("all done")


if __name__ == "__main__":
    main()
