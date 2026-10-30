# TECHSTACK.md

All choices are **from-scratch**: no planning engines, no ML. The agent may use only what is listed here. To add anything, ask first.

---

## 1. Stack

| Layer | Technology | Version | Used for |
|---|---|---|---|
| Language | Python | 3.11+ | Everything |
| Domain representation | STRIPS via `dataclass` + `frozenset` (PDDL files hand-written, separate) | stdlib | States, actions |
| Baseline planner | Custom Forward BFS (`collections.deque`) | stdlib | *Not your module* |
| Advanced planner | Custom Partial-Order Planner | stdlib | *Not your module* |
| **Validation** | Custom Python | stdlib | **Your module** |
| **Visualization** | `graphviz` (Python package) + Graphviz system binary (`dot`) | pkg ≥ 0.20, binary ≥ 2.50 | **Your module** |
| **UI** | Streamlit | ≥ 1.35 | **Your module** |
| Tables / CSV | pandas | ≥ 2.0 | Metrics tables, CSV export |
| Charts | matplotlib (experiments only) | ≥ 3.8 | Report charts |
| Testing | pytest, pytest-cov | ≥ 8.0 | Tests + coverage |
| Lint / format | ruff, black | latest | Style |
| Types (optional) | mypy | latest | Static checks |
| Editor / VCS | VS Code, Git | — | Workflow |

## 2. Explicitly NOT used

- ML/DL: TensorFlow, PyTorch, scikit-learn, transformers
- Planning libraries in core code: `pyperplan`, `unified-planning`, Fast Downward, `pddlpy`
  (pyperplan may be used **by the user only** in an offline cross-check script, never imported by the app)
- Web frameworks other than Streamlit (Flask, FastAPI, Django), JS frontends
- Databases, ORMs, message queues, cloud SDKs, Docker (unless the user requests it)
- Network calls at runtime

## 3. `requirements.txt`

```
streamlit>=1.35
graphviz>=0.20
pandas>=2.0
matplotlib>=3.8
pytest>=8.0
pytest-cov>=5.0
ruff
black
```

## 4. System dependency: Graphviz binary

The `graphviz` pip package only writes DOT; the **`dot` executable must be on PATH** to render.

| OS | Install |
|---|---|
| Windows | Installer from graphviz.org → tick "Add to PATH" → restart terminal |
| Ubuntu / Debian / Kali | `sudo apt install graphviz` |
| macOS | `brew install graphviz` |

Verify: `dot -V`

## 5. Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
dot -V
pytest -q
streamlit run app.py
```

## 6. Project layout

```
coldchain/
├── AGENTS.md  PRD.md  TECHSTACK.md  ARCHITECTURE.md  DOMAIN.md  TASKS.md
├── requirements.txt
├── pyproject.toml              # ruff + black + pytest config
├── model.py                    # [read-only] Action, scenarios
├── bfs.py                      # [read-only] baseline planner
├── pop.py                      # [read-only] partial-order planner
├── pddl/                       # [read-only] domain.pddl, problem*.pddl
├── validator.py                # [YOURS]
├── adapter.py                  # [YOURS] uniform planner interface
├── viz/
│   ├── __init__.py
│   ├── plan_graph.py           # plan_to_dot
│   ├── pop_graph.py            # pop_to_dot
│   └── search_tree.py          # search_tree_to_dot (optional)
├── ui/
│   ├── __init__.py
│   ├── sidebar.py
│   ├── panels.py               # state tables, plan list, compliance panel
│   └── compare.py              # side-by-side + metrics table
├── app.py                      # [YOURS] Streamlit entry point
├── experiments/                # run_compare.py, results.csv
└── tests/
    ├── fixtures/mock_planners.py
    ├── test_validator.py
    ├── test_viz.py
    └── test_adapter.py
```

## 7. Coding conventions

- **Style:** black (line length 100), ruff default + `I` (imports) + `B` (bugbear).
- **Typing:** full annotations; use `from __future__ import annotations`.
- **Data:** `@dataclass(frozen=True)` for Action; `@dataclass` for results; `frozenset` for facts.
- **Naming:** `snake_case` functions/files, `PascalCase` classes, `UPPER_CASE` constants.
- **Facts:** strings in the form `predicate(arg1,arg2)` — **no spaces** after commas, e.g. `at(P1,cold_room)`.
- **Imports:** absolute from the project root (`from model import Action`).
- **Errors:** raise specific exceptions (`ValueError`, custom `PlannerError`); UI converts them to messages.
- **Streamlit:** one `st.set_page_config` at the top of `app.py`; widgets keyed with unique `key=`; heavy work only inside button handlers; results in `st.session_state`.

## 8. Quality gates

```bash
black --check .
ruff check .
pytest -q --cov=validator --cov=viz --cov=adapter --cov-report=term-missing
```

## 9. Browser / platform support

Chrome, Edge, Firefox (latest). Windows 10+, macOS 12+, Ubuntu 22.04+.
