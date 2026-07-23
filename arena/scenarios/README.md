# Arena scenario format (schema v1)

Checked-in fixtures are **JSON** (PyYAML is not yet a direct dependency — plan
§18). Each file in `cases/` is one `Scenario`; each file in `suites/` is one
`Suite` (an ordered list of scenario ids). Validation is strict: unknown fields
are rejected (`extra="forbid"`), so a typo fails `arena validate` loudly.

## Scenario (`cases/<id>.json`)

```jsonc
{
  "schema_version": 1,
  "id": "adaptive.low_confidence_escalates.v1",  // stable, unique
  "category": "escalation",                        // free-form grouping
  "driver": "adaptive",                            // mock | tool | memory | adaptive (Milestone A)
  "input": { "...": "driver-specific payload" },
  "fixture_mode": "pure",                          // pure | replay | live
  "expect": {
    "hard": {                                      // hard gates (any failure fails the scenario)
      "success": true,
      "must_include": ["substr"],
      "must_not_include": ["ERROR"],
      "expected_fields": { "operators_found": true }
    },
    "escalation": { "happened": true, "final_complexity": "high", "min_attempts": 2 },
    "cache": { "hit": true },
    "metrics": { "operator_coverage": { "min": 1.0 } }  // numeric bounds (min/max, inclusive)
  },
  "tags": ["deterministic", "smoke", "ci"],
  "timeout_s": 30,
  "repeats": 1
}
```

## Driver `input` payloads (Milestone A)

| driver | `input` fields |
|---|---|
| `mock` | `answer`, `confidence`, `coverage`, `metrics{name:float}`, `emit_events[]`, `fail`, `error` |
| `tool` (`op=parse_operators`) | `query`, `expected_operators[]` |
| `tool` (`op=cache`) | `key`, `payload` |
| `memory` | `email`, `note?` |
| `adaptive` | `query`, `force_complexity` (low\|mid\|high), `confidence`, `enable_escalation` |

## Suite (`suites/<id>.json`)

```json
{ "schema_version": 1, "id": "smoke", "description": "...", "scenarios": ["id1", "id2"] }
```

## Scoring

Hard gates are evaluated first and are never averaged away; metric bounds are
checked separately. A scenario passes only when **every** hard gate and **every**
metric bound passes (plan §22). Milestone A scoring is deterministic rules only —
no LLM-as-judge.

## Determinism

The `smoke` suite is fully deterministic and requires **no network and no LLM**,
so it is safe as a CI regression gate. RAG-over-fixtures is intentionally *not*
in the smoke suite: Chroma's default embeddings download a model on first use
(network), which violates the pure-CI contract; RAG arrives with the
evidence/replay machinery in a later milestone.
```
