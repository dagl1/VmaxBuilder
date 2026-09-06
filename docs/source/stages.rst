Stages and Implementations
==========================

This page lists the currently wired stages, their wrapper classes, the main concrete
implementations, and the config classes that shape their behavior.

Model stage
-----------

- Stage wrapper: ``ModelStage``
- Stage config: ``ModelCoreConfig``
- Default implementation: ``DefaultIrreversibleModelImplementation``
- Implementation config: ``ModelConfig``
- Additional implementations: ``DefaultGPRImplementation`` and ``TranscriptSMILESGetter``

What it does:

- loads and normalizes the model,
- applies the irreversible-model preprocessing path,
- prepares GPR-related data,
- and retrieves transcript/SMILES-linked artifacts needed downstream.

Protein stage
-------------

- Stage wrapper: ``ProteinStage``
- Stage config: ``ProteinStageConfig``
- Main implementation: ``MvalueTrimmingExpressionPTRImplementation``
- Child implementations: ``ExpressionPTRImplementation`` and ``MValueTrimmingImplementation``
- Additional implementation: ``MissingGeneRemoval``
- Supporting configs: ``ExpressionConfig`` and ``PTRInputConfig``

What it does:

- processes expression data,
- applies PTR logic,
- computes trimming-related artifacts,
- and removes genes that are no longer valid after preprocessing.

Allocation stage
----------------

- Stage wrapper: ``AllocationStage``
- Main implementation: ``FairAllocationImplementation``
- Implementation config: ``FairAllocationConfig``

What it does:

- allocates protein abundance across IFPs,
- optionally trims IFPs when trimming is enabled,
- and emits trimmed and untrimmed allocation artifacts when configured to do so.

Kcat stage
----------

- Stage wrapper: ``KcatStage``
- Main implementation: ``UniKPMainSubstrateImplementation``
- Child implementations: ``UniKPImplementation`` and ``MainSubstrateImplementation``
- Supporting configs: ``UniKPConfig`` and ``MainSubstrateConfig``

What it does:

- runs UniKP-based Kcat prediction paths,
- aggregates results by main substrate,
- and resolves the per-reaction prediction structure used by Vmax.

Vmax stage
----------

- Stage wrapper: ``VmaxStage``
- Main implementation: ``DefaultVmaxReactionResolving``
- Implementation config: ``ReactionResolvingConfig``

What it does:

- combines IFP abundance with per-gene reaction predictions,
- accounts for trimming-aware Kcat behavior when enabled,
- and resolves final reaction capacity values.

How to extend this catalog
--------------------------

When a new implementation is added, update this page so the documentation keeps matching
the active orchestrator wiring.
