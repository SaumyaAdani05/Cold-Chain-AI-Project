# AGENTS.md — Rules for the AI Coding Agent

Project: **Automated Cold-Chain Logistics Planning for Perishable Pharmaceuticals Using Classical AI**
Your scope: **Plan Validation, Visualization, and the Streamlit prototype.**

---

## 0. Read these first (in order)

1. `PRD.md` — what we are building and what "done" means
2. `ARCHITECTURE.md` — modules, ownership, and the data contracts you must obey
3. `DOMAIN.md` — predicates, actions, constraints, scenarios, test plans
4. `TECHSTACK.md` — allowed libraries, versions, commands
5. `TASKS.md` — ordered checklist; work top to bottom

If two documents disagree, `ARCHITECTURE.md` (contracts) wins, then `DOMAIN.md`, then `PRD.md`. Flag the conflict to the user instead of guessing.

---

## 1. Ownership boundaries

| Module | Owner | Your permission |
|---|---|---|
| `validator.py` | **You** | Create, edit, test |
| `viz/` (graph builders) | **You** | Create, edit, test |
| `app.py` + `ui/` (Streamlit) | **You** | Create, edit, test |
| `tests/` for the three modules above | **You** | Create, edit |
| `model.py` (Action, scenarios) | Teammate / user | **Read only.** Propose changes, never edit silently |
| `bfs.py`, `pop.py` (planners) | Teammate / user | **Read only.** Use through the adapter |
| `pddl/*.pddl` | Teammate / user | Read only |

If a planner module does not exist yet, develop against `tests/fixtures/mock_planners.py` (see `ARCHITECTURE.md` §5). Do **not** write a real planner to fill the gap.

---

## 2. DO

**Correctness**
- DO treat every plan as untrusted until `validate()` has passed it. The UI must never show a plan as "valid" without a `ValidationResult`.
- DO implement the validator exactly as specified in `DOMAIN.md` §5 (precondition check → apply delete then add → goal check → constraint checks).
- DO report **every** violation with the step number, action name, and reason (not just the first one).
- DO keep states immutable: use `frozenset` for fact sets. Copy before modifying.
- DO handle `plan is None` (no plan found) as a normal, first-class outcome, not an error.
- DO handle an empty plan `[]` correctly (valid only if the goal already holds in the initial state).

**Code quality**
- DO use Python 3.11+ type hints on every function signature and `@dataclass` for structured data.
- DO write small pure functions. Keep Streamlit calls out of validator and graph-builder modules.
- DO write a docstring for each public function: purpose, args, returns, raises.
- DO follow PEP 8; format with `black` and lint with `ruff` before finishing a task.
- DO use `pathlib` for paths and relative imports within the package.

**Testing**
- DO write the pytest test **with** each feature, not after. Follow the test list in `DOMAIN.md` §7.
- DO include deliberately broken plans (negative tests) for the validator.
- DO run `pytest -q` before reporting a task done, and paste the result summary.

**Streamlit / UX**
- DO store results in `st.session_state` so widget interaction does not wipe the plan.
- DO show clear states: loading spinner, success (green), no plan (amber), invalid plan / violations (red), and unexpected error (red, with message).
- DO catch `graphviz.backend.ExecutableNotFound` and show an install hint instead of crashing.
- DO label every chart and table with units (time units, dry-ice units).

**Communication**
- DO state assumptions explicitly at the top of your reply when a spec is ambiguous.
- DO ask the user before any change that touches a contract in `ARCHITECTURE.md`.
- DO report, at the end of each task: files changed, tests run, and anything left undone.

---

## 3. DON'T

**Scope**
- DON'T implement, rewrite, or "improve" BFS, POP, or any planner. Not even a quick version "for convenience."
- DON'T edit `model.py`, `bfs.py`, `pop.py`, or PDDL files. Propose a diff in your message instead.
- DON'T add features not in `PRD.md` (no user accounts, databases, REST APIs, ML models, authentication, or cloud deployment).
- DON'T change function names, signatures, or result-dictionary keys defined in `ARCHITECTURE.md` without approval.

**Dependencies**
- DON'T add any library not listed in `TECHSTACK.md`. If you think one is needed, ask first.
- DON'T use ML libraries (TensorFlow, PyTorch, scikit-learn) or planning libraries (`pyperplan`, `unified-planning`, Fast Downward) in the core code. This project is from scratch.
- DON'T make network calls, download data, or call external APIs at runtime.

**Code practices**
- DON'T mutate a state, plan list, or action object in place.
- DON'T use bare `except:` or silently swallow exceptions. Catch specific exceptions and surface a message.
- DON'T hardcode absolute paths, scenario data inside UI code, or magic numbers (use constants in one place).
- DON'T use `eval`, `exec`, `pickle` on user-supplied input, or `unsafe_allow_html=True` with user-controlled strings.
- DON'T leave `print` debugging, commented-out code blocks, or `TODO` without an owner in committed code.
- DON'T write secrets, tokens, or personal data to files or logs (there should be none in this project).

**Honesty**
- DON'T claim a test passed unless you ran it.
- DON'T fabricate benchmark numbers. Experiment figures must come from actual runs saved to CSV.
- DON'T mark a task done in `TASKS.md` if its acceptance criteria are not met.
- DON'T hide a failing test by deleting or loosening it. Fix the cause or report it.

---

## 4. Definition of Done (per task)

A task is done only when **all** of these hold:

1. Code matches the contract in `ARCHITECTURE.md`.
2. New/changed behaviour has pytest coverage (positive and negative cases).
3. `pytest -q` passes; `ruff check .` and `black --check .` are clean.
4. The Streamlit app starts with `streamlit run app.py` and the changed feature works on scenarios S1 and S5 at minimum.
5. `TASKS.md` is updated, and your message lists files changed and assumptions made.

---

## 5. When unsure

Stop and ask. Specifically ask before: changing a data contract, adding a dependency, touching a read-only file, interpreting an ambiguous constraint rule, or deleting any existing file.

Preferred question format:

> **Blocker:** one sentence.
> **Options:** A (…), B (…).
> **My recommendation:** A, because …
