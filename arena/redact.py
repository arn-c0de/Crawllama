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
    # OpenAI/Anthropic style keys incl. "sk-proj-..." and "sk-ant-api03-..."
    ("[REDACTED_KEY]", re.compile(r"sk-[A-Za-z0-9_-]{16,}")),
    ("[REDACTED_KEY]", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("[REDACTED_KEY]", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("[REDACTED_KEY]", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("[REDACTED_KEY]", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("[REDACTED_KEY]", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("[REDACTED_KEY]", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("[REDACTED_KEY]", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("[REDACTED_IP]", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    # IPv6: full form (4+ groups) or compressed with "::"
    ("[REDACTED_IP]", re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}\b")),
    ("[REDACTED_IP]", re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}\b")),
    # ISO dates (2024-01-15) are not phone numbers
    ("[REDACTED_PHONE]", re.compile(r"(?<!\w)(?!\d{4}-\d{2}-\d{2}(?!\d))\+?\d[\d\s().-]{7,}\d(?!\w)")),
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
        # Keys can carry PII too (e.g. {"bob@x.com": ...})
        return {redact(k) if isinstance(k, str) else k: redact(v) for k, v in value.items()}
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
        for k, v in value.items():
            _scan(k, found)
            _scan(v, found)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _scan(v, found)


def contains_pii(value: Any) -> bool:
    return bool(find_pii(value))
