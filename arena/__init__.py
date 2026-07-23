"""CrawlLama Model Arena & regression-testing harness.

A reproducible testing / benchmarking subsystem that drives the CrawlLama agent
and its tools through fixed scenarios, captures structured events + metrics, and
stores immutable, comparable run records under ``data/arena/``.

Design: see ``MODEL_ARENA_PLAN.md`` (§17-§25 are the implementation-ready
revision). This package is the Milestone A vertical slice: schema, atomic run
store, worker protocol, a handful of deterministic drivers, rules scoring and a
CLI — all runnable without a live LLM or network.

Hard rule: ``core/`` must never import ``arena/``. Production code only calls the
no-op-by-default sink in :mod:`core.telemetry`; the arena binds a collector into
that sink for the duration of a run.
"""

from __future__ import annotations

# Bump when the on-disk run/scenario/event schema changes in an incompatible way.
SCHEMA_VERSION = 1

# Bump when the worker stdin/stdout JSON-Lines protocol changes incompatibly.
WORKER_PROTOCOL_VERSION = 1

__all__ = ["SCHEMA_VERSION", "WORKER_PROTOCOL_VERSION"]
