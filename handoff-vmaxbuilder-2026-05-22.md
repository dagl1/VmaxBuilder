# Handoff: Move runtime validation into orchestrator

## Session goal
Shift input-readiness check from example script into orchestrator-level runtime validation so all runs validate consistently before any stage executes.

## What user requested
- Move check into `VmaxOrchestrator._ensure_runtime_ready`.
- Ensure validation covers all required inputs per mode.
- Ensure validation happens before any pipeline stage runs.

## Current state
- No code edits applied yet in this session.
- No tests added/updated yet in this session.

## Constraints and instructions to follow next session
- Read and apply instruction files referenced by `.github/copilot-instructions.md`.
- Mandatory gates before edits:
  - Read `.github/documentation.instructions.md`; list rules to apply.
  - Read `.github/testing.instructions.md`; list applicable test types.
- Scope limits:
  - Modify only active modules under `src/VmaxBuilder`.
  - Do not move logic into example script; keep runtime checks in orchestrator.
- Testing gate:
  - Evaluate and update/add tests as needed.
  - Run required checks on touched files:
    - `uv run ruff format <file>`
    - `uv run ty check <file>`
    - `uv run ruff check <file>`

## Likely code areas
- `src/VmaxBuilder/api/` (orchestrator implementation and runtime readiness flow)
- `src/VmaxBuilder/run_example.py` (remove/avoid duplicated guard if present)
- `tests/api/test_orchestrator.py` (runtime-ready behavior by mode)

## Suggested implementation outline
1. Locate existing per-mode input check currently in example path.
2. Move/centralize logic into `VmaxOrchestrator._ensure_runtime_ready`.
3. Ensure method validates all required artifacts for each orchestrator mode.
4. Invoke readiness check at single early pre-stage point in orchestrator execution path.
5. Remove duplicate ad-hoc validation outside orchestrator (if any).
6. Update/add orchestrator tests for:
   - success path with complete inputs
   - failure path per mode with clear error messages
   - guarantee no stage work starts when validation fails

## Suggested skills
- `diagnose` — quickly map current validation flow and failure points before refactor.
- `tdd` — implement validation move with red-green-refactor tests.
- `zoom-out` — confirm orchestrator placement aligns with module architecture.

## Artifacts to reference (do not duplicate)
- `.github/copilot-instructions.md`
- `AGENTS.md`
- `.github/documentation.instructions.md`
- `.github/testing.instructions.md`
