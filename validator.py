"""
validator.py - independent checker for a finished plan.

The validator does NOT trust the planners. It replays a plan step by step
from the initial state and checks:
    1. every precondition holds when its action runs,
    2. no state is contradictory (e.g. a package in two places at once),
    3. the goal is reached at the end,
    4. the simulated constraints hold (temperature, time budget, dry ice).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from actions import LOCATION_PREDICATES, fact
from constraints import (
    check_dry_ice,
    check_time_budget,
    simulate_temperature_readings,
    temperature_violations,
)
from scenarios import Scenario
from strips import Action, State


@dataclass
class ValidationReport:
    """Outcome of replaying one plan."""

    valid: bool
    goal_achieved: bool
    precondition_failures: List[str] = field(default_factory=list)
    state_inconsistencies: List[str] = field(default_factory=list)
    constraint_violations: List[str] = field(default_factory=list)
    total_duration: int = 0       # minutes (sum of action durations)
    dry_ice_used_kg: int = 0      # kg (sum of dry-ice costs)
    final_state: Optional[State] = None

    @property
    def all_problems(self) -> List[str]:
        """Every problem found, as one flat list of messages."""
        return (self.precondition_failures + self.state_inconsistencies
                + self.constraint_violations)


def check_state_consistency(state: State, package_ids: Sequence[str]) -> List[str]:
    """Return a message for every contradictory fact combination in the state."""
    problems: List[str] = []
    for pid in package_ids:
        locations = [p for p in LOCATION_PREDICATES if fact(p, pid) in state]
        if len(locations) > 1:
            problems.append(f"{pid} is in several places at once: {locations}")
        is_open = fact("container_open", pid) in state
        is_sealed = fact("container_sealed", pid) in state
        is_inspected = fact("container_inspected", pid) in state
        if is_open and is_sealed:
            problems.append(f"{pid} has an open and a sealed container at the same time")
        if is_sealed and not is_inspected:
            problems.append(f"{pid} is sealed without an inspection")
        if fact("loaded", pid) in state and not is_sealed:
            problems.append(f"{pid} is loaded but its container is not sealed")
    return problems


def validate_plan(scenario: Scenario, actions: Sequence[Action]) -> ValidationReport:
    """Replay `actions` on the scenario and report every problem found."""
    problem = scenario.build_problem()
    package_ids = [pkg.package_id for pkg in scenario.packages]

    state = problem.initial_state
    precondition_failures: List[str] = []
    inconsistencies: List[str] = check_state_consistency(state, package_ids)

    for index, action in enumerate(actions, start=1):
        missing = action.missing_preconditions(state)
        if missing:
            precondition_failures.append(
                f"Step {index} {action.name}: missing preconditions {sorted(missing)}")
            break  # the rest of the plan cannot be replayed reliably
        state = action.apply(state)
        for message in check_state_consistency(state, package_ids):
            inconsistencies.append(f"After step {index} ({action.name}): {message}")

    # Constraint checks ---------------------------------------------------
    total_minutes = sum(action.duration for action in actions)
    dry_ice_kg = sum(action.dry_ice_cost for action in actions)

    constraint_violations: List[str] = []
    touched_packages = {action.package_id for action in actions if action.package_id}
    for pkg in scenario.packages:
        if pkg.package_id in touched_packages:
            readings = simulate_temperature_readings(pkg)
            constraint_violations += temperature_violations(pkg, readings)
    constraint_violations += check_time_budget(total_minutes, scenario.constraints)
    constraint_violations += check_dry_ice(dry_ice_kg, scenario.constraints)

    goal_achieved = not precondition_failures and problem.goal_satisfied(state)
    valid = (goal_achieved and not precondition_failures and not inconsistencies
             and not constraint_violations)

    return ValidationReport(
        valid=valid,
        goal_achieved=goal_achieved,
        precondition_failures=precondition_failures,
        state_inconsistencies=inconsistencies,
        constraint_violations=constraint_violations,
        total_duration=total_minutes,
        dry_ice_used_kg=dry_ice_kg,
        final_state=state,
    )
