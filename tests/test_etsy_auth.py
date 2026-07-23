import json
import os
from unittest.mock import patch

import pipeline.etsy_auth as etsy_auth


def _env_text(access="old-access", refresh="old-refresh"):
    return f"ETSY_API_KEY=client1\nETSY_ACCESS_TOKEN={access}\nETSY_REFRESH_TOKEN={refresh}\n"


def test_refresh_sends_refresh_token_grant_and_returns_new_access_token(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(_env_text())

    def fake_send(request, timeout=30):
        assert request.full_url == etsy_auth.TOKEN_URL
        body = json.loads(request.data)
        assert body == {"grant_type": "refresh_token", "client_id": "client1", "refresh_token": "old-refresh"}
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}

    with patch("pipeline.etsy_auth.http.send", side_effect=fake_send):
        result = etsy_auth.refresh(client_id="client1", refresh_token="old-refresh", env_path=env_path)

    assert result["access_token"] == "new-access"
    assert result["refresh_token"] == "new-refresh"
    assert result["rotated"] is True
    assert result["expires_in"] == 3600


def test_refresh_persists_rotated_refresh_token_to_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(_env_text())
    monkeypatch.delenv("ETSY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ETSY_REFRESH_TOKEN", raising=False)

    with patch("pipeline.etsy_auth.http.send", return_value={"access_token": "new-access", "refresh_token": "new-refresh"}):
        etsy_auth.refresh(client_id="client1", refresh_token="old-refresh", env_path=env_path)

    text = env_path.read_text()
    assert "ETSY_ACCESS_TOKEN=new-access" in text
    assert "ETSY_REFRESH_TOKEN=new-refresh" in text
    assert os.environ["ETSY_ACCESS_TOKEN"] == "new-access"
    assert os.environ["ETSY_REFRESH_TOKEN"] == "new-refresh"


def test_refresh_keeps_old_refresh_token_when_etsy_does_not_rotate_it(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(_env_text())

    with patch("pipeline.etsy_auth.http.send", return_value={"access_token": "new-access"}):
        result = etsy_auth.refresh(client_id="client1", refresh_token="old-refresh", env_path=env_path)

    assert result["refresh_token"] == "old-refresh"
    assert result["rotated"] is False
    assert "ETSY_REFRESH_TOKEN=old-refresh" in env_path.read_text()
