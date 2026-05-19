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

## Modules

### Preprocessing
- `input_preprocessing` + `input_diagnostics`
- Combined in: `preprocessing.py`
- Output: `combinations/` directory

## Utilities
- Each module has local utils (temporary)
- Target: migrate to `src/VmaxBuilder/utils`

## External dependencies
- `src/VmaxBuilder/cobrapy_overwrites`
- Do NOT modify these

## Active code areas
Only modify:
- `src/VmaxBuilder/`

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

---

# Navigation Notes

- All core APIs and extension points are in `src/VmaxBuilder/`
- Add new strategies via registry/decorator pattern
- Only modify code in `src/VmaxBuilder/`
- Do not touch `cobrapy_fork`
