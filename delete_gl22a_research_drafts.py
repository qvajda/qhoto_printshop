"""One-off, hand-run: delete the two GL-22a research-artefact Etsy drafts.

Owner-approved 2026-08-01 (GL-22 session 2 kickoff §3). First real use of
session 1's `etsy_client.delete_listing`; the `listings_d` re-auth is done.

Destructive and irreversible, on a live external account. So: GET each listing
first and refuse unless it is still a `draft` carrying the research-probe title
recorded in docs/2026-08-01-gl22a-findings.md. If what comes back contradicts
that ledger, this stops and says so rather than deleting something else.

Both IDs and their before/after state are printed, per the kickoff's
"log both listing IDs before and after".

Usage: ETSY_LIVE_MODE=true python delete_gl22a_research_drafts.py
"""
import sys
import urllib.request

from pipeline import config, etsy_client

# docs/2026-08-01-gl22a-findings.md, "Cleanup ledger" rows 1a and 2a.
DRAFT_IDS = ("4547726856", "4547717123")
# The ledger records these as still titled "GL-22a Q1 research probe - DELETE ME", but
# that note predates Q3: the update_listing patch test renamed both, and the findings
# doc records the new title on 4547717123 itself ("GL22A-Q3-CLEAN-PATCH-MARKER
# Wildflower Print" — "our patch"). Live GET on 2026-08-01 returns:
#   4547726856  'GL22A-PATCH-MARKER Dense Wildflower Meadow Print'
#   4547717123  'GL22A-Q3-CLEAN-PATCH-MARKER Wildflower Print'
# Both still state='draft'. So the guard matches the marker prefix this research
# session stamped on them rather than the stale ledger string — narrow enough that it
# cannot match a real listing, since nothing but GL-22a ever wrote a GL22A- title.
EXPECTED_TITLE_PREFIX = "GL22A-"


def get_listing(listing_id):
    api_key = config.require_env("ETSY_API_KEY")
    api_secret = config.require_env("ETSY_API_SECRET")
    access_token = config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{etsy_client.ETSY_API_BASE}/listings/{listing_id}"

    def _build(token):
        return urllib.request.Request(
            url, headers=etsy_client._headers(api_key, api_secret, token), method="GET"
        )

    return etsy_client._call_with_refresh(_build, access_token)


def main():
    config.load_env()
    if not config.is_live_mode("ETSY"):
        print("ETSY_LIVE_MODE is not true - nothing would actually be deleted. Aborting.",
              file=sys.stderr)
        return 1

    to_delete = []
    for listing_id in DRAFT_IDS:
        try:
            listing = get_listing(listing_id)
        except Exception as exc:
            print(f"BEFORE {listing_id}: GET failed ({exc}) - skipping, not deleting blind.")
            continue
        state, title = listing.get("state"), listing.get("title")
        print(f"BEFORE {listing_id}: state={state!r} title={title!r}")
        if state != "draft":
            print(f"  REFUSING {listing_id}: expected state 'draft', got {state!r}. "
                  f"The findings-doc ledger says this was never activated - investigate "
                  f"before deleting.")
            continue
        if not (title or "").startswith(EXPECTED_TITLE_PREFIX):
            print(f"  REFUSING {listing_id}: title does not start with "
                  f"{EXPECTED_TITLE_PREFIX!r}. This is not a GL-22a research artefact.")
            continue
        to_delete.append(listing_id)

    for listing_id in to_delete:
        etsy_client.delete_listing(listing_id)
        try:
            listing = get_listing(listing_id)
            print(f"AFTER  {listing_id}: still readable, state={listing.get('state')!r} "
                  f"- delete may not have taken effect")
        except Exception as exc:
            print(f"AFTER  {listing_id}: gone ({exc})")

    skipped = [i for i in DRAFT_IDS if i not in to_delete]
    if skipped:
        print(f"\nNot deleted: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
