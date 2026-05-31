"""Generated: validation needed.

Description:
    Central catalogue of allowed config values for refactored VmaxBuilder API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from VmaxBuilder.config.enums import (
    DiagnosticSeverity,
    KcatLevel,
    LoadResolutionMode,
    PrimaryOutputFormat,
    ProteinSourceMode,
    ReactionNotation,
    StageName,
    ValidationMode,
)


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """Generated: validation needed.

    Description:
        Describes one editable option catalogue entry.

    Args:
        name (str): Canonical option path.
        allowed_values (tuple[Any, ...] | None): Allowed values for the option.
        description (str): Human-readable guidance for the option.
        validation_mode (ValidationMode): Default validation mode for the option.
    """

    name: str
    allowed_values: tuple[Any, ...] | None
    description: str
    validation_mode: ValidationMode = ValidationMode.STRICT


VALIDATION_OPTION_SPECS: dict[str, OptionSpec] = {
    "validation.mode": OptionSpec(
        name="validation.mode",
        allowed_values=(ValidationMode.STRICT.value, ValidationMode.LENIENT.value),
        description="Global validation default for config and stage inputs.",
    ),
    "validation.field_mode": OptionSpec(
        name="validation.field_mode",
        allowed_values=(ValidationMode.STRICT.value, ValidationMode.LENIENT.value),
        description="Per-field validation override.",
    ),
    "validation.halt_severity": OptionSpec(
        name="validation.halt_severity",
        allowed_values=tuple(severity.value for severity in DiagnosticSeverity),
        description="Minimum severity that stops downstream stage execution.",
    ),
}


STAGE_OPTION_SPECS: dict[str, OptionSpec] = {
    "stage.name": OptionSpec(
        name="stage.name",
        allowed_values=tuple(stage.value for stage in StageName),
        description="Top-level orchestrator stage name.",
    ),
}


PROTEIN_OPTION_SPECS: dict[str, OptionSpec] = {
    "protein.source_mode": OptionSpec(
        name="protein.source_mode",
        allowed_values=tuple(mode.value for mode in ProteinSourceMode),
        description="Protein abundance source strategy.",
    ),
}


MODEL_OPTION_SPECS: dict[str, OptionSpec] = {
    "model.reaction_notation": OptionSpec(
        name="model.reaction_notation",
        allowed_values=tuple(notation.value for notation in ReactionNotation),
        description="Reaction identifier notation expected by model-stage processors.",
    ),
    "model.id_type": OptionSpec(
        name="model.id_type",
        allowed_values=(
            "ensembl",
            "entrez_gene_id",
            "symbol",
            "uniprot",
        ),
        description="Identifier provider used by model-stage and downstream mapping logic.",
    ),
    "model.level": OptionSpec(
        name="model.level",
        allowed_values=("gene", "transcript"),
        description="Gene or transcript granularity for model identifiers.",
    ),
}


EXPRESSION_OPTION_SPECS: dict[str, OptionSpec] = {
    "expression.transcript_aggregation_policy": OptionSpec(
        name="expression.transcript_aggregation_policy",
        allowed_values=("sum",),
        description="Transcript-to-gene aggregation policy used by expression preprocessing.",
    ),
    "expression.data_type": OptionSpec(
        name="expression.data_type",
        allowed_values=("TPM", "FPKM", "raw_counts"),
        description="Type of expression quantification provided in input.",
    ),
    "expression.thresholding": OptionSpec(
        name="expression.thresholding",
        allowed_values=(True, False),
        description=(
            "Whether to apply a data-type-specific thresholding to expression values."
        ),
    ),
    "expression.id_type": OptionSpec(
        name="expression.id_type",
        allowed_values=(
            "ensembl",
            "entrez_gene_id",
            "symbol",
        ),
        description="Identifier provider for expression features.",
    ),
    "expression.level": OptionSpec(
        name="expression.level",
        allowed_values=("gene", "transcript"),
        description="Gene or transcript granularity for expression identifiers.",
    ),
    "expression.sample_type_map": OptionSpec(
        name="expression.sample_type_map",
        allowed_values=None,
        description=(
            "Mapping from expression sample columns to PTR tissue/sample columns "
            "used in expression+PTR multiplication."
        ),
    ),
    "expression.id_translation_provider": OptionSpec(
        name="expression.id_translation_provider",
        allowed_values=("auto", "mygene"),
        description="Provider used for expression identifier translation lookups.",
    ),
}


PTR_OPTION_SPECS: dict[str, OptionSpec] = {
    "ptr.pretransformed_type": OptionSpec(
        name="ptr.pretransformed_type",
        allowed_values=("none", "log10", "log2", "ln"),
        description="Log-scale applied to raw PTR input before linear conversion.",
    ),
    "ptr.missing_value_strategy": OptionSpec(
        name="ptr.missing_value_strategy",
        allowed_values=("weighted_median", "median"),
        description="Within-sample imputation strategy for observed-but-missing PTR values.",
    ),
    "ptr.partial_missing_imputation_statistic": OptionSpec(
        name="ptr.partial_missing_imputation_statistic",
        allowed_values=("median", "mean", "mode", "max", "min"),
        description="Row statistic used for within-sample PTR imputation.",
    ),
    "ptr.partial_missing_use_weighted": OptionSpec(
        name="ptr.partial_missing_use_weighted",
        allowed_values=(True, False),
        description="Apply tissue-scaling weights during within-sample PTR imputation.",
    ),
    "ptr.unobserved_gene_imputation_strategy": OptionSpec(
        name="ptr.unobserved_gene_imputation_strategy",
        allowed_values=("sample_after_imputation", "sample_before_imputation"),
        description="Strategy to fill genes present in expression but absent from PTR.",
    ),
    "ptr.unobserved_gene_imputation_statistic": OptionSpec(
        name="ptr.unobserved_gene_imputation_statistic",
        allowed_values=("median", "mean", "mode", "max", "min"),
        description="Per-sample statistic used when imputing unobserved genes.",
    ),
    "ptr.unobserved_gene_imputation_reference": OptionSpec(
        name="ptr.unobserved_gene_imputation_reference",
        allowed_values=(
            "after_within_sample_imputation",
            "before_within_sample_imputation",
        ),
        description=(
            "Reference frame used to compute statistics for unobserved-gene imputation."
        ),
    ),
    "ptr.use_special_groups_for_unobserved_imputation": OptionSpec(
        name="ptr.use_special_groups_for_unobserved_imputation",
        allowed_values=(True, False),
        description=(
            "Enable independent unobserved-gene imputation per configured special groups."
        ),
    ),
}


LOADING_OPTION_SPECS: dict[str, OptionSpec] = {
    "loading.results_dir_name": OptionSpec(
        name="loading.results_dir_name",
        allowed_values=("VmaxResults",),
        description="User-facing output folder name for generated results.",
    ),
    "loading.primary_output_format": OptionSpec(
        name="loading.primary_output_format",
        allowed_values=tuple(output_format.value for output_format in PrimaryOutputFormat),
        description="Primary file format used when saving output tables.",
    ),
    "loading.write_additional_csv": OptionSpec(
        name="loading.write_additional_csv",
        allowed_values=(True, False),
        description="Whether additional csv output copies are written.",
    ),
}


VMAX_OPTION_SPECS: dict[str, OptionSpec] = {
    "kcat.level": OptionSpec(
        name="kcat.level",
        allowed_values=tuple(level.value for level in KcatLevel),
        description="Canonical kcat level exposed by a predictor or converter.",
    ),
}


RESOLUTION_OPTION_SPECS: dict[str, OptionSpec] = {
    "load.resolution_mode": OptionSpec(
        name="load.resolution_mode",
        allowed_values=tuple(mode.value for mode in LoadResolutionMode),
        description="Path resolution policy used when loading inputs and outputs.",
    ),
}


OPTION_SPECS: dict[str, OptionSpec] = {
    **VALIDATION_OPTION_SPECS,
    **STAGE_OPTION_SPECS,
    **PROTEIN_OPTION_SPECS,
    **MODEL_OPTION_SPECS,
    **EXPRESSION_OPTION_SPECS,
    **PTR_OPTION_SPECS,
    **LOADING_OPTION_SPECS,
    **VMAX_OPTION_SPECS,
    **RESOLUTION_OPTION_SPECS,
}


def get_allowed_values(option_name: str) -> tuple[Any, ...] | None:
    """Generated: validation needed.

    Description:
        Return allowed values for one known option catalogue entry.

    Args:
        option_name (str): Canonical option path to inspect.

    Returns:
        tuple[Any, ...] | None: Allowed values if option is known, else None.
    """

    option_spec = OPTION_SPECS.get(option_name)
    if option_spec is None:
        return None
    return option_spec.allowed_values
