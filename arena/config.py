"""Behaviour-relevant config fingerprinting.

``config_hash`` covers only *canonical, behaviour-relevant* values so that two
runs with the same effective configuration produce the same hash and are
directly comparable. Secrets are never stored or hashed: any key whose name
looks secret-like is replaced with a presence marker (e.g. ``"present"`` /
``"absent"``) before hashing (plan §21).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Substrings that mark a config/env key as secret. Matched case-insensitively.
_SECRET_MARKERS = ("key", "token", "secret", "password", "passwd", "credential", "api_key", "auth")


def _looks_secret(key: str) -> bool:
    k = key.lower()
    return any(marker in k for marker in _SECRET_MARKERS)


def redact_secrets(value: Any) -> Any:
    """Recursively replace secret-looking leaf values with a presence marker.

    A dict key that looks secret-like has its value replaced by ``"present"``
    (truthy) or ``"absent"`` (falsy/empty) rather than the raw secret.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _looks_secret(str(k)):
                out[str(k)] = "present" if v not in (None, "", 0, False) else "absent"
            else:
                out[str(k)] = redact_secrets(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_secrets(v) for v in value]
    return value


def canonicalise(config: dict[str, Any]) -> dict[str, Any]:
    """Produce the redacted, canonical form used for hashing/reporting."""
    return redact_secrets(config or {})


def config_hash(config: dict[str, Any]) -> str:
    """Deterministic SHA-256 over the canonical, secret-redacted config."""
    canonical = canonicalise(config)
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def content_hash(obj: Any) -> str:
    """Stable SHA-256 fingerprint of arbitrary JSON-able content."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()
