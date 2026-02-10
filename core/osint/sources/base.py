"""Base classes and data models for breach sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("crawllama")


class SourceType(str, Enum):
    API_KEYED = "api_keyed"
    API_FREE = "api_free"
    LOCAL_DB = "local_db"
    WEB_SCRAPE = "web_scrape"


@dataclass
class SourceHealth:
    available: bool
    last_error: Optional[str] = None
    response_time_ms: Optional[int] = None


@dataclass
class BreachResult:
    name: str
    title: str
    breach_date: str
    description: str
    data_classes: List[str]
    is_verified: bool
    is_sensitive: bool
    source: str
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {
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

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def is_configured(self) -> bool:
        return True

    def query(self, email: str) -> List[BreachResult]:
        """Query source for breaches. Never raises; returns empty list on error."""
        try:
            results = self._query(email)
            return results or []
        except Exception as exc:
            logger.error(f"Breach source '{self.name}' query failed: {exc}")
            return []

    def health_check(self) -> SourceHealth:
        """Check source health. Never raises; returns unavailable on error."""
        try:
            return self._health_check()
        except Exception as exc:
            logger.debug(f"Health check failed for '{self.name}': {exc}")
            return SourceHealth(available=False, last_error=str(exc))

    @abstractmethod
    def _query(self, email: str) -> List[BreachResult]:
        raise NotImplementedError

    def _health_check(self) -> SourceHealth:
        return SourceHealth(available=True)
