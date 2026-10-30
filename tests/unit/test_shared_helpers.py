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
