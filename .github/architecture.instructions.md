# Architecture Overview

## Core Pattern
The project follows a modular API pattern:

- APIs consist of:
  - Config objects
  - Validation logic
  - Implementation selection via Enum + registry

## Execution Style
- "PCA-style" interface:
  - Instantiate a main object
  - Object exposes all relevant functionality

Example:
- See: `src/SWAMP/optimization/run_example.py`

## Modules

### Preprocessing
- `input_preprocessing` + `input_diagnostics`
- Combined in: `preprocessing.py`
- Output: `combinations/` directory

### Optimization
- Consumes preprocessed inputs
- Performs metabolic task optimization

### Analysis
- Post-processing + analysis API for optimization results

## Utilities
- Each module has local utils (temporary)
- Target: migrate to `src/SWAMP/utils`

## External dependencies
- Use:
  - `src/cobrapy_fork`
  - `src/SWAMP/cobrapy_overwrites`
- Do NOT modify these

## Active code areas
Only modify:
- `src/SWAMP/`

Already refactored:
- `src/SWAMP/analysis`
- `src/SWAMP/optimization`
- `src/SWAMP/sequence_retrieval`

Experimental code:
- `src/scripts`

## Module Responsibilities

### preprocessing
- Combines:
  - input_preprocessing (full_pipeline_preprocessing, kcat_preprocessing, ptr_preprocessing, etc.)
  - input_diagnostics (reaction_activity_diagnostics, model_diagnostics, etc.)
- Produces:
  - `combinations/` directory with processed model, expression, PTR, kcat, and tasklist files
- Used by:
  - optimization
- API/Entrypoint:
  - `PreprocessingPipeline` (full pipeline)
  - Diagnostics classes (e.g., `ReactionActivityDiagnosticer`)
  - `preprocessing.py` main function

### optimization
- Consumes:
  - preprocessed inputs (model, expression, PTR, kcat, tasklist)
- Performs:
  - metabolic task optimization using multiple strategies
- Structure:
  - Config: `RouteOptimizationConfig`, `RunConfig`, `SolverConfig`, `ExpressionConfig`
  - Strategy selection: Enum + registry (`RouteOptimisationMethod`, `get_route_optimisation_method`, `get_method`)
  - Core: `RouteOptimizationInput`, `BaseRouteOptimiser` (abstract), concrete strategies in `optimisation_strategies.py`
- Produces:
  - result files, long-format tables, task/sample summaries
- API/Entrypoint:
  - `RouteOptimizationInput` (input validation/discovery)
  - `BaseRouteOptimiser` (abstract interface)
  - `run_example.py` (usage example)
  - Registry: `get_method("route_optimiser", ...)`
  - Hooks: strategy registration via decorator

### analysis
- Consumes:
  - optimization outputs (run output dir, long format, task summaries)
- Provides:
  - analysis APIs for within/across/differential task scopes
- Structure:
  - Config: `SWAMPAnalysisConfig`
  - Scopes: `AnalysisScope` (within/across/differential)
  - Methods: `WithinTaskMethod`, `AcrossTaskMethod`, `DifferentialTaskMethod`
  - Registry: method registration via decorator
  - Types: `AnalysisInputPaths`
  - Modules: `within_task_strategies.py`, `across_task_strategies.py`, `differential_task_strategies.py`
- API/Entrypoint:
  - `core.py` (main API, method wrappers)
  - `modules/` (strategy implementations)
  - Hooks: `register_method` decorator for new analysis strategies

### sequence_retrieval
- Consumes:
  - gene symbols, model hints
- Provides:
  - APIs for fetching gene/protein sequences from Ensembl/RefSeq
  - Species inference, fallback merging, caching
- Structure:
  - Providers: `fetch_ensembl_sequences`, `fetch_refseq_sequences`
  - Types: `GeneSequenceResult`, `RetrievalSummary`, `SequenceMode`
  - Caching: `LookupCache`
- API/Entrypoint:
  - `api.py` (main API)
  - Hooks: provider registration

### utils
- Provides:
  - Logging, file handling, class/instance utilities, plotting, clustering, error handling
- Structure:
  - `custom_logging.py`, `file_handling.py`, `class_handling.py`, `extra_utils.py`, `plotting.py`, etc.
- Used by:
  - all modules
- API/Entrypoint:
  - Utility functions and classes, e.g., `CustomLogger`, `resolve_instance_variables`

---

# API Endpoints/Hooks

- **preprocessing**: `PreprocessingPipeline`, diagnostics classes, `preprocessing.py`
- **optimization**: `RouteOptimizationInput`, `BaseRouteOptimiser`, `get_method("route_optimiser", ...)`, `run_example.py`
- **analysis**: `core.py` (method wrappers), `register_method` decorator, `modules/` for new strategies
- **sequence_retrieval**: `api.py`, provider registration
- **utils**: direct import of utility functions/classes

---

# Navigation Notes

- All core APIs and extension points are in `src/SWAMP/`
- Add new strategies via registry/decorator pattern
- Only modify code in `src/SWAMP/`
- Do not touch `cobrapy_fork` or `cobrapy_overwrites`
