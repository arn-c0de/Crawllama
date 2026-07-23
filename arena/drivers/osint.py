"""OSINT driver — deterministic, offline OSINT leaf operations.

Calls the *pure* (no-network) methods of the real OSINT modules and times each
call, emitting ``osint.module.started`` / ``osint.module.completed`` events. The
network-heavy entrypoints (``analyze_email`` MX/breach lookups, ``lookup_ip``
geolocation) are intentionally out of scope for the deterministic slice — they
belong to ``live``/``replay`` fixture modes in a later milestone.

Scenario ``input``:
    module: "email" | "ip"
    op:     email -> "validate" | "variations" | "disposable"
            ip    -> "validate" | "classify"
    value:  the input to the operation
    expected_fields: {name: True} checked against the structured output
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class OsintDriver(Driver):
    name = "osint"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        module = str(scenario_input.get("module", "email"))
        op = str(scenario_input.get("op", "validate"))
        value = str(scenario_input.get("value", ""))
        expected = list(scenario_input.get("expected_fields", []) or [])

        telemetry.emit("osint.module.started", **{"arena.module": module, "arena.op": op})
        try:
            with telemetry.span("osint.module.completed", **{"arena.module": module, "arena.op": op}):
                structured = self._dispatch(module, op, value)
        except Exception as exc:  # noqa: BLE001 - a driver-level failure, not a crash
            return DriverResult(success=False, error=f"{type(exc).__name__}: {exc}")

        matched = sum(1 for f in expected if structured.get(f) not in (None, "", [], False))
        coverage = (matched / len(expected)) if expected else 1.0
        return DriverResult(
            success=True,
            raw_output=str(structured.get("result")),
            structured_output=structured,
            coverage=coverage,
            extra_metrics={"osint_coverage": coverage},
        )

    def _dispatch(self, module: str, op: str, value: str) -> dict[str, Any]:
        if module == "email":
            from core.osint.email_intel import EmailIntelligence

            intel = EmailIntelligence()
            if op == "validate":
                ok = intel.validate_syntax(value)
                return {"result": ok, "valid": ok}
            if op == "variations":
                variations = intel.generate_variations(value)
                return {"result": variations, "variations": variations, "count": len(variations)}
            if op == "disposable":
                domain = value.split("@")[-1]
                disp = intel.is_disposable(domain)
                return {"result": disp, "disposable": disp}
            raise ValueError(f"unknown email op: {op!r}")

        if module == "ip":
            from core.osint.ip_intel import IPIntelligence

            intel = IPIntelligence()
            if op == "validate":
                valid, ip_type, desc = intel.validate_ip(value)
                return {"result": valid, "valid": valid, "type": ip_type, "description": desc}
            if op == "classify":
                flags = intel._classify_ip_security(value)
                return {"result": flags, "security_flags": flags}
            raise ValueError(f"unknown ip op: {op!r}")

        raise ValueError(f"unknown osint module: {module!r}")
