"""Tests for FallbackManager."""
import pytest
from core.fallback_manager import FallbackManager, FallbackStrategy


def primary_func(x):
    """Primary function that raises an error."""
    raise ValueError("Primary failed")


def fallback1_func(x):
    """First fallback that also fails."""
    raise ValueError("Fallback 1 failed")


def fallback2_func(x):
    """Second fallback that succeeds."""
    return x * 2


def working_primary(x):
    """Working primary function."""
    return x + 1


def cache_func(x):
    """Cache function."""
    if x == 10:
        return 100
    return None


class TestFallbackStrategy:
    """Test FallbackStrategy class."""

    def test_primary_success(self):
        """Test successful primary execution."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=working_primary,
            fallback_funcs=[fallback2_func]
        )

        result = strategy.execute(5)
        assert result == 6
        assert strategy.stats["primary_success"] == 1
        assert strategy.stats["primary_failures"] == 0

    def test_fallback_execution(self):
        """Test fallback when primary fails."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=primary_func,
            fallback_funcs=[fallback2_func]
        )

        result = strategy.execute(5)
        assert result == 10
        assert strategy.stats["primary_failures"] == 1
        assert strategy.stats["fallback_success"] == 1

    def test_multiple_fallbacks(self):
        """Test multiple fallback attempts."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=primary_func,
            fallback_funcs=[fallback1_func, fallback2_func]
        )

        result = strategy.execute(5)
        assert result == 10
        assert strategy.stats["fallback_failures"] == 1
        assert strategy.stats["fallback_success"] == 1

    def test_all_fail(self):
        """Test when all attempts fail."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=primary_func,
            fallback_funcs=[fallback1_func]
        )

        with pytest.raises(Exception) as exc_info:
            strategy.execute(5)

        assert "All attempts failed" in str(exc_info.value)

    def test_cache_hit(self):
        """Test cache functionality."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=primary_func,
            fallback_funcs=[],
            cache_func=cache_func
        )

        result = strategy.execute(10)
        assert result == 100
        assert strategy.stats["cache_hits"] == 1

    def test_cache_miss_then_primary(self):
        """Test cache miss followed by primary."""
        strategy = FallbackStrategy(
            name="test",
            primary_func=working_primary,
            fallback_funcs=[],
            cache_func=cache_func
        )

        result = strategy.execute(5)
        assert result == 6
        assert strategy.stats["cache_hits"] == 0
        assert strategy.stats["primary_success"] == 1


class TestFallbackManager:
    """Test FallbackManager class."""

    def test_register_and_execute(self):
        """Test registering and executing strategy."""
        manager = FallbackManager()
        manager.register(
            name="test_tool",
            primary_func=working_primary,
            fallback_funcs=[fallback2_func]
        )

        result = manager.execute("test_tool", 5)
        assert result == 6

    def test_unregistered_tool(self):
        """Test executing unregistered tool."""
        manager = FallbackManager()

        with pytest.raises(ValueError) as exc_info:
            manager.execute("nonexistent", 5)

        assert "No fallback strategy" in str(exc_info.value)

    def test_with_fallback_decorator(self):
        """Test decorator functionality."""
        manager = FallbackManager()
        manager.register(
            name="decorated",
            primary_func=working_primary,
            fallback_funcs=[fallback2_func]
        )

        @manager.with_fallback("decorated")
        def test_func(x):
            return x

        result = test_func(5)
        assert result == 6

    def test_get_stats(self):
        """Test statistics retrieval."""
        manager = FallbackManager()
        manager.register(
            name="tool1",
            primary_func=working_primary,
            fallback_funcs=[]
        )
        manager.register(
            name="tool2",
            primary_func=primary_func,
            fallback_funcs=[fallback2_func]
        )

        manager.execute("tool1", 5)
        manager.execute("tool2", 5)

        stats = manager.get_stats()
        assert "tool1" in stats
        assert "tool2" in stats
        assert stats["tool1"]["primary_success"] == 1
        assert stats["tool2"]["fallback_success"] == 1

    def test_get_stats_single_tool(self):
        """Test statistics for single tool."""
        manager = FallbackManager()
        manager.register(
            name="test",
            primary_func=working_primary,
            fallback_funcs=[]
        )

        manager.execute("test", 5)
        stats = manager.get_stats("test")

        assert "test" in stats
        assert stats["test"]["primary_success"] == 1

    def test_reset_stats(self):
        """Test statistics reset."""
        manager = FallbackManager()
        manager.register(
            name="test",
            primary_func=working_primary,
            fallback_funcs=[]
        )

        manager.execute("test", 5)
        assert manager.get_stats("test")["test"]["primary_success"] == 1

        manager.reset_stats()
        assert manager.get_stats("test")["test"]["primary_success"] == 0
