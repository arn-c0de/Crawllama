"""Session state handling for SearchAgent."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("crawllama")


@dataclass
class SessionManager:
    session_file: Path
    max_history: int = 20
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_search_results: List[Dict[str, Any]] = field(default_factory=list)
    last_search_query: str = ""
    loaded_pages_cache: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    last_content: Dict[str, Any] = field(default_factory=lambda: {
        "type": None,
        "subject": None,
        "summary": None,
    })

    def record_history(self, query: str, response: str, context_limit: int) -> None:
        self.conversation_history.append({
            "query": query,
            "response": response[:context_limit],
        })
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def clear_state(self) -> Dict[str, int]:
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

            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

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
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            self.conversation_history = session_data.get("conversation_history", [])
            self.last_search_results = session_data.get("last_search_results", [])
            self.last_search_query = session_data.get("last_search_query", "")
            self.loaded_pages_cache = session_data.get("loaded_pages_cache", {})
            self.last_content = session_data.get("last_content", {
                "type": None,
                "subject": None,
                "summary": None,
            })

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
