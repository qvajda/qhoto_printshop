"""GL-19 M1 throwaway harness: offline render of the real primary bundles
against an approved master. Not promoted into pipeline/. Writes ordered
PNGs to outputs/gl19_m1/ (flat scenes first, then lifestyle - Etsy rank
order) and asserts determinism + size-matches-meta."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.mockup_render import MockupRenderError, render_scene, load_bundle  # noqa: E402
from PIL import Image  # noqa: E402

MASTER = ROOT / "db" / "base_artwork" / "39.png"
BUNDLE_ROOT = ROOT / "assets" / "mockups" / "primary" / "portrait"
SCENE_DIRS = [
    BUNDLE_ROOT / "flat_clips_windowlight",
    BUNDLE_ROOT / "flat_leaning_bookstack",
    BUNDLE_ROOT / "lifestyle_bedroom_console",
    BUNDLE_ROOT / "lifestyle_sage_terracotta",
]
OUT_DIR = ROOT / "outputs" / "gl19_m1"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    art = Image.open(MASTER).convert("RGB")

    # Per-scene rather than one render_scenes() call: GL-21's aspect guard
    # rejects any bundle whose quad is not the master's aspect, and GL-6 attempt
    # 3 re-authors the four bundles one at a time - the harness has to keep
    # rendering the ones that are ready and name the ones that are not.
    blocked = []
    for d in SCENE_DIRS:
        try:
            img1, img2 = (render_scene(art, load_bundle(d)) for _ in range(2))
        except MockupRenderError as e:
            blocked.append(d.name)
            print(f"{d.name}: BLOCKED - {e}")
            continue
        meta = json.loads((d / "meta.json").read_text())
        expected_size = tuple(meta["size"])
        assert img1.size == expected_size, f"{d.name}: size {img1.size} != meta {expected_size}"

        out_path = OUT_DIR / f"{d.name}.png"
        img1.save(out_path)

        b1 = hashlib.sha256(img1.tobytes()).hexdigest()
        b2 = hashlib.sha256(img2.tobytes()).hexdigest()
        assert b1 == b2, f"{d.name}: non-deterministic render ({b1} != {b2})"

        print(f"{d.name}: size={img1.size} sha256={b1[:12]} -> {out_path}")

    n = len(SCENE_DIRS) - len(blocked)
    print(f"\n{n}/{len(SCENE_DIRS)} scenes rendered, deterministic, size-checked OK.")
    if blocked:
        raise SystemExit(f"BLOCKED on {len(blocked)}: {', '.join(blocked)}")


if __name__ == "__main__":
    main()
