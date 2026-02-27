"""GitHub leak source."""
from __future__ import annotations

import os
import time
from typing import List
import logging
import requests

from .base import BreachSource, BreachResult, SourceType

logger = logging.getLogger("crawllama")


class GitHubLeakSource(BreachSource):
    name = "github"
    source_type = SourceType.API_KEYED
    rate_limit_delay = 2.0

    def is_configured(self) -> bool:
        return bool(os.getenv("GITHUB_TOKEN"))

    def _query(self, email: str) -> List[BreachResult]:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return []

        try:
            query = f'"{email}" in:file'
            url = f"https://api.github.com/search/code?q={query}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "user-agent": "CrawlLama-OSINT/1.4.8"
            }
            response = requests.get(url, headers=headers, timeout=15)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return []

            data = response.json()
            total = data.get("total_count", 0)
            items = data.get("items", [])
            if total == 0 or not items:
                return []

            descriptions = []
            for item in items[:5]:
                repo = item.get("repository", {}).get("full_name")
                path = item.get("path")
                if repo and path:
                    descriptions.append(f"{repo}:{path}")

            metadata = {"examples": descriptions} if descriptions else {}

            return [
                BreachResult(
                    name="GitHub",
                    title="GitHub code search findings",
                    breach_date="Unknown",
                    description=(
                        f"Email found in {total} GitHub code search result(s). "
                        "Review repositories for accidental exposure."
                    ),
                    data_classes=["Email addresses"],
                    is_verified=False,
                    is_sensitive=True,
                    source="GitHub",
                    metadata=metadata
                )
            ]
        except Exception as exc:
            logger.debug(f"GitHub leak query failed: {exc}")
            return []
