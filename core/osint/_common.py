"""Shared helpers for the OSINT modules.

Small utilities that several intel modules (and the OSINT tool) would otherwise
re-implement. Keep this lean: only things genuinely used in more than one place.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

__all__ = ["DEFAULT_BROWSER_HEADERS", "DEFAULT_USER_AGENTS", "run_async"]

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


def run_async(coro: Coroutine) -> Any:
    """Run a coroutine to completion from synchronous code.

    Modern replacement for the ``get_event_loop()`` / ``new_event_loop()`` /
    ``set_event_loop()`` dance that was copy-pasted across the OSINT modules.
    ``asyncio.run()`` creates a fresh event loop and closes it cleanly, which
    also fixes the loop leak the old email path had.

    Falls back to a dedicated loop only in the rare case where a loop is already
    running in the current thread (these are sync entry points, so that is the
    exception, not the rule).
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
