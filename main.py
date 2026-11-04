"""
main.py - command-line runner (no browser needed).

Examples:
    python main.py --list
    python main.py --scenario normal_single_vaccine
    python main.py --scenario limited_dry_ice --algorithm bfs
    python main.py                       # runs every scenario with both planners
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from comparison import STATUS_LABELS, AlgorithmRun, compare_algorithms, run_bfs, run_pop
from constraints import simulate_temperature_readings
from scenarios import Scenario, get_scenario, list_scenarios


def scenario_to_dict(scenario: Scenario) -> Dict[str, object]:
    """Scenario definition as plain data (used for the JSON export)."""
    problem = scenario.build_problem()
    constraints = scenario.constraints
    return {
        "key": scenario.key,
        "title": scenario.title,
        "description": scenario.description,
        "lesson": scenario.lesson,
        "expected_outcome": scenario.expected_outcome,
        "constraints": {
            "max_duration_minutes": constraints.max_duration_minutes,
            "dry_ice_available_kg": constraints.dry_ice_available_kg,
            "dry_ice_per_package_kg": constraints.dry_ice_per_package_kg,
            "action_durations": constraints.action_durations,
        },
        "packages": [
            {
                "package_id": pkg.package_id,
                "label": pkg.label,
                "needs_dry_ice": pkg.needs_dry_ice,
                "acceptable_range_c": [pkg.temp_min_c, pkg.temp_max_c],
                "simulated_readings_c": simulate_temperature_readings(pkg),
            }
            for pkg in scenario.packages
        ],
        "initial_state": sorted(problem.initial_state),
        "goal": sorted(problem.goal),
    }


def run_to_dict(run: AlgorithmRun) -> Dict[str, object]:
    """Planner run as plain data (used for the JSON export)."""
    return {
        "algorithm": run.algorithm,
        "representation": run.representation,
        "status": run.status,
        "message": run.message,
        "explored": run.explored,
        "planning_time_ms": round(run.elapsed_seconds * 1000, 3),
        "goal_achieved": run.goal_achieved,
        "plan": [action.name for action in run.actions],
        "plan_length": run.plan_length,
        "sequential_minutes": run.sequential_minutes if run.success else None,
        "parallel_makespan_minutes": run.makespan_minutes,
        "dry_ice_kg": run.dry_ice_kg if run.success else None,
        "violations": run.violations,
    }


def export_json(out_dir: str) -> List[Path]:
    """Write one JSON file per scenario with its definition and both planner results."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for scenario in list_scenarios():
        data = scenario_to_dict(scenario)
        data["results"] = [run_to_dict(run) for run in compare_algorithms(scenario)]
        path = folder / f"{scenario.key}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        written.append(path)
    return written


def print_run(run: AlgorithmRun) -> None:
    """Print one planner run in a readable block."""
    print(f"  [{run.algorithm}] {STATUS_LABELS[run.status]}")
    print(f"      message      : {run.message}")
    print(f"      explored     : {run.explored} ({'states' if run.algorithm == 'BFS' else 'nodes'})")
    print(f"      time         : {run.elapsed_seconds * 1000:.3f} ms")
    if run.success:
        print(f"      goal achieved: {'yes' if run.goal_achieved else 'no'}")
        print(f"      plan length  : {run.plan_length} actions")
        print(f"      duration     : {run.sequential_minutes} min (sequential)")
        print(f"      dry ice used : {run.dry_ice_kg} kg")
    if run.violations:
        for violation in run.violations:
            print(f"      violation    : {violation}")
    if run.actions and run.status == "valid":
        print("      plan (one valid order):")
        for index, action in enumerate(run.actions, start=1):
            print(f"        {index:2d}. {action.name}")
    if run.partial_plan is not None:
        plan = run.partial_plan
        print(f"      causal links : {len(plan.links)}")
        print(f"      ordering constraints (non-redundant): {len(plan.reduced_orderings())}")
        print(f"      unordered step pairs: {len(plan.independent_pairs())}")
        print(f"      parallel makespan   : {plan.critical_path_minutes()} min (informational)")


def run_scenario(key: str, algorithm: str) -> None:
    scenario = get_scenario(key)
    print("=" * 78)
    print(f"{scenario.title}   (expected: {scenario.expected_outcome})")
    print(f"  {scenario.description}")
    if algorithm == "bfs":
        runs = [run_bfs(scenario)]
    elif algorithm == "pop":
        runs = [run_pop(scenario)]
    else:
        runs = compare_algorithms(scenario)
    for run in runs:
        print_run(run)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cold-chain planning with BFS and POP.")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument("--scenario", help="scenario key (default: all scenarios)")
    parser.add_argument("--algorithm", choices=["bfs", "pop", "both"], default="both")
    parser.add_argument(
        "--export-json", metavar="DIR", help="write each scenario and its results as JSON into DIR"
    )
    args = parser.parse_args(argv)

    if args.list:
        for scenario in list_scenarios():
            print(f"{scenario.key:34s} {scenario.expected_outcome:8s} {scenario.title}")
        return 0

    if args.export_json:
        for path in export_json(args.export_json):
            print(f"wrote {path}")
        return 0

    keys = [args.scenario] if args.scenario else [s.key for s in list_scenarios()]
    try:
        for key in keys:
            run_scenario(key, args.algorithm)
    except KeyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
