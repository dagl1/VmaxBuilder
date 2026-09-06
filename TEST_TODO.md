# VmaxBuilder Test TODO Plan

Purpose:
- Provide executable test-planning backlog for full package coverage.
- Focus only on src/VmaxBuilder and tests.
- Exclude external and src/scripts as requested.

Status legend:
- [ ] not started
- [~] planned in detail, pending implementation
- [x] implemented and validated

## 1. Scope and principles

- In scope: all runtime modules under src/VmaxBuilder.
- Out of scope: external, src/scripts, generated build artifacts.
- Test layers to plan for each module:
1. Unit tests for deterministic logic and edge-case behavior.
2. Integration tests for stage boundaries and scaffold lifecycle.
3. Regression tests for previously fixed defects.
4. Performance and memory tests where runtime cost is material.

## 2. Core fixtures and harness to add first

- [ ] T-0001 Add fixture factory for minimal FullConfig variants.
Test type: Unit support.
Target: tests/conftest.py.
Checks: strict and lenient validation, reusable temp output paths, toggles for save and prune behavior.

- [ ] T-0002 Add fixture factory for Scaffold with typed payload presets.
Test type: Unit support.
Target: tests/conftest.py.
Checks: empty scaffold, scaffold with inputs only, scaffold with artifacts and diagnostics.

- [ ] T-0003 Add lightweight fake stage and implementation classes for orchestrator lifecycle tests.
Test type: Integration support.
Target: tests/base fixtures or helper module.
Checks: deterministic call order tracking, configurable failure points, generated scaffold outputs.

- [ ] T-0004 Add shared model fixtures for small COBRA models with controlled GPR complexity.
Test type: Integration support.
Target: tests/conftest.py or tests/model helpers.
Checks: reversible and irreversible reactions, missing genes, nested AND/OR rules.

## 3. Base layer plans

### src/VmaxBuilder/base/classes.py

- [~] T-0101 Expand BaseImplementation run lifecycle test matrix.
Test type: Unit.
Focus: before diagnostics, generate outputs, after diagnostics, save calls, prune calls.
Checks: exact call sequence, scaffold updates merged correctly, finish logs include elapsed time.

- [ ] T-0102 Validate reuse-existing-results behavior for mixed output specs.
Test type: Unit.
Focus: try_reuse_existing_results and reusable spec selection.
Checks: skip only when all required files exist, scaffold_location list handling, overwrite flag precedence.

- [ ] T-0103 Verify prune plan state transitions across child implementations.
Test type: Unit.
Focus: _resolve_pruning_plan_context and prune_unused_scaffold_objects.
Checks: current_index progression, protected key retention, concise pruning logs only list object names.

- [ ] T-0104 Regression test for diagnostics input tracking in additional implementations.
Test type: Regression.
Focus: diagnostic INPUTS in future-required set.
Checks: no accidental pruning of diagnostic dependencies.

- [ ] T-0105 Save pipeline tests for artifacts, outputs, metadata, diagnostics.
Test type: Unit.
Focus: save_all_scaffold_objects and helpers.
Checks: saver arg filtering, fallback JSON path, extension handling, nested diagnostic folder layout.

### src/VmaxBuilder/base/configs.py

- [ ] T-0111 Scaffold deep merge and retrieval semantics.
Test type: Unit.
Focus: get_scaffold_value, get_scaffold_location, update_scaffold.
Checks: recursive match order, type warnings, empty-dict non-overwrite behavior.

- [ ] T-0112 Config path creation and normalization tests.
Test type: Unit.
Focus: RunConfig and path fields.
Checks: path generation stability, run_name sanitization behavior, existing directory reuse.

- [ ] T-0113 Cross-config conflict validation tests.
Test type: Unit.
Focus: validate_config_conflicts.
Checks: duplicate key conflict raises expected exception with source lines.

### src/VmaxBuilder/base/orchestrator.py

- [ ] T-0121 Full orchestrator run integration with fake 5-stage pipeline.
Test type: Integration.
Focus: stage loading, input discovery, execution ordering.
Checks: model -> protein -> allocation -> Kcat -> Vmax order, stage outputs available downstream.

- [ ] T-0122 Failure handling in stage N aborts N+1 and reports useful diagnostics.
Test type: Integration.
Focus: mid-run exceptions.
Checks: no later stage execution, partial artifacts and metadata still consistent.

- [ ] T-0123 End-of-run completion log emission.
Test type: Regression.
Focus: run complete message.
Checks: includes elapsed time and terminal stage count.

- [ ] T-0124 Separate-stage runs do not empty scaffold unexpectedly.
Test type: Regression.
Focus: stage-only execution mode.
Checks: previously produced scaffold objects preserved unless explicitly pruned.

### src/VmaxBuilder/base/enums.py

- [ ] T-0131 Enum value stability tests.
Test type: Unit.
Focus: ValidationMode, StageName, output-format enums.
Checks: values unchanged to protect config compatibility and CLI usage.

### src/VmaxBuilder/base/exceptions.py and src/VmaxBuilder/base/protocols.py

- [ ] T-0141 Exception construction and message contract tests.
Test type: Unit.
Focus: custom base exceptions.
Checks: context fields present and readable.

- [ ] T-0142 Protocol runtime-check smoke tests.
Test type: Unit.
Focus: structural compatibility for protocol-bearing classes.
Checks: expected attributes present on real implementations.

## 4. Utility layer plans

### src/VmaxBuilder/utils/file_loading.py

- [ ] T-0201 Parametric round-trip tests for supported formats.
Test type: Unit.
Focus: csv, tsv, json, pickle, feather, parquet, rds loaders.
Checks: index preservation, dtype expectations, missing-file errors.

- [ ] T-0202 Corrupt file and schema mismatch behavior.
Test type: Unit.
Focus: robust failure paths.
Checks: meaningful exceptions, no silent coercion when invalid.

### src/VmaxBuilder/utils/file_saving.py

- [ ] T-0211 Save-with-retry behavior under intermittent file errors.
Test type: Unit.
Focus: retry loop and overwrite semantics.
Checks: attempts count, final success, proper raise after exhaustion.

- [ ] T-0212 Parallel save race safety smoke tests.
Test type: Integration.
Focus: concurrent writes to distinct files.
Checks: no path collision and all files valid.

### src/VmaxBuilder/utils/file_handling.py

- [~] T-0221 Extend existing tests with unsupported-extension behavior.
Test type: Unit.
Focus: load_existing_file_based_on_extension.
Checks: explicit error or fallback behavior matches contract.

### src/VmaxBuilder/utils/iterables.py

- [ ] T-0231 JSON-serializable conversion for nested scientific objects.
Test type: Unit.
Focus: numpy scalars, pandas objects, datetimes, custom classes.
Checks: json.dumps succeeds, value semantics preserved where feasible.

- [ ] T-0232 Circular reference guard behavior.
Test type: Unit.
Focus: recursive converter safety.
Checks: fails fast with clear error.

### src/VmaxBuilder/utils/optimisation.py

- [ ] T-0241 Optional solver import behavior.
Test type: Unit.
Focus: absent optional dependencies.
Checks: deterministic fallback and actionable exception messaging.

### src/VmaxBuilder/utils/plotting/*

- [ ] T-0251 Color conversion and palette validity tests.
Test type: Unit.
Targets: colors.py.
Checks: RGB bounds, alpha handling, deterministic palette lengths.

- [ ] T-0252 Trendline fit correctness tests.
Test type: Unit.
Targets: trendline.py.
Checks: expected coefficients and monotonicity for synthetic datasets.

- [ ] T-0253 Alluvial input-preprocessing tests.
Test type: Unit.
Targets: alluvial.py and wrappers.py.
Checks: missing categories, single-category input, stable grouping output.

### src/VmaxBuilder/utils/stubs.py and src/VmaxBuilder/utils/type_hinting.py

- [~] T-0261 Keep existing type hinting tests; add edge cases for nested generic aliases.
Test type: Unit.
Checks: Optional, Union, Mapping deep decomposition.

### src/VmaxBuilder/utils/custom_logging.py and src/VmaxBuilder/utils/custom_exceptions.py

- [~] T-0271 Extend logging tests for STARTING and FINISHED formatting consistency.
Test type: Unit.
Checks: print_level filtering and colorized output stability.

- [~] T-0272 Add global exception hook behavior tests once implemented.
Test type: Unit.
Checks: hook wiring and compatibility checks produce clear diagnostics.

## 5. COBRA overwrite plans

### src/VmaxBuilder/cobrapy_overwrites/cobrapy_model.py

- [ ] T-0301 Large reaction batch add performance guard.
Test type: Performance.
Checks: add_reactions_slim upper-bound runtime on representative model sizes.

- [ ] T-0302 Solver population correctness after slim add.
Test type: Integration.
Checks: optimize works and objective unchanged versus baseline addition path.

### src/VmaxBuilder/cobrapy_overwrites/cobrapy_io.py

- [ ] T-0311 Model dict serialization round-trip with complex GPR rules.
Test type: Integration.
Checks: genes, metabolites, bounds, GPR text preserved.

- [ ] T-0312 Regression for unusual gene identifiers and compartment names.
Test type: Regression.
Checks: no key loss and predictable sort order where required.

### src/VmaxBuilder/cobrapy_overwrites/cobrapy_reaction.py

- [ ] T-0321 Bounds and reversibility edge cases.
Test type: Unit.
Checks: blocked reactions, asymmetric bounds, sign correctness.

## 6. Database retrieval plans

### src/VmaxBuilder/database_retrieval/identifier_translation.py

- [~] T-0401 Expand existing sequence retrieval fallback tests.
Test type: Unit.
Checks: Ensembl then RefSeq fallback, partial failures, deterministic mapping.

- [ ] T-0402 Add threaded external-call caching tests.
Test type: Integration.
Checks: cache hit avoids duplicate network calls, disk cache reused across runs.

- [ ] T-0403 Throughput benchmark for large gene lists.
Test type: Performance.
Checks: bounded latency growth and memory profile under chunked retrieval.

## 7. GPR and Kcat preprocessing plans

### src/VmaxBuilder/GPR/gpr_preprocessing.py

- [ ] T-0501 Gene rule parsing and normalization matrix.
Test type: Unit.
Checks: nested boolean logic, whitespace and case normalization, invalid token handling.

### src/VmaxBuilder/GPR/gpr_implementation.py

- [~] T-0502 Extend existing tests for large-model runtime and correctness.
Test type: Integration and performance.
Checks: IFP generation coverage, deterministic results across run seeds.

- [ ] T-0503 Regression for edge reactions with empty or malformed GPR.
Test type: Regression.
Checks: graceful skip and diagnostics marker.

### src/VmaxBuilder/GPR/gpr_diagnostics.py

- [ ] T-0504 Add direct diagnostics payload tests.
Test type: Unit.
Checks: expected counts and schema, save_file_name conventions.

### src/VmaxBuilder/Kcat_preprocessing/config.py

- [ ] T-0511 Config validation defaults and overrides.
Test type: Unit.
Checks: default values, invalid options, interaction between flags.

### src/VmaxBuilder/Kcat_preprocessing/smiles_retrieval.py

- [ ] T-0512 Retrieval fallback and dedup behavior.
Test type: Unit.
Checks: duplicate metabolites, missing IDs, curated override precedence.

### src/VmaxBuilder/Kcat_preprocessing/gene_substrate_preprocessing.py

- [ ] T-0513 Gene-substrate table transformation correctness.
Test type: Unit.
Checks: merge keys, null handling, one-to-many expansion consistency.

### src/VmaxBuilder/Kcat_preprocessing/smiles_transcripts_getters_implementation.py

- [~] T-0514 Extend current tests with malformed CSV rows and mixed delimiter resilience.
Test type: Regression.
Checks: robust parsing for quoted commas and escaped quotes.

## 8. Stage plans

### 8.1 Model stage

Targets:
- src/VmaxBuilder/stages/model/model.py
- src/VmaxBuilder/stages/model/default/config.py
- src/VmaxBuilder/stages/model/default/preprocessing.py
- src/VmaxBuilder/stages/model/default/implementation.py
- src/VmaxBuilder/stages/model/default/diagnostics.py

- [ ] T-0601 End-to-end model stage run with reversible split and transcript artifacts.
Test type: Integration.
Checks: expected outputs in scaffold, artifact schema, metadata timing.

- [ ] T-0602 Transcript preprocessing edge-case matrix.
Test type: Unit.
Checks: canonical-only toggle, duplicate transcripts, missing mapping rows.

- [ ] T-0603 Diagnostics generation and save path checks.
Test type: Unit.
Checks: diagnostics payload shape and file writing contract.

### 8.2 Protein stage

Targets:
- src/VmaxBuilder/stages/protein/protein.py
- src/VmaxBuilder/stages/protein/diagnostics.py
- src/VmaxBuilder/stages/protein/remove_missing_genes.py
- src/VmaxBuilder/stages/protein/expression/config.py
- src/VmaxBuilder/stages/protein/expression/implementation.py
- src/VmaxBuilder/stages/protein/expressionPTR/implementation.py
- src/VmaxBuilder/stages/protein/proteomics/config.py
- src/VmaxBuilder/stages/protein/proteomics/implemenation.py
- src/VmaxBuilder/stages/protein/ptr/config.py
- src/VmaxBuilder/stages/protein/ptr/ptr_utils.py
- src/VmaxBuilder/stages/protein/ptr/imputation_implementation.py
- src/VmaxBuilder/stages/protein/ptr/multiplication_implementation.py
- src/VmaxBuilder/stages/protein/ptr/diagnostics.py
- src/VmaxBuilder/stages/protein/MvalueTrimmingExpressionPTR/implementation.py

- [ ] T-0701 Expression loader and normalization tests.
Test type: Unit.
Checks: gene index handling, NaN strategy, data type normalization.

- [ ] T-0702 PTR imputation branch coverage.
Test type: Unit.
Checks: missing PTR values, default imputation behavior, group-aware branches.

- [ ] T-0703 Expression x PTR multiplication correctness.
Test type: Unit.
Checks: aligned index and columns, scale invariance, negative value handling.

- [ ] T-0704 remove_missing_genes behavior against model and expression mismatches.
Test type: Integration.
Checks: genes removed exactly as expected, no accidental loss of matched genes.

- [ ] T-0705 Protein stage mini-pipeline integration.
Test type: Integration.
Checks: expression -> PTR imputation -> multiplication outputs feed allocation stage contract.

- [ ] T-0706 Protein diagnostics payload tests.
Test type: Unit.
Checks: expected summary fields and stable names for saved outputs.

- [ ] T-0707 Regression for MvalueTrimmingExpressionPTR branching logic.
Test type: Regression.
Checks: trimmed and untrimmed paths produce consistent dimensions and expected keys.

### 8.3 Allocation stage

Targets:
- src/VmaxBuilder/stages/allocation/allocation.py
- src/VmaxBuilder/stages/allocation/FairAllocation/config.py
- src/VmaxBuilder/stages/allocation/FairAllocation/implementation.py
- src/VmaxBuilder/stages/allocation/FairAllocation/diagnostics.py

- [~] T-0801 Extend FairAllocation tests to diagnostic side-effects.
Test type: Unit.
Checks: diagnostics object creation, deterministic naming and schema.

- [ ] T-0802 Allocation integration with protein stage outputs.
Test type: Integration.
Checks: expected IFP_sample_abundance_df columns and reaction coverage.

- [ ] T-0803 Numerical stability tests for extreme abundance and PTR scales.
Test type: Regression.
Checks: no overflow or NaN propagation in capacity intermediates.

### 8.4 Kcat stage

Targets:
- src/VmaxBuilder/stages/Kcat/Kcat.py
- src/VmaxBuilder/stages/Kcat/Kcat_utils.py
- src/VmaxBuilder/stages/Kcat/main_substrate/config.py
- src/VmaxBuilder/stages/Kcat/main_substrate/main_substrate_implementation.py
- src/VmaxBuilder/stages/Kcat/main_substrate/diagnostics.py
- src/VmaxBuilder/stages/Kcat/UniKP/config.py
- src/VmaxBuilder/stages/Kcat/UniKP/implementation.py
- src/VmaxBuilder/stages/Kcat/UniKPMainSubstrate/implementation.py
- src/VmaxBuilder/stages/Kcat/KcatPredictors/UniKP/mock.py
- src/VmaxBuilder/stages/Kcat/KcatPredictors/UniKP/utils.py

- [ ] T-0901 Kcat utility model object serialization and equality tests.
Test type: Unit.
Checks: to_dict stability, optional fields, numeric precision.

- [ ] T-0902 main_substrate implementation branch matrix.
Test type: Integration.
Checks: passive transport handling, missing SMILES, curated vs inferred substrate choice.

- [ ] T-0903 Diagnostics for missing vs present substrate metadata.
Test type: Unit.
Checks: counts and groupings by metabolite and reaction.

- [ ] T-0904 UniKP predictor adapter contract tests.
Test type: Unit.
Checks: predictor input formatting, output parsing, fallback to mock predictor.

- [ ] T-0905 Kcat stage integration with allocation outputs.
Test type: Integration.
Checks: generated per-reaction per-gene predictions keyed as Vmax stage expects.

### 8.5 Vmax stage

Targets:
- src/VmaxBuilder/stages/Vmax/Vmax.py
- src/VmaxBuilder/stages/Vmax/default/config.py
- src/VmaxBuilder/stages/Vmax/default/reaction_resolving.py
- src/VmaxBuilder/stages/Vmax/default/missing_imputation.py
- src/VmaxBuilder/stages/Vmax/default/diagnostics.py

- [~] T-1001 Keep current memory regression tests and expand sample x reaction scale.
Test type: Memory regression.
Checks: compact artifact default, optional gene details toggle, bounded growth profile.

- [ ] T-1002 Vmax numeric correctness test with handcrafted small network.
Test type: Unit.
Checks: exact expected capacity sums and contribution ratios.

- [ ] T-1003 missing_imputation behavior tests.
Test type: Unit.
Checks: imputes only missing entries, does not alter observed values.

- [ ] T-1004 Vmax stage integration with upstream allocation and Kcat outputs.
Test type: Integration.
Checks: output dataframe shape, index alignment, required artifact availability.

- [ ] T-1005 Save and prune interaction test for large Vmax artifact.
Test type: Integration and memory.
Checks: artifact saved, then scaffold pruning frees non-required objects.

## 9. Trimming module plans

Targets:
- src/VmaxBuilder/trimming/Mvalue/trimming_config.py
- src/VmaxBuilder/trimming/Mvalue/trimming_implementation.py
- src/VmaxBuilder/trimming/Mvalue/diagnostics.py

- [ ] T-1101 Trimming threshold behavior matrix across sample groups.
Test type: Unit.
Checks: expected genes trimmed per sample and group.

- [ ] T-1102 Trimming integration with protein allocation path.
Test type: Integration.
Checks: trimmed outputs consumed correctly downstream.

- [ ] T-1103 Trimming diagnostics payload schema and plotting hooks.
Test type: Unit.
Checks: expected counts and alluvial/trendline-ready structures.

## 10. Package and typing surface plans

Targets:
- src/VmaxBuilder/__init__.py
- all module-level __init__.py files
- src/VmaxBuilder/typing_stubs/**

- [ ] T-1201 Import smoke tests for all public package entrypoints.
Test type: Unit.
Checks: import tree loads without side effects or missing optional deps in default mode.

- [ ] T-1202 Typing stubs consistency checks.
Test type: Static/integration.
Checks: key stub fields match implementation config fields for active modules.

## 11. Cross-stage integration plans

- [ ] T-1301 Full pipeline golden-run test on minimal fixture dataset.
Test type: End-to-end integration.
Checks: run completion, outputs and diagnostics present, schema snapshots stable.

- [ ] T-1302 Full pipeline reuse-existing-results mode test.
Test type: Integration and regression.
Checks: second run skips implementations with complete outputs, scaffold remains valid.

- [ ] T-1303 Overwrite plus reuse interaction test.
Test type: Integration.
Checks: overwrite takes precedence and recomputation occurs where required.

- [ ] T-1304 Future-stage dependency protection during pruning.
Test type: Regression.
Checks: objects needed later are not pruned early.

- [ ] T-1305 Diagnostics lifecycle integration test.
Test type: Integration.
Checks: before_run, during_run, after_run diagnostics saved in expected folders.

## 12. Performance and memory plans

- [ ] T-1401 Track peak memory in reaction_resolving on medium synthetic workload.
Test type: Performance and memory.
Checks: threshold budget not exceeded and growth curve plateaus after save and prune.

- [ ] T-1402 Track runtime envelope for GPR preprocessing on large reaction sets.
Test type: Performance.
Checks: runtime scaling near linear for representative input sizes.

- [ ] T-1403 Save throughput benchmark for artifact-heavy runs.
Test type: Performance.
Checks: file I/O throughput and serialization overhead by format.

## 13. Prioritized implementation order

1. T-0001
2. T-0002
3. T-0102
4. T-0121
5. T-1304
6. T-1005
7. T-0705
8. T-0905
9. T-1301
10. T-1302
11. T-0201
12. T-0211
13. T-0231
14. T-0512
15. T-0501
16. T-0601
17. T-1102
18. T-1401
19. T-1402
20. T-1403

## 14. Notes and constraints for future agents

- Prefer pytest parametrization for matrix-style tests.
- Keep tests deterministic and avoid network calls by default.
- Use temporary directories for all save/load tests.
- For performance and memory tests, mark with explicit pytest markers and separate from default quick suite.
- For modules already having tests, extend coverage first before creating redundant new files.
