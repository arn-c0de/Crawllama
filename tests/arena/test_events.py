"""Telemetry sink is a no-op unless an arena collector is active."""

from arena.events import EventCollector
from core import telemetry


def test_emit_is_noop_without_sink():
    # No collector installed -> emit must not raise and must not be observed.
    assert telemetry.active() is False
    telemetry.emit("something.happened", foo=1)  # should be a silent no-op


def test_collector_captures_events():
    with EventCollector("scenario-x") as coll:
        assert telemetry.active() is True
        telemetry.emit("agent.started")
        with telemetry.span("tool.completed", **{"gen_ai.tool.name": "t"}):
            pass
        telemetry.emit("agent.completed")
    assert telemetry.active() is False
    assert coll.names() == ["agent.started", "tool.completed", "agent.completed"]
    assert all(e.scenario_id == "scenario-x" for e in coll.events)
    assert [e.seq for e in coll.events] == [0, 1, 2]


def test_span_records_error_status():
    with EventCollector() as coll:
        try:
            with telemetry.span("risky"):
                raise ValueError("boom")
        except ValueError:
            pass
    evt = coll.by_name("risky")[0]
    assert evt.status == "error"
    assert evt.error_type == "ValueError"
