"""Production instrumentation emits arena events without changing behaviour.

All offline: no network, no live LLM. Verifies the narrow seams added in
Milestone B (cache, tool registry, Ollama client, adaptive integration) and that
capture is inert when no sink is installed.
"""

import tempfile

from arena.collectors import collect_usage
from arena.events import EventCollector
from core import telemetry


# --------------------------------------------------------------------------- #
# Cache                                                                        #
# --------------------------------------------------------------------------- #
def test_cache_emits_lookup_events():
    from core.cache import CacheManager

    with tempfile.TemporaryDirectory() as d, EventCollector("s") as coll:
        c = CacheManager(cache_dir=d, ttl_hours=1)
        assert c.get("k") is None          # miss
        c.set("k", {"v": 1})
        assert c.get("k") == {"v": 1}      # hit (memory)
    outcomes = [(e.attributes.get("outcome"), e.attributes.get("tier")) for e in coll.by_name("cache.lookup")]
    assert ("miss", "disk") in outcomes
    assert ("hit", "memory") in outcomes
    # PII-safe: only a key digest, never the raw key
    assert all("k" != e.attributes.get("arena.key_digest") for e in coll.by_name("cache.lookup"))


def test_cache_is_inert_without_sink():
    from core.cache import CacheManager

    assert telemetry.active() is False
    with tempfile.TemporaryDirectory() as d:
        c = CacheManager(cache_dir=d, ttl_hours=1)
        c.set("k", {"v": 1})
        assert c.get("k") == {"v": 1}      # behaviour unchanged, no sink


# --------------------------------------------------------------------------- #
# Tool registry                                                                #
# --------------------------------------------------------------------------- #
def test_tool_registry_emits_start_and_complete(monkeypatch):
    import tools.tool_registry as tr

    monkeypatch.setattr(tr, "search_with_fallback", lambda *a, **k: [])
    monkeypatch.setattr(tr, "format_search_results", lambda results: "RESULTS")

    registry = tr.ToolRegistry(rag_enabled=False, config={})
    with EventCollector("s") as coll:
        out = registry._web_search_wrapper("berlin weather")
    assert out == "RESULTS"  # answer unchanged
    assert coll.has("tool.started")
    assert coll.has("tool.completed")
    started = coll.by_name("tool.started")[0]
    assert started.attributes["gen_ai.tool.name"] == "web_search"
    # raw query never emitted, only a digest
    assert "berlin weather" not in str(started.attributes)


# --------------------------------------------------------------------------- #
# Ollama client — provider-reported token usage                               #
# --------------------------------------------------------------------------- #
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _make_ollama_client():
    from core.llm_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    # Only the attributes generate() touches on the non-stream path.
    client.model = "qwen2.5:3b"
    client.base_url = "http://127.0.0.1:11434"
    client.timeout = 5
    client.hallu_enabled = False
    client._wait_for_rate_limit = lambda: None
    client._preflight_token_check = lambda prompt, system_prompt: prompt
    client._ensure_connection = lambda: None
    client._build_options = lambda **kw: {}
    return client


def test_ollama_captures_provider_usage(monkeypatch):
    client = _make_ollama_client()
    payload = {
        "response": "hello world",
        "model": "qwen2.5:3b",
        "prompt_eval_count": 11,
        "eval_count": 7,
        "done_reason": "stop",
    }

    class _Session:
        def post(self, *a, **k):
            return _FakeResp(payload)

    client.session = _Session()

    with EventCollector("s") as coll:
        text = client.generate("hi")

    assert text == "hello world"  # answer unchanged
    usage = collect_usage(coll.events)
    assert usage.llm_calls == 1
    assert usage.tokens_in == 11 and usage.tokens_out == 7
    assert usage.token_source == "provider"


def test_ollama_answer_identical_with_and_without_capture(monkeypatch):
    payload = {"response": "deterministic answer", "model": "m", "prompt_eval_count": 3, "eval_count": 4}

    def fresh_client():
        c = _make_ollama_client()

        class _Session:
            def post(self, *a, **k):
                return _FakeResp(payload)

        c.session = _Session()
        return c

    without = fresh_client().generate("q")
    with EventCollector("s"):
        with_capture = fresh_client().generate("q")
    assert without == with_capture == "deterministic answer"


# --------------------------------------------------------------------------- #
# Adaptive integration                                                         #
# --------------------------------------------------------------------------- #
class _FakeAgent:
    """Minimal agent: returns a fixed low confidence so escalation triggers."""

    def __init__(self, confidence):
        self._c = confidence

    def query(self, query):
        return {"answer": f"answer for {query}", "confidence": self._c}


def _make_processor():
    from core.adaptive_hops import AdaptiveConfig, AdaptiveHopManager
    from core.adaptive_integration import AdaptiveQueryProcessor

    manager = AdaptiveHopManager(
        llm=object(),  # never called: we force complexity
        config=AdaptiveConfig(enable_resource_monitoring=False),
        system_monitor=None,
    )
    return AdaptiveQueryProcessor(
        agent=_FakeAgent(confidence=0.3),
        multihop_agent=_FakeAgent(confidence=0.3),
        adaptive_manager=manager,
        max_escalation_attempts=2,
    )


def test_adaptive_emits_decision_and_escalation_events():
    processor = _make_processor()
    with EventCollector("s") as coll:
        resp = processor.process_query("complex query", force_complexity="low", enable_escalation=True)
    assert resp["answer"]  # answer produced
    assert coll.has("adaptive.decision")
    assert coll.has("adaptive.escalated")


def test_adaptive_answer_identical_with_and_without_capture():
    without = _make_processor().process_query("q", force_complexity="low", enable_escalation=True)
    with EventCollector("s"):
        with_capture = _make_processor().process_query("q", force_complexity="low", enable_escalation=True)
    assert without["answer"] == with_capture["answer"]
    assert without["strategy"]["agent_type"] == with_capture["strategy"]["agent_type"]


# --------------------------------------------------------------------------- #
# Cloud client — mocked; same event schema as Ollama                          #
# --------------------------------------------------------------------------- #
class _FakeChoice:
    finish_reason = "stop"

    class message:  # noqa: N801 - mimics the SDK attribute path
        content = "cloud answer"


class _FakeUsage:
    prompt_tokens = 12
    completion_tokens = 8


class _FakeCloudResp:
    model = "gpt-4o-mini-2026"
    usage = _FakeUsage()
    choices = [_FakeChoice()]


def _make_openai_client():
    from core.cloud_llm_client import OpenAIClient

    c = OpenAIClient.__new__(OpenAIClient)
    c.model = "gpt-4o-mini"
    c.temperature = 0.0
    c.max_tokens = 256
    c.context_window = 128000

    class _Completions:
        def create(self, *a, **k):
            return _FakeCloudResp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    c.client = _Client()
    return c


def test_cloud_client_captures_usage_and_matches_ollama_schema():
    # Ollama-side event
    client = _make_ollama_client()
    client.session = type("S", (), {"post": lambda self, *a, **k: _FakeResp(
        {"response": "x", "model": "m", "prompt_eval_count": 1, "eval_count": 1, "done_reason": "stop"}
    )})()
    with EventCollector("s") as ocoll:
        client.generate("hi")

    # Cloud-side event
    with EventCollector("s") as ccoll:
        out = _make_openai_client().chat([{"role": "user", "content": "hi"}])
    assert out == "cloud answer"  # answer unchanged

    ollama_evt = ocoll.by_name("llm.completed")[0]
    cloud_evt = ccoll.by_name("llm.completed")[0]
    assert set(ollama_evt.attributes) == set(cloud_evt.attributes)
    assert cloud_evt.attributes["gen_ai.provider.name"] == "openai"
    assert cloud_evt.attributes["gen_ai.usage.input_tokens"] == 12
    assert cloud_evt.attributes["arena.token_source"] == "provider"
