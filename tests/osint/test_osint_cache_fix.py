"""Regression test for OSINT result-reference behavior (no real web requests).

Goal:
- An OSINT operator query (e.g. `site:...`) must store session search results
  so that result references like `quelle 1` work immediately afterwards.

This test is fully mocked to avoid network/LLM dependencies and CI timeouts.
"""

from unittest.mock import Mock, patch


def test_osint_results_are_referenced_after_osint_search(monkeypatch):
    # Mock web search results returned by tools.web_search.search_with_fallback
    fake_results = [
        {
            "title": "Python.org - Official site",
            "url": "https://www.python.org/",
            "snippet": "The official home of the Python Programming Language.",
        },
        {
            "title": "Python Docs",
            "url": "https://docs.python.org/",
            "snippet": "Python documentation.",
        },
    ]

    monkeypatch.setattr(
        "tools.web_search.search_with_fallback",
        lambda *args, **kwargs: fake_results,
    )

    # Allow OSINT compliance without requiring persisted terms acceptance.
    monkeypatch.setattr(
        "core.osint.compliance.OSINTCompliance.check_query",
        lambda self, query, user_id="default", query_type="general_osint": (True, "Query approved"),
    )

    # Avoid real page fetching when `quelle N` reads a page.
    read_page_mock = Mock(return_value="Dummy page content for summary.")
    monkeypatch.setattr("tools.page_reader.read_page", read_page_mock)

    # Avoid real LLM calls during summarization.
    mock_llm = Mock()
    mock_llm.generate = Mock(return_value="Summary")

    with patch("core.agent.agent.OllamaClient", return_value=mock_llm):
        from core.agent import SearchAgent

        config = {
            "llm": {"provider": "ollama", "model": "test", "stream": False},
            "search": {"region": "de-de", "max_results": 5},
            "osint": {"max_results": 5, "safesearch": "strict"},
            "cache": {"enabled": False},
            "rag": {"enabled": False},
            "security": {"max_context_length": 2000},
            "paths": {"session_file": "data/session.json"},
        }

        agent = SearchAgent(config=config, enable_web=True, debug=False)

        # 1) Run an OSINT operator query (should store results in session).
        agent.query("site:python.org")
        assert agent.session.last_search_results
        assert agent.session.last_search_results[0]["url"] == "https://www.python.org/"

        # 2) Reference the previous result; should NOT say "No previous search results available".
        resp = agent.query("quelle 1")
        assert "No previous search results available" not in resp

        # 3) Ensure we attempted to load the referenced page (mocked).
        read_page_mock.assert_called()
