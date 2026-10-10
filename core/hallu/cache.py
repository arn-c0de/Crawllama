"""Small LRU cache used by the fact checker."""
import logging
from collections import OrderedDict
from typing import Any

logger = logging.getLogger("crawllama")


class LRUCache:
    """Simple LRU cache implementation with size limit."""
    
    def __init__(self, max_size: int = 100):
        """Initialize LRU cache with maximum size."""
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        
    def get(self, key: str) -> dict[str, Any] | None:
        """Get item from cache and move to end (most recent)."""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
        
    def set(self, key: str, value: dict[str, Any]) -> None:
        """Set item in cache with LRU eviction."""
        if key in self.cache:
            # Update existing item and move to end
            self.cache[key] = value
            self.cache.move_to_end(key)
        else:
            # Add new item
            if len(self.cache) >= self.max_size:
                # Remove least recently used item (first item)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                logger.debug(f"LRU cache evicted oldest entry: {oldest_key}")
            
            self.cache[key] = value
            
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self.cache
        
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)
