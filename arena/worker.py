"""Worker: one JSON request → one JSON result over stdin/stdout (JSON Lines).

The worker is the process boundary that lets the coordinator drive a scenario
inside a *specific code checkout and interpreter* (plan §18). Two git SHAs are
never imported into one Python process; the coordinator (Milestone C) speaks this
protocol to a worker launched from each worktree. In Milestone A the worker runs
in-tree and is exercised directly by tests and (optionally) the CLI.

Protocol (version-checked): each stdin line is a JSON request; each stdout line
is a JSON response. Supported ops:

    {"op": "ping"}                              -> {"ok": true, "pong": true, ...}
    {"op": "capabilities"}                      -> {"ok": true, "drivers": [...]}
    {"op": "run_scenario", "scenario": {...},   -> {"ok": true, "result": {...}}
     "seed": 0}

A request whose ``protocol_version`` is newer than the worker's is refused rather
than silently comparing different meanings.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from pydantic import ValidationError

from arena import WORKER_PROTOCOL_VERSION
from arena.drivers import known_drivers
from arena.runner import execute_scenario
from arena.schema import Scenario


def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    """Process one decoded request dict and return a response dict."""
    client_version = req.get("protocol_version", WORKER_PROTOCOL_VERSION)
    if not isinstance(client_version, int) or client_version > WORKER_PROTOCOL_VERSION:
        return _err(f"unsupported protocol_version {client_version!r} (worker={WORKER_PROTOCOL_VERSION})")

    op = req.get("op")
    if op == "ping":
        return {"ok": True, "pong": True, "protocol_version": WORKER_PROTOCOL_VERSION}
    if op == "capabilities":
        return {"ok": True, "protocol_version": WORKER_PROTOCOL_VERSION, "drivers": known_drivers()}
    if op == "run_scenario":
        return _run_scenario(req)
    return _err(f"unknown op {op!r}")


def _run_scenario(req: dict[str, Any]) -> dict[str, Any]:
    raw = req.get("scenario")
    if not isinstance(raw, dict):
        return _err("run_scenario requires a 'scenario' object")
    try:
        scenario = Scenario.model_validate(raw)
    except ValidationError as exc:
        return _err(f"invalid scenario: {exc}")
    seed = int(req.get("seed", 0))
    result = execute_scenario(scenario, seed=seed, run_id=str(req.get("run_id", "worker")))
    return {
        "ok": True,
        "protocol_version": WORKER_PROTOCOL_VERSION,
        "result": result.model_dump(mode="json"),
    }


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "protocol_version": WORKER_PROTOCOL_VERSION, "error": message}


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    """Read JSON-line requests until EOF, writing one JSON-line response each."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = _err(f"malformed JSON: {exc}")
        else:
            resp = handle_request(req)
        stdout.write(json.dumps(resp) + "\n")
        stdout.flush()


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    serve()
