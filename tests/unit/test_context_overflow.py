"""Tests for context window overflow prevention."""
import pytest

from core.context_manager import ContextManager
from core.model_registry import get_model_context_window


def test_budget_reserves_response_tokens():
    """Ensure response tokens are reserved from total context window."""
    cm = ContextManager(
        max_tokens=1000,
        model_name="gpt-4o-mini",
        model_context_window=1000,
        response_tokens=200,
        provider="openai",
    )

    budget = cm.allocate_budget("System", "User question")

    assert budget.total_window == 1000
    assert budget.response_reserved == 200
    assert budget.prompt_budget == 800
    assert budget.context_available <= budget.prompt_budget


def test_budget_with_large_system_prompt():
    """Large system prompts should leave zero context budget."""
    cm = ContextManager(
        max_tokens=300,
        model_name="gpt-4o-mini",
        model_context_window=300,
        response_tokens=100,
        provider="openai",
    )

    large_system = "x" * 2000
    budget = cm.allocate_budget(large_system, "User")

    assert budget.context_available == 0


def test_prioritized_context_respects_priority():
    """Higher priority sections should appear before lower priority ones."""
    cm = ContextManager(model_name="gpt-4o-mini", model_context_window=500)

    sections = [
        {"label": "High", "content": "alpha " * 20, "priority": 1},
        {"label": "Medium", "content": "beta " * 20, "priority": 2},
        {"label": "Low", "content": "gamma " * 20, "priority": 3},
    ]

    output = cm.build_prioritized_context(sections, total_budget=200)

    assert "High" in output
    assert "Medium" in output
    assert output.find("High") < output.find("Medium")


def test_prioritized_context_drops_low_priority():
    """Low priority sections should be dropped when budget is tight."""
    cm = ContextManager(model_name="gpt-4o-mini", model_context_window=200)

    sections = [
        {"label": "High", "content": "alpha " * 20, "priority": 1},
        {"label": "Low", "content": "gamma " * 20, "priority": 3},
    ]

    output = cm.build_prioritized_context(sections, total_budget=25)

    assert "Low" not in output


def test_build_prompt_never_exceeds_budget():
    """Prompt should never exceed the allocated prompt budget."""
    cm = ContextManager(
        max_tokens=300,
        model_name="gpt-4o-mini",
        model_context_window=300,
        response_tokens=80,
        provider="openai",
    )

    system_prompt = "System instruction. " * 30
    user_query = "What is the summary?"
    context = "Context data. " * 200

    prompt = cm.build_prompt(
        system_prompt=system_prompt,
        user_query=user_query,
        context=context,
    )

    assert cm.estimate_tokens(prompt) <= cm.prompt_budget


def test_model_registry_known_and_unknown():
    """Known models should map to fixed windows; unknown should use provider default."""
    assert get_model_context_window("gpt-4o-mini", "openai") == 128000
    assert get_model_context_window("unknown-model", "openai") == 4096


if __name__ == "__main__":
    pytest.main([__file__])


def test_split_into_chunks_terminates_with_large_overlap():
    """Forward-progress guard: overlap >= chunk size must not loop forever."""
    cm = ContextManager(model_name="gpt-4o-mini", model_context_window=500)
    text = ("Short. " * 500).strip()

    chunks = cm.split_into_chunks(text, chunk_size=10, overlap=10)

    assert chunks  # terminated and produced output
    rebuilt = "".join(chunks)
    assert "Short." in rebuilt


def test_split_into_chunks_overlap_smaller_than_chunk():
    """Normal configuration still chunks the full text in order."""
    cm = ContextManager(model_name="gpt-4o-mini", model_context_window=500)
    text = "A" * 5000

    chunks = cm.split_into_chunks(text, chunk_size=100, overlap=10)

    assert all(chunks)
    assert chunks[0].startswith("A")
    assert sum(len(c) for c in chunks) >= 5000  # full coverage incl. overlap
