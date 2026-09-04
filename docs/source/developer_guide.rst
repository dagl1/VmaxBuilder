Developer Guide: Add an Implementation
======================================

VmaxBuilder is designed so new behavior lands as a new implementation class rather than
as a fork of existing code.

The short version
-----------------

1. Subclass ``BaseImplementation`` or ``RealImplementation``.
2. Declare the stage and implementation names.
3. Define input and output specs.
4. Provide a config dataclass if the implementation needs extra parameters.
5. Implement ``generate_outputs()``.
6. Register the implementation through the orchestrator setter for the stage.
7. Add tests and docs.

Minimal example
---------------

.. code-block:: python

   from dataclasses import dataclass

   import pandas as pd

   from VmaxBuilder.base.classes import RealImplementation
   from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold


   @dataclass
   class ToyStageConfig:
       scale_factor: float = 1.0


   class ToyAllocationImplementation(RealImplementation[ToyStageConfig]):
       STAGE_NAME = "allocation"
       IMPL_NAME = "ToyAllocation"
       IMPLEMENTATION_CONFIG_CLASS = ToyStageConfig
       INPUTS = [InputSpec(name="protein_abundance_df", in_scaffold=True, data_type=pd.DataFrame)]
       OUTPUTS = [OutputSpec(name="toy_output", data_type=pd.DataFrame, scaffold_location="outputs")]

       def __init__(self, full_config: FullConfig):
           super().__init__(full_config)

       def generate_outputs(self, scaffold: Scaffold):
           protein_abundance_df = scaffold.get_scaffold_value("protein_abundance_df")
           toy_output = protein_abundance_df * self.config.scale_factor
           return {
               "outputs": {"toy_output": toy_output},
               "artifacts": {},
               "diagnostics": {},
               "metadata": {},
           }

Register it with the orchestrator
---------------------------------

Use the stage setter to activate the implementation at runtime.

.. code-block:: python

   orchestrator.set_allocation_implementation(ToyAllocationImplementation)

What to document when you add one
---------------------------------

- What inputs the implementation expects.
- What outputs it guarantees.
- Which config fields it reads.
- Whether it uses child implementations.
- Whether it needs diagnostics.
- What the saved artifacts mean for downstream stages.

Testing expectations
--------------------

- Add a focused unit test for the new branch or transformation.
- Add an integration test if the implementation changes stage-to-stage data flow.
- Validate the code path through the orchestrator if the new implementation affects
  loading, outputs, or diagnostics.
