"""Snusbase breach source."""
from __future__ import annotations

import os
import time
from typing import List
import logging
import requests

from .base import BreachSource, BreachResult, SourceType

logger = logging.getLogger("crawllama")


class SnusbaseBreachSource(BreachSource):
    name = "snusbase"
    source_type = SourceType.API_KEYED
    rate_limit_delay = 1.0

    def is_configured(self) -> bool:
        return bool(os.getenv("SNUSBASE_API_KEY"))

    def _query(self, email: str) -> List[BreachResult]:
        api_key = os.getenv("SNUSBASE_API_KEY")
        if not api_key:
            return []

        try:
            url = "https://api.snusbase.com/data/search"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "user-agent": "CrawlLama-OSINT/1.4.8"
            }
            payload = {"terms": [email], "types": ["email"]}
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("results", {}) if isinstance(data, dict) else {}
            email_results = results.get("email") if isinstance(results, dict) else None

            sources = set()
            if isinstance(email_results, list):
                for item in email_results:
                    if isinstance(item, dict):
                        source_name = item.get("source") or item.get("database") or "Snusbase"
                        sources.add(source_name)
            if not sources and data.get("count"):
                sources.add("Snusbase")

            breaches: List[BreachResult] = []
            for source_name in sources:
                breaches.append(
                    BreachResult(
                        name=source_name,
                        title=source_name,
                        breach_date="Unknown",
                        description="Email appears in Snusbase data sources.",
                        data_classes=["Email addresses"],
                        is_verified=True,
                        is_sensitive=True,
                        source="Snusbase"
                    )
                )
            return breaches
        except Exception as exc:
            logger.debug(f"Snusbase query failed: {exc}")
            return []
