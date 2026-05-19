# VmaxBuilder Refactor Specification (Modular Pipeline)

## 1. Purpose
Define target architecture for refactoring legacy code into modular, typed, extensible VmaxBuilder pipeline.
This document is binding design contract for implementation, review, and CI gates.

## 2. Goals
- Modular pipeline aligned to workflow:
  1) Expression preprocessing
  2) Model preprocessing
  3) Protein abundance estimation (PTR + expression or direct proteomics)
  4) Kcat estimation + resolving
  5) Reaction capacity assignment / Vmax
- Stable public API through single orchestrator object.
- Pluggable algorithms via enum + registry + typed interfaces.
- Strict quality gates: `ty`, Ruff, tests, docs.
- Contributor-extensible design with strong coding principles.

## 3. Non-Goals
- No backward compatibility guarantees with legacy API in this release.
- No `src/scripts` cleanup in this phase.
- No changes to cobrapy fork/overwrites.

## 4. Target Package Layout
`src/VmaxBuilder/`
- `api/`                  # orchestrator + public entry points
- `config/`               # dataclass configs + loaders + validation
- `core/`                 # shared protocols, scaffold typing, errors
- `expression/`           # expression preprocessing
- `model/`                # model preprocessing/validation
- `protein_abundance/`    # PTR/proteomics integration
- `kcat/`                 # sequence/smiles retrieval + kcat estimation/resolution
- `allocation/`           # GPR split + IFP allocation
- `vmax/`                 # reaction capacity + imputation
- `diagnostics/`          # diagnostics collection/reporting
- `registries/`           # enum + registry implementations
- `utils/`                # logging/cache/io/threading helpers

## 5. Orchestrator Contract
- Single orchestrator initializes stage modules from loaded config.
- API exposes both:
  - explicit stage methods (`run_expression`, `run_model`, ...)
  - generic dispatcher (`run(stages=[...])`)
- Orchestrator passes shared scaffold object across stages.
- Each stage returns updated scaffold + metadata.
- Diagnostics are collected per stage; pipeline stops at configurable failure threshold.

## 6. Shared Scaffold Contract
Use `TypedDict` core keys + extension bag for community modules.
Use dataclasses for stage-specific typed payloads when applicable.

Core keys:
- `inputs`
- `artifacts`
- `outputs`
- `metadata`
- `diagnostics`
- `extras`  # contributor-safe custom payloads

Rules:
- Core keys stable and documented.
- Contributors can extend only via `extras` or typed stage payload models.
- Stage mutation behavior documented per stage (in-place allowed, but explicit).

## 7. Config System
- One top-level dataclass config with nested stage configs.
- Defaults load from TOML/JSON.
- Runtime override supported:
  - `config.expression.impute_method = "..."`, etc.
- Allowed values validated early; unsupported option raises immediately.
- Registry-backed validation hooks enforce per-method constraints.

## 8. Registry and Plugin Model
- Strict registry pattern for all pluggable components.
- Required per pluggable family:
  - protocol/interface
  - enum method keys
  - registration function/decorator
  - config validator
- Plugin policy: **explicit registration only**.
- No auto-discovery by entry points in this design phase.

## 9. Data and Metadata Rules
- Stage IO may use typed domain models and/or pandas DataFrames.
- Every stage returns metadata sufficient for reproducibility:
  - method key
  - normalized input refs
  - runtime options
  - timing
  - cache status
  - version identifiers

## 10. Diagnostics and Failure Policy
- Stage collects all actionable diagnostics in that stage.
- Pipeline continues inside stage until diagnostics collection complete.
- Pipeline halts before downstream stages if severity >= configured threshold.
- Threshold configurable (default recommended: `ERROR`).

## 11. Logging Schema (Structured)
Required fields:
- `timestamp_utc`
- `run_id`
- `stage`
- `module`
- `method`
- `event`
- `severity`
- `message`
- `duration_ms`
- `cache_hit`
- `exception_type`

Optional context fields:
- `sample_id`
- `task_id`
- `reaction_id`
- `gene_id`
- `input_hash`
- `config_hash`
- `worker_id`
- `artifact_path`

## 12. Caching Strategy (`diskcache`)
Backend:
- Standardize on `diskcache`.

Cache key contract:
- `stage`
- `method`
- `input_hash`
- `config_hash`
- `code_version`
- `schema_version`

Canonical key format:
- `"{stage}:{method}:{input_hash}:{config_hash}:{code_version}:{schema_version}"`

Key hashing guidance:
- Normalize structured inputs before hashing:
  - stable JSON for dict-like inputs
  - sorted columns/index policy for DataFrames
  - fixed float precision policy
- Include model identifiers and source file checksums where relevant.

Invalidation policy:
- Invalidate when any of:
  - algorithm logic changed (`code_version` bump)
  - schema changed (`schema_version` bump)
  - config affecting semantics changed (`config_hash` change)
  - source inputs changed (`input_hash` change)
- Manual controls:
  - clear all
  - clear per stage
  - clear per method
  - clear by run_id scope (optional)

Safety:
- Never reuse cache across mismatched schema/version.
- Cache metadata stored with entries for auditability.

## 13. Quality Gates
- Type check gate: `ty` must pass for changed code.
- Ruff gate: follow `pyproject.toml` settings.
- Python support matrix target: 3.11, 3.12, 3.13, 3.14.
- Test categories required: unit, integration, workflow.
- CI/pre-commit gates follow repository workflows and `.pre-commit-config.yaml`.

## 14. Testing Strategy
- Unit tests:
  - non-trivial logic, edge cases, branch behavior
- Integration tests:
  - all stage handoff chains are phase-1 blockers:
    - expression -> protein_abundance
    - model -> allocation
    - protein_abundance + allocation -> vmax
    - kcat -> vmax
    - full pipeline chain
- Workflow tests:
  - fast tests use synthetic fixtures in `data/tests`
  - integration/workflow tests can use selected real data fixtures

## 15. Documentation Standards
- Keep custom Google-like docstring style.
- Keep Sphinx compatibility.
- Use autobuild/API generation pipeline.
- Expand detailed docs incrementally during module refactors.

## 16. Migration Strategy
- Refactor while importing from legacy code (incremental, not big-bang).
- Build orchestrator + config + scaffold first.
- Then refactor in slices:
  1) model + expression
  2) protein_abundance
  3) allocation + vmax
  4) kcat alignment and completion
- Require green quality gates per slice before next slice.

## 17. Initial Sphinx Information Architecture
Top-level docs sections:
- Overview
- Architecture
- API Reference
- How-To
- Developer Guide

## 18. Acceptance Criteria (Phase Completion)
Phase complete when:
- orchestrator contract implemented for targeted stages
- registry dispatch + validation working
- `ty`, Ruff, tests pass
- docs build passes for touched modules
- migration notes updated

## 19. Decision Log
| Date | Decision | Reason | Impact |
|------|----------|--------|--------|
| 2026-05-19 | Both explicit stage API and generic dispatcher | Flexible API for users and automation | Stable public surface |
| 2026-05-19 | Explicit plugin registration only | Strong contributor discipline, deterministic behavior | Simpler plugin governance |
| 2026-05-19 | Shared scaffold = TypedDict core + extensible extras | Balance type safety and extensibility | Safe custom module integration |
| 2026-05-19 | Cache backend = diskcache | Persistent, practical, already dependency | Avoid repeated heavy work |
| 2026-05-19 | Python matrix 3.11-3.14 | Future compatibility target | CI scope defined |
| 2026-05-19 | All stage handoffs are phase-1 blockers | Pipeline integrity first | Strong integration coverage |
