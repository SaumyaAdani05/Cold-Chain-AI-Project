"""Tests for the simulated temperature, time and dry-ice constraints."""

import pytest

from constraints import (
    DEFAULT_DURATIONS,
    ColdChainConstraints,
    check_dry_ice,
    check_time_budget,
    simulate_temperature_readings,
    temperature_ok,
    temperature_violations,
)
from scenarios import FRIDGE_P2, FROZEN_P1, WARM_P2

CONSTRAINTS = ColdChainConstraints(max_duration_minutes=32,
                                   dry_ice_available_kg=2, dry_ice_per_package_kg=2)


def test_simulated_readings_are_deterministic():
    assert simulate_temperature_readings(FRIDGE_P2) == simulate_temperature_readings(FRIDGE_P2)


def test_normal_refrigerated_readings_are_inside_range():
    readings = simulate_temperature_readings(FRIDGE_P2)
    assert len(readings) == FRIDGE_P2.reading_count
    assert all(FRIDGE_P2.temp_min_c <= r <= FRIDGE_P2.temp_max_c for r in readings)
    assert temperature_ok(FRIDGE_P2)


def test_frozen_package_is_inside_its_range():
    assert temperature_ok(FROZEN_P1)


def test_warm_package_is_reported_as_violation():
    readings = simulate_temperature_readings(WARM_P2)
    violations = temperature_violations(WARM_P2, readings)
    assert len(violations) == len(readings)
    assert "outside" in violations[0]
    assert not temperature_ok(WARM_P2)


def test_time_budget_exceeded_is_reported():
    violations = check_time_budget(33, CONSTRAINTS)
    assert len(violations) == 1
    assert "exceeds time budget" in violations[0]


def test_time_budget_exactly_equal_is_allowed():
    assert check_time_budget(32, CONSTRAINTS) == []


def test_dry_ice_shortage_is_reported():
    violations = check_dry_ice(4, CONSTRAINTS)
    assert len(violations) == 1
    assert "exceeds available" in violations[0]


def test_dry_ice_exactly_equal_is_allowed():
    assert check_dry_ice(2, CONSTRAINTS) == []


def test_invalid_configuration_is_rejected():
    bad = ColdChainConstraints(max_duration_minutes=-1, dry_ice_available_kg=0,
                               dry_ice_per_package_kg=0)
    with pytest.raises(ValueError):
        bad.validate()


def test_negative_duration_is_rejected():
    bad = ColdChainConstraints(max_duration_minutes=10, dry_ice_available_kg=0,
                               dry_ice_per_package_kg=0,
                               action_durations={**DEFAULT_DURATIONS, "seal_container": -1})
    with pytest.raises(ValueError, match="seal_container"):
        bad.validate()
