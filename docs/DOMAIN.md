# DOMAIN.md — Cold-Chain Planning Domain

Single source of truth for facts, actions, constraints, scenarios, and validator test cases. Defaults marked **(default)** are proposals; confirm with the team before changing.

---

## 1. Domain summary

A simulated pharmaceutical distribution hub. A package (e.g., a vaccine shipment) moves through **receiving → cold room → inspection → loading dock**. It must be temperature-verified, packed with dry ice while its container is open, inspected, sealed, and loaded. A planner must find an ordered action sequence from an **initial state** to a **goal state** under resource and time constraints.

**PEAS**

| | |
|---|---|
| Performance | Valid plan; few unnecessary actions; short planning time; no temperature/time violations; minimal dry ice; goal achieved |
| Environment | Simulated warehouse: receiving, cold-storage, packing/inspection, sealing, loading areas |
| Actuators | verify temperature, move package, pack dry ice, inspect container, seal container, load pallet |
| Sensors | Simulated temperature readings, location (RFID), inspection status, container status, dry-ice quantity, time |

## 2. Representation

- A **fact** is a string `predicate(arg,arg)` with **no spaces**: `at(P1,cold_room)`.
- A **state** is a `frozenset` of facts that are currently true (closed-world assumption: absent = false).
- An **action** has `pre` (facts that must hold), `add` (facts made true), `delete` (facts made false), plus `duration`, `dry_ice`, `pkg`.
- **Application:** `new_state = (state − delete) ∪ add`. Always apply delete first, then add.
- No negative preconditions (pure STRIPS).

### Predicates

| Predicate | Meaning |
|---|---|
| `at(P,L)` | Package P is at location L |
| `temp_ok(P)` | P's temperature has been verified |
| `open(P)` | P's container is open |
| `iced(P)` | Dry ice is packed with P |
| `inspected(P)` | P's container has been inspected |
| `sealed(P)` | P's container is sealed |
| `loaded(P)` | P is loaded onto the vehicle |

### Locations and connectivity (directed)

`receiving → cold_room → inspection → loading_dock`

Moves exist only along these edges (one direction).

## 3. Action schemas (per package `P`)

| Action | Pre | Add | Delete | Duration | Dry ice |
|---|---|---|---|---|---|
| `verify_temp(P)` | at(P,receiving) | temp_ok(P) | — | 2 | 0 |
| `move(P,A,B)` | at(P,A) | at(P,B) | at(P,A) | 3 | 0 |
| `pack_dry_ice(P)` | at(P,cold_room), temp_ok(P), open(P) | iced(P) | — | 4 | 1 |
| `inspect(P)` | at(P,inspection), iced(P), open(P) | inspected(P) | — | 3 | 0 |
| `seal(P)` | inspected(P), open(P) | sealed(P) | open(P) | 2 | 0 |
| `load(P)` | at(P,loading_dock), sealed(P) | loaded(P) | — | 2 | 0 |

Durations are time units **(default)**. `seal` deletes `open`, so anything that needs `open(P)` (pack, inspect) must happen **before** sealing — this is the key ordering threat that POP must resolve.

## 4. Constraint rules (the validator implements exactly these)

### 4.1 Dry ice
`dry_ice_used = Σ action.dry_ice` over the plan. Violation `DRY_ICE` if `dry_ice_used > dry_ice_stock`. Reported once, at the first step where the cumulative total exceeds the stock.

### 4.2 Time budget
Actions run sequentially: `total_time = Σ action.duration`. Violation `TIME` if `total_time > time_budget`. Reported once, at the first step where the cumulative time exceeds the budget.

### 4.3 Temperature exposure (per package)

- `AMBIENT = {receiving, loading_dock}`, `CONTROLLED = {cold_room, inspection}`.
- Each package has an **exposure counter**, initially 0.
- Before each action with package `p`: look up `p`'s location `L` from `at(p,L)` in the current state. If `L ∈ AMBIENT`, add the action's `duration` to `exposure[p]`.
- After applying the action: if `p`'s new location ∈ CONTROLLED, reset `exposure[p] = 0`.
- Violation `EXPOSURE` if `exposure[p] > exposure_limit` at any point. Reported once per package, at the first step where it is exceeded.
- **Simplification:** waiting time while other packages are being processed is **not** counted — only the package's own actions.
- `max_exposure` in the result = the highest exposure value reached by any package.

### 4.4 Preconditions and goal
- `PRECONDITION` violation: `step`, `action`, and the sorted list of missing facts.
- The simulation **continues** after a failed precondition (effects still applied) so all violations are collected. Later violations may be cascades; the message for each is still literal and specific.
- `GOAL` violation: after the last step, goal facts missing (sorted list). `step=None`.
- Empty plan: valid iff goal ⊆ init; otherwise a single `EMPTY_PLAN` violation.

### 4.5 Strict mode (optional)
Warning (not violation) for any action whose `add ⊆ state` and `delete ∩ state = ∅` before it runs (redundant action).

### 4.6 Defaults

| Parameter | Default |
|---|---|
| `dry_ice_stock` | 2 |
| `time_budget` | 40 |
| `exposure_limit` | 10 |

## 5. Validator algorithm (reference)

```
validate(init, goal, plan, stock, budget, limit, strict):
    if plan == []:
        return valid if goal <= init else Violation(EMPTY_PLAN)
    state = set(init); t = 0; ice = 0; exposure = {}; max_exp = 0; violations = []
    for i, a in enumerate(plan, 1):
        missing = a.pre - state
        if missing:  violations += PRECONDITION(i, a.name, sorted(missing))
        p = a.pkg
        if p and location(p, state) in AMBIENT: exposure[p] += a.duration
        if exposure[p] > limit and not yet reported: violations += EXPOSURE(i, ...)
        state = (state - a.delete) | a.add
        if p and location(p, state) in CONTROLLED: exposure[p] = 0
        t += a.duration; ice += a.dry_ice
        if budget is not None and t > budget and not yet reported: violations += TIME(i, ...)
        if stock is not None and ice > stock and not yet reported: violations += DRY_ICE(i, ...)
    if not goal <= state: violations += GOAL(None, sorted(goal - state))
    return ValidationResult(valid = not violations, ...)
```

Order of violations in the output: ascending step; global (`step=None`) last.

## 6. Scenarios

All packages start **open** (`open(P)`) with no other status facts unless stated.

| ID | Title | Init | Goal | Stock / Budget / Limit | Expected |
|---|---|---|---|---|---|
| **S1** | Single vaccine package, normal | `at(P1,receiving)`, `open(P1)` | `loaded(P1)` | 2 / 40 / 10 | **plan** (8 steps, 22 time, 1 ice) |
| **S2** | Three packages, different starts | P1: `at(P1,receiving)`, `open(P1)` · P2: `at(P2,cold_room)`, `temp_ok(P2)`, `open(P2)` · P3: `at(P3,inspection)`, `temp_ok(P3)`, `iced(P3)`, `open(P3)` | `loaded(P1)`, `loaded(P2)`, `loaded(P3)` | 3 / 60 / 10 | **plan** (min 49 time, 2 ice) |
| **S3** | Limited dry ice | P1, P2, P3 all: `at(Pi,receiving)`, `open(Pi)` | all three loaded | **2** / 100 / 10 | **no plan** (needs 3 ice) |
| **S4** | Restricted time budget | same as S1 | `loaded(P1)` | 2 / **15** / 10 | **no plan** (min time is 22) |
| **S5** | Temperature verification unavailable | same as S1, but action set **excludes** `verify_temp(P1)` | `loaded(P1)` | 2 / 40 / 10 | **no plan** (`temp_ok` unreachable) |

### S1 reference plan (used in tests, mocks, and demos)

| # | Action | Duration | Cumulative time | Ice |
|---|---|---|---|---|
| 1 | `verify_temp(P1)` | 2 | 2 | 0 |
| 2 | `move(P1,receiving,cold_room)` | 3 | 5 | 0 |
| 3 | `pack_dry_ice(P1)` | 4 | 9 | 1 |
| 4 | `move(P1,cold_room,inspection)` | 3 | 12 | 1 |
| 5 | `inspect(P1)` | 3 | 15 | 1 |
| 6 | `seal(P1)` | 2 | 17 | 1 |
| 7 | `move(P1,inspection,loading_dock)` | 3 | 20 | 1 |
| 8 | `load(P1)` | 2 | 22 | 1 |

Exposure: steps 1–2 at receiving → 5 (reset on arrival at cold_room); step 8 at loading_dock → 2. `max_exposure = 5`.

## 7. Validator test plan

Use S1 and the reference plan unless stated. Constraint arguments: stock 2, budget 40, limit 10 unless overridden.

| Test | Input | Expected |
|---|---|---|
| T1 valid reference | reference plan | `valid=True`, no violations, time 22, ice 1, max_exposure 5, plan_length 8 |
| T2 skip verify | steps 2–8 only | `PRECONDITION` at plan step 2 (`pack_dry_ice(P1)`), missing `temp_ok(P1)`; `valid=False` |
| T3 seal before inspect | swap steps 5 and 6 | exactly 2 violations: step 5 `seal(P1)` missing `inspected(P1)`; step 6 `inspect(P1)` missing `open(P1)` |
| T4 load before seal | steps 1–5, then `move(...inspection→loading_dock)`, `load(P1)`, `seal(P1)` | 1 violation: step 7 `load(P1)` missing `sealed(P1)` |
| T5 incomplete plan | steps 1–7 (drop `load`) | 1 `GOAL` violation: missing `loaded(P1)` |
| T6 empty plan, S1 | `[]` | `EMPTY_PLAN` violation; `valid=False` |
| T7 empty plan, goal already true | `[]` with init ⊇ goal | `valid=True` |
| T8 dry-ice exceeded | reference plan, `dry_ice_stock=0` | 1 `DRY_ICE` violation at step 3 |
| T9 time exceeded | reference plan, `time_budget=15` | 1 `TIME` violation at step 6 (cumulative 17) |
| T10 exposure exceeded | reference plan, `exposure_limit=4` | 1 `EXPOSURE` violation at step 2 (cumulative 5) |
| T11 multiple problems | T3 plan with `time_budget=15` | PRECONDITION ×2 + TIME ×1, sorted by step |
| T12 strict redundancy | reference plan with `verify_temp(P1)` inserted twice at the start | `valid=True` but 1 warning for the repeated action (strict mode only) |
| T13 `None` constraints | reference plan, all constraint args `None` | `valid=True`; constraint checks skipped |
| T14 immutability | any plan | input `init`, `goal`, `plan` unchanged after call |
| T15 determinism | any plan | two calls return equal results |
| T16 S2 | hand-built valid S2 plan (≥ 49 time) | `valid=True` |

### Viz tests

- V1: `plan_to_dot(reference)` has 8 action nodes + START + GOAL; every consecutive pair is connected.
- V2: `pop_to_dot(mock POP)` contains a dashed edge labelled with each causal-link fact and a red edge for each resolved threat.
- V3: passing a `ValidationResult` with a violation at step 5 outlines node 5 in red.
- V4: output DOT is identical across two calls (determinism).
- V5: builder does not raise when Graphviz binary is missing (only rendering would).

### UI smoke tests (manual checklist)

- U1: S1 + BFS → green ✅, 8-step list, graph visible.
- U2: S3, S4, S5 → amber "No plan found" (no crash, no graph).
- U3: S1 + Both → two columns and a comparison table with 5 metrics.
- U4: change a slider after running → result marked "outdated" until regenerated.
- U5: Manual tab: paste the T3 broken plan → two red violations listed.
- U6: temporarily rename `dot` → install hint and DOT source shown instead of crash.

## 8. Glossary

| Term | Meaning |
|---|---|
| STRIPS | Planning formalism: actions with preconditions, add list, delete list |
| PDDL | Standard text language for describing planning domains/problems |
| Forward state-space search | Search from the initial state, applying applicable actions until the goal holds |
| BFS planner | Forward search that expands states level by level; finds the shortest plan |
| POP | Partial-order planning: builds a plan with only the necessary ordering constraints |
| Causal link `A →f→ B` | Step A achieves fact `f` needed by step B; `f` must stay true between them |
| Threat | A step that could delete `f` between A and B; fixed by *promotion* (after B) or *demotion* (before A) |
| Linearization | A total order consistent with a partial-order plan; what the validator checks |
| Sussman Anomaly | Classic blocks-world problem showing why naive linear planning fails |
