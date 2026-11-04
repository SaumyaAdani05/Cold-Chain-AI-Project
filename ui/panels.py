"""UI panel components for state inspection, status badges, plan steps, and compliance tracking.

Conforms to PRD.md FR-U2, FR-U4, FR-U5, FR-U6, FR-U7, FR-U9, FR-U12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st

from viz import export_dot, plan_to_dot, pop_to_dot, render_png_safe

if TYPE_CHECKING:
    from adapter import PlannerResult
    from validator import ValidationResult


def render_state_tables(init: frozenset[str], goal: frozenset[str]) -> None:
    """Render initial-state and goal fact tables (FR-U2)."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Initial State Facts:**")
        sorted_init = sorted(init)
        if sorted_init:
            df_init = pd.DataFrame({"Initial Fact": sorted_init})
            st.dataframe(df_init, use_container_width=True, hide_index=True)
        else:
            st.info("Initial state is empty.")

    with col2:
        st.markdown("**Goal State Facts:**")
        sorted_goal = sorted(goal)
        if sorted_goal:
            df_goal = pd.DataFrame({"Goal Fact": sorted_goal})
            st.dataframe(df_goal, use_container_width=True, hide_index=True)
        else:
            st.info("Goal state is empty.")


def render_status_badge(
    planner_name: str,
    result: PlannerResult,
    val_res: ValidationResult | None,
) -> None:
    """Render validation and planning outcome badges (FR-U5)."""
    if result.timed_out:
        st.warning(f"⏱️ **{planner_name.upper()}**: Timed Out after {result.time_s:.1f}s")
        return

    if result.error:
        st.error(f"❌ **{planner_name.upper()} Error**: {result.error}")
        return

    if result.plan is None:
        st.warning(
            f"⚠️ **{planner_name.upper()}**: No valid plan found. "
            f"(Explored: {result.explored} states, Time: {result.time_s:.3f}s)"
        )
        return

    if val_res is None:
        st.info("Plan generated. Awaiting validation...")
        return

    if val_res.valid:
        st.success(
            f"✅ **{planner_name.upper()} Plan Validated Successfully** "
            f"({val_res.plan_length} steps, {val_res.total_time} time units, "
            f"{val_res.dry_ice_used} dry-ice units)"
        )
        if val_res.warnings:
            for w in val_res.warnings:
                st.warning(f"⚠️ Warning: {w}")
    else:
        st.error(f"❌ **{planner_name.upper()} Plan Validation Failed**")
        st.markdown(f"**Found {len(val_res.violations)} violation(s):**")
        for v in val_res.violations:
            loc_str = f"Step {v.step}" if v.step is not None else "Global"
            act_str = f" ({v.action})" if v.action else ""
            st.markdown(f"- 🔴 **[{v.kind}]** {loc_str}{act_str}: {v.message}")


def render_plan_table(
    plan: list[Any],
    val_res: ValidationResult | None = None,
) -> None:
    """Render the action sequence as a structured table with step metrics (FR-U4)."""
    if not plan:
        st.info("No plan steps to display.")
        return

    violating_steps = set()
    if val_res:
        for v in val_res.violations:
            if v.step is not None:
                violating_steps.add(v.step)

    rows = []
    cum_time = 0
    cum_ice = 0
    for i, action in enumerate(plan, 1):
        name = getattr(action, "name", str(action))
        dur = getattr(action, "duration", 1)
        ice = getattr(action, "dry_ice", 0)
        pkg = getattr(action, "pkg", "")
        cum_time += dur
        cum_ice += ice

        status_icon = "❌" if i in violating_steps else "✅"
        rows.append(
            {
                "Step": f"{i} {status_icon}",
                "Action": name,
                "Package": pkg,
                "Duration": dur,
                "Cumulative Time": cum_time,
                "Dry Ice": ice,
                "Cumulative Ice": cum_ice,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_compliance_panel(
    val_res: ValidationResult,
    stock: int | None,
    budget: int | None,
    limit: int | None,
) -> None:
    """Render Cold-Chain Compliance metrics cards (FR-U6)."""
    st.subheader("Cold-Chain Compliance Tracking")
    c1, c2, c3, c4 = st.columns(4)

    # 1. Goal satisfaction
    has_goal_violation = any(v.kind == "GOAL" for v in val_res.violations)
    goal_ok = not has_goal_violation
    with c1:
        st.metric(
            label="Goal Satisfied",
            value="✅ Yes" if goal_ok else "❌ No",
            delta="Complete" if goal_ok else "Unsatisfied",
            delta_color="normal" if goal_ok else "inverse",
        )

    # 2. Total time vs budget
    time_limit_str = f"/ {budget}" if budget is not None else ""
    time_ok = budget is None or val_res.total_time <= budget
    with c2:
        st.metric(
            label="Total Time Elapsed",
            value=f"{val_res.total_time} {time_limit_str}",
            delta="Within Budget" if time_ok else "Budget Exceeded",
            delta_color="normal" if time_ok else "inverse",
        )

    # 3. Dry-ice usage vs stock
    stock_str = f"/ {stock}" if stock is not None else ""
    ice_ok = stock is None or val_res.dry_ice_used <= stock
    with c3:
        st.metric(
            label="Dry Ice Consumed",
            value=f"{val_res.dry_ice_used} {stock_str}",
            delta="Stock OK" if ice_ok else "Depleted",
            delta_color="normal" if ice_ok else "inverse",
        )

    # 4. Temperature exposure
    exp_limit_str = f"/ {limit}" if limit is not None else ""
    exp_ok = limit is None or val_res.max_exposure <= limit
    with c4:
        st.metric(
            label="Worst Exposure",
            value=f"{val_res.max_exposure} {exp_limit_str}",
            delta="Safe" if exp_ok else "Limit Breached",
            delta_color="normal" if exp_ok else "inverse",
        )


def render_graph_view(
    planner_name: str,
    result: PlannerResult,
    val_res: ValidationResult | None,
) -> None:
    """Render the Graphviz interactive diagram with export options (FR-U7, FR-U9, FR-U12)."""
    if result.plan is None:
        return

    st.subheader(f"Plan Structure: {planner_name.upper()}")

    # Build appropriate Digraph
    if planner_name.lower() == "pop" and result.pop is not None:
        dot = pop_to_dot(result.pop, result=val_res, title=f"POP Causal Graph ({len(result.plan)} steps)")
    else:
        dot = plan_to_dot(result.plan, result=val_res, title=f"{planner_name.upper()} Linear Plan")

    # Display Graph
    try:
        st.graphviz_chart(dot, use_container_width=True)
    except Exception as e:
        st.warning(f"Graphviz interactive render issue: {e}")
        st.code(export_dot(dot), language="dot")

    # Export & Downloads
    dot_source = export_dot(dot)
    png_bytes = render_png_safe(dot)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label=f"📥 Download {planner_name.upper()} DOT Source",
            data=dot_source,
            file_name=f"{planner_name.lower()}_plan.dot",
            mime="text/vnd.graphviz",
            key=f"dl_dot_{planner_name}",
        )

    with col2:
        if png_bytes is not None:
            st.download_button(
                label=f"📥 Download {planner_name.upper()} Graph PNG",
                data=png_bytes,
                file_name=f"{planner_name.lower()}_plan.png",
                mime="image/png",
                key=f"dl_png_{planner_name}",
            )
        else:
            st.caption(
                "💡 *PNG export requires the system Graphviz binary (`dot`) installed on PATH. "
                "DOT source is available above.*"
            )
