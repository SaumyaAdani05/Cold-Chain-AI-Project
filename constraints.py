"""
constraints.py - configurable, SIMULATED safety / time / resource constraints.

IMPORTANT: every number in this file is a simulated assumption made for
teaching purposes. None of them is a validated pharmaceutical transport
standard, and this project does not certify compliance with any regulation.

The planners never hard-code these values. They receive the numbers from a
Scenario object (see scenarios.py) so that a scenario can be changed without
touching the algorithms.
"""

import random
import zlib
from dataclasses import dataclass, field
from typing import Dict, List

# Default durations (minutes) for each cold-chain operation (simulated).
DEFAULT_DURATIONS: Dict[str, int] = {
    "receive_package": 5,
    "verify_temperature": 3,
    "move_to_cold_room": 4,
    "pack_dry_ice": 6,
    "inspect_container": 4,
    "seal_container": 2,
    "move_to_loading_dock": 3,
    "load_pallet": 5,
}


@dataclass
class ColdChainConstraints:
    """Time budget, dry-ice stock and action durations for one scenario."""

    max_duration_minutes: int        # total time budget for the whole plan
    dry_ice_available_kg: int        # dry ice in stock
    dry_ice_per_package_kg: int      # dry ice used by each package that needs it
    action_durations: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DURATIONS))

    def duration_for(self, action_type: str) -> int:
        """Duration in minutes of one action type."""
        return self.action_durations[action_type]

    def validate(self) -> None:
        """Raise ValueError for impossible configuration values."""
        if self.max_duration_minutes < 0:
            raise ValueError("max_duration_minutes must be >= 0")
        if self.dry_ice_available_kg < 0:
            raise ValueError("dry_ice_available_kg must be >= 0")
        if self.dry_ice_per_package_kg < 0:
            raise ValueError("dry_ice_per_package_kg must be >= 0")
        for action_type, minutes in self.action_durations.items():
            if minutes < 0:
                raise ValueError(f"duration of {action_type} must be >= 0")


@dataclass(frozen=True)
class PackageSpec:
    """One pharmaceutical package and its simulated temperature profile."""

    package_id: str        # e.g. "P1"
    label: str             # human-readable description
    needs_dry_ice: bool    # True for frozen products that need dry ice
    temp_min_c: float      # lowest acceptable temperature (simulated)
    temp_max_c: float      # highest acceptable temperature (simulated)
    base_temp_c: float     # centre of the simulated sensor readings
    reading_count: int = 5 # how many sensor readings are simulated


def simulate_temperature_readings(package: PackageSpec) -> List[float]:
    """
    Simulate sensor readings around base_temp_c.

    The random generator is seeded from the package id, so the same package
    always gives the same readings. This keeps the demo and the tests
    reproducible.
    """
    rng = random.Random(zlib.crc32(package.package_id.encode("utf-8")))
    jitter = 0.3  # +/- degrees of sensor noise
    return [round(package.base_temp_c + rng.uniform(-jitter, jitter), 2)
            for _ in range(package.reading_count)]


def temperature_violations(package: PackageSpec, readings: List[float]) -> List[str]:
    """Return a message for every reading outside the acceptable range."""
    problems = []
    for index, value in enumerate(readings, start=1):
        if value < package.temp_min_c or value > package.temp_max_c:
            problems.append(
                f"{package.package_id} reading {index} = {value} C is outside "
                f"[{package.temp_min_c}, {package.temp_max_c}] C"
            )
    return problems


def temperature_ok(package: PackageSpec) -> bool:
    """True when every simulated reading of the package is in range."""
    readings = simulate_temperature_readings(package)
    return not temperature_violations(package, readings)


def check_time_budget(total_minutes: int, constraints: ColdChainConstraints) -> List[str]:
    """Return a violation message when the plan is longer than the budget."""
    if total_minutes > constraints.max_duration_minutes:
        return [f"Total duration {total_minutes} min exceeds time budget "
                f"{constraints.max_duration_minutes} min"]
    return []


def check_dry_ice(used_kg: int, constraints: ColdChainConstraints) -> List[str]:
    """Return a violation message when the plan needs more dry ice than stocked."""
    if used_kg > constraints.dry_ice_available_kg:
        return [f"Dry ice required {used_kg} kg exceeds available "
                f"{constraints.dry_ice_available_kg} kg"]
    return []
