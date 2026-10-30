"""Thread-safe lazy singleton accessor."""
import functools
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def lazy_singleton(factory: Callable[[], T]) -> Callable[[], T]:  # noqa: UP047 - keep 3.11 (requires-python)
    """Turn a zero-argument factory into a thread-safe ``get_x()`` accessor.

    The factory runs once, on first call; concurrent first calls cannot build
    two instances (which matters for managers holding per-instance secrets).
    ``accessor.reset()`` drops the instance so the next call rebuilds it.
    """
    lock = threading.Lock()
    instance: list[T] = []

    @functools.wraps(factory)
    def accessor() -> T:
        if not instance:
            with lock:
                if not instance:
                    instance.append(factory())
        return instance[0]

    def reset() -> None:
        with lock:
            instance.clear()

    accessor.reset = reset  # type: ignore[attr-defined]
    return accessor
