"""Breach source manager and orchestrator."""
from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import logging

from utils.rate_limiter import RateLimiter
from utils.validators import sanitize_for_logging
from .base import BreachSource, SourceHealth

logger = logging.getLogger("crawllama")


class BreachManager:
    def __init__(self, config: Optional[dict] = None):
        self.config = config if config is not None else self._load_config()
        osint_config = self.config.get("osint", {}) if isinstance(self.config, dict) else {}
        self._breach_source_settings = osint_config.get("breach_sources", {})
        self._sources: Dict[str, BreachSource] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}

    def _load_config(self) -> dict:
        for path in ("config.json", "config.json.example"):
            try:
                if Path(path).exists():
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception as exc:
                logger.debug(f"Failed to load {path}: {exc}")
        return {}

    def register_source(self, source: BreachSource) -> None:
        self._sources[source.name] = source
        delay = max(float(source.rate_limit_delay or 0.0), 0.0)
        if delay > 0:
            requests_per_second = 1.0 / delay
        else:
            requests_per_second = 1000.0
        self._rate_limiters[source.name] = RateLimiter(requests_per_second=requests_per_second)

    def unregister_source(self, name: str) -> None:
        self._sources.pop(name, None)
        self._rate_limiters.pop(name, None)

    def get_enabled_sources(self) -> List[BreachSource]:
        enabled_sources: List[BreachSource] = []
        for name, source in self._sources.items():
            settings = self._breach_source_settings.get(name, {})
            enabled = settings.get("enabled", True)
            if not enabled:
                continue
            if not source.is_configured():
                continue
            enabled_sources.append(source)

        def _priority(src: BreachSource) -> int:
            settings = self._breach_source_settings.get(src.name, {})
            return int(settings.get("priority", 100))

        return sorted(enabled_sources, key=_priority)

    def query_all(self, email: str) -> Dict[str, object]:
        start = time.time()
        breaches: List[Dict[str, object]] = []
        sources_queried: List[str] = []
        sources_failed: List[str] = []
        seen = set()
        paste_count = 0

        for source in self.get_enabled_sources():
            sources_queried.append(source.name)
            limiter = self._rate_limiters.get(source.name)
            if limiter:
                limiter.wait(source.name)
            success = True
            result_count = 0
            try:
                results = source.query(email)
                result_count = len(results)
                for item in results:
                    breach_dict = item.to_dict()
                    key = (breach_dict.get("Name"), breach_dict.get("Source"))
                    if key in seen:
                        continue
                    seen.add(key)
                    breaches.append(breach_dict)
            except Exception as exc:
                success = False
                sources_failed.append(source.name)
                logger.error(f"Source '{source.name}' failed for {sanitize_for_logging(email, 'email')}: {exc}")
                results = []

            # Optional paste count support
            if hasattr(source, "last_paste_count"):
                try:
                    paste_count += int(getattr(source, "last_paste_count") or 0)
                except Exception:
                    pass

            self._log_source_query(source.name, email, result_count, success)

        query_time_ms = int((time.time() - start) * 1000)
        response: Dict[str, object] = {
            "email": email,
            "pwned": len(breaches) > 0 or paste_count > 0,
            "breach_count": len(breaches),
            "breaches": breaches,
            "sources_queried": sources_queried,
            "sources_failed": sources_failed,
            "query_time_ms": query_time_ms
        }
        if paste_count:
            response["paste_count"] = paste_count
        return response

    def health_check_all(self) -> Dict[str, Dict[str, object]]:
        results: Dict[str, Dict[str, object]] = {}
        for name, source in self._sources.items():
            health: SourceHealth = source.health_check()
            results[name] = {
                "available": health.available,
                "last_error": health.last_error,
                "response_time_ms": health.response_time_ms
            }
        return results

    def _log_source_query(self, source_name: str, email: str, result_count: int, success: bool) -> None:
        try:
            log_dir = Path("data/osint_logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            email_hash = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()
            log_entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": source_name,
                "email_hash": email_hash,
                "result_count": result_count,
                "success": success
            }
            log_file = log_dir / f"breach_queries_{time.strftime('%Y-%m')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug(f"Failed to log breach query: {exc}")
