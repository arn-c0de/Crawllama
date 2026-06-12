"""Tests for LangGraph reasoning-state semantics and LLM marker parsing."""
from typing import get_type_hints

from core.langgraph_agent import ReasoningState, _parse_marker_flag, _parse_marker_score


def test_reasoning_state_has_no_add_reducers():
    """The nodes mutate lists in place and return the full state; an
    operator.add reducer would re-concatenate the returned list onto the
    channel and duplicate context/queries/path on every hop."""
    hints = get_type_hints(ReasoningState, include_extras=True)
    for field in ("context", "search_queries", "reasoning_path"):
        assert not getattr(hints[field], "__metadata__", None), (
            f"{field} must not declare a reducer (see ReasoningState docstring)"
        )


class TestParseMarkerFlag:
    def test_yes(self):
        assert _parse_marker_flag("COMPLETE: YES\nrest", "COMPLETE:", default=False) is True

    def test_no(self):
        assert _parse_marker_flag("COMPLETE: NO\nrest", "COMPLETE:", default=True) is False

    def test_missing_marker_returns_default(self):
        assert _parse_marker_flag("no markers here", "COMPLETE:", default=True) is True
        assert _parse_marker_flag("no markers here", "COMPLETE:", default=False) is False

    def test_marker_at_end_of_string(self):
        assert _parse_marker_flag("COMPLETE:", "COMPLETE:", default=False) is False


class TestParseMarkerScore:
    def test_plain_number(self):
        assert _parse_marker_score("CONFIDENCE: 85\n", "CONFIDENCE:", default=0.5) == 0.85

    def test_number_with_text(self):
        assert _parse_marker_score("QUALITY: about 70 percent\n", "QUALITY:", default=0.5) == 0.70

    def test_missing_marker_returns_default(self):
        assert _parse_marker_score("nothing", "CONFIDENCE:", default=0.4) == 0.4

    def test_non_numeric_returns_default(self):
        assert _parse_marker_score("CONFIDENCE: not applicable\n", "CONFIDENCE:", default=0.3) == 0.3
