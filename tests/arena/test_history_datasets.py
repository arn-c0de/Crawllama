"""Milestone F: drift attribution, redaction, dataset eligibility, retention."""

import pytest

from arena.datasets import (
    DatasetExportError,
    DpoRecord,
    Eligibility,
    SftRecord,
    check_redaction,
    export_dpo,
    export_sft,
)
from arena.drift import classify_drift, snapshot_field_diff
from arena.history import HistoryStore
from arena.manifest import build_manifest
from arena.redact import contains_pii, find_pii, redact
from arena.retention import delete_run, purge_all, rebuild_index
from arena.runner import ArenaRunner
from arena.schema import Profile
from arena.store import ArenaStore


def _manifest(profile, evidence_hash=""):
    return build_manifest(
        profile=profile, suite_id="smoke", scenario_set=[{"id": "a"}], evidence_hash=evidence_hash
    )


# --------------------------------------------------------------------------- #
# Drift attribution                                                            #
# --------------------------------------------------------------------------- #
def test_same_evidence_different_profile_is_behaviour():
    a = _manifest(Profile(id="p1", provider="ollama", model="qwen"), evidence_hash="sha256:E")
    b = _manifest(Profile(id="p2", provider="ollama", model="llama"), evidence_hash="sha256:E")
    d = classify_drift(a, b)
    assert d.kind == "behaviour" and d.certain is True


def test_confounded_is_never_attributed():
    a = _manifest(Profile(id="p1", provider="ollama", model="qwen"), evidence_hash="sha256:E1")
    b = _manifest(Profile(id="p2", provider="ollama", model="llama"), evidence_hash="sha256:E2")
    d = classify_drift(a, b)
    assert d.kind == "confounded"
    assert d.kind not in ("behaviour", "acquisition")  # never mislabelled
    assert d.certain is False


def test_same_profile_different_evidence_is_acquisition_uncertain():
    p = Profile(id="p1", provider="ollama", model="qwen")
    a = _manifest(p, evidence_hash="sha256:E1")
    b = _manifest(p, evidence_hash="sha256:E2")
    # Force identical code dimension (both dirty worktree, same sha) via copy
    b = b.model_copy(update={"git_sha": a.git_sha, "git_dirty": a.git_dirty})
    d = classify_drift(a, b)
    assert d.kind == "acquisition" and d.certain is False


def test_snapshot_field_diff():
    diff = snapshot_field_diff({"mx": 1, "ip": 2, "ssl": 3}, {"mx": 1, "ip": 9, "subdomain": 4})
    assert diff.added == ["subdomain"]
    assert diff.removed == ["ssl"]
    assert diff.changed == ["ip"]
    assert diff.unchanged == ["mx"]


# --------------------------------------------------------------------------- #
# Redaction                                                                    #
# --------------------------------------------------------------------------- #
def test_redact_pii_recursively():
    data = {"a": "mail me at john@example.com", "b": ["ip 10.0.0.1", {"c": "sk-ABCDEFGHIJKLMNOP12345"}]}
    red = redact(data)
    assert not contains_pii(red)
    assert "REDACTED" in red["a"]
    assert find_pii(data)  # original had PII


# --------------------------------------------------------------------------- #
# Dataset eligibility                                                          #
# --------------------------------------------------------------------------- #
def _eligible():
    return Eligibility(
        license_ok=True, consent_recorded=True, redaction_passed=True, no_prompt_secrets=True,
        deduplicated=True, train_eval_separated=True, approved=True, lineage_present=True,
    )


def test_ineligible_cannot_export_even_with_force(tmp_path):
    recs = [SftRecord(prompt="q", response="a", is_eval=False)]
    inelig = Eligibility(license_ok=False)  # everything else also False
    with pytest.raises(DatasetExportError):
        export_sft(recs, inelig, tmp_path / "sft.jsonl", force=True)
    assert not (tmp_path / "sft.jsonl").exists()


def test_eligible_export_excludes_eval_by_default(tmp_path):
    recs = [SftRecord(prompt="q", response="a", is_eval=True)]
    n = export_sft(recs, _eligible(), tmp_path / "sft.jsonl")
    assert n == 0  # eval cases excluded to avoid benchmark contamination


def test_eligible_export_with_force_includes_and_redacts(tmp_path):
    recs = [SftRecord(prompt="email john@example.com", response="ok", is_eval=True)]
    n = export_sft(recs, _eligible(), tmp_path / "sft.jsonl", force=True)
    assert n == 1
    text = (tmp_path / "sft.jsonl").read_text()
    assert "john@example.com" not in text and "REDACTED_EMAIL" in text


def test_dpo_export_drops_equal_pairs(tmp_path):
    recs = [
        DpoRecord(prompt="q", chosen="A", rejected="A", is_eval=False),  # equal -> dropped
        DpoRecord(prompt="q", chosen="A", rejected="B", is_eval=False),
    ]
    n = export_dpo(recs, _eligible(), tmp_path / "dpo.jsonl")
    assert n == 1


def test_check_redaction_true_after_redact():
    recs = [SftRecord(prompt="ip 8.8.8.8", response="mail a@b.com")]
    assert check_redaction(recs) is True


# --------------------------------------------------------------------------- #
# History + retention                                                          #
# --------------------------------------------------------------------------- #
def test_history_snapshots_and_immutability(tmp_path):
    hist = HistoryStore(tmp_path)
    hist.write_snapshot("example.com", "2026-07-01", {"coverage": 0.5, "fields": {"mx": 1}})
    hist.write_snapshot("example.com", "2026-07-02", {"coverage": 0.7, "fields": {"mx": 1, "ip": 2}})
    tl = hist.timeline("example.com")
    assert [s["date"] for s in tl] == ["2026-07-01", "2026-07-02"]
    assert hist.targets() == ["example.com"]
    with pytest.raises(FileExistsError):  # snapshots are immutable
        hist.write_snapshot("example.com", "2026-07-01", {"coverage": 0.9})


def test_retention_delete_and_rebuild_index(tmp_path):
    store = ArenaStore(tmp_path)
    runner = ArenaRunner(store)
    m1, *_ = runner.run_suite("smoke", Profile(id="mock", provider="mock", model="mock"))
    m2, *_ = runner.run_suite("smoke", Profile(id="mock", provider="mock", model="mock"))
    assert set(store.list_runs()) == {m1.run_id, m2.run_id}

    assert delete_run(store, m1.run_id) is True
    assert m1.run_id not in store.list_runs()
    # index no longer references the deleted (PII-bearing) run
    indexed = {s.run_id for s in store.iter_index()}
    assert m1.run_id not in indexed and m2.run_id in indexed

    assert rebuild_index(store) == 1
    assert purge_all(store) == 1
    assert store.list_runs() == []
