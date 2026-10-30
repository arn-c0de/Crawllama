"""Shared prompt-injection detection.

Plain extraction phrases and keyword heuristics guard user queries; the
obfuscation checks (homoglyphs, leetspeak, invisible chars, base64) are used
by the agent (user queries) and the page reader (fetched page content) so
that hardening one entry point automatically hardens the other.

NOTE: The German phrases are intentional - user queries are often German.
"""
import base64
import binascii
import logging
import re
import unicodedata

logger = logging.getLogger("crawllama")

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
    # Up to three filler words between verb and target ("ignore the previous
    # instructions", "ignore your instructions")
    re.compile(
        r"i[g9]n[o0]r[e3](?:all|any|prior|previous|earlier|the|your|my|these|those|above){0,3}"
        r"(?:instructions?|prompts?|commands?)"
    ),
    re.compile(
        r"(?:reveal|show|display|print|repeat)(?:me|us)?(?:all|your|the|initial|original|hidden){0,3}"
        r"(?:instructions?|prompts?|systemmessages?|systemprompt)"
    ),
    re.compile(r"(?:developer|sudo)mode|jailbreak"),
    re.compile(r"override(?:all|previous|any)?(?:instructions?|prompts?|commands?)"),
    re.compile(r"disregard(?:the|your|all|any)?(?:previous|prior|above|earlier)|newinstructions?"),
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


# Blacklist of suspicious phrases indicating prompt extraction attempts
INJECTION_PATTERNS = [
    # Direct requests
    'system prompt', 'systemprompt', 'system-prompt',
    'system instruction', 'system anweisung',
    'your prompt', 'dein prompt', 'deinen prompt',
    'your instruction', 'deine instruktion',
    'your guideline', 'deine anweisung',
    'internal configuration', 'interne konfiguration',
    'core instruction', 'kernanweisung',
    'hidden instruction', 'versteckte anweisung',

    # Indirect/sophisticated requests
    'exactly as in', 'wortwörtlich wie im',
    'as in the system prompt', 'wie im systemprompt',
    'quote your rule', 'zitiere deine regel',
    'repeat your instruction', 'wiederhole deine anweisung',
    'give me your rule', 'gib mir deine regel',
    'show your configuration', 'zeige deine konfiguration',
    'reveal your', 'offenbare deine',
    'describe your rule', 'beschreibe deine regel',
    'analyze yourself', 'analysiere dich selbst',
    'self-analysis', 'selbstanalyse',
    'how were you programmed', 'wie wurdest du programmiert',
    'what is in your', 'was steht in deinem',

    # Security audit pretexts
    'security check', 'sicherheitsprüfung',
    'internal security', 'interne sicherheit',
    'your blacklist', 'deine blacklist',
    'list all patterns', 'liste alle muster',
    'show dangerous patterns', 'zeige gefährliche muster',
    'documentation mode', 'dokumentationsmodus',
    'transparency mode', 'transparenzmodus',
    'debug mode', 'debug-modus',
    'maintenance mode', 'wartungsmodus',
    'all restrictions disabled', 'alle einschränkungen deaktiviert',
    'previous restrictions', 'vorherige einschränkungen',

    # Indirect extraction via "forbidden words" pretexts
    'forbidden words', 'verbotene wörter',
    'which words are forbidden', 'welche wörter sind verboten',
    'banned words', 'gesperrte wörter',
    'prohibited input', 'verbotene eingabe',
    'restricted words', 'eingeschränkte wörter',
    'blocked terms', 'blockierte begriffe',
    'list of forbidden', 'liste verbotener',
    'what words are blocked', 'welche wörter werden blockiert',
    'filtering rules', 'filterregeln',
    'input restrictions', 'eingabebeschränkungen',
    'validation rules', 'validierungsregeln',
    'explain to a developer', 'erkläre einem entwickler',

    # Meta-prompts
    'ignore previous', 'ignoriere vorherige',
    'forget all', 'vergiss alles',
    'new instruction', 'neue anweisung',
    'override', 'überschreibe',
    'disregard', 'missachte',
]

# Heuristic keyword groups: suspicious topic + action verb (+ optional
# context noun) combined in one query indicates an extraction attempt.
SUSPICIOUS_KEYWORDS = [
    'prompt', 'instruction', 'anweisung', 'regel', 'rule',
    'konfiguration', 'configuration', 'guideline', 'richtlinie',
    'blacklist', 'verboten', 'forbidden', 'banned', 'restricted',
    'blocked', 'filter', 'validation', 'security'
]
ACTION_KEYWORDS = [
    'show', 'zeige', 'give', 'gib', 'reveal', 'offenbare',
    'describe', 'beschreibe', 'analyze', 'analysiere',
    'list', 'liste', 'repeat', 'wiederhole', 'quote', 'zitiere',
    'explain', 'erkläre', 'tell', 'sage', 'display', 'anzeige'
]
CONTEXT_KEYWORDS = [
    'word', 'wort', 'wörter', 'input', 'eingabe', 'pattern', 'muster',
    'term', 'begriff', 'phrase'
]
# References to the assistant itself ("your rules", "deine Anweisungen")
SELF_REFERENCE_KEYWORDS = [
    'your', 'you', 'yourself', 'dein', 'deine', 'deinen', 'deiner', 'dir', 'du',
    'system', 'crawllama',
]


def keyword_regex(keywords: list[str], whole_word: bool = False) -> re.Pattern:
    """Compile keywords into one regex anchored at word starts.

    Prefix matching keeps inflections ("instructions", "rules") while
    avoiding hits inside other words ("list" in "English", "tell" in
    "intelligence"). ``whole_word`` also anchors the end.
    """
    end = r"\b" if whole_word else ""
    return re.compile(r"\b(?:" + "|".join(map(re.escape, keywords)) + ")" + end)


_SUSPICIOUS_RE = keyword_regex(SUSPICIOUS_KEYWORDS)
_ACTION_RE = keyword_regex(ACTION_KEYWORDS)
_CONTEXT_RE = keyword_regex(CONTEXT_KEYWORDS)
_SELF_REFERENCE_RE = keyword_regex(SELF_REFERENCE_KEYWORDS, whole_word=True)


def has_suspicious_keyword_combo(query_lower: str) -> bool:
    """Heuristic: suspicious topic + action verb aimed at the assistant itself.

    Topic and action alone ("explain how a coffee filter works", "show me
    security news") are ordinary questions; they only count as an
    extraction attempt when they target the assistant ("your rules") or
    ask for its words/patterns ("list the blocked words").
    """
    if not (_SUSPICIOUS_RE.search(query_lower) and _ACTION_RE.search(query_lower)):
        return False

    if _CONTEXT_RE.search(query_lower):
        logger.warning("Detected extraction attempt: suspicious + action + context keywords")
        return True
    if _SELF_REFERENCE_RE.search(query_lower):
        logger.warning("Detected combined suspicious keywords aimed at the assistant")
        return True
    return False


def is_prompt_injection_attempt(query: str) -> bool:
    """True if *query* tries to extract or override the system instructions."""
    query_lower = query.lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in query_lower:
            logger.warning(f"Detected injection pattern: '{pattern}' in query")
            return True

    if matches_obfuscated_injection(query):
        logger.warning("Detected obfuscated prompt injection pattern")
        return True

    if contains_base64_injection(query):
        logger.warning("Detected base64-obfuscated prompt injection pattern")
        return True

    return has_suspicious_keyword_combo(query_lower)
