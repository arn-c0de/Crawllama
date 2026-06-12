"""Session state handling for SearchAgent."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("crawllama")


@dataclass
class SessionManager:
    session_file: Path
    max_history: int = 20
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    last_search_results: list[dict[str, Any]] = field(default_factory=list)
    last_search_query: str = ""
    loaded_pages_cache: dict[int, dict[str, Any]] = field(default_factory=dict)
    last_content: dict[str, Any] = field(default_factory=lambda: {
        "type": None,
        "subject": None,
        "summary": None,
    })

    # Maximum loaded pages kept in cache (prevents unbounded context growth)
    MAX_CACHED_PAGES: int = 3

    def record_history(self, query: str, response: str, context_limit: int) -> None:
        self.conversation_history.append({
            "query": query,
            "response": response[:context_limit],
        })
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        # Evict oldest cached pages when cache grows too large
        if len(self.loaded_pages_cache) > self.MAX_CACHED_PAGES:
            def cached_at(item: tuple[int, dict[str, Any]]) -> str:
                return item[1].get("cached_at", "")

            sorted_items = sorted(self.loaded_pages_cache.items(), key=cached_at)
            keys_to_remove = [key for key, _ in sorted_items[:-self.MAX_CACHED_PAGES]]
            for key in keys_to_remove:
                del self.loaded_pages_cache[key]
            logger.debug("Evicted %d old pages from cache", len(keys_to_remove))

    def clear_state(self) -> dict[str, int]:
        stats = {
            "conversation_entries": len(self.conversation_history),
            "search_results": len(self.last_search_results),
        }
        self.conversation_history = []
        self.last_search_results = []
        self.last_search_query = ""
        self.loaded_pages_cache = {}
        self.last_content = {
            "type": None,
            "subject": None,
            "summary": None,
        }
        return stats

    def save(self) -> bool:
        try:
            session_data = {
                "timestamp": datetime.now().isoformat(),
                "conversation_history": self.conversation_history,
                "last_search_results": self.last_search_results,
                "last_search_query": self.last_search_query,
                "loaded_pages_cache": self.loaded_pages_cache,
                "last_content": self.last_content,
            }

            # Write to a temp file and rename: a crash mid-write can no longer
            # truncate/corrupt the existing session file.
            tmp_file = self.session_file.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            tmp_file.replace(self.session_file)

            logger.info(f"Session saved to {self.session_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load(self) -> bool:
        if not self.session_file.exists():
            logger.info("No previous session found")
            return False

        try:
            with open(self.session_file, encoding="utf-8") as f:
                session_data = json.load(f)

            if not isinstance(session_data, dict):
                logger.warning("Session file is not a JSON object; ignoring")
                return False

            # SECURITY: restored session content is untrusted (it can be tampered
            # with on disk and is later fed back into prompts). Enforce expected
            # types and cap list/dict sizes to prevent state poisoning and
            # context bloat.
            def _as_list(value, cap):
                return value[:cap] if isinstance(value, list) else []

            self.conversation_history = _as_list(
                session_data.get("conversation_history"), 200
            )
            self.last_search_results = _as_list(
                session_data.get("last_search_results"), 50
            )
            last_query = session_data.get("last_search_query", "")
            self.last_search_query = last_query if isinstance(last_query, str) else ""

            pages_cache = session_data.get("loaded_pages_cache", {})
            self.loaded_pages_cache = pages_cache if isinstance(pages_cache, dict) else {}

            last_content = session_data.get("last_content")
            default_content = {"type": None, "subject": None, "summary": None}
            self.last_content = last_content if isinstance(last_content, dict) else default_content

            timestamp = session_data.get("timestamp", "unknown")
            logger.info(f"Session loaded from {timestamp}")
            logger.info(
                "Restored: %s conversation entries, %s search results",
                len(self.conversation_history),
                len(self.last_search_results),
            )

            return True

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
