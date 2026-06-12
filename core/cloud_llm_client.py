"""Cloud LLM clients for OpenAI, Anthropic, and Groq."""
import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from core.model_registry import get_model_context_window

logger = logging.getLogger("crawllama")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        pass

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        """Chat completion with message history."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            model: Model name (gpt-3.5-turbo, gpt-4, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = get_model_context_window(
            model,
            "openai",
            context_window if context_window > 0 else None,
        )

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"OpenAI client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, **kwargs)

    def _preflight_truncate(self, messages: list) -> list:
        """Truncate the last user message if total tokens exceed input budget."""
        total_content = " ".join(m.get("content", "") for m in messages)
        estimated_tokens = len(total_content) // 4
        max_input = self.context_window - self.max_tokens

        if max_input > 0 and estimated_tokens > max_input:
            logger.warning(
                "Pre-flight: ~%d tokens exceeds input budget ~%d. Truncating.",
                estimated_tokens, max_input,
            )
            max_chars = max_input * 4
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] = msg["content"][:max_chars]
                    break
        return messages

    def chat(self, messages: list, **kwargs) -> str:
        """Chat completion with message history."""
        messages = self._preflight_truncate(messages)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            model: Model name (claude-3-opus, claude-3-sonnet, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY in .env")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = get_model_context_window(
            model,
            "anthropic",
            context_window if context_window > 0 else None,
        )

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
            logger.info(f"Anthropic client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, system_prompt=system_prompt, **kwargs)

    def chat(self, messages: list, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Chat completion with message history."""
        # Pre-flight token check
        total_content = " ".join(m.get("content", "") for m in messages)
        if system_prompt:
            total_content += " " + system_prompt
        estimated_tokens = len(total_content) // 4
        max_input = self.context_window - self.max_tokens

        if max_input > 0 and estimated_tokens > max_input:
            logger.warning(
                "Pre-flight: ~%d tokens exceeds input budget ~%d. Truncating.",
                estimated_tokens, max_input,
            )
            max_chars = max_input * 4
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] = msg["content"][:max_chars]
                    break

        try:
            response = self.client.messages.create(
                model=self.model,
                messages=messages,
                system=system_prompt or "",
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class GroqClient(BaseLLMClient):
    """Groq fast inference client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mixtral-8x7b-32768",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key (or from GROQ_API_KEY env var)
            model: Model name (mixtral-8x7b-32768, llama2-70b-4096, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY in .env")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = get_model_context_window(
            model,
            "groq",
            context_window if context_window > 0 else None,
        )

        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Groq client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, **kwargs)

    def chat(self, messages: list, **kwargs) -> str:
        """Chat completion with message history."""
        # Pre-flight token check
        total_content = " ".join(m.get("content", "") for m in messages)
        estimated_tokens = len(total_content) // 4
        max_input = self.context_window - self.max_tokens

        if max_input > 0 and estimated_tokens > max_input:
            logger.warning(
                "Pre-flight: ~%d tokens exceeds input budget ~%d. Truncating.",
                estimated_tokens, max_input,
            )
            max_chars = max_input * 4
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] = msg["content"][:max_chars]
                    break

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


def get_llm_client(provider: str, **kwargs) -> BaseLLMClient:
    """
    Factory function to get LLM client by provider name.

    Args:
        provider: Provider name ('openai', 'anthropic', 'groq', 'ollama')
        **kwargs: Additional arguments for client initialization

    Returns:
        LLM client instance

    Example:
        >>> client = get_llm_client('openai', model='gpt-4')
        >>> response = client.generate("Hello, world!")
    """
    provider = provider.lower()

    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "anthropic":
        return AnthropicClient(**kwargs)
    elif provider == "groq":
        return GroqClient(**kwargs)
    elif provider == "ollama":
        from core.llm_client import OllamaClient
        return OllamaClient(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: openai, anthropic, groq, ollama")


def create_llm_client_from_config(
    llm_config: Dict[str, Any],
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    context_window: Optional[int] = None,
) -> BaseLLMClient:
    """Create an Ollama or cloud LLM client from a config "llm" section.

    This is the single place that knows how to turn configuration into a
    client; every entry point (CLI, API, agents) should use it so client
    construction cannot drift between them.

    The keyword arguments override the config values; agents use them to pass
    token budgets computed from the model registry.
    """
    provider = llm_config.get("provider", "ollama").lower()
    temperature = llm_config.get("temperature", 0.7)
    if max_tokens is None:
        max_tokens = llm_config.get("max_tokens", 4096)

    if provider == "ollama":
        kwargs: Dict[str, Any] = {
            "base_url": llm_config.get("base_url", "http://127.0.0.1:11434"),
            "model": model or llm_config.get("model", "qwen2.5:3b"),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": llm_config.get("timeout", 120),
            "max_requests_per_minute": llm_config.get("max_requests_per_minute", 60),
        }
        if context_window is not None:
            kwargs["num_ctx"] = context_window
        return get_llm_client("ollama", **kwargs)

    kwargs = {
        "model": model or llm_config.get("model", "gpt-3.5-turbo"),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if context_window is not None:
        kwargs["context_window"] = context_window
    return get_llm_client(provider, **kwargs)
