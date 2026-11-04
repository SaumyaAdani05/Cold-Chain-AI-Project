"""Unit and regression tests for validator.py.

Includes:
1. Scenario-based integration tests for `validate_plan` and `check_state_consistency`.
2. Specification tests T1-T16 for `validate` against reference scenarios and mock plans.
"""

from __future__ import annotations

import pytest

from actions import build_actions
from bfs import bfs_plan
from scenarios import get_scenario, list_scenarios
from tests.fixtures.mock_planners import (
    get_scenario_s1,
    make_s1_actions,
    mock_broken_plans,
)
from tests.fixtures.stubs import Action
from validator import validate, validate_plan

# =====================================================================
# Scenario-based tests (Samkit)
# =====================================================================


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
    sequence = [
        _action(scenario, n)
        for n in (
            "receive_package(P1)",
            "verify_temperature(P1)",
            "move_to_cold_room(P1)",
            "pack_dry_ice(P1)",
            "seal_container(P1)",
        )
    ]
    report = validate_plan(scenario, sequence)
    assert not report.valid
    assert any("seal_container(P1)" in f and "container_inspected" in f for f in report.precondition_failures)


def test_validator_rejects_loading_before_dock():
    scenario = get_scenario("refrigerated_only_success")
    sequence = [
        _action(scenario, n)
        for n in (
            "receive_package(P2)",
            "verify_temperature(P2)",
            "move_to_cold_room(P2)",
            "inspect_container(P2)",
            "seal_container(P2)",
            "load_pallet(P2)",
        )
    ]
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
    problem_actions = [
        a
        for a in scenario.build_problem().actions
        if a.package_id == "P1"
        and a.action_type in ("receive_package", "verify_temperature", "move_to_cold_room", "pack_dry_ice")
    ]
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


# =====================================================================
# T1-T16 Specification Tests (Saumya)
# =====================================================================


def test_t1_valid_reference_plan():
    """T1: S1 reference plan should be valid with 0 violations and exact metrics."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is True
    assert len(result.violations) == 0
    assert result.plan_length == 8
    assert result.total_time == 22
    assert result.dry_ice_used == 1
    assert result.max_exposure == 5
    assert "loaded(P1)" in result.final_state


def test_t2_skip_verify_temp():
    """T2: Skipping verify_temp causes PRECONDITION violation at pack_dry_ice."""
    s1 = get_scenario_s1()
    broken = mock_broken_plans()["t2_skip_verify"]  # steps 2-8 of reference plan

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=broken,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    # pack_dry_ice is now step 2 of this plan
    pre_violation = next((v for v in result.violations if v.kind == "PRECONDITION"), None)
    assert pre_violation is not None
    assert pre_violation.step == 2
    assert "pack_dry_ice(P1)" in (pre_violation.action or "")
    assert "temp_ok(P1)" in pre_violation.message


def test_t3_seal_before_inspect():
    """T3: Swapping seal and inspect produces exactly 2 PRECONDITION violations."""
    s1 = get_scenario_s1()
    broken = mock_broken_plans()["t3_seal_before_inspect"]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=broken,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    pre_violations = [v for v in result.violations if v.kind == "PRECONDITION"]
    assert len(pre_violations) == 2

    # Step 5 is seal(P1) missing inspected(P1)
    v5 = pre_violations[0]
    assert v5.step == 5
    assert "seal(P1)" in (v5.action or "")
    assert "inspected(P1)" in v5.message

    # Step 6 is inspect(P1) missing open(P1) (seal deleted open)
    v6 = pre_violations[1]
    assert v6.step == 6
    assert "inspect(P1)" in (v6.action or "")
    assert "open(P1)" in v6.message


def test_t4_load_before_seal():
    """T4: Loading before sealing causes PRECONDITION violation for sealed(P1)."""
    s1 = get_scenario_s1()
    broken = mock_broken_plans()["t4_load_before_seal"]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=broken,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    load_v = next((v for v in result.violations if v.step == 7 and "load(P1)" in (v.action or "")), None)
    assert load_v is not None
    assert load_v.kind == "PRECONDITION"
    assert "sealed(P1)" in load_v.message


def test_t5_incomplete_plan():
    """T5: Dropping final load causes GOAL violation."""
    s1 = get_scenario_s1()
    broken = mock_broken_plans()["t5_incomplete"]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=broken,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.kind == "GOAL"
    assert v.step is None
    assert "loaded(P1)" in v.message


def test_t6_empty_plan_fails():
    """T6: Empty plan on S1 produces EMPTY_PLAN violation."""
    s1 = get_scenario_s1()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=[],
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    assert len(result.violations) == 1
    assert result.violations[0].kind == "EMPTY_PLAN"
    assert result.violations[0].step is None


def test_t7_empty_plan_succeeds_when_goal_already_met():
    """T7: Empty plan succeeds when goal is a subset of initial state."""
    init = frozenset({"at(P1,loading_dock)", "loaded(P1)"})
    goal = frozenset({"loaded(P1)"})

    result = validate(init=init, goal=goal, plan=[])

    assert result.valid is True
    assert len(result.violations) == 0
    assert result.plan_length == 0


def test_t8_dry_ice_exceeded():
    """T8: Dry ice stock = 0 triggers DRY_ICE violation at step 3."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=0,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    ice_v = next((v for v in result.violations if v.kind == "DRY_ICE"), None)
    assert ice_v is not None
    assert ice_v.step == 3
    assert "pack_dry_ice(P1)" in (ice_v.action or "")


def test_t9_time_budget_exceeded():
    """T9: Time budget = 15 triggers TIME violation at step 6 (cumulative 17)."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=15,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    time_v = next((v for v in result.violations if v.kind == "TIME"), None)
    assert time_v is not None
    assert time_v.step == 6
    assert "seal(P1)" in (time_v.action or "")


def test_t10_exposure_exceeded():
    """T10: Exposure limit = 4 triggers EXPOSURE violation at step 2 (cumulative 5)."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=4,
    )

    assert result.valid is False
    exp_v = next((v for v in result.violations if v.kind == "EXPOSURE"), None)
    assert exp_v is not None
    assert exp_v.step == 2
    assert "move(P1,receiving,cold_room)" in (exp_v.action or "")


def test_t11_multiple_problems_ordering():
    """T11: T3 broken plan with time_budget=15 yields PRECONDITION x 2 + TIME x 1 sorted by step."""
    s1 = get_scenario_s1()
    broken = mock_broken_plans()["t3_seal_before_inspect"]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=broken,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=15,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is False
    assert len(result.violations) == 3

    steps = [v.step for v in result.violations]
    assert steps == sorted(steps)
    kinds = [v.kind for v in result.violations]
    assert "PRECONDITION" in kinds
    assert "TIME" in kinds


def test_t12_strict_redundancy_warning():
    """T12: Repeated verify_temp produces a warning under strict mode but remains valid."""
    s1 = get_scenario_s1()
    actions = make_s1_actions()
    repeated_plan = [actions[0], actions[0]] + actions[1:]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=repeated_plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget + 10,
        exposure_limit=s1.exposure_limit + 10,
        strict=True,
    )

    assert result.valid is True
    assert len(result.violations) == 0
    assert len(result.warnings) == 1
    assert "redundant" in result.warnings[0].lower()


def test_t13_none_constraints():
    """T13: None for constraint arguments skips checks."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=None,
        time_budget=None,
        exposure_limit=None,
    )

    assert result.valid is True
    assert len(result.violations) == 0


def test_t14_immutability():
    """T14: Initial state, goal state, and plan list remain unmodified."""
    s1 = get_scenario_s1()
    init_copy = frozenset(s1.init)
    goal_copy = frozenset(s1.goal)
    plan = make_s1_actions()
    plan_copy = list(plan)

    validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert s1.init == init_copy
    assert s1.goal == goal_copy
    assert plan == plan_copy


def test_t15_determinism():
    """T15: Two calls with the same inputs return equal ValidationResult instances."""
    s1 = get_scenario_s1()
    plan = make_s1_actions()

    r1 = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )
    r2 = validate(
        init=s1.init,
        goal=s1.goal,
        plan=plan,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert r1 == r2


def test_t16_s2_valid_plan():
    """T16: Multi-package Scenario 2 plan validation."""
    init_s2 = frozenset(
        {
            "at(P1,receiving)",
            "open(P1)",
            "at(P2,cold_room)",
            "temp_ok(P2)",
            "open(P2)",
            "at(P3,inspection)",
            "temp_ok(P3)",
            "iced(P3)",
            "open(P3)",
        }
    )
    goal_s2 = frozenset({"loaded(P1)", "loaded(P2)", "loaded(P3)"})

    # P3 actions (4 steps)
    p3_actions = [
        Action(
            name="inspect(P3)",
            pre=frozenset({"at(P3,inspection)", "iced(P3)", "open(P3)"}),
            add=frozenset({"inspected(P3)"}),
            delete=frozenset(),
            duration=3,
            dry_ice=0,
            pkg="P3",
        ),
        Action(
            name="seal(P3)",
            pre=frozenset({"inspected(P3)", "open(P3)"}),
            add=frozenset({"sealed(P3)"}),
            delete=frozenset({"open(P3)"}),
            duration=2,
            dry_ice=0,
            pkg="P3",
        ),
        Action(
            name="move(P3,inspection,loading_dock)",
            pre=frozenset({"at(P3,inspection)"}),
            add=frozenset({"at(P3,loading_dock)"}),
            delete=frozenset({"at(P3,inspection)"}),
            duration=3,
            dry_ice=0,
            pkg="P3",
        ),
        Action(
            name="load(P3)",
            pre=frozenset({"at(P3,loading_dock)", "sealed(P3)"}),
            add=frozenset({"loaded(P3)"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg="P3",
        ),
    ]

    # P2 actions (6 steps)
    p2_actions = [
        Action(
            name="pack_dry_ice(P2)",
            pre=frozenset({"at(P2,cold_room)", "temp_ok(P2)", "open(P2)"}),
            add=frozenset({"iced(P2)"}),
            delete=frozenset(),
            duration=4,
            dry_ice=1,
            pkg="P2",
        ),
        Action(
            name="move(P2,cold_room,inspection)",
            pre=frozenset({"at(P2,cold_room)"}),
            add=frozenset({"at(P2,inspection)"}),
            delete=frozenset({"at(P2,cold_room)"}),
            duration=3,
            dry_ice=0,
            pkg="P2",
        ),
        Action(
            name="inspect(P2)",
            pre=frozenset({"at(P2,inspection)", "iced(P2)", "open(P2)"}),
            add=frozenset({"inspected(P2)"}),
            delete=frozenset(),
            duration=3,
            dry_ice=0,
            pkg="P2",
        ),
        Action(
            name="seal(P2)",
            pre=frozenset({"inspected(P2)", "open(P2)"}),
            add=frozenset({"sealed(P2)"}),
            delete=frozenset({"open(P2)"}),
            duration=2,
            dry_ice=0,
            pkg="P2",
        ),
        Action(
            name="move(P2,inspection,loading_dock)",
            pre=frozenset({"at(P2,inspection)"}),
            add=frozenset({"at(P2,loading_dock)"}),
            delete=frozenset({"at(P2,inspection)"}),
            duration=3,
            dry_ice=0,
            pkg="P2",
        ),
        Action(
            name="load(P2)",
            pre=frozenset({"at(P2,loading_dock)", "sealed(P2)"}),
            add=frozenset({"loaded(P2)"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg="P2",
        ),
    ]

    # P1 actions (8 steps)
    p1_actions = make_s1_actions()

    s2_plan = p3_actions + p2_actions + p1_actions

    result = validate(
        init=init_s2,
        goal=goal_s2,
        plan=s2_plan,
        dry_ice_stock=3,
        time_budget=60,
        exposure_limit=10,
    )

    assert result.valid is True
    assert len(result.violations) == 0
    assert result.plan_length == 18
    assert result.dry_ice_used == 2
    assert result.total_time == 49
    assert result.max_exposure == 5


def test_t1_8_pkg_fallback_parsing():
    """T1.8: Actions without explicit pkg attribute or with pkg='' derive pkg from action name."""
    s1 = get_scenario_s1()
    actions = make_s1_actions()
    actions_no_pkg = [
        Action(
            name=a.name,
            pre=a.pre,
            add=a.add,
            delete=a.delete,
            duration=a.duration,
            dry_ice=a.dry_ice,
            pkg="",
        )
        for a in actions
    ]

    result = validate(
        init=s1.init,
        goal=s1.goal,
        plan=actions_no_pkg,
        dry_ice_stock=s1.dry_ice_stock,
        time_budget=s1.time_budget,
        exposure_limit=s1.exposure_limit,
    )

    assert result.valid is True
    assert result.max_exposure == 5


def test_extract_pkg_and_location_edge_cases():
    """Verify package extraction when action has no parentheses and location when package absent."""
    from validator import _extract_pkg, _get_pkg_location

    class DummyAction:
        name = "noop"
        pkg = ""

    assert _extract_pkg(DummyAction()) == ""
    assert _get_pkg_location("P99", frozenset({"at(P1,receiving)"})) is None
