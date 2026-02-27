"""Model context window registry.

Centralized knowledge of model context window sizes so that
ContextManager and LLM clients can enforce proper token budgets.
"""
import logging
from typing import Optional

logger = logging.getLogger("crawllama")

# Model name -> total context window in tokens
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # OpenAI
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    # Anthropic
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    # Groq
    "mixtral-8x7b-32768": 32768,
    "llama2-70b-4096": 4096,
    "gemma-7b-it": 8192,
    # Ollama local models
    "qwen2.5:3b": 32768,
    "qwen2.5:7b": 32768,
    "qwen3:8b": 32768,
    "gpt-oss": 131072,
    "deepseek-r1:8b": 32768,
    "llama3:7b": 8192,
    "llama3:8b": 8192,
    "llama3.1:8b": 131072,
    "mistral:7b": 8192,
    "phi3:mini": 4096,
}

# Conservative fallback per provider (used when model is unknown)
PROVIDER_DEFAULTS: dict[str, int] = {
    "openai": 4096,
    "anthropic": 200000,
    "groq": 32768,
    "ollama": 4096,
}


def get_model_context_window(
    model_name: str,
    provider: str = "ollama",
    config_override: Optional[int] = None,
) -> int:
    """Get the context window size for a model.

    Priority:
      1. config_override (user explicitly set ``context_window`` in config)
      2. Exact match in MODEL_CONTEXT_WINDOWS
      3. Prefix match (e.g. "gpt-4-0613" matches "gpt-4")
      4. PROVIDER_DEFAULTS fallback

    Args:
        model_name: Model identifier (e.g. "gpt-4o-mini", "qwen2.5:3b")
        provider: Provider name ("openai", "ollama", ...)
        config_override: Optional user-configured value (0 or None = auto)

    Returns:
        Context window size in tokens
    """
    if config_override and config_override > 0:
        return config_override

    # Exact match
    if model_name in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_name]

    # Prefix match (handles versioned models like "gpt-4-0613")
    for known_model, window in MODEL_CONTEXT_WINDOWS.items():
        if model_name.startswith(known_model):
            return window

    default = PROVIDER_DEFAULTS.get(provider, 4096)
    logger.warning(
        "Unknown model '%s' (provider '%s'). "
        "Using default context window: %d. "
        "Set 'context_window' in config.json llm section to override.",
        model_name, provider, default,
    )
    return default
