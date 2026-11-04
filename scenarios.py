"""
scenarios.py - synthetic test scenarios (all data is invented for teaching).

Each scenario bundles its own packages, temperature profiles and constraints.
The user selects one in the Streamlit app or on the command line.

Expected outcomes are stated here only so that tests and the UI can label
the scenario. The planners themselves do not read these labels; the results
come from the actual algorithm runs.
"""

from dataclasses import dataclass
from typing import Tuple

from actions import build_actions, build_goal, build_initial_state
from constraints import ColdChainConstraints, PackageSpec
from strips import PlanningProblem


@dataclass
class Scenario:
    """One synthetic logistics case: packages, constraints and the expected result."""

    key: str
    title: str
    description: str
    lesson: str                          # what the scenario demonstrates
    expected_outcome: str                # "success" or "failure"
    packages: Tuple[PackageSpec, ...]
    constraints: ColdChainConstraints

    def build_problem(self) -> PlanningProblem:
        """Turn the scenario into a STRIPS problem (checks the data first)."""
        self.constraints.validate()
        ids = [pkg.package_id for pkg in self.packages]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate package ids in scenario {self.key}")
        return PlanningProblem(
            name=self.title,
            initial_state=build_initial_state(self.packages),
            goal=build_goal(self.packages),
            actions=build_actions(self.packages, self.constraints),
        )


# ---- Package templates ------------------------------------------------------

FROZEN_P1 = PackageSpec("P1", "mRNA vaccine vial (frozen, needs dry ice)",
                        needs_dry_ice=True, temp_min_c=-80.0, temp_max_c=-60.0, base_temp_c=-72.0)
FROZEN_P3 = PackageSpec("P3", "Second frozen vaccine lot (needs dry ice)",
                        needs_dry_ice=True, temp_min_c=-80.0, temp_max_c=-60.0, base_temp_c=-70.0)
FRIDGE_P2 = PackageSpec("P2", "Refrigerated vaccine (2-8 C, no dry ice)",
                        needs_dry_ice=False, temp_min_c=2.0, temp_max_c=8.0, base_temp_c=5.0)
WARM_P2 = PackageSpec("P2", "Refrigerated vaccine that warmed up in transit",
                      needs_dry_ice=False, temp_min_c=2.0, temp_max_c=8.0, base_temp_c=11.0)


SCENARIOS = (
    Scenario(
        key="normal_single_vaccine",
        title="1. Normal transport of one frozen vaccine",
        description="One frozen vaccine package with enough dry ice and time.",
        lesson="The full chain of eight operations, with pack and inspect in any order.",
        expected_outcome="success",
        packages=(FROZEN_P1,),
        constraints=ColdChainConstraints(max_duration_minutes=120,
                                         dry_ice_available_kg=10, dry_ice_per_package_kg=2),
    ),
    Scenario(
        key="mixed_processing_requirements",
        title="2. Three packages with different requirements",
        description="Two frozen packages (dry ice) and one refrigerated package (no dry ice).",
        lesson="Independent packages can be processed in parallel in a partial-order plan.",
        expected_outcome="success",
        packages=(FROZEN_P1, FRIDGE_P2, FROZEN_P3),
        constraints=ColdChainConstraints(max_duration_minutes=240,
                                         dry_ice_available_kg=10, dry_ice_per_package_kg=2),
    ),
    Scenario(
        key="limited_dry_ice",
        title="3. Limited dry-ice stock",
        description="Two frozen packages but only 2 kg of dry ice (2 kg needed per package).",
        lesson="Resource constraints make the goal unreachable within the stock.",
        expected_outcome="failure",
        packages=(FROZEN_P1, FROZEN_P3),
        constraints=ColdChainConstraints(max_duration_minutes=240,
                                         dry_ice_available_kg=2, dry_ice_per_package_kg=2),
    ),
    Scenario(
        key="restricted_time_budget",
        title="4. Restricted transit-time budget",
        description="One frozen package; the sequential process takes 32 min but the budget is 30 min.",
        lesson="The time budget rejects an otherwise logically correct plan.",
        expected_outcome="failure",
        packages=(FROZEN_P1,),
        constraints=ColdChainConstraints(max_duration_minutes=30,
                                         dry_ice_available_kg=10, dry_ice_per_package_kg=2),
    ),
    Scenario(
        key="temperature_verification_failure",
        title="5. Temperature verification failure",
        description="A refrigerated package whose simulated readings (about 11 C) are above the 2-8 C range.",
        lesson="verify_temperature is not applicable, so no safe plan exists.",
        expected_outcome="failure",
        packages=(WARM_P2,),
        constraints=ColdChainConstraints(max_duration_minutes=120,
                                         dry_ice_available_kg=0, dry_ice_per_package_kg=0),
    ),
    Scenario(
        key="refrigerated_only_success",
        title="6. Refrigerated package, no dry ice",
        description="One refrigerated package that stays inside 2-8 C. No dry ice is needed.",
        lesson="Shows a successful plan that skips the pack-dry-ice operation.",
        expected_outcome="success",
        packages=(FRIDGE_P2,),
        constraints=ColdChainConstraints(max_duration_minutes=60,
                                         dry_ice_available_kg=0, dry_ice_per_package_kg=0),
    ),
)


def list_scenarios() -> Tuple[Scenario, ...]:
    """All scenarios in display order."""
    return SCENARIOS


def get_scenario(key: str) -> Scenario:
    """Look a scenario up by its key. Raises KeyError with a helpful message."""
    for scenario in SCENARIOS:
        if scenario.key == key:
            return scenario
    valid = ", ".join(s.key for s in SCENARIOS)
    raise KeyError(f"Unknown scenario '{key}'. Valid keys: {valid}")
