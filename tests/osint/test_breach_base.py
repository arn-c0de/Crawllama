
from core.osint.sources.base import BreachResult, BreachSource, SourceType
from core.osint.sources.manager import BreachManager


class MockSource(BreachSource):
    name = "mock"
    source_type = SourceType.API_FREE

    def __init__(self, results=None, raise_error=False):
        super().__init__()
        self._results = results or []
        self._raise = raise_error

    def _query(self, email: str):
        if self._raise:
            raise RuntimeError("boom")
        return self._results


def test_breach_result_to_dict():
    result = BreachResult(
        name="Example",
        title="Example Breach",
        breach_date="2020-01-01",
        description="Test",
        data_classes=["Email addresses"],
        is_verified=True,
        is_sensitive=False,
        source="TestSource"
    )
    data = result.to_dict()
    assert data["Name"] == "Example"
    assert data["Title"] == "Example Breach"
    assert data["BreachDate"] == "2020-01-01"
    assert data["Source"] == "TestSource"


def test_breach_manager_register_query_dedup():
    class MockSourceA(MockSource):
        name = "mock_a"

    class MockSourceB(MockSource):
        name = "mock_b"

    r1 = BreachResult(
        name="A",
        title="A",
        breach_date="2020-01-01",
        description="x",
        data_classes=["Email"],
        is_verified=True,
        is_sensitive=True,
        source="S"
    )
    r2 = BreachResult(
        name="A",
        title="A",
        breach_date="2020-01-01",
        description="x",
        data_classes=["Email"],
        is_verified=True,
        is_sensitive=True,
        source="S"
    )
    manager = BreachManager(config={"osint": {"breach_sources": {}}})
    manager.register_source(MockSourceA(results=[r1]))
    manager.register_source(MockSourceB(results=[r2]))
    results = manager.query_all("test@example.com")
    assert results["breach_count"] == 1


def test_breach_manager_disabled_source():
    manager = BreachManager(config={"osint": {"breach_sources": {"mock": {"enabled": False}}}})
    manager.register_source(MockSource())
    results = manager.query_all("test@example.com")
    assert results["breach_count"] == 0
    assert results["sources_queried"] == []


def test_breach_manager_failure_isolated():
    class BadSource(MockSource):
        name = "bad"

        def query(self, email: str):
            raise RuntimeError("boom")

    manager = BreachManager(config={"osint": {"breach_sources": {}}})
    manager.register_source(BadSource())
    results = manager.query_all("test@example.com")
    assert results["breach_count"] == 0
    assert "bad" in results["sources_failed"]


def test_breach_manager_priority_ordering():
    class MockA(MockSource):
        name = "a"

    class MockB(MockSource):
        name = "b"

    config = {"osint": {"breach_sources": {"a": {"priority": 2}, "b": {"priority": 1}}}}
    manager = BreachManager(config=config)
    manager.register_source(MockA())
    manager.register_source(MockB())
    sources = [s.name for s in manager.get_enabled_sources()]
    assert sources == ["b", "a"]
