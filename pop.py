"""
pop.py - simplified Partial-Order Planning (POP) written from scratch.

Unlike BFS, POP does not build a fixed sequence. It builds a PARTIAL ORDER:
steps are only ordered when the logic requires it. Steps that do not
interfere can run in any order (or in parallel).

The main ideas, in simple terms:
    * PLAN = a set of steps, ordering constraints ("a before b"),
      causal links and a list of OPEN CONDITIONS (preconditions that no
      step has been chosen to provide yet).
    * START is a fake step whose effects are the initial state.
      FINISH is a fake step whose preconditions are the goal.
    * CAUSAL LINK  P --c--> C : step P produces condition c for step C.
      P must come before C.
    * SUPPORT: pick an open condition (C, c), then either reuse an existing
      step that adds c or add a new step that adds c. Add a causal link.
    * THREAT: a step T that DELETES c and could run between P and C.
      Resolve it by
          - PROMOTION: order T before P, or
          - DEMOTION : order T after C.
      If an option would create an ordering cycle, it is not allowed.
    * The search is depth-first with backtracking over these choices.
      A plan is complete when there are no open conditions and no threats.

Simplifications (also explained in the README):
    * Actions are already grounded (no variables to bind).
    * Each library action is used at most once in a plan.
    * Open conditions are chosen with a simple "fewest supporters first" rule.
    * Time and dry-ice limits are NOT used during the search. The validator
      checks them on the final plan instead.
    * The number of explored nodes is capped (max_nodes) for safety.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from strips import Action, PlanningProblem

START = "START"    # fake step: its add effects are the initial state
FINISH = "FINISH"  # fake step: its preconditions are the goal


@dataclass(frozen=True)
class CausalLink:
    """Step `producer` provides `condition` to step `consumer`."""

    producer: str
    condition: str
    consumer: str


# ---------------------------------------------------------------------------
# Small graph helpers used for ordering constraints
# ---------------------------------------------------------------------------

def _adjacency(orderings: Set[Tuple[str, str]]) -> Dict[str, List[str]]:
    """Turn (before, after) pairs into a dictionary of successors."""
    adj: Dict[str, List[str]] = defaultdict(list)
    for before, after in orderings:
        adj[before].append(after)
    return adj


def _reachable(adj: Dict[str, List[str]], start: str) -> Set[str]:
    """All steps that must come after `start` (depth-first walk)."""
    seen: Set[str] = set()
    stack = list(adj.get(start, []))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adj.get(node, []))
    return seen


# ---------------------------------------------------------------------------
# Search node: a partial plan
# ---------------------------------------------------------------------------

class PartialPlan:
    """One node of the POP search tree (a partially built plan)."""

    def __init__(self) -> None:
        self.steps: Dict[str, Action] = {}          # step id -> action
        self.creation_order: List[str] = []         # ids in the order created
        self.orderings: Set[Tuple[str, str]] = set()  # explicit "a before b"
        self.links: List[CausalLink] = []           # causal links
        self.open_conditions: List[Tuple[str, str]] = []  # (consumer, condition)
        self.used_action_names: Set[str] = set()    # actions already in plan
        self.counter = 0                            # used to name new steps

    # -- queries -------------------------------------------------------------

    def reachable_from(self, step_id: str) -> Set[str]:
        """Steps that must run after `step_id` (transitively)."""
        return _reachable(_adjacency(self.orderings), step_id)

    def is_before(self, a: str, b: str) -> bool:
        """True when the plan already forces a to run before b."""
        return b in self.reachable_from(a)

    # -- updates -------------------------------------------------------------

    def add_ordering(self, a: str, b: str) -> bool:
        """
        Add the constraint "a before b".
        Returns False (and changes nothing) when it would create a cycle.
        """
        if a == b or self.is_before(b, a):
            return False
        self.orderings.add((a, b))
        return True

    def add_step(self, action: Action) -> str:
        """Add a new step for `action`. Its preconditions become open conditions."""
        self.counter += 1
        step_id = f"A{self.counter}"
        self.steps[step_id] = action
        self.creation_order.append(step_id)
        self.used_action_names.add(action.name)
        self.add_ordering(START, step_id)
        self.add_ordering(step_id, FINISH)
        for precondition in sorted(action.preconditions):
            self.open_conditions.append((step_id, precondition))
        return step_id

    def add_link(self, producer: str, condition: str, consumer: str) -> bool:
        """Add a causal link and the ordering producer < consumer."""
        if not self.add_ordering(producer, consumer):
            return False
        self.links.append(CausalLink(producer, condition, consumer))
        if (consumer, condition) in self.open_conditions:
            self.open_conditions.remove((consumer, condition))
        return True

    def copy(self) -> "PartialPlan":
        """Independent copy, so backtracking can try another branch."""
        clone = PartialPlan()
        clone.steps = dict(self.steps)
        clone.creation_order = list(self.creation_order)
        clone.orderings = set(self.orderings)
        clone.links = list(self.links)
        clone.open_conditions = list(self.open_conditions)
        clone.used_action_names = set(self.used_action_names)
        clone.counter = self.counter
        return clone

    def to_partial_order_plan(self) -> "PartialOrderPlan":
        """Strip START/FINISH and return the final, readable plan."""
        action_ids = [sid for sid in self.creation_order if sid not in (START, FINISH)]
        actions = {sid: self.steps[sid] for sid in action_ids}
        orderings = {(a, b) for (a, b) in self.orderings if a in actions and b in actions}
        return PartialOrderPlan(step_ids=action_ids, actions=actions,
                                orderings=orderings, links=list(self.links))


def initial_partial_plan(problem: PlanningProblem) -> PartialPlan:
    """The starting plan: START before FINISH, goal facts are open conditions."""
    plan = PartialPlan()
    plan.steps[START] = Action(name=START, preconditions=frozenset(),
                               add_effects=problem.initial_state, delete_effects=frozenset())
    plan.steps[FINISH] = Action(name=FINISH, preconditions=problem.goal,
                                add_effects=frozenset(), delete_effects=frozenset())
    plan.creation_order = [START, FINISH]
    plan.orderings.add((START, FINISH))
    for goal_fact in sorted(problem.goal):
        plan.open_conditions.append((FINISH, goal_fact))
    return plan


def find_threats(plan: PartialPlan) -> List[Tuple[CausalLink, str]]:
    """
    A threat is a step T that deletes the condition of a causal link P -> C,
    and that is not already forced to run before P or after C.
    """
    adj = _adjacency(plan.orderings)
    threats: List[Tuple[CausalLink, str]] = []
    for link in plan.links:
        for step_id in plan.creation_order:
            if step_id in (link.producer, link.consumer):
                continue
            if link.condition not in plan.steps[step_id].delete_effects:
                continue
            forced_before_producer = link.producer in _reachable(adj, step_id)
            forced_after_consumer = step_id in _reachable(adj, link.consumer)
            if forced_before_producer or forced_after_consumer:
                continue
            threats.append((link, step_id))
    return threats


# ---------------------------------------------------------------------------
# The finished plan
# ---------------------------------------------------------------------------

@dataclass
class PartialOrderPlan:
    """A finished partially ordered plan (only real actions, no START/FINISH)."""

    step_ids: List[str]                       # action steps in creation order
    actions: Dict[str, Action]                # step id -> action
    orderings: Set[Tuple[str, str]]           # explicit ordering constraints
    links: List[CausalLink] = field(default_factory=list)  # includes START/FINISH links

    def linearization_ids(self) -> List[str]:
        """
        One valid total order (topological sort). Ties are broken by creation
        order, so the result is deterministic.
        """
        predecessors = {sid: {a for (a, b) in self.orderings if b == sid} for sid in self.step_ids}
        remaining = list(self.step_ids)
        done: Set[str] = set()
        order: List[str] = []
        while remaining:
            ready = [sid for sid in remaining if predecessors[sid] <= done]
            if not ready:
                raise ValueError("ordering constraints contain a cycle")
            chosen = ready[0]
            order.append(chosen)
            done.add(chosen)
            remaining.remove(chosen)
        return order

    def linearization(self) -> List[Action]:
        """The actions of one valid total order, ready for the validator."""
        return [self.actions[sid] for sid in self.linearization_ids()]

    def critical_path_minutes(self) -> int:
        """
        Longest chain of durations through the ordering constraints.
        This is the time a plan would take if independent steps ran in parallel.
        """
        finish: Dict[str, int] = {}
        for sid in self.linearization_ids():
            preds = [a for (a, b) in self.orderings if b == sid]
            earliest_start = max((finish[p] for p in preds), default=0)
            finish[sid] = earliest_start + self.actions[sid].duration
        return max(finish.values(), default=0)

    def closure(self) -> Dict[str, Set[str]]:
        """For each step, the set of steps that must come after it."""
        adj = _adjacency(self.orderings)
        return {sid: _reachable(adj, sid) for sid in self.step_ids}

    def independent_pairs(self) -> List[Tuple[str, str]]:
        """Pairs of steps with no ordering in either direction (free to reorder)."""
        clos = self.closure()
        pairs = []
        for i, a in enumerate(self.step_ids):
            for b in self.step_ids[i + 1:]:
                if b not in clos[a] and a not in clos[b]:
                    pairs.append((a, b))
        return pairs

    def reduced_orderings(self) -> List[Tuple[str, str]]:
        """Ordering constraints without the ones implied by other constraints."""
        clos = self.closure()
        kept = []
        for (a, b) in sorted(self.orderings):
            implied = any(c not in (a, b) and c in clos[a] and b in clos[c]
                          for c in self.step_ids)
            if not implied:
                kept.append((a, b))
        return kept


# ---------------------------------------------------------------------------
# Depth-first search with backtracking
# ---------------------------------------------------------------------------

class _POPSearch:
    """Holds the action library and the search counters."""

    def __init__(self, actions: Tuple[Action, ...], max_nodes: int) -> None:
        self.achievers: Dict[str, List[Action]] = defaultdict(list)
        for action in actions:
            for effect in sorted(action.add_effects):
                self.achievers[effect].append(action)
        self.max_nodes = max_nodes
        self.nodes = 0               # plan refinements explored
        self.threats_resolved = 0    # promotion/demotion choices tried
        self.limit_hit = False

    def solve(self, plan: PartialPlan) -> Optional[PartialPlan]:
        """Return a complete plan reachable from `plan`, or None."""
        if self.limit_hit:
            return None
        self.nodes += 1
        if self.nodes > self.max_nodes:
            self.limit_hit = True
            return None

        threats = find_threats(plan)
        if threats:
            return self._resolve_threat(plan, threats[0])
        if not plan.open_conditions:
            return plan
        return self._support_open_condition(plan)

    def _resolve_threat(self, plan: PartialPlan, threat: Tuple[CausalLink, str]) -> Optional[PartialPlan]:
        link, threat_step = threat
        for option in ("promotion", "demotion"):
            candidate = plan.copy()
            if option == "promotion":
                # Put the threat before the producer.
                ok = candidate.add_ordering(threat_step, link.producer)
            else:
                # Put the threat after the consumer.
                ok = candidate.add_ordering(link.consumer, threat_step)
            if not ok:
                continue  # this option would create a cycle
            self.threats_resolved += 1
            result = self.solve(candidate)
            if result is not None:
                return result
            if self.limit_hit:
                return None
        return None

    def _supporters(self, plan: PartialPlan, consumer: str, condition: str) -> List[Tuple[str, object]]:
        """Ways to provide `condition`: reuse an existing step, or add a new one."""
        options: List[Tuple[str, object]] = []
        for step_id in plan.creation_order:
            step = plan.steps[step_id]
            if step_id == consumer or condition not in step.add_effects:
                continue
            if plan.is_before(consumer, step_id):
                continue  # would create an ordering cycle
            options.append(("existing", step_id))
        for action in self.achievers.get(condition, []):
            if action.name in plan.used_action_names:
                continue
            options.append(("new", action))
        return options

    def _support_open_condition(self, plan: PartialPlan) -> Optional[PartialPlan]:
        options_for = {oc: self._supporters(plan, *oc) for oc in plan.open_conditions}
        # Fail fast: choose the open condition with the fewest supporters.
        chosen = min(plan.open_conditions, key=lambda oc: len(options_for[oc]))
        if not options_for[chosen]:
            return None  # nothing can provide this condition
        consumer, condition = chosen
        for kind, payload in options_for[chosen]:
            candidate = plan.copy()
            if kind == "existing":
                ok = candidate.add_link(str(payload), condition, consumer)
            else:
                new_id = candidate.add_step(payload)  # type: ignore[arg-type]
                ok = candidate.add_link(new_id, condition, consumer)
            if not ok:
                continue
            result = self.solve(candidate)
            if result is not None:
                return result
            if self.limit_hit:
                return None
        return None


@dataclass
class POPResult:
    """What the POP run produced, including counters for comparison."""

    success: bool
    plan: Optional[PartialOrderPlan]
    explored_nodes: int = 0
    threats_resolved: int = 0
    elapsed_seconds: float = 0.0
    message: str = ""


def pop_plan(problem: PlanningProblem, max_nodes: int = 20000) -> POPResult:
    """Build a partially ordered plan for the problem with POP."""
    start_clock = time.perf_counter()
    search = _POPSearch(problem.actions, max_nodes)
    solution = search.solve(initial_partial_plan(problem))
    elapsed = time.perf_counter() - start_clock

    if solution is None:
        if search.limit_hit:
            message = f"Search stopped at the node limit ({max_nodes})."
        else:
            message = ("No partially ordered plan exists: an open condition has no "
                       "achiever, or every choice ended in a dead end.")
        return POPResult(success=False, plan=None, explored_nodes=search.nodes,
                         threats_resolved=search.threats_resolved,
                         elapsed_seconds=elapsed, message=message)

    plan = solution.to_partial_order_plan()
    message = (f"Partially ordered plan with {len(plan.step_ids)} steps, "
               f"{len(plan.links)} causal links and "
               f"{len(plan.reduced_orderings())} ordering constraints.")
    return POPResult(success=True, plan=plan, explored_nodes=search.nodes,
                     threats_resolved=search.threats_resolved,
                     elapsed_seconds=elapsed, message=message)
