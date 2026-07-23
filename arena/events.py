"""ContextVar-backed event collection for a single arena scenario run.

:class:`EventCollector` installs itself as the :mod:`core.telemetry` sink for the
duration of a ``with`` block and records every emitted event as an
:class:`arena.schema.Event`. Drivers may also emit directly through the same
:mod:`core.telemetry` API, so a driver's synthetic events and production code's
instrumented events land in one ordered stream.

Sequence numbers are assigned monotonically in emission order; ``started_ns`` is
captured from ``time.monotonic_ns`` and is only meaningful *relative* to other
events in the same run.
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Any

from arena.schema import Event
from core import telemetry


class EventCollector:
    """Collects telemetry events emitted while it is the active sink."""

    def __init__(self, scenario_id: str | None = None) -> None:
        self.scenario_id = scenario_id
        self.events: list[Event] = []
        self._seq = 0
        self._token = None

    # -- sink callback -------------------------------------------------- #
    def _record(
        self,
        name: str,
        attributes: dict[str, Any],
        started_ns: int,
        duration_ns: int,
        status: str,
        error_type: str | None,
    ) -> None:
        self.events.append(
            Event(
                event_id=uuid.uuid4().hex,
                scenario_id=self.scenario_id,
                seq=self._seq,
                name=name,
                started_ns=started_ns,
                duration_ns=duration_ns,
                status=status,
                attributes=dict(attributes),
                error_type=error_type,
            )
        )
        self._seq += 1

    # -- context management --------------------------------------------- #
    def __enter__(self) -> EventCollector:
        self._token = telemetry.set_sink(self._record)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._token is not None:
            telemetry.reset_sink(self._token)
            self._token = None

    # -- queries -------------------------------------------------------- #
    def names(self) -> list[str]:
        return [e.name for e in self.events]

    def by_name(self, name: str) -> list[Event]:
        return [e for e in self.events if e.name == name]

    def has(self, name: str) -> bool:
        return any(e.name == name for e in self.events)
