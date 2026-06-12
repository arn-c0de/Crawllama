"""
MemoryStore class composed from all mixins, plus the singleton accessor.
"""

from .breach import BreachIntelMixin
from .constants import DEFAULT_GLOBAL_LIMIT, DEFAULT_PER_USER_LIMIT
from .export import ExportImportMixin
from .operations import OperationsMixin
from .persistence import PersistenceMixin
from .quotas import QuotaMixin
from .sanitization import SanitizationMixin


class MemoryStore(
    PersistenceMixin,
    QuotaMixin,
    SanitizationMixin,
    OperationsMixin,
    BreachIntelMixin,
    ExportImportMixin,
):
    """
    Persistent storage for OSINT intelligence data.
    Stores emails, phones, IPs, usernames, and custom notes.

    Security Features:
    - Per-user quotas to prevent memory exhaustion DoS
    - Global limits as fallback protection
    - User ID tracking for audit and accountability
    """

    def __init__(
        self,
        memory_file: str = "data/memory.json",
        per_user_limit: int = DEFAULT_PER_USER_LIMIT,
        global_limit: int = DEFAULT_GLOBAL_LIMIT,
    ):
        """
        Initialize memory store.

        Args:
            memory_file: Path to persistent memory JSON file
            per_user_limit: Maximum entries per user per category (default: 100)
            global_limit: Maximum total entries per category (default: 1000)
        """
        self.memory_file = memory_file
        self.per_user_limit = per_user_limit
        self.global_limit = global_limit
        self.data = self._default_data()
        self._load()


# Global instance
_memory_store = None


def get_memory_store() -> MemoryStore:
    """Get or create global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
