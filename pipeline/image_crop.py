import io

from PIL import Image

# Preview crops only need to look right in a Telegram gallery, not print - 2000px
# long edge keeps the JPEG well under Telegram's photo size cap. (Only consumed
# as a size threshold by tests/test_image_crop.py's print-vs-preview assertion
# now that crop_for_group, its one production user, has been removed - GL-5
# final review Minor #1.)
PREVIEW_MAX_EDGE = 2000


# Physical print dimensions (short_edge_in, long_edge_in) per offered size.
# A-series inches are the ISO mm sizes converted (A3 297x420mm, A2 420x594mm,
# A1 594x841mm). Lives here, next to the ratios derived from it, and is read by
# group_product's pre-create DPI guard and by the compositor's crop guard - one
# table, because two copies of a physical constant drift.
SIZE_INCHES = {
    "5x7": (5, 7),
    "8x12": (8, 12),
    "A3": (11.69, 16.54),
    "A2": (16.54, 23.39),
    "A1": (23.39, 33.11),
    "10x24": (10, 24),
}


ISO_A_RATIO = 2 ** -0.5     # every A-series size is exactly 1:sqrt(2)


def size_ratio(size: str) -> float:
    """Printed aspect of one size. A-series is taken as the exact ISO ratio, not
    from SIZE_INCHES: those are mm conversions rounded to 2dp, so A1/A2/A3 come
    out at 0.7064/0.7071/0.7068 and would read as three different products."""
    if len(size) == 2 and size[0] == "A" and size[1].isdigit():
        return ISO_A_RATIO
    short, long = SIZE_INCHES[size]
    return short / long


def printed_ratio_range(group_type: str, static_config: dict) -> tuple[float, float]:
    """The narrowest and widest aspect a group is actually *printed* at.

    The primary group spans two: 8x12 at 0.667 and the A-series at 0.707, with
    the master's own 0.684 between them. That matters to the mockup compositor.
    A panel at 0.667 is not a 2.6% distortion of the master - it is exactly the
    8x12 the buyer receives; a panel anywhere inside the range shows a crop
    between two the buyer legitimately receives; and only outside the range is
    the mockup showing something no size in the group is ever cropped to. Note
    that no single aspect can be within 2% of *both* ends, so a nearest-ratio
    rule would reject the master itself (GL-21 P3.5/F2, owner 2026-07-28)."""
    ratios = [size_ratio(size) for size in static_config["aspect_ratio_groups"][group_type]]
    return min(ratios), max(ratios)


def target_ratio_for_group_type(group_type: str) -> float:
    """5x7 / 10x24 style group_type names are WIDTHxHEIGHT in inches - the exact
    ratio Gelato prints (confirmed via live product variant title, e.g.
    "13x18 cm / 5x7″ - Vertical"), so parsing the name is the source of truth,
    not a separately-maintained ratio table."""
    width, height = group_type.split("x")
    return int(width) / int(height)


def cover_crop(image: Image.Image, target_ratio: float) -> Image.Image:
    width, height = image.size
    current_ratio = width / height
    if current_ratio > target_ratio:
        new_width = round(height * target_ratio)
        x0 = (width - new_width) // 2
        return image.crop((x0, 0, x0 + new_width, height))
    else:
        new_height = round(width / target_ratio)
        y0 = (height - new_height) // 2
        return image.crop((0, y0, width, y0 + new_height))


def _cropped_image(raw_bytes: bytes, group_type: str) -> Image.Image:
    image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    return cover_crop(image, target_ratio_for_group_type(group_type))


def print_crop_bytes(raw_bytes: bytes, group_type: str) -> bytes:
    """Cover-crops the full-resolution master to group_type's aspect ratio and
    returns PNG bytes - no downsizing. This is what Gelato prints from, so the
    source pixel dimensions are preserved to keep the 150 DPI print-resolution
    guard meaningful."""
    cropped = _cropped_image(raw_bytes, group_type)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()
