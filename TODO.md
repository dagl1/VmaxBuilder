# Repository TODO inventory

Status legend:
- (done): implemented and verified in the current codebase.
- (likely done): implemented or effectively covered by adjacent code, but not explicitly validated end-to-end.
- (not yet done): still open or still planned.

## Active / recently resolved

| Status | Origin | Todo |
| --- | --- | --- |
| (done) | [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py) | Add explicit implementation completion log lines after each implementation, including elapsed time. |
| (done) | [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py) | Add diagnostics entry/exit logs with timing for each diagnostics hook. |
| (done) | [src/VmaxBuilder/base/orchestrator.py](src/VmaxBuilder/base/orchestrator.py) | Add end-of-run complete message after the final stage finishes. |

## Remaining backlog

| Status | Origin | Todo |
| --- | --- | --- |
| (not yet done) | [src/VmaxBuilder/base/orchestrator.py](src/VmaxBuilder/base/orchestrator.py) | Add validator at end of implementation to see if all outputs are present. |
| (not yet done) | [src/VmaxBuilder/base/orchestrator.py](src/VmaxBuilder/base/orchestrator.py) | Add overwrite/use-previous-run interaction logic when both flags are set. |
| (not yet done) | [src/VmaxBuilder/base/orchestrator.py](src/VmaxBuilder/base/orchestrator.py) | Review whether the stage keep/plan logic should be public or private. |
| (not yet done) | [src/VmaxBuilder/base/configs.py](src/VmaxBuilder/base/configs.py) | Make all parameters a specific class that returns its value while still containing configuration metadata. |
| (not yet done) | [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py) | Debug scaffold mutation timing around diagnostic hooks and additional process execution. |
| (not yet done) | [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py) | Add a formal way to indicate save_with_tries and extension metadata for output objects. |
| (not yet done) | [src/VmaxBuilder/base/classes.py](src/VmaxBuilder/base/classes.py) | Move internal helper logic out of this file and into a dedicated utility module. |
| (not yet done) | [src/VmaxBuilder/database_retrieval/identifier_translation.py](src/VmaxBuilder/database_retrieval/identifier_translation.py) | Revisit overall sequence lookup speed; it is likely much slower than necessary. |
| (not yet done) | [src/VmaxBuilder/GPR/gpr_diagnostics.py](src/VmaxBuilder/GPR/gpr_diagnostics.py) | Add diagnostics for count/coverage of GPR rules and IFP counts. |
| (not yet done) | [src/VmaxBuilder/stages/allocation/FairAllocation/diagnostics.py](src/VmaxBuilder/stages/allocation/FairAllocation/diagnostics.py) | Expand diagnostics roadmap for trimming-threshold sensitivity analysis. |
| (not yet done) | [src/VmaxBuilder/stages/Kcat/main_substrate/diagnostics.py](src/VmaxBuilder/stages/Kcat/main_substrate/diagnostics.py) | Add alluvial or metabolite-level diagnostics for missing vs present SMILES metadata. |
| (not yet done) | [src/VmaxBuilder/stages/Kcat/main_substrate/main_substrate_implementation.py](src/VmaxBuilder/stages/Kcat/main_substrate/main_substrate_implementation.py) | Add configuration to ignore passive-transport predictions. |
| (not yet done) | [src/VmaxBuilder/stages/Kcat/main_substrate/main_substrate_implementation.py](src/VmaxBuilder/stages/Kcat/main_substrate/main_substrate_implementation.py) | Implement more explicit diagnostics for aggregated substrate prediction outputs. |
| (likely done) | [src/VmaxBuilder/stages/model/default/implementation.py](src/VmaxBuilder/stages/model/default/implementation.py) | Add ability to reuse an existing gene-transcript mapping if present. |
| (not yet done) | [src/VmaxBuilder/stages/protein/expression/implementation.py](src/VmaxBuilder/stages/protein/expression/implementation.py) | Centralize duplicated gene-expression handling and validation. |
| (not yet done) | [src/VmaxBuilder/stages/protein/expression/implementation.py](src/VmaxBuilder/stages/protein/expression/implementation.py) | Validate that genes are actually set to GPR-less in the model when expected. |
| (not yet done) | [src/VmaxBuilder/stages/protein/ptr/multiplication_implementation.py](src/VmaxBuilder/stages/protein/ptr/multiplication_implementation.py) | Add base diagnostics for PTR multiplication. |
| (not yet done) | [src/VmaxBuilder/trimming/Mvalue/diagnostics.py](src/VmaxBuilder/trimming/Mvalue/diagnostics.py) | Extend trimming diagnostics with alluvial plots and kcat-aware summaries. |
| (not yet done) | [src/VmaxBuilder/trimming/Mvalue/trimming_implementation.py](src/VmaxBuilder/trimming/Mvalue/trimming_implementation.py) | Ensure sample-group trimming behaves correctly in diagnostics plots. |
| (not yet done) | [src/VmaxBuilder/typing_stubs/protein/MvalueTrimmingExpressionPTR/implementation.py](src/VmaxBuilder/typing_stubs/protein/MvalueTrimmingExpressionPTR/implementation.py) | Rename use_special_groups_for_unobserved_imputation to PTR naming. |
| (not yet done) | [src/VmaxBuilder/utils/custom_exceptions.py](src/VmaxBuilder/utils/custom_exceptions.py) | Add cross-option compatibility checks and a global exception hook. |
| (not yet done) | [src/VmaxBuilder/utils/custom_logging.py](src/VmaxBuilder/utils/custom_logging.py) | Add nicer color/nesting support for STARTING and FINISHED log events. |
| (not yet done) | [src/VmaxBuilder/utils/custom_logging.py](src/VmaxBuilder/utils/custom_logging.py) | Generalize the custom logging interface to avoid hard-coded class-instance assumptions. |
| (not yet done) | [src/VmaxBuilder/utils/optimisation.py](src/VmaxBuilder/utils/optimisation.py) | Add explicit optional solver imports and dependency validation. |
| (not yet done) | [src/VmaxBuilder/stages/model/default/implementation.py](src/VmaxBuilder/stages/model/default/implementation.py) | Add missing TODO-driven capability for reusing existing transcript mapping artifacts. |

## Notes

This list is intentionally conservative. Items marked as done reflect direct implementation in the current branch, while the rest are still pending work based on the code comments currently present in the repository.
