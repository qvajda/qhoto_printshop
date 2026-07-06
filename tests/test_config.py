import json
import os

import pytest

import pipeline.config as config


def test_parse_env_file_parses_key_value_pairs(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "FOO=bar\n"
        "\n"
        "BAZ=qux\n"
    )

    result = config.parse_env_file(env_file)

    assert result == {"FOO": "bar", "BAZ": "qux"}


def test_load_env_sets_os_environ_without_overwriting_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("QHOTO_TEST_VAR", raising=False)
    monkeypatch.setenv("QHOTO_TEST_VAR_EXISTING", "already_set")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "QHOTO_TEST_VAR=from_file\n"
        "QHOTO_TEST_VAR_EXISTING=from_file\n"
    )

    config.load_env(env_file)

    assert os.environ["QHOTO_TEST_VAR"] == "from_file"
    assert os.environ["QHOTO_TEST_VAR_EXISTING"] == "already_set"


def test_require_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("QHOTO_MISSING_VAR", raising=False)

    with pytest.raises(config.MissingConfigError):
        config.require_env("QHOTO_MISSING_VAR")


def test_require_env_returns_value_when_present(monkeypatch):
    monkeypatch.setenv("QHOTO_PRESENT_VAR", "hello")

    assert config.require_env("QHOTO_PRESENT_VAR") == "hello"


def test_load_static_config_reads_json(tmp_path):
    static_path = tmp_path / "static_config.json"
    static_path.write_text(json.dumps({
        "gelato_templates": {"8x12_portrait": "PLACEHOLDER_8x12_PORTRAIT"},
        "primary_size": "8x12",
    }))

    result = config.load_static_config(static_path)

    assert result["primary_size"] == "8x12"


def test_is_placeholder_detects_placeholder_ids():
    assert config.is_placeholder("PLACEHOLDER_8x12_PORTRAIT") is True
    assert config.is_placeholder("tpl_real_abc123") is False


def test_get_template_id_returns_configured_value():
    static_config = {"gelato_templates": {"8x12_portrait": "tpl_real_abc123"}}

    result = config.get_template_id(static_config, "8x12", "portrait")

    assert result == "tpl_real_abc123"


def test_get_template_id_raises_on_unknown_size_orientation():
    static_config = {"gelato_templates": {"8x12_portrait": "tpl_real_abc123"}}

    with pytest.raises(KeyError):
        config.get_template_id(static_config, "5x7", "landscape")


def test_repo_static_config_has_all_twelve_template_slots():
    static_config = config.load_static_config()

    sizes = ["5x7", "8x12", "A3", "A2", "10x24", "A1"]
    for size in sizes:
        for orientation in ("portrait", "landscape"):
            key = f"{size}_{orientation}"
            assert key in static_config["gelato_templates"]
