"""Owner-review render: every authored bundle of a group, composited against a
real master, into one directory. Unlike gl19_m1_render.py this reads the
bundles on disk, not config/static_config.json's mockup_templates - the point
is to review scenes that are NOT wired in yet.

    python scripts/gl6_review_render.py [group] [master.png]

Writes outputs/gl6_review/<group>/<scene>.png (full frame, no crops - the
verdict is on the finished mockup).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.mockup_render import MockupRenderError, load_bundle, render_scene  # noqa: E402
from PIL import Image  # noqa: E402


def main(group="primary", master="db/base_artwork/39.png", orientation="portrait"):
    art = Image.open(ROOT / master).convert("RGB")
    src = ROOT / "assets" / "mockups" / group / orientation
    out = ROOT / "outputs" / "gl6_review" / group
    out.mkdir(parents=True, exist_ok=True)

    blocked = []
    for d in sorted(p for p in src.iterdir() if (p / "scene.json").exists()):
        try:
            img = render_scene(art, load_bundle(d))
        except MockupRenderError as e:
            blocked.append(d.name)
            print(f"{d.name}: BLOCKED - {e}")
            continue
        img.save(out / f"{d.name}.png")
        print(f"{d.name}: {img.size} -> {out / (d.name + '.png')}")

    print(f"\n{len(list(out.glob('*.png')))} in {out}"
          + (f"; BLOCKED {len(blocked)}: {', '.join(blocked)}" if blocked else ""))


if __name__ == "__main__":
    main(*sys.argv[1:])
