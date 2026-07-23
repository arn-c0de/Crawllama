"""LLM-as-judge: retry-once, pairwise, blind ordering, calibration (offline)."""

from arena.scoring.calibration import calibrate
from arena.scoring.judge import Judge


class _Scripted:
    """A fake completion fn returning canned responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, prompt):
        self.calls += 1
        return self.responses.pop(0) if self.responses else "{}"


def test_pointwise_valid():
    j = Judge(_Scripted(['{"score": 0.8, "rationale": "good"}']))
    r = j.pointwise("q", "a")
    assert not r.failed and r.score == 0.8 and r.attempts == 1


def test_pointwise_retries_once_then_succeeds():
    j = Judge(_Scripted(["not json", '{"score": 0.5}']))
    r = j.pointwise("q", "a")
    assert not r.failed and r.score == 0.5 and r.attempts == 2


def test_pointwise_invalid_twice_marks_failed():
    fake = _Scripted(["nope", "still nope"])
    j = Judge(fake)
    r = j.pointwise("q", "a")
    assert r.failed and r.score is None and r.attempts == 2
    assert fake.calls == 2  # tried once, retried once, no more


def test_pointwise_out_of_range_score_fails():
    j = Judge(_Scripted(['{"score": 5}', '{"score": 42}']))
    r = j.pointwise("q", "a")
    assert r.failed


def test_pairwise_winner():
    j = Judge(_Scripted(['{"winner": "second"}']))
    r = j.pairwise("q", "a", "b")
    assert not r.failed and r.winner == "second"


def _marker_judge():
    """A consistent judge: always prefers the response containing 'GOOD'."""

    def complete(prompt):
        # Response 1 appears before Response 2 in the prompt.
        i1 = prompt.find("Response 1:")
        i2 = prompt.find("Response 2:")
        first = prompt[i1:i2]
        return '{"winner": "first"}' if "GOOD" in first else '{"winner": "second"}'

    return Judge(complete)


def test_pairwise_blind_consistent_winner():
    j = _marker_judge()
    res = j.pairwise_blind("q", "GOOD answer", "weak answer")
    assert res.winner == "A"
    assert res.positional_disagreement is False


def test_pairwise_blind_detects_position_bias():
    # A judge that always picks the first response -> A/B and B/A disagree.
    j = Judge(lambda prompt: '{"winner": "first"}')
    res = j.pairwise_blind("q", "answer a", "answer b")
    assert res.positional_disagreement is True
    assert res.winner == "tie"


def test_judge_on_call_hook_fires():
    calls = []
    j = Judge(_Scripted(['{"score": 0.9}']), on_call=lambda: calls.append(1))
    j.pointwise("q", "a")
    assert len(calls) == 1


def test_calibration_agreement_and_flag():
    # Judge scores 'good' answers high, 'bad' low -> perfect agreement.
    def complete(prompt):
        answer_region = prompt.split("Answer:")[1]
        return '{"score": 0.9}' if "GOODANS" in answer_region else '{"score": 0.1}'

    j = Judge(complete)
    samples = [
        ("q", "GOODANS one", "good"),
        ("q", "GOODANS two", "good"),
        ("q", "GOODANS three", "good"),
        ("q", "weak one", "bad"),
        ("q", "weak two", "bad"),
        ("q", "weak three", "bad"),
    ]
    cal = calibrate(j, samples)
    assert cal.agreement == 1.0
    assert cal.calibrated is True
    assert cal.sample_count == 6


def test_uncalibrated_when_too_few_samples():
    j = Judge(lambda p: '{"score": 0.9}')
    cal = calibrate(j, [("q", "a", "good")])
    assert cal.calibrated is False  # below MIN_SAMPLES
