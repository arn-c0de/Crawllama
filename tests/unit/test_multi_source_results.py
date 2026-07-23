"""Regression: multi-source result references must synthesize when >=1 page loads.

Bug (`<source 1 2 3 4`): a successfully loaded page's content is wrapped in
``[EXTERNAL_WEB_CONTENT_START]…``, so the old success check
``not content.startswith('[')`` treated *every* page — including the loaded
ones — as failed. The handler then returned "All N pages could not be loaded"
and dumped raw page text instead of running the LLM synthesis.

The fix uses an explicit per-page ``ok`` flag. These tests are fully mocked
(no network, no real LLM).
"""

from unittest.mock import Mock, patch

_CONFIG = {
    "llm": {"provider": "ollama", "model": "test", "stream": False},
    "search": {"region": "de-de", "max_results": 5},
    "osint": {"max_results": 5, "safesearch": "strict"},
    "cache": {"enabled": False},
    "rag": {"enabled": False},
    "security": {"max_context_length": 2000},
    "paths": {"session_file": "data/session.json"},
}

_RESULTS = [
    {"title": "Example One", "url": "https://example.com/"},
    {"title": "Example Two", "url": "https://example.org/"},
    {"title": "Example", "url": "https://example.com/"},
    {"title": "LinkedIn", "url": "https://de.linkedin.com/"},
]


def _make_agent():
    mock_llm = Mock()
    mock_llm.generate = Mock(return_value="SYNTHESIZED MULTI-SOURCE ANSWER")
    with patch("core.llm_client.OllamaClient", return_value=mock_llm):
        from core.agent import SearchAgent

        agent = SearchAgent(config=_CONFIG, enable_web=True, debug=False)
    agent.llm = mock_llm  # ensure the synthesis call hits the mock
    agent.session.last_search_results = list(_RESULTS)
    return agent, mock_llm


def test_synthesizes_when_some_pages_load(monkeypatch):
    """3 of 4 pages load (LinkedIn blocked) -> synthesis runs, no false error."""

    def fake_read_page(url, **kwargs):
        if "linkedin" in url:
            return None  # robots.txt / blacklist failure
        return "Real page body about the example company. " * 40

    monkeypatch.setattr("tools.page_reader.read_page", fake_read_page)

    agent, mock_llm = _make_agent()
    resp = agent._handle_multiple_results("compare these sources", [1, 2, 3, 4])

    # The synthesis must actually run and its answer must be returned.
    mock_llm.generate.assert_called_once()
    assert "SYNTHESIZED MULTI-SOURCE ANSWER" in resp
    # The false "all failed" error must NOT appear.
    assert "could not be loaded" not in resp.lower()


def test_reports_error_only_when_all_pages_fail(monkeypatch):
    """Every page fails -> the explicit error is returned and no synthesis runs."""
    monkeypatch.setattr("tools.page_reader.read_page", lambda url, **kwargs: None)

    agent, mock_llm = _make_agent()
    resp = agent._handle_multiple_results("compare these sources", [1, 2, 3, 4])

    assert "All 4 pages could not be loaded" in resp
    mock_llm.generate.assert_not_called()
