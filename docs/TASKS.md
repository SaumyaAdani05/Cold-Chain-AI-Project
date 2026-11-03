# TASKS.md — Ordered Work Plan (Validation → Visualization → Streamlit)

Work top to bottom. Tick a box only when the acceptance criteria are met and the Definition of Done in `AGENTS.md` §4 holds.
Estimated effort is for one developer working with the agent.

---

## Phase 0 — Project hygiene (≈ 0.5 day)

- [x] **T0.1** Create `requirements.txt`, `pyproject.toml` (black line-length 100, ruff, pytest paths).
  *Accept:* `black --check .`, `ruff check .`, `pytest -q` all run (even with 0 tests).
- [x] **T0.2** Create the folder layout from `TECHSTACK.md` §6 with empty `__init__.py` files.
  *Accept:* `python -c "import validator, adapter, viz"` succeeds.
- [x] **T0.3** Confirm with the user whether `model.py` has `Action.pkg` and `Scenario`; if not, create **stand-in dataclasses** in `tests/fixtures/stubs.py` matching `ARCHITECTURE.md` §3 and record the question in the message (do not edit `model.py`).

## Phase 1 — Plan Validation (≈ 2 days)

- [x] **T1.1** Define `Violation` and `ValidationResult` dataclasses in `validator.py`.
  *Accept:* frozen, typed, match `ARCHITECTURE.md` §3.5 exactly.
- [x] **T1.2** Implement precondition simulation + goal check (FR-V1–V3, V7).
  *Accept:* tests T1, T2, T3, T4, T5, T6, T7 pass.
- [x] **T1.3** Add dry-ice and time-budget checks (FR-V4).
  *Accept:* T8, T9, T13 pass.
- [x] **T1.4** Add per-package exposure tracking per `DOMAIN.md` §4.3.
  *Accept:* T10 passes; `max_exposure == 5` on the reference plan.
- [x] **T1.5** Multi-violation ordering + metrics (FR-V5, V6).
  *Accept:* T11 passes; violations sorted by step, global last.
- [x] **T1.6** Strict mode warnings (FR-V9, optional).
  *Accept:* T12 passes.
- [x] **T1.7** Purity and determinism tests (FR-V8).
  *Accept:* T14, T15, T16 pass; coverage of `validator.py` ≥ 90%.
- [x] **T1.8** Fallback for missing `Action.pkg` (parse from `name`).
  *Accept:* test with an Action lacking `pkg` still yields correct exposure.

## Phase 2 — Mocks and Adapter (≈ 1 day)

- [x] **T2.1** Write `tests/fixtures/mock_planners.py` per `ARCHITECTURE.md` §5 (S1 reference plan, POP structure with ≥ 3 causal links and 1 resolved threat, no-plan, timeout, broken plans).
  *Accept:* every mock validates as expected using the validator tests.
- [x] **T2.2** Implement `adapter.py`: `available_planners()`, `run_planner()`, raw-dict → `PlannerResult` normalization, timeout, exception capture, `COLDCHAIN_MOCK=1` switch.
  *Accept:* tests for success, no plan, exception, timeout, and mock mode.

## Phase 3 — Visualization (≈ 2 days)

- [x] **T3.1** `viz/plan_graph.py::plan_to_dot` (FR-G1, G5, G7).
  *Accept:* test V1, V4; rendered S1 graph is readable (manual look at PNG).
- [x] **T3.2** Violation highlighting (FR-G3).
  *Accept:* test V3.
- [x] **T3.3** `viz/pop_graph.py::pop_to_dot` with ordering edges, dashed causal links, red threat edges (FR-G2).
  *Accept:* test V2; mock POP graph shows legend and all causal links.
- [x] **T3.4** Multi-package styling and large-graph truncation (> 80 nodes).
  *Accept:* S2 graph distinguishes packages by label text and colour; truncation node appears for a synthetic 100-step plan.
- [x] **T3.5** Export helpers: DOT source and PNG bytes with `ExecutableNotFound` handling (FR-G6).
  *Accept:* test V5; manual U6.
- [x] **T3.6** *(Optional)* `search_tree_to_dot` (FR-G4).

## Phase 4 — Streamlit prototype (≈ 3 days)

- [x] **T4.1** `app.py` skeleton: page config, sidebar (scenario, planner, sliders), tabs (Planner / Manual validation / About) using mock planners (FR-U1).
  *Accept:* `streamlit run app.py` starts; scenario switch updates state tables (FR-U2).
- [x] **T4.2** Generate Plan flow: adapter → validator → session state; spinner; status badge (FR-U3, U5).
  *Accept:* manual U1, U2.
- [x] **T4.3** Plan list + compliance panel (FR-U4, U6).
  *Accept:* S1 shows 22/40 time, 1/2 ice, max exposure 5/10, goal reached.
- [x] **T4.4** Graph rendering with fallback (FR-U7, U12).
  *Accept:* manual U6.
- [x] **T4.5** "Both" mode: two columns + comparison table (FR-U8).
  *Accept:* manual U3 with all 5 metrics.
- [x] **T4.6** Outdated-result handling and error states (FR-U10, U12).
  *Accept:* manual U4; planner exception and timeout shown as red/amber messages.
- [x] **T4.7** Manual validation tab (FR-U11).
  *Accept:* manual U5.
- [x] **T4.8** Downloads: results CSV, graph PNG/DOT (FR-U9).
  *Accept:* downloaded files open correctly.
- [x] **T4.9** Polish: legend, units on labels, accessible status (icon + text), About tab with action table and PEAS (NFR-7).

## Phase 5 — Integration with real planners (≈ 1 day, when teammates deliver)

- [ ] **T5.1** Point the adapter at real `bfs.py` / `pop.py` (no mock mode).
  *Accept:* S1–S5 outcomes match the table in `DOMAIN.md` §6 for each planner provided.
- [ ] **T5.2** If a planner's real output differs from the contract, **stop and report**; propose an adapter shim, do not edit the planner.
- [ ] **T5.3** Verify every returned plan passes the validator (add a regression test iterating over S1, S2).

## Phase 6 — Experiments and report support (≈ 1 day)

- [x] **T6.1** `experiments/run_compare.py`: run each scenario × planner (≥ 5 runs for timing), write `results.csv` with columns `scenario, planner, plan_found, plan_length, explored, time_s_mean, violations, dry_ice_used, total_time`.
  *Accept:* real numbers only; CSV committed.
- [x] **T6.2** Charts (matplotlib): planning time per scenario, explored states per planner.
  *Accept:* PNGs saved to `experiments/`, titled and labelled with units.
- [ ] **T6.3** Screenshots for the report: S1 valid, S3 no plan, POP causal graph, Manual tab with violations.


## Phase 7 — Final QA (≈ 0.5 day)

- [x] **T7.1** Run quality gates: `black --check .`, `ruff check .`, `pytest --cov`.
- [ ] **T7.2** Fresh-clone test on a second machine or clean venv (AC5).
- [ ] **T7.3** Demo rehearsal: S1 → S3 → S5 → POP graph → Manual broken plan. Verify `dot -V` on the demo laptop.
- [x] **T7.4** Update `README.md` (setup, run, structure, screenshots).

---

## Status log

| Date | Task | Note |
|---|---|---|
| 2026-10-31 | Phase 0–4 | Implemented validator (100% cov), adapter (96% cov), viz (98% cov), and Streamlit UI app (S1-S5, comparison, manual bench). 36 tests passing. |
