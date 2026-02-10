"""LeakCheck breach source."""
from __future__ import annotations

import os
import time
from typing import List
import logging
import requests

from .base import BreachSource, BreachResult, SourceType

logger = logging.getLogger("crawllama")


class LeakCheckBreachSource(BreachSource):
    name = "leakcheck"
    source_type = SourceType.API_FREE
    rate_limit_delay = 1.0

    def is_configured(self) -> bool:
        return True

    def _query(self, email: str) -> List[BreachResult]:
        breaches: List[BreachResult] = []
        breaches.extend(self._query_public(email))

        api_key = os.getenv("LEAKCHECK_API_KEY")
        if api_key:
            breaches.extend(self._query_authenticated(email, api_key))

        return breaches

    def _query_public(self, email: str) -> List[BreachResult]:
        try:
            url = f"https://leakcheck.io/api/public?check={email}"
            headers = {"user-agent": "CrawlLama-OSINT/1.4.7"}
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            if not data.get("success") and not data.get("found"):
                return []

            breaches: List[BreachResult] = []
            sources = data.get("sources") or []
            fields = data.get("fields", ["Email addresses"])
            for source in sources:
                name = source.get("name", "Unknown")
                breach_date = source.get("date", "Unknown")
                breaches.append(
                    BreachResult(
                        name=name,
                        title=name,
                        breach_date=breach_date,
                        description=(
                            f"Data breach from {name} detected by LeakCheck.io. "
                            f"Leaked fields: {', '.join(fields[:5])}"
                        ),
                        data_classes=fields,
                        is_verified=True,
                        is_sensitive=True,
                        source="LeakCheck"
                    )
                )
            return breaches
        except Exception as exc:
            logger.debug(f"LeakCheck public query failed: {exc}")
            return []

    def _query_authenticated(self, email: str, api_key: str) -> List[BreachResult]:
        try:
            url = f"https://leakcheck.io/api/v2/query/{email}"
            headers = {"X-API-Key": api_key, "user-agent": "CrawlLama-OSINT/1.4.7"}
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("result", [])
            breaches: List[BreachResult] = []
            for result in results:
                source_name = result.get("source", "Unknown")
                metadata = {}
                password = result.get("password")
                if password:
                    metadata["password_hint"] = password[0] + "*" * min(len(password) - 1, 8)
                    metadata["password_length"] = len(password)
                if result.get("hash"):
                    metadata["password_hash"] = str(result.get("hash"))[:12] + "..."

                breaches.append(
                    BreachResult(
                        name=source_name,
                        title=source_name,
                        breach_date=result.get("date", "Unknown"),
                        description=f"Email found in LeakCheck source {source_name}.",
                        data_classes=["Email addresses"],
                        is_verified=True,
                        is_sensitive=True,
                        source="LeakCheck",
                        metadata=metadata
                    )
                )
            return breaches
        except Exception as exc:
            logger.debug(f"LeakCheck authenticated query failed: {exc}")
            return []
