# ARCHITECTURE.md

This file defines module boundaries and the **data contracts**. Contracts are frozen: change them only with the user's approval.

---

## 1. System overview

```
┌────────────┐   Scenario     ┌──────────────┐  PlannerResult  ┌───────────────┐
│ model.py   │──────────────▶ │ adapter.py   │◀────────────────│ bfs.py/pop.py │
│ (scenarios,│  init, goal,   │ (uniform     │   plan, stats   │ [read-only]   │
│  actions)  │  actions, cfg  │  interface)  │                 └───────────────┘
└────────────┘                └──────┬───────┘
                                     │ PlannerResult
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
              ┌────────────┐  ┌─────────────┐  ┌───────────────┐
              │ validator  │  │ viz/ graphs │  │ ui/ + app.py  │
              │ [YOURS]    │  │ [YOURS]     │  │ [YOURS]       │
              └─────┬──────┘  └──────┬──────┘  └───────▲───────┘
                    │ ValidationResult│ Digraph         │
                    └────────────────┴─────────────────┘
```

**Data flow in one run:** UI picks a `Scenario` → adapter calls the planner → `PlannerResult` comes back → validator produces `ValidationResult` → viz builds a `Digraph` (optionally highlighting violations) → UI renders everything.

## 2. Module responsibilities

| Module | Responsibility | Must not |
|---|---|---|
| `validator.py` | Simulate and check a plan; compute metrics | Import Streamlit/graphviz; do I/O; mutate inputs |
| `adapter.py` | Call a planner by name, apply timeout, normalize result to `PlannerResult` | Contain planning logic |
| `viz/*` | Build `graphviz.Digraph` objects | Render/save files; import Streamlit |
| `ui/*`, `app.py` | Layout, widgets, session state, calling adapter/validator/viz | Contain validation or planning logic |

## 3. Data contracts

### 3.1 Action (defined in `model.py`, read-only)

```python
@dataclass(frozen=True)
class Action:
    name: str                # e.g. "move(P1,receiving,cold_room)"
    pre: frozenset[str]
    add: frozenset[str]
    delete: frozenset[str]
    duration: int = 1        # time units
    dry_ice: int = 0         # dry-ice units consumed
    pkg: str = ""            # package id this action concerns, e.g. "P1"   <-- PROPOSED FIELD
```

> `pkg` is needed for per-package exposure tracking (see `DOMAIN.md` §4). If `model.py` does not yet have it, the user must add it (or the validator falls back to parsing the first argument inside `name`; see §6).

### 3.2 Scenario

```python
@dataclass(frozen=True)
class Scenario:
    id: str                       # "S1".."S5"
    title: str
    init: frozenset[str]
    goal: frozenset[str]
    actions: tuple[Action, ...]
    dry_ice_stock: int
    time_budget: int
    exposure_limit: int
    expected: str                 # "plan" | "no_plan"  (used by tests/UI badge)
```

### 3.3 PlannerResult (produced by adapter; wraps BFS/POP output)

```python
@dataclass
class PlannerResult:
    planner: str                         # "bfs" | "pop"
    plan: list[Action] | None            # linearized plan; None = no plan found
    explored: int                        # states (BFS) or nodes (POP) expanded
    time_s: float                        # planning wall time
    timed_out: bool = False
    error: str | None = None             # planner exception message, if any
    pop: "PopStructure | None" = None    # only for POP
```

Raw planner dicts are normalized by the adapter. Expected raw keys: BFS → `plan`, `explored`, `time`. POP → the same plus the structure below.

### 3.4 PopStructure (POP only)

```python
@dataclass
class PopStructure:
    steps: dict[str, Action | None]                 # id -> Action; "Start"/"Finish" -> None
    orderings: set[tuple[str, str]]                 # (before_id, after_id)
    causal_links: list[tuple[str, str, str]]        # (producer_id, fact, consumer_id)
    threats_resolved: list[tuple[tuple[str, str, str], str, str]]
    #                      (link,                       threat_step_id, "promotion"|"demotion")
```

Step ids are unique strings: `"Start"`, `"Finish"`, and `"S1"`, `"S2"`, … (one per action instance).

### 3.5 ValidationResult (produced by `validator.py`)

```python
@dataclass(frozen=True)
class Violation:
    step: int | None         # 1-based plan index; None for goal/global violations
    action: str | None       # action name, if step-related
    kind: str                # "PRECONDITION" | "GOAL" | "DRY_ICE" | "TIME" | "EXPOSURE" | "EMPTY_PLAN"
    message: str             # human-readable, specific

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    violations: tuple[Violation, ...]
    warnings: tuple[str, ...]              # e.g. redundant actions (strict mode)
    plan_length: int
    total_time: int
    dry_ice_used: int
    max_exposure: int                      # worst per-package exposure reached
    final_state: frozenset[str]
```

### 3.6 Function signatures (frozen)

```python
# validator.py
def validate(
    init: frozenset[str],
    goal: frozenset[str],
    plan: list[Action],
    dry_ice_stock: int | None = None,
    time_budget: int | None = None,
    exposure_limit: int | None = None,
    strict: bool = False,
) -> ValidationResult: ...

# adapter.py
def run_planner(name: str, scenario: Scenario, timeout_s: float = 30.0) -> PlannerResult: ...
def available_planners() -> list[str]: ...

# viz/plan_graph.py
def plan_to_dot(plan: list[Action], result: ValidationResult | None = None,
                title: str = "") -> "graphviz.Digraph": ...

# viz/pop_graph.py
def pop_to_dot(pop: PopStructure, result: ValidationResult | None = None,
               title: str = "") -> "graphviz.Digraph": ...

# viz/search_tree.py  (optional)
def search_tree_to_dot(edges: list[tuple[str, str, str]], max_nodes: int = 50) -> "graphviz.Digraph": ...
```

`None` constraint arguments in `validate` mean "do not check that constraint."

## 4. Visual encoding (viz)

| Element | Style |
|---|---|
| Start / Goal node | Rounded, dark outline, label "START" / "GOAL" |
| Action node | Box, label `N. verb(args)`; wrap at `(` |
| Ordering edge | Solid arrow, grey |
| Causal link | Dashed arrow, blue, label = fact |
| Resolved threat | Red solid arrow from threat to constraint target, label "promotion"/"demotion" |
| Violating step | Red thick outline + ❌ in label |
| Package colours (multi-package) | Fixed palette keyed by package id; also in label text (not colour-only) |

Graph direction: `rankdir=LR` for linear plans, `TB` for POP. Always set `graph_attr={"fontname": "Helvetica"}`.

## 5. Mock planners (development & tests)

`tests/fixtures/mock_planners.py` provides:

- `mock_bfs_s1() -> PlannerResult` — the reference S1 plan (8 steps).
- `mock_pop_s1() -> PlannerResult` — same plan plus a hand-built `PopStructure` with ≥ 3 causal links and 1 resolved threat.
- `mock_no_plan() -> PlannerResult` — `plan=None`.
- `mock_broken_plans()` — dict of named invalid plans (see `DOMAIN.md` §7).
- `mock_timeout() -> PlannerResult` — `timed_out=True`.

The adapter has a `use_mocks=True` switch (env var `COLDCHAIN_MOCK=1`) so the UI can be built and demoed before real planners exist.

## 6. Fallbacks and edge cases

- **Missing `pkg` on Action:** derive from the first argument of `name` (text between `(` and the first `,` or `)`). Log a warning once.
- **`plan is None`:** validator is not called; UI shows ⚠️ "No plan found".
- **Planner exception:** adapter returns `PlannerResult(plan=None, error=str(e))`; UI shows red error box.
- **Timeout:** run planner in a subprocess/thread with timeout; return `timed_out=True`.
- **Graphviz binary missing:** catch `graphviz.backend.ExecutableNotFound`; show install hint and the DOT source in a code block.
- **Very large graphs (> 80 nodes):** viz truncates with a "… N more" node and a note.

## 7. Streamlit structure

```
app.py
 ├─ st.set_page_config(layout="wide")
 ├─ sidebar: scenario, planner(s), constraint sliders, [Generate Plan]
 ├─ tab "Planner":
 │    ├─ state tables (init / goal)
 │    ├─ results: single column or two columns (Both)
 │    │    ├─ status badge
 │    │    ├─ numbered plan list
 │    │    ├─ compliance panel
 │    │    └─ graph
 │    └─ comparison table (Both)
 ├─ tab "Manual validation": paste/build plan → validate
 └─ tab "About / Domain": action table, PEAS
```

Session-state keys: `results` (dict planner → PlannerResult), `validations` (dict planner → ValidationResult), `last_inputs` (to detect outdated results).

## 8. Determinism

Always sort sets (`sorted(facts)`) before display or graph generation so output is stable across runs.
