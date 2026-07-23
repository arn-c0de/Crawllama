"""Render a :class:`arena.compare.ComparisonReport` as Markdown or JSON.

The Markdown report has explicit **Regressions / Improvements / Unchanged**
sections and a machine-readable verdict line, mirroring the plan's before/after
report (§11). HTML escaping / spreadsheet-formula prefixing is not needed here
because output is Markdown/JSON only (plan §23).
"""

from __future__ import annotations

import json

from arena.compare import ComparisonReport


def to_json(report: ComparisonReport, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(), indent=indent)


def _fmt_latency(delta: float | None) -> str:
    if delta is None:
        return "—"
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}ms"


def to_markdown(report: ComparisonReport) -> str:
    verdict = "❌ REGRESSION" if report.regression else "✅ OK"
    lines: list[str] = []
    lines.append("# Arena before/after comparison")
    lines.append("")
    lines.append(f"**Verdict:** {verdict}  ·  `regression={str(report.regression).lower()}`")
    lines.append("")
    lines.append(f"- **before:** `{report.before_run_id}`")
    lines.append(f"- **after:**  `{report.after_run_id}`")
    lines.append(f"- **varying dimension:** `{report.varying}`")
    lines.append(f"- **win / tie / loss:** {report.win} / {report.tie} / {report.loss}")
    lines.append("")

    # Comparison-identity table
    lines.append("## Comparison identity")
    lines.append("")
    lines.append("| dimension | before | after |")
    lines.append("|---|---|---|")
    for dim in report.dimensions_before:
        b = report.dimensions_before[dim]
        a = report.dimensions_after[dim]
        mark = "" if b == a else " ⚠️"
        lines.append(f"| {dim}{mark} | `{_short(b)}` | `{_short(a)}` |")
    lines.append("")

    _section(lines, "Regressions", report, {"regressed"})
    _section(lines, "Improvements", report, {"improved"})
    _section(lines, "Unchanged", report, {"unchanged_pass", "unchanged_fail"})
    _section(lines, "Added / Removed", report, {"added", "removed"})

    return "\n".join(lines) + "\n"


def _section(lines: list[str], title: str, report: ComparisonReport, statuses: set[str]) -> None:
    rows = [d for d in report.scenarios if d.status in statuses]
    lines.append(f"## {title} ({len(rows)})")
    lines.append("")
    if not rows:
        lines.append("_none_")
        lines.append("")
        return
    lines.append("| scenario | before | after | latency Δ |")
    lines.append("|---|---|---|---|")
    for d in rows:
        lines.append(
            f"| `{d.scenario_id}` | {_passmark(d.before_passed)} | {_passmark(d.after_passed)} | "
            f"{_fmt_latency(d.latency_delta_ms)} |"
        )
    lines.append("")


def _passmark(passed: bool | None) -> str:
    if passed is None:
        return "—"
    return "PASS" if passed else "FAIL"


def _short(value: str, width: int = 20) -> str:
    return value if len(value) <= width else value[:width] + "…"
