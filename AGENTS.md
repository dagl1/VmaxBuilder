# AGENTS.md
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

## Agent instructions

- Found in `.github/copilot-instructions.md`, references:
  - `.github/architecture.instructions.md`
  - `.github/documentation.instructions.md`
  - `.github/project-rules.instructions.md`
  - `.github/style.instructions.md`
  - `.github/workflow.instructions.md`
  - `.github/testing.instructions.md`

## Mandatory documentation gates:
  - Before edits: read `.github/documentation.instructions.md`, list rules you will apply, then edit.
  - If function changed, but no docstring, add using `documentation.instructions.md` requirements.
  - If function signature is modified, update docstring to match and include usage example if helpful.
  - If code edits modify or add docstrings, enforce `documentation.instructions.md` requirements before finishing.


## Mandatory Testing Gates

- Before edits: read `.github/testing.instructions.md`, then proceed.
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
    - diagnostics → preprocessing → diagnostics

- Usability / workflow tests:
  - When relevant, validate changes using datasets from:
    - `data/`
  - If so, copy to test directory and use as test fixture
  - Ensure end-to-end workflows execute without errors

- If code changes are made without updating or adding tests:
  → explicitly justify why no tests are required

---

## Project Overview

- VmaxBuilder: Pipeline for converting transcriptomics data into reaction capacities in genome-scale metabolic models (GEMs).
- UniKP: Deep learning framework for enzyme kinetic parameter prediction. Located in `UniKP/`. Not core to SWAMP pipeline but referenced for advanced workflows.

## Architecture

- Modular pipeline: main focus is `preprocessing/`, each step hereafter is a module that can
  be selected through main API and registry/enum pattern. Overall VmaxBuilder workflow: takes
  `expression/` data, multiplies it with `PTR/`, allocates using `GPR/`, utilises `Kcat` data,
  outputs `Vmax/` values.
- Core module folder: `src/VmaxBuilder/`,
- with submodules for each purpose (e.g., `preprocessing/`, `diagnostics/`, `utils/`).
- Registry pattern: Enum + registry for algorithm selection.
- Data: Input/output in `data/`, configs in `config/`.
- Scripts: Experiments, CLI wrappers in `src/scripts/`.

## Key Patterns & Conventions

- Extend, don't fork: Add new algorithms via registry, not by duplicating code.
- Config objects: All workflows parameterized by config objects (JSON/TOML).
- Functionality via objects: Instantiate classes (PCA-style) for main API access.
- Docstrings required. Type all functions, see `examples.instructions.md` for style.
- Logging/plotting: Use project utilities. No ad-hoc print/debug.
- Only modify active modules in `src/VmaxBuilder`. Use `src/scripts` for experiments.
- External API calls should always be using threaded execution and disk-cached results.

## Developer Workflows

- Build/test: No monolithic build. Run module/unit tests via scripts in `src/scripts/` or test files in `tests/`.
- Demo data: add `data/analysis_demo/` with example datasets and juypter notebooks demonstrating analysis workflows.

## Integration Points

- External models: Place pretrained models (e.g., UniKP, ProtT5-XL-UniRef50) in `UniKP/` as required.
- Data flows: Input models/data in `data/inputs/`, outputs to `data/results/` or experiment-specific folders.
- Sequence retrieval: Supports Ensembl/RefSeq, fallback logic in API.

## References

- Main README: `README.md`
- UniKP: `UniKP/README.md`

## Agent skills

### Issue tracker

Issues tracked on GitHub Issues. See `.github/agents/issue-tracker.md`.

### Triage labels

Default triage label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `.github/agents/triage-labels.md`.

### Domain docs

Single-context: CONTEXT.md and docs/adr/ at repo root. See `.github/agents/domain.md`.

---

For more, follow conventions in `.github/copilot-instructions.md` and referenced instruction files.
