"""Fine-tuning dataset export with eligibility gating (plan §10, §23).

High score is *not* sufficient to export. Eligibility requires: a training-
permitting licence, recorded target consent/provenance, a passing recursive
PII/secret redaction, no prompt secrets or raw private tool responses,
deduplication, train/eval separation, judge/human approval, and traceable
lineage. **An ineligible run cannot be exported even with ``force``** — ``force``
only overrides the default exclusion of arena evaluation cases (contamination),
never the eligibility gate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from arena.redact import contains_pii, redact
from arena.schema import RunResult


class DatasetExportError(RuntimeError):
    """Raised when a dataset cannot be exported (eligibility failure)."""


class Eligibility(BaseModel):
    """The training-eligibility contract (plan §23). All must hold to export."""

    model_config = ConfigDict(extra="forbid")

    license_ok: bool = False
    consent_recorded: bool = False
    redaction_passed: bool = False
    no_prompt_secrets: bool = False
    deduplicated: bool = False
    train_eval_separated: bool = False
    approved: bool = False
    lineage_present: bool = False

    def failing(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if not v]

    @property
    def eligible(self) -> bool:
        return not self.failing()


@dataclass
class SftRecord:
    prompt: str
    response: str
    lineage: dict = field(default_factory=dict)
    is_eval: bool = True  # arena scenarios are evaluation cases by default


@dataclass
class DpoRecord:
    prompt: str
    chosen: str
    rejected: str
    lineage: dict = field(default_factory=dict)
    is_eval: bool = True


def _guard(eligibility: Eligibility) -> None:
    if not eligibility.eligible:
        raise DatasetExportError(
            "run is not eligible for training export; failing: " + ", ".join(eligibility.failing())
        )


def _write_jsonl(rows: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return len(rows)


def export_sft(
    records: list[SftRecord],
    eligibility: Eligibility,
    out_path: str | os.PathLike[str],
    *,
    force: bool = False,
) -> int:
    """Export SFT rows. Refuses ineligible data regardless of ``force``."""
    _guard(eligibility)  # force cannot bypass this
    usable = [r for r in records if force or not r.is_eval]
    rows = [
        {
            "messages": [
                {"role": "user", "content": redact(r.prompt)},
                {"role": "assistant", "content": redact(r.response)},
            ],
            "meta": redact(r.lineage),
        }
        for r in usable
    ]
    return _write_jsonl(rows, Path(out_path))


def export_dpo(
    records: list[DpoRecord],
    eligibility: Eligibility,
    out_path: str | os.PathLike[str],
    *,
    force: bool = False,
) -> int:
    """Export preference (DPO) pairs. Refuses ineligible data regardless of force."""
    _guard(eligibility)
    usable = [r for r in records if (force or not r.is_eval) and r.chosen != r.rejected]
    rows = [
        {
            "prompt": redact(r.prompt),
            "chosen": redact(r.chosen),
            "rejected": redact(r.rejected),
            "meta": redact(r.lineage),
        }
        for r in usable
    ]
    return _write_jsonl(rows, Path(out_path))


def check_redaction(records: list[SftRecord | DpoRecord]) -> bool:
    """True when no residual PII remains after redaction across all records."""
    for r in records:
        parts = [getattr(r, "prompt", "")]
        parts += [getattr(r, "response", ""), getattr(r, "chosen", ""), getattr(r, "rejected", "")]
        if any(contains_pii(redact(p)) for p in parts if p):
            return False
    return True


def sft_records_from_results(
    results: list[RunResult], *, run_id: str, is_eval: bool = True
) -> list[SftRecord]:
    """Build SFT records from a run's results, with source lineage."""
    out: list[SftRecord] = []
    for r in results:
        query = str(r.structured_output.get("query") or r.structured_output.get("answer") or r.scenario_id)
        out.append(
            SftRecord(
                prompt=query,
                response=r.raw_output,
                lineage={"run_id": run_id, "scenario_id": r.scenario_id, "driver": r.driver},
                is_eval=is_eval,
            )
        )
    return out
