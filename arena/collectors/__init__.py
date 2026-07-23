"""Collectors derive metrics from the captured telemetry event stream.

Each collector is a pure function over a list of :class:`arena.schema.Event`
(plus, where relevant, run context) and returns plain values the runner folds
into a :class:`arena.schema.MetricBundle`. Milestone B ships ``usage`` (LLM
tokens) and ``latency``; hallucination and coverage collectors arrive with the
``agent``/``osint`` drivers.
"""

from arena.collectors.latency import llm_latency_ms
from arena.collectors.usage import UsageTotals, collect_usage

__all__ = ["UsageTotals", "collect_usage", "llm_latency_ms"]
