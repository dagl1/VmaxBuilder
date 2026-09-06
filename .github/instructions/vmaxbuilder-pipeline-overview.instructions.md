---
description: "Use when documenting, explaining, or extending the VmaxBuilder orchestrator pipeline, config flow, stage implementations, or modular implementation pattern."
applyTo:
  - "src/VmaxBuilder/**/*.py"
  - "README.md"
  - "docs/source/**/*.rst"
---

# VmaxBuilder Pipeline Overview

Use this document as the shared working summary for any future documentation, tutorial, or implementation-walkthrough task.

## Core Mental Model

- VmaxBuilder is an orchestrated, stage-based pipeline.
- The pipeline runs in a fixed stage order: model -> protein -> allocation -> Kcat -> Vmax.
- The Orchestrator is the entry point that wires stage implementations, loads inputs, manages the shared scaffold, runs stages, and saves outputs.
- Stages are wrappers around concrete implementations.
- Implementations do the real work. They declare inputs, outputs, diagnostics, child implementations, and stage-specific config.
- Scaffold is the shared data bus between stages. It carries inputs, artifacts, outputs, metadata, diagnostics, extras, and discovered input paths.

## Running Perspective

When explaining how the code runs, start here:

1. Build `RunConfig` and `FullConfig`.
2. Create `StageLoading` so each stage knows where to find inputs.
3. Instantiate `Orchestrator` with stage loading and run config.
4. Select concrete implementations with the orchestrator setter methods:
   - `set_model_implementation(...)`
   - `set_protein_implementation(...)`
   - `set_allocation_implementation(...)`
   - `set_Kcat_implementation(...)`
   - `set_Vmax_implementation(...)`
5. Call `run()`.
6. The orchestrator discovers inputs, creates output directories, writes metadata, resolves optional dependencies, loads inputs unless lazy loading is enabled, validates inputs unless lazy validation is enabled, and then runs each stage.

## Config Flow

Describe config as layered, not flat:

- `RunConfig` controls execution behavior, output paths, validation, diagnostics, print level, lazy loading, and output format.
- `FullConfig` holds the per-stage config sections plus `run`, `paths`, and transcript-processing config.
- Each concrete implementation receives `full_config` and resolves its own implementation config class.
- The orchestrator updates the active stage config when a concrete implementation is selected.
- Documentation should show that config is part of runtime wiring, not a separate side system.
- The config is part of the specific implementations and can be found there, alternatively one can look at the config by calling `Orchestrator.return_config()`.

## Stage and Implementation Flow

When documenting a stage, keep the sequence explicit:

- Stage wrapper receives implementation + full config.
- Stage runs diagnostics before the implementation.
- Implementation loads inputs or uses scaffold-loaded inputs.
- Implementation generates outputs and returns scaffold updates.
- Stage may run additional processes after implementation output.
- Stage runs diagnostics after execution.
- Stage validates expected outputs before returning.

## Modular Implementation Pattern

When explaining how to add a new implementation, use this pattern:

- Subclass `BaseImplementation` or `RealImplementation`.
- Declare `STAGE_NAME`, `IMPL_NAME`, `INPUTS`, `OUTPUTS`, `CHILD_IMPLEMENTATIONS`, and optional `DIAGNOSTICS`.
- Provide a concrete config dataclass if the implementation needs its own parameters.
- Put computation in `generate_outputs(...)` and return scaffold updates.
- Register or select the implementation through the orchestrator stage setter.
- Keep behavior extendable by adding a new implementation class instead of forking an existing one.

## Data Flow Rules

Use these terms consistently:

- Inputs are the file-backed or scaffold-backed values loaded before stage execution.
- Artifacts are intermediate values that should remain available for downstream stages or diagnostics.
- Outputs are the main stage results saved for later stages and user consumption.
- Metadata captures reproducibility context such as parameters, timestamps, and status.
- Diagnostics capture stage-specific checks, plots, summaries, and warnings.

## Important Accuracy Rules

- Do not describe the codebase as using an enum-based plugin registry unless you have verified that specific path.
- Do not imply stages are independent; they are sequential and scaffold-driven.
- Do not hide the role of the orchestrator. It is the runtime controller, not just a convenience wrapper.
- Do not describe outputs as only files; they also flow through the scaffold in memory.
- Do not describe child implementations as separate pipelines; they are nested implementations owned by a parent implementation.

## Documentation Targets For Future Agents

When writing the actual docs later, aim for these outputs:

- A short conceptual overview for new users.
- A run-oriented tutorial that explains how to configure and execute the pipeline.
- A developer guide for adding new implementations in the modular pattern.
- Function and class docstrings that match the actual runtime flow.
- Clear examples that start from orchestrator setup and end at saved outputs.

## Best Source Files To Read First

- [src/VmaxBuilder/base/orchestrator.py](src/VmaxBuilder/base/orchestrator.py)
- [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py)
- [src/VmaxBuilder/base/configs.py](src/VmaxBuilder/base/configs.py)
- [src/VmaxBuilder/stages/model/model.py](src/VmaxBuilder/stages/model/model.py)
- [src/VmaxBuilder/stages/protein/protein.py](src/VmaxBuilder/stages/protein/protein.py)
- [src/VmaxBuilder/stages/allocation/allocation.py](src/VmaxBuilder/stages/allocation/allocation.py)
- [src/VmaxBuilder/stages/Kcat/Kcat.py](src/VmaxBuilder/stages/Kcat/Kcat.py)
- [src/VmaxBuilder/stages/Vmax/Vmax.py](src/VmaxBuilder/stages/Vmax/Vmax.py)

## Drafting Standard

When another agent uses this file to write documentation, it should:

- stay close to runtime reality
- prefer clear flow over abstract architecture language
- keep explanations conceptual before implementation details
- show how config, scaffold, and outputs interact
- call out extension points for new implementations
- create subsections for the currently implemented implementations per stage, and their
  configs, and what they do.

## Tutorial & getting started

- Also we want an, uv-based installation for python 3.11, also note that we call UniKP in the Kcat implementation
  - explain that we mostly use Gurobi and how to install it, and link to academic license instructions
  -
- An explanation of the pipeline, what it does, and what the stages are
- A try-out tutorial with both code examples for running, how config is changed, how different
  implementations are selected, and how outputs are saved. As well as what the data should
  look like
- A tutorial for adding a new implementation, with a simple example of a new implementation that does something trivial, and how to register it with the orchestrator.
