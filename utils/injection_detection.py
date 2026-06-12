"""Shared obfuscated prompt-injection detection.

Used by the agent (user queries) and the page reader (fetched page content)
so that hardening one entry point automatically hardens the other.
"""
import base64
import binascii
import re
import unicodedata

# Cyrillic homoglyph -> Latin map applied before injection matching
HOMOGLYPH_MAP = str.maketrans({
    "а": "a", "А": "A",
    "е": "e", "Е": "E",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "с": "c", "С": "C",
    "у": "y", "У": "Y",
    "х": "x", "Х": "X",
    "і": "i", "І": "I",
    "ј": "j", "Ј": "J",
})

# Leetspeak digits/symbols -> letters (applied after lowercasing)
LEETSPEAK_MAP = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "$": "s",
    "@": "a",
})

# Soft hyphen, zero-width and bidi-control characters used to hide keywords
INVISIBLE_CHARS_PATTERN = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
BASE64_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9+/]{20,}={0,2}\b")

# Matched against normalized (compacted) text, so no whitespace handling needed.
OBFUSCATED_INJECTION_PATTERNS = [
    re.compile(r"i[g9]n[o0]r[e3](?:all|any|prior|previous){0,2}(?:instructions?|prompts?|commands?)"),
    re.compile(r"(?:reveal|show|display)(?:all|your|the)?(?:instructions?|prompts?|systemmessages?|systemprompt)"),
    re.compile(r"(?:developer|sudo)mode|jailbreak"),
    re.compile(r"override(?:all|previous|any)?(?:instructions?|prompts?|commands?)"),
    re.compile(r"disregard(?:all|previous|above)|newinstructions?"),
]


def normalize_for_injection_detection(text: str) -> str:
    """Collapse homoglyphs, leetspeak and invisible characters for matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(HOMOGLYPH_MAP)
    normalized = INVISIBLE_CHARS_PATTERN.sub("", normalized)
    normalized = normalized.lower().translate(LEETSPEAK_MAP)
    return NON_ALNUM_PATTERN.sub("", normalized)


def matches_compact_injection_patterns(compact_text: str) -> bool:
    """Check already-normalized (compacted) text against injection indicators."""
    if not compact_text:
        return False
    return any(pattern.search(compact_text) for pattern in OBFUSCATED_INJECTION_PATTERNS)


def matches_obfuscated_injection(text: str) -> bool:
    """Normalize a raw string and check it for obfuscated injection patterns."""
    return matches_compact_injection_patterns(normalize_for_injection_detection(text))


def contains_base64_injection(text: str) -> bool:
    """Decode base64-looking tokens and check them for injection patterns."""
    for token in BASE64_TOKEN_PATTERN.findall(text):
        padded = token + "=" * ((4 - len(token) % 4) % 4)
        try:
            decoded = base64.b64decode(padded, validate=True).decode("utf-8", errors="ignore")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if matches_obfuscated_injection(decoded):
            return True
    return False


def contains_obfuscated_injection(text: str) -> bool:
    """Full check: normalized pattern match plus base64-decoded token contents."""
    return matches_obfuscated_injection(text) or contains_base64_injection(text)
