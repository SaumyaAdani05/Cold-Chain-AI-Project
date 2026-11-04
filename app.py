"""
app.py - Streamlit user interface for the Cold-Chain AI planning project.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

import visualization as viz
from comparison import STATUS_LABELS, AlgorithmRun, compare_algorithms, comparison_rows, run_bfs, run_pop
from constraints import simulate_temperature_readings, temperature_violations
from scenarios import get_scenario, list_scenarios

st.set_page_config(page_title="Cold-Chain AI Planner", page_icon="🧊", layout="wide")

DISCLAIMER = ("All temperatures, durations, dry-ice amounts and time budgets in this app are "
              "**simulated assumptions for teaching**. They are not validated pharmaceutical "
              "transport standards, and the app does not certify compliance with anything.")


def store_runs(scenario_key: str, runs) -> None:
    """Keep the latest run of each algorithm for each scenario."""
    bucket = st.session_state["runs"].setdefault(scenario_key, {})
    for run in runs:
        bucket[run.algorithm] = run


def show_status(run: AlgorithmRun) -> None:
    """Coloured banner with the planner's status."""
    text = f"**{run.algorithm}: {STATUS_LABELS[run.status]}.** {run.message}"
    if run.status == "valid":
        st.success(text)
    elif run.status == "rejected":
        st.warning(text)
    else:
        st.error(text)


def render_dashboard(scenario) -> None:
    st.title("Automated Cold-Chain Logistics Planning")
    st.caption("Perishable pharmaceuticals - Classical AI (STRIPS, BFS, Partial-Order Planning)")
    st.markdown(
        "This application plans the sequence of operations that moves vaccine packages from the "
        "gate to a delivery vehicle. Each operation has preconditions and effects. Two planners "
        "search for a valid plan: a **breadth-first search** that finds a total order, and a "
        "**partial-order planner** that finds ordering constraints and causal links. An independent "
        "validator then checks temperature, time and dry-ice constraints."
    )
    st.info(DISCLAIMER)

    st.subheader("Project workflow")
    steps = [
        ("1. Select", "Choose a scenario in the sidebar."),
        ("2. Inspect", "Read the initial state, goal, actions and constraints."),
        ("3. Plan", "Run BFS, POP, or both on the Planning Engine tab."),
        ("4. Validate", "The validator replays each plan and checks constraints."),
        ("5. Visualise", "Look at the action sequence, state transitions, causal links and ordering."),
    ]
    columns = st.columns(len(steps))
    for column, (heading, text) in zip(columns, steps):
        column.markdown(f"**{heading}**\n\n{text}")

    st.subheader("Scenarios")
    rows = []
    for item in list_scenarios():
        rows.append({
            "Scenario": item.title,
            "Packages": len(item.packages),
            "Time budget (min)": item.constraints.max_duration_minutes,
            "Dry ice (kg)": item.constraints.dry_ice_available_kg,
            "Expected outcome": item.expected_outcome,
            "What it shows": item.lesson,
        })
    st.dataframe(pd.DataFrame(rows).astype(str), hide_index=True)
    st.markdown(f"**Selected scenario:** {scenario.title}. {scenario.description}")


def render_scenario_details(scenario) -> None:
    problem = scenario.build_problem()
    constraints = scenario.constraints

    st.header(scenario.title)
    st.write(scenario.description)

    left, right = st.columns(2)
    with left:
        st.subheader("Initial state")
        st.code("\n".join(sorted(problem.initial_state)), language=None)
    with right:
        st.subheader("Goal state")
        st.code("\n".join(sorted(problem.goal)), language=None)

    st.subheader("Constraints")
    m1, m2, m3 = st.columns(3)
    m1.metric("Time budget", f"{constraints.max_duration_minutes} min")
    m2.metric("Dry ice in stock", f"{constraints.dry_ice_available_kg} kg")
    m3.metric("Dry ice per package", f"{constraints.dry_ice_per_package_kg} kg")

    st.markdown("**Packages and simulated temperature readings**")
    package_rows = []
    for pkg in scenario.packages:
        readings = simulate_temperature_readings(pkg)
        problems = temperature_violations(pkg, readings)
        package_rows.append({
            "Package": pkg.package_id,
            "Description": pkg.label,
            "Needs dry ice": "yes" if pkg.needs_dry_ice else "no",
            "Acceptable range (°C)": f"{pkg.temp_min_c} to {pkg.temp_max_c}",
            "Simulated readings (°C)": ", ".join(str(r) for r in readings),
            "Temperature check": "OK" if not problems else "OUT OF RANGE",
        })
    st.dataframe(pd.DataFrame(package_rows).astype(str), hide_index=True)

    st.subheader("Available actions")
    action_rows = []
    for action in problem.actions:
        action_rows.append({
            "Action": action.name,
            "Preconditions": ", ".join(sorted(action.preconditions)) or "-",
            "Add effects": ", ".join(sorted(action.add_effects)) or "-",
            "Delete effects": ", ".join(sorted(action.delete_effects)) or "-",
            "Duration (min)": action.duration,
            "Dry ice (kg)": action.dry_ice_cost,
        })
    st.dataframe(pd.DataFrame(action_rows).astype(str), hide_index=True)


def render_planning_engine(scenario) -> None:
    st.header("Planning engine")
    st.write("Run a planner on the selected scenario. Results appear below and on the Results tab.")

    b1, b2, b3 = st.columns(3)
    run_bfs_clicked = b1.button("Generate BFS Plan", type="primary")
    run_pop_clicked = b2.button("Generate POP Plan", type="primary")
    compare_clicked = b3.button("Compare Both Algorithms", type="primary")

    if run_bfs_clicked:
        with st.spinner("Running breadth-first search..."):
            store_runs(scenario.key, [run_bfs(scenario)])
    if run_pop_clicked:
        with st.spinner("Running partial-order planning..."):
            store_runs(scenario.key, [run_pop(scenario)])
    if compare_clicked:
        with st.spinner("Running both planners..."):
            runs = compare_algorithms(scenario)
            store_runs(scenario.key, runs)
            st.session_state["last_comparison"] = (scenario.key, comparison_rows(runs))

    runs = st.session_state["runs"].get(scenario.key, {})
    for name in ("BFS", "POP"):
        if name in runs:
            show_status(runs[name])

    comparison = st.session_state.get("last_comparison")
    if comparison and comparison[0] == scenario.key:
        st.subheader("BFS vs POP comparison (measured in this session)")
        st.dataframe(pd.DataFrame(comparison[1]).astype(str), hide_index=True)
        st.caption(
            "BFS returns a total order and POP returns a partial order, so the metrics must be read "
            "with care. 'Explored' counts different things for each planner, and the parallel makespan "
            "is informational only."
        )


def render_results(scenario) -> None:
    st.header("Results")
    runs = st.session_state["runs"].get(scenario.key, {})
    if not runs:
        st.info("No planner has been run for this scenario yet. Use the Planning Engine tab.")
        return

    for name in ("BFS", "POP"):
        if name not in runs:
            continue
        run = runs[name]
        st.subheader(f"{name} ({run.representation})")
        show_status(run)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Planning time", f"{run.elapsed_seconds * 1000:.2f} ms")
        c2.metric("Explored", run.explored)
        c3.metric("Plan length", run.plan_length if run.success else "-")
        c4.metric("Sequential duration", f"{run.sequential_minutes} min" if run.success else "-")
        c5.metric("Dry ice used", f"{run.dry_ice_kg} kg" if run.success else "-")
        st.write(f"**Goal achieved:** {'yes' if run.goal_achieved else 'no'}")

        if run.actions:
            st.markdown("**Generated action sequence** (one valid execution order)")
            sequence_rows = []
            elapsed = 0
            dry_ice = 0
            for index, action in enumerate(run.actions, start=1):
                elapsed += action.duration
                dry_ice += action.dry_ice_cost
                sequence_rows.append({
                    "Step": index,
                    "Action": action.name,
                    "Duration (min)": action.duration,
                    "Cumulative time (min)": elapsed,
                    "Cumulative dry ice (kg)": dry_ice,
                })
            st.dataframe(pd.DataFrame(sequence_rows).astype(str), hide_index=True)

        if run.partial_plan is not None:
            plan = run.partial_plan
            st.markdown("**Causal links** (producer → condition → consumer)")
            link_rows = [{"Producer": link.producer, "Condition": link.condition,
                          "Consumer": link.consumer} for link in plan.links]
            st.dataframe(pd.DataFrame(link_rows).astype(str), hide_index=True)
            st.markdown("**Ordering constraints** (non-redundant)")
            order_rows = [{"Before": a, "After": b} for a, b in plan.reduced_orderings()]
            if order_rows:
                st.dataframe(pd.DataFrame(order_rows).astype(str), hide_index=True)
            st.write(
                f"Unordered step pairs (free to run in either order): "
                f"**{len(plan.independent_pairs())}**"
            )

        st.markdown("**Plan validation**")
        if run.validation is None:
            st.write("No plan to validate.")
        else:
            report = run.validation
            st.write(f"- Preconditions satisfied at every step: "
                     f"{'yes' if not report.precondition_failures else 'no'}")
            st.write(f"- Goal achieved: {'yes' if report.goal_achieved else 'no'}")
            st.write(f"- Time budget: {report.total_duration} min used of "
                     f"{scenario.constraints.max_duration_minutes} min")
            st.write(f"- Dry ice: {report.dry_ice_used_kg} kg used of "
                     f"{scenario.constraints.dry_ice_available_kg} kg")
            if report.all_problems:
                st.markdown("**Constraint and validation violations**")
                for problem_text in report.all_problems:
                    st.write(f"- {problem_text}")
            else:
                st.success("All validation checks passed.")
        st.divider()


def render_visualization(scenario) -> None:
    st.header("Visualization")
    runs = st.session_state["runs"].get(scenario.key, {})
    bfs_run = runs.get("BFS")
    pop_run = runs.get("POP")
    if not runs or not any(r.actions or r.partial_plan for r in runs.values()):
        st.info("Run a planner first. Plans with a sequence or partial order appear here.")
        return

    problem = scenario.build_problem()
    if bfs_run and bfs_run.actions:
        st.subheader("BFS: generated action sequence")
        st.graphviz_chart(viz.action_sequence_graph(bfs_run.actions).source)

        st.subheader("BFS: state transitions")
        st.caption("Each node is a state. Labels show facts added (+) and deleted (-).")
        st.graphviz_chart(viz.state_transition_graph(problem, bfs_run.actions).source)

        st.subheader("Planning dependencies (from the BFS sequence)")
        st.graphviz_chart(viz.dependency_graph(bfs_run.actions).source)

    if pop_run and pop_run.partial_plan is not None:
        st.subheader("POP: causal links")
        st.caption("Each coloured edge means 'the producer provides this condition to the consumer'.")
        st.graphviz_chart(viz.causal_link_graph(pop_run.partial_plan).source)

        st.subheader("POP: ordering constraints")
        st.caption("Dashed edges are ordering constraints. Steps with no path between them are independent.")
        st.graphviz_chart(viz.ordering_constraint_graph(pop_run.partial_plan).source)


def main() -> None:
    if "runs" not in st.session_state:
        st.session_state["runs"] = {}

    scenarios = list_scenarios()
    keys = [s.key for s in scenarios]
    with st.sidebar:
        st.title("Cold-Chain Planner")
        selected_key = st.selectbox("Scenario", keys,
                                    format_func=lambda k: get_scenario(k).title)
        scenario = get_scenario(selected_key)
        st.caption(f"Expected outcome: **{scenario.expected_outcome}**")
        st.info(DISCLAIMER)

    tab_dash, tab_details, tab_engine, tab_results, tab_viz = st.tabs(
        ["Dashboard", "Scenario Details", "Planning Engine", "Results", "Visualization"])
    with tab_dash:
        render_dashboard(scenario)
    with tab_details:
        render_scenario_details(scenario)
    with tab_engine:
        render_planning_engine(scenario)
    with tab_results:
        render_results(scenario)
    with tab_viz:
        render_visualization(scenario)


main()
