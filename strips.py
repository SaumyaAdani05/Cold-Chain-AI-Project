"""
strips.py - STRIPS-style representation of a planning problem.

A STRIPS problem is made of:
    * a STATE: a set of true facts (strings such as "at_gate(P1)"),
    * ACTIONS, each with
        - preconditions : facts that must be true before the action,
        - add effects   : facts that become true after the action,
        - delete effects: facts that stop being true after the action,
    * an INITIAL state and a GOAL (a set of facts that must all be true).

The states are plain frozensets of strings, so they can be stored in sets
and dictionaries (needed by the BFS visited-set and by the POP code).
"""

from dataclasses import dataclass
from typing import FrozenSet, Tuple

# A state is simply the set of facts that are currently true.
State = FrozenSet[str]


@dataclass(frozen=True)
class Action:
    """One grounded STRIPS action, e.g. seal_container(P1)."""

    name: str                       # readable name, e.g. "seal_container(P1)"
    preconditions: FrozenSet[str]   # facts required before the action
    add_effects: FrozenSet[str]     # facts that become true
    delete_effects: FrozenSet[str]  # facts that become false
    duration: int = 1               # minutes (simulated)
    dry_ice_cost: int = 0           # kg of dry ice consumed (simulated)
    action_type: str = ""           # e.g. "seal_container"
    package_id: str = ""            # e.g. "P1" (empty if not package specific)

    def is_applicable(self, state: State) -> bool:
        """An action is applicable when all of its preconditions hold."""
        return self.preconditions <= state

    def missing_preconditions(self, state: State) -> FrozenSet[str]:
        """Return the preconditions that are NOT true in the state."""
        return self.preconditions - state

    def apply(self, state: State) -> State:
        """
        Return the successor state: remove the delete effects, then add the
        add effects. Raises ValueError if the action is not applicable.
        """
        if not self.is_applicable(state):
            missing = ", ".join(sorted(self.missing_preconditions(state)))
            raise ValueError(f"{self.name} is not applicable; missing: {missing}")
        return (state - self.delete_effects) | self.add_effects


@dataclass(frozen=True)
class PlanningProblem:
    """A complete STRIPS problem: initial state, goal and available actions."""

    name: str
    initial_state: State
    goal: FrozenSet[str]
    actions: Tuple[Action, ...]

    def goal_satisfied(self, state: State) -> bool:
        """The goal holds when every goal fact is true in the state."""
        return self.goal <= state

    def unmet_goals(self, state: State) -> FrozenSet[str]:
        """Goal facts that are still missing from the state."""
        return self.goal - state


def describe_state(state: State) -> str:
    """Readable, sorted text version of a state (useful for printing)."""
    return ", ".join(sorted(state))
