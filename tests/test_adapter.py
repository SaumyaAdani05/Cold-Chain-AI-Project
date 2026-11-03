"""Unit tests for adapter.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from adapter import PlannerResult, available_planners, run_planner
from tests.fixtures.mock_planners import get_scenario_s1
from tests.fixtures.stubs import Scenario


def test_available_planners():
    """Verify available_planners returns ['bfs', 'pop']."""
    planners = available_planners()
    assert "bfs" in planners
    assert "pop" in planners


def test_run_planner_mock_bfs():
    """Verify run_planner returns mock BFS plan for S1."""
    s1 = get_scenario_s1()
    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "1"}):
        res = run_planner("bfs", s1)
        assert res.planner == "bfs"
        assert res.plan is not None
        assert len(res.plan) == 8
        assert res.timed_out is False
        assert res.error is None


def test_run_planner_mock_pop():
    """Verify run_planner returns mock POP result with PopStructure for S1."""
    s1 = get_scenario_s1()
    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "1"}):
        res = run_planner("pop", s1)
        assert res.planner == "pop"
        assert res.plan is not None
        assert res.pop is not None
        assert len(res.pop.causal_links) >= 3
        assert len(res.pop.threats_resolved) >= 1


def test_run_planner_no_plan():
    """Verify run_planner returns plan=None for no_plan expected scenarios."""
    s3 = Scenario(
        id="S3",
        title="Limited dry ice",
        init=frozenset(),
        goal=frozenset(),
        actions=(),
        dry_ice_stock=2,
        time_budget=100,
        exposure_limit=10,
        expected="no_plan",
    )
    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "1"}):
        res = run_planner("bfs", s3)
        assert res.plan is None
        assert res.error is None


def test_run_planner_unknown_planner():
    """Verify run_planner handles invalid planner gracefully."""
    s1 = get_scenario_s1()
    res = run_planner("astar_unknown", s1)
    assert res.plan is None
    assert "Unknown planner" in (res.error or "")


def test_run_planner_timeout():
    """Verify run_planner handles execution timeout."""
    s1 = get_scenario_s1()

    def slow_fn(*args, **kwargs):
        import time

        time.sleep(1.0)
        return {"plan": []}

    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "0"}):
        with patch("importlib.import_module") as mock_import:
            fake_mod = MagicMock()
            fake_mod.plan = slow_fn
            mock_import.return_value = fake_mod

            res = run_planner("bfs", s1, timeout_s=0.05)
            assert res.timed_out is True
            assert "timed out" in (res.error or "").lower()


def test_run_planner_normalization_and_exception():
    """Verify dictionary normalization and exception capture."""
    s1 = get_scenario_s1()
    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "0"}):
        with patch("importlib.import_module") as mock_import:
            fake_mod = MagicMock()
            fake_mod.plan.return_value = {"plan": ["step1"], "explored": 10, "time": 0.5}
            mock_import.return_value = fake_mod

            res = run_planner("bfs", s1)
            assert res.plan == ["step1"]
            assert res.explored == 10
            assert res.time_s == 0.5

            # Test exception raising
            fake_mod.plan.side_effect = RuntimeError("Planner failed internally")
            res_err = run_planner("bfs", s1)
            assert res_err.plan is None
            assert "Planner failed internally" in (res_err.error or "")


def test_run_planner_solve_entrypoint_and_types():
    """Test alternative entrypoints and PlannerResult pass-through."""
    s1 = get_scenario_s1()
    with patch.dict(os.environ, {"COLDCHAIN_MOCK": "0"}):
        with patch("importlib.import_module") as mock_import:
            # 1. solve entrypoint returning PlannerResult
            fake_mod = MagicMock(spec=["solve"])
            dummy_res = PlannerResult(planner="bfs", plan=[], explored=5, time_s=0.1)
            fake_mod.solve.return_value = dummy_res
            mock_import.return_value = fake_mod

            res = run_planner("bfs", s1)
            assert res is dummy_res

            # 2. Unexpected return type
            fake_mod.solve.return_value = 12345
            res_type_err = run_planner("bfs", s1)
            assert "unexpected type" in (res_type_err.error or "").lower()

            # 3. No recognized entrypoint
            fake_mod_no_entry = MagicMock(spec=[])
            mock_import.return_value = fake_mod_no_entry
            res_no_entry = run_planner("bfs", s1)
            assert "no recognized entrypoint" in (res_no_entry.error or "").lower()
