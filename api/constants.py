"""Shared limits and validation constants for the API layer.

These are plain, import-time constants with no runtime/global state, so they
can be imported freely by models, validators and endpoints without creating
import cycles.
"""
import re

# ----- Request size limits -----
MAX_QUERY_LENGTH = 5000  # Maximum query length
MAX_MEMORY_ENTRIES = 10000  # Maximum memory entries per category

# ----- Plugin name validation (path-traversal hardening) -----
MAX_PLUGIN_NAME_LENGTH = 50
PLUGIN_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
DANGEROUS_PLUGIN_NAME_PATTERNS = ("..", "/", "\\", "\0", "%")
FORBIDDEN_PLUGIN_NAMES = frozenset({
    ".", "..", "__init__", "config", "secret", "secrets",
    "env", ".env", "password", "key", "token",
    "con", "prn", "aux", "nul",  # Windows reserved names
    "com1", "com2", "lpt1", "lpt2",  # Windows reserved names
})

# ----- Memory category whitelist -----
VALID_MEMORY_CATEGORIES = {
    "email", "phone", "ip", "username", "domain", "note",
    "emails", "phones", "ips", "usernames", "domains", "notes",
}
