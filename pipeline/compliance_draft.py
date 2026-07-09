import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.config as config


DISCLOSURE_TEXT = (
    "This design was created using AI image generation from the seller's own prompts, "
    "then selected, edited, and prepared for print by the seller. Printed and shipped "
    "by our production partner, Gelato."
)


def resolve_compliance_metadata(static_config: dict) -> dict:
    return {
        "who_made": static_config["etsy_who_made"],
        "production_partner_ids": static_config["etsy_production_partner_ids"],
        "taxonomy_id": static_config["etsy_taxonomy_id"],
        "shipping_profile_id": static_config["etsy_shipping_profile_id"],
    }
