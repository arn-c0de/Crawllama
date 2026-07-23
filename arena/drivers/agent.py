"""Agent driver — drives the real SearchAgent with an injected fake LLM.

Constructs the production :class:`core.agent.agent.SearchAgent` with all
filesystem state isolated into the scenario ``workdir`` and web access disabled,
then injects a :class:`FakeLLM` so the real agent code path runs deterministically
with no network and no Ollama. Token usage is captured from the fake's
``llm.completed`` events by the runner's usage collector.
"""

from __future__ import annotations

from typing import Any

from arena.drivers._fakes import FakeLLM
from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


def _isolated_config(context: DriverContext) -> dict[str, Any]:
    return {
        "llm": {"provider": "ollama", "model": "fake"},  # no network at construction
        "rag": {"enabled": False},
        "cache": {"enabled": False},
        "paths": {
            "session_file": str(context.workdir / "session.json"),
            "embeddings_dir": str(context.workdir / "embeddings"),
        },
    }


class AgentDriver(Driver):
    name = "agent"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.agent.agent import SearchAgent

        answer = str(scenario_input.get("answer", "canned agent answer"))
        query = str(scenario_input.get("query", ""))

        telemetry.emit("agent.started", **{"arena.driver": self.name})
        agent = SearchAgent(_isolated_config(context), enable_web=False)
        agent.llm = FakeLLM(answer)
        out = agent.query(query, use_tools=False)
        telemetry.emit("agent.completed", **{"arena.driver": self.name})

        return DriverResult(
            success=bool(out),
            raw_output=out,
            structured_output={"answer": out},
        )
