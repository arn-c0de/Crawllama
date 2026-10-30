"""User-Agent strings sent by CrawlLama, versioned from ``_version.py``.

robots.txt matching uses the ``CrawlLama`` product token, so the version
part can follow the release without changing which rules apply.
"""
from _version import __version__

PRODUCT = f"CrawlLama/{__version__}"
DEFAULT_USER_AGENT = f"{PRODUCT} (AI Research Tool)"


def user_agent(purpose: str) -> str:
    """User agent for a specific component, e.g. ``user_agent("Tor-Check")``."""
    return f"{PRODUCT} {purpose}"
