"""Have I Been Pwned breach source."""
from __future__ import annotations

import logging
import os
import time
import urllib.parse

import requests

from .base import BreachResult, BreachSource, SourceHealth, SourceType

logger = logging.getLogger("crawllama")


class HIBPBreachSource(BreachSource):
    name = "hibp"
    source_type = SourceType.API_KEYED
    rate_limit_delay = 1.6

    def __init__(self, config=None):
        super().__init__(config)
        self.last_paste_count = 0

    def is_configured(self) -> bool:
        return bool(os.getenv("HIBP_API_KEY"))

    def _query(self, email: str) -> list[BreachResult]:
        api_key = os.getenv("HIBP_API_KEY")
        breaches = self._fetch_breaches(email, api_key)
        if api_key:
            self._check_hibp_pastes(email, api_key)
        return breaches

    def _fetch_breaches(self, email: str, api_key: str | None) -> list[BreachResult]:
        """Query the breachedaccount endpoint; without a key HIBP answers 401,
        which is recorded as "not checked" rather than "clean"."""
        try:
            encoded_email = urllib.parse.quote(email, safe="")
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded_email}?truncateResponse=false"
            headers = {"Accept": "application/json"}
            if api_key:
                headers["hibp-api-key"] = api_key
            response = self._get(url, headers=headers, timeout=15)

            if self._response_ok(response):
                return [self._from_hibp_dict(b) for b in response.json()]
            if response.status_code != 404:
                # SECURITY: never log the response body — it can contain breach
                # names tied to the queried email (PII). Log the status only.
                logger.warning(f"HIBP API returned status {response.status_code}")
        except Exception as exc:
            self._record_failure(exc)
            logger.error(f"HIBP API check failed: {exc}")
        return []

    def _check_hibp_pastes(self, email: str, api_key: str) -> None:
        self.last_paste_count = 0
        try:
            url = f"https://haveibeenpwned.com/api/v3/pasteaccount/{urllib.parse.quote(email, safe='')}"
            headers = {
                "hibp-api-key": api_key,
                "Accept": "application/json"
            }
            response = self._get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                pastes = response.json()
                self.last_paste_count = len(pastes)
            elif response.status_code == 404:
                self.last_paste_count = 0
            else:
                self._record_failure(f"pastes: HTTP {response.status_code}")
                logger.warning(f"HIBP paste check returned {response.status_code}")
        except Exception as exc:
            self._record_failure(exc)
            logger.error(f"HIBP paste check failed: {exc}")

    def _from_hibp_dict(self, breach: dict) -> BreachResult:
        return BreachResult(
            name=breach.get("Name", "Unknown"),
            title=breach.get("Title", breach.get("Name", "Unknown")),
            breach_date=breach.get("BreachDate", "Unknown"),
            description=breach.get("Description", ""),
            data_classes=breach.get("DataClasses", ["Email addresses"]),
            is_verified=bool(breach.get("IsVerified", False)),
            is_sensitive=bool(breach.get("IsSensitive", False)),
            source="HaveIBeenPwned"
        )

    def _health_check(self) -> SourceHealth:
        start = time.time()
        try:
            response = requests.head("https://haveibeenpwned.com/api/v3/breaches", timeout=5)
            elapsed = int((time.time() - start) * 1000)
            available = response.status_code < 500
            last_error = None if available else f"HTTP {response.status_code}"
            return SourceHealth(available=available, last_error=last_error, response_time_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.time() - start) * 1000)
            return SourceHealth(available=False, last_error=str(exc), response_time_ms=elapsed)
