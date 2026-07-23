"""LLM-as-judge scoring (plan §22).

The judge is **model-agnostic**: it is constructed with a ``complete(prompt)->str``
callable (a pinned judge LLM in production, a fake in tests), plus a versioned
model id and prompt version. Two grading modes:

* **pointwise** — rubric grade of a single answer, structured JSON.
* **pairwise** — prefer one of two answers; used for before/after and arena
  comparisons. :meth:`Judge.pairwise_blind` runs both A/B and B/A orderings with
  hidden, position-neutral labels and reports positional disagreement.

Robustness: a schema-invalid judge response is retried **once**, then the result
is marked ``failed`` (never silently coerced). ``tie`` is always allowed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

CompletionFn = Callable[[str], str]

JUDGE_PROMPT_VERSION = "v1"


@dataclass
class PointwiseResult:
    failed: bool
    score: float | None = None  # 0..1
    rationale: str = ""
    attempts: int = 0
    raw: list[str] = field(default_factory=list)


@dataclass
class PairwiseResult:
    failed: bool
    winner: Literal["first", "second", "tie"] | None = None
    rationale: str = ""
    attempts: int = 0
    raw: list[str] = field(default_factory=list)


@dataclass
class BlindPairwiseResult:
    """Blind A/B + B/A pairwise with positional-bias detection."""

    winner: Literal["A", "B", "tie"]
    positional_disagreement: bool
    order_ab: PairwiseResult
    order_ba: PairwiseResult
    failed: bool = False


def _extract_json(text: str) -> dict | None:
    """Best-effort JSON object extraction from a model response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


class Judge:
    def __init__(
        self,
        complete: CompletionFn,
        *,
        model: str = "pinned-judge",
        prompt_version: str = JUDGE_PROMPT_VERSION,
        on_call: Callable[[], None] | None = None,
    ) -> None:
        self.complete = complete
        self.model = model
        self.prompt_version = prompt_version
        # optional hook fired before each LLM call (e.g. a budget charge)
        self._on_call = on_call

    # ------------------------------------------------------------------ #
    def _call(self, prompt: str) -> str:
        if self._on_call is not None:
            self._on_call()
        return self.complete(prompt)

    # ------------------------------------------------------------------ #
    def pointwise(self, question: str, answer: str, reference: str | None = None) -> PointwiseResult:
        prompt = self._pointwise_prompt(question, answer, reference)
        raw_all: list[str] = []
        for attempt in (1, 2):  # try once, retry once
            raw = self._call(prompt)
            raw_all.append(raw)
            data = _extract_json(raw)
            if data is not None and isinstance(data.get("score"), (int, float)):
                score = float(data["score"])
                if 0.0 <= score <= 1.0:
                    return PointwiseResult(
                        failed=False,
                        score=score,
                        rationale=str(data.get("rationale", "")),
                        attempts=attempt,
                        raw=raw_all,
                    )
        return PointwiseResult(failed=True, attempts=2, raw=raw_all)

    def pairwise(self, question: str, first: str, second: str) -> PairwiseResult:
        prompt = self._pairwise_prompt(question, first, second)
        raw_all: list[str] = []
        for attempt in (1, 2):
            raw = self._call(prompt)
            raw_all.append(raw)
            data = _extract_json(raw)
            if data is not None and data.get("winner") in ("first", "second", "tie"):
                return PairwiseResult(
                    failed=False,
                    winner=data["winner"],
                    rationale=str(data.get("rationale", "")),
                    attempts=attempt,
                    raw=raw_all,
                )
        return PairwiseResult(failed=True, attempts=2, raw=raw_all)

    def pairwise_blind(self, question: str, answer_a: str, answer_b: str) -> BlindPairwiseResult:
        """Run both orderings; map back to A/B; flag positional disagreement."""
        ab = self.pairwise(question, answer_a, answer_b)  # first=A, second=B
        ba = self.pairwise(question, answer_b, answer_a)  # first=B, second=A

        if ab.failed or ba.failed:
            return BlindPairwiseResult(
                winner="tie", positional_disagreement=False, order_ab=ab, order_ba=ba, failed=True
            )

        winner_ab = {"first": "A", "second": "B", "tie": "tie"}[ab.winner]
        winner_ba = {"first": "B", "second": "A", "tie": "tie"}[ba.winner]

        if winner_ab == winner_ba:
            return BlindPairwiseResult(
                winner=winner_ab, positional_disagreement=False, order_ab=ab, order_ba=ba
            )
        # The two orderings disagree -> position bias / genuine tie; do not pick.
        return BlindPairwiseResult(
            winner="tie", positional_disagreement=True, order_ab=ab, order_ba=ba
        )

    # ------------------------------------------------------------------ #
    def _pointwise_prompt(self, question: str, answer: str, reference: str | None) -> str:
        ref = f"\nReference answer:\n{reference}\n" if reference else ""
        return (
            f"[judge:{self.model}:{self.prompt_version}] You are a strict evaluator.\n"
            f"Question:\n{question}\n\nAnswer:\n{answer}\n{ref}\n"
            'Respond ONLY with JSON: {"score": <0.0-1.0>, "rationale": "<short>"}'
        )

    def _pairwise_prompt(self, question: str, first: str, second: str) -> str:
        return (
            f"[judge:{self.model}:{self.prompt_version}] Compare two responses. "
            "Do not favour position or length.\n"
            f"Question:\n{question}\n\nResponse 1:\n{first}\n\nResponse 2:\n{second}\n\n"
            'Respond ONLY with JSON: {"winner": "first"|"second"|"tie", "rationale": "<short>"}'
        )
