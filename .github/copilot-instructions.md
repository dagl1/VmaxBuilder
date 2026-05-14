Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:

* Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
* Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
* Pattern: \[thing] \[action] \[reason]. \[next step].
* Not: "Sure! I'd be happy to help you with that."
* Yes: "Bug in auth middleware. Fix:"

Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.

# Copilot Instructions

## Instruction Files

Follow these instruction files:

- `style.instructions.md`
  → Naming, typing, formatting rules

- `architecture.instructions.md`
  → API structure, design patterns, module interactions

- `workflow.instructions.md`
  → Logging, plotting, utilities, code reuse

- `project_rules.instructions.md`
  → Scope limitations, allowed files, commit behavior

- `documentation.instructions.md`
  → Docstring format and requirements

- `test.instructions.md`
  → Testing requirements and best practices

---

## Mandatory Documentation Gates

- Before edits: read `.github/documentation.instructions.md`, list rules you will apply, then edit.
- Final response must include `Documentation compliance checklist` with each required section ticked.
- If a function is changed, but does not yet have docstring, add it following `documentation.instructions.md` requirements.
- If a function signature is modified, update docstring to match and include usage example if helpful.
- If code edits modify or add docstrings, enforce `documentation.instructions.md` requirements before finishing.

---

## Mandatory Testing Gates

- Before edits: read `.github/testing.instructions.md`, list applicable test types (unit, integration, usability), then proceed.

- When modifying code:
  - Check if relevant tests exist
  - Update existing tests if behavior changes
  - Add new tests if coverage is insufficient

- Unit tests:
  - Add tests for non-trivial logic, edge cases, and branching behavior
  - Do NOT create tests for trivial private helper functions
  - Prefer testing through public APIs when possible

- Integration tests:
  - Ensure interactions between modules still function correctly
  - Especially validate:
    - preprocessing → optimization
    - optimization → analysis

- Usability / workflow tests:
  - When relevant, validate changes using datasets from:
    - `data/for_SWAMP/`
  - If so, copy to test directory and use as test fixture
  - Ensure end-to-end workflows execute without errors

- Final response must include:
  - `Testing compliance checklist` with:
    - test types considered (unit / integration / usability)
    - tests added or updated
    - justification if tests were not added

- If code changes are made without updating or adding tests:
  → explicitly justify why no tests are required

- Never finish a code change without evaluating testing impact

---

## Priority Order

When generating code, apply rules in this order:

1. Existing patterns in `src/SWAMP/analysis` and `src/SWAMP/optimization`
2. `architecture.instructions.md`
3. `style.instructions.md`
4. `workflow.instructions.md`
5. `project_rules.instructions.md`

---

## Project Mental Model

- Modular API system using:
  - Config objects
  - Enum + registry pattern
- Workflow:
  Preprocessing → Optimization → Analysis
- Functionality is accessed through instantiated objects (PCA-style)

---

## Generation Behavior

- Prefer extending existing code over creating new structures
- Prefer reusable utilities over duplication
- Always:
  - type functions
  - add/update docstrings
  - follow project utilities and patterns

---

## Scope

- Only modify active modules in `src/SWAMP`
- Use `src/scripts` for experiments
- Do not modify cobrapy fork/overwrites
