"""Visualization package for Cold-Chain plans and causal links.

Exposes builders and safe rendering utilities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import graphviz

from viz.plan_graph import plan_to_dot
from viz.pop_graph import pop_to_dot
from viz.search_tree import search_tree_to_dot

logger = logging.getLogger(__name__)


def export_dot(dot: graphviz.Digraph) -> str:
    """Return the raw DOT source string representation of the graph."""
    return dot.source


def render_png_safe(dot: graphviz.Digraph) -> bytes | None:
    """Attempt to render graphviz Digraph to PNG bytes.

    Gracefully catches missing Graphviz system binary or rendering failures.
    Returns bytes on success, or None on failure.
    """
    try:
        return dot.pipe(format="png")
    except Exception as e:
        logger.warning("Graphviz system binary ('dot') execution failed: %s", e)
        return None


__all__ = [
    "plan_to_dot",
    "pop_to_dot",
    "search_tree_to_dot",
    "export_dot",
    "render_png_safe",
]
