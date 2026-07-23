"""Neutral, no-op-by-default telemetry sink.

This is the single seam the arena harness (``arena/``) uses to observe production
code **without** creating a dependency from ``core/`` onto ``arena/``. Production
modules call :func:`emit` / :func:`span`; when no sink is installed (the normal
case, including all production and unit-test runs) these are cheap no-ops.

The arena installs a collector for the duration of a scenario via
:func:`set_sink` / :func:`reset_sink`. Because the active sink lives in a
:class:`contextvars.ContextVar`, capture is naturally scoped and concurrency-safe.

Attribute naming aligns, where practical, with the OpenTelemetry GenAI
conventions (``gen_ai.provider.name``, ``gen_ai.request.model``,
``gen_ai.usage.input_tokens`` …). Raw prompts, tool arguments, retrieved text and
model outputs are **not** telemetry attributes by default — they may contain PII.
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from collections.abc import Callable, Iterator
from typing import Any

# A sink receives (name, attributes, started_ns, duration_ns, status, error_type).
Sink = Callable[[str, dict[str, Any], int, int, str, "str | None"], None]

_sink: contextvars.ContextVar[Sink | None] = contextvars.ContextVar("crawllama_telemetry_sink", default=None)


def active() -> bool:
    """True when a telemetry sink is installed for the current context."""
    return _sink.get() is not None


def set_sink(sink: Sink) -> contextvars.Token:
    """Install *sink* as the active telemetry sink. Returns a reset token."""
    return _sink.set(sink)


def reset_sink(token: contextvars.Token) -> None:
    """Restore the previous sink using the token from :func:`set_sink`."""
    _sink.reset(token)


def emit(
    name: str,
    *,
    started_ns: int | None = None,
    duration_ns: int = 0,
    status: str = "ok",
    error_type: str | None = None,
    **attributes: Any,
) -> None:
    """Emit a point/duration event. No-op when no sink is installed."""
    sink = _sink.get()
    if sink is None:
        return
    ts = started_ns if started_ns is not None else time.monotonic_ns()
    try:
        sink(name, attributes, ts, duration_ns, status, error_type)
    except Exception:  # noqa: BLE001 - telemetry must never break production code
        pass


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Time a block and emit one event with its duration and status.

    Yields a mutable ``attributes`` dict so the caller can attach measured
    values (token counts, cache tier, …) discovered inside the block::

        with telemetry.span("llm.completed", **{"gen_ai.provider.name": "ollama"}) as attrs:
            resp = call()
            attrs["gen_ai.usage.output_tokens"] = resp.eval_count
    """
    if _sink.get() is None:
        # Fast path: nothing is listening, don't even time it.
        yield attributes
        return
    started = time.monotonic_ns()
    status = "ok"
    error_type: str | None = None
    try:
        yield attributes
    except Exception as exc:  # noqa: BLE001 - re-raised after recording
        status = "error"
        error_type = type(exc).__name__
        raise
    finally:
        emit(
            name,
            started_ns=started,
            duration_ns=time.monotonic_ns() - started,
            status=status,
            error_type=error_type,
            **attributes,
        )
