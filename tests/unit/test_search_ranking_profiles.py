"""Tests for adaptive ranking profile selection."""

from tools.web_search import resolve_ranking_profile


def test_resolve_ranking_profile_uses_explicit_profile_operator():
    query = "latest ai benchmark profile:strict_factual"
    assert resolve_ranking_profile(query, requested_profile="auto") == "strict_factual"


def test_resolve_ranking_profile_auto_osint():
    query = 'email:test@example.com site:github.com'
    assert resolve_ranking_profile(query, requested_profile="auto") == "osint"


def test_resolve_ranking_profile_auto_strict_factual():
    query = "official government statistics and source links for inflation"
    assert resolve_ranking_profile(query, requested_profile="auto") == "strict_factual"


def test_resolve_ranking_profile_auto_balanced_fallback():
    query = "best python web frameworks"
    assert resolve_ranking_profile(query, requested_profile="auto") == "balanced"

