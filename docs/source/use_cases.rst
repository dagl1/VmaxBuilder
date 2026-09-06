Use Cases
=========

This page captures practical scenarios for the current orchestrator-driven workflow.

Research scenarios
------------------

- Build condition-specific reaction capacities from model, protein, Kcat, and allocation inputs.
- Compare capacity profiles across tissues or perturbations.
- Use UniKP-backed Kcat prediction when you want a learning-based substrate path.
- Generate trimmed and untrimmed allocation outputs when comparing modeling assumptions.

Developer scenarios
-------------------

- Add new modular implementations with explicit `INPUTS`, `OUTPUTS`, and config dataclasses.
- Validate module outputs with diagnostics-first failure handling.
- Extend the shared scaffold with module-specific metadata and artifacts.
- Register a new implementation through the orchestrator stage setter.

What users should document in their own workflows
--------------------------------------------------

- What inputs were used.
- Which stage implementations were selected.
- Which config values changed from the defaults.
- Where outputs and artifacts were written.
- Whether diagnostics or alternate runs were enabled.

Related pages
-------------

- :doc:`getting_started`
- :doc:`overview`
- :doc:`tutorial`
- :doc:`examples`
- :doc:`developer_guide`
