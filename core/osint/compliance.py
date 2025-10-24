"""OSINT Compliance and Terms of Use Module.

Ensures OSINT operations comply with:
- Legal requirements
- Ethical guidelines
- Rate limiting
- Audit logging
- Privacy protection
"""

import logging
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from collections import defaultdict

logger = logging.getLogger("crawllama")


class OSINTCompliance:
    """Ensure OSINT operations comply with laws and ethical standards."""

    def __init__(self, log_dir: str = "data/osint_logs", config: dict = None):
        """
        Initialize compliance module.

        Args:
            log_dir: Directory for audit logs
            config: Configuration dictionary (optional)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Get limits from config or use defaults
        osint_config = config.get("osint", {}) if config else {}

        # Rate limiting: requests per hour per user
        self.rate_limits = {
            'email_search': osint_config.get('email_search_limit', 50),
            'phone_search': osint_config.get('phone_search_limit', 50),
            'general_osint': osint_config.get('general_osint_limit', 100)
        }

        # Track requests per user
        self.request_history = defaultdict(list)  # {user_id: [(timestamp, query_type), ...]}

        # Blacklisted patterns (privacy-invasive queries)
        self.blacklist_patterns = [
            'password', 'hack', 'crack', 'exploit',
            'stalk', 'spy', 'surveillance'
        ]

        # Terms accepted status
        self.terms_file = self.log_dir / "terms_accepted.json"
        self.terms_accepted = self._load_terms_status()

        logger.info(f"OSINT Compliance initialized (log_dir: {log_dir})")

    def check_terms_accepted(self, user_id: str = "default") -> bool:
        """
        Check if user has accepted terms of use.

        Args:
            user_id: User identifier

        Returns:
            True if terms accepted
        """
        return self.terms_accepted.get(user_id, False)

    def accept_terms(self, user_id: str = "default"):
        """
        Mark terms as accepted for user.

        Args:
            user_id: User identifier
        """
        self.terms_accepted[user_id] = True
        self._save_terms_status()
        logger.info(f"User {user_id} accepted OSINT terms")

    def check_query(self, query: str, user_id: str = "default", query_type: str = "general_osint") -> tuple:
        """
        Check if query is compliant.

        Args:
            query: Search query
            user_id: User identifier
            query_type: Type of query (email_search, phone_search, general_osint)

        Returns:
            Tuple of (allowed: bool, reason: str)

        Example:
            >>> compliance = OSINTCompliance()
            >>> allowed, reason = compliance.check_query("test@example.com", "user1", "email_search")
            >>> allowed
            True
        """
        # Check terms accepted
        if not self.check_terms_accepted(user_id):
            logger.warning(f"Terms not accepted for user {user_id}")
            return (False, "OSINT terms of use must be accepted first")

        # Check blacklist
        if self._is_blacklisted(query):
            logger.warning(f"Blacklisted query from {user_id}: {query}")
            self._log_violation(user_id, query, "blacklisted_content")
            return (False, "Query contains prohibited content")

        # Check rate limit
        if self._exceeds_rate_limit(user_id, query_type):
            logger.warning(f"Rate limit exceeded for {user_id} ({query_type})")
            self._log_violation(user_id, query, "rate_limit_exceeded")
            return (False, f"Rate limit exceeded for {query_type}")

        # Log query
        self._log_query(user_id, query, query_type)

        # Record request
        self._record_request(user_id, query_type)

        return (True, "Query approved")

    def _is_blacklisted(self, query: str) -> bool:
        """
        Check if query contains blacklisted terms.

        Args:
            query: Search query

        Returns:
            True if blacklisted
        """
        query_lower = query.lower()
        for pattern in self.blacklist_patterns:
            if pattern in query_lower:
                return True
        return False

    def _exceeds_rate_limit(self, user_id: str, query_type: str) -> bool:
        """
        Check if user exceeds rate limit.

        Args:
            user_id: User identifier
            query_type: Type of query

        Returns:
            True if limit exceeded
        """
        now = time.time()
        one_hour_ago = now - 3600

        # Get requests in last hour
        recent_requests = [
            (ts, qtype) for ts, qtype in self.request_history[user_id]
            if ts > one_hour_ago and qtype == query_type
        ]

        # Check limit
        limit = self.rate_limits.get(query_type, 100)
        return len(recent_requests) >= limit

    def _record_request(self, user_id: str, query_type: str):
        """
        Record request for rate limiting.

        Args:
            user_id: User identifier
            query_type: Type of query
        """
        now = time.time()
        self.request_history[user_id].append((now, query_type))

        # Clean up old entries (older than 1 hour)
        one_hour_ago = now - 3600
        self.request_history[user_id] = [
            (ts, qtype) for ts, qtype in self.request_history[user_id]
            if ts > one_hour_ago
        ]

    def _log_query(self, user_id: str, query: str, query_type: str):
        """
        Log OSINT query for audit.

        Args:
            user_id: User identifier
            query: Search query
            query_type: Type of query
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'query': query,
            'query_type': query_type,
            'status': 'approved'
        }

        # Append to log file
        log_file = self.log_dir / f"osint_queries_{datetime.now().strftime('%Y-%m')}.jsonl"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def _log_violation(self, user_id: str, query: str, violation_type: str):
        """
        Log compliance violation.

        Args:
            user_id: User identifier
            query: Search query
            violation_type: Type of violation
        """
        violation_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'query': query,
            'violation_type': violation_type
        }

        # Append to violations log
        violations_file = self.log_dir / "violations.jsonl"
        with open(violations_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(violation_entry, ensure_ascii=False) + '\n')

        logger.warning(f"Violation logged: {violation_type} from {user_id}")

    def _load_terms_status(self) -> Dict[str, bool]:
        """Load terms acceptance status."""
        if self.terms_file.exists():
            try:
                with open(self.terms_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load terms status: {e}")
        return {}

    def _save_terms_status(self):
        """Save terms acceptance status."""
        try:
            with open(self.terms_file, 'w', encoding='utf-8') as f:
                json.dump(self.terms_accepted, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save terms status: {e}")

    def get_usage_stats(self, user_id: str = "default") -> Dict:
        """
        Get usage statistics for user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage stats
        """
        now = time.time()
        one_hour_ago = now - 3600

        # Count requests by type in last hour
        recent_requests = [
            qtype for ts, qtype in self.request_history[user_id]
            if ts > one_hour_ago
        ]

        stats = {
            'user_id': user_id,
            'total_requests_last_hour': len(recent_requests),
            'by_type': {},
            'remaining_limits': {}
        }

        # Count by type
        for query_type in ['email_search', 'phone_search', 'general_osint']:
            count = recent_requests.count(query_type)
            limit = self.rate_limits.get(query_type, 100)
            stats['by_type'][query_type] = count
            stats['remaining_limits'][query_type] = max(0, limit - count)

        return stats

    def display_terms(self) -> str:
        """
        Get terms of use text.

        Returns:
            Terms of use text
        """
        email_limit = self.rate_limits.get('email_search', 50)
        phone_limit = self.rate_limits.get('phone_search', 50)
        general_limit = self.rate_limits.get('general_osint', 100)

        return f"""
╔══════════════════════════════════════════════════════════════╗
║                    OSINT TERMS OF USE                        ║
╚══════════════════════════════════════════════════════════════╝

By using OSINT features, you agree to:

1. Use OSINT features ONLY for legitimate, legal purposes
2. Respect privacy laws (GDPR, CCPA, local regulations)
3. NO harassment, stalking, or intimidation
4. Comply with rate limits and API terms
5. All actions are logged for audit purposes
6. Violations will result in immediate access suspension

✓ Legitimate Use Cases:
  • Security research and threat intelligence
  • Investigative journalism
  • Compliance and due diligence
  • Academic research
  • Legal investigations with proper authorization

✗ Prohibited Use:
  • Stalking or harassment
  • Identity theft or fraud
  • Unauthorized surveillance
  • Privacy violations
  • Any illegal activities

Rate Limits:
  • Email searches: {email_limit}/hour
  • Phone searches: {phone_limit}/hour
  • General OSINT: {general_limit}/hour

All OSINT queries are logged with timestamps and user IDs for
compliance and audit purposes.

By typing 'accept', you acknowledge that you have read and agree
to these terms.
"""
