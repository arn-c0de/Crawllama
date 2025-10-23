"""Robustness utilities for error handling, retries, and timeouts."""
import logging
import time
import functools
from typing import Callable, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("crawllama")


class RobustnessError(Exception):
    """Base exception for robustness-related errors."""
    pass


class TimeoutError(RobustnessError):
    """Raised when an operation times out."""
    pass


class RetryError(RobustnessError):
    """Raised when all retries are exhausted."""
    pass


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Exception, ...] = (Exception,)
) -> Callable:
    """
    Decorator to retry a function on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier (delay *= backoff after each retry)
        exceptions: Tuple of exceptions to catch and retry on

    Returns:
        Decorated function

    Example:
        @retry_on_failure(max_retries=3, delay=1.0)
        def unstable_function():
            # May fail occasionally
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )

            raise RetryError(
                f"Failed after {max_retries} retries: {last_exception}"
            ) from last_exception

        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_error: bool = True,
    **kwargs
) -> Tuple[bool, Any]:
    """
    Safely execute a function and return success status and result.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        default: Default return value if function fails
        log_error: Whether to log errors
        **kwargs: Keyword arguments for func

    Returns:
        Tuple of (success: bool, result: Any)
        - If successful: (True, function_result)
        - If failed: (False, default_value)

    Example:
        success, result = safe_execute(risky_function, arg1, arg2, default="N/A")
        if success:
            print(f"Result: {result}")
        else:
            print(f"Failed, using default: {result}")
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        if log_error:
            logger.error(f"safe_execute failed for {func.__name__}: {e}")
        return False, default


def validate_input(
    value: Any,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    allowed_types: Optional[Tuple[type, ...]] = None,
    not_empty: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Validate input value against criteria.

    Args:
        value: Value to validate
        min_length: Minimum length (for strings/lists)
        max_length: Maximum length (for strings/lists)
        allowed_types: Tuple of allowed types
        not_empty: Whether value must not be empty

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])

    Example:
        is_valid, error = validate_input(user_query, min_length=1, max_length=1000)
        if not is_valid:
            return f"Invalid input: {error}"
    """
    # Type check
    if allowed_types and not isinstance(value, allowed_types):
        return False, f"Invalid type: expected {allowed_types}, got {type(value)}"

    # Empty check
    if not_empty:
        if value is None:
            return False, "Value cannot be None"
        if isinstance(value, (str, list, dict)) and len(value) == 0:
            return False, "Value cannot be empty"
        if isinstance(value, str) and not value.strip():
            return False, "Value cannot be blank"

    # Length checks
    if hasattr(value, '__len__'):
        length = len(value)
        if min_length is not None and length < min_length:
            return False, f"Value too short: minimum {min_length} characters"
        if max_length is not None and length > max_length:
            return False, f"Value too long: maximum {max_length} characters"

    return True, None


def sanitize_query(query: str) -> str:
    """
    Sanitize user query to prevent issues.

    Args:
        query: Raw user query

    Returns:
        Sanitized query

    Example:
        clean_query = sanitize_query(user_input)
    """
    if not query or not isinstance(query, str):
        return ""

    # Remove excessive whitespace
    query = " ".join(query.split())

    # Remove null bytes
    query = query.replace('\x00', '')

    # Trim to reasonable length
    max_query_length = 5000
    if len(query) > max_query_length:
        logger.warning(f"Query truncated from {len(query)} to {max_query_length} characters")
        query = query[:max_query_length]

    return query.strip()


def with_timeout(
    timeout_seconds: float,
    default: Any = None
) -> Callable:
    """
    Decorator to add timeout to a function (simple implementation).

    Note: This is a basic implementation. For production use,
    consider using concurrent.futures or signal-based timeouts.

    Args:
        timeout_seconds: Maximum execution time in seconds
        default: Default return value on timeout

    Returns:
        Decorated function

    Example:
        @with_timeout(timeout_seconds=5.0, default="Timeout")
        def slow_function():
            time.sleep(10)
            return "Done"
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import threading

            result = [default]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)

            if thread.is_alive():
                logger.warning(
                    f"{func.__name__} timed out after {timeout_seconds}s"
                )
                return default

            if exception[0]:
                raise exception[0]

            return result[0]

        return wrapper
    return decorator


class HealthCheck:
    """Health check utilities for monitoring system components."""

    def __init__(self):
        """Initialize health checker."""
        self.checks = {}
        self.last_check_time = {}

    def register_check(
        self,
        name: str,
        check_func: Callable[[], bool],
        cache_seconds: int = 60
    ):
        """
        Register a health check function.

        Args:
            name: Name of the component to check
            check_func: Function that returns True if healthy
            cache_seconds: Cache check result for this many seconds
        """
        self.checks[name] = {
            'func': check_func,
            'cache_seconds': cache_seconds
        }

    def is_healthy(self, name: str) -> bool:
        """
        Check if a component is healthy.

        Args:
            name: Name of the component

        Returns:
            True if healthy, False otherwise
        """
        if name not in self.checks:
            logger.warning(f"Health check '{name}' not registered")
            return False

        # Check cache
        now = time.time()
        if name in self.last_check_time:
            cache_seconds = self.checks[name]['cache_seconds']
            if now - self.last_check_time[name] < cache_seconds:
                # Use cached result
                return self.checks[name].get('last_result', False)

        # Run check
        check_func = self.checks[name]['func']
        success, result = safe_execute(check_func, default=False, log_error=True)

        # Cache result
        self.checks[name]['last_result'] = result if success else False
        self.last_check_time[name] = now

        return result if success else False

    def get_status(self) -> dict:
        """
        Get health status of all registered components.

        Returns:
            Dictionary of component statuses
        """
        status = {}
        for name in self.checks:
            status[name] = self.is_healthy(name)
        return status


# Global health checker instance
health_checker = HealthCheck()


def log_performance(func: Callable) -> Callable:
    """
    Decorator to log function execution time.

    Args:
        func: Function to monitor

    Returns:
        Decorated function

    Example:
        @log_performance
        def slow_function():
            time.sleep(2)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise

    return wrapper
