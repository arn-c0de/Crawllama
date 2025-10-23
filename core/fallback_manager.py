"""Fallback management system for tool failures."""
import functools
from typing import Callable, Any, Optional, List, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


class FallbackStrategy:
    """Represents a fallback strategy for a tool."""

    def __init__(
        self,
        name: str,
        primary_func: Callable,
        fallback_funcs: List[Callable],
        cache_func: Optional[Callable] = None
    ):
        """
        Initialize fallback strategy.

        Args:
            name: Name of the tool
            primary_func: Primary function to execute
            fallback_funcs: List of fallback functions (in order)
            cache_func: Optional cache function to try first
        """
        self.name = name
        self.primary_func = primary_func
        self.fallback_funcs = fallback_funcs
        self.cache_func = cache_func
        self.stats = {
            "primary_success": 0,
            "primary_failures": 0,
            "fallback_success": 0,
            "fallback_failures": 0,
            "cache_hits": 0
        }

    def execute(self, *args, **kwargs) -> Any:
        """
        Execute with fallback strategy.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from primary or fallback function

        Raises:
            Exception: If all attempts fail
        """
        errors = []

        # Try cache first if available
        if self.cache_func:
            try:
                logger.debug(f"[{self.name}] Trying cache")
                result = self.cache_func(*args, **kwargs)
                if result:
                    self.stats["cache_hits"] += 1
                    logger.info(f"[{self.name}] ✓ Cache hit")
                    return result
            except Exception as e:
                logger.debug(f"[{self.name}] Cache miss: {e}")

        # Try primary function
        try:
            logger.debug(f"[{self.name}] Trying primary function")
            result = self.primary_func(*args, **kwargs)
            self.stats["primary_success"] += 1
            logger.info(f"[{self.name}] ✓ Primary function succeeded")
            return result

        except Exception as e:
            self.stats["primary_failures"] += 1
            errors.append(f"Primary: {str(e)}")
            logger.warning(f"[{self.name}] ✗ Primary function failed: {e}")

        # Try fallback functions
        for i, fallback_func in enumerate(self.fallback_funcs):
            try:
                logger.debug(f"[{self.name}] Trying fallback {i+1}/{len(self.fallback_funcs)}")
                result = fallback_func(*args, **kwargs)
                self.stats["fallback_success"] += 1
                logger.info(f"[{self.name}] ✓ Fallback {i+1} succeeded")
                return result

            except Exception as e:
                self.stats["fallback_failures"] += 1
                errors.append(f"Fallback {i+1}: {str(e)}")
                logger.warning(f"[{self.name}] ✗ Fallback {i+1} failed: {e}")

        # All attempts failed
        error_msg = f"All attempts failed for {self.name}: " + "; ".join(errors)
        logger.error(error_msg)
        raise Exception(error_msg)

    def get_stats(self) -> Dict[str, int]:
        """
        Get execution statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()


class FallbackManager:
    """Manage fallback strategies for multiple tools."""

    def __init__(self):
        """Initialize fallback manager."""
        self.strategies: Dict[str, FallbackStrategy] = {}

    def register(
        self,
        name: str,
        primary_func: Callable,
        fallback_funcs: List[Callable],
        cache_func: Optional[Callable] = None
    ):
        """
        Register a fallback strategy.

        Args:
            name: Name of the tool
            primary_func: Primary function
            fallback_funcs: List of fallback functions
            cache_func: Optional cache function
        """
        strategy = FallbackStrategy(name, primary_func, fallback_funcs, cache_func)
        self.strategies[name] = strategy
        logger.info(f"Registered fallback strategy for '{name}' with {len(fallback_funcs)} fallbacks")

    def execute(self, name: str, *args, **kwargs) -> Any:
        """
        Execute a tool with fallback.

        Args:
            name: Name of the tool
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from execution

        Raises:
            ValueError: If tool not registered
            Exception: If all attempts fail
        """
        if name not in self.strategies:
            raise ValueError(f"No fallback strategy registered for '{name}'")

        return self.strategies[name].execute(*args, **kwargs)

    def with_fallback(self, name: str):
        """
        Decorator to execute function with fallback.

        Args:
            name: Name of the tool

        Returns:
            Decorated function
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self.execute(name, *args, **kwargs)
            return wrapper
        return decorator

    def get_stats(self, name: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for all or specific tool.

        Args:
            name: Optional tool name (returns all if None)

        Returns:
            Dictionary with statistics
        """
        if name:
            if name not in self.strategies:
                return {}
            return {name: self.strategies[name].get_stats()}

        return {
            tool_name: strategy.get_stats()
            for tool_name, strategy in self.strategies.items()
        }

    def reset_stats(self):
        """Reset all statistics."""
        for strategy in self.strategies.values():
            strategy.stats = {
                "primary_success": 0,
                "primary_failures": 0,
                "fallback_success": 0,
                "fallback_failures": 0,
                "cache_hits": 0
            }
        logger.info("Statistics reset")


# Global fallback manager instance
fallback_manager = FallbackManager()


def register_web_search_fallbacks(
    duckduckgo_func: Callable,
    brave_func: Optional[Callable] = None,
    serper_func: Optional[Callable] = None,
    cache_func: Optional[Callable] = None
):
    """
    Register web search fallbacks.

    Args:
        duckduckgo_func: DuckDuckGo search function
        brave_func: Optional Brave search function
        serper_func: Optional Serper API function
        cache_func: Optional cache function
    """
    fallbacks = []
    if brave_func:
        fallbacks.append(brave_func)
    if serper_func:
        fallbacks.append(serper_func)

    fallback_manager.register(
        name="web_search",
        primary_func=duckduckgo_func,
        fallback_funcs=fallbacks,
        cache_func=cache_func
    )


def register_wiki_lookup_fallbacks(
    primary_func: Callable,
    cache_func: Optional[Callable] = None
):
    """
    Register Wikipedia lookup fallbacks.

    Args:
        primary_func: Primary Wikipedia function
        cache_func: Optional cache function
    """
    fallback_manager.register(
        name="wiki_lookup",
        primary_func=primary_func,
        fallback_funcs=[],  # No fallbacks for Wikipedia
        cache_func=cache_func
    )
