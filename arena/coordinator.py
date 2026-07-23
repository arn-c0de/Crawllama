"""Worktree-per-SHA coordination (plan §18).

To compare two code states fairly, each state must run from **its own checkout**;
two SHAs are never imported into one Python process. The coordinator checks out a
SHA into an isolated ``git worktree``, runs the arena CLI there as a subprocess
(``python -m arena run``), and stores the result into a **shared** arena root so
the two runs can be compared afterwards.

The subprocess uses the current interpreter (``sys.executable``) with the
worktree as its working directory, so it imports *that SHA's* ``arena``/``core``
code while reusing the already-installed dependency environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from arena.compare import ComparisonReport, compare_runs
from arena.store import ArenaStore


class CoordinatorError(RuntimeError):
    """Raised when a worktree run cannot be produced."""


def _git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60, check=False
    )


def run_suite_at_sha(
    sha: str,
    *,
    suite: str,
    profile: str = "mock",
    arena_root: str | os.PathLike[str],
    seed: int = 0,
    repo_root: str = ".",
    timeout_s: int = 600,
) -> str:
    """Run *suite* at commit *sha* in an isolated worktree; return the run id.

    Results are written into the shared *arena_root* (made absolute so the run
    lands there regardless of the worktree cwd).
    """
    arena_root = str(Path(arena_root).resolve())
    with tempfile.TemporaryDirectory(prefix="arena-worktree-") as tmp:
        worktree = str(Path(tmp) / "wt")
        add = _git(["worktree", "add", "--detach", worktree, sha], repo_root)
        if add.returncode != 0:
            raise CoordinatorError(f"git worktree add failed for {sha!r}: {add.stderr.strip()}")
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "arena",
                    "--root", arena_root,
                    "run", "--suite", suite, "--profile", profile,
                    "--seed", str(seed), "--json",
                ],
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            if proc.returncode not in (0, 1):  # 1 == some scenario failed (still a valid run)
                raise CoordinatorError(
                    f"arena run failed at {sha!r} (exit {proc.returncode}): {proc.stderr.strip()[:500]}"
                )
            try:
                summary = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                raise CoordinatorError(f"could not parse run summary at {sha!r}: {exc}") from exc
            return str(summary["run_id"])
        finally:
            _git(["worktree", "remove", "--force", worktree], repo_root)


def compare_shas(
    before_sha: str,
    after_sha: str,
    *,
    suite: str,
    profile: str = "mock",
    arena_root: str | os.PathLike[str],
    seed: int = 0,
    repo_root: str = ".",
    allow_mismatch: set[str] | None = None,
) -> ComparisonReport:
    """Produce runs for two SHAs in worktrees and return a code comparison."""
    before_id = run_suite_at_sha(
        before_sha, suite=suite, profile=profile, arena_root=arena_root, seed=seed, repo_root=repo_root
    )
    after_id = run_suite_at_sha(
        after_sha, suite=suite, profile=profile, arena_root=arena_root, seed=seed, repo_root=repo_root
    )
    store = ArenaStore(arena_root)
    return compare_runs(
        store.read_manifest(before_id),
        store.read_results(before_id),
        store.read_manifest(after_id),
        store.read_results(after_id),
        varying="code",
        allow_mismatch=allow_mismatch or set(),
    )
