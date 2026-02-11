"""Shared constants and regex patterns for SearchAgent."""
import re

# Pre-compiled regex patterns for performance
URL_PATTERN = re.compile(r'https?://[^\s]+')
NAME_PATTERN = re.compile(r'\b[A-ZÄÖÜß][a-zäöüß]+(?: [A-ZÄÖÜß][a-zäöüß]+)+\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(?:\+\d{1,3}[\s.-]?)?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}')

# Result reference patterns
RESULT_REFERENCE_PATTERNS = [
    re.compile(r'\bresults?\s+(\d+)\b'),      # result OR results + number
    re.compile(r'\bergebnisse?\s+(\d+)\b'),  # ergebnis OR ergebnisse + number
    re.compile(r'\bsources?\s+(\d+)\b'),      # source OR sources + number
    re.compile(r'\bquellen?\s+(\d+)\b'),      # quelle OR quellen + number
    re.compile(r'\b(\d+)\.\s*results?\b'),
    re.compile(r'\b(\d+)\.\s*ergebnisse?\b'),
    re.compile(r'\b(\d+)\.\s*sources?\b'),
    re.compile(r'\b(\d+)\.\s*quellen?\b'),
    re.compile(r'\bresults?:\s*\d+'),
    re.compile(r'\bergebnisse?:\s*\d+'),
    re.compile(r'\bsources?:\s*\d+'),
    re.compile(r'\bquellen?:\s*\d+'),
    re.compile(r'\bsearch\s+sources?\b'),
    re.compile(r'\bdurchsuche\s+quellen?\b'),
    re.compile(r'\bsearch\s+in\s+sources?\b'),
    re.compile(r'\bsuche\s+in\s+quellen?\b'),
    re.compile(r'\banalyze\s+.*sources?\b'),
    re.compile(r'\banalysiere\s+.*quellen?\b'),
    re.compile(r'\bsummarize\s+.*sources?\b'),
    re.compile(r'\bfasse.*zusammen\s+.*quellen?\b'),
    re.compile(r'\bcompare\s+.*sources?\b'),
    re.compile(r'\bvergleiche\s+.*quellen?\b'),
    re.compile(r'\bin\s+sources?\s+(\d+)\b'),
    re.compile(r'\bin\s+quellen?\s+(\d+)\b'),
    re.compile(r'\bin\s+results?\s+(\d+)\b'),
    re.compile(r'\bin\s+ergebnisse?\s+(\d+)\b')
]

# Additional patterns
PATTERN_1A = re.compile(r'(?:results?|sources?|ergebnisse?|quellen?)\s+(\d+)')
PATTERN_1B = re.compile(r'(?:results?|sources?|ergebnisse?|quellen?):\s*(\d+)')
PATTERN_2 = re.compile(r'\b(\d+)\b')
RESULT_PATTERN = re.compile(r'(?:result|source|ergebnis|quelle)\s*(\d+)')

# Follow-up detection patterns
FOLLOWUP_PATTERNS = [
    re.compile(r'\b(wo|was|wer|wie|warum|wann|welche?)\b'),
    re.compile(r'\b(where|what|who|how|why|when|which)\b'),
    re.compile(r'\b(mehr|details?|genauer|weiter)\b'),
    re.compile(r'\b(more|details?|further)\b')
]
