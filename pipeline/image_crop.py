import io
from pathlib import Path

from PIL import Image

import pipeline.http as http

CROP_CACHE_DIR = Path(__file__).resolve().parent.parent / "db" / "group_preview_images"

# Preview crops only need to look right in a Telegram gallery, not print - 2000px
# long edge keeps the JPEG well under Telegram's photo size cap.
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


def crop_for_group(source_image_url: str, group_type: str, group_product_id: int) -> str:
    """Fetches the source artwork, cover-crops it to group_type's aspect ratio, and
    saves it locally - returns the local file path (product_images.image_url stores
    either an http(s) URL or a local path; callers that need to fetch it check
    which)."""
    raw = http.fetch_bytes(source_image_url)
    cropped = _cropped_image(raw, group_type)

    # This is a *review/digest preview*, not the print file - the print file goes
    # through print_crop_bytes below and keeps full resolution. A print-res master
    # (now 6656x9728 after the B5 scale=8 bump) saved as q90 JPEG blows past
    # Telegram's ~10MB photo multipart cap (already bitten once, commit b3977d1),
    # so cap the preview's long edge.
    cropped.thumbnail((PREVIEW_MAX_EDGE, PREVIEW_MAX_EDGE))

    CROP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CROP_CACHE_DIR / f"{group_product_id}.jpg"
    cropped.save(out_path, format="JPEG", quality=90)
    return str(out_path)


def print_crop_bytes(raw_bytes: bytes, group_type: str) -> bytes:
    """Cover-crops the full-resolution master to group_type's aspect ratio and
    returns PNG bytes - no downsizing. This is what Gelato prints from (unlike
    crop_for_group's downsized Telegram preview), so the source pixel dimensions
    are preserved to keep the 150 DPI print-resolution guard meaningful."""
    cropped = _cropped_image(raw_bytes, group_type)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()
