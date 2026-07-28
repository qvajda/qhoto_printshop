import io

from PIL import Image

import pipeline.image_crop as image_crop


def test_target_ratio_for_group_type_parses_width_x_height():
    assert image_crop.target_ratio_for_group_type("5x7") == 5 / 7
    assert image_crop.target_ratio_for_group_type("10x24") == 10 / 24


def test_cover_crop_narrows_a_wide_image_to_a_tall_target_ratio():
    # 1000x1000 square source, cropping to a 5x7 (0.714) portrait target should
    # narrow the width and keep the full height - a cover-crop, not a letterbox.
    image = Image.new("RGB", (1000, 1000))
    cropped = image_crop.cover_crop(image, 5 / 7)
    assert cropped.height == 1000
    assert cropped.width == round(1000 * 5 / 7)


def test_cover_crop_shortens_a_tall_image_to_a_wide_target_ratio():
    # Portrait source, cropping to 10x24 (0.417, even more elongated portrait than
    # the source) should narrow width and keep full height.
    image = Image.new("RGB", (800, 1000))
    cropped = image_crop.cover_crop(image, 10 / 24)
    assert cropped.height == 1000
    assert cropped.width == round(1000 * 10 / 24)


def test_cover_crop_fills_frame_no_letterbox():
    # Whatever the target ratio, cover-crop must always fill the full source in at
    # least one dimension (never shrink both - that would be a letterbox/fit, which
    # is exactly the "10x24 white bars" bug this replaces).
    image = Image.new("RGB", (1200, 400))
    cropped = image_crop.cover_crop(image, 10 / 24)
    assert cropped.width == 1200 or cropped.height == 400


def test_print_crop_bytes_fills_target_ratio_no_letterbox():
    # 3328x4864 (a real scaled-down stand-in for the 6656x9728 B5 master, 2:3
    # ratio) cropped to 10x24 (0.417) must exactly hit that ratio, no margin.
    big = Image.new("RGB", (3328, 4864), (200, 180, 150))
    buf = io.BytesIO()
    big.save(buf, format="PNG")

    cropped_bytes = image_crop.print_crop_bytes(buf.getvalue(), "10x24")

    with Image.open(io.BytesIO(cropped_bytes)) as cropped:
        assert cropped.height == 4864
        assert cropped.width == round(4864 * 10 / 24)


def test_print_crop_bytes_stays_full_resolution_not_preview_capped():
    # Same size master as the preview test, but print_crop_bytes must NOT apply
    # PREVIEW_MAX_EDGE - this is the actual file submitted to Gelato for printing.
    big = Image.new("RGB", (3328, 4864), (200, 180, 150))
    buf = io.BytesIO()
    big.save(buf, format="PNG")

    cropped_bytes = image_crop.print_crop_bytes(buf.getvalue(), "10x24")

    with Image.open(io.BytesIO(cropped_bytes)) as cropped:
        assert max(cropped.size) > image_crop.PREVIEW_MAX_EDGE
