# PRD — Cold-Chain Planning Prototype (Validation, Visualization, UI)

**Track:** A – Applied AI System Development (Robotic Manipulation & Classical Planning)
**Project type:** Applied AI system / prototype
**Status:** Stage 1 proposal approved → implementation

---

## 1. Overview

Pharmaceutical products (vaccines, biological samples, temperature-sensitive medicines) must move through a distribution hub — temperature verification, cold storage, dry-ice packing, inspection, sealing, loading — under temperature, time, and resource limits. Doing steps in the wrong order can invalidate required conditions.

The system uses **Classical AI automated planning (STRIPS/PDDL)** to generate a valid action sequence from an initial state to a goal state. Two planners are compared: a baseline **Forward State-Space BFS** and an advanced **Partial-Order Planner (POP)**.

This is a **planning system, not a machine-learning system.** There is no training data; scenarios are synthetic.

## 2. This PRD's scope (my modules)

| In scope (this document) | Out of scope here (owned elsewhere) |
|---|---|
| **Plan Validation** — verify any plan against preconditions, goal, and constraints | Implementing BFS |
| **Visualization** — Graphviz graphs of plans, causal links, optional search tree | Implementing POP |
| **Streamlit prototype** — scenario selection, plan generation, results, comparison | Domain/action definitions (`model.py`) and PDDL files |

The three in-scope modules **consume** planner output through the contracts in `ARCHITECTURE.md`.

## 3. Goals

1. G1: Any plan (from BFS, POP, or hand-written) can be validated, with precise, human-readable violation messages.
2. G2: Plans and causal structure are visualized clearly enough to explain in a viva/demo.
3. G3: A non-technical user can select a scenario, run a planner, and understand whether the result is compliant — with no code.
4. G4: The UI supports side-by-side comparison of BFS vs POP on the agreed metrics.

## 4. Non-goals

- No real sensor/IoT integration, real hardware, or robot control.
- No ML, probabilistic planning, or learning from data.
- No user accounts, database, or deployment infrastructure.
- No new planner algorithms in these modules.

## 5. Users

| User | Need |
|---|---|
| Student / presenter (primary) | Demo the system, explain plan structure and compliance live |
| Examiner / reviewer | Verify correctness, see metrics and the reasoning behind plans |
| Teammate (planner developer) | Plug a planner in and instantly see it validated and visualized |

## 6. Functional requirements

### 6.1 Plan Validation (`validator.py`)

| ID | Requirement | Priority |
|---|---|---|
| FR-V1 | Simulate a plan from the initial state; at each step check all preconditions hold | Must |
| FR-V2 | Apply effects as `(state − delete) ∪ add` after each step | Must |
| FR-V3 | After the last step, check all goal facts hold | Must |
| FR-V4 | Check dry-ice use ≤ stock; total time ≤ budget; per-package exposure ≤ limit (rules in `DOMAIN.md` §4) | Must |
| FR-V5 | Collect **all** violations, each with step index, action name, violation type, and message | Must |
| FR-V6 | Return computed metrics: total time, dry-ice used, plan length, final state | Must |
| FR-V7 | Treat `None` plan as "no plan" (not an error); treat `[]` correctly | Must |
| FR-V8 | Pure function: no I/O, no Streamlit, no mutation of inputs | Must |
| FR-V9 | Optional strict mode: flag redundant actions (action adds nothing new) as warnings | Could |

### 6.2 Visualization (`viz/`)

| ID | Requirement | Priority |
|---|---|---|
| FR-G1 | `plan_to_dot`: linear plan graph (Start → steps → Goal), nodes numbered | Must |
| FR-G2 | `pop_to_dot`: POP graph with steps, ordering edges (solid), causal links (dashed, labelled with the fact), resolved threats (red) | Must |
| FR-G3 | Highlight the steps that violated validation (red outline) when a `ValidationResult` is supplied | Should |
| FR-G4 | `search_tree_to_dot`: first N explored states for small scenarios | Could |
| FR-G5 | Return `graphviz.Digraph` objects; no rendering side effects inside builders | Must |
| FR-G6 | Export graph as PNG and DOT source | Should |
| FR-G7 | Consistent colour legend and readable labels; long action names wrapped | Should |

### 6.3 Streamlit prototype (`app.py`, `ui/`)

Flow: **Select scenario → show initial state & goal → choose planner → generate plan → validate → visualize → compliance result.**

| ID | Requirement | Priority |
|---|---|---|
| FR-U1 | Sidebar: scenario dropdown (S1–S5), planner selector (BFS / POP / Both), sliders for dry-ice stock, time budget, exposure limit (defaults from scenario) | Must |
| FR-U2 | Display initial-state and goal fact tables | Must |
| FR-U3 | "Generate Plan" button runs selected planner(s) via the adapter; spinner while running | Must |
| FR-U4 | Show plan as a numbered list with per-step duration and dry-ice use | Must |
| FR-U5 | Show validation badge: ✅ Valid / ❌ Invalid (violations listed) / ⚠️ No plan found | Must |
| FR-U6 | Show Cold-Chain Compliance panel: temperature/exposure OK, time budget used/limit, dry-ice used/stock, goal reached | Must |
| FR-U7 | Render the Graphviz graph for the chosen planner | Must |
| FR-U8 | "Both" mode: side-by-side columns and a metrics comparison table (planning time, plan length, explored states, violations, dry-ice used) | Must |
| FR-U9 | Download buttons: results CSV, graph PNG/DOT | Should |
| FR-U10 | Keep results in `st.session_state`; changing a widget must not crash or silently show stale results (mark as "outdated") | Must |
| FR-U11 | "Manual plan" tab: user pastes or builds a plan and validates it (shows the validator catching errors) | Should |
| FR-U12 | Graceful errors: missing Graphviz binary, planner exception, planner timeout | Must |

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Validator runs in < 50 ms for plans up to 100 steps |
| NFR-2 | UI first paint < 3 s; scenario switch < 1 s (excluding planner runtime) |
| NFR-3 | Planner call has a configurable timeout (default 30 s); UI stays responsive and reports timeout |
| NFR-4 | Python 3.11+; runs on Windows, macOS, Linux with only `pip install -r requirements.txt` plus the Graphviz binary |
| NFR-5 | ≥ 90% line coverage for `validator.py`; every public function in `viz/` has at least a smoke test |
| NFR-6 | Deterministic: same scenario + planner → same output (sort sets before display) |
| NFR-7 | Accessible: status conveyed by icon + text, not colour alone |

## 8. Scenarios (see `DOMAIN.md` §6 for full definitions)

| ID | Description | Expected outcome |
|---|---|---|
| S1 | Single vaccine package, normal conditions | Valid plan, 8 steps |
| S2 | Three packages, different start states | Valid plan |
| S3 | Limited dry ice (2 units, 3 packages) | No plan |
| S4 | Restricted time budget (15 units) | No plan |
| S5 | Temperature verification unavailable | No plan |

## 9. Acceptance criteria (project-level)

- AC1: Validator accepts the reference plan for S1 and rejects each broken plan in `DOMAIN.md` §7 with the expected violation.
- AC2: For S1–S5, the UI shows the outcome in the table above for each implemented planner.
- AC3: POP graph shows ≥ 1 labelled causal link and (when applicable) a resolved threat on S1/S2.
- AC4: "Both" mode shows a comparison table with all five metrics.
- AC5: Fresh clone + install instructions → app runs on a second machine.
- AC6: All tests pass; no ruff/black errors.

## 10. Metrics for the project report

Planning time, plan length, explored states / nodes, constraint violations, dry-ice usage — collected per scenario per planner (≥ 5 runs for time, averaged), saved to CSV, plotted.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Planner modules not ready when UI work starts | Develop against mock planners in `tests/fixtures/` |
| Contract drift between teammates | Contracts frozen in `ARCHITECTURE.md`; changes require agreement |
| Graphviz binary missing on demo machine | Graceful fallback to showing DOT source + install hint; test on demo laptop in advance |
| BFS too slow on S2 | Timeout + "timed out" UI state; keep package count small in the demo |
| Constraint-rule ambiguity | Rules fixed in `DOMAIN.md` §4; confirm with the team before changing |

## 12. Open questions (confirm with the team)

1. Should `Action` carry a `pkg` field (needed for per-package exposure tracking)? — **Proposed: yes**, see `ARCHITECTURE.md` §3.
2. Are the default durations and exposure limit in `DOMAIN.md` §3–4 acceptable to the course/supervisor?
3. Will POP return a linearized `plan` in addition to its partial-order structure? — **Required** for validation.
