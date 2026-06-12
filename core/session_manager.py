"""Session management for multi-user support with SQLite."""
import json
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils.secure_hash import hmac_sha256_hex

logger = logging.getLogger("crawllama")

# Maximum number of IP addresses tracked per session (prevents unbounded growth)
MAX_SESSION_IPS = 20

# Database schema
CREATE_TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        api_key TEXT UNIQUE,
        created_at TEXT NOT NULL,
        last_seen TEXT,
        settings TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        metadata TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_history (
        query_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        query TEXT NOT NULL,
        response TEXT,
        timestamp TEXT NOT NULL,
        elapsed_time REAL,
        used_multihop INTEGER DEFAULT 0,
        metadata TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """,
]

CREATE_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active, expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_history_user ON query_history(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_history_session ON query_history(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON query_history(timestamp)",
]


class SessionManager:
    """Manage user sessions with SQLite backend."""

    def __init__(self, db_path: str = "data/history/sessions.db"):
        """
        Initialize session manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Session manager initialized: {db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for SQLite connections with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for statement in CREATE_TABLE_STATEMENTS:
                cursor.execute(statement)

            for statement in CREATE_INDEX_STATEMENTS:
                cursor.execute(statement)

            conn.commit()

        logger.info("Database initialized")

    def create_user(
        self,
        username: str,
        settings: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """
        Create a new user.

        Args:
            username: Username
            settings: Optional user settings

        Returns:
            Dictionary with user_id and api_key
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Derive a stable user identifier using HMAC-SHA256 keyed with an
                # application secret to avoid reversible raw hashes of PII.
                user_id = hmac_sha256_hex(username)
                api_key = secrets.token_urlsafe(32)
                created_at = datetime.now().isoformat()

                settings_json = json.dumps(settings or {})

                cursor.execute("""
                    INSERT INTO users (user_id, username, api_key, created_at, settings)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, api_key, created_at, settings_json))

                conn.commit()

                logger.info(f"Created user: {username} (ID: {user_id})")

                return {
                    "user_id": user_id,
                    "username": username,
                    "api_key": api_key
                }

            except sqlite3.IntegrityError:
                logger.error(f"User '{username}' already exists")
                raise ValueError(f"User '{username}' already exists") from None

    def get_user_by_api_key(self, api_key: str) -> dict[str, Any] | None:
        """
        Get user by API key.

        Args:
            api_key: User's API key

        Returns:
            User data or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT user_id, username, created_at, last_seen, settings
                FROM users
                WHERE api_key = ?
            """, (api_key,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "user_id": row[0],
                "username": row[1],
                "created_at": row[2],
                "last_seen": row[3],
                "settings": json.loads(row[4]) if row[4] else {}
            }

    def create_session(
        self,
        user_id: str,
        duration_hours: int = 24,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Create a new session for a user.

        Args:
            user_id: User ID
            duration_hours: Session duration in hours
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            session_id = secrets.token_urlsafe(24)
            created_at = datetime.now()
            expires_at = created_at + timedelta(hours=duration_hours)

            metadata_json = json.dumps(metadata or {})

            cursor.execute("""
                INSERT INTO sessions (session_id, user_id, created_at, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, created_at.isoformat(), expires_at.isoformat(), metadata_json))

            conn.commit()

            logger.info(f"Created session for user {user_id}: {session_id}")

            return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if expired/invalid
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT session_id, user_id, created_at, expires_at, is_active, metadata
                FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))

            row = cursor.fetchone()

            if not row:
                return None

            # Check if expired
            expires_at = datetime.fromisoformat(row[3])
            if datetime.now() > expires_at:
                self.invalidate_session(session_id)
                return None

            return {
                "session_id": row[0],
                "user_id": row[1],
                "created_at": row[2],
                "expires_at": row[3],
                "is_active": bool(row[4]),
                "metadata": json.loads(row[5]) if row[5] else {}
            }

    def invalidate_session(self, session_id: str):
        """
        Invalidate a session.

        Args:
            session_id: Session ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sessions
                SET is_active = 0
                WHERE session_id = ?
            """, (session_id,))

            conn.commit()

            logger.info(f"Invalidated session: {session_id}")

    def log_query(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str,
        elapsed_time: float,
        used_multihop: bool = False,
        metadata: dict[str, Any] | None = None
    ):
        """
        Log a query to history.

        Args:
            session_id: Session ID
            user_id: User ID
            query: Query text
            response: Response text
            elapsed_time: Query processing time
            used_multihop: Whether multi-hop was used
            metadata: Optional metadata
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            timestamp = datetime.now().isoformat()
            metadata_json = json.dumps(metadata or {})

            cursor.execute("""
                INSERT INTO query_history (
                    session_id, user_id, query, response, timestamp,
                    elapsed_time, used_multihop, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user_id, query, response, timestamp, elapsed_time, int(used_multihop), metadata_json))

            conn.commit()

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get query history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of queries to return
            session_id: Optional session ID to filter by

        Returns:
            List of query records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT query_id, session_id, query, response, timestamp,
                           elapsed_time, used_multihop, metadata
                    FROM query_history
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_id, session_id, limit))
            else:
                cursor.execute("""
                    SELECT query_id, session_id, query, response, timestamp,
                           elapsed_time, used_multihop, metadata
                    FROM query_history
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_id, limit))

            return [self._history_row_to_dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _history_row_to_dict(row: tuple) -> dict[str, Any]:
        """Convert a query_history row to a dictionary."""
        return {
            "query_id": row[0],
            "session_id": row[1],
            "query": row[2],
            "response": row[3],
            "timestamp": row[4],
            "elapsed_time": row[5],
            "used_multihop": bool(row[6]),
            "metadata": json.loads(row[7]) if row[7] else {}
        }

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """
        Get statistics for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total queries
            cursor.execute("""
                SELECT COUNT(*), AVG(elapsed_time), SUM(used_multihop)
                FROM query_history
                WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()

            # Active sessions
            cursor.execute("""
                SELECT COUNT(*)
                FROM sessions
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))

            active_sessions = cursor.fetchone()[0]

            return {
                "total_queries": row[0] if row[0] else 0,
                "avg_elapsed_time": row[1] if row[1] else 0,
                "multihop_queries": row[2] if row[2] else 0,
                "active_sessions": active_sessions
            }

    def cleanup_expired_sessions(self):
        """Deactivate expired sessions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute("""
                UPDATE sessions
                SET is_active = 0
                WHERE expires_at < ? AND is_active = 1
            """, (now,))

            count = cursor.rowcount
            conn.commit()

            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")

            return count

    def purge_old_data(self, days: int = 90) -> dict[str, int]:
        """Delete inactive sessions and old query history to prevent unbounded growth.

        Args:
            days: Delete data older than this many days

        Returns:
            Dictionary with counts of deleted sessions and history entries
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete old query history for inactive sessions
            cursor.execute("""
                DELETE FROM query_history
                WHERE timestamp < ? AND session_id IN (
                    SELECT session_id FROM sessions WHERE is_active = 0
                )
            """, (cutoff,))
            history_deleted = cursor.rowcount

            # Delete old inactive sessions
            cursor.execute("""
                DELETE FROM sessions
                WHERE is_active = 0 AND expires_at < ?
            """, (cutoff,))
            sessions_deleted = cursor.rowcount

            conn.commit()

            if history_deleted > 0 or sessions_deleted > 0:
                logger.info(
                    f"Purged old data: {sessions_deleted} sessions, "
                    f"{history_deleted} history entries (older than {days} days)"
                )

            return {
                "sessions_deleted": sessions_deleted,
                "history_deleted": history_deleted
            }

    # ================================
    # Enhanced Session Security Methods
    # ================================

    def update_session_activity(
        self,
        session_id: str,
        ip_address: str | None = None,
        update_metadata: dict[str, Any] | None = None
    ) -> bool:
        """Update session's last activity timestamp and optionally IP address.
        
        Args:
            session_id: Session ID
            ip_address: Client IP address (optional)
            update_metadata: Additional metadata to merge (optional)
            
        Returns:
            True if session was updated, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get current session
            cursor.execute("""
                SELECT metadata FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return False

            # Parse existing metadata
            metadata = json.loads(row[0]) if row[0] else {}

            # Update last activity
            metadata["last_activity"] = datetime.now().isoformat()

            if ip_address:
                self._track_session_ip(metadata, ip_address)

            # Merge additional metadata
            if update_metadata:
                metadata.update(update_metadata)

            # Update database
            cursor.execute("""
                UPDATE sessions
                SET metadata = ?
                WHERE session_id = ?
            """, (json.dumps(metadata), session_id))

            conn.commit()
            return True

    @staticmethod
    def _track_session_ip(metadata: dict[str, Any], ip_address: str) -> None:
        """Record an IP address in session metadata, capped at MAX_SESSION_IPS."""
        ip_addresses = metadata.setdefault("ip_addresses", [])

        if ip_address not in ip_addresses:
            if len(ip_addresses) >= MAX_SESSION_IPS:
                # Drop oldest IP to stay within limit
                ip_addresses.pop(0)
            ip_addresses.append(ip_address)

        metadata["current_ip"] = ip_address

    def refresh_session(
        self,
        session_id: str,
        extend_hours: int = 24
    ) -> str | None:
        """Refresh (extend) a session's expiration time.
        
        Args:
            session_id: Session ID
            extend_hours: Hours to extend expiration by
            
        Returns:
            New expiration timestamp or None if session invalid
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get current session
            cursor.execute("""
                SELECT expires_at FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Extend from now (not from current expiry) for security
            new_expiry = datetime.now() + timedelta(hours=extend_hours)

            # Update database
            cursor.execute("""
                UPDATE sessions
                SET expires_at = ?
                WHERE session_id = ?
            """, (new_expiry.isoformat(), session_id))

            conn.commit()

            logger.info(f"Refreshed session {session_id}, new expiry: {new_expiry.isoformat()}")
            return new_expiry.isoformat()

    def validate_session_ip(
        self,
        session_id: str,
        ip_address: str,
        strict_mode: bool = False
    ) -> bool:
        """Validate that a session is being accessed from an expected IP.
        
        Args:
            session_id: Session ID
            ip_address: Current client IP address
            strict_mode: If True, only allow original IP. If False, allow any previously seen IP.
            
        Returns:
            True if IP is valid, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get session metadata
            cursor.execute("""
                SELECT metadata FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return False

            metadata = json.loads(row[0]) if row[0] else {}

            # If no IP tracking yet, allow (first access)
            if "ip_addresses" not in metadata:
                return True

            known_ips = metadata["ip_addresses"]

            if strict_mode:
                # Strict mode: must match original IP
                original_ip = known_ips[0] if known_ips else None
                if original_ip != ip_address:
                    logger.warning(
                        f"Session {session_id[:8]}... IP mismatch: "
                        f"expected {original_ip}, got {ip_address}"
                    )
                    return False
                return True

            # Relaxed mode: must be in list of previously seen IPs
            if ip_address not in known_ips:
                logger.warning(
                    f"Session {session_id[:8]}... accessed from unknown IP: {ip_address}"
                )
                return False

            return True

    def get_session_metadata(self, session_id: str) -> dict[str, Any] | None:
        """Get session metadata including IP tracking and activity.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session metadata dictionary or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT session_id, user_id, created_at, expires_at, metadata
                FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            metadata = json.loads(row[4]) if row[4] else {}

            return {
                "session_id": row[0],
                "user_id": row[1],
                "created_at": row[2],
                "expires_at": row[3],
                "last_activity": metadata.get("last_activity"),
                "current_ip": metadata.get("current_ip"),
                "ip_addresses": metadata.get("ip_addresses", []),
                "activity_count": metadata.get("activity_count", 0),
                "metadata": metadata
            }

    def get_all_active_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Get all active sessions, optionally filtered by user.
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            List of active session dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if user_id:
                cursor.execute("""
                    SELECT session_id, user_id, created_at, expires_at, metadata
                    FROM sessions
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT session_id, user_id, created_at, expires_at, metadata
                    FROM sessions
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                """)

            return [self._active_session_row_to_dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _active_session_row_to_dict(row: tuple) -> dict[str, Any]:
        """Convert a sessions row to a display dictionary with truncated IDs."""
        metadata = json.loads(row[4]) if row[4] else {}
        return {
            "session_id": f"{row[0][:16]}...",  # Truncate for display
            "user_id": f"{row[1][:16]}...",
            "created_at": row[2],
            "expires_at": row[3],
            "last_activity": metadata.get("last_activity"),
            "current_ip": metadata.get("current_ip")
        }
