"""
Modular memory store package for OSINT intelligence data.

Survives session clear and provides long-term storage for important findings.

Security Features:
- Per-user entry limits to prevent DoS attacks
- Global entry limits as fallback
- User ID tracking for all entries
"""

from .constants import (
    DEFAULT_PER_USER_LIMIT,
    DEFAULT_GLOBAL_LIMIT,
    DEFAULT_USER_ID,
    CATEGORIES,
)
from .store import MemoryStore, get_memory_store

__all__ = [
    "MemoryStore",
    "get_memory_store",
    "DEFAULT_PER_USER_LIMIT",
    "DEFAULT_GLOBAL_LIMIT",
    "DEFAULT_USER_ID",
    "CATEGORIES",
]

__version__ = "2.0.0"
