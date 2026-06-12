"""Cloud LLM clients for OpenAI, Anthropic, and Groq."""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from core.model_registry import get_model_context_window
from utils.tor_mode import sdk_http_client

logger = logging.getLogger("crawllama")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
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
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            model: Model name (gpt-4o-mini, gpt-4o, gpt-4.1, ...)
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
            # In Tor mode, route SDK traffic through the Tor SOCKS proxy
            self.client = OpenAI(api_key=self.api_key, http_client=sdk_http_client())
            logger.info(f"OpenAI client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai") from None

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
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


# Models that reject sampling parameters (temperature/top_p/top_k return 400).
# Applies to Claude Opus 4.7 and newer; steer these models via prompting.
_NO_SAMPLING_MODEL_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-fable",
    "claude-mythos",
)


def _accepts_sampling_params(model: str) -> bool:
    """Whether the model accepts temperature/top_p sampling parameters."""
    return not model.startswith(_NO_SAMPLING_MODEL_PREFIXES)


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-opus-4-8",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            model: Model name (claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5, ...)
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
            # In Tor mode, route SDK traffic through the Tor SOCKS proxy
            self.client = Anthropic(api_key=self.api_key, http_client=sdk_http_client())
            logger.info(f"Anthropic client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic") from None

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, system_prompt=system_prompt, **kwargs)

    def chat(self, messages: list, system_prompt: str | None = None, **kwargs) -> str:
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
            request: dict = {
                "model": self.model,
                "messages": messages,
                "system": system_prompt or "",
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            }
            if _accepts_sampling_params(self.model):
                request["temperature"] = kwargs.get("temperature", self.temperature)
            response = self.client.messages.create(**request)
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class GroqClient(BaseLLMClient):
    """Groq fast inference client."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 0
    ):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key (or from GROQ_API_KEY env var)
            model: Model name (llama-3.3-70b-versatile, llama-3.1-8b-instant, ...)
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
            # In Tor mode, route SDK traffic through the Tor SOCKS proxy
            self.client = Groq(api_key=self.api_key, http_client=sdk_http_client())
            logger.info(f"Groq client initialized: {model} (context_window={self.context_window})")
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq") from None

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
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
    llm_config: dict[str, Any],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    context_window: int | None = None,
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
        kwargs: dict[str, Any] = {
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
        "model": model or llm_config.get("model", "gpt-4o-mini"),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if context_window is not None:
        kwargs["context_window"] = context_window
    return get_llm_client(provider, **kwargs)
