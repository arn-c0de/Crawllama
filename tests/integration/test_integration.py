"""Integration tests for CrawlLama."""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def test_config():
    """Load test configuration."""
    config = {
        "llm": {
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model": "qwen2.5:3b",
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False
        },
        "cache": {
            "enabled": False
        },
        "rag": {
            "enabled": False
        }
    }
    return config


def test_config_loading():
    """Test configuration loading."""
    # Check for config.json first, fall back to config.json.example
    config_path = Path("config.json")
    if not config_path.exists():
        config_path = Path("config/config.json.example")
    
    assert config_path.exists(), "Neither config.json nor config.json.example found"

    with open(config_path) as f:
        config = json.load(f)

    assert "llm" in config
    assert "cache" in config
    assert "rag" in config


def test_agent_initialization(test_config):
    """Test agent initialization."""
    with patch("core.llm_client.OllamaClient") as mock_client:
        mock_instance = Mock()
        mock_instance._ensure_connection.return_value = True
        mock_client.return_value = mock_instance

        from core.agent import SearchAgent

        agent = SearchAgent(config=test_config, enable_web=False)
        assert agent is not None
        assert agent.enable_web is False


def test_directory_structure():
    """Test that all required directories exist or can be created."""
    required_dirs = [
        "core",
        "tools",
        "utils",
        "tests",
        "data",
        "logs"
    ]

    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        assert dir_path.exists() or dir_path.mkdir(parents=True, exist_ok=True)
