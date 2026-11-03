# Cold-Chain AI Planning Prototype
## Applied AI System for Perishable Pharmaceutical Logistics

A classical automated planning system for simulating, validating, and visualizing temperature-controlled pharmaceutical distribution (vaccines, biological samples, and medicines) across warehouse environments.

---

## ❄️ System Overview

The distribution hub requires packages to transition across strictly ordered physical stages under temperature, time, and dry-ice resource constraints:
$$\text{receiving} \longrightarrow \text{cold\_room} \longrightarrow \text{inspection} \longrightarrow \text{loading\_dock}$$

- **Ambient Environments**: `receiving`, `loading_dock` (accumulate exposure counter).
- **Temperature-Controlled Environments**: `cold_room`, `inspection` (reset exposure counter to 0).

### Core Modules Implemented:
1. **Plan Validation (`validator.py`)**: Pure simulation engine that strictly validates STRIPS action sequences, verifying preconditions, state transitions `(state - delete) ∪ add`, goal satisfaction, cumulative dry-ice stock, total time budget, and per-package ambient exposure limits.
2. **Unified Adapter (`adapter.py`)**: Standardized interface decoupling the UI/validator from planning engines (Forward BFS and Partial-Order Planning), featuring timeout handling, exception containment, and fallback mock support (`COLDCHAIN_MOCK=1`).
3. **Graphviz Visualization (`viz/`)**:
   - `plan_to_dot`: Sequential action flow with red violation highlighting.
   - `pop_to_dot`: Partial-order planning graph rendering causal links (dashed blue), ordering constraints (solid grey), and threat resolutions (solid red).
   - Safe rendering utilities (`export_dot`, `render_png_safe`) that gracefully degrade when system binaries are absent.
4. **Interactive Streamlit Prototype (`app.py`, `ui/`)**:
   - Multi-tab application for scenario exploration (S1–S5), real-time constraint tuning, compliance metrics tracking, side-by-side planner comparisons, and manual testbed validation.

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.11+
- (Optional) Graphviz system binary `dot` for PNG image generation (interactive DOT graphs work natively).

### 2. Installation
```bash
python -m pip install -r requirements.txt
```

### 3. Launching the Streamlit Prototype
```bash
streamlit run app.py
```

### 4. Running the Test Suite & Coverage
```bash
python -m pytest -q --cov=validator --cov=viz --cov=adapter --cov-report=term-missing
```

---

## 📋 Scenarios Reference (S1–S5)

| ID | Title | Constraints (Stock / Budget / Limit) | Expected Result |
|---|---|---|---|
| **S1** | Single vaccine package, normal | `2 / 40 / 10` | Valid Plan (8 steps, 22 time, 1 ice) |
| **S2** | Three packages, different starts | `3 / 60 / 10` | Valid Plan (18 steps, 49 time, 2 ice) |
| **S3** | Limited dry ice | `2 / 100 / 10` | ⚠️ No Plan (Requires 3 ice units) |
| **S4** | Restricted time budget | `2 / 15 / 10` | ⚠️ No Plan (Minimum time is 22) |
| **S5** | Temperature verification unavailable | `2 / 40 / 10` | ⚠️ No Plan (`temp_ok` unreachable) |

---

## 🧪 Quality Gates
- **Linting & Code Quality**: `ruff check .`
- **Formatting**: `ruff format --check .`
- **Test Coverage**: $\ge 90\%$ line coverage across all core modules.

