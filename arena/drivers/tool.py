"""Tool driver — exercises deterministic tool-layer components.

Two network-free operations, selected by ``input["op"]``:

* ``parse_operators`` — runs the real :class:`core.osint.query_parser.OSINTQueryParser`
  over a query and reports which advanced operators (``site:``/``inurl:``/
  ``filetype:`` …) were extracted. Coverage = matched ÷ expected operators.
* ``cache`` — drives the real :class:`core.cache.CacheManager` through a
  miss → set → hit cycle in an isolated cache dir, emitting ``cache.lookup``
  events with the real ``hit``/``miss`` outcome.

Both are deterministic and require no network or LLM.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class ToolDriver(Driver):
    name = "tool"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        op = str(scenario_input.get("op", "parse_operators"))
        if op == "parse_operators":
            return self._parse_operators(scenario_input)
        if op == "cache":
            return self._cache(scenario_input, context)
        if op == "invoke_tool":
            return self._invoke_tool(scenario_input, context)
        return DriverResult(success=False, error=f"unknown tool op: {op!r}")

    # ------------------------------------------------------------------ #
    def _parse_operators(self, scenario_input: dict[str, Any]) -> DriverResult:
        from core.osint.query_parser import OSINTQueryParser

        query = str(scenario_input.get("query", ""))
        expected = list(scenario_input.get("expected_operators", []) or [])

        with telemetry.span("tool.started", **{"gen_ai.tool.name": "query_parser"}):
            parsed = OSINTQueryParser().parse(query)

        as_dict = dataclasses.asdict(parsed) if dataclasses.is_dataclass(parsed) else dict(vars(parsed))
        # An operator is "found" when its parsed field is truthy.
        found = {op: bool(as_dict.get(op)) for op in expected}
        matched = sum(1 for v in found.values() if v)
        coverage = (matched / len(expected)) if expected else 1.0
        telemetry.emit("tool.completed", **{"gen_ai.tool.name": "query_parser", "matched": matched})

        return DriverResult(
            success=True,
            raw_output=str(as_dict.get("text", query)),
            structured_output={"parsed": _jsonable(as_dict), "operators_found": found},
            coverage=coverage,
            tool_calls=1,
            extra_metrics={"operator_coverage": coverage},
        )

    # ------------------------------------------------------------------ #
    def _invoke_tool(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        """Invoke a real registered production tool by name (live/replay only).

        Covers web_search / read_page / wiki_lookup / rag_search. The tool
        wrappers never raise (they return an error string), so success is derived
        from whether a non-empty, non-``*failed*`` result came back.
        """
        from tools.tool_registry import ToolRegistry

        tool_name = str(scenario_input.get("tool", ""))
        tool_input = str(scenario_input.get("input", ""))
        registry = ToolRegistry(rag_enabled=(tool_name == "rag_search"), config=scenario_input.get("config", {}))
        tools = {t.name: t for t in registry.get_tools()}
        tool = tools.get(tool_name)
        if tool is None:
            return DriverResult(success=False, error=f"tool {tool_name!r} not registered")

        output = tool.func(tool_input)
        failed = (not output) or ("failed" in output.lower()[:40]) or ("not enabled" in output.lower())
        return DriverResult(
            success=not failed,
            raw_output=output,
            structured_output={"tool": tool_name, "length": len(output or "")},
            tool_calls=1,
        )

    # ------------------------------------------------------------------ #
    def _cache(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.cache import CacheManager

        key = str(scenario_input.get("key", "arena-cache-probe"))
        payload = scenario_input.get("payload", {"cached": True})
        cache = CacheManager(cache_dir=str(context.cache_dir), ttl_hours=1)

        # 1) cold lookup -> miss
        pre = cache.get(key)
        telemetry.emit("cache.lookup", **{"outcome": "miss" if pre is None else "hit", "phase": "cold"})
        # 2) populate
        cache.set(key, payload)
        # 3) warm lookup -> hit
        post = cache.get(key)
        hit = post is not None
        telemetry.emit("cache.lookup", **{"outcome": "hit" if hit else "miss", "phase": "warm"})

        return DriverResult(
            success=hit and pre is None,
            raw_output="cache hit" if hit else "cache miss",
            structured_output={"cold": pre, "warm": _jsonable(post)},
            cache_hit=hit,
            tool_calls=2,
            extra_metrics={"cache_hit": 1.0 if hit else 0.0},
        )


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion of arbitrary values to JSON-safe primitives."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
