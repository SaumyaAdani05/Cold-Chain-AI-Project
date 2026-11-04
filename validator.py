"""Plan Validation module for the Cold-Chain logistics planning system.

Simulates action sequences against initial states and checks:
- Action preconditions
- Delete and Add effect transitions
- Final goal fact satisfaction
- Dry-ice stock limits
- Total time budget limits
- Ambient temperature exposure limits per package
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AMBIENT = frozenset({"receiving", "loading_dock"})
CONTROLLED = frozenset({"cold_room", "inspection"})


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
    for fact in state:
        if fact.startswith(prefix) and fact.endswith(")"):
            return fact[len(prefix) : -1]
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
                    f"Step {i} ({action.name}) is redundant: "
                    "add effects already hold and nothing deleted."
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
