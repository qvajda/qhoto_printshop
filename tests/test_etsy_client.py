import json
import pathlib
from unittest.mock import patch

import pytest

import pipeline.etsy_client as etsy_client
import pipeline.http as http


def test_get_seller_taxonomy_nodes_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://openapi.etsy.com/v3/application/seller-taxonomy/nodes"
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1:secret1"
        assert request.get_header("Authorization") == "Bearer token1"
        return {"count": 2, "results": [{"id": 1}, {"id": 2}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.get_seller_taxonomy_nodes(api_key="key1", api_secret="secret1", access_token="token1")

    assert result == [{"id": 1}, {"id": 2}]


def test_create_draft_listing_dry_run_makes_no_network_call():
    listing_data = {"title": "Botanical print", "price": 24.0}

    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.create_draft_listing(
            "shop1", listing_data, api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True
    assert result["title"] == "Botanical print"


def test_create_draft_listing_sends_listing_data_as_json_body_when_live():
    captured = {}
    listing_data = {"title": "Botanical print", "price": 24.0, "who_made": "i_did"}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return {"listing_id": 999, "state": "draft"}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.create_draft_listing(
            "shop1", listing_data, api_key="key1", api_secret="secret1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings"
    assert captured["body"] == listing_data
    assert result == {"listing_id": 999, "state": "draft"}


def test_upload_listing_image_dry_run_makes_no_network_call():
    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.upload_listing_image(
            "shop1", "listing1", b"fake-image-bytes", api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_upload_listing_image_sends_multipart_body_with_image_bytes_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = request.data
        return {"listing_image_id": 555}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.upload_listing_image(
            "shop1", "listing1", b"fake-image-bytes",
            api_key="key1", api_secret="secret1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings/listing1/images"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert b"fake-image-bytes" in captured["body"]
    assert b'name="image"' in captured["body"]
    assert result == {"listing_image_id": 555}


def test_dry_run_defaults_from_live_mode_env_var(monkeypatch):
    monkeypatch.delenv("ETSY_LIVE_MODE", raising=False)

    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.create_draft_listing(
            "shop1", {"title": "x"}, api_key="key1", access_token="token1"
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_dry_run_false_when_live_mode_env_var_is_true(monkeypatch):
    monkeypatch.setenv("ETSY_LIVE_MODE", "true")

    def fake_send(request, timeout=30):
        return {"listing_id": 1}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send) as mock_send:
        etsy_client.create_draft_listing(
            "shop1", {"title": "x"}, api_key="key1", api_secret="secret1", access_token="token1"
        )

    mock_send.assert_called_once()


def test_find_all_listings_active_builds_correct_request_with_only_required_param():
    def fake_send(request, timeout=30):
        assert request.full_url == (
            "https://openapi.etsy.com/v3/application/listings/active?keywords=botanical+poster"
        )
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1:secret1"
        assert request.get_header("Authorization") is None
        return {"count": 243150, "results": [{"listing_id": 1, "num_favorers": 3}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.find_all_listings_active("botanical poster", api_key="key1", api_secret="secret1")

    assert result == {"count": 243150, "results": [{"listing_id": 1, "num_favorers": 3}]}


def test_find_all_listings_active_includes_optional_params_when_given():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        return {"count": 0, "results": []}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        etsy_client.find_all_listings_active(
            "botanical poster", limit=10, sort_on="favorites", sort_order="desc",
            api_key="key1", api_secret="secret1",
        )

    assert "limit=10" in captured["url"]
    assert "sort_on=favorites" in captured["url"]
    assert "sort_order=desc" in captured["url"]


def test_update_listing_state_dry_run_makes_no_network_call():
    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.update_listing_state(
            "shop1", "listing1", "active", api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result == {"listing_id": "listing1", "state": "active", "_dry_run": True}


def test_update_listing_state_sends_patch_with_state_body_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"listing_id": 999, "state": "active"}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.update_listing_state(
            "shop1", "listing1", "active",
            api_key="key1", api_secret="secret1", access_token="token1", dry_run=False,
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings/listing1"
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"state": "active"}
    assert result == {"listing_id": 999, "state": "active"}


def test_update_listing_patches_full_field_set():
    listing_data = {
        "title": "Monstera Line Art", "description": "desc", "tags": ["a", "b"],
        "taxonomy_id": 1027, "who_made": "i_did", "when_made": "made_to_order",
        "is_supply": False, "shop_section_id": 59380312, "production_partner_ids": [5717252],
    }
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"listing_id": 555, **listing_data}
        result = etsy_client.update_listing(
            "shop1", "555", listing_data, api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "PATCH"
    assert sent_request.full_url == "https://openapi.etsy.com/v3/application/shops/shop1/listings/555"
    body = json.loads(sent_request.data)
    assert body == listing_data
    assert result["listing_id"] == 555


def test_update_listing_dry_run_does_not_call_http():
    with patch("pipeline.http.send") as mock_send:
        result = etsy_client.update_listing("shop1", "555", {"title": "x"}, dry_run=True)
    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_get_listing_inventory_sends_get():
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"products": []}
        etsy_client.get_listing_inventory("shop1", "555", api_key="k", api_secret="s",
                                           access_token="t", dry_run=False)
    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "GET"
    assert sent_request.full_url == "https://openapi.etsy.com/v3/application/listings/555/inventory"


def test_update_listing_inventory_sets_price_on_matching_size_and_strips_readonly_fields():
    inventory = {
        "products": [
            {
                "product_id": 1, "sku": "", "is_deleted": False,
                "property_values": [{"property_id": 100, "property_name": "Size",
                                      "value_ids": [1], "scale_id": None, "scale_name": None,
                                      "values": ["8x12"]}],
                "offerings": [{"offering_id": 10, "price": {"amount": 2000, "divisor": 100, "currency_code": "EUR"},
                               "quantity": 999, "is_enabled": True}],
            },
            {
                "product_id": 2, "sku": "", "is_deleted": False,
                "property_values": [{"property_id": 100, "property_name": "Size",
                                      "value_ids": [2], "scale_id": None, "scale_name": None,
                                      "values": ["A3"]}],
                "offerings": [{"offering_id": 11, "price": {"amount": 3000, "divisor": 100, "currency_code": "EUR"},
                               "quantity": 999, "is_enabled": True}],
            },
        ]
    }
    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get, \
         patch("pipeline.http.send") as mock_send:
        mock_get.return_value = inventory
        mock_send.return_value = {"products": []}
        etsy_client.update_listing_inventory(
            "shop1", "555", {"8x12": 24.0, "A3": 35.0},
            api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    assert sent_request.method == "PUT"
    body = json.loads(sent_request.data)
    prices = {p["property_values"][0]["values"][0]: p["offerings"][0]["price"] for p in body["products"]}
    assert prices["8x12"] == 24.0
    assert prices["A3"] == 35.0
    assert "product_id" not in body["products"][0]
    assert "is_deleted" not in body["products"][0]
    assert "offering_id" not in body["products"][0]["offerings"][0]


def test_update_listing_inventory_matches_single_size_product_with_no_variation_property():
    # A single-size group (5x7, 10x24) has no Etsy variation property at all - Gelato only
    # creates one when there's more than one size - so property_values comes back empty.
    inventory = {"products": [{"product_id": 1, "sku": "", "is_deleted": False,
                                "property_values": [],
                                "offerings": [{"offering_id": 10,
                                               "price": {"amount": 1900, "divisor": 100, "currency_code": "EUR"},
                                               "quantity": 999, "is_enabled": True}]}]}
    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get, \
         patch("pipeline.http.send") as mock_send:
        mock_get.return_value = inventory
        mock_send.return_value = {"products": []}
        etsy_client.update_listing_inventory(
            "shop1", "555", {"5x7": 19.0}, api_key="k", api_secret="s", access_token="t", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    body = json.loads(sent_request.data)
    assert body["products"][0]["offerings"][0]["price"] == 19.0


# --- GL-15: 401 auto-refresh + retry ---

def test_update_listing_retries_once_with_new_token_after_a_401():
    calls = []

    def fake_send(request, timeout=30):
        calls.append(request.get_header("Authorization"))
        if len(calls) == 1:
            raise http.HTTPError(401, "expired token")
        return {"listing_id": 555}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send), \
         patch("pipeline.etsy_client.etsy_auth.refresh", return_value={"access_token": "fresh-token"}) as mock_refresh:
        result = etsy_client.update_listing(
            "shop1", "555", {"title": "x"}, api_key="k", api_secret="s",
            access_token="stale-token", dry_run=False,
        )

    mock_refresh.assert_called_once()
    assert calls == ["Bearer stale-token", "Bearer fresh-token"]
    assert result == {"listing_id": 555}


def test_update_listing_does_not_loop_on_a_second_401_after_refresh():
    with patch("pipeline.etsy_client.http.send", side_effect=http.HTTPError(401, "still expired")), \
         patch("pipeline.etsy_client.etsy_auth.refresh", return_value={"access_token": "fresh-token"}) as mock_refresh:
        with pytest.raises(http.HTTPError):
            etsy_client.update_listing(
                "shop1", "555", {"title": "x"}, api_key="k", api_secret="s",
                access_token="stale-token", dry_run=False,
            )

    mock_refresh.assert_called_once()  # exactly one refresh attempt, no retry loop


def test_non_401_error_is_not_treated_as_an_expired_token():
    with patch("pipeline.etsy_client.http.send", side_effect=http.HTTPError(500, "server error")), \
         patch("pipeline.etsy_client.etsy_auth.refresh") as mock_refresh:
        with pytest.raises(http.HTTPError):
            etsy_client.update_listing(
                "shop1", "555", {"title": "x"}, api_key="k", api_secret="s",
                access_token="token", dry_run=False,
            )

    mock_refresh.assert_not_called()


def test_no_urllib_urlopen_remains_in_pipeline():
    pipeline_dir = pathlib.Path(etsy_client.__file__).resolve().parent
    offenders = [
        str(py) for py in pipeline_dir.glob("*.py")
        if "urllib.request.urlopen" in py.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"raw urlopen resurfaced in pipeline/: {offenders}"


def test_update_listing_inventory_raises_if_a_size_has_no_matching_product():
    inventory = {"products": [{"product_id": 1, "sku": "", "is_deleted": False,
                                "property_values": [{"property_id": 100, "property_name": "Size",
                                                      "value_ids": [1], "scale_id": None, "scale_name": None,
                                                      "values": ["8x12"]}],
                                "offerings": [{"offering_id": 10,
                                               "price": {"amount": 2000, "divisor": 100, "currency_code": "EUR"},
                                               "quantity": 999, "is_enabled": True}]}]}
    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get:
        mock_get.return_value = inventory
        with pytest.raises(ValueError, match="A1"):
            etsy_client.update_listing_inventory("shop1", "555", {"8x12": 24.0, "A1": 49.0}, dry_run=False)
