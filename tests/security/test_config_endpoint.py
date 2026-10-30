"""PATCH /config writes through api.runtime and refuses unsafe updates."""
import json

import pytest
from fastapi.testclient import TestClient

from api import runtime
from app import API_KEY, _grant_bootstrap_admin_role, app
from core.api_key_manager import get_api_key_manager

HEADERS = {"X-API-Key": API_KEY, "Origin": "http://localhost:3000"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(get_api_key_manager(), "storage_file", tmp_path / "api_keys.json")
    monkeypatch.setattr(runtime, "config", {"search": {"region": "de-de", "max_results": 10}})
    monkeypatch.setattr(runtime, "config_loaded_from_file", True)
    _grant_bootstrap_admin_role()
    return TestClient(app)


def _patch(client, body):
    token = client.post("/csrf-token", headers=HEADERS).json()["csrf_token"]
    return client.patch("/config", headers={**HEADERS, "X-CSRF-Token": token}, json=body)


def test_patch_config_updates_file_and_live_config(client, tmp_path):
    response = _patch(client, {"category": "search", "key": "region", "value": "ü-region"})
    assert response.status_code == 200, response.text
    assert runtime.config["search"]["region"] == "ü-region"
    written = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert json.loads(written)["search"]["region"] == "ü-region"
    assert "ü-region" in written  # UTF-8, not ASCII-escaped


def test_patch_config_rejects_wrong_type(client, tmp_path):
    response = _patch(client, {"category": "search", "key": "max_results", "value": "many"})
    assert response.status_code == 400
    assert not (tmp_path / "config.json").exists()


def test_patch_config_refuses_fallback_config(client, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "config_loaded_from_file", False)
    response = _patch(client, {"category": "search", "key": "region", "value": "x"})
    assert response.status_code == 409
    assert not (tmp_path / "config.json").exists()
