"""Mock planners and sample test plans for Cold-Chain development and tests.

Conforms to ARCHITECTURE.md section 5 and DOMAIN.md section 6-7.
"""

from __future__ import annotations

from adapter import PlannerResult, PopStructure
from tests.fixtures.stubs import Action, Scenario


def make_s1_actions() -> list[Action]:
    """Return the 8 canonical actions for Scenario 1 reference plan."""
    return [
        Action(
            name="verify_temp(P1)",
            pre=frozenset({"at(P1,receiving)"}),
            add=frozenset({"temp_ok(P1)"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="move(P1,receiving,cold_room)",
            pre=frozenset({"at(P1,receiving)"}),
            add=frozenset({"at(P1,cold_room)"}),
            delete=frozenset({"at(P1,receiving)"}),
            duration=3,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="pack_dry_ice(P1)",
            pre=frozenset({"at(P1,cold_room)", "temp_ok(P1)", "open(P1)"}),
            add=frozenset({"iced(P1)"}),
            delete=frozenset(),
            duration=4,
            dry_ice=1,
            pkg="P1",
        ),
        Action(
            name="move(P1,cold_room,inspection)",
            pre=frozenset({"at(P1,cold_room)"}),
            add=frozenset({"at(P1,inspection)"}),
            delete=frozenset({"at(P1,cold_room)"}),
            duration=3,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="inspect(P1)",
            pre=frozenset({"at(P1,inspection)", "iced(P1)", "open(P1)"}),
            add=frozenset({"inspected(P1)"}),
            delete=frozenset(),
            duration=3,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="seal(P1)",
            pre=frozenset({"inspected(P1)", "open(P1)"}),
            add=frozenset({"sealed(P1)"}),
            delete=frozenset({"open(P1)"}),
            duration=2,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="move(P1,inspection,loading_dock)",
            pre=frozenset({"at(P1,inspection)"}),
            add=frozenset({"at(P1,loading_dock)"}),
            delete=frozenset({"at(P1,inspection)"}),
            duration=3,
            dry_ice=0,
            pkg="P1",
        ),
        Action(
            name="load(P1)",
            pre=frozenset({"at(P1,loading_dock)", "sealed(P1)"}),
            add=frozenset({"loaded(P1)"}),
            delete=frozenset(),
            duration=2,
            dry_ice=0,
            pkg="P1",
        ),
    ]


def get_scenario_s1() -> Scenario:
    """Return Scenario 1 specification."""
    return Scenario(
        id="S1",
        title="Single vaccine package, normal",
        init=frozenset({"at(P1,receiving)", "open(P1)"}),
        goal=frozenset({"loaded(P1)"}),
        actions=tuple(make_s1_actions()),
        dry_ice_stock=2,
        time_budget=40,
        exposure_limit=10,
        expected="plan",
    )


def mock_bfs_s1() -> PlannerResult:
    """Mock result for BFS planner on Scenario 1."""
    return PlannerResult(
        planner="bfs",
        plan=make_s1_actions(),
        explored=42,
        time_s=0.015,
        timed_out=False,
        error=None,
    )


def mock_pop_s1() -> PlannerResult:
    """Mock result for POP planner on Scenario 1 with Causal Links and Threat Resolution."""
    actions = make_s1_actions()
    step_dict = {
        "Start": None,
        "Finish": None,
        "S1": actions[0],  # verify_temp(P1)
        "S2": actions[1],  # move(P1,receiving,cold_room)
        "S3": actions[2],  # pack_dry_ice(P1)
        "S4": actions[3],  # move(P1,cold_room,inspection)
        "S5": actions[4],  # inspect(P1)
        "S6": actions[5],  # seal(P1)
        "S7": actions[6],  # move(P1,inspection,loading_dock)
        "S8": actions[7],  # load(P1)
    }

    orderings = {
        ("Start", "S1"),
        ("S1", "S3"),
        ("Start", "S2"),
        ("S2", "S3"),
        ("S3", "S4"),
        ("S4", "S5"),
        ("S5", "S6"),
        ("S6", "S7"),
        ("S7", "S8"),
        ("S8", "Finish"),
    }

    causal_links = [
        ("Start", "at(P1,receiving)", "S1"),
        ("S1", "temp_ok(P1)", "S3"),
        ("S2", "at(P1,cold_room)", "S3"),
        ("S3", "iced(P1)", "S5"),
        ("S4", "at(P1,inspection)", "S5"),
        ("S5", "inspected(P1)", "S6"),
        ("S6", "sealed(P1)", "S8"),
        ("S7", "at(P1,loading_dock)", "S8"),
        ("S8", "loaded(P1)", "Finish"),
    ]

    threats_resolved = [
        (("Start", "open(P1)", "S5"), "S6", "demotion"),
    ]

    pop_struct = PopStructure(
        steps=step_dict,
        orderings=orderings,
        causal_links=causal_links,
        threats_resolved=threats_resolved,
    )

    return PlannerResult(
        planner="pop",
        plan=actions,
        explored=18,
        time_s=0.022,
        timed_out=False,
        error=None,
        pop=pop_struct,
    )


def mock_no_plan() -> PlannerResult:
    """Mock planner returning no plan."""
    return PlannerResult(
        planner="bfs",
        plan=None,
        explored=150,
        time_s=0.045,
        timed_out=False,
        error=None,
    )


def mock_timeout() -> PlannerResult:
    """Mock planner timeout."""
    return PlannerResult(
        planner="bfs",
        plan=None,
        explored=9999,
        time_s=30.0,
        timed_out=True,
        error="Planner timed out after 30.0s",
    )


def mock_broken_plans() -> dict[str, list[Action]]:
    """Return dictionary of broken plan variants corresponding to DOMAIN.md section 7."""
    actions = make_s1_actions()
    return {
        # T2: Skip verify_temp (steps 2-8)
        "t2_skip_verify": actions[1:],
        # T3: Seal before inspect (swap steps 5 and 6)
        "t3_seal_before_inspect": [
            actions[0],
            actions[1],
            actions[2],
            actions[3],
            actions[5],  # seal(P1)
            actions[4],  # inspect(P1)
            actions[6],
            actions[7],
        ],
        # T4: Load before seal
        "t4_load_before_seal": [
            actions[0],
            actions[1],
            actions[2],
            actions[3],
            actions[4],
            actions[6],  # move to loading dock
            actions[7],  # load
            actions[5],  # seal
        ],
        # T5: Incomplete plan (drop load)
        "t5_incomplete": actions[:7],
    }
