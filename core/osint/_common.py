"""Shared helpers for the OSINT modules.

Small utilities that several intel modules (and the OSINT tool) would otherwise
re-implement. Keep this lean: only things genuinely used in more than one place.
"""

import asyncio
from typing import Any, Coroutine

__all__ = ["run_async"]


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
