"""Tests for the independent plan validator and the scenario definitions."""

import pytest

from actions import build_actions
from bfs import bfs_plan
from scenarios import get_scenario, list_scenarios
from validator import validate_plan


def _action(scenario, name):
    return next(a for a in scenario.build_problem().actions if a.name == name)


def test_validator_accepts_a_correct_bfs_plan():
    scenario = get_scenario("normal_single_vaccine")
    plan = bfs_plan(scenario.build_problem(), max_duration=120, max_dry_ice=10).actions
    report = validate_plan(scenario, plan)
    assert report.valid
    assert report.goal_achieved
    assert report.total_duration == 32
    assert report.dry_ice_used_kg == 2
    assert report.all_problems == []


def test_validator_rejects_sealing_before_inspection():
    scenario = get_scenario("normal_single_vaccine")
    sequence = [_action(scenario, n) for n in (
        "receive_package(P1)", "verify_temperature(P1)", "move_to_cold_room(P1)",
        "pack_dry_ice(P1)", "seal_container(P1)")]
    report = validate_plan(scenario, sequence)
    assert not report.valid
    assert any("seal_container(P1)" in f and "container_inspected" in f
               for f in report.precondition_failures)


def test_validator_rejects_loading_before_dock():
    scenario = get_scenario("refrigerated_only_success")
    sequence = [_action(scenario, n) for n in (
        "receive_package(P2)", "verify_temperature(P2)", "move_to_cold_room(P2)",
        "inspect_container(P2)", "seal_container(P2)", "load_pallet(P2)")]
    report = validate_plan(scenario, sequence)
    assert not report.valid
    assert any("load_pallet(P2)" in f for f in report.precondition_failures)


def test_validator_reports_temperature_violation_for_warm_package():
    scenario = get_scenario("temperature_verification_failure")
    sequence = [_action(scenario, "receive_package(P2)")]
    report = validate_plan(scenario, sequence)
    assert not report.valid
    assert any("outside" in v for v in report.constraint_violations)


def test_partial_plan_does_not_achieve_goal():
    scenario = get_scenario("normal_single_vaccine")
    plan = bfs_plan(scenario.build_problem(), max_duration=120, max_dry_ice=10).actions
    report = validate_plan(scenario, plan[:3])
    assert not report.goal_achieved
    assert not report.valid


def test_one_package_within_dry_ice_stock_is_not_flagged():
    scenario = get_scenario("limited_dry_ice")  # 2 kg in stock, 2 kg per package
    problem_actions = [a for a in scenario.build_problem().actions
                       if a.package_id == "P1" and a.action_type in (
                           "receive_package", "verify_temperature", "move_to_cold_room", "pack_dry_ice")]
    report = validate_plan(scenario, problem_actions)
    assert report.dry_ice_used_kg == 2
    assert not any("Dry ice" in v for v in report.constraint_violations)


def test_two_packages_exceed_dry_ice_stock_and_are_flagged():
    scenario = get_scenario("limited_dry_ice")  # packages P1 and P3 need 2 kg each
    pack_actions = [a for a in scenario.build_problem().actions if a.action_type == "pack_dry_ice"]
    report = validate_plan(scenario, pack_actions)
    assert report.dry_ice_used_kg == 4
    assert any("Dry ice required 4 kg" in v for v in report.constraint_violations)


def test_every_scenario_builds_a_consistent_problem():
    for scenario in list_scenarios():
        problem = scenario.build_problem()
        for pkg in scenario.packages:
            assert f"at_gate({pkg.package_id})" in problem.initial_state
            assert f"container_open({pkg.package_id})" in problem.initial_state
            assert f"loaded({pkg.package_id})" in problem.goal
        assert len(problem.actions) == len(build_actions(scenario.packages, scenario.constraints))


def test_unknown_scenario_key_raises_helpful_error():
    with pytest.raises(KeyError, match="Valid keys"):
        get_scenario("does_not_exist")
