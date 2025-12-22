"""Helpers for safe hashing of PII and sensitive identifiers.

Provides HMAC-SHA256 based deterministic identifiers derived from a server-side
secret. This avoids using raw SHA256 on sensitive data which may be vulnerable
to dictionary/brute-force reversal.
"""
from __future__ import annotations

import hmac
import hashlib
import os
from typing import Optional

from .secure_config import SecureConfig


def _get_hmac_key() -> bytes:
    """Get an HMAC key from environment or the SecureConfig encryption key.

    Priority:
    1. Environment variable HMAC_KEY (bytes or utf-8 string)
    2. SecureConfig internal encryption key (generated in .encryption_key)
    """
    env_key = os.getenv("HMAC_KEY")
    if env_key:
        # Allow plain-text key in env for testing; encode to bytes
        return env_key.encode("utf-8")

    sc = SecureConfig()
    return sc._get_or_create_encryption_key()


def hmac_sha256_hex(value: str, key: Optional[bytes] = None, length: Optional[int] = None) -> str:
    """Return an HMAC-SHA256 hex digest of `value`.

    Args:
        value: Input string to derive from
        key: Optional bytes key to use (defaults to internal key)
        length: Optional truncate length of hex digest

    Returns:
        Hex digest (full 64-char SHA256 hex unless truncated)
    """
    if key is None:
        key = _get_hmac_key()

    digest = hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest if length is None else digest[:length]
