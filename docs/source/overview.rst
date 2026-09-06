VmaxBuilder Overview
====================

VmaxBuilder is an orchestrated Python pipeline for converting model, expression, protein,
Kcat, and allocation inputs into reaction-capacity estimates for genome-scale metabolic
models.

The codebase is built around one central runtime idea: the :class:`~VmaxBuilder.base.orchestrator.Orchestrator`
selects concrete stage implementations, loads inputs, passes a shared scaffold between
stages, and writes outputs, metadata, diagnostics, and artifacts.

What the pipeline does
----------------------

At a high level, the pipeline:

1. Loads model and transcript-related inputs.
2. Converts the model into the working form used by downstream stages.
3. Processes expression and protein-related data.
4. Estimates or resolves Kcat values, including UniKP-based prediction paths.
5. Allocates protein abundance to IFPs.
6. Combines IFP abundance and Kcat information to compute Vmax values.

Core runtime objects
--------------------

- ``RunConfig`` controls execution behavior, output paths, diagnostics, validation, and print level.
- ``StageLoading`` tells the orchestrator where each stage should discover inputs.
- ``FullConfig`` carries all per-stage configuration sections plus shared execution settings.
- ``Scaffold`` is the shared in-memory payload that moves between stages.

How to read the code
--------------------

Start with these files:

- ``src/VmaxBuilder/base/orchestrator.py``
- ``src/VmaxBuilder/base/classes.py``
- ``src/VmaxBuilder/base/configs.py``

Then move to the stage wrappers and concrete implementations listed in :doc:`stages`.

Current implementation model
----------------------------

Each stage has a wrapper class and one or more concrete implementations:

- The stage wrapper defines the runtime stage boundary.
- The implementation performs the actual work.
- Child implementations are nested under a parent implementation when a stage is composed from multiple steps.
- Additional implementations can run after the main implementation when a stage needs post-processing.

The current codebase is intentionally modular. For the implementation catalog and config
names, see :doc:`stages`.

What to document next
---------------------

The most useful downstream docs are:

- a quick-start tutorial,
- a configuration and output guide,
- a stage catalog,
- and a developer guide for adding new implementations.

Those pages are meant to stay close to runtime behavior, not abstract architecture.
