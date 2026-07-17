import io
from pathlib import Path

from PIL import Image

import pipeline.http as http

CROP_CACHE_DIR = Path(__file__).resolve().parent.parent / "db" / "group_preview_images"


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


def crop_for_group(source_image_url: str, group_type: str, group_product_id: int) -> str:
    """Fetches the source artwork, cover-crops it to group_type's aspect ratio, and
    saves it locally - returns the local file path (product_images.image_url stores
    either an http(s) URL or a local path; callers that need to fetch it check
    which)."""
    raw = http.fetch_bytes(source_image_url)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    cropped = cover_crop(image, target_ratio_for_group_type(group_type))

    CROP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CROP_CACHE_DIR / f"{group_product_id}.jpg"
    cropped.save(out_path, format="JPEG", quality=90)
    return str(out_path)
