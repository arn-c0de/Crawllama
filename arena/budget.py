"""Budget caps for cloud-API cost control during arena runs (plan §15, §22).

A tournament or judged run must stop cleanly when it exhausts its budget of LLM
calls / tokens / cost, leaving *partial* results marked incomplete rather than
running up an unbounded bill. :class:`BudgetTracker.charge` raises
:class:`BudgetExhausted` the moment a limit would be crossed.
"""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExhausted(RuntimeError):
    """Raised when a charge would exceed a configured budget limit."""

    def __init__(self, limit: str, used: float, cap: float) -> None:
        super().__init__(f"budget exhausted: {limit} used={used:g} cap={cap:g}")
        self.limit = limit
        self.used = used
        self.cap = cap


@dataclass
class Budget:
    """Optional caps; ``None`` means unlimited for that dimension."""

    max_llm_calls: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None


class BudgetTracker:
    def __init__(self, budget: Budget | None = None) -> None:
        self.budget = budget or Budget()
        self.llm_calls = 0
        self.tokens = 0
        self.cost_usd = 0.0

    def would_exceed(self, *, calls: int = 0, tokens: int = 0, cost: float = 0.0) -> str | None:
        b = self.budget
        if b.max_llm_calls is not None and self.llm_calls + calls > b.max_llm_calls:
            return "llm_calls"
        if b.max_tokens is not None and self.tokens + tokens > b.max_tokens:
            return "tokens"
        if b.max_cost_usd is not None and self.cost_usd + cost > b.max_cost_usd:
            return "cost_usd"
        return None

    def charge(self, *, calls: int = 0, tokens: int = 0, cost: float = 0.0) -> None:
        """Record usage; raise :class:`BudgetExhausted` if a cap would be crossed."""
        limit = self.would_exceed(calls=calls, tokens=tokens, cost=cost)
        if limit is not None:
            used = {"llm_calls": self.llm_calls, "tokens": self.tokens, "cost_usd": self.cost_usd}[limit]
            cap = {
                "llm_calls": self.budget.max_llm_calls,
                "tokens": self.budget.max_tokens,
                "cost_usd": self.budget.max_cost_usd,
            }[limit]
            raise BudgetExhausted(limit, float(used), float(cap))
        self.llm_calls += calls
        self.tokens += tokens
        self.cost_usd += cost

    def snapshot(self) -> dict[str, float]:
        return {"llm_calls": self.llm_calls, "tokens": self.tokens, "cost_usd": self.cost_usd}
