import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.critic_pass as critic_pass
import pipeline.db as db


def test_build_critic_prompt_includes_rubric_and_listing_text():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "description": "A minimalist botanical print.",
    }

    prompt = critic_pass.build_critic_prompt(listing_text, 3)

    assert "Monstera Line Art Botanical Print" in prompt
    assert "A minimalist botanical print." in prompt
    assert "named artist's style" in prompt
    assert "watermark-like elements" in prompt
    assert "off-center or cut-off composition" in prompt
    assert "3 gallery images" in prompt
    assert "'passed' (boolean)" in prompt
