"""Shared constants, patterns and stop-word sets for hallucination detection."""
# Minimum text similarity for a Wikipedia article to count as supporting a claim.
WIKIPEDIA_SIMILARITY_THRESHOLD = 0.3

# Common words ignored when extracting key terms for fact checking.
FACT_CHECK_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should"
}

# Common words ignored when extracting concepts for context analysis.
CONCEPT_STOP_WORDS = {
    "this", "that", "with", "from", "they", "them", "their", "there",
    "where", "when", "what", "which", "while", "would", "could", "should",
    "about", "above", "after", "again", "against", "before", "below",
    "between", "during", "until", "under", "over"
}

# (negated form, positive form) regex pairs used for contradiction detection.
NEGATION_PATTERNS = [
    (r"not\s+(\w+)", r"\1"),
    (r"no\s+(\w+)", r"\1"),
    (r"never\s+(\w+)", r"\1"),
    (r"cannot\s+(\w+)", r"can \1"),
    (r"isn't\s+(\w+)", r"is \1"),
    (r"aren't\s+(\w+)", r"are \1"),
    (r"wasn't\s+(\w+)", r"was \1"),
    (r"weren't\s+(\w+)", r"were \1")
]

# Patterns indicating vague or hedging language.
VAGUE_LANGUAGE_PATTERNS = [
    r'\b(maybe|perhaps|possibly|might|could be|seems like|appears to)\b',
    r'\b(I think|I believe|I guess|probably|likely)\b',
    r'\b(some|many|several|various|numerous)\b'
]

# Patterns indicating a sentence makes a verifiable factual claim.
FACTUAL_CLAIM_PATTERNS = [
    r'\b(in \d{4}|\d{4}s?)\b',  # Years
    r'\b\d+(\.\d+)?\s*(percent|%|million|billion|thousand)\b',  # Numbers with units
    r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Proper names (simplified)
    r'\b(located in|founded in|established in|created by)\b',  # Factual relationships
]

# Patterns indicating potentially fabricated citations or references.
CITATION_PATTERNS = [
    r'\b(according to|as reported by|studies show|research indicates)\b',
    r'\b(Source:|Reference:|Citation:)\b',
    r'\[\d+\]|\(\d{4}\)',  # Citation markers
]

# Patterns for overly specific information that should be backed by context.
SPECIFIC_INFO_PATTERNS = [
    r'\b\d{1,2}:\d{2}\s*(AM|PM)\b',  # Specific times
    r'\b\$\d+(\.\d{2})?\b',  # Exact prices
    r'\b\d+(\.\d+)?%\b',  # Exact percentages
]

# (positive, negative) regex pairs that signal internal contradictions.
CONTRADICTORY_PATTERN_PAIRS = [
    (r'\b(is|are)\b', r'\b(is not|are not|isn\'t|aren\'t)\b'),
    (r'\b(can|will)\b', r'\b(cannot|can\'t|will not|won\'t)\b'),
    (r'\b(always)\b', r'\b(never)\b'),
    (r'\b(all)\b', r'\b(none|no)\b'),
]

# Weight of a violation by its severity when scoring hallucination confidence.
SEVERITY_WEIGHTS = {"low": 0.1, "medium": 0.3, "high": 0.6}
