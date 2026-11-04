"""
comparison.py - run BFS and POP on the same scenario and compare the results.

All numbers come from real executions of the algorithms. Nothing is typed in
by hand.

IMPORTANT: BFS returns a TOTAL ORDER (one fixed sequence of actions), while
POP returns a PARTIAL ORDER (a set of steps with ordering constraints).
Their metrics are therefore not perfectly comparable:
    * "explored" counts BFS states expanded but POP search nodes refined.
      They measure different things.
    * "sequential duration" adds every action duration. This is the same
      rule for both algorithms and is what the time budget checks.
    * "parallel makespan" (POP only) is the longest chain of ordering
      constraints. It shows how much time independent steps could save,
      but it is informational and is not used for pass/fail.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bfs import bfs_plan
from pop import PartialOrderPlan, pop_plan
from scenarios import Scenario
from strips import Action
from validator import ValidationReport, validate_plan


@dataclass
class AlgorithmRun:
    """One planner run on one scenario, plus its validation result."""

    algorithm: str  # "BFS" or "POP"
    status: str  # "valid", "rejected" or "no_plan"
    message: str  # planner's own explanation
    explored: int  # BFS: states expanded; POP: nodes refined
    elapsed_seconds: float  # wall-clock planning time
    representation: str  # "total order" or "partial order"
    actions: List[Action] = field(default_factory=list)  # sequence checked by validator
    partial_plan: Optional[PartialOrderPlan] = None  # POP only
    validation: Optional[ValidationReport] = None
    pruned_successors: int = 0  # BFS only
    threats_resolved: int = 0  # POP only (counted over the whole search)

    @property
    def success(self) -> bool:
        """True when the planner found a plan (before validation)."""
        return self.status != "no_plan"

    @property
    def goal_achieved(self) -> bool:
        return bool(self.validation and self.validation.goal_achieved)

    @property
    def plan_length(self) -> int:
        return len(self.actions)

    @property
    def sequential_minutes(self) -> int:
        return sum(action.duration for action in self.actions)

    @property
    def makespan_minutes(self) -> Optional[int]:
        """Parallel makespan (POP only); None for BFS."""
        if self.partial_plan is None:
            return None
        return self.partial_plan.critical_path_minutes()

    @property
    def dry_ice_kg(self) -> int:
        return sum(action.dry_ice_cost for action in self.actions)

    @property
    def violations(self) -> List[str]:
        if self.validation is None:
            return []
        return self.validation.all_problems


def _status_for(success: bool, validation: Optional[ValidationReport]) -> str:
    if not success:
        return "no_plan"
    return "valid" if validation and validation.valid else "rejected"


def run_bfs(scenario: Scenario) -> AlgorithmRun:
    """Run the BFS planner with the scenario's time and dry-ice limits."""
    problem = scenario.build_problem()
    limits = scenario.constraints
    result = bfs_plan(
        problem, max_duration=limits.max_duration_minutes, max_dry_ice=limits.dry_ice_available_kg
    )
    validation = validate_plan(scenario, result.actions) if result.success else None
    return AlgorithmRun(
        algorithm="BFS",
        status=_status_for(result.success, validation),
        message=result.message,
        explored=result.explored_states,
        elapsed_seconds=result.elapsed_seconds,
        representation="total order",
        actions=list(result.actions),
        validation=validation,
        pruned_successors=result.pruned_successors,
    )


def run_pop(scenario: Scenario) -> AlgorithmRun:
    """
    Run the POP planner. POP does not use the limits during search, so the
    validator is the place where time and dry-ice violations are caught.
    """
    problem = scenario.build_problem()
    result = pop_plan(problem)
    actions: List[Action] = []
    validation = None
    if result.success and result.plan is not None:
        actions = result.plan.linearization()
        validation = validate_plan(scenario, actions)
    return AlgorithmRun(
        algorithm="POP",
        status=_status_for(result.success, validation),
        message=result.message,
        explored=result.explored_nodes,
        elapsed_seconds=result.elapsed_seconds,
        representation="partial order",
        actions=actions,
        partial_plan=result.plan,
        validation=validation,
        threats_resolved=result.threats_resolved,
    )


def compare_algorithms(scenario: Scenario) -> List[AlgorithmRun]:
    """Run both planners on the same scenario."""
    return [run_bfs(scenario), run_pop(scenario)]


STATUS_LABELS = {
    "valid": "Valid plan",
    "rejected": "Plan rejected by constraints",
    "no_plan": "No plan found",
}


def comparison_rows(runs: List[AlgorithmRun]) -> List[Dict[str, object]]:
    """Table rows (one dict per algorithm) for display in the UI or the CLI."""
    rows = []
    for run in runs:
        rows.append(
            {
                "Algorithm": run.algorithm,
                "Result": STATUS_LABELS[run.status],
                "Goal achieved": "yes" if run.goal_achieved else "no",
                "Plan length (actions)": run.plan_length if run.success else "-",
                "Planning time (ms)": round(run.elapsed_seconds * 1000, 3),
                "Explored (states / nodes)": run.explored,
                "Sequential duration (min)": run.sequential_minutes if run.success else "-",
                "Parallel makespan (min)": run.makespan_minutes if run.makespan_minutes is not None else "-",
                "Dry ice used (kg)": run.dry_ice_kg if run.success else "-",
                "Constraint violations": len(run.violations) if run.validation else "-",
                "Plan representation": run.representation,
            }
        )
    return rows
