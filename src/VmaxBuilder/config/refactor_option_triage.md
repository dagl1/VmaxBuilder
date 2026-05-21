# Refactor Option Triage

## Purpose
This file maps legacy option intent to new package ownership.
No backward-compatibility aliases are planned.

## Scope Rules

- Legacy names are triage input only.
- New names are clean API targets.
- Keep only options that match `model -> protein -> allocation -> vmax` workflow.
- `task_list` options are dropped from VmaxBuilder.

## Triage Status

- Step 2 baseline triage: in progress
- Step 4 implementation target now: model options

## Model Option Triage (Implemented First)

| Legacy intent | New option name | Owner | Keep/Drop | Notes | Default |
|---|---|---|---|---|
| `should_close_model` | `model.close_model` | `ModelConfig` | Keep | Boolean | False |
| `should_unforce_open_reactions` | `model.unforce_open_reactions` | `ModelConfig` | Keep | Boolean | False |
| `model_is_already_irreversible` | `model.allow_irreversible_input` | `ModelConfig` | Drop | Inverted semantic
removed |
| `alternative_reaction_notation` | `model.reaction_notation` | `ModelConfig` | Drop | Enum planned |
| `unbounded_lower_bound_value` | `model.unbounded_lower_bound` | `ModelConfig` | Drop | Numeric bound |
| `unbounded_upper_bound_value` | `model.unbounded_upper_bound` | `ModelConfig` | Drop | Numeric bound |
| `filename_model` | `loading.model_path` | `LoadingPolicy` | Keep (renamed) | Explicit path preferred | None |
| `model_version` | `loading.model_path` or registry id | `LoadingPolicy` / model strategy | Split | Path-first design |
| `task_list` | n/a | n/a | Drop | Out of package scope |

## Loading and Results Triage

| Legacy intent | New option name | Owner | Keep/Drop    | Notes | Default |
|---|---|---|--------------|---|
| `main_data_folder` | `loading.search_roots` | `LoadingPolicy` | Keep (renamed) | Tuple of roots |
| `use_independent_datafolder_filepaths` | `loading.resolution_mode` | `LoadingPolicy` | Keep (renamed) | Explicit mode enum |
| `combinations` folder naming | `loading.results_dir_name` = `VmaxResults` | `LoadingPolicy` | Keep (renamed) | User-facing outputs root |
| `_overwriting_combination_name` | n/a | n/a | Drop         | Legacy private override |
| `_overwritten_parent_combination_folder` | n/a | n/a | Drop         | Legacy private override |
| `save_format_data` | `loading.primary_output_format` | `LoadingPolicy` | drop         | `feather` only currently |
| `save_format_should_create_additional_CSV` | `loading.write_additional_csv` | `LoadingPolicy` | Keep         | Optional bloat export |
| `parquet` save path | n/a | n/a | Drop (for now) | Out of current scope |

## Protein / Allocation / Vmax Triage (Pending Deep Pass)

- `protein.*`: keep only options required for protein abundance construction.
- `allocation.*`: keep options that control IFP split/allocation/imputation.
- `vmax.*`: keep kcat enable/disable, canonical-level conversion, fallback policy.
- Remove diagnostics toggles from business config where possible and move to diagnostics policy.

## Next Action

1. Finish model + loading option implementation in typed config and allowed-values catalogue.
2. Add validation tests for strict/lenient behavior of these options.
3. Continue triage table with protein options next.
