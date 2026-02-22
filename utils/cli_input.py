"""CLI input helpers with history and line editing."""
from __future__ import annotations

import atexit
import logging
from pathlib import Path
from typing import Optional

_HISTORY_PATH = Path("data") / ".cli_history"
_HISTORY_LEN = 1000
logger = logging.getLogger("crawllama")


try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.history import FileHistory

    _SESSION: Optional[PromptSession] = None

    def _get_session() -> PromptSession:
        global _SESSION
        if _SESSION is None:
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SESSION = PromptSession(history=FileHistory(str(_HISTORY_PATH)))
        return _SESSION

    def read_user_input(prompt: str = "\n\033[1;36m❯\033[0m ") -> str:
        session = _get_session()
        return session.prompt(ANSI(prompt))

except Exception:  # pragma: no cover - fallback for environments without prompt_toolkit
    try:
        import readline  # type: ignore

        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            if _HISTORY_PATH.exists():
                readline.read_history_file(str(_HISTORY_PATH))
        except Exception as exc:
            logger.debug("Unable to load CLI history file: %s", exc)

        readline.set_history_length(_HISTORY_LEN)

        def _save_history() -> None:
            try:
                readline.write_history_file(str(_HISTORY_PATH))
            except Exception as exc:
                logger.debug("Unable to persist CLI history file: %s", exc)

        atexit.register(_save_history)

        def read_user_input(prompt: str = "\n\033[1;36m❯\033[0m ") -> str:
            return input(prompt)

    except Exception:  # pragma: no cover
        def read_user_input(prompt: str = "\n> ") -> str:
            return input(prompt)
