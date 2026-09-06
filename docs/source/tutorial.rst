Tutorial: Run the Orchestrator
==============================

This tutorial shows the runtime flow a user should follow when running VmaxBuilder.

1. Build configuration objects.
2. Select stage implementations.
3. Run the orchestrator.
4. Inspect config, outputs, and saved artifacts.

Installation first
------------------

Before running the pipeline, install the project with ``uv`` and make sure the solver
stack is available. See :doc:`installation` for the full setup path.

Minimal orchestrator skeleton
-----------------------------

.. code-block:: python

   from pathlib import Path

   from VmaxBuilder.base.configs import RunConfig, StageLoading, StageLoadingInfo
   from VmaxBuilder.base.orchestrator import Orchestrator
   from VmaxBuilder.stages.Kcat.UniKPMainSubstrate.implementation import (
       UniKPMainSubstrateImplementation,
   )
   from VmaxBuilder.stages.Vmax.default.reaction_resolving import (
       DefaultVmaxReactionResolving,
   )
   from VmaxBuilder.stages.allocation.FairAllocation.implementation import (
       FairAllocationImplementation,
   )
   from VmaxBuilder.stages.model.default.implementation import (
       DefaultIrreversibleModelImplementation,
   )
   from VmaxBuilder.stages.protein.MvalueTrimmingExpressionPTR.implementation import (
       MvalueTrimmingExpressionPTRImplementation,
   )

   run_config = RunConfig(
       output_dir=Path("data/results"),
       run_name="demo_run",
       print_level="INFO",
       run_input_validation=True,
       run_output_validation=True,
       run_diagnostics=True,
       prune_scaffold_unused_objects=True,
       use_existing_results_if_available=False,
   )

   stage_loading = StageLoading(
       model_loading_info=StageLoadingInfo(
           stage_name="model",
           directories=[Path("data/inputs/model")],
       ),
       protein_loading_info=StageLoadingInfo(
           stage_name="protein",
           directories=[Path("data/inputs/protein")],
       ),
       allocation_loading_info=StageLoadingInfo(
           stage_name="allocation",
           directories=[Path("data/inputs/allocation")],
       ),
       Vmax_loading_info=StageLoadingInfo(
           stage_name="Vmax",
           directories=[Path("data/inputs/Vmax")],
       ),
       Kcat_loading_info=StageLoadingInfo(
           stage_name="Kcat",
           directories=[Path("data/inputs/Kcat")],
       ),
   )

   orchestrator = Orchestrator(
       stage_implementations=stage_loading,
       run_config=run_config,
   )
   orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
   orchestrator.set_protein_implementation(MvalueTrimmingExpressionPTRImplementation)
   orchestrator.set_allocation_implementation(FairAllocationImplementation)
   orchestrator.set_Kcat_implementation(UniKPMainSubstrateImplementation)
   orchestrator.set_Vmax_implementation(DefaultVmaxReactionResolving)
   orchestrator.run()

Execution options that matter in practice
-----------------------------------------

Two ``RunConfig`` switches are useful for long runs and restart workflows:

- ``prune_scaffold_unused_objects=True``
    Prunes in-memory scaffold inputs/artifacts/extras after each implementation save,
    while keeping objects required by remaining consumers in this and future stages.
- ``use_existing_results_if_available=True``
    Reuses already-saved implementation outputs when all required output files are
    present, and skips recomputation for that implementation.

If ``overwrite_existing_results=True`` is set, reuse is intentionally disabled.

Stage-by-stage API usage
------------------------

When a user runs stages or implementations manually through the API (instead of
``orchestrator.run()``), scaffold pruning is not activated by default run context.
This keeps scaffold objects available for interactive debugging and custom flows.

Inspect config and print settings
---------------------------------

The orchestrator exposes the active configuration after implementation selection.

.. code-block:: python

   print(orchestrator.return_config("run"))
   print(orchestrator.return_config("model"))
   print(orchestrator.return_config("allocation"))

Use ``set_print_level()`` when you want more or less runtime logging.

.. code-block:: python

   orchestrator.set_print_level("DEBUG")

The output directory layout
---------------------------

Runs are written under ``output_dir / run_name`` with these top-level folders:

- ``outputs`` for primary results,
- ``artifacts`` for intermediate data that should be preserved,
- ``diagnostics`` for stage reports and plots,
- ``metadata`` for reproducibility details.

Choosing different implementations
----------------------------------

The orchestrator setters select the concrete implementations used at runtime. That means
the same pipeline can be run with a different model implementation, a different protein
coordination path, or a different Kcat strategy without changing the stage order.

When you change a stage implementation, update the matching config section as well.

What to look for after a run
----------------------------

- ``orchestrator.return_config()`` to confirm the active parameters.
- The saved CSV/JSON/PKL outputs in the run directory.
- Diagnostics artifacts if diagnostics were enabled.
- Stage-specific intermediate results in ``artifacts``.

If you want to add a new implementation next, read :doc:`developer_guide`.
