"""Managed API keys act for the principal they were issued to (1.4.12)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import API_KEY, _grant_bootstrap_admin_role, app
from core.api_key_manager import get_api_key_manager

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Keep issued keys out of the real key store
    monkeypatch.setattr(get_api_key_manager(), "storage_file", tmp_path / "api_keys.json")
    _grant_bootstrap_admin_role()
    return TestClient(app)


def _csrf_headers(client: TestClient, api_key: str) -> dict:
    headers = {"X-API-Key": api_key, **ORIGIN}
    token = client.post("/csrf-token", headers=headers).json()["csrf_token"]
    return {**headers, "X-CSRF-Token": token}


def test_managed_key_lists_and_revokes_its_owners_keys(client):
    owner = f"user-{uuid.uuid4().hex}"
    admin = _csrf_headers(client, API_KEY)
    issued = client.post("/admin/api-keys/generate", headers=admin, json={"user_id": owner})
    assert issued.status_code == 200
    managed_key, key_id = issued.json()["api_key"], issued.json()["key_id"]

    managed = _csrf_headers(client, managed_key)

    listed = client.get("/admin/api-keys/list", headers=managed).json()
    assert listed["total_keys"] == 1
    assert listed["keys"][0]["key_id"] == key_id

    revoked = client.delete(f"/admin/api-keys/revoke/{key_id}", headers=managed)
    assert revoked.status_code == 200


def test_role_assigned_via_key_applies_to_owner(client):
    owner = f"user-{uuid.uuid4().hex}"
    admin = _csrf_headers(client, API_KEY)
    managed_key = client.post(
        "/admin/api-keys/generate", headers=admin, json={"user_id": owner}
    ).json()["api_key"]

    assert client.get("/admin/roles/me", headers={"X-API-Key": managed_key}).json()["role"] == "read_only"

    assigned = client.post(
        "/admin/roles/assign", headers=admin,
        json={"api_key_to_manage": managed_key, "role": "user"},
    )
    assert assigned.status_code == 200
    assert client.get("/admin/roles/me", headers={"X-API-Key": managed_key}).json()["role"] == "user"

