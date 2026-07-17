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
