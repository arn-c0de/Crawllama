"""Token-usage collector.

Aggregates ``llm.completed`` events (emitted by the instrumented Ollama and
cloud clients, or by a fake in tests) into total input/output tokens and the
number of LLM calls. The token source is reported as ``provider`` when every
contributing event carried provider-reported usage, otherwise ``estimated`` —
so a run never silently mixes measured and guessed token counts (plan §17, §19).
"""

from __future__ import annotations

from dataclasses import dataclass

from arena.schema import Event

_LLM_EVENT = "llm.completed"


@dataclass
class UsageTotals:
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    token_source: str | None = None  # "provider" | "estimated" | None

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


def collect_usage(events: list[Event]) -> UsageTotals:
    """Sum token usage across all ``llm.completed`` events in *events*."""
    totals = UsageTotals()
    sources: set[str] = set()
    saw_any = False
    for e in events:
        if e.name != _LLM_EVENT:
            continue
        totals.llm_calls += 1
        attrs = e.attributes
        ti = attrs.get("gen_ai.usage.input_tokens")
        to = attrs.get("gen_ai.usage.output_tokens")
        if ti is not None:
            totals.tokens_in += int(ti)
        if to is not None:
            totals.tokens_out += int(to)
            saw_any = True
        if ti is not None:
            saw_any = True
        src = attrs.get("arena.token_source")
        if src:
            sources.add(str(src))

    if not saw_any:
        totals.token_source = None
    elif sources == {"provider"}:
        totals.token_source = "provider"
    else:
        # any missing/mixed/estimated source degrades the whole run to estimated
        totals.token_source = "estimated"
    return totals
