"""E12 §2 - GL-69 alt-text read-back probe. Throwaway, owner-run.

One question, one verbatim answer: does Etsy's uploadListingImage accept and
PERSIST the `alt_text` multipart field as `etsy_client.upload_listing_image`
now sends it? A 200 is not evidence (CLAUDE.md, earned by GL-22a Q2) - the
read-back is.

Runs against a THROWAWAY draft listing it creates itself, never against a real
one. Prints the raw get_listing_images response so the finding can be pasted
into the findings doc verbatim.

    python scripts/e12_alt_text_probe.py run     # create, upload, read back, KEEP
    python scripts/e12_alt_text_probe.py clean <listing_id>   # delete the throwaway

'run' does not auto-delete: the read-back has to be on disk before anything is
torn down, and a crash mid-run would otherwise leave the listing behind with
nothing saying so. It prints the exact clean command to run next.

ponytail: throwaway. Delete once GL-69 has its verdict.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.etsy_client as etsy_client

ROOT = Path(__file__).resolve().parent.parent
STATIC_CONFIG = json.loads((ROOT / "config" / "static_config.json").read_text(encoding="utf-8"))
# Cannot occur naturally in generated alt text, so a read-back match cannot be coincidence.
SENTINEL = "GL69-PROBE-SENTINEL-a7f3c2e9-do-not-reuse"
READINESS_STATE_ID = 1428762550751  # read off live listing 4554354628


def _probe_image_bytes() -> bytes:
    """Any real PNG will do - Etsy rejects non-images, not boring ones."""
    for candidate in sorted(ROOT.glob("assets/mockups/geometry_cards/*.png")):
        return candidate.read_bytes()
    raise SystemExit("no geometry card PNG found to upload; point IMAGE at any real png")


def run():
    shop_id = config.require_env("ETSY_SHOP_ID")
    if not config.is_live_mode("ETSY"):
        raise SystemExit("ETSY_LIVE_MODE is not true - this probe is only meaningful live")

    listing_data = {
        "quantity": 1,
        "title": "E12 GL-69 alt-text probe - throwaway, do not publish",
        "description": "Throwaway draft created by scripts/e12_alt_text_probe.py. Delete me.",
        "price": 19.0,
        "who_made": STATIC_CONFIG["etsy_who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "taxonomy_id": STATIC_CONFIG["etsy_taxonomy_id"],
        "shipping_profile_id": int(STATIC_CONFIG["etsy_shipping_profile_id"]),
        # E12: Etsy now rejects a physical draft without one ("A readiness_state_id is
        # required for physical listings"). Read off a live listing, not invented.
        "readiness_state_id": READINESS_STATE_ID,
        "state": "draft",
    }
    listing = etsy_client.create_draft_listing(shop_id, listing_data, dry_run=False)
    listing_id = listing["listing_id"]
    print(f"created throwaway draft listing {listing_id}")

    upload = etsy_client.upload_listing_image(
        shop_id, listing_id, _probe_image_bytes(), rank=1, alt_text=SENTINEL, dry_run=False,
    )
    print("UPLOAD RESPONSE (raw):")
    print(json.dumps(upload, indent=2, ensure_ascii=False))

    images = etsy_client.get_listing_images(listing_id, dry_run=False)
    print("READ-BACK get_listing_images (raw):")
    print(json.dumps(images, indent=2, ensure_ascii=False))

    results = images.get("results", [])
    stored = [r.get("alt_text") for r in results]
    verdict = "PASS - sentinel persisted" if SENTINEL in stored else "FAIL - sentinel absent"
    print(f"VERDICT: {verdict}  (alt_text values read back: {stored!r})")
    print(f"NEXT: python scripts/e12_alt_text_probe.py clean {listing_id}")


def clean(listing_id):
    print(json.dumps(etsy_client.delete_listing(listing_id, dry_run=False), indent=2))
    print(f"deleted throwaway listing {listing_id}")


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    config.load_env()
    if argv[1] == "run":
        run()
    elif argv[1] == "clean":
        if len(argv) != 3:
            raise SystemExit("clean takes exactly one listing id")
        clean(argv[2])
    else:
        raise SystemExit(f"unknown command {argv[1]!r}")


if __name__ == "__main__":
    main(sys.argv)
