"""End-to-end tests: both planners on every scenario, plus the comparison and CLI."""

import pytest

from comparison import comparison_rows, compare_algorithms
from main import main
from scenarios import get_scenario, list_scenarios

# Expected (BFS status, POP status) for each scenario. "valid" means the plan
# was found and passed the validator; "rejected" means a plan was found but
# broke a constraint; "no_plan" means the planner found nothing.
EXPECTED_STATUS = {
    "normal_single_vaccine": ("valid", "valid"),
    "mixed_processing_requirements": ("valid", "valid"),
    "limited_dry_ice": ("no_plan", "rejected"),
    "restricted_time_budget": ("no_plan", "rejected"),
    "temperature_verification_failure": ("no_plan", "no_plan"),
    "refrigerated_only_success": ("valid", "valid"),
}


@pytest.mark.parametrize("key", sorted(EXPECTED_STATUS))
def test_both_planners_match_expected_outcome(key):
    bfs_run, pop_run = compare_algorithms(get_scenario(key))
    assert (bfs_run.status, pop_run.status) == EXPECTED_STATUS[key]


def test_every_scenario_has_an_expectation():
    assert {s.key for s in list_scenarios()} == set(EXPECTED_STATUS)


def test_comparison_rows_have_one_row_per_algorithm():
    runs = compare_algorithms(get_scenario("normal_single_vaccine"))
    rows = comparison_rows(runs)
    assert [row["Algorithm"] for row in rows] == ["BFS", "POP"]
    assert rows[0]["Parallel makespan (min)"] == "-"  # BFS has no partial order


def test_metrics_come_from_real_runs():
    scenario = get_scenario("normal_single_vaccine")
    bfs_run, pop_run = compare_algorithms(scenario)
    assert bfs_run.plan_length == 8
    assert pop_run.plan_length == 8
    assert bfs_run.sequential_minutes == 32
    assert pop_run.dry_ice_kg == 2
    assert bfs_run.elapsed_seconds >= 0 and pop_run.elapsed_seconds >= 0


def test_cli_list_returns_zero():
    assert main(["--list"]) == 0


def test_cli_unknown_scenario_returns_error_code(capsys):
    assert main(["--scenario", "nope"]) == 2
    assert "Unknown scenario" in capsys.readouterr().err
