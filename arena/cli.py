"""Command-line interface: ``python -m arena ...``.

Milestone A commands::

    arena validate                       # validate all scenarios & suites
    arena drivers                        # list registered drivers
    arena run --suite smoke --profile mock [--seed N] [--no-store] [--json]
    arena list                           # show the run index
    arena show <run_id>                  # show one run's results
    arena doctor                         # report incomplete/partial run dirs

Exit codes: ``run`` exits non-zero if any scenario failed (usable as a smoke
gate); ``validate`` exits non-zero on any invalid fixture.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from arena.drivers import known_drivers
from arena.loader import ScenarioError, validate_all
from arena.runner import ArenaRunner
from arena.schema import Profile
from arena.store import ArenaStore

# Built-in profiles usable by id without a file.
_BUILTIN_PROFILES: dict[str, Profile] = {
    "mock": Profile(id="mock", provider="mock", model="mock"),
}


def _resolve_profile(spec: str) -> Profile:
    if spec in _BUILTIN_PROFILES:
        return _BUILTIN_PROFILES[spec]
    path = Path(spec)
    if path.exists():
        return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    raise SystemExit(f"unknown profile {spec!r} (built-ins: {sorted(_BUILTIN_PROFILES)}; or pass a JSON path)")


def _cmd_validate(_args: argparse.Namespace) -> int:
    try:
        cases, suites = validate_all()
    except ScenarioError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(cases)} scenarios, {len(suites)} suites")
    for s in suites:
        print(f"  suite: {s}")
    return 0


def _cmd_drivers(_args: argparse.Namespace) -> int:
    for name in known_drivers():
        print(name)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    profile = _resolve_profile(args.profile)
    store = ArenaStore(args.root) if args.root else ArenaStore()
    runner = ArenaRunner(store)
    try:
        manifest, results, summary = runner.run_suite(
            args.suite, profile, seed=args.seed, persist=not args.no_store
        )
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary.model_dump(), indent=2))
    else:
        _print_table(manifest.run_id, results)
        status = "PASS" if summary.failed == 0 else "FAIL"
        print(
            f"\n{status}  run={manifest.run_id}  suite={summary.suite_id}  "
            f"profile={summary.profile_id}  {summary.passed}/{summary.scenario_count} passed  "
            f"mean_latency={summary.mean_latency_ms:.1f}ms"
        )
        if not args.no_store:
            print(f"stored: {store.runs_dir / manifest.run_id}")
    return 0 if summary.failed == 0 else 1


def _print_table(run_id: str, results: list[Any]) -> None:
    width = max((len(r.scenario_id) for r in results), default=10)
    for r in results:
        mark = "PASS" if r.score.passed else "FAIL"
        line = f"  [{mark}] {r.scenario_id:<{width}}  {r.metrics.latency_ms:6.1f}ms  driver={r.driver}"
        print(line)
        if not r.score.passed:
            for g in list(r.score.gates) + list(r.score.metric_checks):
                if not g.passed:
                    print(f"         - {g.name}: {g.detail}")


def _cmd_list(args: argparse.Namespace) -> int:
    store = ArenaStore(args.root) if args.root else ArenaStore()
    rows = list(store.iter_index())
    if not rows:
        print("(no runs indexed)")
        return 0
    for row in rows:
        print(
            f"{row.run_id}  {row.created_at}  {row.suite_id:<12}  {row.profile_id:<12}  "
            f"{row.passed}/{row.scenario_count} passed"
        )
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    store = ArenaStore(args.root) if args.root else ArenaStore()
    if not store.is_complete(args.run_id):
        print(f"run {args.run_id!r} not found or incomplete", file=sys.stderr)
        return 1
    manifest = store.read_manifest(args.run_id)
    print(f"run={manifest.run_id} suite={manifest.suite_id} git={manifest.git_sha[:12]} dirty={manifest.git_dirty}")
    _print_table(manifest.run_id, store.read_results(args.run_id))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    from arena.compare import ComparabilityError, compare_runs
    from arena.report import to_json, to_markdown

    store = ArenaStore(args.root) if args.root else ArenaStore()
    for run_id in (args.before, args.after):
        if not store.is_complete(run_id):
            print(f"run {run_id!r} not found or incomplete", file=sys.stderr)
            return 2

    try:
        report = compare_runs(
            store.read_manifest(args.before),
            store.read_results(args.before),
            store.read_manifest(args.after),
            store.read_results(args.after),
            varying=args.varying,
            allow_mismatch=set(args.allow_mismatch or []),
        )
    except ComparabilityError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(to_json(report) if args.format == "json" else to_markdown(report))
    if args.gate and report.regression:
        return 1
    return 0


def _cmd_compare_sha(args: argparse.Namespace) -> int:
    from arena.compare import ComparabilityError
    from arena.coordinator import CoordinatorError, compare_shas
    from arena.report import to_json, to_markdown

    root = args.root or "data/arena"
    try:
        report = compare_shas(
            args.before,
            args.after,
            suite=args.suite,
            profile=args.profile,
            arena_root=root,
            seed=args.seed,
            allow_mismatch=set(args.allow_mismatch or []),
        )
    except CoordinatorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ComparabilityError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(to_json(report) if args.format == "json" else to_markdown(report))
    if args.gate and report.regression:
        return 1
    return 0


def _cmd_coverage(args: argparse.Namespace) -> int:
    from arena.coverage import coverage_report, to_json, to_markdown

    report = coverage_report()
    print(to_json(report) if args.format == "json" else to_markdown(report))
    if args.gate and not report.complete:
        return 1
    return 0


def _cmd_tournament(args: argparse.Namespace) -> int:
    from arena.runner import ArenaRunner
    from arena.store import ArenaStore
    from arena.tournament import run_tournament, to_json, to_markdown

    store = ArenaStore(args.root) if args.root else ArenaStore()
    runner = ArenaRunner(store)
    runs_by_profile: dict = {}
    for spec in args.profiles.split(","):
        spec = spec.strip()
        if not spec:
            continue
        profile = _resolve_profile(spec)
        manifest, results, _ = runner.run_suite(args.suite, profile, seed=args.seed, persist=not args.no_store)
        runs_by_profile[profile.id] = (manifest, results)

    report = run_tournament(args.suite, runs_by_profile)
    print(to_json(report) if args.format == "json" else to_markdown(report))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    store = ArenaStore(args.root) if args.root else ArenaStore()
    incomplete = store.find_incomplete()
    if not incomplete:
        print("OK: no incomplete run directories")
        return 0
    print("incomplete run directories:")
    for name in incomplete:
        print(f"  {name}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arena", description="CrawlLama Model Arena harness")
    parser.add_argument("--root", help="arena data root (default data/arena)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate all scenarios and suites").set_defaults(func=_cmd_validate)
    sub.add_parser("drivers", help="list registered drivers").set_defaults(func=_cmd_drivers)

    run = sub.add_parser("run", help="run a suite against a profile")
    run.add_argument("--suite", required=True)
    run.add_argument("--profile", required=True, help="built-in id (e.g. mock) or path to a profile JSON")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--no-store", action="store_true", help="do not persist the run")
    run.add_argument("--json", action="store_true", help="print the summary as JSON")
    run.set_defaults(func=_cmd_run)

    sub.add_parser("list", help="list indexed runs").set_defaults(func=_cmd_list)

    show = sub.add_parser("show", help="show one run")
    show.add_argument("run_id")
    show.set_defaults(func=_cmd_show)

    comp = sub.add_parser("compare", help="before/after comparison + regression gate")
    comp.add_argument("--before", required=True, help="baseline run id")
    comp.add_argument("--after", required=True, help="candidate run id")
    comp.add_argument(
        "--varying",
        default="code",
        choices=["code", "model", "scenarios", "scorer", "evidence"],
        help="the single dimension expected to differ (default: code)",
    )
    comp.add_argument(
        "--allow-mismatch",
        action="append",
        default=[],
        help="permit a required-equal dimension to differ (repeatable)",
    )
    comp.add_argument("--gate", action="store_true", help="exit non-zero on regression")
    comp.add_argument("--format", choices=["md", "json"], default="md")
    comp.set_defaults(func=_cmd_compare)

    csha = sub.add_parser("compare-sha", help="run a suite at two git SHAs (worktrees) and compare")
    csha.add_argument("--before", required=True, help="baseline git SHA/ref")
    csha.add_argument("--after", required=True, help="candidate git SHA/ref")
    csha.add_argument("--suite", required=True)
    csha.add_argument("--profile", default="mock")
    csha.add_argument("--seed", type=int, default=0)
    csha.add_argument("--allow-mismatch", action="append", default=[])
    csha.add_argument("--gate", action="store_true", help="exit non-zero on regression")
    csha.add_argument("--format", choices=["md", "json"], default="md")
    csha.set_defaults(func=_cmd_compare_sha)

    cov = sub.add_parser("coverage", help="capability coverage report")
    cov.add_argument("--format", choices=["md", "json"], default="md")
    cov.add_argument("--gate", action="store_true", help="exit non-zero if any required capability is uncovered")
    cov.set_defaults(func=_cmd_coverage)

    tour = sub.add_parser("tournament", help="run a suite across profiles and rank them")
    tour.add_argument("--profiles", required=True, help="comma-separated profile ids/paths")
    tour.add_argument("--suite", required=True)
    tour.add_argument("--seed", type=int, default=0)
    tour.add_argument("--no-store", action="store_true")
    tour.add_argument("--format", choices=["md", "json"], default="md")
    tour.set_defaults(func=_cmd_tournament)

    sub.add_parser("doctor", help="report incomplete run directories").set_defaults(func=_cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
