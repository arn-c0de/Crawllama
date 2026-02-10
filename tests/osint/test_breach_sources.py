import time
import importlib

import pytest

from core.osint.sources.hibp_source import HIBPBreachSource
from core.osint.sources.leakcheck_source import LeakCheckBreachSource
from core.osint.sources.intelx_source import IntelXBreachSource
from core.osint.sources.dehashed_source import DeHashedBreachSource
from core.osint.sources.snusbase_source import SnusbaseBreachSource
from core.osint.sources.local_db_source import LocalDBBreachSource


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


def test_hibp_source_with_key(monkeypatch):
    monkeypatch.setenv("HIBP_API_KEY", "test")
    source = HIBPBreachSource()

    responses = iter([
        MockResponse(200, json_data=[{
            "Name": "Example",
            "Title": "Example",
            "BreachDate": "2020-01-01",
            "Description": "Test",
            "DataClasses": ["Email addresses"],
            "IsVerified": True,
            "IsSensitive": True
        }]),
        MockResponse(200, json_data=[{"Source": "paste"}])
    ])

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    results = source.query("test@example.com")
    assert len(results) == 1
    assert source.last_paste_count == 1


def test_hibp_source_no_key(monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    source = HIBPBreachSource()
    assert not source.is_configured()


def test_leakcheck_public(monkeypatch):
    source = LeakCheckBreachSource()
    data = {
        "success": True,
        "found": 1,
        "sources": [{"name": "Example", "date": "2020-01-01"}],
        "fields": ["Email addresses", "Passwords"]
    }

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse(200, json_data=data))
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    results = source.query("test@example.com")
    assert results
    assert results[0].name == "Example"


def test_leakcheck_rate_limit(monkeypatch):
    source = LeakCheckBreachSource()
    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse(429))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    results = source.query("test@example.com")
    assert results == []


def test_intelx_public(monkeypatch):
    source = IntelXBreachSource()
    data = {"selectors": ["a", "b"]}
    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse(200, json_data=data))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    results = source.query("test@example.com")
    assert len(results) == 1


def test_dehashed_api(monkeypatch):
    monkeypatch.setenv("DEHASHED_API_KEY", "key")
    monkeypatch.setenv("DEHASHED_USERNAME", "user")
    source = DeHashedBreachSource()
    data = {"entries": [{"database_name": "Example", "date": "2020-01-01"}]}

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse(200, json_data=data))
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    results = source.query("test@example.com")
    assert results
    assert results[0].name == "Example"


def test_dehashed_free_scrape(monkeypatch):
    try:
        importlib.import_module("bs4")
    except Exception:
        pytest.skip("bs4 not installed")

    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    monkeypatch.delenv("DEHASHED_USERNAME", raising=False)
    source = DeHashedBreachSource()

    html = "1 results found"
    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse(200, text=html))
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    results = source.query("test@example.com")
    assert results


def test_snusbase_source(monkeypatch):
    monkeypatch.setenv("SNUSBASE_API_KEY", "key")
    source = SnusbaseBreachSource()

    data = {"results": {"email": [{"source": "ExampleSource"}]}}

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockResponse(200, json_data=data))
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    results = source.query("test@example.com")
    assert results
    assert results[0].name == "ExampleSource"


def test_local_db_source_scan(monkeypatch, tmp_path):
    breach_dir = tmp_path / "data" / "breaches"
    breach_dir.mkdir(parents=True)
    sample = breach_dir / "sample.txt"
    sample.write_text("user@example.com:password\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    source = LocalDBBreachSource()
    results = source.query("user@example.com")
    assert results
    assert results[0].source == "LocalDB"
