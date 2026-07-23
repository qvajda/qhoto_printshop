import io

from PIL import Image

# Preview crops only need to look right in a Telegram gallery, not print - 2000px
# long edge keeps the JPEG well under Telegram's photo size cap. (Only consumed
# as a size threshold by tests/test_image_crop.py's print-vs-preview assertion
# now that crop_for_group, its one production user, has been removed - GL-5
# final review Minor #1.)
PREVIEW_MAX_EDGE = 2000


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
