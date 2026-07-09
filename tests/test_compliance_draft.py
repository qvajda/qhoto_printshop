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
