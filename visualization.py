"""
visualization.py - Graphviz (DOT) diagrams for plans, states and POP structure.

The functions return `graphviz.Digraph` objects. The Streamlit app shows them
with st.graphviz_chart(dot.source), which renders them in the browser, so the
Graphviz program does not need to be installed for the app to work.
"""

from typing import List, Sequence

import graphviz

from pop import FINISH, START, CausalLink, PartialOrderPlan
from strips import Action, PlanningProblem, State

_NODE_STYLE = {"shape": "box", "style": "rounded,filled", "fillcolor": "#EAF2FB",
               "fontname": "Helvetica", "fontsize": "11"}
_TERMINAL_STYLE = {"shape": "ellipse", "style": "filled", "fillcolor": "#E8F8F0",
                   "fontname": "Helvetica", "fontsize": "11"}
_GOAL_STYLE = {"shape": "ellipse", "style": "filled", "fillcolor": "#FDEBD0",
               "fontname": "Helvetica", "fontsize": "11"}
_LINK_COLOURS = ["#1F618D", "#7D3C98", "#117A65", "#B9770E", "#943126", "#2E4053"]


def _digraph(name: str, rankdir: str = "TB") -> graphviz.Digraph:
    return graphviz.Digraph(name, graph_attr={"rankdir": rankdir, "fontname": "Helvetica"},
                            edge_attr={"fontname": "Helvetica", "fontsize": "10"})


def _short_list(items: Sequence[str], limit: int = 4) -> str:
    """Show at most `limit` facts, then '...' (keeps node labels readable)."""
    shown = list(items[:limit])
    if len(items) > limit:
        shown.append("...")
    return "\\n".join(shown) if shown else "(none)"


def action_sequence_graph(actions: Sequence[Action]) -> graphviz.Digraph:
    """A BFS plan (total order) drawn as a chain of numbered operations."""
    dot = _digraph("sequence", rankdir="LR")
    dot.node("init", "Initial state", **_TERMINAL_STYLE)
    previous = "init"
    for index, action in enumerate(actions, start=1):
        node = f"a{index}"
        dot.node(node, f"{index}. {action.name}\\n{action.duration} min", **_NODE_STYLE)
        dot.edge(previous, node)
        previous = node
    dot.node("goal", "Goal reached", **_GOAL_STYLE)
    dot.edge(previous, "goal")
    return dot


def state_transition_graph(problem: PlanningProblem, actions: Sequence[Action]) -> graphviz.Digraph:
    """Each node is a state. Labels list the facts added (+) and deleted (-)."""
    dot = _digraph("transitions", rankdir="TB")
    state: State = problem.initial_state
    dot.node("S0", f"S0 (initial)\\n{len(state)} facts", **_TERMINAL_STYLE)
    for index, action in enumerate(actions, start=1):
        new_state = action.apply(state)
        added = sorted(new_state - state)
        deleted = sorted(state - new_state)
        label = f"S{index}\\n+ {_short_list(added, 2)}\\n- {_short_list(deleted, 2)}"
        dot.node(f"S{index}", label, **_NODE_STYLE)
        dot.edge(f"S{index - 1}", f"S{index}", label=action.name)
        state = new_state
    return dot


def dependency_graph(actions: Sequence[Action]) -> graphviz.Digraph:
    """
    Which earlier action provides each precondition of a later action.
    The provider is the most recent earlier action that adds the fact.
    """
    dot = _digraph("dependencies", rankdir="LR")
    dot.node("init", "Initial state", **_TERMINAL_STYLE)
    for index, action in enumerate(actions):
        dot.node(f"a{index}", action.name, **_NODE_STYLE)
    for index, action in enumerate(actions):
        for condition in sorted(action.preconditions):
            provider = "init"
            for earlier in range(index - 1, -1, -1):
                if condition in actions[earlier].add_effects:
                    provider = f"a{earlier}"
                    break
            dot.edge(provider, f"a{index}", label=condition, color="#7F8C8D")
    return dot


def causal_link_graph(plan: PartialOrderPlan) -> graphviz.Digraph:
    """POP causal links: each edge says 'producer provides condition to consumer'."""
    dot = _digraph("causal_links", rankdir="LR")
    dot.node("init", "Initial state", **_TERMINAL_STYLE)
    dot.node("goal", "Goal", **_GOAL_STYLE)
    for sid in plan.step_ids:
        dot.node(sid, f"{sid}: {plan.actions[sid].name}", **_NODE_STYLE)
    colour_of: dict = {}
    for link in plan.links:
        colour = colour_of.setdefault(link.condition,
                                      _LINK_COLOURS[len(colour_of) % len(_LINK_COLOURS)])
        source = "init" if link.producer == START else link.producer
        target = "goal" if link.consumer == FINISH else link.consumer
        dot.edge(source, target, label=link.condition, color=colour, fontcolor=colour)
    return dot


def ordering_constraint_graph(plan: PartialOrderPlan) -> graphviz.Digraph:
    """POP ordering constraints (transitive reduction). Steps with no path between them are free."""
    dot = _digraph("ordering", rankdir="TB")
    for sid in plan.step_ids:
        dot.node(sid, f"{sid}: {plan.actions[sid].name}", **_NODE_STYLE)
    for before, after in plan.reduced_orderings():
        dot.edge(before, after, style="dashed", color="#34495E", arrowhead="normal")
    # Show the steps that have no ordering with each other as a legend.
    free = plan.independent_pairs()
    label = (f"{len(plan.reduced_orderings())} ordering constraints; "
             f"{len(free)} unordered step pairs (free to run in either order)")
    dot.attr(label=label, labelloc="t", fontname="Helvetica", fontsize="12")
    return dot


def linearization_note(plan: PartialOrderPlan) -> List[str]:
    """One valid execution order, written as a list of step names."""
    return [f"{sid}: {plan.actions[sid].name}" for sid in plan.linearization_ids()]
