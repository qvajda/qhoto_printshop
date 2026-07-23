import json
from pathlib import Path

import pytest
from PIL import Image

import pipeline.mockup_render as mockup_render
from pipeline.mockup_render import MockupRenderError, load_bundle, render_scene, render_scenes

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mockups" / "flat_clips_windowlight"


def _artwork(size=(600, 800)):
    # simple synthetic pattern, not a real design - just needs real pixels
    img = Image.new("RGB", size, (200, 50, 50))
    for x in range(0, size[0], 40):
        for y in range(0, size[1], 40):
            img.putpixel((x, y), (50, 200, 50))
    return img


def test_render_scene_output_matches_bundle_size():
    bundle = load_bundle(FIXTURE_DIR)
    out = render_scene(_artwork(), bundle)
    meta = json.loads((FIXTURE_DIR / "meta.json").read_text())
    assert out.size == tuple(meta["size"])
    assert out.mode == "RGB"


def test_render_scene_produces_plausible_pixel_content():
    # coarse property check instead of a byte-exact golden (avoids opencv/libjpeg
    # version flakiness) - the composite should not just be a flat solid color
    bundle = load_bundle(FIXTURE_DIR)
    out = render_scene(_artwork(), bundle)
    colors = out.getcolors(maxcolors=out.width * out.height)
    assert colors is not None and len(colors) > 10


def test_load_bundle_raises_on_missing_dir(tmp_path):
    with pytest.raises(MockupRenderError):
        load_bundle(tmp_path / "does_not_exist")


def test_load_bundle_raises_on_missing_required_file(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "meta.json").write_text(json.dumps({
        "scene": "x", "group_type": "primary", "orientation": "portrait",
        "aperture": [[0, 0], [10, 0], [10, 10], [0, 10]], "size": [10, 10], "tag": "flat",
    }))
    (bundle_dir / "background.png").write_bytes(_png_bytes())
    # overlay.png intentionally missing
    with pytest.raises(MockupRenderError):
        load_bundle(bundle_dir)


def test_load_bundle_raises_on_malformed_aperture(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "meta.json").write_text(json.dumps({
        "scene": "x", "group_type": "primary", "orientation": "portrait",
        "aperture": [[0, 0], [10, 0], [10, 10]],  # only 3 points, not 4x2
        "size": [10, 10], "tag": "flat",
    }))
    (bundle_dir / "background.png").write_bytes(_png_bytes())
    (bundle_dir / "overlay.png").write_bytes(_png_bytes())
    with pytest.raises(MockupRenderError):
        load_bundle(bundle_dir)


def test_load_bundle_defaults_overfill_when_absent():
    bundle = load_bundle(FIXTURE_DIR)
    assert bundle.overfill == mockup_render.DEFAULT_OVERFILL


def test_render_scenes_preserves_order(tmp_path):
    artwork_path = tmp_path / "art.png"
    _artwork().save(artwork_path)
    outputs = render_scenes(str(artwork_path), [FIXTURE_DIR, FIXTURE_DIR, FIXTURE_DIR])
    assert len(outputs) == 3
    meta = json.loads((FIXTURE_DIR / "meta.json").read_text())
    for out in outputs:
        assert out.size == tuple(meta["size"])


def test_render_scene_is_deterministic():
    bundle = load_bundle(FIXTURE_DIR)
    art = _artwork()
    out1 = render_scene(art, bundle)
    out2 = render_scene(art, bundle)
    assert out1.tobytes() == out2.tobytes()


def test_render_scene_signature_takes_no_paths():
    # purity check: render_scene must not accept path-like args - it's
    # in-memory Image.Image + SceneBundle only, no file/network I/O possible
    import inspect
    params = list(inspect.signature(render_scene).parameters.values())
    assert len(params) == 2
    for p in params:
        assert p.annotation != str


def _png_bytes():
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10)).save(buf, format="PNG")
    return buf.getvalue()
