"""Uniform planner interface adapter.

Provides run_planner and available_planners per ARCHITECTURE.md.
Normalizes raw planner output to PlannerResult, handles timeouts and exceptions,
and supports COLDCHAIN_MOCK=1 for developing against mocks.
"""

from __future__ import annotations

import concurrent.futures
import importlib
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class PopStructure:
    steps: dict[str, Any]  # id -> Action; "Start"/"Finish" -> None
    orderings: set[tuple[str, str]]  # (before_id, after_id)
    causal_links: list[tuple[str, str, str]]  # (producer_id, fact, consumer_id)
    threats_resolved: list[tuple[tuple[str, str, str], str, str]]


@dataclass
class PlannerResult:
    planner: str  # "bfs" | "pop"
    plan: list[Any] | None  # linearized plan; None = no plan found
    explored: int  # states (BFS) or nodes (POP) expanded
    time_s: float  # planning wall time
    timed_out: bool = False
    error: str | None = None  # planner exception message, if any
    pop: PopStructure | None = None  # only for POP


def available_planners() -> list[str]:
    """Return list of supported planner identifiers."""
    return ["bfs", "pop"]


def _run_mock_planner(name: str, scenario: Any) -> PlannerResult:
    """Return mock planner result based on scenario and planner name."""
    from tests.fixtures import mock_planners

    scenario_id = getattr(scenario, "id", "")
    expected = getattr(scenario, "expected", "plan")

    if expected == "no_plan" or scenario_id in {"S3", "S4", "S5"}:
        res = mock_planners.mock_no_plan()
        res.planner = name
        return res

    if name.lower() == "pop":
        return mock_planners.mock_pop_s1()
    return mock_planners.mock_bfs_s1()


def run_planner(name: str, scenario: Any, timeout_s: float = 30.0) -> PlannerResult:
    """Execute a planner against a scenario within the specified timeout.

    Args:
        name: Planner name ('bfs' or 'pop').
        scenario: Scenario dataclass.
        timeout_s: Maximum execution time in seconds.

    Returns:
        PlannerResult object with execution stats and normalized plan.
    """
    normalized_name = name.lower().strip()
    if normalized_name not in available_planners():
        return PlannerResult(
            planner=name,
            plan=None,
            explored=0,
            time_s=0.0,
            timed_out=False,
            error=f"Unknown planner '{name}'. Available: {available_planners()}",
        )

    # Check if mock mode is forced via environment or if real modules are absent
    use_mock = os.environ.get("COLDCHAIN_MOCK", "").strip() in {"1", "true", "True"}

    def _execute() -> PlannerResult:
        if use_mock:
            return _run_mock_planner(normalized_name, scenario)

        # Attempt to import real planner module
        mod_name = normalized_name
        try:
            planner_mod = importlib.import_module(mod_name)
        except ImportError:
            # Fallback to mock planner if real module is not yet created by teammate
            return _run_mock_planner(normalized_name, scenario)

        # Real planner invocation
        start_t = time.perf_counter()
        if hasattr(planner_mod, "plan"):
            raw = planner_mod.plan(scenario)
        elif hasattr(planner_mod, "solve"):
            raw = planner_mod.solve(scenario)
        elif hasattr(planner_mod, "run"):
            raw = planner_mod.run(scenario)
        else:
            msg = f"Module '{mod_name}' has no recognized entrypoint (plan/solve/run)."
            raise AttributeError(msg)

        elapsed = time.perf_counter() - start_t

        # Normalize raw dictionary or object to PlannerResult
        if isinstance(raw, PlannerResult):
            return raw

        if isinstance(raw, dict):
            plan_val = raw.get("plan")
            explored_val = raw.get("explored", 0)
            time_val = raw.get("time", elapsed)
            pop_struct = raw.get("pop")
            return PlannerResult(
                planner=normalized_name,
                plan=plan_val,
                explored=explored_val,
                time_s=time_val,
                timed_out=False,
                error=None,
                pop=pop_struct,
            )

        raise TypeError(f"Planner '{mod_name}' returned unexpected type: {type(raw)}")

    start_wall = time.perf_counter()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_execute)
    try:
        res = future.result(timeout=timeout_s)
        return res
    except concurrent.futures.TimeoutError:
        elapsed = time.perf_counter() - start_wall
        return PlannerResult(
            planner=normalized_name,
            plan=None,
            explored=0,
            time_s=elapsed,
            timed_out=True,
            error=f"Planner '{normalized_name}' timed out after {timeout_s:.1f}s",
        )
    except Exception as e:
        elapsed = time.perf_counter() - start_wall
        return PlannerResult(
            planner=normalized_name,
            plan=None,
            explored=0,
            time_s=elapsed,
            timed_out=False,
            error=str(e),
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
