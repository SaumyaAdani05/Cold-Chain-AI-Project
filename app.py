"""
app.py - Streamlit user interface for the Cold-Chain AI Planning Project.

Beginner-friendly, guided, single-flow design.
Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import visualization as viz
from comparison import STATUS_LABELS, AlgorithmRun, compare_algorithms, comparison_rows, run_bfs, run_pop
from constraints import simulate_temperature_readings, temperature_violations
from scenarios import get_scenario, list_scenarios

# Optional: Prototype & Compliance Testbed (Saumya modules)
try:
    from adapter import PlannerResult, run_planner
    from ui.compare import render_comparison_metrics
    from ui.panels import (
        render_compliance_panel,
        render_graph_view,
        render_plan_table,
        render_state_tables,
        render_status_badge,
    )
    from ui.sidebar import render_sidebar as render_prototype_sidebar
    from validator import ValidationResult, validate

    PROTOTYPE_AVAILABLE = True
except Exception:
    PROTOTYPE_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cold-Chain AI Planner",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DISCLAIMER = (
    "⚠️ All temperatures, durations, dry-ice amounts and time budgets are "
    "**simulated assumptions for teaching purposes only**. This app does not certify "
    "compliance with any real pharmaceutical transport standard."
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS – subtle warm card style + step badges
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Softer background for metric cards */
    [data-testid="metric-container"] {
        background: #f0f8ff;
        border: 1px solid #c8dff5;
        border-radius: 10px;
        padding: 10px 14px;
    }
    /* Step badge */
    .step-badge {
        display: inline-block;
        background: #1f77b4;
        color: white;
        border-radius: 50%;
        width: 28px; height: 28px;
        text-align: center;
        line-height: 28px;
        font-weight: bold;
        margin-right: 8px;
    }
    /* Info box override */
    .stAlert { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
if "runs" not in st.session_state:
    st.session_state["runs"] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def store_runs(scenario_key: str, runs: list) -> None:
    """Persist the latest planner runs in session state."""
    bucket = st.session_state["runs"].setdefault(scenario_key, {})
    for run in runs:
        bucket[run.algorithm] = run


def show_status(run: AlgorithmRun) -> None:
    """Coloured banner summarising planner outcome."""
    text = f"**{run.algorithm}: {STATUS_LABELS[run.status]}.** {run.message}"
    if run.status == "valid":
        st.success(text)
    elif run.status == "rejected":
        st.warning(text)
    else:
        st.error(text)


def _plain_english_fact(fact: str) -> str:
    """Turn a STRIPS predicate string into something readable."""
    mapping = {
        "at_gate": "📦 Package is waiting at the receiving gate",
        "in_cold_room": "🥶 Package is inside the cold room (temperature safe)",
        "on_vehicle": "🚚 Package has been loaded onto the delivery vehicle",
        "checked": "✅ Package has passed temperature inspection",
        "dry_ice_applied": "🧊 Dry ice has been applied to this package",
        "delivered": "✔️ Package has been delivered",
    }
    for key, label in mapping.items():
        if key in fact:
            pkg = fact.split("(")[-1].rstrip(")")
            return f"{label} — *{pkg}*"
    return fact


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar: guided step-by-step controls
# ─────────────────────────────────────────────────────────────────────────────


def render_sidebar() -> tuple:
    """Render the guided sidebar and return (scenario, algorithm_choice)."""
    scenarios = list_scenarios()
    keys = [s.key for s in scenarios]

    with st.sidebar:
        st.image(
            "https://em-content.zobj.net/source/twitter/376/snowflake_2744-fe0f.png",
            width=56,
        )
        st.title("Cold-Chain AI Planner")
        st.caption("AI planning for vaccine cold-chain logistics")
        st.divider()

        # ── Step 1 ────────────────────────────────────────────────────────
        st.markdown('<span class="step-badge">1</span> **Pick a scenario**', unsafe_allow_html=True)
        selected_key = st.selectbox(
            "Scenario",
            keys,
            format_func=lambda k: get_scenario(k).title,
            help="Each scenario represents a different real-world cold-chain situation. "
            "Start with 'Normal Single Vaccine' if you are new.",
            label_visibility="collapsed",
        )
        scenario = get_scenario(selected_key)
        with st.expander("📄 What does this scenario involve?"):
            st.write(scenario.description)
            st.write(f"**Expected outcome:** {scenario.expected_outcome}")
            st.write(f"**What it teaches:** {scenario.lesson}")

        st.divider()

        # ── Step 2 ────────────────────────────────────────────────────────
        st.markdown('<span class="step-badge">2</span> **Choose a planner**', unsafe_allow_html=True)
        algo = st.radio(
            "Algorithm",
            ["BFS", "POP", "Both"],
            help=(
                "**BFS** (Breadth-First Search): Explores step-by-step in order, "
                "guaranteed to find the *shortest* plan. Great for small problems.\n\n"
                "**POP** (Partial-Order Planner): Finds which steps *must* happen before others "
                "and which can run in parallel. More flexible for complex schedules.\n\n"
                "**Both**: Run both and compare them side-by-side."
            ),
            label_visibility="collapsed",
        )

        st.divider()

        # ── Step 3 ────────────────────────────────────────────────────────
        st.markdown('<span class="step-badge">3</span> **Run the planner**', unsafe_allow_html=True)
        run_clicked = st.button(
            "▶ Run Planning",
            type="primary",
            use_container_width=True,
            help="Click to execute the selected planning algorithm on the chosen scenario.",
        )

        st.divider()
        st.info(DISCLAIMER, icon="⚠️")

    return scenario, algo, run_clicked


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 – 🚀 Run Planner  (main guided experience)
# ─────────────────────────────────────────────────────────────────────────────


def render_run_tab(scenario, algo: str, run_clicked: bool) -> None:

    # ── Welcome banner (first-time users) ─────────────────────────────────
    with st.expander("👋 New here? Start with this quick guide", expanded=False):
        st.markdown(
            """
            **What is this app?**
            This tool uses classical **AI planning** to automatically figure out the safest
            sequence of steps to move temperature-sensitive vaccine packages from a receiving
            gate to a delivery vehicle — without breaking the cold chain.

            **How does it work?**
            | Step | What you do | What the app does |
            |------|-------------|-------------------|
            | 1 | Pick a scenario (sidebar) | Loads packages, constraints & rules |
            | 2 | Choose BFS, POP or Both   | Selects the search algorithm |
            | 3 | Click ▶ Run Planning       | Finds a valid action sequence |
            | 4 | Read the results below     | Shows plan, metrics & validations |

            **Tip:** Try **"Normal Single Vaccine"** with **BFS** first — it's the simplest case!
            """
        )

    # ── Scenario summary card ──────────────────────────────────────────────
    st.markdown("## 📦 Selected Scenario")
    col_info, col_constraints = st.columns([3, 2])

    with col_info:
        st.markdown(f"### {scenario.title}")
        st.write(scenario.description)
        st.markdown(f"🎯 **Expected outcome:** `{scenario.expected_outcome}`")
        st.markdown(f"💡 **Teaches:** {scenario.lesson}")

    with col_constraints:
        c = scenario.constraints
        st.markdown("#### ⚙️ Constraints")
        st.metric(
            "⏱ Time budget", f"{c.max_duration_minutes} min", help="Total allowed time from gate to vehicle"
        )
        st.metric(
            "🧊 Dry ice available",
            f"{c.dry_ice_available_kg} kg",
            help="Total dry ice that can be used across all packages",
        )
        st.metric(
            "❄️ Dry ice per package",
            f"{c.dry_ice_per_package_kg} kg",
            help="How much dry ice each frozen package requires",
        )

    # ── Package details ────────────────────────────────────────────────────
    with st.expander("📋 Package Details & Temperature Readings", expanded=False):
        rows = []
        for pkg in scenario.packages:
            readings = simulate_temperature_readings(pkg)
            problems = temperature_violations(pkg, readings)
            rows.append(
                {
                    "Package": pkg.package_id,
                    "Description": pkg.label,
                    "Needs dry ice": "✅ Yes" if pkg.needs_dry_ice else "❌ No",
                    "Safe range (°C)": f"{pkg.temp_min_c} → {pkg.temp_max_c}",
                    "Simulated readings (°C)": ", ".join(str(r) for r in readings),
                    "Temp check": "✅ OK" if not problems else "🔴 OUT OF RANGE",
                }
            )
        st.dataframe(pd.DataFrame(rows).astype(str), hide_index=True, use_container_width=True)

    # ── Initial state & goal ───────────────────────────────────────────────
    with st.expander("🗂️ Initial State & Goal (what the planner sees)", expanded=False):
        problem = scenario.build_problem()
        left, right = st.columns(2)
        with left:
            st.markdown("**Initial State** — where everything starts")
            for fact in sorted(problem.initial_state):
                st.markdown(f"- {_plain_english_fact(fact)}")
        with right:
            st.markdown("**Goal State** — what must be true when the plan succeeds")
            for fact in sorted(problem.goal):
                st.markdown(f"- {_plain_english_fact(fact)}")

    # ── Available actions ──────────────────────────────────────────────────
    with st.expander("🔧 Available Actions (what the planner can do)", expanded=False):
        action_rows = []
        for action in problem.actions:
            action_rows.append(
                {
                    "Action": action.name,
                    "Duration (min)": action.duration,
                    "Dry ice used (kg)": action.dry_ice_cost,
                    "Preconditions": ", ".join(sorted(action.preconditions)) or "none",
                    "Adds": ", ".join(sorted(action.add_effects)) or "none",
                    "Removes": ", ".join(sorted(action.delete_effects)) or "none",
                }
            )
        st.dataframe(pd.DataFrame(action_rows).astype(str), hide_index=True, use_container_width=True)
        st.caption(
            "Preconditions = facts that must be true *before* the action can run. "
            "Adds / Removes = facts that become true / false *after* the action."
        )

    st.divider()

    # ── Execute planner when button clicked ───────────────────────────────
    if run_clicked:
        if algo == "BFS":
            with st.spinner("🔍 BFS is searching step-by-step for the shortest plan…"):
                store_runs(scenario.key, [run_bfs(scenario)])
        elif algo == "POP":
            with st.spinner("🔀 POP is building an optimal partial-order plan…"):
                store_runs(scenario.key, [run_pop(scenario)])
        else:
            with st.spinner("⚙️ Running both BFS and POP — this may take a moment…"):
                runs = compare_algorithms(scenario)
                store_runs(scenario.key, runs)
                st.session_state["last_comparison"] = (scenario.key, comparison_rows(runs))

    # ── Results ────────────────────────────────────────────────────────────
    runs = st.session_state["runs"].get(scenario.key, {})
    if not runs:
        st.info(
            "👈 Use the sidebar to pick a scenario and algorithm, then click **▶ Run Planning**.",
            icon="ℹ️",
        )
        return

    st.markdown("## 📊 Results")

    for name in ("BFS", "POP"):
        if name not in runs:
            continue
        run = runs[name]

        label = "🔵 BFS — Breadth-First Search" if name == "BFS" else "🟠 POP — Partial-Order Planner"
        with st.container(border=True):
            st.markdown(f"### {label}")
            show_status(run)

            # Metrics row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric(
                "⏱ Planning time",
                f"{run.elapsed_seconds * 1000:.1f} ms",
                help="Wall-clock time the algorithm took to find a plan",
            )
            m2.metric(
                "🔎 States explored",
                str(run.explored),
                help="Number of states the algorithm examined before finding a plan",
            )
            m3.metric(
                "📋 Plan length",
                str(run.plan_length) if run.success else "—",
                help="Number of actions in the plan",
            )
            m4.metric(
                "⏰ Total duration",
                f"{run.sequential_minutes} min" if run.success else "—",
                help="Sum of action durations — total time the plan takes",
            )
            m5.metric(
                "🧊 Dry ice used",
                f"{run.dry_ice_kg} kg" if run.success else "—",
                help="Total dry ice consumed by the plan",
            )

            if run.actions:
                st.markdown("#### 🗒️ Step-by-Step Plan")
                st.caption(
                    "Each row is one action the system must perform, in order. "
                    "Cumulative time and dry ice let you check the constraints at a glance."
                )
                seq_rows = []
                elapsed = 0
                dry_ice = 0
                for idx, action in enumerate(run.actions, start=1):
                    elapsed += action.duration
                    dry_ice += action.dry_ice_cost
                    seq_rows.append(
                        {
                            "Step": idx,
                            "Action": action.name,
                            "Duration (min)": action.duration,
                            "Cumulative time (min)": elapsed,
                            "Cumulative dry ice (kg)": dry_ice,
                        }
                    )
                st.dataframe(pd.DataFrame(seq_rows).astype(str), hide_index=True, use_container_width=True)

            if run.partial_plan is not None:
                plan = run.partial_plan
                with st.expander("🔗 Causal Links (which action depends on which)", expanded=False):
                    st.caption(
                        "A causal link means: 'Action A must run before Action B because A "
                        "produces the fact that B needs.' These links prevent the planner from "
                        "reordering steps in an unsafe way."
                    )
                    link_rows = [
                        {
                            "Producer action": lk.producer,
                            "Provides condition": lk.condition,
                            "To consumer action": lk.consumer,
                        }
                        for lk in plan.links
                    ]
                    st.dataframe(
                        pd.DataFrame(link_rows).astype(str), hide_index=True, use_container_width=True
                    )
                with st.expander("📐 Ordering Constraints (which steps must come first)", expanded=False):
                    order_rows = [{"Must happen first": a, "Before": b} for a, b in plan.reduced_orderings()]
                    if order_rows:
                        st.dataframe(
                            pd.DataFrame(order_rows).astype(str),
                            hide_index=True,
                            use_container_width=True,
                        )
                    free = len(plan.independent_pairs())
                    st.success(
                        f"✅ **{free}** step pair(s) are completely independent — they can run in any order!"
                    )

            # Validation
            st.markdown("#### 🛡️ Plan Validation")
            if run.validation is None:
                st.write("No plan to validate.")
            else:
                report = run.validation
                v1, v2, v3, v4 = st.columns(4)
                v1.metric(
                    "Preconditions OK",
                    "✅ Yes" if not report.precondition_failures else "❌ No",
                    help="Were all preconditions satisfied at every step?",
                )
                v2.metric(
                    "Goal achieved",
                    "✅ Yes" if report.goal_achieved else "❌ No",
                    help="Did the plan reach the goal state?",
                )
                v3.metric(
                    "Time used",
                    f"{report.total_duration} / {scenario.constraints.max_duration_minutes} min",
                    help="Time consumed vs. time budget",
                )
                v4.metric(
                    "Dry ice used",
                    f"{report.dry_ice_used_kg} / {scenario.constraints.dry_ice_available_kg} kg",
                    help="Dry ice consumed vs. available stock",
                )
                if report.all_problems:
                    st.error("⚠️ Constraint violations found:")
                    for prob in report.all_problems:
                        st.write(f"  - {prob}")
                else:
                    st.success("🎉 All validation checks passed — the plan is safe and feasible!")

            # Graphs
            if run.actions or run.partial_plan is not None:
                with st.expander("📈 Visualisations", expanded=False):
                    st.caption(
                        "These diagrams show *how* the plan is structured. "
                        "If the graph doesn't render, Graphviz is not installed on this machine — "
                        "the DOT source code is shown instead so you can paste it at graphviz.online."
                    )
                    if run.actions:
                        st.markdown("**Action sequence graph** — arrows show the order of steps")
                        st.graphviz_chart(viz.action_sequence_graph(run.actions).source)
                        st.markdown("**State transition graph** — each node is a world state")
                        st.graphviz_chart(
                            viz.state_transition_graph(scenario.build_problem(), run.actions).source
                        )
                        st.markdown("**Dependency graph** — which actions depend on each other")
                        st.graphviz_chart(viz.dependency_graph(run.actions).source)
                    if run.partial_plan is not None:
                        st.markdown("**Causal link graph** — coloured edges show causal dependencies")
                        st.graphviz_chart(viz.causal_link_graph(run.partial_plan).source)
                        st.markdown("**Ordering constraint graph** — dashed edges show ordering constraints")
                        st.graphviz_chart(viz.ordering_constraint_graph(run.partial_plan).source)

    # ── Comparison table (Both) ────────────────────────────────────────────
    comparison = st.session_state.get("last_comparison")
    if comparison and comparison[0] == scenario.key and algo == "Both":
        with st.container(border=True):
            st.markdown("### ⚖️ BFS vs POP — Side-by-Side Comparison")
            st.caption(
                "BFS explores states one-by-one and guarantees the shortest *total-order* plan. "
                "POP focuses on causal dependencies and may discover that some steps can run in parallel, "
                "giving a shorter *parallel makespan* even if the step count is similar."
            )
            st.dataframe(pd.DataFrame(comparison[1]).astype(str), hide_index=True, use_container_width=True)
            st.info(
                "💡 'Explored' means different things for each algorithm: "
                "BFS counts **states visited**, POP counts **flaws resolved**.",
                icon="💡",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 – 🧪 Validate / Prototype Testbed
# ─────────────────────────────────────────────────────────────────────────────


def render_validate_tab() -> None:
    if not PROTOTYPE_AVAILABLE:
        st.error(
            "The Prototype & Compliance Testbed modules could not be loaded. "
            "Make sure `adapter.py`, `validator.py` and `ui/` are present."
        )
        return

    st.markdown("## 🧪 Prototype & Compliance Testbed")
    st.write(
        "This tab lets you adjust constraint sliders (dry-ice stock, time budget, exposure limit) "
        "and immediately see how they affect plan feasibility and compliance."
    )

    # Reuse the prototype sidebar
    if "results" not in st.session_state:
        st.session_state.results = {}
    if "validations" not in st.session_state:
        st.session_state.validations = {}

    scenario, planner_choice, constraints, generate_clicked = render_prototype_sidebar()

    if generate_clicked:
        planners_to_run = ["bfs", "pop"] if planner_choice == "Both" else [planner_choice.lower()]
        new_results: dict[str, PlannerResult] = {}
        new_validations: dict[str, ValidationResult] = {}

        with st.spinner("⚙️ Running planners and validating action sequences…"):
            for p_name in planners_to_run:
                res = run_planner(p_name, scenario, timeout_s=30.0)
                new_results[p_name] = res
                if res.plan is not None:
                    new_validations[p_name] = validate(
                        init=scenario.init,
                        goal=scenario.goal,
                        plan=res.plan,
                        dry_ice_stock=constraints["stock"],
                        time_budget=constraints["budget"],
                        exposure_limit=constraints["limit"],
                        strict=constraints["strict"],
                    )
                else:
                    new_validations[p_name] = None

        st.session_state.results = new_results
        st.session_state.validations = new_validations

    sub_plan, sub_manual, sub_about = st.tabs(
        ["🚀 Planner Execution & Compliance", "🧪 Manual Plan Validation", "📖 Domain & PEAS Architecture"]
    )

    with sub_plan:
        st.subheader(f"Scenario {scenario.id}: {scenario.title}")
        render_state_tables(scenario.init, scenario.goal)
        st.divider()

        results = st.session_state.results
        validations = st.session_state.validations

        if not results:
            st.info(
                "👈 Adjust constraints in the sidebar and click **'🚀 Generate & Validate Plan'** to begin.",
                icon="ℹ️",
            )
        else:
            if planner_choice == "Both":
                col_bfs, col_pop = st.columns(2)
                with col_bfs:
                    st.markdown("### 🔵 BFS — Baseline Forward Search")
                    if "bfs" in results:
                        res_bfs = results["bfs"]
                        val_bfs = validations.get("bfs")
                        render_status_badge("BFS", res_bfs, val_bfs)
                        if res_bfs.plan and val_bfs:
                            render_compliance_panel(
                                val_bfs, constraints["stock"], constraints["budget"], constraints["limit"]
                            )
                            with st.expander("Step-by-Step Plan", expanded=True):
                                render_plan_table(res_bfs.plan, val_bfs)
                            render_graph_view("BFS", res_bfs, val_bfs)
                with col_pop:
                    st.markdown("### 🟠 POP — Partial-Order Planner")
                    if "pop" in results:
                        res_pop = results["pop"]
                        val_pop = validations.get("pop")
                        render_status_badge("POP", res_pop, val_pop)
                        if res_pop.plan and val_pop:
                            render_compliance_panel(
                                val_pop, constraints["stock"], constraints["budget"], constraints["limit"]
                            )
                            with st.expander("Step-by-Step Plan", expanded=True):
                                render_plan_table(res_pop.plan, val_pop)
                            render_graph_view("POP", res_pop, val_pop)
                st.divider()
                render_comparison_metrics(results, validations)
            else:
                p = planner_choice.lower()
                if p in results:
                    res = results[p]
                    val = validations.get(p)
                    render_status_badge(planner_choice, res, val)
                    if res.plan and val:
                        render_compliance_panel(
                            val, constraints["stock"], constraints["budget"], constraints["limit"]
                        )
                        with st.expander("Step-by-Step Plan", expanded=True):
                            render_plan_table(res.plan, val)
                        render_graph_view(planner_choice, res, val)

    with sub_manual:
        st.info("Manual plan entry and validation coming soon.", icon="🚧")

    with sub_about:
        _render_learn_tab()


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 – 📖 Learn: Domain & PEAS
# ─────────────────────────────────────────────────────────────────────────────


def _render_learn_tab() -> None:
    st.markdown("## 📖 Understand the Domain")

    # PEAS
    with st.expander("🤖 PEAS Architecture — What kind of AI agent is this?", expanded=False):
        st.markdown(
            """
            **PEAS** stands for **Performance, Environment, Actuators, Sensors** — the standard
            framework for describing an AI agent.

            | Component | Description |
            |-----------|-------------|
            | **Performance** | Deliver all packages safely within time and dry-ice budget |
            | **Environment** | Cold-room, ambient area, delivery vehicle, temperature sensors |
            | **Actuators** | Move to cold room, apply dry ice, load on vehicle, verify temperature |
            | **Sensors** | Current location of each package, temperature readings, dry-ice stock level |

            This is a **goal-based, deterministic, fully observable** agent operating in a
            **static, discrete** environment — a classic STRIPS planning domain.
            """
        )

    # Glossary
    with st.expander("📗 Glossary — What do these terms mean?", expanded=False):
        glossary = {
            "STRIPS": (
                "Stanford Research Institute Problem Solver — a formal language for describing "
                "planning problems. Each action has *preconditions* (what must be true before) "
                "and *effects* (what changes after)."
            ),
            "BFS (Breadth-First Search)": (
                "A graph-search algorithm that explores all actions at depth 1 before depth 2, "
                "and so on. It is *complete* (always finds a plan if one exists) and finds the "
                "*shortest* plan, but can be slow on large problems."
            ),
            "POP (Partial-Order Planning)": (
                "Instead of committing to a fixed sequence, POP builds a set of *ordering "
                "constraints* and *causal links*. Steps that do not causally depend on each other "
                "remain unordered — a human operator can run them in parallel."
            ),
            "Causal Link": (
                "A link `A →[condition]→ B` means: action A *produces* the fact that action B "
                "*requires*. If you remove A, B can no longer run safely."
            ),
            "Precondition": (
                "A fact that must be true in the current world state *before* an action can be "
                "legally executed."
            ),
            "Cold chain": (
                "An unbroken series of storage and distribution activities that maintain a "
                "product within a specified low-temperature range."
            ),
            "Dry ice": (
                "Solid CO₂ at −78.5 °C used to keep ultra-cold vaccines (e.g. mRNA) frozen "
                "during transport. This app models it as a consumable resource."
            ),
            "Exposure limit": (
                "The maximum time (in minutes) a package may remain outside a temperature-"
                "controlled zone before it is considered at risk."
            ),
        }
        for term, definition in glossary.items():
            st.markdown(f"**{term}**")
            st.write(definition)
            st.markdown("---")

    # Scenario overview table
    with st.expander("🗂️ All Scenarios at a Glance", expanded=False):
        rows = []
        for item in list_scenarios():
            rows.append(
                {
                    "Scenario": item.title,
                    "Packages": len(item.packages),
                    "Time budget (min)": item.constraints.max_duration_minutes,
                    "Dry ice (kg)": item.constraints.dry_ice_available_kg,
                    "Expected outcome": item.expected_outcome,
                    "What it teaches": item.lesson,
                }
            )
        st.dataframe(pd.DataFrame(rows).astype(str), hide_index=True, use_container_width=True)

    # Tips for first-time users
    with st.expander("🌟 Tips for Exploring the App", expanded=True):
        tips = [
            "**Start simple** — select *Normal Single Vaccine* + *BFS* and click Run Planning.",
            "**Compare algorithms** — switch to *Both* to see how BFS and POP differ.",
            "**Break the plan** — try *Temperature Verification Failure* to see the validator in action.",
            "**Change constraints** — in the 🧪 Validate tab set dry-ice stock to 0 and re-run.",
            "**Read causal links** — in a POP result, expand Causal Links and trace each dependency.",
        ]
        for i, tip in enumerate(tips, start=1):
            st.markdown(f"{i}. {tip}")


def render_learn_tab() -> None:
    _render_learn_tab()


# ─────────────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    # Sidebar controls (always visible)
    scenario, algo, run_clicked = render_sidebar()

    # App header
    st.markdown(
        """
        <h1 style='margin-bottom:0'>🧊 Cold-Chain AI Planning System</h1>
        <p style='color:grey; margin-top:4px'>
        Automated logistics planning for temperature-sensitive pharmaceutical distribution
        using classical AI (STRIPS · BFS · Partial-Order Planning)
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Top-level tabs
    tab_run, tab_validate, tab_learn = st.tabs(
        ["🚀 Run Planner", "🧪 Validate / Testbed", "📖 Learn & Glossary"]
    )

    with tab_run:
        render_run_tab(scenario, algo, run_clicked)

    with tab_validate:
        render_validate_tab()

    with tab_learn:
        render_learn_tab()


main()
