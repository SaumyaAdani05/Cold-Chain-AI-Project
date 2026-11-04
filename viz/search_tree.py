"""State-space search tree graph builder using Graphviz.

Conforms to PRD.md FR-G4 and ARCHITECTURE.md section 3.6.
"""

from __future__ import annotations

import graphviz


def search_tree_to_dot(
    edges: list[tuple[str, str, str]],
    max_nodes: int = 50,
    title: str = "Search Space Tree",
) -> graphviz.Digraph:
    """Build a Graphviz Digraph from search tree expansion edges.

    Args:
        edges: List of tuples (parent_state_summary, action_label, child_state_summary).
        max_nodes: Maximum nodes to render before truncating.
        title: Title of diagram.

    Returns:
        graphviz.Digraph object.
    """
    dot = graphviz.Digraph(
        name="SearchTree",
        graph_attr={
            "rankdir": "TB",
            "fontname": "Helvetica",
            "label": title,
            "labelloc": "t",
            "fontsize": "12",
        },
        node_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
            "shape": "ellipse",
            "style": "filled",
            "fillcolor": "#f5f5f5",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "8",
            "color": "#757575",
        },
    )

    rendered_nodes = set()
    node_count = 0

    for u, action, v in edges:
        if node_count >= max_nodes:
            dot.node("trunc", "... max nodes reached ...", shape="box", style="dashed")
            dot.edge(u, "trunc")
            break

        if u not in rendered_nodes:
            dot.node(u, u)
            rendered_nodes.add(u)
            node_count += 1

        if v not in rendered_nodes:
            dot.node(v, v)
            rendered_nodes.add(v)
            node_count += 1

        dot.edge(u, v, label=f" {action} ")

    return dot
