"""Longitudinal / historical snapshots for a fixed target (plan §9).

Stores an immutable snapshot per (target, date) under
``data/arena/history/<target>/<YYYY-MM-DD>.json`` and builds a timeline. Drift
between consecutive snapshots is attributed with :mod:`arena.drift` (behaviour vs
acquisition vs confounded), holding the manifest to decide *why* the extraction
changed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from arena.store import DEFAULT_ARENA_ROOT

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_target(target: str) -> str:
    return _SAFE.sub("_", target)


class HistoryStore:
    def __init__(self, root: str | os.PathLike[str] = DEFAULT_ARENA_ROOT) -> None:
        self.history_dir = Path(root) / "history"

    def _target_dir(self, target: str) -> Path:
        return self.history_dir / _safe_target(target)

    def write_snapshot(self, target: str, date: str, snapshot: dict[str, Any]) -> Path:
        """Write an immutable snapshot; refuses to overwrite an existing date."""
        target_dir = self._target_dir(target)
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(target_dir, 0o700)
        except OSError:
            pass
        path = target_dir / f"{date}.json"
        if path.exists():
            raise FileExistsError(f"snapshot already exists (immutable): {path}")
        payload = {"target": target, "date": date, **snapshot}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2))
        return path

    def timeline(self, target: str) -> list[dict[str, Any]]:
        """Return snapshots for a target, sorted by date ascending."""
        target_dir = self._target_dir(target)
        if not target_dir.exists():
            return []
        snaps = []
        for path in sorted(target_dir.glob("*.json")):
            snaps.append(json.loads(path.read_text(encoding="utf-8")))
        return snaps

    def targets(self) -> list[str]:
        if not self.history_dir.exists():
            return []
        return sorted(p.name for p in self.history_dir.iterdir() if p.is_dir())
