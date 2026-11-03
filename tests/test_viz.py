"""Unit tests for the visualization module viz/.

Tests V1-V5 from DOMAIN.md section 7 and ARCHITECTURE.md.
"""

from __future__ import annotations

from tests.fixtures.mock_planners import make_s1_actions, mock_pop_s1
from tests.fixtures.stubs import Action
from validator import ValidationResult, Violation
from viz import export_dot, plan_to_dot, pop_to_dot, render_png_safe, search_tree_to_dot


def test_v1_plan_to_dot_nodes_and_edges():
    """V1: plan_to_dot produces START, 8 actions, GOAL and connects consecutive nodes."""
    plan = make_s1_actions()
    dot = plan_to_dot(plan, title="S1 Plan")
    source = dot.source

    assert "start" in source
    assert "goal" in source
    for i in range(1, 9):
        assert f"step_{i}" in source

    # Sequential edges
    assert "start -> step_1" in source
    assert "step_8 -> goal" in source
    assert "rankdir=LR" in source


def test_v2_pop_to_dot_causal_links_and_threats():
    """V2: pop_to_dot contains dashed blue causal links and solid red threat edges."""
    pop_res = mock_pop_s1()
    assert pop_res.pop is not None

    dot = pop_to_dot(pop_res.pop, title="S1 POP Graph")
    source = dot.source

    # Causal links style and facts
    assert 'style="dashed"' in source or "style=dashed" in source
    assert "#1976d2" in source
    assert "temp_ok(P1)" in source
    assert "iced(P1)" in source

    # Resolved threats
    assert "#d32f2f" in source
    assert "threat: demotion" in source


def test_v3_violation_highlighting():
    """V3: Supplying ValidationResult with step violation adds red outline and marker."""
    plan = make_s1_actions()
    dummy_result = ValidationResult(
        valid=False,
        violations=(
            Violation(
                step=5,
                action="inspect(P1)",
                kind="PRECONDITION",
                message="Missing open(P1)",
            ),
        ),
        warnings=(),
        plan_length=8,
        total_time=22,
        dry_ice_used=1,
        max_exposure=5,
        final_state=frozenset(),
    )

    dot = plan_to_dot(plan, result=dummy_result)
    source = dot.source

    # Step 5 must be styled with violation red color
    assert "#d32f2f" in source
    assert "❌ 5. inspect" in source


def test_v4_determinism():
    """V4: Calling plan_to_dot and pop_to_dot twice produces identical DOT source."""
    plan = make_s1_actions()
    dot1 = plan_to_dot(plan)
    dot2 = plan_to_dot(plan)
    assert export_dot(dot1) == export_dot(dot2)

    pop_res = mock_pop_s1()
    assert pop_res.pop is not None
    pdot1 = pop_to_dot(pop_res.pop)
    pdot2 = pop_to_dot(pop_res.pop)
    assert export_dot(pdot1) == export_dot(pdot2)


def test_v5_safe_rendering_when_dot_missing():
    """V5: Creating digraph does not invoke dot; render_png_safe handles missing binary."""
    plan = make_s1_actions()
    dot = plan_to_dot(plan)

    # Builder succeeds without binary
    assert dot is not None
    source = export_dot(dot)
    assert len(source) > 50

    # render_png_safe returns either bytes (if dot is installed) or None (if missing)
    png_bytes = render_png_safe(dot)
    assert png_bytes is None or isinstance(png_bytes, bytes)


def test_plan_truncation_for_large_plans():
    """Verify large plans (>80 steps) have a truncation indicator node."""
    huge_plan = [
        Action(f"step_{i}(P1)", frozenset(), frozenset(), frozenset(), 1, 0, "P1")
        for i in range(1, 101)
    ]
    dot = plan_to_dot(huge_plan, max_steps=80)
    source = dot.source

    assert "truncated" in source
    assert "20 more actions" in source


def test_search_tree_to_dot():
    """Verify search tree graph construction."""
    edges = [
        ("s0", "verify", "s1"),
        ("s1", "move", "s2"),
    ]
    dot = search_tree_to_dot(edges)
    source = dot.source
    assert "s0" in source
    assert "s2" in source
    assert "verify" in source


def test_viz_edge_cases():
    """Cover edge cases in plan_graph, pop_graph, and search_tree."""
    # 1. Action with no parens in plan_to_dot
    a_simple = Action("simple_action", frozenset(), frozenset(), frozenset(), 1, 0, "")
    dot_simple = plan_to_dot([a_simple])
    assert "simple_action" in dot_simple.source

    # 2. POP with FINISH, promotion threat, and violating action
    from adapter import PopStructure

    pop_struct = PopStructure(
        steps={
            "Start": None,
            "Finish": None,
            "S1": Action("inspect(P1)", frozenset(), frozenset(), frozenset(), 1, 0, "P1"),
        },
        orderings={("Start", "S1"), ("S1", "Finish")},
        causal_links=[("Start", "open(P1)", "S1")],
        threats_resolved=[(("Start", "open(P1)", "S1"), "S2", "promotion")],
    )

    dummy_res = ValidationResult(
        valid=False,
        violations=(Violation(step=1, action="inspect(P1)", kind="PRECONDITION", message="err"),),
        warnings=(),
        plan_length=1,
        total_time=1,
        dry_ice_used=0,
        max_exposure=0,
        final_state=frozenset(),
    )
    pop_dot = pop_to_dot(pop_struct, result=dummy_res)
    assert "FINISH" in pop_dot.source
    assert "threat: promotion" in pop_dot.source
    assert "❌ " in pop_dot.source

    # 3. Search tree truncation
    st_edges = [(f"node_{i}", "act", f"node_{i + 1}") for i in range(10)]
    st_dot = search_tree_to_dot(st_edges, max_nodes=3)
    assert "max nodes reached" in st_dot.source
