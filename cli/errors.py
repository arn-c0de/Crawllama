"""Shared CLI exception type.

Kept in its own module so the extracted CLI helpers (bootstrap, commands) and
``main`` can all raise/catch it without importing each other.
"""


class CrawllamaException(Exception):
    """Custom exception for Crawllama application errors."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message
