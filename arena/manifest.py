"""Run identity and reproducibility capture (plan §21).

Builds the :class:`arena.schema.RunManifest`: a sortable ``run_id``, git state,
the config fingerprint, a scenario-set hash and *sanitised* host metadata. Host
metadata deliberately excludes usernames, home paths, environment dumps and raw
GPU serials.

``run_id`` is a ULID-like, lexicographically sortable identifier (48-bit ms
timestamp + 80 bits of randomness, Crockford base32) so that a directory listing
is chronological without a separate index. It is *not* the comparison identity —
comparability is a separate content fingerprint.
"""

from __future__ import annotations

import os
import platform
import secrets
import subprocess  # nosec B404 - fixed argv lists, never shell=True
import sys
import time
from datetime import UTC, datetime

from arena import WORKER_PROTOCOL_VERSION
from arena.config import config_hash, content_hash
from arena.schema import Profile, RunManifest

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_run_id() -> str:
    """ULID-like sortable id: 10 chars time + 16 chars randomness."""
    ms = int(time.time() * 1000)
    rand = secrets.randbits(80)
    return _base32(ms, 10) + _base32(rand, 16)


def _run_git(args: list[str], cwd: str) -> str | None:
    try:
        # argv list (never shell=True); "git" is intentionally resolved from PATH
        out = subprocess.run(  # nosec B603, B607
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_state(cwd: str = ".") -> tuple[str, bool]:
    """Return (git_sha, dirty). Falls back to ('unknown', True) outside a repo."""
    sha = _run_git(["rev-parse", "HEAD"], cwd)
    if sha is None:
        return "unknown", True
    status = _run_git(["status", "--porcelain"], cwd)
    dirty = bool(status)  # any output => working tree has changes
    return sha, dirty


def host_metadata() -> dict[str, object]:
    """Best-effort, privacy-sanitised host description (no user/home/env dump)."""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "cpu_count": os.cpu_count(),
    }


def build_manifest(
    *,
    profile: Profile,
    suite_id: str,
    scenario_set: object,
    effective_config: dict | None = None,
    seed: int = 0,
    cwd: str = ".",
    evidence_hash: str = "",
    now: datetime | None = None,
) -> RunManifest:
    """Assemble a fully-populated, reproducible manifest."""
    from arena.scoring import policy_fingerprint

    sha, dirty = git_state(cwd)
    created = (now or datetime.now(UTC)).isoformat()
    return RunManifest(
        run_id=new_run_id(),
        created_at=created,
        git_sha=sha,
        git_dirty=dirty,
        config_hash=config_hash(effective_config or {}),
        profile=profile,
        suite_id=suite_id,
        scenario_set_hash=content_hash(scenario_set),
        seed=seed,
        host=host_metadata(),
        worker_protocol_version=WORKER_PROTOCOL_VERSION,
        scorer_hash=policy_fingerprint(),
        evidence_hash=evidence_hash,
    )
