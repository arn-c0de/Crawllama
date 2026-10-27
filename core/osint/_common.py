"""Shared helpers for the OSINT modules.

Small utilities that several intel modules (and the OSINT tool) would otherwise
re-implement. Keep this lean: only things genuinely used in more than one place.
"""

import logging
import socket

from utils.async_utils import run_async
from utils.tor_mode import is_tor_enabled

__all__ = ["DEFAULT_BROWSER_HEADERS", "DEFAULT_USER_AGENTS", "reverse_dns", "run_async"]

logger = logging.getLogger("crawllama")

# Browser-like client identity shared by the OSINT scrapers (ip_intel,
# social_intel) so the lists cannot drift apart again.
DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

DEFAULT_BROWSER_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


def reverse_dns(ip: str) -> tuple[str, list[str]] | None:
    """Reverse-DNS an IP; return (hostname, aliases) or None.

    Skipped in Tor mode: the lookup goes to the local resolver directly and
    would leak the investigated IP. Shared by domain_intel and ip_intel.
    """
    if is_tor_enabled():
        logger.debug("Tor mode active: skipping local reverse DNS lookup")
        return None
    try:
        hostname, aliases, _addresses = socket.gethostbyaddr(ip)
    except OSError as e:  # herror / gaierror / timeout
        logger.debug(f"No reverse DNS for {ip}: {e}")
        return None
    return hostname, aliases
