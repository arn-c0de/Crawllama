"""CLI input helpers with history and line editing."""
from __future__ import annotations

import atexit
from pathlib import Path
from typing import Optional

_HISTORY_PATH = Path("data") / ".cli_history"
_HISTORY_LEN = 1000


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
        import re
        import readline  # type: ignore

        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            if _HISTORY_PATH.exists():
                readline.read_history_file(str(_HISTORY_PATH))
        except (OSError, IOError):
            # History support is optional; continue with interactive input.
            ...

        readline.set_history_length(_HISTORY_LEN)

        def _save_history() -> None:
            try:
                readline.write_history_file(str(_HISTORY_PATH))
            except (OSError, IOError):
                # Ignore history persistence errors without impacting input.
                ...

        atexit.register(_save_history)

        _ANSI_RE = re.compile(r"(\x1b\[[0-9;?]*[ -/]*[@-~])")

        def _readline_safe_prompt(prompt: str) -> str:
            # Mark ANSI escape sequences as non-printing for GNU readline.
            return _ANSI_RE.sub(lambda m: f"\001{m.group(1)}\002", prompt)

        def read_user_input(prompt: str = "\n\033[1;36m❯\033[0m ") -> str:
            return input(_readline_safe_prompt(prompt))

    except Exception:  # pragma: no cover
        def read_user_input(prompt: str = "\n> ") -> str:
            return input(prompt)
