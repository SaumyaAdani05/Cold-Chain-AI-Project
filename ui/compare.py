"""Side-by-side comparison module for BFS vs POP planners.

Conforms to PRD.md FR-U8 and ARCHITECTURE.md section 7.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from adapter import PlannerResult
    from validator import ValidationResult


def build_comparison_dataframe(
    results: dict[str, PlannerResult],
    val_results: dict[str, ValidationResult],
) -> pd.DataFrame:
    """Construct metrics comparison DataFrame from execution and validation results."""
    metrics_data = []

    for name in ["bfs", "pop"]:
        if name in results:
            res = results[name]
            val = val_results.get(name)

            plan_found = res.plan is not None
            plan_len = len(res.plan) if res.plan else 0
            violations_count = len(val.violations) if val else 0
            is_valid = val.valid if val else False
            total_time = val.total_time if val else 0
            dry_ice = val.dry_ice_used if val else 0
            max_exp = val.max_exposure if val else 0

            metrics_data.append(
                {
                    "Planner": name.upper(),
                    "Status": "✅ Valid"
                    if is_valid
                    else ("⚠️ No Plan" if not plan_found else "❌ Invalid"),
                    "Planning Time (s)": round(res.time_s, 4),
                    "Plan Length": plan_len,
                    "Explored States/Nodes": res.explored,
                    "Violations Count": violations_count,
                    "Total Action Time": total_time,
                    "Dry Ice Used": dry_ice,
                    "Max Exposure": max_exp,
                }
            )

    return pd.DataFrame(metrics_data)


def render_comparison_metrics(
    results: dict[str, PlannerResult],
    val_results: dict[str, ValidationResult],
) -> None:
    """Render metrics comparison table with CSV export."""
    st.subheader("📊 Planner Performance Comparison")
    df = build_comparison_dataframe(results, val_results)

    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Comparison Metrics CSV",
            data=csv_data,
            file_name="planner_comparison_metrics.csv",
            mime="text/csv",
            key="dl_compare_csv",
        )
    else:
        st.info("No comparative results generated yet.")
