"""Evidence model + replay network guard (plan §20)."""

import socket

import pytest

from arena.evidence import (
    EvidenceSnapshot,
    NetworkAccessError,
    block_network,
    evidence_set_hash,
)
from arena.runner import ArenaRunner
from arena.schema import Profile, Scenario
from arena.store import ArenaStore


# --------------------------------------------------------------------------- #
# Network guard                                                                #
# --------------------------------------------------------------------------- #
def test_block_network_raises_on_connect():
    with block_network():
        with pytest.raises(NetworkAccessError):
            socket.create_connection(("example.com", 80), timeout=1)
        s = socket.socket()
        with pytest.raises(NetworkAccessError):
            s.connect(("1.1.1.1", 53))


def test_block_network_restores_socket():
    original = socket.socket.connect
    with block_network():
        pass
    assert socket.socket.connect is original


def test_block_network_allows_allowlisted_host():
    # Allowlisted host is not blocked by the guard (connection itself may still
    # fail, but not with NetworkAccessError).
    with block_network(allow_hosts={"127.0.0.1"}):
        s = socket.socket()
        s.settimeout(0.05)
        try:
            s.connect(("127.0.0.1", 9))  # discard port; likely refused
        except NetworkAccessError:
            raise AssertionError("allowlisted host must not be blocked")
        except OSError:
            pass  # connection refused/timeout is fine
        finally:
            s.close()


def test_runner_blocks_network_for_pure_scenario(tmp_path, monkeypatch):
    """A pure-mode driver that touches the network fails as a scenario."""
    import arena.drivers as drivers
    from arena.drivers.base import Driver, DriverResult

    class _NetDriver(Driver):
        name = "mock"  # reuse a registered name via monkeypatch below

        def run(self, scenario_input, context):
            socket.create_connection(("example.com", 80), timeout=1)
            return DriverResult(success=True)

    monkeypatch.setitem(drivers._REGISTRY, "mock", _NetDriver())

    runner = ArenaRunner(ArenaStore(tmp_path))
    scenario = Scenario(id="net.test", driver="mock", fixture_mode="pure")
    result = runner._run_one("run", scenario, seed=0, root=tmp_path, repeat=0)
    assert result.metrics.success is False
    assert "NetworkAccessError" in (result.metrics.error or "")


# --------------------------------------------------------------------------- #
# Evidence model                                                               #
# --------------------------------------------------------------------------- #
def test_evidence_match_key_ignores_response_fields():
    a = EvidenceSnapshot(request_method="get", canonical_url="https://x/y", content_digest="d1")
    b = EvidenceSnapshot(request_method="GET", canonical_url="https://x/y", content_digest="d2")
    # method case-normalised, response digest irrelevant to matching
    assert a.match_key() == b.match_key()


def test_evidence_set_hash_order_independent():
    s1 = EvidenceSnapshot(canonical_url="a", content_digest="da")
    s2 = EvidenceSnapshot(canonical_url="b", content_digest="db")
    assert evidence_set_hash([s1, s2]) == evidence_set_hash([s2, s1])
    assert evidence_set_hash([]) == ""


def test_evidence_snapshot_forbids_unknown_fields():
    with pytest.raises(Exception):
        EvidenceSnapshot.model_validate({"canonical_url": "x", "bogus": 1})


def test_evidence_hash_flows_into_manifest_dimension():
    from arena.compare import comparison_dimensions
    from arena.manifest import build_manifest

    ev = evidence_set_hash([EvidenceSnapshot(canonical_url="a", content_digest="da")])
    m = build_manifest(
        profile=Profile(id="mock"), suite_id="smoke", scenario_set=[{"id": "a"}], evidence_hash=ev
    )
    assert comparison_dimensions(m)["evidence"] == ev
