"""Retention / deletion and index rebuild (plan §8, §23).

Arena outputs may contain OSINT/PII, so deletion must actually remove the
run directory (all artifacts) and the index must be rebuildable from the
surviving run summaries — never left pointing at deleted, PII-bearing data.
"""

from __future__ import annotations

import os
from pathlib import Path

from arena.store import ArenaStore, _rmtree


def delete_run(store: ArenaStore, run_id: str) -> bool:
    """Remove a run directory and all its artifacts. Returns True if deleted.

    ``run_id`` must name a single directory inside ``runs_dir``: an empty id,
    "." / ".." or a path would otherwise delete ``runs_dir`` or its parent.
    """
    if not _is_plain_run_id(run_id):
        raise ValueError(f"Invalid run id: {run_id!r}")
    run_dir = store.runs_dir / run_id
    if run_dir.resolve().parent != store.runs_dir.resolve() or not run_dir.is_dir():
        return False
    _rmtree(run_dir)
    rebuild_index(store)
    return True


def _is_plain_run_id(run_id: str) -> bool:
    """True for a single, non-special path component."""
    return (
        bool(run_id)
        and run_id not in (".", "..")
        and "/" not in run_id
        and "\\" not in run_id
        and Path(run_id).name == run_id
    )


def rebuild_index(store: ArenaStore) -> int:
    """Rewrite index.jsonl from the surviving completed run summaries.

    Returns the number of runs indexed. Any index rows pointing at deleted runs
    are dropped.
    """
    summaries = []
    for run_id in store.list_runs():
        try:
            summaries.append(store.read_summary(run_id))
        except (OSError, ValueError):
            continue
    summaries.sort(key=lambda s: s.run_id)

    tmp = store.index_path.with_suffix(".jsonl.tmp")
    store.root.mkdir(parents=True, exist_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for s in summaries:
            fh.write(s.model_dump_json() + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, store.index_path)
    return len(summaries)


def purge_all(store: ArenaStore) -> int:
    """Delete every run and clear the index. Returns number of runs removed."""
    run_ids = store.list_runs()
    for run_id in run_ids:
        run_dir = store.runs_dir / run_id
        if run_dir.exists():
            _rmtree(run_dir)
    # also drop any incomplete/partial dirs
    if store.runs_dir.exists():
        for p in list(store.runs_dir.iterdir()):
            if p.is_dir():
                _rmtree(p)
    Path(store.index_path).unlink(missing_ok=True)
    return len(run_ids)
