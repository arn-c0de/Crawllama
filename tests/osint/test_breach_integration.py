from core.osint.email_intel import EmailIntelligence
from core.osint.sources.base import BreachSource, BreachResult, SourceType
from core.osint.sources.manager import BreachManager


class MockSource(BreachSource):
    name = "mock"
    source_type = SourceType.API_FREE

    def _query(self, email: str):
        return [
            BreachResult(
                name="Example",
                title="Example",
                breach_date="2020-01-01",
                description="Test",
                data_classes=["Email addresses"],
                is_verified=True,
                is_sensitive=True,
                source="Mock"
            )
        ]


def test_email_intel_check_data_breaches(monkeypatch):
    manager = BreachManager(config={"osint": {"breach_sources": {}}})
    manager.register_source(MockSource())

    import core.osint.sources
    monkeypatch.setattr(core.osint.sources, "create_default_manager", lambda config=None: manager)

    intel = EmailIntelligence()
    result = intel.check_data_breaches("test@example.com")
    assert result["breach_count"] == 1
    assert result["pwned"] is True
    assert result["breaches"]
