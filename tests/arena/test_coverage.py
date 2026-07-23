"""Capability coverage report + no-secrets fixture guard (Milestone D)."""

import json
import re
from pathlib import Path

from arena.coverage import CAPABILITIES, REGISTERED_TOOLS, coverage_report
from arena.drivers import known_drivers
from arena.loader import CASES_DIR


def test_coverage_is_complete():
    report = coverage_report()
    assert report.complete is True, f"uncovered={report.uncovered} drivers={report.drivers_without_scenarios}"
    assert report.uncovered == []


def test_every_registered_tool_has_a_scenario():
    report = coverage_report()
    by_id = {c.id: c for c in report.capabilities}
    for tool in REGISTERED_TOOLS:
        assert tool in by_id, f"tool {tool} missing from catalog"
        assert by_id[tool].covered, f"tool {tool} has no scenario"


def test_skipped_capabilities_have_machine_readable_reason():
    report = coverage_report()
    for c in report.capabilities:
        if c.skipped:
            assert c.optional is True
            assert c.skip_reason and len(c.skip_reason) > 10


def test_every_registered_driver_has_a_scenario():
    report = coverage_report()
    assert report.drivers_without_scenarios == []
    # mock is the CI anchor; every other driver maps to a capability scenario
    for driver in known_drivers():
        assert driver in report.driver_coverage


def test_catalog_has_no_duplicate_ids():
    ids = [c.id for c in CAPABILITIES]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# Security: no checked-in fixture may contain real secrets / uncontrolled PII  #
# --------------------------------------------------------------------------- #
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),          # OpenAI-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),             # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),         # GitHub PAT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),  # PEM private key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack token
]


def test_no_scenario_fixture_contains_secrets():
    for path in Path(CASES_DIR).glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for pat in _SECRET_PATTERNS:
            assert not pat.search(text), f"possible secret in fixture {path.name}: {pat.pattern}"


def test_fixtures_use_reserved_example_identifiers_only():
    """OSINT-ish fixtures must use reserved/synthetic identifiers (example.com, 8.8.8.8)."""
    for path in Path(CASES_DIR).glob("osint.*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        value = str(data.get("input", {}).get("value", ""))
        if "@" in value:
            assert value.endswith("example.com") or value.endswith("example.org")
