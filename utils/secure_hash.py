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


def hmac_sha256_hex(value: str, key: Optional[bytes] = None, length: Optional[int] = None, algorithm: str = "sha3_256") -> str:
    """Return an HMAC hex digest of `value` using a modern hash algorithm.

    By default this uses SHA3-256 to satisfy strong-hash requirements in static
    analysis tools (SHA-2 or SHA-3 are acceptable for non-password uses). This
    helper is intended for *identifier derivation* (deterministic, keyed
    identifiers for logging/rate-limiting), **not** for password hashing.

    For password hashing / limited input spaces, use a slow KDF (Argon2,
    bcrypt, scrypt, or PBKDF2).

    Args:
        value: Input string to derive from
        key: Optional bytes key to use (defaults to internal key)
        length: Optional truncate length of hex digest
        algorithm: Hash algorithm name from `hashlib` (default: 'sha3_256')

    Returns:
        Hex digest (full 64-char hex unless truncated)
    """
    if key is None:
        key = _get_hmac_key()

    # Choose digest constructor from hashlib. Default is sha3_256 (SHA-3 family).
    digestmod = getattr(hashlib, algorithm)
    digest = hmac.new(key, value.encode("utf-8"), digestmod).hexdigest()
    return digest if length is None else digest[:length]
