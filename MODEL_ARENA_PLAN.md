# CrawlLama Model Arena & Regression Testing Harness — Design Plan

> **Status:** Implementation-ready design revision (codebase audited 2026-07-23)
> **Target version:** 1.5.x
> **Owner:** CrawlLama Team
> **Scope:** A reproducible testing, benchmarking, and "arena" subsystem that lets us
> (a) compare tool behaviour **before vs. after code changes**, (b) compare **different LLM
> models / providers / configs** head-to-head, (c) build **longitudinal / historical** records
> for the *same* target (e.g. one web domain analysed repeatedly over time), and (d) export
> high-quality traces as **fine-tuning data**. It must exercise **every major tool function**,
> including adaptive-hop **escalation**.

> **Revision note:** §17–§25 contain the codebase-audited implementation decisions and
> supersede conflicting details in the earlier proposal (especially the single generic
> runner, mixed JSONL storage, drift attribution, REST timing, and automatic fine-tuning
> export assumptions).

---

## 1. Motivation & Goals

CrawlLama is an AI research / OSINT agent whose output quality depends on three moving
parts that all change independently:

1. **The code** — crawler, OSINT modules, RAG, adaptive-hop routing, prompts.
2. **The model** — local (Ollama) or cloud (OpenAI / Anthropic / Groq), plus temperature,
   context window, and sampling parameters.
3. **The target world** — the live web, which drifts over time.

Today there is no systematic way to answer questions like *"did my refactor of
`core/agent/agent.py` make domain analysis better or worse?"* or *"is `qwen3:8b` actually
better than `llama3.1:8b` for multi-hop OSINT?"* The health dashboard
(`core/health/`) measures **liveness and latency**, and `pytest` measures **correctness of
deterministic units**, but neither measures **research quality** or supports **A/B comparison**.

### Goals

- **G1 — Before/after regression detection.** Given two code states (git SHAs / working tree),
  run the same fixed suite and produce a diff report highlighting quality/latency
  regressions and improvements per capability.
- **G2 — Model & config arena.** Run the same suite across N `(provider, model, params)`
  profiles and rank them per metric (tournament / leaderboard).
- **G3 — Full functional coverage.** Every major capability is represented by at least one
  scenario: web search, multi-hop reasoning, RAG, caching, all OSINT modules
  (email / phone / IP / social / domain / company / breach), memory store, compliance,
  hallucination detection, plugins, and **adaptive-hop escalation**.
- **G4 — Longitudinal / historical tracking.** Re-run a scenario (e.g. analyse one domain)
  on a schedule; store immutable snapshots; detect **drift** in tool output and model
  behaviour over time; maximise information extracted per run.
- **G5 — Fine-tuning data export.** Turn high-scoring runs into SFT / preference (DPO) datasets
  keyed to a model version, closing the loop between "evaluate" and "improve the model".
- **G6 — Reproducibility.** Every run is fully described by an immutable **manifest**
  (git SHA, config hash, model, seed, fixture version, timestamp) so results are comparable.

### Non-goals

- Not a replacement for `pytest` unit tests (deterministic correctness) or the health
  dashboard (system liveness). The arena **reuses** both.
- Not a live-web scraper for production use — arena runs are measurement runs and must be
  reproducible; live-web scenarios are explicitly flagged as *non-deterministic* (see §7).

---

## 2. Where this fits in the existing codebase

The harness reuses existing infrastructure rather than reinventing it:

| Need | Existing component to reuse |
|---|---|
| Run the agent programmatically | `core/agent/agent.py`, `core/langgraph_agent.py`, `main.py` entrypoint |
| Adaptive routing + **escalation** trace | `core/adaptive_hops.py` (`AdaptiveHopManager.should_escalate`, confidence thresholds), `core/adaptive_integration.py` (`max_escalation_attempts`) |
| Model abstraction (swap models) | `core/llm_client.py` (Ollama), `core/cloud_llm_client.py` (OpenAI/Anthropic/Groq), `core/model_registry.py` |
| Latency / throughput metrics | `core/health/performance_tracker.py` (`PerformanceStats`: p50/p95/p99, success rate, throughput) |
| Quality signal (hallucinations) | `core/hallu_detect.py` (`get_detector`, `HallucinationResult`) |
| Token / context accounting | `core/context_manager.py`, `tiktoken`, `model_registry.get_model_context_window` |
| OSINT capabilities under test | `core/osint/*` (email/phone/ip/domain/company/compliance), `core/memory/breach.py` |
| Report rendering | `core/report_exporter.py` (markdown/pdf builders) |
| Test execution plumbing | `core/health/test_runner.py` (parallel pytest runner — pattern to mirror) |
| Config surface | `config/config.json.example`, `.env.example`, interactive settings menu |
| Storage location | `data/history/`, `data/exports/` already exist and are owner-only (0o700) |

New code lives under a single new package: **`arena/`** (mirrors the `core/` style), plus a
**`arena/scenarios/`** fixture tree and a **`data/arena/`** results store.

---

## 3. High-level architecture

```
                        ┌──────────────────────────────────────────────┐
                        │                arena CLI / API                │
                        │  run · compare · tournament · history · report│
                        └───────────────┬──────────────────────────────┘
                                        │
                 ┌──────────────────────┼───────────────────────┐
                 ▼                      ▼                        ▼
        ┌────────────────┐    ┌──────────────────┐     ┌──────────────────┐
        │  ScenarioSet   │    │   ProfileMatrix  │     │   RunManifest    │
        │ (fixtures +    │    │ (model×config×   │     │ git SHA, cfg hash│
        │  expectations) │    │  code-state)     │     │ seed, ts, versions│
        └───────┬────────┘    └────────┬─────────┘     └────────┬─────────┘
                └──────────────┬───────┴────────────────────────┘
                               ▼
                     ┌───────────────────┐   drives    ┌─────────────────────────┐
                     │   ArenaRunner     │────────────▶│  CrawlLama Agent (SUT)  │
                     │ (per scenario ×   │             │ core/agent, langgraph,  │
                     │  per profile)     │◀────────────│ osint/*, adaptive_hops  │
                     └─────────┬─────────┘   captures  └─────────────────────────┘
                               ▼
                     ┌───────────────────┐
                     │  MetricCollectors │  correctness · latency · hallucination ·
                     │                   │  confidence · escalation · tokens · cost ·
                     │                   │  coverage · reproducibility
                     └─────────┬─────────┘
                               ▼
                     ┌───────────────────┐        ┌────────────────────────┐
                     │  Scorer / Judge   │───────▶│  data/arena/runs/*.jsonl│
                     │ (rules + LLM-as-  │        │  (immutable, indexed)   │
                     │  judge)           │        └───────────┬─────────────┘
                     └───────────────────┘                    ▼
                                                   ┌────────────────────────┐
                                                   │ Comparators & Reports  │
                                                   │ before/after · A/B ·   │
                                                   │ tournament · drift     │
                                                   └────────────────────────┘
```

### Package layout

```
arena/
  __init__.py
  models.py            # dataclasses: Scenario, Expectation, Profile, RunManifest,
                       #   RunResult, MetricBundle, ScenarioScore
  runner.py            # ArenaRunner: executes scenario × profile, isolates state
  profiles.py          # ProfileMatrix loader; resolves (provider, model, params, code-state)
  collectors/
    __init__.py
    latency.py         # wraps core/health/performance_tracker
    tokens.py          # wraps core/context_manager + tiktoken
    hallucination.py   # wraps core/hallu_detect
    escalation.py      # captures adaptive_hops decisions + hop trace
    coverage.py        # counts extracted OSINT fields vs. expected schema
  scoring/
    __init__.py
    rules.py           # deterministic scoring (regex/field presence/set overlap/F1)
    judge.py           # LLM-as-judge scoring (uses cloud_llm_client; pinned judge model)
    aggregate.py       # weighted composite score per scenario / per profile
  store.py             # append-only JSONL writer/reader for data/arena/runs/
  compare.py           # before/after diff, A/B, tournament ranking, drift analysis
  report.py            # markdown/HTML report builders (reuse report_exporter style)
  cli.py               # `python -m arena ...`
  scenarios/
    _schema.md         # scenario file format documentation
    search/*.yaml
    multihop/*.yaml
    osint/*.yaml
    escalation/*.yaml
    domain_history/*.yaml
    ...
```

---

## 4. Core data model

All dataclasses in `arena/models.py`, JSON-serialisable, versioned with a `schema_version`.

```python
@dataclass
class Scenario:
    id: str                      # stable, e.g. "osint.domain.example_com.v1"
    category: str                # search | multihop | osint | escalation | rag | memory | ...
    query: str                   # the input given to the agent
    target: str | None           # e.g. a domain, email, phone (for OSINT/history)
    expectation: Expectation     # how to score it (see below)
    tags: list[str]              # e.g. ["deterministic"], ["live-web"], ["escalation-expected"]
    timeout_s: int = 120
    repeats: int = 1             # run N times to measure variance/non-determinism

@dataclass
class Expectation:
    mode: str                    # "rules" | "judge" | "hybrid"
    must_include: list[str]      # substrings/entities that MUST appear
    must_not_include: list[str]  # e.g. hallucinated markers, refusal text
    expected_fields: dict        # OSINT schema: {"mx_records": True, "geolocation": True, ...}
    reference_answer: str | None # gold answer for judge/F1 scoring
    min_confidence: float | None
    escalation_expected: bool | None  # should adaptive-hops escalate?

@dataclass
class Profile:
    id: str                      # "qwen3-8b@sha_abc123"
    provider: str                # ollama | openai | anthropic | groq
    model: str
    params: dict                 # temperature, max_tokens, context_window, seed, num_ctx
    code_state: str              # git SHA or "WORKTREE"
    config_overrides: dict       # any config.json overrides for this profile

@dataclass
class RunManifest:              # the reproducibility contract
    run_id: str
    created_at: str             # ISO timestamp (injected — no wallclock in pure logic)
    git_sha: str
    git_dirty: bool
    config_hash: str            # sha256 of the effective merged config
    profile: Profile
    scenario_set_version: str
    seed: int
    host: dict                  # os, python version, gpu (best-effort)

@dataclass
class RunResult:
    manifest_ref: str            # run_id
    scenario_id: str
    repeat_index: int
    raw_output: str              # the agent's answer
    metrics: MetricBundle
    score: ScenarioScore
    trace: dict                  # tool calls, hop path, escalation decisions, timings

@dataclass
class MetricBundle:
    latency_ms: float
    p50_ms: float; p95_ms: float          # when repeats > 1
    tokens_in: int; tokens_out: int
    context_utilisation: float            # tokens / model context window
    hallucination_score: float            # from core/hallu_detect
    final_confidence: float | None
    escalation: EscalationTrace
    coverage: float                       # extracted_fields / expected_fields
    tool_calls: int
    cost_usd: float | None                # cloud providers only
    success: bool
    error: str | None

@dataclass
class EscalationTrace:
    initial_complexity: str      # low | mid | high
    final_complexity: str
    escalated: bool
    attempts: int
    reasons: list[str]           # from AdaptiveHopManager.should_escalate reasons
    hop_path: list[str]          # Router → Search → Analyze → Follow-Up → Synthesize → Critique
```

---

## 5. Metrics — what we measure

Each metric maps to an existing signal source so we don't re-implement measurement:

| Metric | Source / method | Higher-is-better |
|---|---|---|
| **Correctness** | rules (`must_include`/`must_not_include`, `expected_fields` presence) + F1 vs `reference_answer` | ✅ |
| **Quality** | LLM-as-judge score (0–10) on relevance, completeness, faithfulness | ✅ |
| **Hallucination** | `core/hallu_detect.get_detector()` → `HallucinationResult` | ❌ (lower) |
| **Coverage** | `arena/collectors/coverage.py`: extracted OSINT fields ÷ expected fields | ✅ |
| **Latency** | `core/health/performance_tracker` p50/p95/p99 | ❌ (lower) |
| **Tokens / context util** | `core/context_manager` + `tiktoken` + `model_registry` window | context-dependent |
| **Escalation correctness** | `EscalationTrace.escalated == expectation.escalation_expected` | ✅ (match) |
| **Confidence calibration** | `final_confidence` vs. actual correctness (Brier-style) | ✅ |
| **Cost** | provider pricing × tokens (cloud) | ❌ (lower) |
| **Stability** | variance across `repeats` (non-determinism penalty) | ❌ (lower) |
| **Robustness** | did it error / time out / fall back (`core/fallback_manager`) | ✅ (no error) |

**Composite score** (`scoring/aggregate.py`): a weighted, normalised sum with configurable
weights per use-case profile (e.g. an "OSINT-accuracy" weighting vs. a "latency-sensitive"
weighting). Weights live in `arena/scenarios/_weights.yaml` so scoring policy is versioned.

**Scoring modes:**
- **`rules`** — fully deterministic, CI-safe, no model calls. Preferred for regression gates.
- **`judge`** — LLM-as-judge using a **pinned** judge model (default a strong cloud model via
  `core/cloud_llm_client`) so the *judge* is constant while the *system-under-test* varies.
  Judge prompt is versioned; judge is never the same model being evaluated.
- **`hybrid`** — rules gate first (hard fails), judge scores the remainder.

---

## 6. Functional coverage matrix (G3)

Every major capability gets ≥1 scenario. Initial suite:

| Category | Scenario examples | Key metric |
|---|---|---|
| **Web search** | multi-source query, fallback provider path (DDG→Brave→Serper) | correctness, latency |
| **Multi-hop reasoning** | complex query forcing Router→…→Critique | quality, hop_path |
| **RAG** | question answerable only from retrieved chunks | faithfulness, coverage |
| **Caching** | repeat identical query → expect cache hit + speedup | latency delta, correctness parity |
| **OSINT email** | validate + MX + disposable + variations | coverage, correctness |
| **OSINT phone** | validate + carrier + country | coverage |
| **OSINT IP** | geo + ISP + reputation + VPN detection | coverage |
| **OSINT social** | username across 12 platforms | coverage |
| **OSINT domain** | full domain profile (the headline history target) | coverage, drift |
| **OSINT company** | company-intel enrichment | coverage, quality |
| **Breach** | known-fixture email → expected breach set | correctness (set overlap) |
| **Memory store** | remember → clear → recall persistence | correctness (deterministic) |
| **Compliance** | rate-limit / robots.txt respected | robustness (no violation) |
| **Adaptive escalation** | low-confidence query that *must* escalate low→high | escalation match |
| **Hallucination guard** | trap query with no real answer → expect refusal/low-confidence | hallucination score |
| **Plugins** | load plugin → invoke → unload | robustness |
| **Advanced operators** | `site:` `inurl:` `filetype:` parsing | correctness |

Deterministic scenarios (memory, operator parsing, cache mechanics, breach against local
fixtures in `tests/fixtures/breaches/`) form the **CI regression gate**; live-web scenarios
run in scheduled/manual mode only.

---

## 7. Determinism, isolation & fairness

Comparability is the whole point, so runs must be as controlled as possible:

- **Seeded models.** Pass `seed` + `temperature=0` where supported (Ollama `num_ctx`/seed,
  OpenAI seed) for deterministic scenarios; store the seed in the manifest.
- **Response fixtures / VCR.** For deterministic web scenarios, record live HTTP once and
  replay from a cassette (`arena/scenarios/**/cassettes/`) so the *web* is frozen and only
  *code+model* vary. Live-web scenarios are tagged `live-web` and excluded from regression gates.
- **State isolation.** Each run gets a fresh cache dir, memory store, and session
  (temp dirs, mirroring `core/health/test_runner`'s tempdir pattern). No cross-run leakage.
- **Config hashing.** The effective merged config (defaults + profile overrides + env) is
  hashed into `config_hash`; two runs with different hashes are flagged as not directly
  comparable.
- **Code-state control.** `code_state` is a git SHA. For before/after, the runner can drive
  runs against two SHAs by launching the agent in a **git worktree per SHA** (isolated
  checkout) so we don't mutate the working tree. Working-tree runs are marked `git_dirty=true`.
- **Fairness rules for model arena.** Same scenario set, same cassettes, same weights, same
  judge — only the `(provider, model, params)` tuple changes across profiles.

---

## 8. Storage & indexing

- **Location:** `data/arena/` (owner-only `0o700`, like `data/exports/`).
  - `data/arena/runs/<run_id>.jsonl` — append-only: one manifest line + one line per RunResult.
  - `data/arena/index.jsonl` — one summary row per run (run_id, git_sha, model, mean score, ts).
  - `data/arena/history/<target>/<date>.json` — longitudinal snapshots (see §9).
  - `data/arena/datasets/` — exported fine-tuning data (see §10).
- **Immutability:** run files are never edited after write; re-runs create new run_ids.
- **Retention/PII:** OSINT outputs may contain PII → same owner-only perms and `.gitignore`
  entry as existing `data/` subdirs; add `data/arena/` to `.gitignore`.

---

## 9. Longitudinal / historical mode (G4)

The headline use-case: **"always analyse the same web domain and compare over time, extracting
as much information as possible."**

- A `domain_history` scenario has a stable `target` (e.g. `example.com`) and runs on a
  schedule (via existing `/loop` / cron tooling, or the health dashboard).
- Each run stores a **snapshot** under `data/arena/history/<target>/<YYYY-MM-DD>.json`
  containing: full extracted field set, coverage %, per-tool output, model+code manifest.
- **Drift analysis** (`compare.py::drift`) compares consecutive snapshots and separates:
  - **World drift** — the target actually changed (new subdomain, cert, tech) → *signal*.
  - **Behaviour drift** — same world, different extraction because code/model changed → *regression risk*.
  It disentangles the two by holding the manifest constant across the compared snapshots
  (same model+SHA → any diff is world drift; different model+SHA → attribute to the change).
- **Info-maximisation loop.** For history targets the runner can run in a "greedy coverage"
  mode: re-invoke with escalation forced up and all OSINT modules enabled, then report which
  expected fields are still missing (`coverage` gaps) so the suite/code can be improved to
  extract more next time.
- Output: a per-target **timeline report** (markdown + optional Artifact HTML) showing
  coverage and quality trend lines across dates and across model/code versions.

---

## 10. Fine-tuning loop (G5)

The arena is also the data factory for improving the local model:

- **SFT export:** runs scoring above a threshold export `(query, tools_context, gold_answer)`
  tuples in JSONL to `data/arena/datasets/sft/`.
- **Preference (DPO) export:** when the same scenario is run across multiple profiles, the
  higher-scored vs. lower-scored outputs form `(prompt, chosen, rejected)` pairs →
  `data/arena/datasets/dpo/`.
- **Model versioning:** new fine-tunes are registered in `core/model_registry.py`
  (`MODEL_CONTEXT_WINDOWS`) and immediately become a `Profile` — so "did the fine-tune help?"
  is answered by the exact same before/after machinery (§11).
- Redaction pass reuses `core/memory/sanitization.py` so exported training data is PII-scrubbed.

This closes the loop: **evaluate → export → fine-tune → register → re-evaluate.**

---

## 11. Comparison & reporting (G1, G2)

`arena/compare.py` + `arena/report.py` produce:

1. **Before/After (regression) report** — two runs (SHA-A vs SHA-B, same profile+suite):
   per-scenario score delta, latency delta, coverage delta; sections for
   **Regressions / Improvements / Unchanged**; overall verdict + a machine-readable
   `regression: bool` for CI gating.
2. **A/B model report** — same suite+SHA, two models: side-by-side per-metric table + winner.
3. **Tournament / leaderboard** — N profiles ranked by composite score, with per-category
   breakdown (a model can win OSINT but lose latency); Elo-style pairwise ranking optional.
4. **Drift timeline** — §9 longitudinal view.

Rendering reuses the `core/report_exporter.py` markdown builders; an optional HTML dashboard
can be a self-contained **Artifact** for sharing, and the results can also surface as a new
tab/widget in the existing health dashboard (`core/health/`).

---

## 12. Interfaces

### CLI (`python -m arena ...`)
```
arena run       --profile qwen3-8b --suite all            # run suite, store results
arena run       --profile-matrix profiles.yaml            # model arena (many profiles)
arena compare   --before <run_id|SHA> --after <run_id|SHA>  --gate   # regression gate
arena tournament --profiles a,b,c --suite osint           # leaderboard
arena history   --target example.com                      # longitudinal timeline
arena export    --dataset dpo --min-score 8               # fine-tuning data
arena report    --run <run_id> --format md|html
```
`--gate` exits non-zero on regression (for CI).

### REST API (extends `app.py`)
New router (admin-gated, same `verify_api_key` / rate-limit / CSRF pattern as existing
`/admin/*` and `/query-adaptive` endpoints):
```
POST /arena/run          POST /arena/compare       GET /arena/leaderboard
GET  /arena/runs         GET  /arena/history/{target}
```

### CI integration (`.github/`)
A workflow runs the **deterministic** suite on each PR against `base` vs `head` (two
worktrees) and fails on regression; posts the before/after markdown as a PR comment.

---

## 13. Implementation phases

**Phase 0 — Foundations (no behaviour change)**
- Create `arena/` package, `arena/models.py` dataclasses, `store.py` (JSONL + index),
  `RunManifest` capture (git SHA/dirty, config hash, host).
- Add `data/arena/` to `.gitignore`, owner-only perms.

**Phase 1 — Single-run runner + deterministic scoring**
- `runner.py` drives the agent programmatically for one scenario × one profile with isolated
  state; `collectors/latency.py`, `tokens.py`, `escalation.py`, `hallucination.py`, `coverage.py`.
- `scoring/rules.py` (deterministic). Seed the deterministic scenarios (memory, operators,
  cache, breach-vs-fixture). Wire `arena run` CLI.
- **Exit criterion:** `arena run --profile <default>` produces a stored, scored run.

**Phase 2 — Before/after comparison + CI gate (G1)**
- `compare.py` before/after diff; `report.py` markdown; worktree-per-SHA execution;
  `arena compare --gate`; GitHub Action on PRs.
- **Exit criterion:** a deliberate quality-lowering change is caught by the gate.

**Phase 3 — Model arena + LLM-as-judge (G2)**
- `profiles.py` ProfileMatrix; provider swap across Ollama/OpenAI/Anthropic/Groq;
  `scoring/judge.py` with a pinned judge; `arena tournament` + leaderboard report.
- **Exit criterion:** two models produce a comparable leaderboard on the same suite.

**Phase 4 — Full coverage suite (G3)**
- Author scenarios for **every** row in §6; add VCR cassettes for deterministic web scenarios;
  escalation scenarios asserting `EscalationTrace`.
- **Exit criterion:** coverage matrix 100% populated; deterministic subset green in CI.

**Phase 5 — Longitudinal / history (G4)**
- `history` snapshots, drift analysis, timeline report, greedy-coverage info-max mode,
  schedule hook (via `/loop`/cron), optional health-dashboard widget.
- **Exit criterion:** repeated same-domain runs show a coverage/quality trend and separate
  world-drift from behaviour-drift.

**Phase 6 — Fine-tuning export (G5)**
- SFT + DPO exporters with PII redaction; model-registry integration; re-eval loop.
- **Exit criterion:** a fine-tune exported from arena data can be registered as a Profile and
  A/B-tested against its base with the Phase 2/3 machinery.

---

## 14. Testing the tester

- Unit tests under `tests/arena/` for scoring rules, manifest hashing, store round-trips,
  drift math, and score aggregation (all deterministic, no model/network).
- A tiny **mock profile** (canned agent responses) so `arena run` itself is testable in CI
  without a live LLM.
- Golden reports checked in for `compare`/`tournament` output formatting.

---

## 15. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM output non-determinism swamps signal | seed + temp=0 for deterministic scenarios; `repeats` + variance metric; cassettes freeze the web |
| Judge model bias / drift | pin judge model+prompt version; judge ≠ system-under-test; keep a rules gate independent of the judge |
| Live-web flakiness in CI | only deterministic/cassette scenarios gate CI; live-web is scheduled/manual |
| PII in stored results / datasets | owner-only dirs, `.gitignore`, `sanitization.py` redaction on export |
| Cloud API cost during arena | cost metric + budget cap per run; default suite runs local Ollama; cloud profiles opt-in |
| Comparing incomparable runs | `config_hash` + manifest guard; comparator refuses/flags mismatched manifests |

---

## 16. Resolved design decisions

1. Ship three named score views (`accuracy`, `latency`, `osint_coverage`) but **never gate on
   one opaque composite alone**. Hard correctness/safety constraints and per-metric deltas
   remain visible.
2. A judge profile is explicit and versioned; no cloud judge is silently selected. Offline
   local judging is supported, but judge calibration results must be attached to the report.
3. Elo is deferred. V1 uses paired per-scenario deltas and win/tie/loss counts; these are
   easier to interpret and audit.
4. Scheduling is external (`cron`/systemd timer/GitHub Actions). The health dashboard may
   display results later, but does not own a scheduler.

---

## 17. Codebase audit: corrections and missing integration seams

The current code supports the arena, but not through a single `agent.query()` wrapper.
Different capabilities expose different return shapes and state:

| Current code | Audit finding | Required arena integration |
|---|---|---|
| `SearchAgent.query()` | Returns only `str`; cache/tool/LLM details are not returned | `AgentDriver` plus event capture |
| `MultiHopReasoningAgent.query()` | Already returns answer, confidence, steps, queries and `reasoning_path` | `MultiHopDriver`; keep structured result |
| `AdaptiveQueryProcessor.process_query()` | Already returns strategy, attempts and `escalation_history` | `AdaptiveDriver`; use returned metadata directly |
| `ToolRegistry` | Central construction point for four `StructuredTool`s | Instrument wrapper calls once here |
| `core/osint/*` | Direct modules return structured dictionaries and do not all pass through the agent | Dedicated `OsintDriver` adapters |
| `CacheManager` | Has isolated `cache_dir`, but no observable hit/miss counter | Emit cache events or add per-instance counters |
| cloud/Ollama LLM clients | Provider response usage is discarded when returning text | Capture provider usage before returning; estimate only as fallback |
| `PerformanceTracker` | Process-global rolling health stats, not run-scoped measurements | Do not use as the arena source of truth; use run-local monotonic timers |
| `HallucinationResult.confidence_score` | Higher means **higher hallucination risk** | Store as `hallucination_risk`, not ambiguous `hallucination_score` |
| `SanitizationMixin` | Only sanitises email/phone for logging; it is not a dataset redactor | Add an arena-specific recursive redaction policy |
| `core/report_exporter.py` | Only exports the latest conversation to Markdown/text | Reuse permission/atomic-write patterns, not its report data model |
| `pyproject.toml` | Pydantic is direct; YAML is only transitive | Use strict Pydantic models; either declare PyYAML directly or use JSON |

### Chosen execution model

Scenarios declare a `driver`, not just a query:

```yaml
schema_version: 1
id: adaptive.low_confidence_escalates.v1
driver: adaptive                  # agent | multihop | adaptive | tool | osint | memory | plugin
input:
  query: "..."
  force_complexity: low
  enable_escalation: true
fixture_mode: replay              # pure | replay | live
expect:
  escalation:
    happened: true
    final_complexity: high
  hard:
    success: true
  metrics:
    answer_quality:
      min: 0.75
tags: [deterministic, escalation]
```

This is the smallest design that can exercise every promised capability without parsing
human-formatted answers back into unreliable pseudo-structure.

---

## 18. Revised package and dependency boundaries

```text
arena/
  __init__.py
  __main__.py                 # python -m arena
  cli.py
  schema.py                   # strict Pydantic models, extra="forbid"
  config.py                   # safe merge + behaviour fingerprint
  manifest.py
  runner.py                   # orchestration only
  worker.py                   # one JSON request -> one JSON result
  events.py                   # ContextVar-backed optional event sink
  drivers/
    base.py
    agent.py
    multihop.py
    adaptive.py
    tool.py
    osint.py
    memory.py
    plugin.py
  collectors/
    latency.py
    usage.py
    hallucination.py
    coverage.py
  scoring/
    rules.py
    pointwise.py
    pairwise.py
    aggregate.py
    calibration.py
  evidence/
    model.py
    record.py
    replay.py
    normalize.py
  store.py
  compare.py
  statistics.py
  redact.py
  datasets.py
  report.py
  scenarios/
    schema-v1.json
    suites/
    cases/
tests/arena/
```

Rules:

- `core/` must never import `arena/`. Production code only calls the no-op-by-default event
  function in a small neutral module (`core/telemetry.py`), preventing a circular dependency.
- Arena drivers may import public production entry points. They must not duplicate business
  logic from `core/`.
- Each code state runs `python -m arena.worker` from **its own checkout and interpreter
  environment**. The coordinator communicates over JSON Lines on stdin/stdout. Two SHAs are
  never imported into one Python process.
- The worker protocol and stored schema are versioned. A coordinator refuses incompatible
  worker schema versions rather than silently comparing different meanings.
- Scenario YAML is acceptable only after `pyyaml` becomes a direct dependency. For the
  dependency-minimal MVP, checked-in scenarios use JSON; the examples in this document remain
  YAML for readability.

---

## 19. Trace and telemetry contract

An arena result needs events, not log scraping. Add a tiny optional sink backed by
`contextvars.ContextVar`; outside an arena run it is a no-op. Events have:

```text
event_id, run_id, scenario_id, parent_id, seq, name,
started_ns, duration_ns, status, attributes, error_type
```

Initial event names:

- `agent.started`, `agent.completed`
- `llm.started`, `llm.completed` (provider, requested model, response model, usage, finish reason)
- `tool.started`, `tool.completed` (tool name, redacted input digest, result digest)
- `cache.lookup` (`hit`, `miss`, `expired`, `memory`, `disk`)
- `adaptive.decision`, `adaptive.escalated`
- `rag.retrieval` (document IDs/scores, not document bodies by default)
- `osint.module.started`, `osint.module.completed`

Instrumentation points are deliberately narrow:

1. `core/cloud_llm_client.py` and `core/llm_client.py` retain provider token usage and response
   metadata before returning the existing string. The public return type stays compatible.
2. `tools/tool_registry.py` wraps the four registered tool calls.
3. `core/cache.py` emits lookup outcomes.
4. `core/adaptive_integration.py` emits decisions in addition to its already-structured
   escalation history.
5. Direct OSINT drivers time module calls themselves; production OSINT modules need no broad
   rewrite in the MVP.

Attribute names should align where practical with OpenTelemetry GenAI conventions
(`gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`). Raw prompts, tool arguments,
retrieved text and outputs are **not telemetry attributes by default**, because they may
contain PII.

---

## 20. Evidence-first replay and correct drift attribution

The earlier assertion that “same model+SHA means every difference is world drift” is too
strong: model nondeterminism, provider revisions, ranking changes and transient failures can
also change output.

Use two stages:

1. **Acquisition:** tools collect a normalised `EvidenceSnapshot` with source URL, retrieval
   time, HTTP status/content type, content digest, sanitised extracted text, tool/provider,
   errors and cassette version.
2. **Reasoning:** one or more code/model profiles operate on the exact same evidence snapshot.

This enables defensible comparisons:

| Comparison | What can be inferred |
|---|---|
| Same evidence, different SHA/model | Behaviour difference |
| Different evidence, same pinned profile with repeats | Likely world/acquisition drift, with uncertainty |
| Different evidence and different profile | Confounded; report separately, never attribute automatically |

Replay rules:

- CI uses `pure` or `replay`; an unexpected network call is a hard failure.
- Recording is a separate explicit command and never happens in PR CI.
- Cassettes/evidence remove authorization headers, cookies, API keys, query secrets and
  sensitive response fields before writing.
- Match requests on method, canonical URL, safe query parameters and a request-body digest.
- Store fixture licence/provenance and a `recorded_at` timestamp.
- Prefer local fakes for provider APIs and local DNS/HTTP fixtures over recording personal or
  mutable OSINT data.

---

## 21. Storage, identity and reproducibility contract

Replace the mixed “manifest line + result lines” file with one atomic run directory:

```text
data/arena/runs/<run_id>/
  manifest.json
  results.jsonl
  events.jsonl
  summary.json
  COMPLETE
data/arena/index.jsonl
```

- Write into `<run_id>.partial/`; fsync/close, rename atomically, then create `COMPLETE`.
- Ignore incomplete directories during normal reads; provide `arena doctor` to diagnose them.
- Use a file lock when appending `index.jsonl`, or rebuild the index from run summaries.
- `run_id` is UUIDv7/ULID-like sortable identity; comparison identity is a separate SHA-256
  fingerprint.
- `config_hash` covers only canonical, behaviour-relevant values. Secrets are replaced with
  a presence marker (for example `OPENAI_API_KEY=present`) and are never stored or hashed.
- Add hashes for scenario content, evidence snapshot, judge prompt/rubric, scoring policy,
  worker schema, Python lockfile and effective tool set.
- Store requested model and provider-returned model/version when available.
- Host metadata must not include usernames, home paths, environment dumps or raw GPU serials.
- Apply directory `0700` and file `0600`; add `data/arena/*` with an optional `.gitkeep` to
  `.gitignore`.

Comparability is field-specific. A model comparison requires equal code/evidence/scenarios/
scorer, while a code comparison requires equal model/evidence/scenarios/scorer. The
comparator reports the exact mismatches and supports `--allow-mismatch <field>`; it does not
use one all-or-nothing config hash.

---

## 22. Scoring, judge calibration and regression gates

### Metric hierarchy

1. **Hard gates:** execution success, schema validity, forbidden leakage, compliance, expected
   escalation/cache/tool behaviour.
2. **Deterministic task metrics:** exact/set match, precision/recall/F1, required fields,
   citation validity and source support.
3. **Model-based metrics:** rubric-specific relevance, completeness and faithfulness.
4. **Operational metrics:** latency, provider-reported tokens, cost, tool calls, retries and
   cache behaviour.

Do not hide a hard failure inside a weighted mean. Composite views are for ranking after hard
gates pass.

### LLM-as-judge

- Standalone runs may use pointwise rubric grading with structured JSON output.
- Before/after and arena comparisons prefer **pairwise** grading.
- Randomise candidate order, hide profile/model names, run both A/B and B/A ordering, and
  report positional disagreement.
- Allow `tie`; keep judge rationale and raw structured decision.
- Calibrate each judge+prompt version against a small human-labelled set. Store agreement,
  per-category confusion and sample count. An uncalibrated judge cannot be a CI gate.
- Never use a judge to verify facts it was not given. Faithfulness judges receive the exact
  evidence snapshot and citations.

### Statistical gate

The unit of comparison is the paired scenario, not the global mean:

- Report per-scenario deltas and win/tie/loss.
- For stochastic scenarios use at least three repeats in scheduled runs and show median,
  dispersion and a paired bootstrap confidence interval.
- A PR fails on any hard-gate regression, or when a configured practical threshold is crossed
  and the paired confidence interval excludes zero.
- Latency gates run only on controlled runners, include warm-up, and compare medians; normal
  shared GitHub runners produce informational latency only.
- Missing/error results are failures, never dropped from the denominator.
- Version thresholds beside the scenario suite; changes to thresholds require review and are
  shown in the comparison report.

---

## 23. Security, privacy and fine-tuning eligibility

Arena inputs are untrusted and outputs may be sensitive:

- Default checked-in cases use synthetic identities, reserved domains/IP ranges, local fixtures
  and consented project-owned targets.
- `live` mode requires an explicit target allowlist, request/time/byte budget, robots/rate-limit
  compliance and an operator acknowledgement.
- The worker receives a minimal environment allowlist. It does not inherit all shell variables.
- Worktrees are read-only to the worker except for an explicit temporary state directory.
- Scenario timeouts kill the entire worker process group; retries are bounded and recorded.
- Plugin scenarios use a temporary plugin directory with known fixture plugins only.
- Reports escape HTML and spreadsheet-formula prefixes where relevant.

Fine-tuning export is **not** “all runs above score N”. Eligibility requires:

1. fixture/data licence permits training;
2. target consent/provenance is recorded;
3. recursive PII/secret redaction passes;
4. no prompt secrets or raw private tool responses;
5. deduplication and train/eval target separation;
6. judge/human approval status is present;
7. the source run, evidence and scorer versions remain traceable.

SFT exports use conversation/tool-call schemas expected by the actual trainer. Preference pairs
must differ meaningfully, pass hard gates, and should be human-reviewed before release. Arena
evaluation cases are excluded from training exports by default to prevent benchmark
contamination.

---

## 24. Revised delivery plan and acceptance tests

### Milestone A — Vertical deterministic slice

Implement schema, run directory store, worker protocol, CLI and four drivers:
`tool`, `memory`, `adaptive`, `mock`. Add five cases: operator parsing, memory round-trip,
cache hit, RAG local fixture and forced low-confidence escalation.

Acceptance:

- `python -m arena validate`
- `python -m arena run --suite smoke --profile mock`
- run is atomic, schema-valid and contains real escalation/cache events;
- all `tests/arena/` pass without network or a live LLM.

### Milestone B — Production instrumentation and model profiles

Add the no-op event sink and narrow instrumentation in LLM clients, tool registry, cache and
adaptive integration. Add `agent`, `multihop` and direct `osint` drivers. Capture provider
usage without changing existing public return types.

Acceptance:

- existing tests remain green;
- enabling/disabling capture does not change answers;
- one Ollama and one mocked cloud run produce the same event schema;
- token source is marked `provider` or `estimated`.

### Milestone C — Replayable before/after gate

Add evidence snapshots, explicit record/replay, worktree workers, comparator, hard gates and
Markdown/JSON reports. Start with deterministic functional metrics; no judge yet.

Acceptance:

- an intentional cache/escalation/tool regression fails the gate;
- network access in replay mode fails immediately;
- comparing incompatible evidence gives a clear refusal;
- dirty working-tree and git-SHA runs are identified correctly.

### Milestone D — Full capability coverage

Complete the matrix for search, page reading, RAG, every OSINT module, fallback, plugins,
compliance, hallucination guard, memory and adaptive/multihop paths. Maintain a generated
coverage report from registered drivers/tools to scenarios.

Acceptance:

- every registered tool and declared capability maps to at least one active scenario;
- skipped optional capabilities include a machine-readable reason;
- no checked-in fixture contains real secrets or uncontrolled PII.

### Milestone E — Calibrated model arena

Add pointwise/pairwise judges, blind ordering, calibration set, repeats, paired statistics,
budgets and tournament reporting.

Acceptance:

- judge schema-invalid responses are retried once then marked failed;
- A/B vs B/A disagreement is visible;
- reports show hard gates separately from composite rankings;
- budget exhaustion ends cleanly with partial results marked incomplete.

### Milestone F — History and curated dataset export

Add acquisition/reasoning drift reports, external scheduling examples, retention policy,
redaction audit, SFT/preference eligibility and lineage.

Acceptance:

- same evidence across profiles is classified as behaviour comparison;
- confounded comparisons are never labelled world or behaviour drift;
- ineligible runs cannot be exported even with `--force`;
- deletion/retention can remove PII-bearing artifacts and rebuild the index.

### Deferred until after Milestone C

- REST API, dashboard tab and leaderboard service;
- HTML charts;
- Elo;
- automatic fine-tune registration.

If an API is later added, `POST /arena/jobs` creates a bounded background job and returns
`202 + job_id`; `GET /arena/jobs/{id}` reports progress, and admin-only cancellation is
supported. A long model tournament must never block a FastAPI request worker.

---

## 25. Initial file-by-file change map

| File | First change |
|---|---|
| `arena/schema.py` | Pydantic scenario/profile/manifest/result/event models |
| `arena/worker.py` | JSONL worker protocol and driver registry |
| `arena/store.py` | partial directory, atomic finalisation, permissions |
| `core/telemetry.py` | optional `ContextVar` event sink; no arena import |
| `core/cloud_llm_client.py` | capture response model, finish reason and provider usage |
| `core/llm_client.py` | capture Ollama `prompt_eval_count`/`eval_count` and durations |
| `tools/tool_registry.py` | central tool start/end events |
| `core/cache.py` | explicit hit/miss/expired/tier events or counters |
| `core/adaptive_integration.py` | decision/escalation events; retain response metadata |
| `config/config.json.example` | optional arena budgets/retention only after schema exists |
| `.gitignore` | ignore `data/arena/*`, retain `.gitkeep` |
| `tests/arena/` | schema/store/worker/scoring/replay/security tests |

Avoid changing `app.py`, the health dashboard or `core/report_exporter.py` in the first
milestone. They are consumers of stable arena results, not prerequisites for measuring them.

---

## 26. Research basis

The revision follows these current primary/official references:

- [LangSmith evaluation workflow](https://docs.langchain.com/langsmith/evaluation):
  datasets, code/LLM/human evaluators, experiments and a feedback loop.
- [LangSmith repetitions](https://docs.langchain.com/langsmith/repetition): repeated runs and
  dispersion for non-deterministic agent outputs.
- [LangSmith experiment comparison](https://docs.langchain.com/langsmith/compare-experiment-results):
  baselines, per-example regressions, diffs, metrics and traces.
- [OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/):
  interoperable model/provider/usage/tool/evaluation naming plus explicit PII warnings.
- [pytest monkeypatch guidance](https://docs.pytest.org/en/stable/how-to/monkeypatch.html):
  scoped environment/filesystem replacement restored after tests.
- [VCR.py documentation](https://vcrpy.readthedocs.io/en/latest/): record/replay modes and
  filtering sensitive headers/query/body fields.
- [OpenAI model evaluation guidance](https://developers.openai.com/api/docs/guides/latest-model):
  compare configurations on the same representative tasks and measure quality, tokens,
  latency, cost, calls and retries.
- [OpenAI GDPval grading](https://evals.openai.com/gdpval/grading): expert pairwise preference
  is the reference standard; automated judging is an approximation.

---

*No arena implementation exists yet. Milestone A is the recommended next coding step because
it proves the storage, isolation, driver and trace contracts before expanding the suite.*
