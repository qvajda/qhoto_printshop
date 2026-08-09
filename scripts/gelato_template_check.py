"""Verify a Gelato integration by reading Gelato, never by trusting a 200.

Two read-only checks, both born out of GL-48:

  templates  - every `<size>_<orientation>` key in config/static_config.json must
               name a templateVariantId and an image_placeholder_name that the LIVE
               template actually exposes. The config went stale for eight days
               because the template was edited in the dashboard and nothing here
               re-read it.
  product ID - download each variant's preview and measure the placed artwork
               rectangle inside it. GL-22a Q2 proved Gelato returns 200 for changes
               it silently drops, so "the create succeeded" is not evidence that the
               right file landed in the right variant.

Usage:
    python scripts/gelato_template_check.py                 # templates only
    python scripts/gelato_template_check.py <product_id>    # + measure a product
"""
import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image

import pipeline.config as config
import pipeline.gelato_client as gelato_client


def check_templates() -> list:
    """Returns the config keys whose variant id or placeholder name is stale."""
    static_config = config.load_static_config()
    mismatched, live = [], {}
    for key, entry in static_config["gelato_templates"].items():
        template_id = entry["template_id"]
        if template_id not in live:
            template = gelato_client.get_template(template_id)
            live[template_id] = {
                variant["id"]: [p.get("name") for p in variant.get("imagePlaceholders", [])]
                for variant in template.get("variants", [])
            }
        variants = live[template_id]
        variant_id = entry["template_variant_id"]
        names = variants.get(variant_id)
        if names is None:
            print(f"  MISMATCH {key}: templateVariantId {variant_id} is not in the live template")
        elif entry["image_placeholder_name"] not in names:
            print(f"  MISMATCH {key}: placeholder {entry['image_placeholder_name']!r} "
                  f"not in live {names}")
        else:
            print(f"  ok {key}: {entry['image_placeholder_name']}")
            continue
        mismatched.append(key)
    return mismatched


def _placed_artwork_aspect(png_bytes: bytes) -> float:
    """Aspect of the printed artwork *inside* Gelato's square preview render.

    Gelato's productImages are 1000x1000 scene previews, not the submitted print
    file - so the file's own pixel aspect is not readable from the API at all. What
    IS readable, and is what the defect lives in, is the rectangle the artwork
    occupies on the paper: a placeholder transform authored for the wrong ratio
    letterboxes the artwork and this number stops matching the paper's ratio.
    Detected on tinted (non-white) pixels, so the white paper and the white page
    background both drop out."""
    a = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB")).astype(int)
    tinted = (a[:, :, 0] - a[:, :, 2]) > 4
    ys, xs = np.nonzero(tinted)
    return (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1)


def measure_product(product_id: str) -> None:
    product = gelato_client.get_product(product_id)
    titles = {variant["id"]: variant["title"] for variant in product.get("variants", [])}
    for image in product.get("productImages", []):
        label = ", ".join(titles.get(i, i) for i in image.get("productVariantIds", []))
        with urllib.request.urlopen(image["fileUrl"], timeout=60) as response:
            aspect = _placed_artwork_aspect(response.read())
        print(f"  {label}: placed artwork aspect {aspect:.4f}")


def main() -> int:
    config.load_env()
    print("static_config vs live templates:")
    mismatches = check_templates()
    if len(sys.argv) > 1:
        print(f"\nproduct {sys.argv[1]} - placed artwork per variant:")
        measure_product(sys.argv[1])
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
