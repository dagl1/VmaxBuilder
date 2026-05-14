# Testing Instructions

## Core Principle

When modifying or adding functionality:

→ Always evaluate whether tests must be added or updated.

Testing is required for:
- new functionality
- changes to existing logic
- bug fixes
- refactors that affect behavior

---

## Types of Tests

### Unit Tests
- Test individual functions or small components
- Focus on:
  - core logic
  - edge cases
  - failure modes

Guidelines:
- Do NOT test trivial private helper functions directly
- DO test private logic indirectly through public APIs
- Prioritize functions with:
  - non-trivial logic
  - branching behavior
  - transformations

---

### Integration Tests
- Test interaction between modules

Focus on:
- preprocessing → optimization
- optimization → analysis
- full API workflows

Guidelines:
- Ensure modules work together correctly
- Validate expected data flow and outputs
- Use realistic inputs where possible

---

### Usability / Workflow Tests
- Test realistic usage scenarios

Use:
- datasets from:
  - `data/for_SWAMP/`
  - If so, copy to test directory and use as test fixture
Focus on:
- end-to-end execution
- typical user workflows
- stability across different inputs

Guidelines:
- Prefer representative datasets over synthetic ones
- Ensure outputs are:
  - valid
  - consistent
  - interpretable

---

## Test Coverage Expectations

- High coverage is expected for:
  - core logic
  - public APIs
  - critical workflows

- Lower coverage is acceptable for:
  - trivial helpers
  - thin wrappers
  - simple data containers

Avoid:
- redundant tests
- testing implementation details instead of behavior

---

## When Modifying Code

When a function or module is modified:

1. Check if tests exist
2. Update affected tests
3. Add missing tests if:
   - behavior changed
   - edge cases are not covered
   - new branches are introduced

---

## Test Organization

- Tests should mirror the structure of:
  - `src/SWAMP/`

Example:
``` id="rsc2ts"
src/SWAMP/optimization/...
→ tests/optimization/...
