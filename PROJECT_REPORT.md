# Automated Cold-Chain Logistics Planning for Perishable Pharmaceuticals Using Classical AI

**Project report**

---

## Abstract

Perishable pharmaceuticals such as vaccines must be kept inside a narrow temperature range
while they pass through a warehouse. Preparing a package for transport means following a
strict order of operations (receive, verify temperature, move, pack, inspect, seal, move to
dock, load) and staying within resource limits, such as a fixed quantity of dry ice and a
time budget. This report describes a classical AI planning system that represents the
problem in STRIPS form and solves it with two planners that were implemented from scratch:
a forward breadth-first search (BFS) and a simplified partial-order planner (POP). An
independent validator replays each plan and checks simulated temperature, time and
dry-ice constraints. Six synthetic scenarios exercise successful and failing cases. The
results show that BFS returns the shortest total-order plan but explores many states when
packages interact, and that POP returns a compact partial order with explicit causal links
and threat resolution. POP ignores resource limits during search, so the validator is what
rejects its over-budget plans. All temperatures, durations and constraints in the project
are simulated assumptions and are not validated pharmaceutical standards.

---

## 1. Introduction

Cold-chain logistics keeps temperature-sensitive goods within specified limits between the
point of origin and the point of use. For vaccines and other biological products, a single
excursion outside the range can make a whole batch unusable. Logistics staff therefore
need a reliable order of operations: a package must be verified before it moves, a
container must be inspected before it is sealed, and dry ice must be placed before sealing
when the product is frozen.

Planning is a natural fit for this problem. A plan is an ordered (or partially ordered)
set of actions, and correctness can be checked formally: each action must be applicable
when it runs, and the goal must hold at the end. Classical AI planning gives a clear model
for this, with explainable steps and no training data. This project applies that model to
a simulated pharmaceutical warehouse.

## 2. Problem statement

Given:

* a set of packages, each with a simulated temperature profile and a flag that says whether
  it needs dry ice,
* a set of operations with preconditions and effects,
* a time budget in minutes, and
* a stock of dry ice in kilograms, with a consumption rate per package,

produce a sequence or partial order of operations that loads every package onto the
delivery pallet, such that every precondition holds when its operation runs, every
simulated temperature reading is in range, the total duration is within the budget, and the
dry ice used does not exceed the stock. If no such plan exists, the system must say so.

## 3. Objectives

1. Model the domain in STRIPS form and provide matching PDDL files.
2. Implement a custom BFS planner with a visited set, constraint pruning, plan
   reconstruction and counters.
3. Implement a simplified POP planner with open conditions, causal links, ordering
   constraints, threat detection, and promotion/demotion.
4. Keep constraints configurable and separate from the planning algorithms.
5. Provide at least five scenarios, covering both success and failure.
6. Provide a Streamlit interface, Graphviz visualisations and a command-line runner.
7. Compare the two planners using measured metrics, with honest notes on interpretation.
8. Verify the implementation with automated tests.

## 4. PEAS formulation

| Element | Description |
|---|---|
| **Performance measure** | Plan validity (preconditions hold, goal reached), constraint satisfaction (temperature, time, dry ice), and planning cost (time and explored states or nodes). |
| **Environment** | A simulated pharmaceutical warehouse with a gate, receiving bay, cold room, loading dock and delivery pallet. Packages are discrete objects. Each package has one container. |
| **Actuators** | The eight operations (receive, verify, move, pack dry ice, inspect, seal, move to dock, load). In the simulation these are state transitions, not physical commands. |
| **Sensors** | Simulated temperature readings and the container and location facts in the state. In the simulation these are deterministic values that the planner reads from the scenario. |

The agent is a deliberative planner. It does not act in the physical world. It produces a
plan that a logistics operator or a warehouse control system could then carry out.

## 5. Methodology

The work followed the sequence below.

1. **Domain modelling.** Each operation was written as a STRIPS action with preconditions,
   add effects and delete effects. Location and container states were designed so that
   every package is in exactly one location, and the container is either open, inspected,
   or sealed in a consistent way.
2. **Constraint design.** Temperature ranges, durations, dry-ice amounts and the time budget
   were placed in configuration objects. The planners receive the numbers as inputs.
3. **Algorithm implementation.** BFS and POP were implemented from first principles, without
   a planning library.
4. **Validation.** A separate validator replays a plan step by step and reports every
   failure. It does not reuse the planners' internal logic.
5. **Scenario design.** Six scenarios were written with their own packages, temperature
   profiles and constraints. Each has an expected outcome, which the tests check against
   the actual algorithm runs.
6. **Testing and interface.** Automated tests were written first for the components and then
   for the end-to-end behaviour. The Streamlit interface was driven headlessly to check that
   every button and tab works.

## 6. Algorithms

### 6.1 STRIPS representation

A state is a frozen set of ground facts. An action is a record with a name, a precondition
set, an add set, a delete set, a duration and a dry-ice cost. Applicability is a subset test,
and the successor state is `(s − delete) ∪ add`. The eight operations give 7 or 8 grounded
actions per package. The initial state contains `at_gate`, `container_open` and, when the
simulated readings are in range, `temp_in_range` for each package. The goal is `loaded` for
each package.

Temperature is handled in two places. The initial-state builder adds `temp_in_range` only
when the readings are in range. Without that fact, `verify_temperature` is never applicable,
so a failing package cannot reach a plan. The validator also checks the readings directly.

### 6.2 Breadth-first search

The planner keeps a FIFO queue of nodes `(state, minutes, dry ice)` and a dictionary of
visited nodes. Each node stores a pointer to its parent and the action that produced it.
A node is expanded only when it is dequeued. Successors are pruned when they exceed the
time budget or the dry-ice stock, and pruned successors are counted. Because the search is
breadth-first, the first goal node found has the fewest actions among the plans that satisfy
the constraints.

Successors that are no worse than an already reached state for the same facts are skipped
(dominance checking), which removes repeated no-op actions from the search.

Complexity is exponential in the number of packages in the worst case, because interleavings
multiply. The implementation is explicit about this through its counters.

### 6.3 Partial-order planning

The POP planner works on a partial plan with two fake steps, START and FINISH. The search
is depth-first with backtracking.

* **Threat detection.** For each causal link `P --c--> C`, a step `T` that deletes `c` is a
  threat unless the plan already forces `T` before `P` or after `C`.
* **Resolution.** Promotion orders `T < P`. Demotion orders `C < T`. An option that would
  create a cycle is rejected, and the search tries the other option.
* **Support.** For an open condition `(C, c)`, the planner either reuses an existing step
  that adds `c`, or adds a new library action that adds `c`. It then adds the causal link
  and the ordering `P < C`.
* **Choice of open condition.** The condition with the fewest supporters is chosen first.
  If any open condition has no supporters, the branch fails immediately.

The search has a node limit as a safeguard. Each library action is used at most once in a
plan, which keeps the search space finite.

In the cold-chain domain, the seal operation deletes `container_open`. That threatens the
link from START to the pack operation, so the planner must demote the seal after the pack.
The inspection operation also needs `container_open`, but it does not delete it. Pack and
inspection are therefore unordered, and the plan keeps that freedom.

### 6.4 Validation

The validator replays a sequence from the initial state. For each action it checks the
preconditions, then applies the effects, then checks the state for contradictions (a package
in two locations, an open and a sealed container at once, a sealed container without
inspection, a loaded package whose container is not sealed). After the replay it checks the
goal. It also checks the simulated temperature readings of each package the plan touches,
the total duration against the budget, and the total dry ice against the stock.

## 7. Implementation

The project is written in Python 3.11 or newer. The main modules are:

| Module | Responsibility |
|---|---|
| `strips.py` | `Action` and `PlanningProblem` data types, applicability and effects |
| `actions.py` | The eight cold-chain operators, initial state, goal |
| `constraints.py` | Durations, time budget, dry-ice stock, simulated readings, range checks |
| `bfs.py` | Forward BFS planner |
| `pop.py` | Partial-order planner, threat handling, partial-order plan class |
| `validator.py` | Independent plan replay and constraint checks |
| `scenarios.py` | Six synthetic scenarios |
| `comparison.py` | Runs both planners and produces comparison metrics |
| `visualization.py` | Graphviz diagrams |
| `app.py` | Streamlit interface |
| `main.py` | Command-line runner and JSON export |

Each module has a single responsibility. The planners do not import the validator, and the
validator does not depend on either planner. The constraint values are passed in, so a
scenario can be changed without touching the algorithms.

The Streamlit interface has five tabs (Dashboard, Scenario Details, Planning Engine, Results,
Visualization). Graphviz diagrams are generated as DOT source and displayed with
`st.graphviz_chart`, so the Graphviz program is not needed to run the app.

## 8. Results

### 8.1 Test results

The automated suite contains 75 tests in six test files. It was re-run during this review
with Python 3.13.5 and pytest 9.0.2, and all 75 tests passed. The verbose log is included as
`sample_outputs/pytest_output.txt`. The tests cover the STRIPS model, BFS plans and no-solution
cases, POP causal links, ordering constraints, threats, promotion and demotion, the validator,
the constraints, and both planners on every scenario against its expected outcome.

The Streamlit interface was not launched during this review because Streamlit is not installed
in the review environment; install the dependencies from `requirements.txt` before running it.
The Python modules compile successfully, the command-line runner works, and 19 generated
Graphviz diagrams (across the scenarios with plans) were successfully rendered with `dot`.
The PDDL files are documentation/model artifacts and were not run through an external PDDL
planner.

### 8.2 Scenario outcomes

| # | Scenario | Expected | BFS | POP |
|---|---|---|---|---|
| 1 | Normal transport of one frozen vaccine | success | valid, 8 actions, 32 min, 2 kg | valid, 8 steps, 32 min, 2 kg |
| 2 | Three packages, mixed requirements | success | valid, 23 actions, 90 min, 4 kg | valid, 23 steps, 90 min, 4 kg |
| 3 | Limited dry ice (2 kg for 4 kg of need) | failure | no plan | plan rejected: 4 kg needed, 2 kg available |
| 4 | Restricted time budget (30 min for 32 min of work) | failure | no plan | plan rejected: 32 min exceeds 30 min |
| 5 | Temperature verification failure (about 11 °C) | failure | no plan | no plan |
| 6 | Refrigerated package, no dry ice | success | valid, 7 actions, 26 min, 0 kg | valid, 7 steps, 26 min, 0 kg |

Every "valid" result passed the validator. Every "rejected" result is a plan the planner
produced without respecting the constraints, which the validator then caught. Every "no plan"
result is a case where the planner correctly found nothing.

### 8.3 Search effort

| # | BFS explored states | BFS pruned successors | POP search nodes | POP causal links | POP ordering constraints | POP unordered pairs |
|---|---|---|---|---|---|---|
| 1 | 10 | 0 | 18 | 17 | 8 | 1 |
| 2 | 800 | 0 | 49 | 48 | 22 | 178 |
| 3 | 75 | 40 | 35 | 34 | 16 | 66 |
| 4 | 9 | 1 | 18 | 17 | 8 | 1 |
| 5 | 2 | 0 | 10 | – | – | – |
| 6 | 8 | 0 | 15 | 14 | 6 | 0 |

Planning-time measurements are included in `sample_outputs/cli_output.txt`. They are
machine-dependent and vary from run to run, so treat them as illustrative measurements rather
than fixed performance guarantees.

### 8.4 Issue found and fixed during testing

The first BFS version put elapsed time into the visited key, which meant that repeating a
no-op action produced a new node each time. On the three-package scenario it expanded 89,118
states. Had the goal been unreachable with no time budget, the search would never have ended. The fix was to add
dominance checking (Section 6.2) and two regression tests: one with a repeatable no-op action
and no budget, and one confirming the 23-action plan is still found. The table above uses the
corrected counts. The plans and outcomes did not change, only the search effort.

## 9. BFS versus POP comparison

**How to read the comparison.** BFS returns a total order, which is one fixed action
sequence. POP returns a partial order, which is a set of steps with ordering constraints
and causal links. The two representations are not the same kind of object, so the metrics
must be read with care:

* **Explored** counts states expanded by BFS and search nodes refined by POP. These are
  different units and cannot be ranked against each other.
* **Sequential duration** adds the duration of every action, which is the rule used by the
  time budget for both planners.
* **Parallel makespan** is the longest chain of ordering constraints in the POP plan. It
  shows how much time independent steps could save if they ran in parallel. It is reported
  for information only and is not used for pass/fail.

**Observations from the measured runs.**

1. **Plan length.** For a single package, both planners produce plans of the same length (8).
   BFS guarantees the fewest actions, and POP's plan is the same length here.
2. **Search effort.** Going from one package (scenario 1) to three (scenario 2), BFS expands
   10 states rising to 800, roughly an 80-fold increase. POP refines 18 nodes rising to 49, about
   2.7 times. BFS explores interleavings of the packages' steps. POP keeps the packages unordered
   relative to each other and resolves only the orderings the logic needs. The two counts are
   in different units, so the growth rates are the meaningful comparison, not the raw numbers.
3. **Flexibility.** POP's plan for three packages has 178 unordered pairs of steps. The
   parallel makespan is 28 minutes, against 90 minutes for the sequential sum. BFS cannot
   express this flexibility, because it returns one sequence.
4. **Constraint handling.** BFS checks time and dry ice during search and therefore reports
   no plan when the constraints cannot be met. POP ignores them during search, so it returns
   a logically correct plan that the validator then rejects. This is an honest limitation of
   the simplified POP. A real system would add resource checks to the search.
5. **Failure detection.** Both planners correctly find no plan when the temperature check fails.
   BFS does so after exploring 2 states. POP does so after refining 10 nodes.

## 10. Conclusion

The project shows that a classical AI pipeline can plan a cold-chain workflow with explicit
preconditions, causal reasoning and independent checking. BFS is simple, complete and gives
a shortest total-order plan, but its effort grows quickly with the number of packages. POP
gives a compact partial order that exposes which steps are independent. Its simplified form
does not enforce resource limits during search, which the validator compensates for by
rejecting over-budget plans.

The system behaves as designed in six scenarios. Its outputs come from actual executions,
and its results are checked by 75 automated tests. The main caveat is that all temperatures,
durations and constraints are simulated, so the system is a teaching model and not a
compliance tool.

## 11. Future scope

1. Add a heuristic search, such as A* with a relaxed-plan heuristic, to handle larger
   problems.
2. Model dry ice as a numeric resource inside the search so that POP respects it.
3. Use the parallel makespan for the time budget, once concurrency is modelled.
4. Add temperature drift during transport and a replanning step after a violation.
5. Run the PDDL files through an external planner and compare the results with the Python
   planners.
6. Add per-package deadlines and vehicle capacity.
7. Replace the simulated readings with imported sensor logs.

## 12. References

1. Fikes, R. E., & Nilsson, N. J. (1971). STRIPS: A new approach to the application of theorem
   proving to problem solving. *Artificial Intelligence*, 2(3–4), 189–208.
2. Russell, S., & Norvig, P. *Artificial Intelligence: A Modern Approach* (4th ed.), Chapter 11,
   "Automated Planning". Pearson, 2020.
3. McAllester, D., & Rosenblitt, D. (1991). Systematic nonlinear planning. *Proceedings of the
   Ninth National Conference on Artificial Intelligence (AAAI-91)*.
4. Penberthy, J. S., & Weld, D. S. (1992). UCPOP: A sound, complete, partial order planner for
   ADL. *Proceedings of KR-92*.
5. McDermott, D., et al. (1998). *PDDL: The Planning Domain Definition Language*. Technical
   report, Yale Center for Computational Vision and Control.
6. Graphviz. DOT language documentation. https://graphviz.org/doc/info/lang.html
7. Streamlit. Documentation. https://docs.streamlit.io
