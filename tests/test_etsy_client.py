import json
from unittest.mock import patch

import pytest

import pipeline.etsy_client as etsy_client


def test_get_seller_taxonomy_nodes_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://openapi.etsy.com/v3/application/seller-taxonomy/nodes"
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1"
        assert request.get_header("Authorization") == "Bearer token1"
        return {"count": 2, "results": [{"id": 1}, {"id": 2}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.get_seller_taxonomy_nodes(api_key="key1", access_token="token1")

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
            "shop1", listing_data, api_key="key1", access_token="token1", dry_run=False
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
            "shop1", "listing1", b"fake-image-bytes", api_key="key1", access_token="token1", dry_run=False
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
        etsy_client.create_draft_listing("shop1", {"title": "x"}, api_key="key1", access_token="token1")

    mock_send.assert_called_once()
