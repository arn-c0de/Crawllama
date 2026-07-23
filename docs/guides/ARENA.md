# Model Arena & Regression Harness

The **arena** (`arena/` package, run via `python -m arena`) is CrawlLama's
reproducible testing, benchmarking and A/B-comparison subsystem. It answers
questions `pytest` and the health dashboard cannot:

- *Did my refactor make domain analysis better or worse?* → **before/after gate**
- *Is `llama3.1:8b` actually better than another model for this suite?* → **tournament**
- *Which capabilities have no scenario yet?* → **coverage report**
- *How does the same target drift over time?* → **history / drift**

It reuses existing infrastructure (agents, OSINT modules, hallucination detector,
adaptive hops) rather than reinventing measurement. The full design lives in
[`MODEL_ARENA_PLAN.md`](../../MODEL_ARENA_PLAN.md); this guide is the operational
how-to.

> **Status:** Milestones A–F implemented. The scenario format reference is in
> [`arena/scenarios/README.md`](../../arena/scenarios/README.md); external
> scheduling is in [`arena/scenarios/SCHEDULING.md`](../../arena/scenarios/SCHEDULING.md).

---

## 1. Mental model — how a run works

```
 suite (list of scenario ids)          profile (provider, model, params)
             │                                        │
             ▼                                        ▼
        ┌──────────────────────  ArenaRunner  ──────────────────────┐
        │  for each scenario:                                       │
        │    1. isolate state  (temp workdir: cache, memory, session)│
        │    2. pick driver    (mock | tool | memory | adaptive | …) │
        │    3. run driver     → DriverResult + telemetry events     │
        │    4. score          → hard gates first, then metric bounds │
        └───────────────────────────┬───────────────────────────────┘
                                     ▼
              data/arena/runs/<run_id>/  (manifest, results, events, summary)
                                     ▼
        compare · tournament · coverage · history · retention
```

**Key design fact — the arena is deterministic and offline by design.** Every
driver injects a **`FakeLLM`** and disables network access, so a run is fully
reproducible and safe as a CI gate. This means:

- The **profile's `provider`/`model` do not drive live inference** today. They are
  recorded in the run **manifest** as *comparison-identity* dimensions — labels
  that say *which configuration a result belongs to* so `compare`/`tournament`
  can group and diff runs correctly. Running "with ollama" means running the
  deterministic suite under an ollama-labelled manifest, not calling Ollama.
- The world is frozen (fixtures / disabled web), so any difference between two
  runs is attributable to **code** or **scenario** changes, not the live web.

This is deliberate (plan §7, §17): comparability is the whole point, and a live
LLM's non-determinism would swamp the signal.

---

## 2. Quick start

```bash
# Validate all scenarios + suites (strict; a typo fails loudly)
uv run python -m arena validate

# List the registered drivers
uv run python -m arena drivers

# Run the deterministic CI gate with the built-in mock profile
uv run python -m arena run --suite smoke --profile mock

# Run under a named ollama profile (see §6)
uv run python -m arena run --suite smoke \
    --profile arena/scenarios/profiles/ollama-llama31-8b.json

# Inspect stored runs
uv run python -m arena list
uv run python -m arena show <run_id>
```

A passing run prints a per-scenario table and stores results under
`data/arena/runs/<run_id>/`.

---

## 3. CLI reference

All commands are subcommands of `python -m arena` and accept a global
`--root <dir>` to point at a different data root (default `data/arena`).

| Command | Purpose |
|---|---|
| `validate` | Validate every scenario/suite JSON (strict, `extra="forbid"`). |
| `drivers` | List registered driver names. |
| `run --suite S --profile P` | Run suite `S` under profile `P`; store + score. Flags: `--seed`, `--no-store`, `--json`. |
| `list` | List indexed runs (from `index.jsonl`). |
| `show <run_id>` | Show one run's manifest + per-scenario results. |
| `compare --before <id> --after <id>` | Before/after diff + regression gate over two existing runs. |
| `compare-sha --before <ref> --after <ref> --suite S` | Check out two git SHAs into worktrees, run the suite in each, and compare. |
| `coverage` | Capability coverage report (drivers/tools → scenarios). |
| `tournament --profiles a,b,c --suite S` | Run one suite across N profiles and rank them. |
| `history --target T` | Longitudinal timeline for a target. |
| `retention [--delete <id>] [--rebuild-index]` | Delete a run's artifacts / rebuild the index. |
| `doctor` | Report incomplete (crashed) run directories. |

### Comparison & gating

`compare` enforces **field-specific comparability** (plan §21): to compare two
runs you must vary exactly one dimension and hold the rest equal.

```bash
# Code change: same model/scenarios/scorer, different code state
uv run python -m arena compare --before <baseline_id> --after <candidate_id> \
    --varying code --gate

# Model change (A/B): same code/scenarios, different provider/model
uv run python -m arena compare --before <run_a> --after <run_b> \
    --varying model --gate
```

- `--varying {code|model|scenarios|scorer|evidence}` — the one dimension expected
  to differ (default `code`).
- `--allow-mismatch <field>` (repeatable) — permit a normally-required-equal
  dimension to differ; the report flags it.
- `--gate` — **exit non-zero on regression**, for CI.
- `--format {md|json}`.

The comparator refuses (or flags) mismatched manifests rather than silently
comparing incomparable runs.

### Tournament

```bash
uv run python -m arena tournament \
    --profiles mock,arena/scenarios/profiles/ollama-llama31-8b.json \
    --suite smoke --format md
```

Runs the same suite under each profile and ranks them, with per-category
breakdown. Hard-gate results are always shown **separately** from composite
rankings (a hard failure is never averaged away).

---

## 4. Scenarios, suites & drivers

A **scenario** (`arena/scenarios/cases/<id>.json`) declares a `driver`, an
`input` payload, a `fixture_mode` (`pure | replay | live`) and an `expect` block
of gates/metrics. A **suite** (`arena/scenarios/suites/<id>.json`) is an ordered
list of scenario ids. Full format: [`arena/scenarios/README.md`](../../arena/scenarios/README.md).

### Built-in suites

| Suite | What it exercises | Network / LLM |
|---|---|---|
| `smoke` | Operators, cache, memory, adaptive escalation, offline OSINT, hallucination guard, compliance, fallback, plugin load/invoke/unload. **The CI regression gate.** | none |
| `capabilities` | The **real** `SearchAgent` (context-only) and `MultiHopReasoningAgent`, built offline with an injected fake LLM. Heavier. | none |
| `live` | Network-bound tools: web search, page read, wiki, RAG. **Not run in CI.** | requires network/embeddings |

### Drivers

Each scenario names a driver that adapts one production capability to the arena:

```
adaptive  agent  compliance  fallback  hallucination
memory    mock   multihop    osint     plugin        tool
```

`agent` and `multihop` construct the real production agents but neutralise web
access, isolate all filesystem state into the scenario workdir, and inject a
`FakeLLM` that returns a canned answer while emitting `llm.completed` telemetry
events (token source `estimated`). The rest are pure/offline leaf operations.

---

## 5. Scoring

Scoring is deterministic rules (Milestone A–D); the metric hierarchy (plan §22):

1. **Hard gates** — execution success, `must_include`/`must_not_include`,
   required fields, expected escalation/cache/tool behaviour. **Any** hard-gate
   failure fails the scenario and is never hidden inside a weighted mean.
2. **Metric bounds** — numeric `min`/`max` checks (e.g. `operator_coverage ≥ 1.0`).

A scenario passes only when **every** hard gate **and every** metric bound passes.
LLM-as-judge scoring (`scoring/judge.py`, pinned judge model, pairwise + blind
ordering + calibration) is available for model-comparison use but is never the
sole gate.

---

## 6. Profiles (including "with ollama")

A **profile** is a JSON file (or the built-in `mock`) describing the
configuration a run is labelled with:

```json
{
  "id": "ollama-llama31-8b",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "params": { "temperature": 0.0, "seed": 0, "num_ctx": 16000 },
  "code_state": "WORKTREE",
  "config_overrides": {}
}
```

Pass it by path: `--profile arena/scenarios/profiles/ollama-llama31-8b.json`.
Every field lands in the run manifest so `compare --varying model` can A/B two
model profiles fairly (same code, same scenarios, same scorer). As noted in §1,
the profile labels the run; it does not (yet) trigger live Ollama inference.

Built-in: `mock` (`provider=mock, model=mock`).

---

## 7. Storage layout

Results live under `data/arena/` (owner-only `0o700`, git-ignored, may contain
PII). One atomic directory per run (plan §21):

```
data/arena/
  index.jsonl                     # one summary row per run (id, sha, model, pass/total, ts)
  runs/<run_id>/
    manifest.json                 # reproducibility contract (git sha/dirty, config_hash, profile, hashes)
    results.jsonl                 # one line per scenario result (metrics, score, gates)
    events.jsonl                  # telemetry events (OpenTelemetry GenAI-aligned attrs)
    summary.json                  # run rollup (passed/failed, mean latency, provider/model)
    COMPLETE                      # marker; incomplete dirs are ignored by readers
```

- `run_id` is a sortable ULID-like id; comparison identity is a separate hash set.
- Writes go to a `.partial/` dir, fsync + atomic rename, then a `COMPLETE` marker;
  `arena doctor` finds crashed/incomplete directories, `arena retention` prunes
  and rebuilds the index.
- **Events** use OpenTelemetry GenAI attribute names (`gen_ai.provider.name`,
  `gen_ai.request.model`, `gen_ai.usage.input_tokens`, …). Raw prompts, tool
  arguments and outputs are **not** stored as attributes by default (PII).

---

## 8. Determinism, isolation & CI

- **State isolation:** each scenario gets a fresh temp workdir (cache, memory,
  session) — no cross-run leakage.
- **No network / no LLM** in `smoke` and `capabilities`; an unexpected network
  call in `replay` mode is a hard failure.
- **CI gate:** run the deterministic suite on each PR and fail on regression:
  ```bash
  uv run python -m arena run --suite smoke --profile mock
  uv run python -m arena compare --before <base_run> --after <head_run> --gate
  ```
- **Full screening (tests + arena in one gate):** `./full-screening.sh` merges
  both testing layers — it runs the **pytest suite first** (unit correctness of
  every tool) and, only if green, **then the arena** (validate → coverage gate →
  smoke → capabilities). This is the "screen everything" entry point:
  ```bash
  ./full-screening.sh                  # pytest + deterministic arena
  ./full-screening.sh --live           # also the live tool suite (web/page/wiki/RAG)
  ./full-screening.sh --profile arena/scenarios/profiles/ollama-llama31-8b.json
  ```
  The `arena coverage --gate` stage enforces that **every registered tool/
  capability maps to at least one scenario**, so a new tool without a scenario
  fails the screening.
- **Scheduling is external** (cron / systemd / GitHub Actions) — the arena owns
  no scheduler. See [`arena/scenarios/SCHEDULING.md`](../../arena/scenarios/SCHEDULING.md).

---

## 9. Where things live (package map)

| Path | Responsibility |
|---|---|
| `arena/cli.py`, `arena/__main__.py` | `python -m arena` command surface |
| `arena/schema.py` | Strict Pydantic models (Scenario, Profile, Manifest, Result, Event, …) |
| `arena/loader.py` | Load + validate scenarios/suites |
| `arena/runner.py`, `arena/coordinator.py`, `arena/worker.py` | Orchestration + JSONL worker protocol |
| `arena/drivers/` | One adapter per capability (see §4) |
| `arena/collectors/` | Latency + token/usage collection |
| `arena/scoring/` | `rules`, `judge`, `calibration` |
| `arena/store.py` | Atomic run directories, index, permissions |
| `arena/compare.py`, `arena/tournament.py`, `arena/coverage.py` | Comparisons + reports |
| `arena/history.py`, `arena/drift.py` | Longitudinal timeline + drift attribution |
| `arena/datasets.py`, `arena/redact.py`, `arena/retention.py` | Fine-tuning export, PII redaction, retention |
| `arena/evidence/`, `arena/budget.py`, `arena/statistics.py` | Evidence replay, cost budgets, paired stats |
| `core/telemetry.py` | No-op-by-default event sink (`core/` never imports `arena/`) |
| `arena/scenarios/` | Checked-in JSON cases + suites + profiles |

---

## See also

- [`MODEL_ARENA_PLAN.md`](../../MODEL_ARENA_PLAN.md) — full design and rationale.
- [`arena/scenarios/README.md`](../../arena/scenarios/README.md) — scenario/suite JSON format.
- [`arena/scenarios/SCHEDULING.md`](../../arena/scenarios/SCHEDULING.md) — external scheduling recipes.
