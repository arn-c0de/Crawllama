"""Multihop driver — drives the real MultiHopReasoningAgent with a fake LLM.

Constructs the production :class:`core.langgraph_agent.MultiHopReasoningAgent`
with RAG disabled and web tools neutralised (replaced by offline stubs), then
injects a :class:`FakeLLM`. This exercises the real LangGraph reasoning path
(router → analyse → synthesise) deterministically with no network, and returns
the structured result (answer, confidence, steps, reasoning_path).
"""

from __future__ import annotations

from typing import Any

from arena.drivers._fakes import FakeLLM
from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


def _neutralise_web(agent: Any) -> None:
    """Replace the agent's web-touching tool wrappers with offline stubs.

    The LangGraph nodes call the registry's wrappers; stubbing them keeps the
    reasoning path offline while still exercising the real graph.
    """
    registry = getattr(agent, "tool_registry", None)
    if registry is None:
        return
    registry._web_search_wrapper = lambda query: "No web results (arena offline mode)."
    registry._page_reader_wrapper = lambda url: "No page content (arena offline mode)."
    registry._wiki_lookup_wrapper = lambda query: "No wiki article (arena offline mode)."
    registry._rag_search_wrapper = lambda query: "RAG disabled (arena offline mode)."


class MultiHopDriver(Driver):
    name = "multihop"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.langgraph_agent import MultiHopReasoningAgent

        answer = str(scenario_input.get("answer", "canned multihop answer"))
        query = str(scenario_input.get("query", ""))
        max_hops = int(scenario_input.get("max_hops", 1))

        config = {
            "llm": {"provider": "ollama", "model": "fake"},
            "rag": {"enabled": False},
            "cache": {"enabled": False},
            "paths": {"embeddings_dir": str(context.workdir / "embeddings")},
        }

        telemetry.emit("agent.started", **{"arena.driver": self.name})
        agent = MultiHopReasoningAgent(config, max_hops=max_hops, enable_critique=False)
        agent.llm = FakeLLM(answer)
        _neutralise_web(agent)
        result = agent.query(query)
        telemetry.emit("agent.completed", **{"arena.driver": self.name})

        return DriverResult(
            success=bool(result.get("answer")),
            raw_output=str(result.get("answer", "")),
            structured_output={
                "answer": result.get("answer"),
                "confidence": result.get("confidence"),
                "steps": result.get("steps"),
                "reasoning_path": result.get("reasoning_path"),
                "search_queries": result.get("search_queries"),
            },
            final_confidence=result.get("confidence"),
        )
