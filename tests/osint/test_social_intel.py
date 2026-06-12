"""Tests for SocialIntelligence networking behavior (robots.txt caching)."""
import time

from core.osint.social_intel import SocialIntelligence

ROBOTS_BODY = "User-agent: *\nDisallow: /private/\n"


class _FakeResponse:
    def __init__(self, status: int, body: str):
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    """Counts robots.txt fetches; returns a canned response."""

    def __init__(self, status: int = 200, body: str = ROBOTS_BODY, error: Exception | None = None):
        self.status = status
        self.body = body
        self.error = error
        self.calls = 0

    def get(self, url: str, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _FakeResponse(self.status, self.body)


class TestRobotsCache:
    async def test_robots_txt_fetched_once_per_host(self):
        intel = SocialIntelligence()
        session = _FakeSession()

        assert await intel._check_robots_permission(session, "https://example.com/alice") is True
        assert await intel._check_robots_permission(session, "https://example.com/bob") is True
        assert session.calls == 1

    async def test_robots_txt_disallow_is_enforced_from_cache(self):
        intel = SocialIntelligence()
        session = _FakeSession()

        assert await intel._check_robots_permission(session, "https://example.com/private/x") is False
        assert await intel._check_robots_permission(session, "https://example.com/private/y") is False
        assert session.calls == 1

    async def test_fetch_failure_is_cached_and_allows(self):
        intel = SocialIntelligence()
        session = _FakeSession(error=ConnectionError("unreachable"))

        assert await intel._check_robots_permission(session, "https://down.example/alice") is True
        assert await intel._check_robots_permission(session, "https://down.example/bob") is True
        assert session.calls == 1

    async def test_cache_expires_after_ttl(self):
        intel = SocialIntelligence()
        intel._robots_cache_ttl = 0.01
        session = _FakeSession()

        await intel._check_robots_permission(session, "https://example.com/alice")
        time.sleep(0.02)
        await intel._check_robots_permission(session, "https://example.com/bob")
        assert session.calls == 2

    async def test_separate_hosts_fetch_separately(self):
        intel = SocialIntelligence()
        session = _FakeSession()

        await intel._check_robots_permission(session, "https://a.example/alice")
        await intel._check_robots_permission(session, "https://b.example/alice")
        assert session.calls == 2
