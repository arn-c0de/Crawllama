"""Tests for web search functionality."""
import pytest
from tools.web_search import web_search, format_search_results


def test_web_search_returns_results():
    """Test that web search returns results."""
    results = web_search("Python programming", max_results=3)

    assert isinstance(results, list)
    assert len(results) <= 3

    if results:
        assert "url" in results[0]
        assert "title" in results[0]
        assert "snippet" in results[0]


def test_web_search_empty_query():
    """Test web search with empty query."""
    results = web_search("", max_results=3)
    assert isinstance(results, list)


def test_format_search_results():
    """Test formatting of search results."""
    results = [
        {
            "title": "Test Title",
            "url": "https://test.example.com",
            "snippet": "Test snippet"
        }
    ]

    formatted = format_search_results(results)
    assert "Test Title" in formatted
    assert "https://test.example.com" in formatted
    assert "Test snippet" in formatted


def test_format_empty_results():
    """Test formatting empty results."""
    formatted = format_search_results([])
    assert "No search results" in formatted
