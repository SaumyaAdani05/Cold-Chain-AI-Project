"""Tests for the breadth-first search planner."""

from bfs import bfs_plan
from scenarios import get_scenario
from validator import validate_plan


def _run(key, **overrides):
    scenario = get_scenario(key)
    limits = scenario.constraints
    kwargs = {"max_duration": limits.max_duration_minutes,
              "max_dry_ice": limits.dry_ice_available_kg}
    kwargs.update(overrides)
    return scenario, bfs_plan(scenario.build_problem(), **kwargs)


def test_bfs_finds_valid_plan_for_single_frozen_vaccine():
    scenario, result = _run("normal_single_vaccine")
    assert result.success
    assert len(result.actions) == 8  # each of the eight operations is needed once
    assert result.actions[0].name == "receive_package(P1)"
    assert result.actions[-1].name == "load_pallet(P1)"
    assert validate_plan(scenario, result.actions).valid


def test_bfs_counts_explored_and_generated_states():
    _, result = _run("normal_single_vaccine")
    assert result.explored_states >= len(result.actions)
    assert result.generated_states >= result.explored_states - 1
    assert result.elapsed_seconds >= 0


def test_bfs_plan_for_multiple_packages_is_valid():
    scenario, result = _run("mixed_processing_requirements")
    assert result.success
    assert len(result.actions) == 8 + 7 + 8  # two frozen packages and one refrigerated
    assert validate_plan(scenario, result.actions).valid


def test_bfs_no_solution_when_temperature_check_fails():
    _, result = _run("temperature_verification_failure")
    assert not result.success
    assert result.actions == []
    assert "exhausted" in result.message
    assert result.explored_states > 0


def test_bfs_no_solution_when_dry_ice_is_insufficient():
    _, result = _run("limited_dry_ice")
    assert not result.success
    assert result.pruned_successors > 0
    assert "rejected by the time budget or dry-ice limit" in result.message


def test_bfs_time_budget_boundary():
    scenario = get_scenario("normal_single_vaccine")
    problem = scenario.build_problem()
    # The plan needs 32 minutes, so 31 must fail and 32 must succeed.
    assert not bfs_plan(problem, max_duration=31).success
    assert bfs_plan(problem, max_duration=32).success


def test_bfs_goal_already_true_returns_empty_plan():
    scenario = get_scenario("normal_single_vaccine")
    problem = scenario.build_problem()
    satisfied = type(problem)(name="trivial", initial_state=problem.goal,
                              goal=problem.goal, actions=problem.actions)
    result = bfs_plan(satisfied)
    assert result.success
    assert result.actions == []


def test_bfs_plan_respects_preconditions_step_by_step():
    scenario, result = _run("refrigerated_only_success")
    problem = scenario.build_problem()
    state = problem.initial_state
    for action in result.actions:
        assert action.is_applicable(state), action.name
        state = action.apply(state)
    assert problem.goal_satisfied(state)


def test_bfs_terminates_when_an_action_can_be_repeated_without_budget():
    # "tick" changes nothing, so repeating it must not create endless new nodes.
    # The goal is unreachable, so the search has to finish on its own.
    from strips import Action, PlanningProblem

    tick = Action(name="tick", preconditions=frozenset(), add_effects=frozenset(),
                  delete_effects=frozenset(), duration=1)
    problem = PlanningProblem(name="loop", initial_state=frozenset(),
                              goal=frozenset({"never"}), actions=(tick,))
    result = bfs_plan(problem)
    assert not result.success
    assert result.explored_states <= 2


def test_bfs_still_finds_shortest_plan_with_repeatable_actions():
    scenario = get_scenario("mixed_processing_requirements")
    limits = scenario.constraints
    result = bfs_plan(scenario.build_problem(), max_duration=limits.max_duration_minutes,
                      max_dry_ice=limits.dry_ice_available_kg)
    assert result.success
    assert len(result.actions) == 23
