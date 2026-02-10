"""Have I Been Pwned breach source."""
from __future__ import annotations

import os
import time
import urllib.parse
from typing import List
import logging
import requests

from .base import BreachSource, BreachResult, SourceType, SourceHealth

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

    def _query(self, email: str) -> List[BreachResult]:
        breaches: List[BreachResult] = []
        api_key = os.getenv("HIBP_API_KEY")
        if api_key:
            breaches = self._check_hibp_with_key(email, api_key)
            self._check_hibp_pastes(email, api_key)
            return breaches

        # No key: try direct call (likely 401)
        return self._try_hibp_api_direct(email)

    def _check_hibp_with_key(self, email: str, api_key: str) -> List[BreachResult]:
        try:
            encoded_email = urllib.parse.quote(email)
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded_email}?truncateResponse=false"
            headers = {
                "hibp-api-key": api_key,
                "user-agent": "CrawlLama-OSINT/1.4.7",
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=15)
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                return [self._from_hibp_dict(b) for b in response.json()]
            if response.status_code == 404:
                return []
            logger.warning(f"HIBP API returned {response.status_code}: {response.text}")
        except Exception as exc:
            logger.error(f"HIBP API check failed: {exc}")
        return []

    def _try_hibp_api_direct(self, email: str) -> List[BreachResult]:
        try:
            encoded_email = urllib.parse.quote(email)
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded_email}?truncateResponse=false"
            headers = {
                "user-agent": "CrawlLama-OSINT/1.4.7",
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=15)
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                return [self._from_hibp_dict(b) for b in response.json()]
            if response.status_code in (401, 403, 404):
                return []
            logger.warning(f"HIBP direct call returned {response.status_code}")
        except Exception as exc:
            logger.debug(f"HIBP direct call failed: {exc}")
        return []

    def _check_hibp_pastes(self, email: str, api_key: str) -> None:
        self.last_paste_count = 0
        try:
            url = f"https://haveibeenpwned.com/api/v3/pasteaccount/{email}"
            headers = {
                "hibp-api-key": api_key,
                "user-agent": "CrawlLama-OSINT/1.4.7",
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                pastes = response.json()
                self.last_paste_count = len(pastes)
            elif response.status_code == 404:
                self.last_paste_count = 0
            else:
                logger.warning(f"HIBP paste check returned {response.status_code}")
        except Exception as exc:
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
