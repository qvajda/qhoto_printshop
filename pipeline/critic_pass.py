import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.primary_mockup as primary_mockup
import pipeline.research as research


CRITIC_RUBRIC_PROMPT_TEMPLATE = (
    "You are the compliance and quality critic for an Etsy AI-generated wall art listing. "
    "Review the {image_count} gallery images above against this rubric:\n"
    "1. Hard no-go list: no named artist's style, no recognizable characters, franchises, or "
    "logos, no implied celebrity likeness, no claims of hand-painted or one-of-a-kind original "
    "artwork - this is a print reproduction.\n"
    "2. Image quality: no obvious artifacts, no garbled or watermark-like elements, no "
    "off-center or cut-off composition, in any image.\n"
    "3. Text match: does this draft title and description actually match what's shown in the "
    "images and fit the niche?\n\n"
    "Title: {title}\n"
    "Description: {description}\n\n"
    "Reply with ONLY a JSON object with keys 'passed' (boolean) and 'reason' (string explaining "
    "the verdict - cite the specific rubric point if failing), no other text."
)


def build_critic_prompt(listing_text: dict, image_count: int) -> str:
    return CRITIC_RUBRIC_PROMPT_TEMPLATE.format(
        image_count=image_count,
        title=listing_text["title"],
        description=listing_text["description"],
    )
