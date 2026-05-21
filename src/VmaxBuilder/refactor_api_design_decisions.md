# VmaxBuilder Refactored API Design Decisions

## Purpose
This document captures current design decisions for the refactored VmaxBuilder API.
It is intended as a stable reference when migrating legacy orchestration code.

## Agreed Top-Level Pipeline
Top-level orchestrator stages are:

1. `model`
2. `protein`
3. `allocation`
4. `vmax`

Rationale:
- Keep user-facing API aligned with the core mental model.
- Allow internal complexity (expression/PTR/proteomics/kcat paths) without exposing unnecessary top-level stage branching.

## Orchestrator Surface
The orchestrator exposes both explicit stage methods and generic dispatch:

- `run_model()`
- `run_protein()`
- `run_allocation()`
- `run_vmax()`
- `run(stages=[...])`
- `run_all()`

## Final Architecture Shape
The refactored API is organized around a single orchestrator object that owns stage execution
and delegates work to stage modules and strategy modules.

Core concepts:

- `Orchestrator`: user-facing entrypoint
- `Stage`: top-level pipeline unit with a stable output contract
- `Strategy`: interchangeable implementation inside a stage
- `DiagnosticsRunner`: coordinates diagnostics hooks around stage execution
- `DiagnosticHook`: reusable check attached to a stage or strategy
- `Config`: typed runtime configuration with early validation
- `Registry`: explicit registration for stages, strategies, and diagnostics

Design rules:

- Keep public API small and predictable.
- Keep stage contracts stable even when internal strategies change.
- Replace whole stages only when module semantics differ.
- Replace strategies when only algorithmic behavior differs.
- Use diagnostics hooks for validation, tracing, and optional auto-fix policies.

## Shared Scaffold Contract
Use stable scaffold keys:

- `inputs`
- `artifacts`
- `outputs`
- `metadata`
- `diagnostics`
- `extras`

Rules:
- Core keys are stable.
- Stage-specific extensions go in typed payloads or `extras`.
- `extras` carries custom strategy payloads between stages.

## Scope Boundary
VmaxBuilder does not own task-analysis processing.

The legacy task list / task-analysis logic is intentionally removed from the VmaxBuilder
subset and will live in a separate package or workflow layer.

## Stage Contracts

### Model stage
Must return:
- validated/fixed model artifact
- model metadata

### Protein stage
Must always return canonical `protein_abundance` output shape.
May additionally return strategy-specific payloads via `extras`.

Supported internal pathways include, for example:
- expression + PTR integration
- direct proteomics preprocessing/integration

### Allocation stage
Must return:
- `IFP_members`
- `IFP_allocation`
- optional `trimmed_genes_per_sample`

May additionally return strategy-specific payloads via `extras`.

### Vmax stage
Must return:
- `reaction_capacity`

May additionally return:
- `imputed_reaction_capacity`
- `kcat` metadata/artifacts used during capacity estimation

Kcat policy:

- If user disables Kcat usage, missing Kcat defaults to `1.0` implicitly.
- If user enables Kcat usage and Kcat input is missing, stage fails early.

## Validation and Config Policy
Validation is strict by default.

Rules:

- Unknown values raise early.
- Lenient validation is opt-in.
- Lenient validation can be applied per field, not only globally.
- High-noise inputs such as tissue labels can be lenient when they are only metadata.
- Stage-critical inputs such as PTR, Kcat, and model loading must validate as soon as the
  relevant stage is initialized.

Configuration design rules:

- Use clean new option names only.
- Do not carry backward-compatibility aliases.
- Keep allowed values easy to discover and edit in one place.
- Prefer explicit paths first.
- Allow automated file discovery as a fallback when a path is not provided.
- Legacy option names are not preserved; new package uses clean options only.

Loading naming rules:

- Use `VmaxResults` or `artifacts` terminology instead of `combinations`.
- `VmaxResults` is the user-facing folder name for generated results.
- `artifacts` is the internal generated-data name for stage-local files.

Saving policy:

- Primary saved table format: `feather`.
- Optional additional export format: `csv`.
- Other formats are out of scope for current refactor slice.

## Kcat Canonical Design
Kcat processing uses a canonical internal representation with level-based conversion.
Different prediction strategies may enter at different levels and skip earlier conversions.

### Canonical levels
- `L1`: gene-substrate
- `L2`: gene-reaction
- `L3`: ifp-substrate
- `L4`: ifp-reaction (target level for Vmax consumption)

### Conversion policy
- Predictor declares `produces_level`.
- System executes only required converters from `produces_level` to `L4`.
- Examples:
  - `L1` output runs full chain `L1 -> L2 -> L3 -> L4`.
  - `L3` output runs `L3 -> L4` only.
  - `L4` output requires no conversion.

### Canonical record fields
Each canonical kcat record contains:
- `entity_level`
- `entity_id`
- `reaction_id` (optional where not yet resolved)
- `substrate_id` (optional for reaction-level records)
- `kcat_value`
- `unit`
- `source_method`
- `confidence`
- `metadata` (free-form strategy-specific fields)

### Converter interfaces (conceptual)
- `GeneSubstrateToGeneReactionConverter`
- `GeneReactionToIfpSubstrateConverter`
- `IfpSubstrateToIfpReactionConverter`

Each converter:
- accepts canonical records at one level
- emits canonical records at next level
- logs metadata and diagnostics

## Plugin and Registry Model
Swapping is supported at two granularities:

1. Whole stage implementations
2. Submodule/strategy implementations within a stage

This enables:
- complete alternative module replacement
- targeted strategy replacement within standard stage contracts

## Diagnostics Integration Decision
Diagnostics are implemented as separate modules, but strategy-aware and module-aware.

Rules:
- Diagnostics hook into active stage/submodule execution.
- Core diagnostics utilities are reusable across modules.
- Strategy authors can extend diagnostics by composing existing diagnostics utilities and adding strategy-specific checks.
- Diagnostics output is written into scaffold `diagnostics` with stage and method context.

### Diagnostics runner and hooks
Diagnostics are executed through a runner that wraps stage execution.

Runner responsibilities:

- invoke pre-stage hooks
- invoke post-stage hooks
- aggregate diagnostics records
- attach severity and provenance metadata
- decide whether the pipeline stops after the stage

Hook responsibilities:

- inspect stage inputs
- inspect stage outputs
- emit diagnostics records
- optionally perform stage-local fixes when policy allows

Hook attachment levels:

- stage-level hooks
- strategy-level hooks
- shared reusable hook components

This allows a new module author to reuse existing diagnostics utilities and add only the
strategy-specific checks that are unique to their implementation.

## Failure Policy
- Diagnostics are aggregated per stage execution.
- Pipeline halt threshold defaults to `ERROR`.
- Stage completes diagnostics collection before orchestrator decides to halt downstream stages.

## Migration Use During Refactor
When integrating legacy orchestration code, classify each legacy function into one of:

1. stage entrypoint logic
2. submodule strategy logic
3. kcat predictor adapter
4. kcat converter edge
5. utility/helper (candidate for `utils`)
6. configuration/validation concern

This document is the reference for deciding target placement and contract alignment.

## Refactor Execution Plan (Approved)

1. Freeze design decisions in this document and keep them as source of truth.
2. Create responsibility triage from legacy logic into new stage/config/utility owners.
3. Remove `task_list` and legacy `combinations` concepts from new API surface.
4. Build typed config and validation incrementally, starting with model options.
5. Build thin orchestrator + stage interfaces with diagnostics runner hooks.
6. Migrate behavior in slices with tests per slice.

Current focus:

- Step 2 triage + Step 4 model-options build.
- Comparison utilities move to `src/scripts` only, not core package API.
