"""Memory driver — deterministic persistence round-trip.

Drives the real :class:`core.memory.MemoryStore` through
remember → recall → clear → recall-again, reopening the store from the same file
to prove persistence. Fully deterministic; state lives in the isolated
``context.memory_file`` so runs never touch the user's ``data/memory.json``.

Scenario ``input`` fields:
    email: str      -> entity to remember (default a synthetic address)
    note: str|None  -> optional note to remember alongside
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class MemoryDriver(Driver):
    name = "memory"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.memory import MemoryStore

        email = str(scenario_input.get("email", "arena-fixture@example.com"))
        note = scenario_input.get("note")
        path = str(context.memory_file)

        store = MemoryStore(memory_file=path)
        telemetry.emit("osint.module.started", **{"arena.module": "memory"})

        added = store.remember_email(email)
        if note:
            store.add_note(str(note))

        recalled = [e.get("value") for e in store.get_all_emails()]
        present = email in recalled

        cleared = store.clear_all()

        # Reopen from disk to verify the clear persisted.
        reopened = MemoryStore(memory_file=path)
        after_clear = [e.get("value") for e in reopened.get_all_emails()]
        empty_after = len(after_clear) == 0

        telemetry.emit(
            "osint.module.completed",
            **{"arena.module": "memory", "added": added, "recalled": present, "cleared": cleared},
        )

        success = bool(added and present and cleared and empty_after)
        return DriverResult(
            success=success,
            raw_output=f"remembered={added} recalled={present} cleared_empty={empty_after}",
            structured_output={
                "added": added,
                "recalled": present,
                "recalled_values": recalled,
                "cleared": cleared,
                "empty_after_clear": empty_after,
            },
            extra_metrics={
                "remember_ok": 1.0 if added else 0.0,
                "recall_ok": 1.0 if present else 0.0,
                "persistence_ok": 1.0 if empty_after else 0.0,
            },
        )
