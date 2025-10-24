"""Token management and context handling for LLMs."""
import logging
from typing import List, Optional
from utils.text_cleaner import get_text_cleaner

logger = logging.getLogger("crawllama")


class ContextManager:
    """Manages context window and token limits with accurate token counting."""

    def __init__(self, max_tokens: int = 16000, model_name: str = "gpt-3.5-turbo"):
        """
        Initialize context manager.

        Args:
            max_tokens: Maximum tokens allowed in context (increased default for RTX 3080)
            model_name: Model name for tokenizer selection (default: gpt-3.5-turbo for cl100k_base)
        """
        self.max_tokens = max_tokens
        self.model_name = model_name
        
        # Use TextCleaner for all text operations
        self.text_cleaner = get_text_cleaner(model_name)
        
        logger.info(f"Context manager initialized: max_tokens={max_tokens}, model={model_name}")

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text using tiktoken or fallback.

        Args:
            text: Input text

        Returns:
            Accurate token count (if tiktoken available) or estimated count
        """
        return self.text_cleaner.estimate_tokens(text)

    def truncate(self, text: str, max_tokens: Optional[int] = None) -> str:
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
    ) -> List[str]:
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
            if end < len(text):
                # Look for sentence end
                last_period = chunk.rfind('.')
                last_question = chunk.rfind('?')
                last_exclaim = chunk.rfind('!')

                sentence_end = max(last_period, last_question, last_exclaim)

                if sentence_end > chunk_chars // 2:
                    chunk = chunk[:sentence_end + 1]

            chunks.append(chunk.strip())
            start = end - overlap_chars

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks

    def fits_in_context(self, text: str, max_tokens: Optional[int] = None) -> bool:
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

    def build_prompt(
        self,
        system_prompt: str,
        user_query: str,
        context: Optional[str] = None,
        max_context_tokens: int = 4000
    ) -> str:
        """
        Build complete prompt with system, context, and user query.

        Args:
            system_prompt: System instructions
            user_query: User's question
            context: Optional context information
            max_context_tokens: Max tokens for context section (increased default for RTX 3080 16k)

        Returns:
            Complete prompt string
        """
        prompt_parts = [system_prompt]

        if context:
            # Truncate context if needed
            context = self.truncate(context, max_context_tokens)
            prompt_parts.append(f"\n\n**Context:**\n{context}")

        prompt_parts.append(f"\n\n**Question:** {user_query}")

        full_prompt = "\n".join(prompt_parts)

        # Final check
        if not self.fits_in_context(full_prompt):
            logger.warning("Prompt exceeds token limit, truncating")
            full_prompt = self.truncate(full_prompt)

        return full_prompt
