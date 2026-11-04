"""Partial-Order Planning (POP) graph generator using Graphviz.

Conforms to ARCHITECTURE.md sections 3.6 & 4, and PRD.md FR-G2.
Renders step nodes, ordering constraints (solid grey), causal links (dashed blue),
and resolved threats (solid red).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import graphviz

if TYPE_CHECKING:
    from adapter import PopStructure
    from validator import ValidationResult


def pop_to_dot(
    pop: PopStructure,
    result: ValidationResult | None = None,
    title: str = "",
) -> graphviz.Digraph:
    """Construct a Graphviz Digraph for a Partial-Order Plan.

    Args:
        pop: PopStructure containing steps, orderings, causal_links, threats_resolved.
        result: Optional ValidationResult to highlight violating steps.
        title: Optional diagram title.

    Returns:
        graphviz.Digraph object.
    """
    dot = graphviz.Digraph(
        name="PopPlan",
        graph_attr={
            "rankdir": "TB",
            "fontname": "Helvetica",
            "bgcolor": "transparent",
            "label": title,
            "labelloc": "t",
            "fontsize": "14",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "10",
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#ffffff",
            "color": "#333333",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
            "arrowsize": "0.8",
        },
    )

    violating_actions = set()
    if result is not None:
        for v in result.violations:
            if v.action:
                violating_actions.add(v.action)

    # 1. Step Nodes
    for step_id, action in pop.steps.items():
        if step_id.lower() == "start":
            dot.node(
                step_id,
                "START",
                shape="ellipse",
                style="filled",
                fillcolor="#e0e0e0",
                color="#212121",
                penwidth="2.0",
            )
        elif step_id.lower() in {"finish", "goal"}:
            dot.node(
                step_id,
                "FINISH",
                shape="ellipse",
                style="filled",
                fillcolor="#c8e6c9",
                color="#2e7d32",
                penwidth="2.0",
            )
        else:
            action_name = getattr(action, "name", str(action)) if action else step_id
            is_violating = action_name in violating_actions

            prefix = "❌ " if is_violating else ""
            if "(" in action_name:
                verb, args = action_name.split("(", 1)
                label = f"{prefix}[{step_id}] {verb}\n({args}"
            else:
                label = f"{prefix}[{step_id}] {action_name}"

            attrs = {"label": label}
            if is_violating:
                attrs.update(
                    {
                        "fillcolor": "#ffebee",
                        "color": "#d32f2f",
                        "penwidth": "2.5",
                    }
                )
            else:
                attrs.update(
                    {
                        "fillcolor": "#f5f5f5",
                        "color": "#424242",
                        "penwidth": "1.0",
                    }
                )

            dot.node(step_id, **attrs)

    # 2. Ordering Constraints (solid grey)
    for u, v in pop.orderings:
        dot.edge(u, v, style="solid", color="#9e9e9e", penwidth="1.2")

    # 3. Causal Links (dashed blue with fact label)
    for producer, fact, consumer in pop.causal_links:
        dot.edge(
            producer,
            consumer,
            label=f" {fact} ",
            style="dashed",
            color="#1976d2",
            fontcolor="#0d47a1",
            penwidth="1.5",
        )

    # 4. Resolved Threats (solid red)
    for (prod, _fact, cons), threat_id, resolution in pop.threats_resolved:
        # Arrow from threat node to consumer (promotion) or producer to threat (demotion)
        target = cons if resolution.lower() == "promotion" else threat_id
        source = threat_id if resolution.lower() == "promotion" else prod
        dot.edge(
            source,
            target,
            label=f" threat: {resolution} ",
            style="solid",
            color="#d32f2f",
            fontcolor="#b71c1c",
            penwidth="1.8",
        )

    return dot
