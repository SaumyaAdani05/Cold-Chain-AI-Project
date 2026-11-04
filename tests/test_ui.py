"""Unit tests for UI helper logic and scenario configurations."""

from __future__ import annotations

from adapter import PlannerResult
from ui.compare import build_comparison_dataframe
from ui.scenarios import get_all_scenarios
from validator import ValidationResult


def test_scenarios_s1_to_s5_structure():
    """Verify all 5 scenarios (S1-S5) exist with proper domain configurations."""
    scenarios = get_all_scenarios()
    assert set(scenarios.keys()) == {"S1", "S2", "S3", "S4", "S5"}

    # S1
    s1 = scenarios["S1"]
    assert s1.expected == "plan"
    assert s1.dry_ice_stock == 2
    assert s1.time_budget == 40
    assert s1.exposure_limit == 10

    # S2
    s2 = scenarios["S2"]
    assert s2.expected == "plan"
    assert len(s2.actions) == 24  # 8 * 3 packages

    # S3: limited dry ice
    s3 = scenarios["S3"]
    assert s3.expected == "no_plan"
    assert s3.dry_ice_stock == 2

    # S4: restricted budget
    s4 = scenarios["S4"]
    assert s4.expected == "no_plan"
    assert s4.time_budget == 15

    # S5: missing verify_temp
    s5 = scenarios["S5"]
    assert s5.expected == "no_plan"
    assert not any(a.name.startswith("verify_temp") for a in s5.actions)


def test_build_comparison_dataframe():
    """Verify build_comparison_dataframe handles BFS and POP results."""
    bfs_res = PlannerResult(planner="bfs", plan=["act1", "act2"], explored=20, time_s=0.012)
    pop_res = PlannerResult(planner="pop", plan=["act1", "act2"], explored=12, time_s=0.018)

    val_bfs = ValidationResult(
        valid=True,
        violations=(),
        warnings=(),
        plan_length=2,
        total_time=5,
        dry_ice_used=1,
        max_exposure=2,
        final_state=frozenset(),
    )

    df = build_comparison_dataframe(
        results={"bfs": bfs_res, "pop": pop_res},
        val_results={"bfs": val_bfs, "pop": val_bfs},
    )

    assert len(df) == 2
    assert "BFS" in df["Planner"].values
    assert "POP" in df["Planner"].values
    assert "Planning Time (s)" in df.columns
    assert "Explored States/Nodes" in df.columns
