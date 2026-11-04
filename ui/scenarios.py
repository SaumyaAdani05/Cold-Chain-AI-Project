"""Canonical Scenarios S1-S5 for the Cold-Chain planning prototype.

Conforms to DOMAIN.md section 6.
"""

from __future__ import annotations

from tests.fixtures.mock_planners import make_s1_actions
from tests.fixtures.stubs import Action, Scenario


def _make_package_actions(pkg: str) -> list[Action]:
    """Generate all standard actions for a package."""
    return [
        Action(
            name=f"verify_temp({pkg})",
            pre=frozenset({f"at({pkg},receiving)"}),
            add=frozenset({f"temp_ok({pkg})"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"move({pkg},receiving,cold_room)",
            pre=frozenset({f"at({pkg},receiving)"}),
            add=frozenset({f"at({pkg},cold_room)"}),
            delete=frozenset({f"at({pkg},receiving)"}),
            duration=3,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"pack_dry_ice({pkg})",
            pre=frozenset({f"at({pkg},cold_room)", f"temp_ok({pkg})", f"open({pkg})"}),
            add=frozenset({f"iced({pkg})"}),
            delete=frozenset(),
            duration=4,
            dry_ice=1,
            pkg=pkg,
        ),
        Action(
            name=f"move({pkg},cold_room,inspection)",
            pre=frozenset({f"at({pkg},cold_room)"}),
            add=frozenset({f"at({pkg},inspection)"}),
            delete=frozenset({f"at({pkg},cold_room)"}),
            duration=3,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"inspect({pkg})",
            pre=frozenset({f"at({pkg},inspection)", f"iced({pkg})", f"open({pkg})"}),
            add=frozenset({f"inspected({pkg})"}),
            delete=frozenset(),
            duration=3,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"seal({pkg})",
            pre=frozenset({f"inspected({pkg})", f"open({pkg})"}),
            add=frozenset({f"sealed({pkg})"}),
            delete=frozenset({f"open({pkg})"}),
            duration=2,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"move({pkg},inspection,loading_dock)",
            pre=frozenset({f"at({pkg},inspection)"}),
            add=frozenset({f"at({pkg},loading_dock)"}),
            delete=frozenset({f"at({pkg},inspection)"}),
            duration=3,
            dry_ice=0,
            pkg=pkg,
        ),
        Action(
            name=f"load({pkg})",
            pre=frozenset({f"at({pkg},loading_dock)", f"sealed({pkg})"}),
            add=frozenset({f"loaded({pkg})"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg=pkg,
        ),
    ]


def get_all_scenarios() -> dict[str, Scenario]:
    """Return dictionary of canonical scenarios S1 to S5."""
    s1_acts = make_s1_actions()
    p1_acts = _make_package_actions("P1")
    p2_acts = _make_package_actions("P2")
    p3_acts = _make_package_actions("P3")

    s1 = Scenario(
        id="S1",
        title="Single vaccine package, normal",
        init=frozenset({"at(P1,receiving)", "open(P1)"}),
        goal=frozenset({"loaded(P1)"}),
        actions=tuple(s1_acts),
        dry_ice_stock=2,
        time_budget=40,
        exposure_limit=10,
        expected="plan",
    )

    s2 = Scenario(
        id="S2",
        title="Three packages, different start states",
        init=frozenset(
            {
                "at(P1,receiving)",
                "open(P1)",
                "at(P2,cold_room)",
                "temp_ok(P2)",
                "open(P2)",
                "at(P3,inspection)",
                "temp_ok(P3)",
                "iced(P3)",
                "open(P3)",
            }
        ),
        goal=frozenset({"loaded(P1)", "loaded(P2)", "loaded(P3)"}),
        actions=tuple(p1_acts + p2_acts + p3_acts),
        dry_ice_stock=3,
        time_budget=60,
        exposure_limit=10,
        expected="plan",
    )

    s3 = Scenario(
        id="S3",
        title="Limited dry ice (2 units for 3 packages)",
        init=frozenset(
            {
                "at(P1,receiving)",
                "open(P1)",
                "at(P2,receiving)",
                "open(P2)",
                "at(P3,receiving)",
                "open(P3)",
            }
        ),
        goal=frozenset({"loaded(P1)", "loaded(P2)", "loaded(P3)"}),
        actions=tuple(p1_acts + p2_acts + p3_acts),
        dry_ice_stock=2,
        time_budget=100,
        exposure_limit=10,
        expected="no_plan",
    )

    s4 = Scenario(
        id="S4",
        title="Restricted time budget (15 units)",
        init=frozenset({"at(P1,receiving)", "open(P1)"}),
        goal=frozenset({"loaded(P1)"}),
        actions=tuple(s1_acts),
        dry_ice_stock=2,
        time_budget=15,
        exposure_limit=10,
        expected="no_plan",
    )

    # S5: temperature verification excluded
    s5_actions = [a for a in s1_acts if not a.name.startswith("verify_temp")]
    s5 = Scenario(
        id="S5",
        title="Temperature verification unavailable",
        init=frozenset({"at(P1,receiving)", "open(P1)"}),
        goal=frozenset({"loaded(P1)"}),
        actions=tuple(s5_actions),
        dry_ice_stock=2,
        time_budget=40,
        exposure_limit=10,
        expected="no_plan",
    )

    return {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5}
