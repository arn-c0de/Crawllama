"""DeHashed breach source."""
from __future__ import annotations

import logging
import os
import re
import time
from urllib.parse import quote

import requests

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class DeHashedBreachSource(BreachSource):
    name = "dehashed"
    source_type = SourceType.WEB_SCRAPE
    rate_limit_delay = 1.0

    def is_configured(self) -> bool:
        if os.getenv("DEHASHED_API_KEY"):
            return True
        try:
            import bs4  # noqa: F401
            return True
        except Exception:
            return False

    def _query(self, email: str) -> list[BreachResult]:
        api_key = os.getenv("DEHASHED_API_KEY")
        username = os.getenv("DEHASHED_USERNAME")
        if api_key and username:
            return self._query_api(email, username, api_key)
        return self._query_free(email)

    def _query_api(self, email: str, username: str, api_key: str) -> list[BreachResult]:
        try:
            # URL-encode the email inside the DeHashed query expression.
            url = f"https://api.dehashed.com/search?query=email:{quote(email, safe='')}"
            response = requests.get(url, auth=(username, api_key), timeout=15)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            entries = data.get("entries", [])
            if not entries:
                return []

            breaches = []
            for entry in entries[:20]:
                breaches.append(
                    BreachResult(
                        name=entry.get("database_name", "DeHashed"),
                        title=entry.get("database_name", "DeHashed"),
                        breach_date=entry.get("date", "Unknown"),
                        description="Email appears in DeHashed database (API access).",
                        data_classes=["Email addresses"],
                        is_verified=True,
                        is_sensitive=True,
                        source="DeHashed"
                    )
                )
            return breaches
        except Exception as exc:
            logger.debug(f"DeHashed API query failed: {exc}")
            return []

    def _query_free(self, email: str) -> list[BreachResult]:
        try:
            from bs4 import BeautifulSoup
        except Exception:
            return []

        try:
            url = f"https://www.dehashed.com/search?query={quote(email, safe='')}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            results_text = response.text.lower()
            results_match = re.search(r"(\d+)\s+results?\s+found", results_text)

            if results_match or "results found" in results_text:
                result_count = results_match.group(1) if results_match else "multiple"
                has_password_data = bool(soup.find_all(string=re.compile(r"password", re.I)))

                metadata = {"requires_login": True}
                if has_password_data:
                    metadata["has_password_data"] = True

                return [
                    BreachResult(
                        name="DeHashed",
                        title=f"DeHashed search results ({result_count})",
                        breach_date="Unknown",
                        description=(
                            f"Email appears in DeHashed database ({result_count} entries). "
                            "Login required for full details."
                        ),
                        data_classes=["Email addresses"],
                        is_verified=False,
                        is_sensitive=True,
                        source="DeHashed",
                        metadata=metadata
                    )
                ]
        except Exception as exc:
            logger.debug(f"DeHashed free query failed: {exc}")

        return []
