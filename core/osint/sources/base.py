"""Base classes and data models for breach sources."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import requests
from requests.structures import CaseInsensitiveDict

from _version import __version__

logger = logging.getLogger("crawllama")

USER_AGENT = f"CrawlLama-OSINT/{__version__}"


class SourceType(str, Enum):
    API_KEYED = "api_keyed"
    API_FREE = "api_free"
    LOCAL_DB = "local_db"
    WEB_SCRAPE = "web_scrape"


@dataclass
class SourceHealth:
    available: bool
    last_error: str | None = None
    response_time_ms: int | None = None


@dataclass
class BreachResult:
    name: str
    title: str
    breach_date: str
    description: str
    data_classes: list[str]
    is_verified: bool
    is_sensitive: bool
    source: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "Name": self.name,
            "Title": self.title,
            "BreachDate": self.breach_date,
            "Description": self.description,
            "DataClasses": self.data_classes,
            "IsVerified": self.is_verified,
            "IsSensitive": self.is_sensitive,
            "Source": self.source
        }
        if self.metadata:
            data["Metadata"] = self.metadata
        return data


class BreachSource(ABC):
    """Abstract base class for breach sources."""

    name: str = "base"
    source_type: SourceType = SourceType.API_FREE
    rate_limit_delay: float = 1.0

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def is_configured(self) -> bool:
        return True

    last_error: str | None = None

    def query(self, email: str) -> list[BreachResult]:
        """Query source for breaches. Never raises; returns empty list on error.

        A failed lookup (HTTP error, exception) is recorded in ``last_error``
        so callers can tell "no breaches" apart from "source unavailable".
        """
        self.last_error = None
        try:
            results = self._query(email)
            return results or []
        except Exception as exc:
            logger.error(f"Breach source '{self.name}' query failed: {exc}")
            self._record_failure(exc)
            return []

    def _record_failure(self, reason: object) -> None:
        """Remember why the current query failed (see ``last_error``)."""
        self.last_error = str(reason)

    def _get(self, url: str, **kwargs) -> requests.Response:
        """``requests.get`` with the OSINT user agent, followed by the rate-limit pause."""
        return self._request("get", url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        """``requests.post`` with the OSINT user agent, followed by the rate-limit pause."""
        return self._request("post", url, **kwargs)

    def _request(self, method: str, url: str, *, headers: dict | None = None, **kwargs) -> requests.Response:
        merged = CaseInsensitiveDict({"User-Agent": USER_AGENT})
        merged.update(headers or {})
        try:
            return getattr(requests, method)(url, headers=merged, **kwargs)
        finally:
            time.sleep(self.rate_limit_delay)

    def _response_ok(self, response, no_data_codes: tuple[int, ...] = (404,)) -> bool:
        """True for HTTP 200; ``no_data_codes`` mean "nothing found"; anything
        else (401/429/5xx...) is recorded as a source failure."""
        if response.status_code == 200:
            return True
        if response.status_code not in no_data_codes:
            self._record_failure(f"HTTP {response.status_code}")
        return False

    def health_check(self) -> SourceHealth:
        """Check source health. Never raises; returns unavailable on error."""
        try:
            return self._health_check()
        except Exception as exc:
            logger.debug(f"Health check failed for '{self.name}': {exc}")
            return SourceHealth(available=False, last_error=str(exc))

    @abstractmethod
    def _query(self, email: str) -> list[BreachResult]:
        raise NotImplementedError

    def _health_check(self) -> SourceHealth:
        return SourceHealth(available=True)
