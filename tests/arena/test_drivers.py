"""Each Milestone A driver runs deterministically without network or an LLM."""

from arena.drivers import DriverContext, get_driver, known_drivers


def _ctx(tmp_path):
    return DriverContext(workdir=tmp_path, seed=0)


def test_registry_has_milestone_a_drivers():
    assert set(known_drivers()) == {"mock", "tool", "memory", "adaptive"}


def test_mock_driver(tmp_path):
    d = get_driver("mock")
    r = d.run({"answer": "hello", "confidence": 0.9, "metrics": {"q": 1.0}}, _ctx(tmp_path))
    assert r.success is True
    assert r.raw_output == "hello"
    assert r.extra_metrics["q"] == 1.0
    assert r.final_confidence == 0.9


def test_mock_driver_can_fail(tmp_path):
    r = get_driver("mock").run({"fail": True, "error": "nope"}, _ctx(tmp_path))
    assert r.success is False and r.error == "nope"


def test_tool_operator_parsing(tmp_path):
    r = get_driver("tool").run(
        {
            "op": "parse_operators",
            "query": "leak site:example.com inurl:admin filetype:pdf",
            "expected_operators": ["site", "inurl", "filetype"],
        },
        _ctx(tmp_path),
    )
    assert r.success is True
    assert r.coverage == 1.0
    found = r.structured_output["operators_found"]
    assert found["site"] and found["inurl"] and found["filetype"]


def test_tool_cache_hit(tmp_path):
    r = get_driver("tool").run({"op": "cache", "key": "k", "payload": {"v": 1}}, _ctx(tmp_path))
    assert r.success is True
    assert r.cache_hit is True


def test_memory_roundtrip(tmp_path):
    r = get_driver("memory").run({"email": "a@example.com"}, _ctx(tmp_path))
    assert r.success is True
    assert r.structured_output["added"] is True
    assert r.structured_output["recalled"] is True
    assert r.structured_output["empty_after_clear"] is True
    # isolated in the workdir, never the real data/memory.json
    assert (tmp_path / "memory.json").exists()


def test_adaptive_low_confidence_escalates_to_high(tmp_path):
    r = get_driver("adaptive").run(
        {"query": "complex", "force_complexity": "low", "confidence": 0.3},
        _ctx(tmp_path),
    )
    assert r.success is True
    assert r.escalated is True
    assert r.final_complexity == "high"
    assert r.escalation_attempts == 2
    assert r.structured_output["hop_path"] == ["low", "mid", "high"]


def test_adaptive_high_confidence_does_not_escalate(tmp_path):
    r = get_driver("adaptive").run(
        {"query": "q", "force_complexity": "low", "confidence": 0.95},
        _ctx(tmp_path),
    )
    assert r.escalated is False
    assert r.final_complexity == "low"
