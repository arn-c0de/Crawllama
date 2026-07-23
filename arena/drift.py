"""Drift attribution (plan §9, §20).

Separates two kinds of change between two runs of the *same target*:

* **behaviour drift** — same evidence, different code/model → the *reasoning*
  changed. Defensible and certain.
* **acquisition (world) drift** — same pinned profile, different evidence → the
  *target/world* changed. Reported with uncertainty (model nondeterminism,
  provider revisions and transient failures can also change evidence).
* **confounded** — both evidence and profile changed → never auto-labelled as
  world or behaviour drift; reported separately.

The earlier over-strong claim ("same model+SHA ⇒ every difference is world drift")
is explicitly rejected: acquisition drift is uncertain, and confounded cases are
never attributed automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from arena.compare import comparison_dimensions
from arena.schema import RunManifest

DriftKind = Literal["identical", "behaviour", "acquisition", "confounded"]


@dataclass
class DriftClassification:
    kind: DriftKind
    evidence_changed: bool
    profile_changed: bool
    certain: bool
    detail: str


def _profile_changed(before: RunManifest, after: RunManifest) -> bool:
    db, da = comparison_dimensions(before), comparison_dimensions(after)
    return db["code"] != da["code"] or db["model"] != da["model"]


def classify_drift(before: RunManifest, after: RunManifest) -> DriftClassification:
    """Classify the drift between two runs; never guess on confounded inputs."""
    db, da = comparison_dimensions(before), comparison_dimensions(after)
    evidence_changed = db["evidence"] != da["evidence"]
    profile_changed = _profile_changed(before, after)

    if not evidence_changed and not profile_changed:
        return DriftClassification(
            "identical", False, False, True,
            "same evidence and same profile; any output difference is nondeterminism",
        )
    if not evidence_changed and profile_changed:
        return DriftClassification(
            "behaviour", False, True, True,
            "same evidence, different code/model → behaviour difference",
        )
    if evidence_changed and not profile_changed:
        return DriftClassification(
            "acquisition", True, False, False,
            "same pinned profile, different evidence → likely world/acquisition drift (uncertain)",
        )
    return DriftClassification(
        "confounded", True, True, False,
        "evidence AND profile changed → confounded; reported separately, not attributed",
    )


@dataclass
class FieldDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def snapshot_field_diff(before: dict[str, Any], after: dict[str, Any]) -> FieldDiff:
    """Diff two extracted-field snapshots (e.g. an OSINT domain profile)."""
    diff = FieldDiff()
    keys = sorted(set(before) | set(after))
    for k in keys:
        if k not in before:
            diff.added.append(k)
        elif k not in after:
            diff.removed.append(k)
        elif before[k] != after[k]:
            diff.changed.append(k)
        else:
            diff.unchanged.append(k)
    return diff
