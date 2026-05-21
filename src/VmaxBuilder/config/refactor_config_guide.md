# VmaxBuilder Refactored Config Guide

## Purpose
This document shows how to configure refactored VmaxBuilder from API-development perspective.
It explains:

- where stage-specific strategy values go
- where allowed values live
- how strict validation works
- which options are still unresolved

## Mental Model
Use one root config object: `APIConfig`.

It contains:

- `validation`: global + field-level validation policy
- `loading`: input/output path resolution policy
- `model`: model-stage config
- `protein`: protein-abundance config
- `allocation`: IFP allocation config
- `vmax`: Kcat + reaction-capacity config
- `metadata`: free-form run metadata

Rule of thumb:

- cross-cutting values go into explicit top-level config fields
- strategy-specific values go into `StageConfig.options`
- field validation overrides go into `ValidationPolicy.field_modes`
- stage validation overrides go into `ValidationPolicy.stage_modes`

## Where to Put Values

### 1. Global behavior
Put global behavior in `APIConfig.validation` and `APIConfig.loading`.

Examples:

- strict vs lenient validation
- halt severity
- exact file paths
- discovery roots
- filename preferences

Direct assignment style is supported:

```python
config.loading.model_path = Path(r"C:\\data\\model.json")
config.loading.expression_path = Path(r"C:\\data\\expression.csv")
config.protein.tissue_type = "heart"
```

### 2. Stage strategy key
Put selected strategy name in `StageConfig.method`.

Examples:

- protein strategy key
- allocation strategy key
- vmax/kcat strategy key

### 3. Strategy-specific parameters
Put strategy-specific values in `StageConfig.options`.

Examples:

- PTR imputation method
- expression transformation method
- GPR aggregation method
- kcat predictor or resolver sub-parameters

### 4. Allowed values
Put shared allowed values in `src/VmaxBuilder/config/options.py`.

That file contains `OPTION_SPECS`, which is the canonical catalogue for values that should fail fast.

### 5. Validation overrides
Put per-field or per-stage strictness in `ValidationPolicy`.

Examples:

- `field_modes={"protein.tissue_type": ValidationMode.LENIENT}`
- `stage_modes={StageName.PROTEIN: ValidationMode.LENIENT}`

## Example: API Development Setup

```python
from pathlib import Path

from VmaxBuilder.config import (
    APIConfig,
    AllocationConfig,
    DiagnosticSeverity,
    KcatLevel,
    LoadResolutionMode,
    LoadingPolicy,
    ModelConfig,
    ProteinConfig,
    ProteinSourceMode,
    StageName,
    ValidationMode,
    ValidationPolicy,
    VmaxConfig,
)

config = APIConfig(
    validation=ValidationPolicy(
        mode=ValidationMode.STRICT,
        field_modes={
            "protein.tissue_type": ValidationMode.LENIENT,
        },
        stage_modes={
            StageName.PROTEIN: ValidationMode.STRICT,
        },
        halt_severity=DiagnosticSeverity.ERROR,
    ),
    loading=LoadingPolicy(
        resolution_mode=LoadResolutionMode.EXACT_THEN_DISCOVER,
        model_path=Path(r"C:\data\model.json"),
        expression_path=Path(r"C:\data\expression.csv"),
        search_roots=(Path(r"C:\data"), Path(r"C:\fallback")),
        preferred_filenames={
            "model": ("model_", "Model_"),
            "expression": ("data_",),
        },
        allow_ambiguous_discovery=False,
    ),
    model=ModelConfig(
        close_model=True,
        unforce_open_reactions=True,
        allow_irreversible_input=True,
    ),
    protein=ProteinConfig(
        source_mode=ProteinSourceMode.EXPRESSION_PTR,
        expression_scale="log10",
        ptr_scale="log10",
        tissue_type="heart",
        allow_direct_proteomics=False,
        ptr_required=True,
    ),
    allocation=AllocationConfig(
        trim_genes=True,
        gpr_or_strategy="sum",
        gpr_and_strategy="trimmin3",
        impute_expressionless_reactions=True,
    ),
    vmax=VmaxConfig(
        kcat_level=KcatLevel.IFP_REACTION,
        kcat_strategy="unikp",
        allow_missing_kcat=True,
    ),
    metadata={
        "run_name": "cardio_refactor_test",
        "author": "example",
    },
)
```

## Example: Where Strategy Parameters Go

Use `StageConfig.options` for knobs that vary between implementations.

```python
protein_strategy_options = {
    "ptr_missing_values": "weighted_median",
    "ptr_imputation_mode": "sample_after_imputation",
    "expression_transformation": "log10",
}

allocation_strategy_options = {
    "gpr_or_aggregation": "sum",
    "gpr_and_aggregation": "trimmin3",
    "trim_genes_percentile": (2.5, 97.5),
}

vmax_strategy_options = {
    "predictor": "UniKP",
    "input_level": "L1",
    "conversion_policy": "auto_to_L4",
}
```

Current rule:

- if the option is shared and stable, promote it to a typed config field
- if the option is strategy-specific, keep it in `options`
- if the option should be validated early, add it to `OPTION_SPECS`

Note on loading fields:

- typed loading fields (`model_path`, `expression_path`, `ptr_path`, etc.) are preferred for common inputs
- `exact_paths` remains for uncommon/custom artifact keys
- call `config.loading.get_effective_exact_paths()` to get merged map

## Example: Allowed Values

Allowed values are stored in `src/VmaxBuilder/config/options.py`.

Example structure:

```python
protein_source_spec = OPTION_SPECS["protein.source_mode"]
validation_mode_spec = OPTION_SPECS["validation.mode"]
load_resolution_spec = OPTION_SPECS["load.resolution_mode"]
```

That means:

- `validation.mode` only accepts `strict` or `lenient`
- `protein.source_mode` only accepts the registered protein source modes
- `load.resolution_mode` only accepts the registered loading behaviors

When a new strategy needs a new allowed value:

1. add it to the relevant enum or option catalogue
2. add its registry entry
3. add tests
4. document it here

## Implemented First Slice: Model + Loading Options

Model options now explicitly supported in typed config:

- `model.close_model`
- `model.unforce_open_reactions`
- `model.allow_irreversible_input`
- `model.reaction_notation`
- `model.unbounded_lower_bound`
- `model.unbounded_upper_bound`

Loading options now explicitly supported in typed config:

- `loading.model_path`
- `loading.expression_path`
- `loading.ptr_path`
- `loading.proteomics_path`
- `loading.kcat_path`
- `loading.output_path`
- `loading.results_dir_name` (fixed user-facing default: `VmaxResults`)
- `loading.primary_output_format` (currently `feather`)
- `loading.write_additional_csv`

Central allowed values remain in `src/VmaxBuilder/config/options.py`.

## Where Specific Strategy Values Should Go

### Protein stage
Put protein strategy selection in:

- `protein.method`

Put protein strategy parameters in:

- `protein.options`

Examples:

- PTR preprocessing method
- PTR imputation method
- proteomics preprocessing method
- expression transformation details

### Allocation stage
Put allocation strategy selection in:

- `allocation.method`

Put allocation strategy parameters in:

- `allocation.options`

Examples:

- OR aggregation policy
- AND aggregation policy
- trimming thresholds
- imputation fallback policy

### Vmax stage
Put kcat strategy selection in:

- `vmax.method`

Put kcat conversion and resolution parameters in:

- `vmax.options`

Examples:

- predictor method
- canonical entry level
- conversion override policy
- missing-kcat fallback behavior

## Validation and Discovery Rules

### Strict default
Validation should fail early by default.

### Lenient opt-in
Lenient mode is allowed, but only when explicitly requested.

### Field-level leniency
Some fields should not be globally strict.

Example:

- `protein.tissue_type` should be lenient, because tissue labels may be noisy metadata

### Stage-level early validation
If PTR is enabled, PTR-related values should be validated as soon as protein stage is initialized.
That keeps bad config from failing after expensive runtime work.

### File discovery
Use this order:

1. explicit path from config
2. fallback discovery in search roots
3. error if not found or ambiguous, unless lenient discovery is explicitly enabled

## Options Still Unclear
These are the current refactor gaps I would not freeze yet.

| Option / Area | Why unclear | Suggested direction | Current state |
|---|---|---|---|
| `protein.expression_scale` | Need final canonical scale names | Keep as explicit field, validate against small enum | unresolved |
| `protein.ptr_scale` | Same as expression scale | Keep as explicit field, validate early | unresolved |
| `protein.tissue_type` | Metadata-like, often noisy | Lenient by default at field level | likely lenient |
| `protein.allow_direct_proteomics` | May overlap with `source_mode` | Decide if redundant or keep as compatibility-free toggle | unresolved |
| `protein.ptr_required` | May be derived from `source_mode` | Decide if explicit flag is needed | unresolved |
| `allocation.gpr_or_strategy` | Naming still legacy-flavored | Rename to clearer policy term if possible | unresolved |
| `allocation.gpr_and_strategy` | Same as above | Rename to clearer policy term if possible | unresolved |
| `allocation.impute_expressionless_reactions` | Could belong in allocation or downstream fallback policy | Keep in allocation for now, revisit after orchestration draft | unresolved |
| `vmax.kcat_strategy` | Could mean predictor, resolver, or whole kcat pipeline | Split into clearer predictor/resolver fields if needed | unresolved |
| `vmax.allow_missing_kcat` | Might belong in failure policy instead | Decide if this is stage-local fallback or global policy | unresolved |
| `loading.preferred_filenames` | Pattern semantics not locked | Keep as fallback hints, not hard contract | unresolved |
| `loading.search_roots` | Need precedence rules for multiple roots | Use ordered search roots | likely fixed |
| `loading.allow_ambiguous_discovery` | Need deterministic tie-breaking policy | Keep false by default | likely fixed |
| `stage.options` | Too generic for long-term typed config | Use as temporary strategy payload bag | transitional |

## Practical Recommendation
For this phase:

- keep config simple
- keep allowed values centralized
- keep strategy-specific knobs inside `options`
- promote stable knobs into typed config fields later
- avoid backward-compat aliases
- document unresolved values before they become hard-coded

## Next Refactor Step
After the legacy orchestration files are pasted, map every old option into one of:

- `typed field`
- `stage.options`
- `validation policy`
- `loading policy`
- `allowed-values catalogue`
- `drop`

That mapping will make the config refactor mechanical.
