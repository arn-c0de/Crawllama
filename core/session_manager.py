"""Session management for multi-user support with SQLite."""
import logging
import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import secrets
from utils.secure_hash import hmac_sha256_hex

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

    # ================================
    # Enhanced Session Security Methods
    # ================================

    def update_session_activity(
        self,
        session_id: str,
        ip_address: Optional[str] = None,
        update_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update session's last activity timestamp and optionally IP address.
        
        Args:
            session_id: Session ID
            ip_address: Client IP address (optional)
            update_metadata: Additional metadata to merge (optional)
            
        Returns:
            True if session was updated, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
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
            
            # Update IP address if provided
            if ip_address:
                if "ip_addresses" not in metadata:
                    metadata["ip_addresses"] = []
                
                # Track all IP addresses used in session (for security auditing)
                if ip_address not in metadata["ip_addresses"]:
                    metadata["ip_addresses"].append(ip_address)
                
                metadata["current_ip"] = ip_address
            
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
            
        finally:
            conn.close()

    def refresh_session(
        self,
        session_id: str,
        extend_hours: int = 24
    ) -> Optional[str]:
        """Refresh (extend) a session's expiration time.
        
        Args:
            session_id: Session ID
            extend_hours: Hours to extend expiration by
            
        Returns:
            New expiration timestamp or None if session invalid
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get current session
            cursor.execute("""
                SELECT expires_at FROM sessions
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Calculate new expiration
            current_expiry = datetime.fromisoformat(row[0])
            
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
            
        finally:
            conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
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
            
            if strict_mode:
                # Strict mode: must match original IP
                original_ip = metadata["ip_addresses"][0] if metadata["ip_addresses"] else None
                if original_ip != ip_address:
                    logger.warning(
                        f"Session {session_id[:8]}... IP mismatch: "
                        f"expected {original_ip}, got {ip_address}"
                    )
                    return False
            else:
                # Relaxed mode: must be in list of previously seen IPs
                if ip_address not in metadata["ip_addresses"]:
                    logger.warning(
                        f"Session {session_id[:8]}... accessed from unknown IP: {ip_address}"
                    )
                    return False
            
            return True
            
        finally:
            conn.close()

    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session metadata including IP tracking and activity.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session metadata dictionary or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
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
            
        finally:
            conn.close()

    def get_all_active_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active sessions, optionally filtered by user.
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            List of active session dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
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
            
            rows = cursor.fetchall()
            
            sessions = []
            for row in rows:
                metadata = json.loads(row[4]) if row[4] else {}
                sessions.append({
                    "session_id": row[0][:16] + "...",  # Truncate for display
                    "user_id": row[1][:16] + "...",
                    "created_at": row[2],
                    "expires_at": row[3],
                    "last_activity": metadata.get("last_activity"),
                    "current_ip": metadata.get("current_ip")
                })
            
            return sessions
            
        finally:
            conn.close()
