"""GL-19 M1 throwaway harness: offline render of the real primary bundles
against an approved master. Not promoted into pipeline/. Writes ordered
PNGs to outputs/gl19_m1/ (flat scenes first, then lifestyle - Etsy rank
order) and asserts determinism + size-matches-meta."""

import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.mockup_render import MockupRenderError, render_scene, load_bundle  # noqa: E402
from pipeline import image_crop  # noqa: E402
from PIL import Image  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "masters" / "portrait-0684.png"
REAL_MASTER = ROOT / "db" / "base_artwork" / "39.png"     # candidate 39, approved


def resolve_master(argv=()) -> Path:
    """`--art PATH`, else the approved master, else the tracked fixture.

    db/base_artwork/ is gitignored, so on CI the fixture is what runs. Same
    ratio (0.6846 against 0.6842), 1024px instead of 9728."""
    argv = list(argv)
    if "--art" in argv:
        return Path(argv[argv.index("--art") + 1])
    return REAL_MASTER if REAL_MASTER.exists() else FIXTURE


MASTER = resolve_master()
# Read from the config rather than a list kept in step with it by hand: this
# harness exists to render exactly what the pipeline would, and P4 is adding
# bundles. Groups with no bundles yet simply contribute nothing.
_CFG = json.loads((ROOT / "config" / "static_config.json").read_text())["mockup_templates"]
SCENE_DIRS = [(group, ROOT / "assets" / "mockups" / group / orientation / scene)
              for group, by_orientation in _CFG.items()
              for orientation, scenes in by_orientation.items()
              for scene in scenes]
OUT_DIR = ROOT / "outputs" / "gl19_m1"


def main(argv=()):
    master = resolve_master(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"master: {master}")
    master_bytes = master.read_bytes()
    art_primary = Image.open(master).convert("RGB")
    # group_product.py pre-crops the master to the group's print ratio for every
    # non-primary group before render_scene ever sees it (only primary skips that
    # step - CLAUDE.md: master's 0.6842 is close enough to primary's own range).
    # Feeding the raw master into a 5x7/10x24 bundle's aspect guard is a harness
    # bug, not a bundle defect: no 0.68-ish master can ever pass a 2%-budget check
    # against an un-precropped 10x24 target.
    art_by_group = {"primary": art_primary}

    # Per-scene rather than one render_scenes() call: GL-21's aspect guard
    # rejects any bundle whose quad is not the master's aspect, and GL-6 attempt
    # 3 re-authors the four bundles one at a time - the harness has to keep
    # rendering the ones that are ready and name the ones that are not.
    blocked = []
    for group, d in SCENE_DIRS:
        if group not in art_by_group:
            art_by_group[group] = Image.open(
                io.BytesIO(image_crop.print_crop_bytes(master_bytes, group))
            ).convert("RGB")
        art = art_by_group[group]
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
    main(sys.argv[1:])
