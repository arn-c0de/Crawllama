"""Cloud LLM clients for OpenAI, Anthropic, and Groq."""
import os
import logging
from typing import Optional, Dict, Any, Iterator
from abc import ABC, abstractmethod

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
        max_tokens: int = 4096
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

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"OpenAI client initialized: {model}")
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, **kwargs)

    def chat(self, messages: list, **kwargs) -> str:
        """Chat completion with message history."""
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
        max_tokens: int = 4096
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

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
            logger.info(f"Anthropic client initialized: {model}")
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate completion from prompt."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, system_prompt=system_prompt, **kwargs)

    def chat(self, messages: list, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Chat completion with message history."""
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
        max_tokens: int = 4096
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

        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Groq client initialized: {model}")
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
