"""Judge calibration against a small human-labelled set (plan §22).

An uncalibrated judge cannot be a CI gate. :func:`calibrate` runs the judge over
labelled samples and reports agreement, a per-bucket confusion matrix and the
sample count; ``calibrated`` is true only when agreement meets a threshold on a
minimum number of samples. Results must be attached to any judged report.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from arena.scoring.judge import Judge

# A labelled sample: (question, answer, human_label) where label is "good"/"bad".
LabelledSample = tuple[str, str, str]

MIN_SAMPLES = 5
DEFAULT_THRESHOLD = 0.7


def _bucket(score: float, boundary: float = 0.5) -> str:
    return "good" if score >= boundary else "bad"


@dataclass
class CalibrationResult:
    judge_model: str
    prompt_version: str
    sample_count: int
    agreement: float
    confusion: dict[str, int] = field(default_factory=dict)  # keys: "good_good", "good_bad", ...
    failures: int = 0
    threshold: float = DEFAULT_THRESHOLD
    calibrated: bool = False


def calibrate(
    judge: Judge,
    samples: Sequence[LabelledSample],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    boundary: float = 0.5,
) -> CalibrationResult:
    confusion = {"good_good": 0, "good_bad": 0, "bad_good": 0, "bad_bad": 0}
    matches = 0
    scored = 0
    failures = 0

    for question, answer, human in samples:
        result = judge.pointwise(question, answer)
        if result.failed or result.score is None:
            failures += 1
            continue
        predicted = _bucket(result.score, boundary)
        confusion[f"{human}_{predicted}"] = confusion.get(f"{human}_{predicted}", 0) + 1
        scored += 1
        if predicted == human:
            matches += 1

    agreement = (matches / scored) if scored else 0.0
    calibrated = scored >= MIN_SAMPLES and agreement >= threshold and failures == 0
    return CalibrationResult(
        judge_model=judge.model,
        prompt_version=judge.prompt_version,
        sample_count=len(samples),
        agreement=agreement,
        confusion=confusion,
        failures=failures,
        threshold=threshold,
        calibrated=calibrated,
    )
