"""
CRUD operations mixin for the memory store.
Handles remember/forget/get/clear/search for all data categories.
"""

import ipaddress
import re
from datetime import datetime
from typing import Any

from utils.logger import Logger

from .constants import DEFAULT_USER_ID

logger = Logger.get(__name__)

# --- Input-validation caps (anti memory-poisoning / prompt-bloat) -----------
# Untrusted content (crawled pages / search results) can reach these methods via
# the "remember those" context-store path, so every stored value is validated:
# size-capped, control-char/marker-rejected, and format-checked before persisting.
MAX_EMAIL_LEN = 254
MAX_PHONE_LEN = 32
MAX_IP_LEN = 45
MAX_USERNAME_LEN = 64
MAX_DOMAIN_LEN = 253
MAX_NOTE_LEN = 4096
MAX_CATEGORY_LEN = 64

_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_CTRL_CHARS_ALLOW_WS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _validate_memory_value(value: str, label: str, max_len: int, allow_newlines: bool = False) -> str:
    """Validate an untrusted value before persisting it; raise ValueError if unsafe.

    Rejects non-strings, empty values, oversized values (token-exhaustion /
    store bloat), control characters, and any attempt to embed the reserved
    ``[EXTERNAL_WEB_CONTENT_*]`` trust-boundary marker.
    """
    if not isinstance(value, str):
        raise ValueError(f"Invalid {label}: must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"Invalid {label}: empty value")
    if len(stripped) > max_len:
        raise ValueError(f"Invalid {label}: exceeds maximum length ({max_len})")
    ctrl_re = _CTRL_CHARS_ALLOW_WS_RE if allow_newlines else _CTRL_CHARS_RE
    if ctrl_re.search(stripped):
        raise ValueError(f"Invalid {label}: contains control characters")
    if "external_web_content_" in stripped.lower():
        raise ValueError(f"Invalid {label}: contains reserved trust-boundary marker")
    return stripped


class OperationsMixin:
    """Mixin providing all CRUD operations for memory categories."""

    def remember_email(self, email: str, metadata: dict | None = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember an email address.

        Args:
            email: Email address to remember
            metadata: Optional metadata (source, timestamp, etc.)
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        # Validate the (possibly untrusted) value before anything else
        email = _validate_memory_value(email, "email", MAX_EMAIL_LEN)
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email: not a valid address")

        # Check quotas BEFORE adding
        if not self._check_user_limit('emails', user_id):
            raise ValueError(
                f"Per-user quota exceeded for emails. "
                f"Limit: {self.per_user_limit} entries per user."
            )

        if not self._check_global_limit('emails'):
            raise ValueError(
                f"Global quota exceeded for emails. "
                f"Limit: {self.global_limit} total entries."
            )

        entry = {
            'value': email.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Sanitize email for logging to prevent sensitive data exposure
        sanitized_email = self._sanitize_email_for_logging(email)

        # Check if already exists
        existing_entry = next((e for e in self.data['emails'] if e['value'] == entry['value']), None)
        if existing_entry:
            # Update metadata if provided
            if metadata:
                existing_entry['metadata'].update(metadata)
                existing_entry['last_updated'] = datetime.now().isoformat()
                self._save()
                logger.info(f"Updated email metadata: {sanitized_email}")
            else:
                logger.info(f"Email {sanitized_email} already in memory")
            return False

        self.data['emails'].append(entry)
        self._save()
        logger.info(f"Remembered email: {sanitized_email} (user: {user_id})")
        return True

    def remember_phone(self, phone: str, metadata: dict | None = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a phone number.

        Args:
            phone: Phone number to remember
            metadata: Optional metadata (country, type, etc.)
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        phone = _validate_memory_value(phone, "phone", MAX_PHONE_LEN)
        if sum(c.isdigit() for c in phone) < 6:
            raise ValueError("Invalid phone: too few digits")

        if not self._check_user_limit('phones', user_id):
            raise ValueError(f"Per-user quota exceeded for phones. Limit: {self.per_user_limit}")

        if not self._check_global_limit('phones'):
            raise ValueError(f"Global quota exceeded for phones. Limit: {self.global_limit}")

        # Normalize phone for storage and duplicate detection
        normalized_phone = self._normalize_phone(phone)

        entry = {
            'value': normalized_phone,
            'original': phone.strip(),  # Keep original format for reference
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Sanitize phone for logging
        sanitized_phone = self._sanitize_phone_for_logging(phone)

        # Check if already exists (compare normalized values)
        if any(self._normalize_phone(p['value']) == normalized_phone for p in self.data['phones']):
            logger.info(f"Phone {sanitized_phone} already in memory")
            return False

        self.data['phones'].append(entry)
        self._save()
        logger.info(f"Remembered phone: {sanitized_phone} (user: {user_id})")
        return True

    def remember_ip(self, ip: str, metadata: dict | None = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember an IP address.

        Args:
            ip: IP address to remember
            metadata: Optional metadata (location, ISP, etc.)
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        ip = _validate_memory_value(ip, "IP", MAX_IP_LEN)
        ipaddress.ip_address(ip)  # raises ValueError on a malformed address

        if not self._check_user_limit('ips', user_id):
            raise ValueError(f"Per-user quota exceeded for IPs. Limit: {self.per_user_limit}")

        if not self._check_global_limit('ips'):
            raise ValueError(f"Global quota exceeded for IPs. Limit: {self.global_limit}")

        entry = {
            'value': ip.strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Check if already exists
        if any(i['value'] == entry['value'] for i in self.data['ips']):
            logger.info(f"IP {ip} already in memory")
            return False

        self.data['ips'].append(entry)
        self._save()
        logger.info(f"Remembered IP: {ip} (user: {user_id})")
        return True

    def remember_username(self, username: str, metadata: dict | None = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a username.

        Args:
            username: Username to remember
            metadata: Optional metadata (platforms, etc.)
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        username = _validate_memory_value(username, "username", MAX_USERNAME_LEN)

        if not self._check_user_limit('usernames', user_id):
            raise ValueError(f"Per-user quota exceeded for usernames. Limit: {self.per_user_limit}")

        if not self._check_global_limit('usernames'):
            raise ValueError(f"Global quota exceeded for usernames. Limit: {self.global_limit}")

        entry = {
            'value': username.strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Check if already exists
        if any(u['value'] == entry['value'] for u in self.data['usernames']):
            logger.info(f"Username {username} already in memory")
            return False

        self.data['usernames'].append(entry)
        self._save()
        logger.info(f"Remembered username: {username} (user: {user_id})")
        return True

    def remember_domain(self, domain: str, metadata: dict | None = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a domain.

        Args:
            domain: Domain to remember
            metadata: Optional metadata
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        domain = _validate_memory_value(domain, "domain", MAX_DOMAIN_LEN)
        if "." not in domain or " " in domain:
            raise ValueError("Invalid domain")

        if not self._check_user_limit('domains', user_id):
            raise ValueError(f"Per-user quota exceeded for domains. Limit: {self.per_user_limit}")

        if not self._check_global_limit('domains'):
            raise ValueError(f"Global quota exceeded for domains. Limit: {self.global_limit}")

        entry = {
            'value': domain.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Check if already exists
        if any(d['value'] == entry['value'] for d in self.data['domains']):
            logger.info("Domain already in memory")  # lgtm[py/clear-text-logging-sensitive-data] - Domain content is not logged to avoid leaking data
            return False

        self.data['domains'].append(entry)
        self._save()
        logger.info("Remembered domain (user redacted)")  # lgtm[py/clear-text-logging-sensitive-data] - User identifiers are not logged
        return True

    def add_note(self, note: str, category: str | None = None, user_id: str = DEFAULT_USER_ID, metadata: dict | None = None) -> bool:
        """
        Add a custom note.

        Args:
            note: Note text
            category: Optional category/tag
            user_id: User identifier for quota tracking
            metadata: Optional metadata dict

        Returns:
            True on success

        Raises:
            ValueError: If the value is invalid or a quota is exceeded
        """
        note = _validate_memory_value(note, "note", MAX_NOTE_LEN, allow_newlines=True)
        if category is not None:
            category = _validate_memory_value(category, "category", MAX_CATEGORY_LEN)

        if not self._check_user_limit('notes', user_id):
            raise ValueError(f"Per-user quota exceeded for notes. Limit: {self.per_user_limit}")

        if not self._check_global_limit('notes'):
            raise ValueError(f"Global quota exceeded for notes. Limit: {self.global_limit}")

        entry = {
            'text': note,
            'category': category,
            'user_id': user_id,
            'added_at': datetime.now().isoformat()
        }

        if metadata:
            entry['metadata'] = metadata

        self.data['notes'].append(entry)
        self._save()
        logger.info(f"Added note: {note[:50]}... (user: {user_id})")
        return True

    def forget_email(self, email: str) -> bool:
        """Remove an email from memory."""
        email = email.lower().strip()
        sanitized_email = self._sanitize_email_for_logging(email)
        original_count = len(self.data['emails'])
        self.data['emails'] = [e for e in self.data['emails'] if e['value'] != email]

        if len(self.data['emails']) < original_count:
            self._save()
            logger.info(f"Forgot email: {sanitized_email}")
            return True
        return False

    def forget_phone(self, phone: str) -> bool:
        """Remove a phone from memory."""
        phone = phone.strip()
        sanitized_phone = self._sanitize_phone_for_logging(phone)
        original_count = len(self.data['phones'])
        self.data['phones'] = [p for p in self.data['phones'] if p['value'] != phone]

        if len(self.data['phones']) < original_count:
            self._save()
            logger.info(f"Forgot phone: {sanitized_phone}")
            return True
        return False

    def forget_ip(self, ip: str) -> bool:
        """Remove an IP from memory."""
        ip = ip.strip()
        original_count = len(self.data['ips'])
        self.data['ips'] = [i for i in self.data['ips'] if i['value'] != ip]

        if len(self.data['ips']) < original_count:
            self._save()
            logger.info(f"Forgot IP: {ip}")
            return True
        return False

    def forget_username(self, username: str) -> bool:
        """Remove a username from memory."""
        username = username.strip()
        original_count = len(self.data['usernames'])
        self.data['usernames'] = [u for u in self.data['usernames'] if u['value'] != username]

        if len(self.data['usernames']) < original_count:
            self._save()
            logger.info(f"Forgot username: {username}")
            return True
        return False

    def clear_all(self) -> bool:
        """Clear all memory data."""
        self.data = {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': [],
            'created_at': self.data.get('created_at'),
            'last_updated': None
        }
        self._save()
        logger.info("Cleared all memory")
        return True

    def clear_category(self, category: str) -> bool:
        """
        Clear specific category.

        Args:
            category: 'emails', 'phones', 'ips', 'usernames', 'domains', or 'notes'

        Returns:
            True on success
        """
        if category in self.data and isinstance(self.data[category], list):
            self.data[category] = []
            self._save()
            logger.info("Cleared category: %s", category)  # lgtm[py/log-injection] - parameterized logging; false positive
            return True
        return False

    def get_all(self) -> dict[str, Any]:
        """
        Get all memory data.

        Returns:
            The full data dictionary
        """
        return self.data

    def get_all_emails(self) -> list[dict]:
        """Get all remembered emails with breach information."""
        return self.data.get('emails', [])

    def get_all_phones(self) -> list[dict]:
        """Get all remembered phones."""
        return self.data.get('phones', [])

    def get_all_ips(self) -> list[dict]:
        """Get all remembered IPs."""
        return self.data.get('ips', [])

    def get_all_usernames(self) -> list[dict]:
        """Get all remembered usernames."""
        return self.data.get('usernames', [])

    def get_all_domains(self) -> list[dict]:
        """Get all remembered domains."""
        return self.data.get('domains', [])

    def get_all_notes(self) -> list[dict]:
        """Get all notes."""
        return self.data.get('notes', [])

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with counts and metadata
        """
        return {
            'emails': len(self.data.get('emails', [])),
            'phones': len(self.data.get('phones', [])),
            'ips': len(self.data.get('ips', [])),
            'usernames': len(self.data.get('usernames', [])),
            'domains': len(self.data.get('domains', [])),
            'notes': len(self.data.get('notes', [])),
            'created_at': self.data.get('created_at'),
            'last_updated': self.data.get('last_updated'),
            'total_entries': sum([
                len(self.data.get('emails', [])),
                len(self.data.get('phones', [])),
                len(self.data.get('ips', [])),
                len(self.data.get('usernames', [])),
                len(self.data.get('domains', [])),
                len(self.data.get('notes', []))
            ])
        }

    def search(self, query: str) -> dict[str, list[dict]]:
        """
        Search across all categories.

        Args:
            query: Search term

        Returns:
            Dictionary with matching entries per category
        """
        query = query.lower()
        results = {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': []
        }

        for email in self.data.get('emails', []):
            if query in email['value'].lower():
                results['emails'].append(email)

        for phone in self.data.get('phones', []):
            if query in phone['value']:
                results['phones'].append(phone)

        for ip in self.data.get('ips', []):
            if query in ip['value']:
                results['ips'].append(ip)

        for username in self.data.get('usernames', []):
            if query in username['value'].lower():
                results['usernames'].append(username)

        for domain in self.data.get('domains', []):
            if query in domain['value'].lower():
                results['domains'].append(domain)

        for note in self.data.get('notes', []):
            if query in note['text'].lower() or (note.get('category') and query in note['category'].lower()):
                results['notes'].append(note)

        return results
