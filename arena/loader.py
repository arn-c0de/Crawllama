"""Load and validate checked-in scenarios and suites (JSON).

Milestone A uses JSON for checked-in fixtures because PyYAML is not yet a
*direct* dependency (plan §18). The documentation examples remain YAML for
readability; the on-disk format is JSON with the same field names.

Directory layout::

    arena/scenarios/
      cases/<id>.json     # one Scenario per file
      suites/<id>.json    # one Suite (list of scenario ids) per file
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from arena.schema import Scenario, Suite

_HERE = Path(__file__).resolve().parent
SCENARIOS_ROOT = _HERE / "scenarios"
CASES_DIR = SCENARIOS_ROOT / "cases"
SUITES_DIR = SCENARIOS_ROOT / "suites"


class ScenarioError(ValueError):
    """Raised when a scenario/suite file is missing or invalid."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read {path}: {exc}") from exc


def load_all_scenarios(cases_dir: Path | None = None) -> dict[str, Scenario]:
    """Load every case file into a {scenario_id: Scenario} map."""
    cases_dir = cases_dir or CASES_DIR
    out: dict[str, Scenario] = {}
    for path in sorted(cases_dir.glob("*.json")):
        data = _load_json(path)
        try:
            scenario = Scenario.model_validate(data)
        except ValidationError as exc:
            raise ScenarioError(f"invalid scenario {path.name}: {exc}") from exc
        if scenario.id in out:
            raise ScenarioError(f"duplicate scenario id {scenario.id!r} in {path.name}")
        out[scenario.id] = scenario
    return out


def load_suite(suite_id: str, suites_dir: Path | None = None) -> Suite:
    suites_dir = suites_dir or SUITES_DIR
    path = suites_dir / f"{suite_id}.json"
    if not path.exists():
        raise ScenarioError(f"unknown suite {suite_id!r} (looked in {suites_dir})")
    try:
        return Suite.model_validate(_load_json(path))
    except ValidationError as exc:
        raise ScenarioError(f"invalid suite {suite_id!r}: {exc}") from exc


def resolve_suite(suite_id: str) -> list[Scenario]:
    """Return the ordered scenarios referenced by a suite, validating references."""
    suite = load_suite(suite_id)
    scenarios = load_all_scenarios()
    resolved: list[Scenario] = []
    missing: list[str] = []
    for sid in suite.scenarios:
        if sid in scenarios:
            resolved.append(scenarios[sid])
        else:
            missing.append(sid)
    if missing:
        raise ScenarioError(f"suite {suite_id!r} references unknown scenarios: {missing}")
    return resolved


def validate_all() -> tuple[list[str], list[str]]:
    """Validate every case and suite. Returns (case_ids, suite_ids). Raises on error."""
    scenarios = load_all_scenarios()
    suite_ids = []
    for path in sorted(SUITES_DIR.glob("*.json")):
        suite = load_suite(path.stem)
        for sid in suite.scenarios:
            if sid not in scenarios:
                raise ScenarioError(f"suite {suite.id!r} references unknown scenario {sid!r}")
        suite_ids.append(suite.id)
    return sorted(scenarios), sorted(suite_ids)
