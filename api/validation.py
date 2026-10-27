"""Stateless input validators and sanitizers for API endpoints.

These helpers raise :class:`fastapi.HTTPException` on invalid input and depend
only on the constants in :mod:`api.constants` plus the standard library, so
they carry no runtime/global state and are safe to import anywhere.
"""
import copy
import os
import re
import unicodedata
from typing import Any

from fastapi import HTTPException, status

from api.constants import (
    DANGEROUS_PLUGIN_NAME_PATTERNS,
    FORBIDDEN_PLUGIN_NAMES,
    MAX_PLUGIN_NAME_LENGTH,
    PLUGIN_NAME_PATTERN,
    VALID_MEMORY_CATEGORIES,
)


def validate_plugin_name(plugin_name: str) -> str:
    """
    Validate plugin name to prevent path traversal attacks.

    Implements multiple security layers:
    1. Unicode normalization to prevent bypass attempts
    2. Length limits to prevent buffer overflow
    3. Whitelist-based character validation
    4. Path traversal pattern detection
    5. Forbidden names blacklist
    6. Absolute path verification

    Args:
        plugin_name: The plugin name to validate

    Returns:
        Validated plugin name

    Raises:
        HTTPException: If validation fails
    """
    if not plugin_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin name cannot be empty."
        )

    # 1. Unicode normalization (NFKC) to prevent Unicode bypass attacks
    # This converts characters like . (Unicode dot) to actual dot
    plugin_name = unicodedata.normalize('NFKC', plugin_name)

    # 2. Length limit to prevent excessively long names
    if len(plugin_name) > MAX_PLUGIN_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plugin name too long. Maximum {MAX_PLUGIN_NAME_LENGTH} characters allowed."
        )

    # 3. Whitelist-based validation - only alphanumeric, underscore, and hyphen
    if not PLUGIN_NAME_PATTERN.match(plugin_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plugin name. Only alphanumeric, underscore, and hyphen allowed."
        )

    # 4. Prevent path traversal patterns
    for pattern in DANGEROUS_PLUGIN_NAME_PATTERNS:
        if pattern in plugin_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid plugin name. Path traversal or dangerous characters detected."
            )

    # 5. Forbidden names blacklist
    if plugin_name.lower() in FORBIDDEN_PLUGIN_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin name is forbidden."
        )

    # 6. Verify that constructed path stays within plugins directory
    plugin_path = os.path.join("plugins", plugin_name)
    plugin_path_normalized = os.path.normpath(plugin_path)

    # Ensure the normalized path still starts with "plugins"
    if not plugin_path_normalized.startswith("plugins" + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plugin path. Security violation detected."
        )

    return plugin_name


def validate_memory_category(category: str) -> str:
    """Validate memory category against whitelist."""
    if category not in VALID_MEMORY_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_MEMORY_CATEGORIES))}"
        )
    return category


# Key parts (split on "_"/"-") that mark a secret; "max_tokens" is not one.
_SENSITIVE_KEY_PARTS = frozenset({
    "secret", "password", "passwd", "token", "credential", "credentials", "apikey",
})
# Compact key fragments ("api_key" -> "apikey") that mark a secret
_SENSITIVE_KEY_FRAGMENTS = ("apikey", "apisecret", "privatekey", "accesskey", "secretkey", "authtoken")
_REDACTED = "***REDACTED***"


def _is_sensitive_key(key: str) -> bool:
    """Return True if a config key names a secret."""
    lowered = str(key).lower()
    parts = set(re.split(r"[_\-.]", lowered))
    compact = re.sub(r"[_\-.]", "", lowered)
    return bool(parts & _SENSITIVE_KEY_PARTS) or any(f in compact for f in _SENSITIVE_KEY_FRAGMENTS)


def _redact_url_userinfo(value: str) -> str:
    """Hide credentials embedded in URLs (scheme://user:pass@host)."""
    return re.sub(r"(?<=://)[^/@\s]+@", "***@", value)


def filter_sensitive_config(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Filter sensitive data from config before returning to client.

    Recurses into nested dicts and lists, redacts values of secret-named keys
    and strips credentials embedded in URL strings.
    """
    def _filter(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: _REDACTED if _is_sensitive_key(key) else _filter(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [_filter(item) for item in value]
        if isinstance(value, str):
            return _redact_url_userinfo(value)
        return value

    return _filter(copy.deepcopy(config_dict))
