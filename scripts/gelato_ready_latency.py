"""GL-20: measure how long Gelato actually took to rehost product images.

Read-only. For every group_products row with a non-NULL gelato_product_id,
GET the live product and compute max(productImages[].updatedAt) -
product.createdAt - the rehost lag poll_until_ready exists to wait out.
This is a lower bound: it can't see _image_is_fetchable's S3 GET lag (see
pipeline/group_product.py). No create, no patch, no publish, no DB write.
"""
import sqlite3
import statistics
import sys
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client

DB_PATH = "db/qhoto.sqlite3"


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def measure(product_id: str) -> tuple[float, int] | None:
    product = gelato_client.get_product(product_id)
    created_at = product.get("createdAt")
    images = product.get("productImages", [])
    if not created_at or not images:
        return None
    updated_ats = [image["updatedAt"] for image in images if image.get("updatedAt")]
    if not updated_ats:
        return None
    lag = (max(_parse(t) for t in updated_ats) - _parse(created_at)).total_seconds()
    return lag, len(images)


def main() -> int:
    config.load_env()
    conn = sqlite3.connect(DB_PATH)
    product_ids = [
        row[0] for row in conn.execute(
            "SELECT gelato_product_id FROM group_products WHERE gelato_product_id IS NOT NULL"
        )
    ]

    lags = []
    print(f"{'product_id':<40} {'lag_s':>8} {'images':>7}")
    for product_id in product_ids:
        try:
            result = measure(product_id)
        except Exception as exc:
            print(f"{product_id:<40} {'ERROR':>8} {exc}")
            continue
        if result is None:
            print(f"{product_id:<40} {'SKIP':>8} (no createdAt/images)")
            continue
        lag, image_count = result
        lags.append(lag)
        print(f"{product_id:<40} {lag:>8.1f} {image_count:>7}")

    if not lags:
        print("n=0 - no measurable products", file=sys.stderr)
        return 1

    lags.sort()
    print()
    print(
        f"n={len(lags)} min={min(lags):.1f}s median={statistics.median(lags):.1f}s "
        f"p90={lags[int(0.9 * (len(lags) - 1))]:.1f}s max={max(lags):.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
