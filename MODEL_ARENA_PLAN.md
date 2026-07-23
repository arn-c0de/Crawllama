# CrawlLama Model Arena & Regression Testing Harness — Design Plan

> **Status:** Proposal / design draft
> **Target version:** 1.5.x
> **Owner:** CrawlLama Team
> **Scope:** A reproducible testing, benchmarking, and "arena" subsystem that lets us
> (a) compare tool behaviour **before vs. after code changes**, (b) compare **different LLM
> models / providers / configs** head-to-head, (c) build **longitudinal / historical** records
> for the *same* target (e.g. one web domain analysed repeatedly over time), and (d) export
> high-quality traces as **fine-tuning data**. It must exercise **every major tool function**,
> including adaptive-hop **escalation**.

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

## 16. Open questions

1. Composite-score default weights — one canonical weighting, or ship 2–3 named profiles
   (accuracy-first, latency-first, OSINT-coverage-first)?
2. Judge model default — which cloud model, and do we allow a strong *local* judge for fully
   offline operation?
3. Elo/pairwise ranking in the tournament, or is a simple weighted mean sufficient for v1?
4. Should the history scheduler live inside the health dashboard or as a standalone cron/loop?

---

*This document is a design proposal. No code has been written yet; Phase 0–1 are the
recommended starting point and are self-contained.*
