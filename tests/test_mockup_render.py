import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import pipeline.mockup_render as mockup_render
from pipeline.mockup_render import MockupRenderError, load_bundle, render_scene, render_scenes

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mockups" / "flat_clips_windowlight"


def _artwork(size=(600, 866)):
    # 0.6928 - the fixture aperture's own aspect (0.6929), so the C3 cover-crop
    # is a no-op here and these tests keep testing what they used to test.
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


# --- GL-21 C1: BORDER_REPLICATE on the colour warp ---

def test_warp_border_pixels_are_not_contaminated_toward_black():
    # The bug: warpPerspective defaults to BORDER_CONSTANT=0 and INTER_CUBIC
    # samples it, so a flat bright artwork's own border came out near black.
    # Straight identity-ish warp of a uniform mid-grey, inset by half a pixel so
    # the border is partial-coverage.
    art = Image.new("RGB", (200, 300), (246, 246, 246))
    quad = np.array([[10.5, 10.5], [189.5, 10.5], [189.5, 289.5], [10.5, 289.5]], np.float32)
    warped = np.array(mockup_render._warp_into_quad(art, (200, 300), quad))
    rgb, alpha = warped[:, :, :3], warped[:, :, 3]
    covered = alpha > 0
    assert covered.any()
    # every pixel the mask says is covered carries the artwork's colour, not a
    # blend toward 0 - pre-C1 the border ring read ~0 here
    assert rgb[covered].min() > 200, rgb[covered].min()


# --- GL-21 C2: optional per-pixel matte ---

def _bundle_with_matte(tmp_path, matte_img):
    import shutil
    d = tmp_path / "bundle"
    shutil.copytree(FIXTURE_DIR, d)
    if matte_img is not None:
        matte_img.save(d / "matte.png")
    return d


def test_load_bundle_matte_is_none_when_file_absent():
    assert load_bundle(FIXTURE_DIR).matte is None


def test_opaque_matte_renders_byte_identical_to_no_matte(tmp_path):
    # C2's compatibility contract: the matte path must not perturb a bundle that
    # does not use it. An all-255 matte is the identity, so it must reproduce the
    # matte-less render exactly.
    size = tuple(json.loads((FIXTURE_DIR / "meta.json").read_text())["size"])
    d = _bundle_with_matte(tmp_path, Image.new("L", size, 255))
    art = _artwork()
    assert render_scene(art, load_bundle(d)).tobytes() == render_scene(art, load_bundle(FIXTURE_DIR)).tobytes()


def test_zero_matte_leaves_background_untouched(tmp_path):
    size = tuple(json.loads((FIXTURE_DIR / "meta.json").read_text())["size"])
    d = _bundle_with_matte(tmp_path, Image.new("L", size, 0))
    bundle = load_bundle(d)
    out = np.array(render_scene(_artwork(), bundle))
    plain = Image.alpha_composite(bundle.background, bundle.overlay).convert("RGB")
    assert out.tobytes() == plain.tobytes()


def test_matte_hole_shows_background_through_the_art(tmp_path):
    size = tuple(json.loads((FIXTURE_DIR / "meta.json").read_text())["size"])
    matte = Image.new("L", size, 255)
    # punch a hole in the middle of the aperture - a book spine / clip jaw
    quad = np.asarray(json.loads((FIXTURE_DIR / "meta.json").read_text())["aperture"], np.float32)
    cx, cy = quad.mean(axis=0).astype(int)
    for x in range(cx - 5, cx + 5):
        for y in range(cy - 5, cy + 5):
            matte.putpixel((x, y), 0)
    d = _bundle_with_matte(tmp_path, matte)
    with_hole = np.array(render_scene(_artwork(), load_bundle(d)))
    without = np.array(render_scene(_artwork(), load_bundle(FIXTURE_DIR)))
    assert (with_hole[cy, cx] != without[cy, cx]).any()
    assert (with_hole[0, 0] == without[0, 0]).all()   # untouched outside the hole


def test_load_bundle_raises_on_matte_size_mismatch(tmp_path):
    d = _bundle_with_matte(tmp_path, Image.new("L", (7, 9), 255))
    with pytest.raises(MockupRenderError):
        load_bundle(d)


def test_matte_accepts_rgba_and_uses_its_alpha_channel(tmp_path):
    size = tuple(json.loads((FIXTURE_DIR / "meta.json").read_text())["size"])
    rgba = Image.new("RGBA", size, (255, 0, 0, 0))          # opaque-looking RGB, alpha 0
    d = _bundle_with_matte(tmp_path, rgba)
    bundle = load_bundle(d)
    assert bundle.matte is not None and bundle.matte.max() == 0.0


# --- GL-21 C3: cover-crop aspect guard ---

def test_cover_crop_is_a_noop_when_aspects_match():
    art = _artwork((684, 1000))
    out, crop = mockup_render.cover_crop_to_aspect(art, 0.684)
    assert crop == pytest.approx(0.0, abs=1e-4)
    assert out.size == art.size


def test_cover_crop_trims_the_long_axis_and_never_stretches():
    art = _artwork((695, 1000))                    # 0.695 vs a 0.684 target: 1.6%
    out, crop = mockup_render.cover_crop_to_aspect(art, 0.684)
    assert crop == pytest.approx(1 - 0.684 / 0.695, abs=1e-3)
    assert out.size[1] == 1000                     # height kept, width trimmed
    assert out.size[0] / out.size[1] == pytest.approx(0.684, abs=1e-3)


def test_cover_crop_is_centred():
    art = Image.new("RGB", (100, 100), (0, 0, 0))
    art.paste(Image.new("RGB", (2, 100), (255, 255, 255)), (49, 0))   # centre stripe
    out, _ = mockup_render.cover_crop_to_aspect(art, 0.99)
    assert out.getpixel((out.width // 2, 50))[0] > 200


def test_cover_crop_raises_past_the_limit():
    with pytest.raises(MockupRenderError, match="cover-crop"):
        mockup_render.cover_crop_to_aspect(_artwork((750, 1000)), 0.684)   # 8.8%


def test_render_scene_fails_loud_on_an_aspect_mismatched_bundle():
    # the guard is wired into render_scene, not just available as a helper
    with pytest.raises(MockupRenderError, match="cover-crop"):
        render_scene(_artwork((900, 1000)), load_bundle(FIXTURE_DIR))


# --- C3's reference: the ratios the group prints, not the master's own -------
# GL-21 P3.5/F2, owner 2026-07-28. The primary group prints at 0.6667 (8x12) and
# 0.7071 (A3/A2/A1); the master's 0.6842 sits between them, so no single aspect
# is within 2% of both ends and "nearest printed ratio" would reject the master
# itself. A quad anywhere inside the range shows a crop between two the buyer
# genuinely receives.

@pytest.mark.parametrize("aspect, expected_gap", [
    (0.6667, 0.0),          # exactly the 8x12 print
    (0.7071, 0.0),          # exactly the A-series print
    (0.6842, 0.0),          # the master, between the two
    (0.6425, 0.0363),       # lifestyle_bedroom_console's framed opening
    (0.5610, 0.1585),       # attempt 1's hand-read sage quad
])
def test_print_mismatch_measures_distance_outside_the_groups_printed_range(aspect, expected_gap):
    gap, _ = mockup_render.print_mismatch(aspect, "primary")
    assert gap == pytest.approx(expected_gap, abs=5e-4)


def test_print_mismatch_is_silent_for_a_group_with_no_printed_sizes():
    assert mockup_render.print_mismatch(0.42, "not-a-group") == (0.0, 0.42)


def test_a_series_sizes_all_share_the_exact_iso_ratio():
    # SIZE_INCHES holds mm conversions rounded to 2dp, which put A1/A2/A3 at
    # 0.7064/0.7071/0.7068 - three "different products" that are one product.
    from pipeline.image_crop import ISO_A_RATIO, size_ratio
    assert {size_ratio(s) for s in ("A1", "A2", "A3")} == {ISO_A_RATIO}
    assert size_ratio("8x12") == pytest.approx(2 / 3)


def test_render_scene_accepts_a_panel_at_a_ratio_the_group_actually_prints(tmp_path):
    # 0.6667 is 2.6% off the master and would have failed the old master-relative
    # guard, while being the exact shape of the 8x12 the buyer receives.
    bundle_dir = _bundle_at_aspect(tmp_path, 2 / 3)
    assert render_scene(_artwork(), load_bundle(bundle_dir)).size == (896, 1152)


def test_render_scene_still_fails_loud_outside_the_printed_range(tmp_path):
    bundle_dir = _bundle_at_aspect(tmp_path, 0.6425)
    with pytest.raises(MockupRenderError, match="outside the ratios primary prints"):
        render_scene(_artwork(), load_bundle(bundle_dir))


def _bundle_at_aspect(tmp_path, aspect, height=600):
    import shutil
    d = tmp_path / "bundle"
    shutil.copytree(FIXTURE_DIR, d)
    meta = json.loads((d / "meta.json").read_text())
    w = round(height * aspect)
    meta["aperture"] = [[100, 100], [100 + w, 100], [100 + w, 100 + height], [100, 100 + height]]
    meta["overfill"] = 0.0
    (d / "meta.json").write_text(json.dumps(meta))
    return d
