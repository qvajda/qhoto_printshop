"""#239 backfill - four drafts patched since #233 have Material multi = Archival
paper (5285); config now reads Paper (196). One PUT each, then measured
read-back (GL-22a Q2: a 200 is not evidence).

    python scripts/e239_material_backfill.py run
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.etsy_client as etsy_client

LISTING_IDS = [4583511623, 4583512453, 4583523660, 4583524152]
PROPERTY_ID = 148789511893


def _get_listing_properties(shop_id, listing_id, api_key, api_secret, access_token):
    """No get_listing_properties in etsy_client.py - #239 scope excludes touching it.
    Same GET-with-refresh shape as etsy_client.get_listing."""
    url = f"{etsy_client.ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}/properties"

    def _build(token):
        return urllib.request.Request(
            url, headers=etsy_client._headers(api_key, api_secret, token), method="GET"
        )

    return etsy_client._call_with_refresh(_build, access_token)


def run():
    shop_id = config.require_env("ETSY_SHOP_ID")
    api_key = config.require_env("ETSY_API_KEY")
    api_secret = config.require_env("ETSY_API_SECRET")
    access_token = config.require_env("ETSY_ACCESS_TOKEN")
    if not config.is_live_mode("ETSY"):
        raise SystemExit("ETSY_LIVE_MODE is not true - this backfill is only meaningful live")

    for listing_id in LISTING_IDS:
        etsy_client.update_listing_property(
            shop_id, listing_id, PROPERTY_ID, [196], ["Paper"],
            api_key=api_key, api_secret=api_secret, access_token=access_token, dry_run=False,
        )
        props = _get_listing_properties(shop_id, listing_id, api_key, api_secret, access_token)
        print(f"listing {listing_id} properties (raw):")
        print(json.dumps(props, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    config.load_env(sys.argv[1] if len(sys.argv) > 1 else None)
    run()
