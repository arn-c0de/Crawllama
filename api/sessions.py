"""Per-principal conversation sessions for the shared SearchAgent.

The API serves many clients with one SearchAgent. Its conversation state
(history, last search results, loaded pages) lives entirely in
``agent.session``, so each principal gets its own :class:`SessionManager`
that is swapped in for the duration of a request (under
``runtime.agent_lock``). One client can therefore no longer see or continue
another client's results ("show result #1") or conversation.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from pathlib import Path

from core.agent.session import SessionManager
from utils.secure_hash import hmac_sha256_hex


class PrincipalSessions:
    """LRU of per-principal sessions, persisted as one file per principal."""

    def __init__(self, base_dir: str | Path = "data/sessions", max_sessions: int = 256, max_history: int = 20):
        self.base_dir = Path(base_dir)
        self.max_sessions = max_sessions
        self.max_history = max_history
        self._sessions: OrderedDict[str, SessionManager] = OrderedDict()
        self._lock = threading.Lock()

    def session_file(self, principal_id: str) -> Path:
        """File for a principal; the id is hashed so it is filesystem-safe."""
        return self.base_dir / f"{hmac_sha256_hex(principal_id, length=32)}.json"

    def get(self, principal_id: str) -> SessionManager:
        """Return (loading or creating) the session of a principal."""
        with self._lock:
            session = self._sessions.get(principal_id)
            if session is not None:
                self._sessions.move_to_end(principal_id)
                return session

            self.base_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.base_dir, 0o700)  # sessions hold queries/results (PII)
            except OSError:
                pass
            session = SessionManager(session_file=self.session_file(principal_id), max_history=self.max_history)
            session.load()
            self._sessions[principal_id] = session
            # Evicted sessions stay on disk and are reloaded on next use
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return session
