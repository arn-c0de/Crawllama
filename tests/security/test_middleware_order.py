"""Rejections from inner middleware are still audited and get security headers."""
import pytest
from fastapi.testclient import TestClient

from app import API_KEY, _grant_bootstrap_admin_role, app


@pytest.fixture
def client():
    _grant_bootstrap_admin_role()
    return TestClient(app)


def test_csrf_rejection_carries_security_headers(client):
    response = client.post(
        "/cache/clear",
        headers={"X-API-Key": API_KEY, "Origin": "http://evil.example"},
    )
    assert response.status_code == 403
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_csrf_rejection_is_audited(client, monkeypatch):
    import app as app_module

    logged = []
    monkeypatch.setattr(app_module.audit_logger, "log_api_request", lambda **kw: logged.append(kw))
    client.post("/cache/clear", headers={"X-API-Key": API_KEY, "Origin": "http://evil.example"})
    assert any(entry["endpoint"] == "/cache/clear" and entry["status_code"] == 403 for entry in logged)
