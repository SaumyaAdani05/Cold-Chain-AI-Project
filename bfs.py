"""
bfs.py - custom forward state-space Breadth-First Search planner.

How it works (in simple terms):
    1. Start from the initial state.
    2. Take the oldest state from the queue (FIFO = breadth-first).
    3. Try every action; keep the ones whose preconditions hold.
    4. Apply each usable action to get a new state (add/delete effects).
    5. If that new state is not dominated by an earlier one (same facts, no
       more time and no more dry ice), store it and queue it, remembering
       which action led there.
    6. Stop when a dequeued state satisfies the goal. Walk the parent links
       backwards to recover the action sequence.

Because the search is breadth-first, the first plan found has the FEWEST
ACTIONS. It does not minimise total time.

Resource limits (time budget and dry ice) are passed in as plain numbers.
A successor that breaks a limit is pruned, so the planner never returns a
plan that is over budget.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from strips import Action, PlanningProblem, State

# A search node is (state, minutes used so far, dry ice used so far).
# Time and dry ice are part of the key so that the parent links stay exact.
NodeKey = Tuple[State, int, int]


def _is_dominated(earlier: List[Tuple[int, int]], minutes: int, ice: int) -> bool:
    """True when some earlier (minutes, ice) pair is no worse in both values."""
    return any(old_minutes <= minutes and old_ice <= ice for old_minutes, old_ice in earlier)


@dataclass
class BFSResult:
    """Everything the BFS run produced, including counters for comparison."""

    success: bool
    actions: List[Action] = field(default_factory=list)  # the plan (in order)
    explored_states: int = 0       # states taken from the queue and expanded
    generated_states: int = 0      # new states added to the queue
    pruned_successors: int = 0     # successors rejected by time/dry-ice limits
    elapsed_seconds: float = 0.0   # wall-clock planning time
    message: str = ""
    final_state: Optional[State] = None

    @property
    def plan_names(self) -> List[str]:
        """Action names of the plan, in execution order."""
        return [action.name for action in self.actions]


def bfs_plan(problem: PlanningProblem,
             max_duration: Optional[int] = None,
             max_dry_ice: Optional[int] = None) -> BFSResult:
    """
    Search for a plan with breadth-first search.

    Args:
        problem: STRIPS problem (initial state, goal, actions).
        max_duration: optional time budget in minutes (None = no limit).
        max_dry_ice: optional dry-ice stock in kg (None = no limit).
    """
    start_clock = time.perf_counter()

    initial_key: NodeKey = (problem.initial_state, 0, 0)
    queue = deque([initial_key])
    # parent[key] = (previous_key, action used) ; the start node has None.
    parent: Dict[NodeKey, Optional[Tuple[NodeKey, Action]]] = {initial_key: None}
    # Dominance memory: for each set of facts, the (minutes, dry ice) pairs
    # already reached. A new node is skipped when an earlier pair is no worse.
    reached: Dict[State, List[Tuple[int, int]]] = {problem.initial_state: [(0, 0)]}

    explored = 0
    generated = 1  # the initial node
    pruned = 0
    goal_key: Optional[NodeKey] = None

    while queue:
        key = queue.popleft()
        explored += 1
        state, minutes_used, ice_used = key

        if problem.goal_satisfied(state):
            goal_key = key
            break

        for action in problem.actions:
            if not action.is_applicable(state):
                continue

            new_minutes = minutes_used + action.duration
            new_ice = ice_used + action.dry_ice_cost

            # Constraint pruning: never enqueue a state that breaks a limit.
            if max_duration is not None and new_minutes > max_duration:
                pruned += 1
                continue
            if max_dry_ice is not None and new_ice > max_dry_ice:
                pruned += 1
                continue

            new_state = action.apply(state)

            # Dominance check. Repeating a no-op action (for example packing
            # dry ice twice) gives the same facts with more time, so it is
            # skipped here. Without this check the search would never end
            # when there is no time budget.
            if _is_dominated(reached.get(new_state, []), new_minutes, new_ice):
                continue
            reached.setdefault(new_state, []).append((new_minutes, new_ice))

            new_key: NodeKey = (new_state, new_minutes, new_ice)
            parent[new_key] = (key, action)
            generated += 1
            queue.append(new_key)

    elapsed = time.perf_counter() - start_clock

    if goal_key is None:
        if pruned > 0:
            message = ("No plan found. The search was exhausted, and "
                       f"{pruned} successor state(s) were rejected by the "
                       "time budget or dry-ice limit.")
        else:
            message = "No plan found. The search was exhausted without reaching the goal."
        return BFSResult(success=False, explored_states=explored,
                         generated_states=generated, pruned_successors=pruned,
                         elapsed_seconds=elapsed, message=message)

    # Walk the parent links backwards to rebuild the action sequence.
    actions_in_reverse: List[Action] = []
    node = goal_key
    while parent[node] is not None:
        previous_key, action = parent[node]
        actions_in_reverse.append(action)
        node = previous_key
    actions_in_reverse.reverse()

    return BFSResult(
        success=True,
        actions=actions_in_reverse,
        explored_states=explored,
        generated_states=generated,
        pruned_successors=pruned,
        elapsed_seconds=elapsed,
        message=f"Plan found with {len(actions_in_reverse)} actions.",
        final_state=goal_key[0],
    )
