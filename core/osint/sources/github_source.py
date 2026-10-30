"""GitHub leak source."""
from __future__ import annotations

import logging
import os

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class GitHubLeakSource(BreachSource):
    name = "github"
    source_type = SourceType.API_KEYED
    rate_limit_delay = 2.0

    def is_configured(self) -> bool:
        return bool(os.getenv("GITHUB_TOKEN"))

    def _query(self, email: str) -> list[BreachResult]:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return []

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            }
            # Pass the query via params= so requests URL-encodes it; interpolating
            # the raw email into the URL would allow query-parameter injection
            # (e.g. an email containing '&', '#' or '?').
            response = self._get(
                "https://api.github.com/search/code",
                headers=headers,
                params={"q": f'"{email}" in:file'},
                timeout=15,
            )

            if not self._response_ok(response):
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
            self._record_failure(exc)
            logger.debug(f"GitHub leak query failed: {exc}")
            return []
