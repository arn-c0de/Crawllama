"""Deterministic fakes for offline agent/multihop drivers.

A :class:`FakeLLM` satisfies the single method every CrawlLama agent calls on
its LLM — ``generate(prompt, system_prompt=None, **kwargs) -> str`` — and emits a
synthetic ``llm.completed`` event (token source ``estimated``) so the usage /
latency collectors have data even without a real provider. This lets the agent
and multihop drivers exercise the *real* agent code paths with no network and no
Ollama, deterministically.
"""

from __future__ import annotations

from typing import Any

from core import telemetry


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class FakeLLM:
    """A canned, offline LLM. Returns the same answer for every prompt."""

    def __init__(self, answer: str = "canned answer", model: str = "fake-llm") -> None:
        self.answer = answer
        self.model = model
        self.calls = 0

    def generate(self, prompt: str = "", system_prompt: str | None = None, **kwargs: Any) -> str:
        self.calls += 1
        telemetry.emit_llm(
            provider="fake",
            request_model=self.model,
            response_model=self.model,
            input_tokens=_estimate_tokens(str(prompt)) + _estimate_tokens(str(system_prompt or "")),
            output_tokens=_estimate_tokens(self.answer),
            finish_reason="stop",
            token_source="estimated",  # nosec B106 - provenance label, not a credential
        )
        return self.answer
