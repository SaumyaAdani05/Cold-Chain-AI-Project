"""Stand-in dataclasses and contracts for Action and Scenario.

Matches ARCHITECTURE.md sections 3.1 and 3.2.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    name: str  # e.g. "move(P1,receiving,cold_room)"
    pre: frozenset[str]
    add: frozenset[str]
    delete: frozenset[str]
    duration: int = 1  # time units
    dry_ice: int = 0  # dry-ice units consumed
    pkg: str = ""  # package id this action concerns, e.g. "P1"


@dataclass(frozen=True)
class Scenario:
    id: str  # "S1".."S5"
    title: str
    init: frozenset[str]
    goal: frozenset[str]
    actions: tuple[Action, ...]
    dry_ice_stock: int
    time_budget: int
    exposure_limit: int
    expected: str  # "plan" | "no_plan"
