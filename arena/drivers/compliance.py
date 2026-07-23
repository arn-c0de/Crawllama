"""Compliance driver — deterministic, offline OSINT compliance decisions.

Drives the real :class:`core.osint.compliance.OSINTCompliance` gate: accept terms,
then check a query against the blacklist and rate limits. All state is local
filesystem (isolated to the scenario workdir); no network. A blacklisted query is
rejected; an allowed query passes.

Scenario ``input``:
    query: str
    query_type: str = "general_osint"
    config: dict | None   (e.g. {"osint": {"general_osint_limit": 1}})
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class ComplianceDriver(Driver):
    name = "compliance"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.osint.compliance import OSINTCompliance

        query = str(scenario_input.get("query", ""))
        query_type = str(scenario_input.get("query_type", "general_osint"))
        compliance = OSINTCompliance(
            log_dir=str(context.workdir / "osint_logs"),
            config=scenario_input.get("config"),
        )
        user = "arena"
        compliance.accept_terms(user)

        with telemetry.span("compliance.checked", **{"arena.query_type": query_type}):
            allowed, message = compliance.check_query(query, user, query_type)
        telemetry.emit("compliance.decision", **{"allowed": allowed})

        return DriverResult(
            success=True,
            raw_output=message,
            structured_output={"allowed": allowed, "message": message},
            extra_metrics={"allowed": 1.0 if allowed else 0.0},
        )
