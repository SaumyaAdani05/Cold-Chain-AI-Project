"""Sidebar components for scenario selection, planner configuration, and execution parameters.

Conforms to PRD.md FR-U1 and ARCHITECTURE.md section 7.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from tests.fixtures.stubs import Scenario
from ui.scenarios import get_all_scenarios


def render_sidebar() -> tuple[Scenario, str, dict[str, Any], bool]:
    """Render the sidebar controls and return the active configuration.

    Returns:
        tuple containing:
        - active Scenario
        - planner selection ("BFS", "POP", or "Both")
        - constraint overrides (stock, budget, limit, strict)
        - generate_clicked flag
    """
    st.sidebar.title("❄️ Cold-Chain AI Planner")
    st.sidebar.markdown(
        "Automated planning and validation for temperature-sensitive pharmaceutical distribution."
    )
    st.sidebar.divider()

    scenarios = get_all_scenarios()
    scenario_keys = list(scenarios.keys())

    # Scenario selection
    scenario_choice = st.sidebar.selectbox(
        "Select Scenario",
        options=scenario_keys,
        format_func=lambda k: f"{k}: {scenarios[k].title}",
        help="Select a cold-chain operational scenario (S1-S5).",
        key="scenario_select",
    )
    base_scenario = scenarios[scenario_choice]

    # Planner selection
    planner_choice = st.sidebar.radio(
        "Planner Algorithm",
        options=["BFS", "POP", "Both"],
        help="Select planner: Forward BFS, Partial-Order Planner (POP), or Both.",
        key="planner_select",
    )

    st.sidebar.subheader("Constraint Parameters")

    # Sliders initialized with scenario defaults
    stock_override = st.sidebar.slider(
        "Dry-Ice Stock (units)",
        min_value=0,
        max_value=10,
        value=base_scenario.dry_ice_stock,
        help="Maximum units of dry ice available at the distribution hub.",
        key="stock_slider",
    )

    budget_override = st.sidebar.slider(
        "Time Budget (time units)",
        min_value=5,
        max_value=120,
        value=base_scenario.time_budget,
        help="Maximum allowable total time for the action sequence.",
        key="budget_slider",
    )

    limit_override = st.sidebar.slider(
        "Exposure Limit (time units)",
        min_value=1,
        max_value=30,
        value=base_scenario.exposure_limit,
        help="Maximum time a package can remain in ambient locations without cold-room return.",
        key="limit_slider",
    )

    strict_mode = st.sidebar.checkbox(
        "Strict Validation Mode",
        value=False,
        help="Flags redundant or superfluous actions as warnings.",
        key="strict_checkbox",
    )

    st.sidebar.divider()
    generate_clicked = st.sidebar.button(
        "🚀 Generate & Validate Plan",
        type="primary",
        use_container_width=True,
        key="btn_generate",
    )

    # Active scenario with updated constraints
    active_scenario = Scenario(
        id=base_scenario.id,
        title=base_scenario.title,
        init=base_scenario.init,
        goal=base_scenario.goal,
        actions=base_scenario.actions,
        dry_ice_stock=stock_override,
        time_budget=budget_override,
        exposure_limit=limit_override,
        expected=base_scenario.expected,
    )

    constraints = {
        "stock": stock_override,
        "budget": budget_override,
        "limit": limit_override,
        "strict": strict_mode,
    }

    return active_scenario, planner_choice, constraints, generate_clicked
