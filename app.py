"""Streamlit main application entry point for the Cold-Chain AI Planning system.

Conforms to PRD.md FR-U1 through FR-U12 and ARCHITECTURE.md section 7.
"""

from __future__ import annotations

import streamlit as st

from adapter import PlannerResult, run_planner
from tests.fixtures.mock_planners import make_s1_actions, mock_broken_plans
from ui.compare import render_comparison_metrics
from ui.panels import (
    render_compliance_panel,
    render_graph_view,
    render_plan_table,
    render_state_tables,
    render_status_badge,
)
from ui.scenarios import get_all_scenarios
from ui.sidebar import render_sidebar
from validator import ValidationResult, validate

# 1. Page Configuration (single invocation at top)
st.set_page_config(
    page_title="Cold-Chain AI Planning Prototype",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Session State Initialization
if "results" not in st.session_state:
    st.session_state.results = {}
if "validations" not in st.session_state:
    st.session_state.validations = {}
if "last_inputs" not in st.session_state:
    st.session_state.last_inputs = None

# 3. Sidebar
scenario, planner_choice, constraints, generate_clicked = render_sidebar()

current_inputs = (
    scenario.id,
    constraints["stock"],
    constraints["budget"],
    constraints["limit"],
    constraints["strict"],
    planner_choice,
)

# 4. Trigger Execution
if generate_clicked:
    planners_to_run = ["bfs", "pop"] if planner_choice == "Both" else [planner_choice.lower()]
    new_results: dict[str, PlannerResult] = {}
    new_validations: dict[str, ValidationResult] = {}

    with st.spinner("Executing planners and validating action sequences..."):
        for p_name in planners_to_run:
            res = run_planner(p_name, scenario, timeout_s=30.0)
            new_results[p_name] = res

            if res.plan is not None:
                val_res = validate(
                    init=scenario.init,
                    goal=scenario.goal,
                    plan=res.plan,
                    dry_ice_stock=constraints["stock"],
                    time_budget=constraints["budget"],
                    exposure_limit=constraints["limit"],
                    strict=constraints["strict"],
                )
                new_validations[p_name] = val_res
            else:
                new_validations[p_name] = None

    st.session_state.results = new_results
    st.session_state.validations = new_validations
    st.session_state.last_inputs = current_inputs

# 5. Outdated Result Warning
is_outdated = (
    st.session_state.last_inputs is not None
    and st.session_state.last_inputs != current_inputs
    and bool(st.session_state.results)
)

if is_outdated:
    st.warning(
        "⚠️ **Input parameters or scenario selection have changed since last run.** "
        "The results below may be outdated. Click **'Generate & Validate Plan'** to refresh."
    )

# 6. Main Navigation Tabs
tab_planner, tab_manual, tab_about = st.tabs(
    [
        "🚀 Planner Execution & Compliance",
        "🧪 Manual Plan Validation",
        "📖 Domain & PEAS Architecture",
    ]
)

# ==========================================================
# TAB 1: Planner Execution & Compliance
# ==========================================================
with tab_planner:
    st.subheader(f"Scenario {scenario.id}: {scenario.title}")
    render_state_tables(scenario.init, scenario.goal)
    st.divider()

    results = st.session_state.results
    validations = st.session_state.validations

    if not results:
        st.info(
            "👈 Select a scenario in the sidebar, then click "
            "**'Generate & Validate Plan'** to begin."
        )

    else:
        if planner_choice == "Both":
            # Side-by-side layout
            col_bfs, col_pop = st.columns(2)

            with col_bfs:
                st.markdown("### 🔹 Baseline: Forward BFS")
                if "bfs" in results:
                    res_bfs = results["bfs"]
                    val_bfs = validations.get("bfs")
                    render_status_badge("BFS", res_bfs, val_bfs)
                    if res_bfs.plan and val_bfs:
                        render_compliance_panel(
                            val_bfs,
                            constraints["stock"],
                            constraints["budget"],
                            constraints["limit"],
                        )
                        with st.expander("Step-by-Step Action Sequence", expanded=True):
                            render_plan_table(res_bfs.plan, val_bfs)
                        render_graph_view("BFS", res_bfs, val_bfs)

            with col_pop:
                st.markdown("### 🔸 Advanced: Partial-Order Planner (POP)")
                if "pop" in results:
                    res_pop = results["pop"]
                    val_pop = validations.get("pop")
                    render_status_badge("POP", res_pop, val_pop)
                    if res_pop.plan and val_pop:
                        render_compliance_panel(
                            val_pop,
                            constraints["stock"],
                            constraints["budget"],
                            constraints["limit"],
                        )
                        with st.expander("Step-by-Step Action Sequence", expanded=True):
                            render_plan_table(res_pop.plan, val_pop)
                        render_graph_view("POP", res_pop, val_pop)

            st.divider()
            render_comparison_metrics(results, validations)

        else:
            chosen = planner_choice.lower()
            if chosen in results:
                res = results[chosen]
                val = validations.get(chosen)

                render_status_badge(planner_choice, res, val)
                if res.plan and val:
                    render_compliance_panel(
                        val,
                        constraints["stock"],
                        constraints["budget"],
                        constraints["limit"],
                    )
                    st.divider()
                    col_left, col_right = st.columns([1, 1])
                    with col_left:
                        st.subheader("Step-by-Step Plan")
                        render_plan_table(res.plan, val)
                    with col_right:
                        render_graph_view(planner_choice, res, val)

# ==========================================================
# TAB 2: Manual Plan Validation Testbed
# ==========================================================
with tab_manual:
    st.subheader("🧪 Manual Plan Validation Bench")
    st.markdown(
        "Directly test the validator against known edge-cases and deliberately invalid plans "
        "(e.g., skipping temperature verification, or sealing before inspection)."
    )

    scenarios = get_all_scenarios()
    manual_scen_key = st.selectbox(
        "Choose Reference Scenario Context",
        options=list(scenarios.keys()),
        index=0,
        key="manual_scen_select",
    )
    manual_scen = scenarios[manual_scen_key]

    broken_plans_dict = mock_broken_plans()
    preset_options = {
        "Reference S1 Plan (Valid 8 steps)": make_s1_actions(),
        "T2: Skip Temperature Verification (Missing temp_ok)": broken_plans_dict["t2_skip_verify"],
        "T3: Seal Before Inspect (Ordering threat violation)": broken_plans_dict[
            "t3_seal_before_inspect"
        ],
        "T4: Load Before Seal (Missing sealed)": broken_plans_dict["t4_load_before_seal"],
        "T5: Incomplete Plan (Missing goal loaded)": broken_plans_dict["t5_incomplete"],
        "Custom Empty Plan []": [],
    }

    selected_preset = st.selectbox(
        "Load Preset Action Sequence",
        options=list(preset_options.keys()),
        key="manual_preset_select",
    )
    active_test_plan = preset_options[selected_preset]

    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1:
        m_stock = st.number_input(
            "Dry Ice Stock", min_value=0, max_value=10, value=manual_scen.dry_ice_stock
        )
    with c_m2:
        m_budget = st.number_input(
            "Time Budget", min_value=1, max_value=120, value=manual_scen.time_budget
        )
    with c_m3:
        m_limit = st.number_input(
            "Exposure Limit", min_value=1, max_value=30, value=manual_scen.exposure_limit
        )

    if st.button("🔍 Validate Selected Sequence", type="primary", key="btn_manual_validate"):
        manual_val_res = validate(
            init=manual_scen.init,
            goal=manual_scen.goal,
            plan=active_test_plan,
            dry_ice_stock=m_stock,
            time_budget=m_budget,
            exposure_limit=m_limit,
            strict=True,
        )

        dummy_p_res = PlannerResult(
            planner="Manual",
            plan=active_test_plan,
            explored=0,
            time_s=0.0,
        )
        render_status_badge("Manual", dummy_p_res, manual_val_res)

        if active_test_plan:
            render_compliance_panel(manual_val_res, m_stock, m_budget, m_limit)
            col_m_plan, col_m_graph = st.columns([1, 1])
            with col_m_plan:
                st.markdown("**Sequence Details:**")
                render_plan_table(active_test_plan, manual_val_res)
            with col_m_graph:
                render_graph_view("Manual", dummy_p_res, manual_val_res)

# ==========================================================
# TAB 3: About & PEAS Architecture
# ==========================================================
with tab_about:
    st.subheader("Cold-Chain Logistics Domain Specification")

    st.markdown(
        """
        ### 📦 Operational Workflow
        Packages move strictly across directed physical locations:

        `receiving` $\\rightarrow$ `cold_room` $\\rightarrow$
        `inspection` $\\rightarrow$ `loading_dock`

        - **Ambient Locations**: `receiving`, `loading_dock` (accumulate exposure counter).
        - **Controlled Locations**: `cold_room`, `inspection` (resets exposure counter to 0).
        """
    )

    st.markdown("### 📋 PEAS Framework")
    st.table(
        {
            "Component": ["Performance", "Environment", "Actuators", "Sensors"],
            "Specification": [
                (
                    "Valid STRIPS plan; minimal unnecessary actions; zero temperature/time "
                    "breaches; minimal dry ice; goal reached."
                ),
                "Simulated distribution hub: receiving, cold room, inspection room, loading dock.",
                "verify_temp(P), move(P, A, B), pack_dry_ice(P), inspect(P), seal(P), load(P).",
                (
                    "Temperature status, package location (RFID), container integrity, "
                    "dry-ice quantity, elapsed time."
                ),
            ],
        }
    )

    st.markdown("### ⚙️ STRIPS Action Schemas")
    st.table(
        {
            "Action": [
                "verify_temp(P)",
                "move(P, A, B)",
                "pack_dry_ice(P)",
                "inspect(P)",
                "seal(P)",
                "load(P)",
            ],
            "Preconditions": [
                "at(P, receiving)",
                "at(P, A)",
                "at(P, cold_room), temp_ok(P), open(P)",
                "at(P, inspection), iced(P), open(P)",
                "inspected(P), open(P)",
                "at(P, loading_dock), sealed(P)",
            ],
            "Add Effects": [
                "temp_ok(P)",
                "at(P, B)",
                "iced(P)",
                "inspected(P)",
                "sealed(P)",
                "loaded(P)",
            ],
            "Delete Effects": [
                "—",
                "at(P, A)",
                "—",
                "—",
                "open(P)",
                "—",
            ],
            "Duration (t)": [2, 3, 4, 3, 2, 2],
            "Dry Ice": [0, 0, 1, 0, 0, 0],
        }
    )
