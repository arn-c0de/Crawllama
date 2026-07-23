"""Recursive PII/secret redaction for dataset export (plan §10, §17, §23).

``core.memory.SanitizationMixin`` only masks email/phone for logging; it is not a
dataset redactor. This module recursively walks arbitrary JSON-able structures
and replaces emails, phone numbers, IP addresses and common secret tokens with
stable placeholders, and can *audit* a structure for any residual PII — the check
that gates dataset eligibility.
"""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("[REDACTED_EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("[REDACTED_KEY]", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("[REDACTED_KEY]", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("[REDACTED_KEY]", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("[REDACTED_KEY]", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("[REDACTED_IP]", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("[REDACTED_PHONE]", re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")),
]


def redact_text(text: str) -> str:
    for placeholder, pattern in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def redact(value: Any) -> Any:
    """Return a deep copy of *value* with PII/secrets replaced by placeholders."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def find_pii(value: Any) -> list[str]:
    """Return a list of PII/secret categories still present in *value*."""
    found: set[str] = set()
    _scan(value, found)
    return sorted(found)


def _scan(value: Any, found: set[str]) -> None:
    if isinstance(value, str):
        for placeholder, pattern in _PATTERNS:
            if pattern.search(value):
                found.add(placeholder)
    elif isinstance(value, dict):
        for v in value.values():
            _scan(v, found)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _scan(v, found)


def contains_pii(value: Any) -> bool:
    return bool(find_pii(value))
