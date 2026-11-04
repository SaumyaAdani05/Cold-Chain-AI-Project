"""Automated benchmarking and report support script.

Runs each scenario (S1-S5) x planner (BFS, POP) for >= 5 timing runs,
computes metrics, saves results.csv, and generates publication-ready matplotlib charts.
Conforms to TASKS.md Phase 6 (T6.1, T6.2).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Ensure project root is on sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapter import run_planner  # noqa: E402
from ui.scenarios import get_all_scenarios  # noqa: E402
from validator import validate  # noqa: E402


def run_benchmarks(num_runs: int = 5, output_dir: Path | None = None) -> Path:
    """Execute scenarios against planners, average execution times, and save results.csv."""
    if output_dir is None:
        output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = get_all_scenarios()
    planners = ["bfs", "pop"]
    rows = []

    print(f"Running benchmarks ({num_runs} runs per combination)...")

    for s_id, scenario in scenarios.items():
        for planner_name in planners:
            times = []
            final_res = None

            for _ in range(num_runs):
                res = run_planner(planner_name, scenario, timeout_s=30.0)
                times.append(res.time_s)
                final_res = res

            assert final_res is not None
            mean_time = sum(times) / len(times)

            plan_found = final_res.plan is not None
            plan_length = len(final_res.plan) if final_res.plan else 0
            explored = final_res.explored

            if plan_found and final_res.plan:
                val_res = validate(
                    init=scenario.init,
                    goal=scenario.goal,
                    plan=final_res.plan,
                    dry_ice_stock=scenario.dry_ice_stock,
                    time_budget=scenario.time_budget,
                    exposure_limit=scenario.exposure_limit,
                )
                violations = len(val_res.violations)
                dry_ice_used = val_res.dry_ice_used
                total_time = val_res.total_time
            else:
                violations = 0
                dry_ice_used = 0
                total_time = 0

            rows.append(
                {
                    "scenario": s_id,
                    "planner": planner_name.upper(),
                    "plan_found": plan_found,
                    "plan_length": plan_length,
                    "explored": explored,
                    "time_s_mean": round(mean_time, 5),
                    "violations": violations,
                    "dry_ice_used": dry_ice_used,
                    "total_time": total_time,
                }
            )

    csv_path = output_dir / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario",
                "planner",
                "plan_found",
                "plan_length",
                "explored",
                "time_s_mean",
                "violations",
                "dry_ice_used",
                "total_time",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Benchmark results saved to: {csv_path}")
    return csv_path


def generate_charts(csv_path: Path, output_dir: Path | None = None) -> list[Path]:
    """Generate matplotlib figures from benchmark results.csv."""
    if output_dir is None:
        output_dir = csv_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    generated_charts = []

    # Chart 1: Planning Time per Scenario
    plt.figure(figsize=(8, 5))
    scenarios = df["scenario"].unique()
    bfs_times = df[df["planner"] == "BFS"].set_index("scenario").reindex(scenarios)["time_s_mean"]
    pop_times = df[df["planner"] == "POP"].set_index("scenario").reindex(scenarios)["time_s_mean"]

    x = range(len(scenarios))
    width = 0.35

    plt.bar([i - width / 2 for i in x], bfs_times, width, label="BFS", color="#1976d2")
    plt.bar([i + width / 2 for i in x], pop_times, width, label="POP", color="#f57c00")

    plt.xlabel("Scenario ID", fontsize=11)
    plt.ylabel("Mean Planning Time (seconds)", fontsize=11)
    plt.title("Planning Time Comparison by Scenario (Mean of 5 Runs)", fontsize=12, fontweight="bold")
    plt.xticks(x, scenarios)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    time_chart_path = output_dir / "chart_planning_time.png"
    plt.savefig(time_chart_path, dpi=200)
    plt.close()
    generated_charts.append(time_chart_path)

    # Chart 2: Explored States / Nodes
    plt.figure(figsize=(8, 5))
    bfs_explored = df[df["planner"] == "BFS"].set_index("scenario").reindex(scenarios)["explored"]
    pop_explored = df[df["planner"] == "POP"].set_index("scenario").reindex(scenarios)["explored"]

    plt.bar([i - width / 2 for i in x], bfs_explored, width, label="BFS (States)", color="#388e3c")
    plt.bar([i + width / 2 for i in x], pop_explored, width, label="POP (Nodes)", color="#7b1fa2")

    plt.xlabel("Scenario ID", fontsize=11)
    plt.ylabel("Explored Search Nodes / States", fontsize=11)
    plt.title("Search Space Exploration Comparison", fontsize=12, fontweight="bold")
    plt.xticks(x, scenarios)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    nodes_chart_path = output_dir / "chart_explored_nodes.png"
    plt.savefig(nodes_chart_path, dpi=200)
    plt.close()
    generated_charts.append(nodes_chart_path)

    print(f"Generated charts: {[str(p) for p in generated_charts]}")
    return generated_charts


if __name__ == "__main__":
    csv_file = run_benchmarks()
    generate_charts(csv_file)
