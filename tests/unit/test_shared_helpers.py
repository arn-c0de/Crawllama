"""Tests for small helpers extracted during deduplication."""
import json
from pathlib import Path

import pytest

from core.hallu.result import HallucinationResult
from core.health.component_checker import ComponentHealthChecker, HealthStatus
from core.osint._common import ip_api_geolocation
from utils.file_utils import write_json_atomic


def test_write_json_atomic_writes_utf8_and_leaves_no_tmp(tmp_path: Path):
    target = tmp_path / "data.json"
    write_json_atomic(target, {"name": "Müller"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"name": "Müller"}
    assert "Müller" in target.read_text(encoding="utf-8")  # ensure_ascii=False
    assert list(tmp_path.iterdir()) == [target]


def test_write_json_atomic_keeps_old_file_on_serialization_error(tmp_path: Path):
    target = tmp_path / "data.json"
    write_json_atomic(target, {"ok": 1})
    with pytest.raises(TypeError):
        write_json_atomic(target, {"bad": object()})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": 1}
    assert list(tmp_path.iterdir()) == [target]


def test_ip_api_geolocation_maps_fields_and_custom_keys():
    data = {"country": "Germany", "countryCode": "DE", "regionName": "Berlin",
            "city": "Berlin", "lat": 52.5, "lon": 13.4, "timezone": "Europe/Berlin",
            "isp": "ISP", "org": "Org", "as": "AS123"}
    geo = ip_api_geolocation(data)
    assert geo["country_code"] == "DE" and geo["region"] == "Berlin"
    assert geo["org"] == "Org" and geo["as"] == "AS123"

    geo = ip_api_geolocation(data, org_key="organization", as_key="as_number")
    assert geo["organization"] == "Org" and geo["as_number"] == "AS123"
    assert "org" not in geo and "as" not in geo


def test_hallucination_result_disabled():
    result = HallucinationResult.disabled()
    assert result.risk_level == "disabled"
    assert result.is_hallucination is False
    assert result.context_alignment == 1.0


def test_run_check_turns_exceptions_into_unhealthy():
    def boom():
        raise RuntimeError("down")

    health = ComponentHealthChecker._run_check("X", boom)
    assert health.status is HealthStatus.UNHEALTHY
    assert health.message == "Error: down"
    assert health.details is None and health.response_time_ms >= 0

    health = ComponentHealthChecker._run_check(
        "Y", lambda: (HealthStatus.HEALTHY, "fine", {"k": 1})
    )
    assert (health.name, health.status, health.details) == ("Y", HealthStatus.HEALTHY, {"k": 1})


def test_probe_config_supports_flat_and_nested(tmp_path: Path):
    checker = ComponentHealthChecker(tmp_path)
    assert checker._probe_config()[0] is HealthStatus.UNHEALTHY

    (tmp_path / "config.json").write_text(json.dumps({"llm": {"model": "m"}}))
    status, message, _ = checker._probe_config()
    assert status is HealthStatus.DEGRADED and "base_url" in message

    (tmp_path / "config.json").write_text(json.dumps({"model": "m", "base_url": "u"}))
    assert checker._probe_config()[0] is HealthStatus.HEALTHY


def test_lazy_singleton_builds_once_even_under_concurrency():
    import threading
    import time

    from utils.singleton import lazy_singleton

    calls = []

    @lazy_singleton
    def get_thing():
        calls.append(1)
        time.sleep(0.01)
        return object()

    results = []
    threads = [threading.Thread(target=lambda: results.append(get_thing())) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1 and len({id(r) for r in results}) == 1

    get_thing.reset()
    assert get_thing() is not results[0] and len(calls) == 2


def test_breach_source_request_sets_user_agent_and_sleeps(monkeypatch):
    import requests
    from requests.structures import CaseInsensitiveDict

    from _version import __version__
    from core.osint.sources import base
    from core.osint.sources.intelx_source import IntelXBreachSource

    seen, slept = CaseInsensitiveDict(), []

    def fake_get(url, headers=None, **kwargs):
        seen.update(headers)
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", slept.append)

    source = IntelXBreachSource()
    with pytest.raises(requests.ConnectionError):
        source._get("https://example.invalid", headers={"X-Key": "k"})
    assert seen["User-Agent"] == f"CrawlLama-OSINT/{__version__}" and seen["X-Key"] == "k"
    assert slept == [source.rate_limit_delay]  # pause even when the request fails

    seen.clear()
    with pytest.raises(requests.ConnectionError):
        source._get("https://example.invalid", headers={"user-agent": "custom"})
    assert seen["User-Agent"] == "custom"  # case-insensitive override
