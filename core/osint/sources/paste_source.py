"""Public paste monitoring source (limited)."""
from __future__ import annotations

import logging
import time

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class PasteBreachSource(BreachSource):
    name = "paste"
    source_type = SourceType.WEB_SCRAPE
    rate_limit_delay = 10.0

    _cache: dict[str, tuple[float, list[BreachResult]]] = {}
    _cache_ttl = 3600

    def is_configured(self) -> bool:
        return True

    def _query(self, email: str) -> list[BreachResult]:
        now = time.time()
        cached = self._cache.get(email)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        # Placeholder: public paste scraping not implemented yet.
        results: list[BreachResult] = []
        self._cache[email] = (now, results)
        return results
