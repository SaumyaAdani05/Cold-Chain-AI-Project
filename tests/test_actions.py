"""Tests for the cold-chain action library: preconditions, effects and state consistency."""

import pytest

from actions import (
    build_actions,
    build_goal,
    build_initial_state,
    fact,
    inspect_container,
    load_pallet,
    move_to_cold_room,
    move_to_loading_dock,
    pack_dry_ice,
    receive_package,
    seal_container,
    verify_temperature,
)
from constraints import DEFAULT_DURATIONS, ColdChainConstraints
from scenarios import FRIDGE_P2, FROZEN_P1, WARM_P2
from validator import check_state_consistency

CONSTRAINTS = ColdChainConstraints(max_duration_minutes=100,
                                   dry_ice_available_kg=10, dry_ice_per_package_kg=2)


def test_receive_moves_package_from_gate_to_receiving():
    action = receive_package(FROZEN_P1, CONSTRAINTS)
    assert action.preconditions == {"at_gate(P1)"}
    assert action.add_effects == {"at_receiving(P1)"}
    assert action.delete_effects == {"at_gate(P1)"}


def test_move_to_cold_room_needs_temperature_verified():
    action = move_to_cold_room(FROZEN_P1, CONSTRAINTS)
    assert "temp_verified(P1)" in action.preconditions
    before = frozenset({"at_receiving(P1)"})
    assert not action.is_applicable(before)


def test_apply_adds_and_deletes_effects():
    state = frozenset({"at_receiving(P1)", "temp_verified(P1)"})
    new_state = move_to_cold_room(FROZEN_P1, CONSTRAINTS).apply(state)
    assert new_state == frozenset({"at_cold_room(P1)", "temp_verified(P1)"})


def test_apply_raises_when_precondition_missing():
    with pytest.raises(ValueError, match="not applicable"):
        seal_container(FRIDGE_P2, CONSTRAINTS).apply(frozenset())


def test_cannot_seal_before_inspection():
    seal = seal_container(FRIDGE_P2, CONSTRAINTS)
    open_but_not_inspected = frozenset({"container_open(P2)"})
    inspected = open_but_not_inspected | {"container_inspected(P2)"}
    assert not seal.is_applicable(open_but_not_inspected)
    assert seal.is_applicable(inspected)


def test_frozen_package_cannot_be_sealed_without_dry_ice():
    seal = seal_container(FROZEN_P1, CONSTRAINTS)
    assert "dry_ice_packed(P1)" in seal.preconditions
    inspected_only = frozenset({"container_open(P1)", "container_inspected(P1)"})
    assert not seal.is_applicable(inspected_only)


def test_refrigerated_package_can_be_sealed_without_dry_ice():
    seal = seal_container(FRIDGE_P2, CONSTRAINTS)
    assert "dry_ice_packed(P2)" not in seal.preconditions


def test_dry_ice_cannot_be_packed_into_sealed_container():
    pack = pack_dry_ice(FROZEN_P1, CONSTRAINTS)
    assert "container_open(P1)" in pack.preconditions
    sealed = frozenset({"at_cold_room(P1)", "container_inspected(P1)", "container_sealed(P1)"})
    assert not pack.is_applicable(sealed)


def test_pack_dry_ice_consumes_configured_dry_ice():
    assert pack_dry_ice(FROZEN_P1, CONSTRAINTS).dry_ice_cost == 2
    assert inspect_container(FROZEN_P1, CONSTRAINTS).dry_ice_cost == 0


def test_seal_deletes_open_container_status():
    seal = seal_container(FRIDGE_P2, CONSTRAINTS)
    assert "container_open(P2)" in seal.delete_effects
    assert "container_sealed(P2)" in seal.add_effects


def test_cannot_load_before_reaching_dock():
    load = load_pallet(FRIDGE_P2, CONSTRAINTS)
    assert "at_dock(P2)" in load.preconditions
    at_cold_room = frozenset({"at_cold_room(P2)", "container_sealed(P2)"})
    assert not load.is_applicable(at_cold_room)


def test_move_to_dock_requires_sealed_container():
    move = move_to_loading_dock(FRIDGE_P2, CONSTRAINTS)
    assert not move.is_applicable(frozenset({"at_cold_room(P2)"}))
    assert move.is_applicable(frozenset({"at_cold_room(P2)", "container_sealed(P2)"}))


def test_frozen_package_has_eight_actions_and_refrigerated_has_seven():
    frozen = build_actions([FROZEN_P1], CONSTRAINTS)
    fridge = build_actions([FRIDGE_P2], CONSTRAINTS)
    assert len(frozen) == 8
    assert len(fridge) == 7
    assert "pack_dry_ice(P2)" not in {a.name for a in fridge}


def test_action_types_cover_the_required_operations():
    names = {a.action_type for a in build_actions([FROZEN_P1], CONSTRAINTS)}
    assert names == {
        "receive_package", "verify_temperature", "move_to_cold_room", "pack_dry_ice",
        "inspect_container", "seal_container", "move_to_loading_dock", "load_pallet",
    }


def test_durations_come_from_constraints_and_can_be_changed():
    default_receive = receive_package(FROZEN_P1, CONSTRAINTS).duration
    assert default_receive == DEFAULT_DURATIONS["receive_package"]
    custom = ColdChainConstraints(max_duration_minutes=10, dry_ice_available_kg=0,
                                  dry_ice_per_package_kg=0,
                                  action_durations={**DEFAULT_DURATIONS, "receive_package": 50})
    assert receive_package(FROZEN_P1, custom).duration == 50


def test_initial_state_has_temperature_fact_only_when_readings_in_range():
    good = build_initial_state([FRIDGE_P2])
    bad = build_initial_state([WARM_P2])
    assert fact("temp_in_range", "P2") in good
    assert fact("temp_in_range", "P2") not in bad
    assert fact("at_gate", "P2") in bad


def test_goal_is_every_package_loaded():
    assert build_goal([FROZEN_P1, FRIDGE_P2]) == {"loaded(P1)", "loaded(P2)"}


def test_location_consistency_detects_two_locations():
    problems = check_state_consistency(frozenset({"at_gate(P1)", "at_cold_room(P1)"}), ["P1"])
    assert any("several places" in p for p in problems)


def test_consistency_detects_open_and_sealed_container():
    state = frozenset({"container_open(P1)", "container_sealed(P1)", "container_inspected(P1)"})
    problems = check_state_consistency(state, ["P1"])
    assert any("open and a sealed" in p for p in problems)


def test_consistency_detects_sealing_without_inspection():
    problems = check_state_consistency(frozenset({"container_sealed(P1)"}), ["P1"])
    assert any("without an inspection" in p for p in problems)


def test_consistent_state_has_no_problems():
    state = frozenset({"at_cold_room(P1)", "container_open(P1)", "container_inspected(P1)"})
    assert check_state_consistency(state, ["P1"]) == []


def test_verify_temperature_needs_in_range_fact():
    verify = verify_temperature(WARM_P2, CONSTRAINTS)
    assert "temp_in_range(P2)" in verify.preconditions
    assert not verify.is_applicable(frozenset({"at_receiving(P2)"}))
