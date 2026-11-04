"""
actions.py - the cold-chain operation library (grounded STRIPS actions).

Each package P has its own copy of every operation, e.g. seal_container(P1).

Location model (one location fact per package, always exactly one):
    at_gate -> at_receiving -> at_cold_room -> at_dock -> loaded

Container model (per package):
    container_open -> container_inspected   (inspection adds, does not remove)
    container_open -> container_sealed      (sealing deletes container_open)

Key ordering rules enforced by the preconditions:
    * seal_container needs container_inspected      (no sealing before inspection)
    * pack_dry_ice needs container_open             (no packing into a sealed box)
    * load_pallet needs at_dock                     (no loading before the dock)
    * move_to_cold_room needs temp_verified         (verify temperature first)
"""

from typing import Iterable, List, Tuple

from constraints import ColdChainConstraints, PackageSpec, temperature_ok
from strips import Action, State

# ---- Predicate names (fact builders) ---------------------------------------


def fact(predicate: str, package_id: str) -> str:
    """Build a ground fact such as 'at_cold_room(P1)'."""
    return f"{predicate}({package_id})"


PREDICATES = (
    "at_gate",
    "at_receiving",
    "temp_in_range",
    "temp_verified",
    "at_cold_room",
    "container_open",
    "dry_ice_packed",
    "container_inspected",
    "container_sealed",
    "at_dock",
    "loaded",
)

ACTION_TYPES = (
    "receive_package",
    "verify_temperature",
    "move_to_cold_room",
    "pack_dry_ice",
    "inspect_container",
    "seal_container",
    "move_to_loading_dock",
    "load_pallet",
)

LOCATION_PREDICATES = ("at_gate", "at_receiving", "at_cold_room", "at_dock", "loaded")


# ---- Helper that creates one grounded action -------------------------------


def _make_action(
    action_type: str,
    package: PackageSpec,
    constraints: ColdChainConstraints,
    preconditions: Iterable[str],
    add: Iterable[str],
    delete: Iterable[str],
    dry_ice_cost: int = 0,
) -> Action:
    pid = package.package_id
    return Action(
        name=f"{action_type}({pid})",
        preconditions=frozenset(preconditions),
        add_effects=frozenset(add),
        delete_effects=frozenset(delete),
        duration=constraints.duration_for(action_type),
        dry_ice_cost=dry_ice_cost,
        action_type=action_type,
        package_id=pid,
    )


# ---- The eight cold-chain operations ---------------------------------------


def receive_package(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Package is taken from the gate onto the receiving bay."""
    pid = pkg.package_id
    return _make_action(
        "receive_package",
        pkg,
        c,
        preconditions=[fact("at_gate", pid)],
        add=[fact("at_receiving", pid)],
        delete=[fact("at_gate", pid)],
    )


def verify_temperature(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Check the temperature readings. Only applicable when the readings are in range."""
    pid = pkg.package_id
    return _make_action(
        "verify_temperature",
        pkg,
        c,
        preconditions=[fact("at_receiving", pid), fact("temp_in_range", pid)],
        add=[fact("temp_verified", pid)],
        delete=[],
    )


def move_to_cold_room(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Move the verified package into the cold room."""
    pid = pkg.package_id
    return _make_action(
        "move_to_cold_room",
        pkg,
        c,
        preconditions=[fact("at_receiving", pid), fact("temp_verified", pid)],
        add=[fact("at_cold_room", pid)],
        delete=[fact("at_receiving", pid)],
    )


def pack_dry_ice(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Put dry ice into the still-open container. Consumes dry-ice stock."""
    pid = pkg.package_id
    return _make_action(
        "pack_dry_ice",
        pkg,
        c,
        preconditions=[fact("at_cold_room", pid), fact("container_open", pid)],
        add=[fact("dry_ice_packed", pid)],
        delete=[],
        dry_ice_cost=c.dry_ice_per_package_kg,
    )


def inspect_container(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Inspect the open container. Independent of dry-ice packing."""
    pid = pkg.package_id
    return _make_action(
        "inspect_container",
        pkg,
        c,
        preconditions=[fact("at_cold_room", pid), fact("container_open", pid)],
        add=[fact("container_inspected", pid)],
        delete=[],
    )


def seal_container(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Seal the container. Needs inspection and, for frozen packages, dry ice."""
    pid = pkg.package_id
    preconditions = [fact("container_inspected", pid), fact("container_open", pid)]
    if pkg.needs_dry_ice:
        preconditions.append(fact("dry_ice_packed", pid))
    return _make_action(
        "seal_container",
        pkg,
        c,
        preconditions=preconditions,
        add=[fact("container_sealed", pid)],
        delete=[fact("container_open", pid)],
    )


def move_to_loading_dock(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Move a sealed package from the cold room to the loading dock."""
    pid = pkg.package_id
    return _make_action(
        "move_to_loading_dock",
        pkg,
        c,
        preconditions=[fact("at_cold_room", pid), fact("container_sealed", pid)],
        add=[fact("at_dock", pid)],
        delete=[fact("at_cold_room", pid)],
    )


def load_pallet(pkg: PackageSpec, c: ColdChainConstraints) -> Action:
    """Load the sealed package onto the delivery pallet."""
    pid = pkg.package_id
    return _make_action(
        "load_pallet",
        pkg,
        c,
        preconditions=[fact("at_dock", pid), fact("container_sealed", pid)],
        add=[fact("loaded", pid)],
        delete=[fact("at_dock", pid)],
    )


# ---- Building the whole action library and the initial state ---------------


def actions_for_package(pkg: PackageSpec, c: ColdChainConstraints) -> List[Action]:
    """All grounded actions for one package. Pack-dry-ice exists only if needed."""
    actions = [
        receive_package(pkg, c),
        verify_temperature(pkg, c),
        move_to_cold_room(pkg, c),
    ]
    if pkg.needs_dry_ice:
        actions.append(pack_dry_ice(pkg, c))
    actions += [
        inspect_container(pkg, c),
        seal_container(pkg, c),
        move_to_loading_dock(pkg, c),
        load_pallet(pkg, c),
    ]
    return actions


def build_actions(packages: Iterable[PackageSpec], c: ColdChainConstraints) -> Tuple[Action, ...]:
    """Action library for every package in a scenario."""
    actions: List[Action] = []
    for pkg in packages:
        actions.extend(actions_for_package(pkg, c))
    return tuple(actions)


def build_initial_state(packages: Iterable[PackageSpec]) -> State:
    """
    Initial facts: every package is at the gate with an open container.
    The temperature fact is added only when the simulated readings are in range,
    so a failed temperature check makes verify_temperature impossible.
    """
    facts = set()
    for pkg in packages:
        facts.add(fact("at_gate", pkg.package_id))
        facts.add(fact("container_open", pkg.package_id))
        if temperature_ok(pkg):
            facts.add(fact("temp_in_range", pkg.package_id))
    return frozenset(facts)


def build_goal(packages: Iterable[PackageSpec]) -> State:
    """Goal: every package has been loaded onto the delivery pallet."""
    return frozenset(fact("loaded", pkg.package_id) for pkg in packages)
