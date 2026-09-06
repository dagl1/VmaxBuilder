Usage
=====

This page explains how to inspect and control the orchestrator at runtime.

Inspect config
--------------

After selecting implementations, you can print the current config sections.

.. code-block:: python

	print(orchestrator.return_config("run"))
	print(orchestrator.return_config("model"))
	print(orchestrator.return_config("protein"))
	print(orchestrator.return_config("allocation"))
	print(orchestrator.return_config("Kcat"))
	print(orchestrator.return_config("Vmax"))

Change print level
------------------

Use ``set_print_level()`` when you need quieter or more verbose runs.

.. code-block:: python

	orchestrator.set_print_level("DEBUG")

Runtime execution switches
--------------------------

Key ``RunConfig`` options for execution control:

- ``prune_scaffold_unused_objects``: defaults to ``True`` and prunes only
  in orchestrator full runs.
- ``use_existing_results_if_available``: when ``True``, implementations can skip
  recomputation by loading existing required output files.
- ``overwrite_existing_results``: when ``True``, existing files are overwritten and
  reuse-skip mode is disabled.

Example:

.. code-block:: python

	run_config.prune_scaffold_unused_objects = True
	run_config.use_existing_results_if_available = True
	run_config.overwrite_existing_results = False

Stage-only API behavior
-----------------------

If you run stage objects directly for debugging, automatic scaffold pruning is not
activated by orchestrator-run context markers. This keeps scaffold state available
between manual API calls.

Output locations
----------------

The run directory is created from ``RunConfig.output_dir`` and ``RunConfig.run_name``.
Inside that directory you should expect:

- ``outputs`` for primary results,
- ``artifacts`` for intermediate or downstream-useful data,
- ``diagnostics`` for plots and reports,
- ``metadata`` for reproducibility details.

Choose implementations
----------------------

Each stage has a dedicated setter on the orchestrator:

- ``set_model_implementation(...)``
- ``set_protein_implementation(...)``
- ``set_allocation_implementation(...)``
- ``set_Kcat_implementation(...)``
- ``set_Vmax_implementation(...)``

These setters control which concrete implementation class runs inside the fixed stage
order.
