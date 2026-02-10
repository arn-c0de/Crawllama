"""Public paste monitoring source (limited)."""
from __future__ import annotations

import time
from typing import Dict, List, Tuple
import logging

from .base import BreachSource, BreachResult, SourceType

logger = logging.getLogger("crawllama")


class PasteBreachSource(BreachSource):
    name = "paste"
    source_type = SourceType.WEB_SCRAPE
    rate_limit_delay = 10.0

    _cache: Dict[str, Tuple[float, List[BreachResult]]] = {}
    _cache_ttl = 3600

    def is_configured(self) -> bool:
        return True

    def _query(self, email: str) -> List[BreachResult]:
        now = time.time()
        cached = self._cache.get(email)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        # Placeholder: public paste scraping not implemented yet.
        results: List[BreachResult] = []
        self._cache[email] = (now, results)
        return results
