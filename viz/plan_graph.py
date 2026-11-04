"""Linear plan graph generator using Graphviz.

Conforms to ARCHITECTURE.md sections 3.6 & 4, and PRD.md FR-G1, FR-G3, FR-G5.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import graphviz

if TYPE_CHECKING:
    from validator import ValidationResult


PKG_COLORS = {
    "P1": "#e3f2fd",  # light blue
    "P2": "#e8f5e9",  # light green
    "P3": "#fff3e0",  # light orange
    "P4": "#f3e5f5",  # light purple
}


def _extract_pkg_id(action: Any) -> str:
    """Extract package identifier from action."""
    pkg = getattr(action, "pkg", "")
    if pkg:
        return pkg
    name = getattr(action, "name", "")
    if "(" in name:
        inside = name.split("(", 1)[1]
        return inside.split(",", 1)[0].split(")", 1)[0].strip()
    return ""


def _format_action_label(index: int, action: Any, is_violating: bool) -> str:
    """Format action node label with wrapping and violation marker."""
    name = getattr(action, "name", str(action))
    prefix = f"{index}. "
    if is_violating:
        prefix = f"❌ {prefix}"

    dur = getattr(action, "duration", 1)
    ice = getattr(action, "dry_ice", 0)
    meta = f"[{dur}t, {ice}ice]"

    if "(" in name:
        verb, args = name.split("(", 1)
        label = f"{prefix}{verb}\n({args}\n{meta}"
    else:
        label = f"{prefix}{name}\n{meta}"

    return label


def plan_to_dot(
    plan: list[Any],
    result: ValidationResult | None = None,
    title: str = "",
    max_steps: int = 80,
) -> graphviz.Digraph:
    """Construct a Graphviz Digraph for a linear sequence of actions.

    Args:
        plan: Ordered list of Action objects.
        result: Optional ValidationResult to highlight violating steps.
        title: Optional diagram title.
        max_steps: Threshold above which plan is truncated.

    Returns:
        graphviz.Digraph object.
    """
    dot = graphviz.Digraph(
        name="LinearPlan",
        graph_attr={
            "rankdir": "LR",
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
            "color": "#666666",
            "arrowsize": "0.8",
        },
    )

    # Collect violating step numbers
    violating_steps = set()
    if result is not None:
        for v in result.violations:
            if v.step is not None:
                violating_steps.add(v.step)

    # Start Node
    dot.node(
        "start",
        "START",
        shape="ellipse",
        style="filled",
        fillcolor="#e0e0e0",
        color="#212121",
        penwidth="2.0",
    )

    prev_node = "start"

    step_limit = min(len(plan), max_steps)
    for i in range(1, step_limit + 1):
        action = plan[i - 1]
        node_id = f"step_{i}"
        is_violating = i in violating_steps

        label = _format_action_label(i, action, is_violating)
        pkg = _extract_pkg_id(action)
        fill = PKG_COLORS.get(pkg, "#ffffff")

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
                    "fillcolor": fill,
                    "color": "#424242",
                    "penwidth": "1.0",
                }
            )

        dot.node(node_id, **attrs)
        dot.edge(prev_node, node_id)
        prev_node = node_id

    # Large graph truncation node
    if len(plan) > max_steps:
        trunc_id = "truncated"
        more_count = len(plan) - max_steps
        dot.node(
            trunc_id,
            f"... {more_count} more actions ...",
            shape="box",
            style="dashed,filled",
            fillcolor="#fff9c4",
            color="#fbc02d",
        )
        dot.edge(prev_node, trunc_id)
        prev_node = trunc_id

    # Goal Node
    dot.node(
        "goal",
        "GOAL",
        shape="ellipse",
        style="filled",
        fillcolor="#c8e6c9",
        color="#2e7d32",
        penwidth="2.0",
    )
    dot.edge(prev_node, "goal")

    return dot
