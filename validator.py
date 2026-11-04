"""Plan Validation module for the Cold-Chain logistics planning system.

Provides:
1. `validate` and `ValidationResult`: Pure simulation engine that strictly validates
   STRIPS action sequences against initial states, checking preconditions, state
   transitions (state - delete) | add, goal satisfaction, cumulative dry-ice stock,
   total time budget, and per-package ambient exposure limits.
2. `validate_plan` and `ValidationReport`: Independent checker for finished scenario plans
   with domain constraint validation (simulated temperature, time budget, dry ice, state
   consistency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

from actions import LOCATION_PREDICATES, fact
from constraints import (
    check_dry_ice,
    check_time_budget,
    simulate_temperature_readings,
    temperature_violations,
)
from scenarios import Scenario
from strips import Action, State

AMBIENT = frozenset({"receiving", "loading_dock"})
CONTROLLED = frozenset({"cold_room", "inspection"})


# =====================================================================
# Saumya's Validation Interface (used by adapter, UI panels, viz)
# =====================================================================


@dataclass(frozen=True)
class Violation:
    step: int | None  # 1-based plan index; None for goal/global violations
    action: str | None  # action name, if step-related
    kind: str  # "PRECONDITION" | "GOAL" | "DRY_ICE" | "TIME" | "EXPOSURE" | "EMPTY_PLAN"
    message: str  # human-readable, specific


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    violations: tuple[Violation, ...]
    warnings: tuple[str, ...]  # e.g. redundant actions (strict mode)
    plan_length: int
    total_time: int
    dry_ice_used: int
    max_exposure: int  # worst per-package exposure reached
    final_state: frozenset[str]


def _extract_pkg(action: Any) -> str:
    """Extract package ID from action.pkg or fallback to action.name."""
    pkg = getattr(action, "pkg", "")
    if pkg:
        return pkg

    name = getattr(action, "name", "")
    if "(" in name:
        inside = name.split("(", 1)[1]
        arg = inside.split(",", 1)[0].split(")", 1)[0].strip()
        return arg
    return ""


def _get_pkg_location(pkg: str, state: frozenset[str] | set[str]) -> str | None:
    """Find current location of package from 'at(pkg,loc)' facts in state."""
    prefix = f"at({pkg},"
    for item in state:
        if item.startswith(prefix) and item.endswith(")"):
            return item[len(prefix) : -1]
    return None


def validate(
    init: frozenset[str],
    goal: frozenset[str],
    plan: list[Any],
    dry_ice_stock: int | None = None,
    time_budget: int | None = None,
    exposure_limit: int | None = None,
    strict: bool = False,
) -> ValidationResult:
    """Validate a plan against initial state, goal, and domain constraints.

    Args:
        init: Initial set of predicate facts.
        goal: Goal set of predicate facts that must hold at the end.
        plan: Ordered list of Action objects to simulate.
        dry_ice_stock: Max dry-ice units allowed. None disables check.
        time_budget: Max cumulative duration allowed. None disables check.
        exposure_limit: Max ambient exposure units per package. None disables check.
        strict: When True, records warnings for redundant actions.

    Returns:
        ValidationResult containing validation status, violations, and metrics.
    """
    if len(plan) == 0:
        if goal.issubset(init):
            return ValidationResult(
                valid=True,
                violations=(),
                warnings=(),
                plan_length=0,
                total_time=0,
                dry_ice_used=0,
                max_exposure=0,
                final_state=frozenset(init),
            )
        return ValidationResult(
            valid=False,
            violations=(
                Violation(
                    step=None,
                    action=None,
                    kind="EMPTY_PLAN",
                    message="Plan is empty but initial state does not satisfy goal.",
                ),
            ),
            warnings=(),
            plan_length=0,
            total_time=0,
            dry_ice_used=0,
            max_exposure=0,
            final_state=frozenset(init),
        )

    current_state = set(init)
    total_time = 0
    dry_ice_used = 0
    exposure: dict[str, int] = {}
    max_exposure = 0

    violations: list[Violation] = []
    warnings: list[str] = []

    reported_time = False
    reported_ice = False
    reported_exposure_pkgs: set[str] = set()

    for i, action in enumerate(plan, 1):
        # 1. Preconditions check
        missing_pre = sorted(action.pre - current_state)
        if missing_pre:
            violations.append(
                Violation(
                    step=i,
                    action=action.name,
                    kind="PRECONDITION",
                    message=f"Step {i} ({action.name}) missing preconditions: {missing_pre}",
                )
            )

        # 2. Strict mode redundancy check
        if strict:
            if action.add.issubset(current_state) and not (action.delete & current_state):
                warnings.append(
                    f"Step {i} ({action.name}) is redundant: add effects already hold and nothing deleted."
                )

        # 3. Ambient exposure check before action applies
        pkg = _extract_pkg(action)
        if pkg:
            loc_before = _get_pkg_location(pkg, current_state)
            if loc_before in AMBIENT:
                exposure[pkg] = exposure.get(pkg, 0) + action.duration
                if exposure[pkg] > max_exposure:
                    max_exposure = exposure[pkg]

                if (
                    exposure_limit is not None
                    and exposure[pkg] > exposure_limit
                    and pkg not in reported_exposure_pkgs
                ):
                    reported_exposure_pkgs.add(pkg)
                    violations.append(
                        Violation(
                            step=i,
                            action=action.name,
                            kind="EXPOSURE",
                            message=(
                                f"Step {i} ({action.name}): package {pkg} exposure "
                                f"({exposure[pkg]}) exceeded limit ({exposure_limit})."
                            ),
                        )
                    )

        # 4. State transition: (state - delete) | add
        current_state = (current_state - action.delete) | action.add

        # 5. Reset exposure if now in controlled location
        if pkg:
            loc_after = _get_pkg_location(pkg, current_state)
            if loc_after in CONTROLLED:
                exposure[pkg] = 0

        # 6. Cumulative resource tracking
        total_time += action.duration
        dry_ice_used += action.dry_ice

        if time_budget is not None and total_time > time_budget and not reported_time:
            reported_time = True
            violations.append(
                Violation(
                    step=i,
                    action=action.name,
                    kind="TIME",
                    message=(
                        f"Step {i} ({action.name}): cumulative time ({total_time}) "
                        f"exceeded budget ({time_budget})."
                    ),
                )
            )

        if dry_ice_stock is not None and dry_ice_used > dry_ice_stock and not reported_ice:
            reported_ice = True
            violations.append(
                Violation(
                    step=i,
                    action=action.name,
                    kind="DRY_ICE",
                    message=(
                        f"Step {i} ({action.name}): cumulative dry ice ({dry_ice_used}) "
                        f"exceeded stock ({dry_ice_stock})."
                    ),
                )
            )

    # 7. Goal check after last step
    final_frozenset = frozenset(current_state)
    missing_goal = sorted(goal - final_frozenset)
    if missing_goal:
        violations.append(
            Violation(
                step=None,
                action=None,
                kind="GOAL",
                message=f"Goal facts not satisfied at end of plan: {missing_goal}",
            )
        )

    # 8. Sort violations: ascending by step, global (step=None) last
    violations.sort(key=lambda v: (1 if v.step is None else 0, v.step or 0))

    return ValidationResult(
        valid=len(violations) == 0,
        violations=tuple(violations),
        warnings=tuple(warnings),
        plan_length=len(plan),
        total_time=total_time,
        dry_ice_used=dry_ice_used,
        max_exposure=max_exposure,
        final_state=final_frozenset,
    )


# =====================================================================
# Samkit's Validation Interface (used by scenarios, comparison, main)
# =====================================================================


@dataclass
class ValidationReport:
    """Outcome of replaying one plan."""

    valid: bool
    goal_achieved: bool
    precondition_failures: List[str] = field(default_factory=list)
    state_inconsistencies: List[str] = field(default_factory=list)
    constraint_violations: List[str] = field(default_factory=list)
    total_duration: int = 0  # minutes (sum of action durations)
    dry_ice_used_kg: int = 0  # kg (sum of dry-ice costs)
    final_state: Optional[State] = None

    @property
    def all_problems(self) -> List[str]:
        """Every problem found, as one flat list of messages."""
        return self.precondition_failures + self.state_inconsistencies + self.constraint_violations


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
                f"Step {index} {action.name}: missing preconditions {sorted(missing)}"
            )
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
    valid = goal_achieved and not precondition_failures and not inconsistencies and not constraint_violations

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
