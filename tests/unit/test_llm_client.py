"""Tests for Ollama LLM client."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import Mock, patch

import pytest

from core.llm_client import OllamaClient


@pytest.fixture
def mock_ollama():
    """Mock Ollama client: all HTTP goes through the client's pooled session."""
    with patch("core.llm_client.requests.Session") as mock_session_cls:
        mock_session = mock_session_cls.return_value

        # Mock successful connection
        mock_response = Mock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen2.5:3b"
        )

        yield client, mock_session


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
    client, mock_session = mock_ollama

    # Mock generation response
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Test response"}
    mock_response.raise_for_status = Mock()
    mock_session.post.return_value = mock_response

    result = client.generate("Test prompt", stream=False)
    assert result == "Test response"


def test_connection_check(mock_ollama):
    """Test connection check."""
    client, mock_session = mock_ollama

    # Mock the connection check
    mock_response = Mock()
    mock_response.json.return_value = {"models": []}
    mock_response.raise_for_status = Mock()
    mock_session.get.return_value = mock_response

    assert client._ensure_connection() is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])