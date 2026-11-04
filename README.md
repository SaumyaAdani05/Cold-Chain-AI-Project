# Automated Cold-Chain Logistics Planning for Perishable Pharmaceuticals Using Classical AI

A classical automated planning system for simulating, validating, and visualizing temperature-controlled pharmaceutical distribution (vaccines, biological samples, and medicines) across warehouse environments.

Two planners are written from scratch in Python:
* a **breadth-first search** (BFS) over STRIPS states, which returns a total order, and
* a simplified **partial-order planner** (POP), which returns causal links and ordering constraints.

A separate validator replays every plan and checks simulated temperature, time, and dry-ice constraints. An interactive Streamlit interface, prototype compliance testbed, and command-line runner use the unified code.

> **Important:** every temperature range, duration, dry-ice amount, and time budget in this project is a **simulated assumption for teaching**. None of them is a validated pharmaceutical transport standard, and the project does not certify compliance with any regulation.

---

## ❄️ System Overview

The distribution hub requires packages to transition across strictly ordered physical stages under temperature, time, and dry-ice resource constraints:
$$\text{receiving} \longrightarrow \text{cold\_room} \longrightarrow \text{inspection} \longrightarrow \text{loading\_dock}$$

- **Ambient Environments**: `receiving`, `loading_dock` (accumulate exposure counter).
- **Temperature-Controlled Environments**: `cold_room`, `inspection` (reset exposure counter to 0).

### Core Modules Implemented:
1. **Classical AI Planners**:
   - `bfs.py`: Custom forward state-space Breadth-First Search planner with state dominance and pruning.
   - `pop.py`: Partial-Order Planner with causal links, ordering constraints, threat detection, and promotion/demotion.
   - `strips.py`: Grounded STRIPS representation (`Action`, `State`, `PlanningProblem`).
2. **Plan Validation (`validator.py`)**:
   - `validate`: Strict simulation engine verifying preconditions, transitions `(state - delete) ∪ add`, goal satisfaction, dry-ice stock, total time budget, and ambient exposure limits.
   - `validate_plan`: Replays plans against synthetic sensor profiles, temperature limits, and state consistency.
3. **Unified Adapter (`adapter.py`)**: Standardized interface decoupling UI/validator from planning engines with timeout containment and mock fallback (`COLDCHAIN_MOCK=1`).
4. **Graphviz Visualization (`viz/` & `visualization.py`)**:
   - Sequential action flows and state transitions.
   - Partial-order graphs rendering causal links (dashed blue), ordering constraints (solid grey), and threat resolutions (solid red).
5. **Interactive Streamlit Interface (`app.py`, `ui/`)**:
   - Live execution of BFS & POP with real-time comparison tables.
   - S1–S5 scenario inspection, constraint tuning, and manual testbed validation.

---

## 1. Problem Definition

Given a set of packages, each with a simulated temperature profile, find a sequence (or a partially ordered set) of the eight operations below so that every package is loaded onto the delivery pallet, while:

* every precondition holds when its operation runs,
* every simulated temperature reading stays inside the package's acceptable range,
* the total duration does not exceed the time budget, and
* the dry-ice used does not exceed the dry-ice stock.

The eight operations are:
`receive_package`, `verify_temperature`, `move_to_cold_room`, `pack_dry_ice`, `inspect_container`, `seal_container`, `move_to_loading_dock`, `load_pallet`.

---

## 2. Classical AI & STRIPS Representation

Classical planning works on symbolic, fully specified problems. The world is described as a set of true facts. An action can run only when its preconditions are true, and it changes the world by deleting some facts and adding others: `(state - delete) ∪ add`.

A state is a set of facts such as `at_gate(P1)` or `container_sealed(P1)`. For example, `seal_container(P1)`:

| Part | Content |
|---|---|
| Preconditions | `container_inspected(P1)`, `container_open(P1)`, `dry_ice_packed(P1)` (frozen packages only) |
| Add effects | `container_sealed(P1)` |
| Delete effects | `container_open(P1)` |
| Duration | 2 min (configurable) |
| Dry ice | 0 kg |

The location of a package is always exactly one fact (`at_gate` → `at_receiving` → `at_cold_room` → `at_dock` → `loaded`), and each move deletes the previous location to ensure consistency.

---

## 3. Planners: BFS vs POP

- **Breadth-First Search (BFS)** expands states level-by-level, returning the shortest total order of actions. Node pruning skips states that exceed resource budgets, and dominance checking prevents redundant re-expansion.
- **Partial-Order Planning (POP)** searches the space of plans rather than states. It resolves open preconditions by establishing causal links `A --c--> B` and ordering constraints `A < B`, resolving threats via promotion or demotion.

---

## 4. System Architecture

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
          | Action, PlanningProblem  |       | viz/ (Graphviz)    |
          +------------+-------------+       +--------------------+
                       |
          +------------v-------------+       +--------------------+
          |        actions.py        |<------|   scenarios.py     |
          | 8 cold-chain operators   |       | 6 synthetic cases  |
          +------------+-------------+       +----------+---------+
```

---

## 5. Installation & Getting Started

Requirements: **Python 3.11 or newer**.

### Installation
```bash
# Clone the repository
git clone https://github.com/SaumyaAdani05/Cold-Chain-AI-Project.git
cd Cold-Chain-AI-Project

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Launch the Streamlit Interface
```bash
streamlit run app.py
```

### Command-Line Runner
```bash
python main.py --list                                  # list scenarios
python main.py --scenario normal_single_vaccine        # run both planners on one scenario
python main.py --scenario limited_dry_ice --algorithm bfs
python main.py                                         # run all scenarios
python main.py --export-json sample_outputs/scenarios  # export scenario results to JSON
```

---

## 6. Running Tests & Quality Gates

Run the comprehensive automated test suite (including planner, scenario, validator, adapter, and visualization tests):

```bash
python -m pytest -v
```

Run test coverage:
```bash
python -m pytest -q --cov=validator --cov=viz --cov=adapter --cov-report=term-missing
```

Code formatting and linting:
```bash
ruff check .
black --check .
```

---

## 📋 Scenarios Reference

| Key / ID | Title | Constraints (Stock / Budget / Limit) | Expected Result | BFS / POP Outcome |
|---|---|---|---|---|
| `normal_single_vaccine` (**S1**) | Single vaccine package, normal | `2 / 40 / 10` | Valid Plan | valid / valid |
| `mixed_processing_requirements` (**S2**) | Three packages, different starts | `3 / 60 / 10` | Valid Plan | valid / valid |
| `limited_dry_ice` (**S3**) | Limited dry ice | `2 / 100 / 10` | ⚠️ Failure | no plan / rejected |
| `restricted_time_budget` (**S4**) | Restricted time budget | `2 / 15 / 10` | ⚠️ Failure | no plan / rejected |
| `temperature_verification_failure` (**S5**) | Temperature verification failure | `2 / 40 / 10` | ⚠️ Failure | no plan / no plan |
| `refrigerated_only_success` | One refrigerated package, no dry ice | `0 / 40 / 10` | Valid Plan | valid / valid |

---

## 7. Limitations and Future Improvements

- **Simulated sensors**: Sensor temperatures and timings are simulated assumptions for educational demonstrations.
- **Heuristic search**: Can be extended with A* search and delete-relaxation heuristics (e.g. FF / Fast-Forward).
- **Concurrency**: Parallel makespan and vehicle route dispatching can be extended for multi-vehicle logistics.
