"""Failure handling for parallel aspect searches."""

from threading import Event

import pytest

from utils.parallel_search import ParallelSearchManager


@pytest.mark.parametrize("multi_aspect", [False, True])
def test_failed_aspect_is_not_counted_as_success(multi_aspect):
    manager = ParallelSearchManager(max_workers=2)

    def search(query):
        if "broken" in query:
            raise RuntimeError("provider failed")
        return "found"

    if multi_aspect:
        result = manager.multi_aspect_search(
            "query", search, {"working": "{query} working", "broken": "{query} broken"}
        )
    else:
        result = manager.parallel_search("query", ["working", "broken"], search)
        assert result["aspects_completed"] == 1

    assert result["aspect_results"] == {"working": "found", "broken": None}
    assert len(result["errors"]) == 1
    assert "provider failed" in result["errors"][0]
    assert "provider failed" not in result["combined_result"]


@pytest.mark.parametrize("multi_aspect", [False, True])
def test_timeout_preserves_completed_aspect(multi_aspect):
    manager = ParallelSearchManager(max_workers=2, timeout=0.02)
    release_slow_search = Event()

    def search(query):
        if "slow" in query:
            release_slow_search.wait(timeout=1)
        return "found"

    try:
        if multi_aspect:
            result = manager.multi_aspect_search(
                "query", search, {"fast": "{query} fast", "slow": "{query} slow"}
            )
        else:
            result = manager.parallel_search("query", ["fast", "slow"], search)

        assert result["aspect_results"] == {"fast": "found", "slow": None}
        assert len(result["errors"]) == 1
        assert "timed out" in result["errors"][0]
        assert "found" in result["combined_result"]
        if not multi_aspect:
            assert result["aspects_completed"] == 1
    finally:
        release_slow_search.set()
