"""Run identity and manifest capture."""

from arena.manifest import build_manifest, git_state, host_metadata, new_run_id
from arena.schema import Profile


def test_run_id_unique_and_time_prefixed():
    import time

    ids = [new_run_id() for _ in range(200)]
    assert len(set(ids)) == len(ids)  # unique
    assert all(len(i) == 26 for i in ids)
    # The 10-char millisecond prefix makes ids sort chronologically across a gap.
    early = new_run_id()
    time.sleep(0.005)
    later = new_run_id()
    assert early[:10] <= later[:10]


def test_git_state_returns_tuple():
    sha, dirty = git_state(".")
    assert isinstance(sha, str) and isinstance(dirty, bool)


def test_host_metadata_has_no_user_or_home():
    meta = host_metadata()
    blob = str(meta).lower()
    assert "os" in meta and "python" in meta
    assert "/home/" not in blob and "username" not in meta


def test_build_manifest_populates_contract():
    profile = Profile(id="mock", provider="mock", model="mock")
    m = build_manifest(
        profile=profile,
        suite_id="smoke",
        scenario_set=[{"id": "a"}],
        effective_config={"model": "mock", "API_KEY": "secret"},
        seed=7,
    )
    assert m.run_id and m.created_at and m.suite_id == "smoke"
    assert m.seed == 7
    assert m.config_hash.startswith("sha256:")
    assert m.scenario_set_hash.startswith("sha256:")
    # secret must not leak into the manifest anywhere
    assert "secret" not in m.model_dump_json()
