"""Tests for the partial-order planner: causal links, orderings, threats and resolution."""

from pop import START, find_threats, initial_partial_plan, pop_plan
from scenarios import get_scenario
from validator import validate_plan


def _plan_for(key):
    scenario = get_scenario(key)
    result = pop_plan(scenario.build_problem())
    return scenario, result


def _step_name(plan, step_id):
    return plan.actions[step_id].name if step_id in plan.actions else step_id


def _link_triples(plan):
    return {
        (_step_name(plan, link.producer), link.condition, _step_name(plan, link.consumer))
        for link in plan.links
    }


def _must_precede(plan, before_name, after_name):
    ids = {action.name: sid for sid, action in plan.actions.items()}
    return ids[after_name] in plan.closure()[ids[before_name]]


def test_pop_finds_valid_plan_for_single_frozen_vaccine():
    scenario, result = _plan_for("normal_single_vaccine")
    assert result.success
    assert len(result.plan.step_ids) == 8
    assert validate_plan(scenario, result.plan.linearization()).valid


def test_causal_links_connect_producers_to_consumers():
    _, result = _plan_for("normal_single_vaccine")
    links = _link_triples(result.plan)
    assert ("move_to_cold_room(P1)", "at_cold_room(P1)", "pack_dry_ice(P1)") in links
    assert ("move_to_cold_room(P1)", "at_cold_room(P1)", "inspect_container(P1)") in links
    assert ("pack_dry_ice(P1)", "dry_ice_packed(P1)", "seal_container(P1)") in links
    assert ("inspect_container(P1)", "container_inspected(P1)", "seal_container(P1)") in links
    assert ("START", "container_open(P1)", "seal_container(P1)") in links


def test_ordering_constraints_follow_the_cold_chain_logic():
    _, result = _plan_for("normal_single_vaccine")
    plan = result.plan
    assert _must_precede(plan, "receive_package(P1)", "verify_temperature(P1)")
    assert _must_precede(plan, "verify_temperature(P1)", "move_to_cold_room(P1)")
    assert _must_precede(plan, "inspect_container(P1)", "seal_container(P1)")
    assert _must_precede(plan, "pack_dry_ice(P1)", "seal_container(P1)")
    assert _must_precede(plan, "seal_container(P1)", "move_to_loading_dock(P1)")
    assert _must_precede(plan, "move_to_loading_dock(P1)", "load_pallet(P1)")


def test_pack_dry_ice_and_inspection_are_independent():
    _, result = _plan_for("normal_single_vaccine")
    plan = result.plan
    assert not _must_precede(plan, "pack_dry_ice(P1)", "inspect_container(P1)")
    assert not _must_precede(plan, "inspect_container(P1)", "pack_dry_ice(P1)")
    names = {(plan.actions[a].name, plan.actions[b].name) for a, b in plan.independent_pairs()}
    assert ("pack_dry_ice(P1)", "inspect_container(P1)") in names or (
        "inspect_container(P1)",
        "pack_dry_ice(P1)",
    ) in names


def test_independent_packages_are_not_ordered_against_each_other():
    _, result = _plan_for("mixed_processing_requirements")
    plan = result.plan
    assert not _must_precede(plan, "receive_package(P1)", "receive_package(P3)")
    assert not _must_precede(plan, "receive_package(P3)", "receive_package(P1)")


def test_parallel_makespan_is_shorter_than_sequential_duration():
    scenario, result = _plan_for("mixed_processing_requirements")
    plan = result.plan
    sequential = sum(a.duration for a in plan.actions.values())
    assert plan.critical_path_minutes() < sequential


def test_threat_is_detected_when_seal_could_run_before_pack():
    scenario = get_scenario("normal_single_vaccine")
    problem = scenario.build_problem()
    plan = initial_partial_plan(problem)
    pack = next(a for a in problem.actions if a.name == "pack_dry_ice(P1)")
    seal = next(a for a in problem.actions if a.name == "seal_container(P1)")
    pack_id = plan.add_step(pack)
    seal_id = plan.add_step(seal)
    assert plan.add_link(START, "container_open(P1)", pack_id)
    threats = find_threats(plan)
    assert any(
        link.producer == START and link.consumer == pack_id and threat == seal_id for link, threat in threats
    )


def test_promotion_is_rejected_when_it_would_create_a_cycle():
    scenario = get_scenario("normal_single_vaccine")
    problem = scenario.build_problem()
    plan = initial_partial_plan(problem)
    seal = next(a for a in problem.actions if a.name == "seal_container(P1)")
    seal_id = plan.add_step(seal)
    # START already comes before the seal, so ordering the seal before START is a cycle.
    assert plan.add_ordering(seal_id, START) is False


def test_demotion_removes_the_threat():
    scenario = get_scenario("normal_single_vaccine")
    problem = scenario.build_problem()
    plan = initial_partial_plan(problem)
    pack = next(a for a in problem.actions if a.name == "pack_dry_ice(P1)")
    seal = next(a for a in problem.actions if a.name == "seal_container(P1)")
    pack_id = plan.add_step(pack)
    seal_id = plan.add_step(seal)
    plan.add_link(START, "container_open(P1)", pack_id)
    assert plan.add_ordering(pack_id, seal_id)  # demotion: seal goes after the pack
    assert not any(threat == seal_id for _, threat in find_threats(plan))


def test_linearization_respects_every_ordering_constraint():
    _, result = _plan_for("mixed_processing_requirements")
    plan = result.plan
    position = {sid: i for i, sid in enumerate(plan.linearization_ids())}
    for before, after in plan.orderings:
        assert position[before] < position[after]


def test_pop_reports_no_plan_when_temperature_check_fails():
    _, result = _plan_for("temperature_verification_failure")
    assert not result.success
    assert result.plan is None
    assert "No partially ordered plan exists" in result.message


def test_pop_does_not_enforce_time_or_dry_ice_limits_during_search():
    scenario, result = _plan_for("limited_dry_ice")
    assert result.success  # logically valid ...
    report = validate_plan(scenario, result.plan.linearization())
    assert not report.valid  # ... but the validator rejects the dry-ice shortage
    assert any("Dry ice required" in v for v in report.constraint_violations)


def test_pop_time_budget_violation_is_caught_by_validator():
    scenario, result = _plan_for("restricted_time_budget")
    assert result.success
    report = validate_plan(scenario, result.plan.linearization())
    assert any("exceeds time budget" in v for v in report.constraint_violations)
