# Automated Cold-Chain Logistics Planning for Perishable Pharmaceuticals Using Classical AI

A college-level classical AI project. It plans the sequence of operations that moves
temperature-sensitive pharmaceutical packages (for example, vaccines) from a warehouse
gate onto a delivery vehicle. Two planners are written from scratch in Python:

* a **breadth-first search** (BFS) over STRIPS states, which returns a total order, and
* a simplified **partial-order planner** (POP), which returns causal links and ordering
  constraints.

A separate validator replays every plan and checks simulated temperature, time and dry-ice
constraints. A Streamlit interface and a command-line runner use the same code.

> **Important:** every temperature range, duration, dry-ice amount and time budget in this
> project is a **simulated assumption for teaching**. None of them is a validated
> pharmaceutical transport standard, and the project does not certify compliance with any
> regulation.

---

## 1. Project introduction

Cold-chain logistics is the controlled movement of perishable goods between temperature
limits. Vaccines and other biologics are a typical example: if a package leaves its
range, it may have to be discarded. A plan therefore has to respect an order of operations
(for example, a container must be inspected before it is sealed) and resource limits
(for example, a fixed amount of dry ice).

This project treats cold-chain preparation as a **classical planning problem**. The
planner receives an initial state, a goal, and a set of actions with preconditions and
effects. It searches for a valid plan. No machine learning is used.

## 2. Problem definition

Given a set of packages, each with a simulated temperature profile, find a sequence (or a
partially ordered set) of the eight operations below so that every package is loaded onto
the delivery pallet, while:

* every precondition holds when its operation runs,
* every simulated temperature reading stays inside the package's acceptable range,
* the total duration does not exceed the time budget, and
* the dry-ice used does not exceed the dry-ice stock.

The eight operations are: receive package, verify temperature, move to cold room, pack dry
ice, inspect container, seal container, move to loading dock, load pallet.

## 3. Project objectives

1. Represent the cold-chain domain in STRIPS form (state, actions, preconditions, add and
   delete effects), with a matching PDDL domain and problem file.
2. Implement a custom forward BFS planner that returns a plan, explored-state counts,
   planning time and a "no plan" result when appropriate.
3. Implement a simplified POP planner with open conditions, causal links, ordering
   constraints, threat detection, and promotion/demotion.
4. Model temperature, time and dry-ice constraints as configurable simulated data.
5. Provide at least five synthetic scenarios, both successful and unsuccessful.
6. Provide a Streamlit interface and a command-line runner.
7. Compare BFS and POP using metrics measured from real executions.
8. Test the implementation with automated tests.

## 4. Classical AI explanation

*Classical* AI planning works on symbolic, fully specified problems. The world is described
as a set of true facts. An action can run only when its preconditions are true, and it
changes the world by deleting some facts and adding others. Search finds a path from the
initial state to a goal state. Nothing is learned from data; every step is derived from the
model, which makes the result explainable and easy to check.

## 5. STRIPS representation

A state is a set of facts such as `at_gate(P1)` or `container_sealed(P1)`. Each grounded
action has three parts. For example, `seal_container(P1)` is:

| Part | Content |
|---|---|
| Preconditions | `container_inspected(P1)`, `container_open(P1)`, `dry_ice_packed(P1)` (frozen packages only) |
| Add effects | `container_sealed(P1)` |
| Delete effects | `container_open(P1)` |
| Duration | 2 min (configurable) |
| Dry ice | 0 kg |

Applying an action gives the successor state `(state - delete) ∪ add`. The location of a
package is always exactly one fact (`at_gate` → `at_receiving` → `at_cold_room` → `at_dock`
→ `loaded`), and each move deletes the previous location. This keeps the states consistent.
The validator checks this on every step.

Ordering rules are built into the preconditions:

* `seal_container` needs `container_inspected`, so there is no sealing before inspection.
* `pack_dry_ice` needs `container_open`, and sealing deletes `container_open`, so dry ice
  cannot be packed into a sealed container.
* `load_pallet` needs `at_dock`, so loading cannot happen before the loading dock.
* `move_to_cold_room` needs `temp_verified`, so temperature is verified first.

The PDDL files in `pddl/` express the same model in standard PDDL form.

## 6. Breadth-first search (BFS)

BFS expands states level by level, so the first goal state it reaches is one that needs
the fewest actions.

Simple example: from a start state, BFS first tries every applicable action (level 1), then
every applicable action from each of those states (level 2), and so on. A visited set stops
it from re-expanding a state. Each queued node remembers the action that led to it, so the
plan is rebuilt by walking those links backwards.

In this project each node is `(state, minutes used, dry ice used)`. Successors that exceed
the time budget or the dry-ice stock are pruned, and BFS reports how many it rejected, so it
never returns a plan that is over budget.

The visited check uses **dominance**. A new node is skipped when the same facts were already
reached with no more minutes and no more dry ice. This matters because repeating a no-op
action (for example, packing dry ice twice) changes only the time. Without dominance the
search keeps generating those copies. If the goal were unreachable and no time budget were set,
the search would never end. The
dominance rule never removes a plan: any continuation of a skipped node is also available
from the node that dominates it, so the first plan found still has the fewest actions.

## 7. Partial-order planning (POP)

POP does not build a fixed sequence. It builds a plan with:

* **steps** (actions) and two fake steps, `START` (its effects are the initial state) and
  `FINISH` (its preconditions are the goal),
* **ordering constraints** ("A before B"),
* **causal links** `A --c--> B` meaning "A provides condition c to B", and
* **open conditions**, preconditions that no step provides yet.

The search repeats until no open conditions or threats remain:

1. **Threat detection.** A step T threatens a link `A --c--> B` when T deletes `c` and could
   run between A and B.
2. **Threat resolution.** *Promotion* orders T before A. *Demotion* orders T after B. Any
   option that would create an ordering cycle is rejected, and the other option is tried.
3. **Support.** Pick an open condition `(B, c)`. Either reuse an existing step that adds `c`,
   or add a new step that adds `c`. Then add the causal link and the ordering `A < B`.

Example from this scenario. `seal_container(P1)` deletes `container_open(P1)`. The link
`START --container_open(P1)--> pack_dry_ice(P1)` is threatened by the seal. Promotion would
put the seal before `START`, which is a cycle, so it is rejected. Demotion puts the seal
after the pack, so the planner adds `pack_dry_ice(P1) < seal_container(P1)`.

Inspection and dry-ice packing both need an open container and neither deletes it, so
neither is ordered against the other. The plan therefore allows either order, which is the
kind of flexibility a partial order is meant to express.

## 8. System architecture

```
          +-----------------+         +------------------+
          |     app.py      |         |     main.py      |   (command line)
          |   (Streamlit)   |         +------------------+
          +--------+--------+                  |
                   |                           |
        +----------v---------------------------v----------+
        |                 comparison.py                    |
        |   run_bfs / run_pop / compare / metric rows      |
        +----+------------------+---------------------+----+
             |                  |                     |
        +----v----+        +----v----+           +----v-----+
        |  bfs.py |        |  pop.py |           | validator.py |
        +----+----+        +----+----+           +----+-----+
             |                  |                     |
             +---------+--------+---------------------+
                       |
          +------------v-------------+       +--------------------+
          |        strips.py         |       | visualization.py   |
          | Action, PlanningProblem  |       | (Graphviz DOT)     |
          +------------+-------------+       +--------------------+
                       |
          +------------v-------------+       +--------------------+
          |        actions.py        |<------|   scenarios.py     |
          | 8 cold-chain operators   |       | 6 synthetic cases  |
          +------------+-------------+       +----------+---------+
                       |                                |
                       +---------------+----------------+
                                       |
                            +----------v-----------+
                            |   constraints.py     |
                            | temperature, time,   |
                            | dry-ice (simulated)  |
                            +----------------------+
```

Data flow: a `Scenario` supplies packages and constraints. `actions.py` turns them into
grounded STRIPS actions and an initial state. A planner searches. `validator.py` replays
the resulting plan and reports every problem found. The results are shown in the UI or on
the command line.

## 9. Project folder structure

```
Cold_Chain_AI_Project/
├── app.py               Streamlit interface (dashboard, details, planning, results, graphs)
├── main.py              Command-line runner and JSON export
├── strips.py            Action and PlanningProblem (STRIPS representation)
├── actions.py           The eight cold-chain operators and initial state/goal builders
├── bfs.py               Custom breadth-first search planner
├── pop.py               Custom partial-order planner (links, orderings, threats)
├── validator.py         Independent plan replay and constraint checking
├── constraints.py       Simulated temperature, time and dry-ice constraints
├── scenarios.py         Six synthetic scenarios (3 succeed, 3 fail as designed)
├── visualization.py     Graphviz diagrams (sequence, states, dependencies, causal links, ordering)
├── comparison.py        Runs both planners and builds comparison metrics
├── pddl/
│   ├── domain.pddl      STRIPS-style PDDL domain
│   └── problem.pddl     PDDL problem for scenario 1
├── tests/
│   ├── conftest.py
│   ├── test_actions.py
│   ├── test_bfs.py
│   ├── test_pop.py
│   ├── test_constraints.py
│   ├── test_validator.py
│   └── test_comparison.py
├── sample_outputs/
│   ├── cli_output.txt       Output of `python main.py`
│   ├── pytest_output.txt    Verbose output of `python -m pytest -v`
│   └── scenarios/*.json     Each scenario with both planner results
├── requirements.txt
├── README.md
├── PROJECT_REPORT.md
└── .gitignore
```

## 10. Installation

Requirements: **Python 3.11 or newer**. Works on Windows, macOS and Linux.

The Python `graphviz` package generates diagram source. The app displays it in the browser,
so the Graphviz program itself is **not required** to run the app. Installing Graphviz
(from graphviz.org) is only needed if you want to render images outside the app.

**Windows (PowerShell or Command Prompt in VS Code):**

```bat
cd Cold_Chain_AI_Project
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
cd Cold_Chain_AI_Project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 11. How to run the application

```bash
streamlit run app.py
```

Streamlit opens the app in your browser (usually at http://localhost:8501).

1. Pick a scenario in the sidebar.
2. **Dashboard**: project description, workflow, scenario overview.
3. **Scenario Details**: initial state, goal, actions, packages and simulated temperature
   readings, time budget and dry-ice stock.
4. **Planning Engine**: press *Generate BFS Plan*, *Generate POP Plan* or
   *Compare Both Algorithms*.
5. **Results**: action sequence, success or failure, goal achievement, plan validation,
   planning time, explored states or nodes, plan length, resource use and violations.
6. **Visualization**: Graphviz diagrams of the action sequence, state transitions,
   planning dependencies, POP causal links and POP ordering constraints.

Command-line alternative:

```bash
python main.py --list                                  # list scenarios
python main.py --scenario normal_single_vaccine        # both planners, one scenario
python main.py --scenario limited_dry_ice --algorithm bfs
python main.py                                         # every scenario
python main.py --export-json sample_outputs/scenarios  # write JSON files
```

## 12. Running the tests

```bash
python -m pytest -v
```

The suite has 75 tests. They cover action preconditions, add and delete effects,
consistency of location and container states, BFS plans and no-solution cases, the time
boundary, POP causal links, ordering constraints, independence, threat detection, promotion
and demotion, linearisation, temperature, time-budget and dry-ice violations, validator
behaviour, and both planners on every scenario against its expected outcome.

Rechecked in this review environment with Python 3.13.5 and pytest 9.0.2: `75 passed`. The full
verbose log is in `sample_outputs/pytest_output.txt`.

## 13. Sample outputs

The complete command-line log is in `sample_outputs/cli_output.txt`. Two excerpts follow.
Planning times vary by machine, so they are left out here. The other numbers are exact and
repeat on every run.

**Scenario 1, normal transport of one frozen vaccine**

```
1. Normal transport of one frozen vaccine   (expected: success)
  [BFS] Valid plan
      message      : Plan found with 8 actions.
      explored     : 10 (states)
      goal achieved: yes
      plan length  : 8 actions
      duration     : 32 min (sequential)
      dry ice used : 2 kg
  [POP] Valid plan
      message      : Partially ordered plan with 8 steps, 17 causal links and 8 ordering constraints.
      explored     : 18 (nodes)
      goal achieved: yes
      plan length  : 8 actions
      duration     : 32 min (sequential)
      dry ice used : 2 kg
      causal links : 17
      ordering constraints (non-redundant): 8
      unordered step pairs: 1
      parallel makespan   : 28 min (informational)
```

The one unordered pair is `pack_dry_ice(P1)` and `inspect_container(P1)`. The POP plan
found inspection before packing in one linearisation, and BFS found the reverse order.

**Scenario 3, limited dry-ice stock (expected failure)**

```
3. Limited dry-ice stock   (expected: failure)
  [BFS] No plan found
      message      : No plan found. The search was exhausted, and 40 successor state(s) were rejected by the time budget or dry-ice limit.
      explored     : 75 (states)
  [POP] Plan rejected by constraints
      message      : Partially ordered plan with 16 steps, 34 causal links and 16 ordering constraints.
      explored     : 35 (nodes)
      violation    : Dry ice required 4 kg exceeds available 2 kg
```

BFS prunes over-budget states during search, so it finds no plan. POP does not use the
limits during search, so it finds a logically valid plan that the validator rejects.

## 14. Scenarios

| Key | Scenario | Expected | Result: BFS / POP |
|---|---|---|---|
| `normal_single_vaccine` | One frozen vaccine, enough dry ice and time | success | valid / valid |
| `mixed_processing_requirements` | Two frozen packages and one refrigerated package | success | valid / valid |
| `limited_dry_ice` | Two frozen packages, 2 kg dry ice (4 kg needed) | failure | no plan / rejected |
| `restricted_time_budget` | One frozen package, 30 min budget (32 min needed) | failure | no plan / rejected |
| `temperature_verification_failure` | Refrigerated package at about 11 °C | failure | no plan / no plan |
| `refrigerated_only_success` | One refrigerated package, no dry ice | success | valid / valid |

## 15. Limitations and future improvements

**Limitations (honest account):**

* **Simulated, not validated.** Temperatures, durations, dry-ice amounts and budgets are
  invented for teaching. The project is not a compliance tool.
* **Deterministic sensors.** Readings come from a seeded random generator around a chosen
  base temperature. Real sensors drift, fail and have gaps, and none of that is modelled.
* **Grounded actions only.** Each package has its own copy of each operation. There are no
  variables to bind, and each library action is used at most once per POP plan.
* **POP is simplified.** It uses a fixed "fewest supporters first" choice of open condition,
  and no heuristic guides the search. It does not handle conditional effects, disjunctive
  preconditions, or resources during the search. Time and dry ice are checked afterwards by
  the validator, which is why POP can return a plan the validator rejects.
* **BFS is exhaustive.** It is guaranteed to find a shortest action sequence, but it is
  exponential in the worst case. The three-package scenario expands 800 states, while POP refines 49 nodes.
* **Sequential time model.** BFS and the time budget add up action durations as if nothing
  runs in parallel. POP's parallel makespan is shown only for information.
* **Metrics are not directly comparable.** BFS explores states, POP explores search nodes,
  and BFS returns a total order while POP returns a partial order.
* **PDDL is not executed.** `pddl/domain.pddl` and `pddl/problem.pddl` document the model.
  The Python planners are the ones that run and are tested. The PDDL domain uses an
  `ice-ready` predicate to avoid conditional preconditions. It is not an exact copy of the
  Python preconditions.
* **One vehicle and one warehouse.** There is no routing, no multiple vehicles and no
  replanning after a failure.

**Future improvements:**

* Add a heuristic search (A* with a relaxed-plan heuristic) so that large problems finish
  faster.
* Model dry ice as a numeric resource inside the search, and model durations as
  concurrency-aware, so that the time budget can use the parallel makespan.
* Add temperature drift during transport and a replanning step after a violation.
* Run the PDDL files through an external planner (such as Fast Downward) and compare results.
* Add per-package deadlines and vehicle capacity.
* Replace the simulated readings with an import from a CSV log.

## 16. Licence and attribution

This is an educational project. The scenarios, temperature values and constraints are
invented. Graphviz is used for diagram source and Streamlit for the user interface.
