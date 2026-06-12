"""Token management and context handling for LLMs."""
import logging
from dataclasses import dataclass
from typing import Any

from core.model_registry import get_model_context_window
from utils.text_cleaner import get_text_cleaner

logger = logging.getLogger("crawllama")


@dataclass
class TokenBudget:
    """Token budget allocation for a prompt."""

    total_window: int
    response_reserved: int
    system_prompt: int
    user_query: int
    context_available: int  # What remains for context sections

    @property
    def prompt_budget(self) -> int:
        """Total tokens available for the prompt (window minus response)."""
        return self.total_window - self.response_reserved


class ContextManager:
    """Manages context window and token limits with accurate token counting."""

    def __init__(
        self,
        max_tokens: int = 16000,
        model_name: str = "gpt-3.5-turbo",
        model_context_window: int = 0,
        response_tokens: int = 0,
        provider: str = "ollama",
    ):
        """
        Initialize context manager.

        Args:
            max_tokens: Legacy max-tokens cap (used as upper bound for context)
            model_name: Model name for tokenizer selection
            model_context_window: Explicit context window override (0 = auto)
            response_tokens: Tokens to reserve for the LLM response (0 = auto)
            provider: LLM provider name for model registry lookup
        """
        self.max_tokens = max_tokens
        self.model_name = model_name

        # Use TextCleaner for all text operations
        self.text_cleaner = get_text_cleaner(model_name)

        # Resolve actual model context window
        self.model_context_window = get_model_context_window(
            model_name, provider, model_context_window if model_context_window > 0 else None
        )

        # Response token reservation (default: 20% of window, min 256, capped to window)
        if response_tokens > 0:
            self.response_tokens = min(response_tokens, self.model_context_window)
        else:
            self.response_tokens = min(
                self.model_context_window,
                min(max_tokens, max(256, self.model_context_window // 5)),
            )

        # Total tokens available for the entire prompt (everything except response)
        self.prompt_budget = max(0, self.model_context_window - self.response_tokens)

        logger.info(
            "Context manager: window=%d, response_reserved=%d, prompt_budget=%d, model=%s",
            self.model_context_window, self.response_tokens, self.prompt_budget, model_name,
        )

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text using tiktoken or fallback.

        Args:
            text: Input text

        Returns:
            Accurate token count (if tiktoken available) or estimated count
        """
        return self.text_cleaner.estimate_tokens(text)

    def truncate(self, text: str, max_tokens: int | None = None) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Max tokens (uses instance max if not specified)

        Returns:
            Truncated text
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        return self.text_cleaner.truncate_by_tokens(text, max_tokens)

    def split_into_chunks(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> list[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to split
            chunk_size: Size of each chunk in tokens
            overlap: Overlap between chunks in tokens

        Returns:
            List of text chunks
        """
        # Convert tokens to characters (approximate: 4 chars per token)
        CHARS_PER_TOKEN = 4
        chunk_chars = chunk_size * CHARS_PER_TOKEN
        overlap_chars = overlap * CHARS_PER_TOKEN

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_chars
            chunk = text[start:end]

            # Try to break at sentence boundary
            actual_end = end
            if end < len(text):
                # Look for sentence end
                last_period = chunk.rfind('.')
                last_question = chunk.rfind('?')
                last_exclaim = chunk.rfind('!')

                sentence_end = max(last_period, last_question, last_exclaim)

                if sentence_end > chunk_chars // 2:
                    chunk = chunk[:sentence_end + 1]
                    actual_end = start + sentence_end + 1

            chunks.append(chunk.strip())
            # Use actual_end (after sentence boundary adjustment) for correct
            # overlap. The max() guard guarantees forward progress: with a
            # large overlap and an early sentence break, the next start could
            # otherwise move backwards and loop forever.
            start = max(actual_end - overlap_chars, start + 1)

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks

    def fits_in_context(self, text: str, max_tokens: int | None = None) -> bool:
        """
        Check if text fits within token limit.

        Args:
            text: Text to check
            max_tokens: Max tokens (uses instance max if not specified)

        Returns:
            True if fits, False otherwise
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        return self.estimate_tokens(text) <= max_tokens

    # ------------------------------------------------------------------
    # Budget-aware prompt building
    # ------------------------------------------------------------------

    def allocate_budget(
        self,
        system_prompt: str,
        user_query: str,
        max_context_tokens: int = 0,
    ) -> TokenBudget:
        """Allocate token budget with priority-based reservation.

        Priority (highest first):
          1. Response tokens (reserved, not part of prompt)
          2. User query (never truncated)
          3. System prompt (never truncated)
          4. Context (gets whatever remains, capped by *max_context_tokens*)

        Args:
            system_prompt: The system prompt text
            user_query: The user's query text
            max_context_tokens: Optional hard cap on context tokens

        Returns:
            TokenBudget describing the allocation
        """
        system_tokens = self.estimate_tokens(system_prompt)
        query_tokens = self.estimate_tokens(user_query)
        overhead = 20  # formatting tokens (newlines, **Context:**, etc.)

        context_available = self.prompt_budget - system_tokens - query_tokens - overhead
        context_available = max(0, context_available)

        if max_context_tokens > 0:
            context_available = min(context_available, max_context_tokens)

        budget = TokenBudget(
            total_window=self.model_context_window,
            response_reserved=self.response_tokens,
            system_prompt=system_tokens,
            user_query=query_tokens,
            context_available=context_available,
        )

        if context_available <= 0:
            logger.warning(
                "No token budget for context! system=%d, query=%d, prompt_budget=%d",
                system_tokens, query_tokens, self.prompt_budget,
            )

        return budget

    def build_prompt(
        self,
        system_prompt: str,
        user_query: str,
        context: str | None = None,
        max_context_tokens: int = 4000,
    ) -> str:
        """Build complete prompt with budget-aware truncation.

        The method signature is unchanged for backward compatibility.
        Internally it now uses :meth:`allocate_budget` to guarantee the
        total prompt fits within ``prompt_budget`` (= model window minus
        response reservation).

        Args:
            system_prompt: System instructions
            user_query: User's question
            context: Optional context information
            max_context_tokens: Max tokens for the context section

        Returns:
            Complete prompt string
        """
        budget = self.allocate_budget(system_prompt, user_query, max_context_tokens)

        prompt_parts = [system_prompt]

        if context and budget.context_available > 0:
            context = self.truncate(context, budget.context_available)
            prompt_parts.append(f"\n\n**Context:**\n{context}")
        elif context and budget.context_available <= 0:
            logger.warning("Context dropped entirely - no budget remaining")

        prompt_parts.append(f"\n\n**Question:** {user_query}")

        full_prompt = "\n".join(prompt_parts)

        # Final safety check
        prompt_tokens = self.estimate_tokens(full_prompt)
        if prompt_tokens > self.prompt_budget:
            logger.warning(
                "Prompt exceeds budget after allocation: %d > %d. Force-truncating.",
                prompt_tokens, self.prompt_budget,
            )
            full_prompt = self.truncate(full_prompt, self.prompt_budget)

        return full_prompt

    def build_prioritized_context(
        self,
        sections: list[dict[str, Any]],
        total_budget: int,
    ) -> str:
        """Build context from prioritized sections within a token budget.

        Each section is a dict with:
          - ``label``:    str  – heading (e.g. "Recent Q&A")
          - ``content``:  str  – the text
          - ``priority``: int  – lower = higher priority (1 = highest)

        Sections are included in priority order.  When budget runs out,
        remaining sections are truncated or dropped entirely.

        Args:
            sections: List of section dicts
            total_budget: Total tokens available for all context

        Returns:
            Combined context string
        """
        if not sections or total_budget <= 0:
            return ""

        sorted_sections = sorted(sections, key=lambda s: s.get("priority", 99))

        remaining = total_budget
        allocated: list[str] = []

        for section in sorted_sections:
            if remaining <= 50:  # not enough for meaningful content
                logger.debug("Dropping section '%s' - no budget left", section["label"])
                break

            content = section["content"]
            content_tokens = self.estimate_tokens(content)
            label_overhead = 10  # tokens for the label line

            if content_tokens + label_overhead <= remaining:
                # Fits entirely
                allocated.append(f"--- {section['label']} ---\n{content}")
                remaining -= content_tokens + label_overhead
            else:
                # Truncate to fit
                truncated = self.truncate(content, remaining - label_overhead)
                allocated.append(f"--- {section['label']} (truncated) ---\n{truncated}")
                remaining = 0

        return "\n\n".join(allocated)
