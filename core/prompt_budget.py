"""Pre-flight prompt truncation shared by the local and cloud LLM clients.

Uses a fast 4-characters-per-token estimate so the client layer does not need
tiktoken. Only the last user message is shortened, and it is cut in the
middle: prompts built by the agent put the retrieved context first and the
actual question last, so keeping head and tail preserves the question.
"""
import logging

logger = logging.getLogger("crawllama")

CHARS_PER_TOKEN = 4
TRUNCATION_MARKER = "\n...[truncated]...\n"


def truncate_middle(text: str, max_chars: int) -> str:
    """Shorten ``text`` to ``max_chars`` by removing its middle part."""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_MARKER):
        return text[-max_chars:] if max_chars > 0 else ""
    keep = max_chars - len(TRUNCATION_MARKER)
    head = keep // 2
    tail = keep - head
    return text[:head] + TRUNCATION_MARKER + text[len(text) - tail:]


def fit_messages_to_budget(
    messages: list[dict],
    context_window: int,
    max_tokens: int,
    system_prompt: str | None = None,
) -> list[dict]:
    """Return a copy of ``messages`` whose estimated size fits the input budget.

    The input budget is ``context_window - max_tokens`` (the rest is reserved
    for the response). Everything except the last user message, including a
    separate ``system_prompt``, counts against the budget unchanged.
    The caller's message dicts are never modified.
    """
    max_input_chars = (context_window - max_tokens) * CHARS_PER_TOKEN
    if context_window <= 0 or max_input_chars <= 0:
        return messages

    total_chars = sum(len(m.get("content") or "") for m in messages)
    total_chars += len(system_prompt or "")
    if total_chars <= max_input_chars:
        return messages

    last_user = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "user"),
        None,
    )
    if last_user is None:
        return messages

    logger.warning(
        "Pre-flight: ~%d tokens exceeds input budget ~%d. Truncating.",
        total_chars // CHARS_PER_TOKEN, max_input_chars // CHARS_PER_TOKEN,
    )
    content = messages[last_user].get("content") or ""
    other_chars = total_chars - len(content)
    allowed = max(0, max_input_chars - other_chars)

    fitted = [dict(m) for m in messages]
    fitted[last_user]["content"] = truncate_middle(content, allowed)
    return fitted


def fit_prompt_to_budget(
    prompt: str, context_window: int, max_tokens: int, system_prompt: str | None = None
) -> str:
    """String variant of :func:`fit_messages_to_budget` for single prompts."""
    fitted = fit_messages_to_budget(
        [{"role": "user", "content": prompt}], context_window, max_tokens, system_prompt
    )
    return fitted[0]["content"]
