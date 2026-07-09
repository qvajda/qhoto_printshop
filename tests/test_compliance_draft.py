import pytest

import pipeline.compliance_draft as compliance_draft


STATIC_CONFIG = {
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
}


def test_resolve_compliance_metadata_reads_static_config_fields():
    metadata = compliance_draft.resolve_compliance_metadata(STATIC_CONFIG)

    assert metadata == {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }


def test_validate_listing_text_accepts_valid_input():
    compliance_draft.validate_listing_text("Botanical Wall Art Print", ["botanical", "wall art", "minimalist"])


def test_validate_listing_text_rejects_title_over_140_chars():
    long_title = "x" * 141

    with pytest.raises(ValueError, match="140"):
        compliance_draft.validate_listing_text(long_title, ["botanical"])


def test_validate_listing_text_rejects_more_than_13_tags():
    too_many_tags = [f"tag{i}" for i in range(14)]

    with pytest.raises(ValueError, match="13"):
        compliance_draft.validate_listing_text("A short title", too_many_tags)


def test_validate_listing_text_rejects_tag_over_20_chars():
    long_tag = "x" * 21

    with pytest.raises(ValueError, match="20"):
        compliance_draft.validate_listing_text("A short title", [long_tag])
