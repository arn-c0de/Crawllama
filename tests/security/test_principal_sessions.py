"""API clients get their own conversation session (1.4.12)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from api import runtime
from api.sessions import PrincipalSessions
from app import API_KEY, _grant_bootstrap_admin_role, app
from core.agent.session import SessionManager
from core.api_key_manager import get_api_key_manager


class RecordingAgent:
    """Minimal agent: remembers each query in whatever session is active."""

    def __init__(self, tmp_path):
        self.session = SessionManager(session_file=tmp_path / "default.json")

    def query(self, user_query, use_tools=True):
        self.session.record_history(user_query, f"answer to {user_query}", context_limit=1000)
        return f"seen: {[e['query'] for e in self.session.conversation_history]}"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_api_key_manager(), "storage_file", tmp_path / "api_keys.json")
    monkeypatch.setattr(runtime, "agent", RecordingAgent(tmp_path))
    monkeypatch.setattr(runtime, "sessions", PrincipalSessions(base_dir=tmp_path / "sessions"))
    _grant_bootstrap_admin_role()
    return TestClient(app)


def _issue_key(client: TestClient, owner: str) -> str:
    headers = {"X-API-Key": API_KEY, "Origin": "http://localhost:3000"}
    token = client.post("/csrf-token", headers=headers).json()["csrf_token"]
    response = client.post(
        "/admin/api-keys/generate", headers={**headers, "X-CSRF-Token": token}, json={"user_id": owner}
    )
    return response.json()["api_key"]


def _ask(client: TestClient, api_key: str, query: str) -> str:
    response = client.post(
        "/query", headers={"X-API-Key": api_key, "Origin": "http://localhost:3000"}, json={"query": query}
    )
    assert response.status_code == 200, response.text
    return response.json()["answer"]


def test_clients_do_not_share_conversation(client):
    alice = _issue_key(client, f"alice-{uuid.uuid4().hex}")
    bob = _issue_key(client, f"bob-{uuid.uuid4().hex}")

    _ask(client, alice, "alice secret question")
    answer = _ask(client, bob, "bob question")

    assert "alice secret question" not in answer
    assert "alice secret question" in _ask(client, alice, "follow up")


def test_default_session_is_restored_after_request(client):
    default_session = runtime.agent.session
    _ask(client, API_KEY, "hello")
    assert runtime.agent.session is default_session
    assert default_session.conversation_history == []
