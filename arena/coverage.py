"""Capability coverage report (plan §6, Milestone D acceptance).

Declares the capability catalog the arena must cover and cross-references it
against the checked-in scenarios (by each scenario's ``capability`` field) and the
registered drivers. Every declared capability must map to at least one scenario,
or be an ``optional`` capability carrying a machine-readable ``skip_reason``.

Network-bound capabilities (web search, page read, wiki, RAG, and most OSINT
modules) are covered by ``live``-mode scenarios that exist but are excluded from
the deterministic CI gate; the report marks them ``live_only``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from arena.drivers import known_drivers
from arena.loader import load_all_scenarios


@dataclass(frozen=True)
class Capability:
    id: str
    kind: str  # tool | osint | reasoning | safety | infra
    description: str
    requires: tuple[str, ...] = ()  # e.g. ("network",), ("network", "embeddings")
    optional: bool = False
    skip_reason: str | None = None


# The registered production tools (tools/tool_registry.py get_tools()).
REGISTERED_TOOLS: tuple[str, ...] = ("web_search", "read_page", "wiki_lookup", "rag_search")


CAPABILITIES: list[Capability] = [
    # --- deterministic / offline -------------------------------------- #
    Capability("advanced_operators", "tool", "site:/inurl:/filetype: operator parsing"),
    Capability("caching", "infra", "cache miss -> set -> hit + tier events"),
    Capability("memory", "infra", "remember -> recall -> clear persistence"),
    Capability("adaptive_escalation", "reasoning", "low-confidence escalation low->high"),
    Capability("agent_context", "reasoning", "SearchAgent context-only answer"),
    Capability("multihop", "reasoning", "MultiHopReasoningAgent graph path"),
    Capability("osint_email", "osint", "email syntax validation (offline)"),
    Capability("osint_ip", "osint", "IP classification/validation (offline)"),
    Capability("hallucination_guard", "safety", "trap response -> high hallucination risk"),
    Capability("compliance", "safety", "robots/rate-limit policy decision (offline)"),
    Capability("fallback", "infra", "primary fails -> secondary provider chosen"),
    Capability("plugins", "infra", "load -> invoke -> unload a fixture plugin"),
    # --- network-bound tools: live scenarios only --------------------- #
    Capability("web_search", "tool", "web search via provider fallback", requires=("network",)),
    Capability("read_page", "tool", "fetch & extract a web page", requires=("network",)),
    Capability("wiki_lookup", "tool", "Wikipedia lookup", requires=("network",)),
    Capability("rag_search", "tool", "semantic search over local docs", requires=("network", "embeddings")),
    # --- optional OSINT modules (network / extra deps): skipped ------- #
    Capability(
        "osint_phone", "osint", "phone validate/carrier/country",
        requires=("phonenumbers",), optional=True,
        skip_reason="requires the 'osint' extra (phonenumbers) + carrier data; offline slice deferred to a later milestone",
    ),
    Capability(
        "osint_domain", "osint", "domain profile (MX/DNS/WHOIS)",
        requires=("network",), optional=True,
        skip_reason="requires live DNS/WHOIS; belongs to replay/live evidence mode",
    ),
    Capability(
        "osint_social", "osint", "username across platforms",
        requires=("network",), optional=True,
        skip_reason="requires live platform HTTP; belongs to replay/live evidence mode",
    ),
    Capability(
        "osint_company", "osint", "company intel enrichment",
        requires=("network",), optional=True,
        skip_reason="requires live enrichment sources; belongs to replay/live evidence mode",
    ),
    Capability(
        "breach", "osint", "known-fixture email -> expected breach set",
        requires=("fixtures",), optional=True,
        skip_reason="needs a curated local breach fixture set; deferred (only a tiny sample exists)",
    ),
]


class CapabilityCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    description: str
    requires: list[str] = Field(default_factory=list)
    optional: bool = False
    covered: bool = False
    live_only: bool = False
    scenarios: list[str] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilityCoverage] = Field(default_factory=list)
    driver_coverage: dict[str, list[str]] = Field(default_factory=dict)
    drivers_without_scenarios: list[str] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)
    complete: bool = False


@dataclass
class _Index:
    by_capability: dict[str, list] = field(default_factory=dict)
    by_driver: dict[str, list] = field(default_factory=dict)


def _index_scenarios() -> _Index:
    idx = _Index()
    for scenario in load_all_scenarios().values():
        if scenario.capability:
            idx.by_capability.setdefault(scenario.capability, []).append(scenario)
        idx.by_driver.setdefault(scenario.driver, []).append(scenario)
    return idx


def coverage_report() -> CoverageReport:
    idx = _index_scenarios()
    caps: list[CapabilityCoverage] = []
    uncovered: list[str] = []

    for cap in CAPABILITIES:
        matched = idx.by_capability.get(cap.id, [])
        scenario_ids = sorted(s.id for s in matched)
        covered = bool(matched)
        live_only = covered and all(s.fixture_mode == "live" for s in matched)
        skipped = cap.optional and not covered and cap.skip_reason is not None
        if not covered and not skipped:
            uncovered.append(cap.id)
        caps.append(
            CapabilityCoverage(
                id=cap.id,
                kind=cap.kind,
                description=cap.description,
                requires=list(cap.requires),
                optional=cap.optional,
                covered=covered,
                live_only=live_only,
                scenarios=scenario_ids,
                skipped=skipped,
                skip_reason=cap.skip_reason if skipped else None,
            )
        )

    driver_coverage = {d: sorted(s.id for s in idx.by_driver.get(d, [])) for d in known_drivers()}
    drivers_without = sorted(d for d, ids in driver_coverage.items() if not ids)

    return CoverageReport(
        capabilities=caps,
        driver_coverage=driver_coverage,
        drivers_without_scenarios=drivers_without,
        uncovered=uncovered,
        complete=not uncovered and not drivers_without,
    )


def to_markdown(report: CoverageReport) -> str:
    lines = ["# Arena capability coverage", ""]
    status = "✅ COMPLETE" if report.complete else "❌ GAPS"
    lines.append(f"**Status:** {status}")
    if report.uncovered:
        lines.append(f"**Uncovered (required):** {', '.join(report.uncovered)}")
    if report.drivers_without_scenarios:
        lines.append(f"**Drivers without a scenario:** {', '.join(report.drivers_without_scenarios)}")
    lines.append("")
    lines.append("| capability | kind | status | scenarios / reason |")
    lines.append("|---|---|---|---|")
    for c in report.capabilities:
        if c.covered:
            state = "live-only" if c.live_only else "covered"
            detail = ", ".join(f"`{s}`" for s in c.scenarios)
        elif c.skipped:
            state = "skipped"
            detail = c.skip_reason or ""
        else:
            state = "UNCOVERED"
            detail = ""
        lines.append(f"| {c.id} | {c.kind} | {state} | {detail} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def to_json(report: CoverageReport, *, indent: int = 2) -> str:
    import json

    return json.dumps(report.model_dump(), indent=indent)
