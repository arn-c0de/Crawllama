"""Session management for multi-user support with SQLite."""
import logging
import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import secrets

logger = logging.getLogger("crawllama")


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

    def _init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                api_key TEXT UNIQUE,
                created_at TEXT NOT NULL,
                last_seen TEXT,
                settings TEXT
            )
        """)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Query history table
        cursor.execute("""
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
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON query_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session ON query_history(session_id)")

        conn.commit()
        conn.close()

        logger.info("Database initialized")

    def create_user(
        self,
        username: str,
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Create a new user.

        Args:
            username: Username
            settings: Optional user settings

        Returns:
            Dictionary with user_id and api_key
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            user_id = hashlib.sha256(username.encode()).hexdigest()
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
            raise ValueError(f"User '{username}' already exists")

        finally:
            conn.close()

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Get user by API key.

        Args:
            api_key: User's API key

        Returns:
            User data or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, username, created_at, last_seen, settings
            FROM users
            WHERE api_key = ?
        """, (api_key,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "created_at": row[2],
                "last_seen": row[3],
                "settings": json.loads(row[4]) if row[4] else {}
            }

        return None

    def create_session(
        self,
        user_id: str,
        duration_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
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
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

        logger.info(f"Created session for user {user_id}: {session_id}")

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if expired/invalid
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, user_id, created_at, expires_at, is_active, metadata
            FROM sessions
            WHERE session_id = ? AND is_active = 1
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET is_active = 0
            WHERE session_id = ?
        """, (session_id,))

        conn.commit()
        conn.close()

        logger.info(f"Invalidated session: {session_id}")

    def log_query(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str,
        elapsed_time: float,
        used_multihop: bool = False,
        metadata: Optional[Dict[str, Any]] = None
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
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get query history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of queries to return
            session_id: Optional session ID to filter by

        Returns:
            List of query records
        """
        conn = sqlite3.connect(self.db_path)
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

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "query_id": row[0],
                "session_id": row[1],
                "query": row[2],
                "response": row[3],
                "timestamp": row[4],
                "elapsed_time": row[5],
                "used_multihop": bool(row[6]),
                "metadata": json.loads(row[7]) if row[7] else {}
            })

        return history

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user statistics
        """
        conn = sqlite3.connect(self.db_path)
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

        conn.close()

        return {
            "total_queries": row[0] if row[0] else 0,
            "avg_elapsed_time": row[1] if row[1] else 0,
            "multihop_queries": row[2] if row[2] else 0,
            "active_sessions": active_sessions
        }

    def cleanup_expired_sessions(self):
        """Remove expired sessions from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE sessions
            SET is_active = 0
            WHERE expires_at < ? AND is_active = 1
        """, (now,))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")

        return count
