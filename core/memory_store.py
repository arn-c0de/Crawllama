"""
Backward-compatibility shim.

All functionality has been moved to the ``core.memory`` package.
Existing imports (``from core.memory_store import ...``) continue to work.
"""

from core.memory import (  # noqa: F401
    MemoryStore,
    get_memory_store,
    DEFAULT_PER_USER_LIMIT,
    DEFAULT_GLOBAL_LIMIT,
    DEFAULT_USER_ID,
)
