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

from pipeline.mockup_render import render_scenes  # noqa: E402

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

    run1 = render_scenes(str(MASTER), SCENE_DIRS)
    run2 = render_scenes(str(MASTER), SCENE_DIRS)

    for d, img1, img2 in zip(SCENE_DIRS, run1, run2):
        meta = json.loads((d / "meta.json").read_text())
        expected_size = tuple(meta["size"])
        assert img1.size == expected_size, f"{d.name}: size {img1.size} != meta {expected_size}"

        out_path = OUT_DIR / f"{d.name}.png"
        img1.save(out_path)

        b1 = hashlib.sha256(img1.tobytes()).hexdigest()
        b2 = hashlib.sha256(img2.tobytes()).hexdigest()
        assert b1 == b2, f"{d.name}: non-deterministic render ({b1} != {b2})"

        print(f"{d.name}: size={img1.size} sha256={b1[:12]} -> {out_path}")

    print(f"\nAll {len(SCENE_DIRS)} scenes rendered, deterministic, size-checked OK.")


if __name__ == "__main__":
    main()
