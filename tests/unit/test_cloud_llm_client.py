"""Tests for cloud LLM clients."""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from core.cloud_llm_client import (
    OpenAIClient,
    AnthropicClient,
    GroqClient,
    get_llm_client
)

# Check if optional packages are available
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


@pytest.mark.skipif(not HAS_OPENAI, reason="openai package not installed")
class TestOpenAIClient:
    """Test OpenAI client."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    @patch("openai.OpenAI")
    def test_initialization(self, mock_openai):
        """Test OpenAI client initialization."""
        client = OpenAIClient(model="gpt-4")
        assert client.model == "gpt-4"
        assert client.api_key == "test_key"
        mock_openai.assert_called_once_with(api_key="test_key")

    def test_missing_api_key(self):
        """Test error when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                OpenAIClient()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    @patch("openai.OpenAI")
    def test_generate(self, mock_openai_class):
        """Test text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Generated text"))]
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenAIClient()
        result = client.generate("Test prompt", system_prompt="System instruction")

        assert result == "Generated text"
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    @patch("openai.OpenAI")
    def test_chat(self, mock_openai_class):
        """Test chat completion."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Chat response"))]
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenAIClient()
        messages = [{"role": "user", "content": "Hello"}]
        result = client.chat(messages)

        assert result == "Chat response"


@pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
class TestAnthropicClient:
    """Test Anthropic client."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"})
    @patch("anthropic.Anthropic")
    def test_initialization(self, mock_anthropic):
        """Test Anthropic client initialization."""
        client = AnthropicClient(model="claude-3-opus-20240229")
        assert client.model == "claude-3-opus-20240229"
        assert client.api_key == "test_key"
        mock_anthropic.assert_called_once_with(api_key="test_key")

    def test_missing_api_key(self):
        """Test error when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Anthropic API key required"):
                AnthropicClient()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"})
    @patch("anthropic.Anthropic")
    def test_generate(self, mock_anthropic_class):
        """Test text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="Generated text")]
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = AnthropicClient()
        result = client.generate("Test prompt", system_prompt="System instruction")

        assert result == "Generated text"
        mock_client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"})
    @patch("anthropic.Anthropic")
    def test_chat(self, mock_anthropic_class):
        """Test chat completion."""
        # Mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="Chat response")]
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = AnthropicClient()
        messages = [{"role": "user", "content": "Hello"}]
        result = client.chat(messages)

        assert result == "Chat response"


@pytest.mark.skipif(not HAS_GROQ, reason="groq package not installed")
class TestGroqClient:
    """Test Groq client."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test_key"})
    @patch("groq.Groq")
    def test_initialization(self, mock_groq):
        """Test Groq client initialization."""
        client = GroqClient(model="llama2-70b-4096")
        assert client.model == "llama2-70b-4096"
        assert client.api_key == "test_key"
        mock_groq.assert_called_once_with(api_key="test_key")

    def test_missing_api_key(self):
        """Test error when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Groq API key required"):
                GroqClient()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test_key"})
    @patch("groq.Groq")
    def test_generate(self, mock_groq_class):
        """Test text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Generated text"))]
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class.return_value = mock_client

        client = GroqClient()
        result = client.generate("Test prompt", system_prompt="System instruction")

        assert result == "Generated text"
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test_key"})
    @patch("groq.Groq")
    def test_chat(self, mock_groq_class):
        """Test chat completion."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Chat response"))]
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class.return_value = mock_client

        client = GroqClient()
        messages = [{"role": "user", "content": "Hello"}]
        result = client.chat(messages)

        assert result == "Chat response"


class TestGetLLMClient:
    """Test LLM client factory function."""

    @pytest.mark.skipif(not HAS_OPENAI, reason="openai package not installed")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    @patch("openai.OpenAI")
    def test_get_openai_client(self, mock_openai):
        """Test getting OpenAI client."""
        client = get_llm_client("openai", model="gpt-4")
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4"

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"})
    @patch("anthropic.Anthropic")
    def test_get_anthropic_client(self, mock_anthropic):
        """Test getting Anthropic client."""
        client = get_llm_client("anthropic", model="claude-3-opus-20240229")
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-3-opus-20240229"

    @pytest.mark.skipif(not HAS_GROQ, reason="groq package not installed")
    @patch.dict(os.environ, {"GROQ_API_KEY": "test_key"})
    @patch("groq.Groq")
    def test_get_groq_client(self, mock_groq):
        """Test getting Groq client."""
        client = get_llm_client("groq", model="mixtral-8x7b-32768")
        assert isinstance(client, GroqClient)
        assert client.model == "mixtral-8x7b-32768"

    @patch("core.llm_client.OllamaClient")
    def test_get_ollama_client(self, mock_ollama):
        """Test getting Ollama client."""
        client = get_llm_client("ollama", model="qwen2.5:3b")
        # Returns OllamaClient instance
        mock_ollama.assert_called_once()

    def test_unknown_provider(self):
        """Test error with unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_llm_client("unknown_provider")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
