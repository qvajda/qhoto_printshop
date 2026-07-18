import json
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.gelato_client as gelato_client


def test_get_template_builds_correct_request():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["api_key_header"] = request.get_header("X-api-key")
        return {"id": "tpl_abc", "variants": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.get_template("tpl_abc", api_key="key1")

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/templates/tpl_abc"
    assert captured["method"] == "GET"
    assert captured["api_key_header"] == "key1"
    assert result == {"id": "tpl_abc", "variants": []}


def test_get_product_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://ecommerce.gelatoapis.com/v1/stores/store1/products/prod1"
        assert request.get_method() == "GET"
        return {"id": "prod1", "productImages": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.get_product("prod1", store_id="store1", api_key="key1")

    assert result == {"id": "prod1", "productImages": []}


def test_create_product_from_template_dry_run_makes_no_network_call():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        result = gelato_client.create_product_from_template(
            "tpl_real",
            [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
            "Botanical print", store_id="store1", api_key="key1", dry_run=True,
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True
    assert result["title"] == "Botanical print"


def test_create_product_from_template_raises_on_placeholder_template_id_when_live():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        with pytest.raises(gelato_client.GelatoPlaceholderTemplateError, match="template_id"):
            gelato_client.create_product_from_template(
                "PLACEHOLDER_8x12_PORTRAIT",
                [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
                "Botanical print",
                store_id="store1", api_key="key1", dry_run=False,
            )

    mock_send.assert_not_called()


def test_create_product_from_template_raises_on_placeholder_variant_id_when_live():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        with pytest.raises(gelato_client.GelatoPlaceholderTemplateError, match="template_variant_id"):
            gelato_client.create_product_from_template(
                "tpl_real",
                [{"template_variant_id": "PLACEHOLDER_8x12_PORTRAIT_VARIANT", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
                "Botanical print",
                store_id="store1", api_key="key1", dry_run=False,
            )

    mock_send.assert_not_called()


def test_create_product_from_template_sends_correct_request_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return {"id": "prod_new", "status": "created", "previewUrl": None, "productImages": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.create_product_from_template(
            "tpl_real_123",
            [{"template_variant_id": "variant_real_456", "image_placeholder_name": "011_mt_sunday_brook.JPG", "image_url": "https://img.example/x.png"}],
            "Botanical print",
            store_id="store1", api_key="key1", dry_run=False,
        )

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/stores/store1/products:create-from-template"
    assert captured["body"]["templateId"] == "tpl_real_123"
    assert captured["body"]["title"] == "Botanical print"
    assert captured["body"]["isVisibleInTheOnlineStore"] is False
    assert captured["body"]["variants"] == [{
        "templateVariantId": "variant_real_456",
        "imagePlaceholders": [{"name": "011_mt_sunday_brook.JPG", "fileUrl": "https://img.example/x.png"}],
    }]
    assert result["id"] == "prod_new"


def test_create_product_from_template_builds_one_variant_entry_per_size():
    variants = [
        {"template_variant_id": "var-8x12", "image_placeholder_name": "ph1", "image_url": "https://x/a.png"},
        {"template_variant_id": "var-a3", "image_placeholder_name": "ph1", "image_url": "https://x/a.png"},
    ]
    with patch("pipeline.http.send") as mock_send:
        mock_send.return_value = {"id": "prod123"}
        gelato_client.create_product_from_template(
            "tmpl1", variants, "Test Title", store_id="store1", api_key="key1", dry_run=False,
        )

    sent_request = mock_send.call_args[0][0]
    body = json.loads(sent_request.data)
    assert len(body["variants"]) == 2
    assert body["variants"][0]["templateVariantId"] == "var-8x12"
    assert body["variants"][1]["templateVariantId"] == "var-a3"
    assert body["variants"][0]["imagePlaceholders"] == [{"name": "ph1", "fileUrl": "https://x/a.png"}]


def test_create_product_from_template_dry_run_ignores_variant_count():
    result = gelato_client.create_product_from_template(
        "tmpl1", [{"template_variant_id": "v1", "image_placeholder_name": "ph1", "image_url": "u1"}],
        "Test Title", dry_run=True,
    )
    assert result["_dry_run"] is True


def test_create_product_from_template_refuses_placeholder_in_any_variant():
    variants = [
        {"template_variant_id": "REAL_VAR", "image_placeholder_name": "ph1", "image_url": "u1"},
        {"template_variant_id": "PLACEHOLDER_VAR", "image_placeholder_name": "ph1", "image_url": "u1"},
    ]
    with pytest.raises(gelato_client.GelatoPlaceholderTemplateError):
        gelato_client.create_product_from_template("tmpl1", variants, "Test Title", dry_run=False)


def test_create_product_from_template_raises_on_replicate_delivery_url_when_live():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        with pytest.raises(gelato_client.GelatoReplicateURLError, match="replicate.delivery"):
            gelato_client.create_product_from_template(
                "tpl_real",
                [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://replicate.delivery/xyz/out.png"}],
                "Botanical print",
                store_id="store1", api_key="key1", dry_run=False,
            )

    mock_send.assert_not_called()


def test_create_product_from_template_dry_run_ignores_replicate_delivery_url():
    result = gelato_client.create_product_from_template(
        "tpl_real",
        [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://replicate.delivery/xyz/out.png"}],
        "Botanical print", store_id="store1", api_key="key1", dry_run=True,
    )
    assert result["_dry_run"] is True


def test_create_product_from_template_allows_durable_url_when_live():
    def fake_send(request, timeout=30):
        return {"id": "prod_new", "status": "created", "previewUrl": None, "productImages": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send) as mock_send:
        result = gelato_client.create_product_from_template(
            "tpl_real",
            [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://pub-abc123.r2.dev/artwork/xyz.png"}],
            "Botanical print",
            store_id="store1", api_key="key1", dry_run=False,
        )

    mock_send.assert_called_once()
    assert result["id"] == "prod_new"


def test_get_etsy_listing_id_returns_external_id_when_present():
    with patch("pipeline.gelato_client.get_product") as mock_get:
        mock_get.return_value = {"id": "prod123", "externalId": "etsy-listing-999"}
        result = gelato_client.get_etsy_listing_id("prod123", store_id="store1", api_key="key1")
    assert result == "etsy-listing-999"


def test_get_etsy_listing_id_returns_none_when_not_yet_synced():
    with patch("pipeline.gelato_client.get_product") as mock_get:
        mock_get.return_value = {"id": "prod123", "externalId": None}
        result = gelato_client.get_etsy_listing_id("prod123")
    assert result is None


def test_delete_product_dry_run_makes_no_network_call():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        gelato_client.delete_product("prod1", store_id="store1", api_key="key1", dry_run=True)

    mock_send.assert_not_called()


def test_delete_product_sends_delete_request_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return {}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        gelato_client.delete_product("prod1", store_id="store1", api_key="key1", dry_run=False)

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/stores/store1/products/prod1"
    assert captured["method"] == "DELETE"


def test_dry_run_defaults_from_live_mode_env_var(monkeypatch):
    monkeypatch.delenv("GELATO_LIVE_MODE", raising=False)

    with patch("pipeline.gelato_client.http.send") as mock_send:
        result = gelato_client.create_product_from_template(
            "tpl_real",
            [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
            "Botanical print", store_id="store1", api_key="key1",
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_dry_run_false_when_live_mode_env_var_is_true(monkeypatch):
    monkeypatch.setenv("GELATO_LIVE_MODE", "true")

    def fake_send(request, timeout=30):
        return {"id": "prod_x", "status": "created"}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send) as mock_send:
        gelato_client.create_product_from_template(
            "tpl_real",
            [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
            "Botanical print", store_id="store1", api_key="key1",
        )

    mock_send.assert_called_once()


def test_missing_store_id_raises_when_live_and_not_provided(monkeypatch):
    monkeypatch.delenv("GELATO_STORE_ID", raising=False)

    with pytest.raises(config.MissingConfigError):
        gelato_client.create_product_from_template(
            "tpl_real",
            [{"template_variant_id": "variant_real", "image_placeholder_name": "image_slot_real.jpg", "image_url": "https://img.example/x.png"}],
            "Botanical print", api_key="key1", dry_run=False,
        )
