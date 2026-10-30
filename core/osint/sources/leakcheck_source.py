"""LeakCheck breach source."""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class LeakCheckBreachSource(BreachSource):
    name = "leakcheck"
    source_type = SourceType.API_FREE
    rate_limit_delay = 1.0

    def is_configured(self) -> bool:
        return True

    def _query(self, email: str) -> list[BreachResult]:
        breaches: list[BreachResult] = []
        breaches.extend(self._query_public(email))

        api_key = os.getenv("LEAKCHECK_API_KEY")
        if api_key:
            breaches.extend(self._query_authenticated(email, api_key))

        return breaches

    def _query_public(self, email: str) -> list[BreachResult]:
        try:
            url = "https://leakcheck.io/api/public"
            # URL-encode the email via params to prevent query injection.
            response = self._get(url, params={"check": email}, timeout=10)

            if not self._response_ok(response):
                return []

            data = response.json()
            if not data.get("success") and not data.get("found"):
                return []

            breaches: list[BreachResult] = []
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
            self._record_failure(exc)
            logger.debug(f"LeakCheck public query failed: {exc}")
            return []

    def _query_authenticated(self, email: str, api_key: str) -> list[BreachResult]:
        try:
            # Encode the email as a single path segment (no '/' or other
            # reserved characters can break out of the path).
            url = f"https://leakcheck.io/api/v2/query/{quote(email, safe='')}"
            headers = {"X-API-Key": api_key}
            response = self._get(url, headers=headers, timeout=10)

            if not self._response_ok(response):
                return []

            data = response.json()
            results = data.get("result", [])
            breaches: list[BreachResult] = []
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
            self._record_failure(exc)
            logger.debug(f"LeakCheck authenticated query failed: {exc}")
            return []
