"""IntelX breach source."""
from __future__ import annotations

import logging
import time

import requests

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class IntelXBreachSource(BreachSource):
    name = "intelx"
    source_type = SourceType.API_FREE
    rate_limit_delay = 1.0

    def is_configured(self) -> bool:
        return True

    def _query(self, email: str) -> list[BreachResult]:
        try:
            url = "https://2.intelx.io/phonebook/search"
            headers = {"user-agent": "CrawlLama-OSINT/1.4.8"}
            # Pass the email via params so it is URL-encoded (prevents query
            # parameter injection from crafted addresses).
            response = requests.get(url, headers=headers, params={"k": email}, timeout=10)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            selectors = data.get("selectors") or []
            if not selectors:
                return []

            count = len(selectors)
            return [
                BreachResult(
                    name="IntelligenceX",
                    title=f"Found {count} references",
                    breach_date="Various",
                    description=(
                        f"Email found in {count} indexed source(s) on Intelligence X. "
                        "This includes pastes, leaks, and public databases."
                    ),
                    data_classes=["Email addresses"],
                    is_verified=False,
                    is_sensitive=True,
                    source="IntelX"
                )
            ]
        except Exception as exc:
            logger.debug(f"IntelX query failed: {exc}")
            return []
