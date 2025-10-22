"""Tests for Ollama LLM client."""
import pytest
from unittest.mock import Mock, patch
from core.llm_client import OllamaClient


@pytest.fixture
def mock_ollama():
    """Mock Ollama client."""
    with patch("core.llm_client.requests") as mock_requests:
        # Mock successful connection
        mock_response = Mock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen2.5:3b"
        )

        yield client, mock_requests


def test_ollama_client_initialization():
    """Test OllamaClient initialization."""
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:3b",
        temperature=0.7
    )

    assert client.base_url == "http://localhost:11434"
    assert client.model == "qwen2.5:3b"
    assert client.temperature == 0.7


def test_generate_basic(mock_ollama):
    """Test basic generation."""
    client, mock_requests = mock_ollama

    # Mock generation response
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test response"}
    mock_response.raise_for_status = Mock()
    mock_requests.post.return_value = mock_response

    result = client.generate("Test prompt", stream=False)
    assert result == "Test response"


def test_connection_check(mock_ollama):
    """Test connection check."""
    client, _ = mock_ollama
    assert client._ensure_connection() is True
