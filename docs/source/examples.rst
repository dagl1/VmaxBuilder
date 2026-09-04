Examples
========

These examples are intentionally short and map directly onto the runtime flow.

Example 1: print the active config
----------------------------------

.. code-block:: python

   print(orchestrator.return_config("run"))
   print(orchestrator.return_config("allocation"))

Example 2: change runtime verbosity
-----------------------------------

.. code-block:: python

   orchestrator.set_print_level("INFO")
   orchestrator.set_print_level("DEBUG")

Example 3: switch implementations
----------------------------------

.. code-block:: python

   orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
   orchestrator.set_protein_implementation(MvalueTrimmingExpressionPTRImplementation)
   orchestrator.set_allocation_implementation(FairAllocationImplementation)
   orchestrator.set_Kcat_implementation(UniKPMainSubstrateImplementation)
   orchestrator.set_Vmax_implementation(DefaultVmaxReactionResolving)

See also
--------

- :doc:`getting_started`
- :doc:`tutorial`
- :doc:`use_cases`
- :doc:`api`
