"""Atomic, immutable run storage (plan §21).

Layout::

    data/arena/runs/<run_id>/
      manifest.json
      results.jsonl
      events.jsonl
      summary.json
      COMPLETE          # marker written last
    data/arena/index.jsonl

A run is written into ``<run_id>.partial/`` first; every file is flushed and
fsynced, the directory is atomically renamed to its final name, and only then is
the ``COMPLETE`` marker created and the ``index.jsonl`` row appended (under a
file lock). Readers ignore any directory lacking ``COMPLETE``.

Permissions: run directories are ``0o700`` and files ``0o600`` — arena outputs
may contain OSINT/PII, matching the existing owner-only ``data/`` subdirs.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from filelock import FileLock

from arena.schema import Event, RunManifest, RunResult, RunSummary

DEFAULT_ARENA_ROOT = Path("data/arena")
_DIR_MODE = 0o700
_FILE_MODE = 0o600
COMPLETE_MARKER = "COMPLETE"


def _secure_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, _DIR_MODE)
    except OSError:
        pass


def _write_secure(path: Path, text: str) -> None:
    """Write *text* to *path* with owner-only perms and an fsync."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        # os.fdopen closes fd; nothing else to do.
        pass


def _fsync_dir(path: Path) -> None:
    try:
        dfd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


class ArenaStore:
    """Reads and writes immutable run directories under an arena root."""

    def __init__(self, root: str | os.PathLike[str] = DEFAULT_ARENA_ROOT) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.index_path = self.root / "index.jsonl"
        self.datasets_dir = self.root / "datasets"
        self.history_dir = self.root / "history"

    # ------------------------------------------------------------------ #
    # Writing                                                            #
    # ------------------------------------------------------------------ #
    def write_run(
        self,
        manifest: RunManifest,
        results: list[RunResult],
        summary: RunSummary,
        events: list[Event] | None = None,
    ) -> Path:
        """Atomically persist a complete run; returns the final run directory."""
        _secure_mkdir(self.runs_dir)
        final_dir = self.runs_dir / manifest.run_id
        partial_dir = self.runs_dir / f"{manifest.run_id}.partial"
        if partial_dir.exists():
            _rmtree(partial_dir)
        _secure_mkdir(partial_dir)

        _write_secure(partial_dir / "manifest.json", manifest.model_dump_json(indent=2))
        _write_secure(
            partial_dir / "results.jsonl",
            "".join(r.model_dump_json() + "\n" for r in results),
        )
        _write_secure(
            partial_dir / "events.jsonl",
            "".join(e.model_dump_json() + "\n" for e in (events or [])),
        )
        _write_secure(partial_dir / "summary.json", summary.model_dump_json(indent=2))
        _fsync_dir(partial_dir)

        # Atomic publish, then the COMPLETE marker, then index the run.
        os.replace(partial_dir, final_dir)
        _fsync_dir(self.runs_dir)
        _write_secure(final_dir / COMPLETE_MARKER, "")
        _fsync_dir(final_dir)

        self._append_index(summary)
        return final_dir

    def _append_index(self, summary: RunSummary) -> None:
        _secure_mkdir(self.root)
        lock = FileLock(str(self.index_path) + ".lock")
        with lock:
            with open(os.open(self.index_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _FILE_MODE), "a", encoding="utf-8") as fh:
                fh.write(summary.model_dump_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())

    # ------------------------------------------------------------------ #
    # Reading                                                            #
    # ------------------------------------------------------------------ #
    def is_complete(self, run_id: str) -> bool:
        return (self.runs_dir / run_id / COMPLETE_MARKER).exists()

    def list_runs(self) -> list[str]:
        """Sorted run ids for completed runs only (ignores *.partial)."""
        if not self.runs_dir.exists():
            return []
        out = [p.name for p in self.runs_dir.iterdir() if p.is_dir() and (p / COMPLETE_MARKER).exists()]
        return sorted(out)

    def read_manifest(self, run_id: str) -> RunManifest:
        data = json.loads((self.runs_dir / run_id / "manifest.json").read_text(encoding="utf-8"))
        return RunManifest.model_validate(data)

    def read_summary(self, run_id: str) -> RunSummary:
        data = json.loads((self.runs_dir / run_id / "summary.json").read_text(encoding="utf-8"))
        return RunSummary.model_validate(data)

    def read_results(self, run_id: str) -> list[RunResult]:
        path = self.runs_dir / run_id / "results.jsonl"
        out: list[RunResult] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(RunResult.model_validate_json(line))
        return out

    def iter_index(self) -> Iterator[RunSummary]:
        if not self.index_path.exists():
            return
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield RunSummary.model_validate_json(line)

    def find_incomplete(self) -> list[str]:
        """Partial/abandoned run directories (for ``arena doctor``)."""
        if not self.runs_dir.exists():
            return []
        out = []
        for p in self.runs_dir.iterdir():
            if p.is_dir() and (p.name.endswith(".partial") or not (p / COMPLETE_MARKER).exists()):
                out.append(p.name)
        return sorted(out)


def _rmtree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _rmtree(child)
        else:
            child.unlink()
    path.rmdir()
