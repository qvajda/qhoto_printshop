"""Verify a Gelato integration by reading Gelato, never by trusting a 200.

Two read-only checks, both born out of GL-48:

  templates  - every `<size>_<orientation>` key in config/static_config.json must
               name a templateVariantId and an image_placeholder_name that the LIVE
               template actually exposes. The config went stale for eight days
               because the template was edited in the dashboard and nothing here
               re-read it.
  product ID - download each variant's preview and measure the placed artwork
               rectangle inside it, alongside the dimensions and aspect of the file
               we submitted (GL-53 rider). GL-22a Q2 proved Gelato returns 200 for
               changes it silently drops, so "the create succeeded" is not evidence
               that the right file landed in the right variant - and until the two
               numbers sat on one line, a template-side re-crop was unobservable.

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


def _submitted_file_size(url: str) -> tuple:
    """(width, height) of the file we submitted for a placeholder.

    GL-53/GL-52 rider: observability only. Nothing in the pipeline ever compared
    what we sent to what the template did with it, so a template-side re-crop was
    invisible - the same failure shape as GL-53 (a decision with no assertion
    behind it). Printing both numbers on one line makes a mismatch visible without
    opening the Design editor. It does NOT detect the crop-within-rect defect
    itself; that needs the dashboard answer first (GL-52 kickoff).
    """
    # ponytail: reads the whole file to get two integers out of its header. Print
    # masters are ~20MB and this is a hand-run script; switch to a ranged GET if
    # it ever runs per-variant in a loop that matters.
    with urllib.request.urlopen(url, timeout=120) as response:
        return Image.open(io.BytesIO(response.read())).size


def measure_product(product_id: str) -> None:
    product = gelato_client.get_product(product_id)
    titles, submitted = {}, {}
    for variant in product.get("variants", []):
        titles[variant["id"]] = variant["title"]
        for placeholder in variant.get("imagePlaceholders", []) or []:
            if placeholder.get("fileUrl"):
                submitted[variant["id"]] = placeholder["fileUrl"]
    for image in product.get("productImages", []):
        variant_ids = image.get("productVariantIds", [])
        label = ", ".join(titles.get(i, i) for i in variant_ids)
        with urllib.request.urlopen(image["fileUrl"], timeout=60) as response:
            aspect = _placed_artwork_aspect(response.read())
        line = f"  {label}: placed artwork aspect {aspect:.4f}"
        url = next((submitted[i] for i in variant_ids if i in submitted), None)
        if url is None:
            print(f"{line}, submitted file: not returned by the API for this variant")
            continue
        width, height = _submitted_file_size(url)
        print(f"{line}, submitted {width}x{height} aspect {width / height:.4f}")


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
