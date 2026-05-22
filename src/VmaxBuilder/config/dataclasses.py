"""Generated: validation needed.

Description:
    Dataclass configuration models for refactored VmaxBuilder API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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


@dataclass(slots=True)
class ValidationPolicy:
    """Generated: validation needed.

    Description:
        Validation policy with strict-by-default behavior and per-field overrides.

    Args:
        mode (ValidationMode): Global default validation mode.
        field_modes (dict[str, ValidationMode]): Per-field validation overrides.
        stage_modes (dict[StageName, ValidationMode]): Per-stage validation overrides.
        halt_severity (DiagnosticSeverity): Minimum severity that stops downstream execution.
    """

    mode: ValidationMode = ValidationMode.STRICT
    field_modes: dict[str, ValidationMode] = field(default_factory=dict)
    stage_modes: dict[StageName, ValidationMode] = field(default_factory=dict)
    halt_severity: DiagnosticSeverity = DiagnosticSeverity.ERROR

    def resolve_mode(
        self,
        field_name: str,
        stage_name: StageName | None = None,
    ) -> ValidationMode:
        """Generated: validation needed.

        Description:
            Resolve validation mode for one field, optionally within one stage.

        Args:
            field_name (str): Canonical field name.
            stage_name (StageName | None): Optional stage name for stage-local overrides.

        Returns:
            ValidationMode: Resolved validation mode.
        """

        if field_name in self.field_modes:
            return self.field_modes[field_name]
        if stage_name is not None and stage_name in self.stage_modes:
            return self.stage_modes[stage_name]
        return self.mode


@dataclass(slots=True)
class LoadingPolicy:
    """Generated: validation needed.

    Description:
        Loading policy that prefers explicit paths and optionally falls back to discovery.

    Args:
        resolution_mode (LoadResolutionMode): Path resolution order.
        model_path (Path | None): Optional explicit model file path.
        model_object (Any | None): Optional in-memory model object provided by caller.
        expression_path (Path | None): Optional explicit expression file path.
        ptr_path (Path | None): Optional explicit PTR file path.
        proteomics_path (Path | None): Optional explicit proteomics file path.
        kcat_path (Path | None): Optional explicit kcat file path.
        output_path (Path | None): Optional explicit output root path.
        results_dir_name (str): User-facing results folder name.
        primary_output_format (PrimaryOutputFormat): Primary format for saved tables.
        write_additional_csv (bool): Whether to write additional csv copies.
        exact_paths (dict[str, Path]): Explicit artifact paths keyed by logical name.
        in_memory_inputs (dict[str, Any]): In-memory input objects keyed by logical name.
        discovery_prefixes (dict[str, tuple[str, ...]]): Filename prefixes used when
            resolving directories.
        discovery_extensions (dict[str, tuple[str, ...]]): Allowed file extensions used
            during discovery.
        search_roots (tuple[Path, ...]): Roots used for fallback discovery.
        preferred_filenames (dict[str, tuple[str, ...]]): Preferred filename patterns by key.
        allow_ambiguous_discovery (bool): Allow multiple matches during fallback discovery.
    """

    resolution_mode: LoadResolutionMode = LoadResolutionMode.EXACT_THEN_DISCOVER
    model_path: Path | None = None
    model_object: Any | None = None
    expression_path: Path | None = None
    ptr_path: Path | None = None
    proteomics_path: Path | None = None
    kcat_path: Path | None = None
    output_path: Path | None = None
    results_dir_name: str = "VmaxResults"
    primary_output_format: PrimaryOutputFormat = PrimaryOutputFormat.FEATHER
    write_additional_csv: bool = False
    exact_paths: dict[str, Path] = field(default_factory=dict)
    in_memory_inputs: dict[str, Any] = field(default_factory=dict)
    discovery_prefixes: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "model": ("model",),
            "expression": ("data__",),
            "ptr": ("ptr__",),
            "proteomics": ("data__",),
        }
    )
    discovery_extensions: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "model": (".json", ".xml", ".mat"),
            "expression": (".csv", ".xlsx", ".tsv"),
            "ptr": (".csv", ".xlsx", ".tsv"),
            "proteomics": (".csv", ".xlsx", ".tsv"),
        }
    )
    search_roots: tuple[Path, ...] = ()
    preferred_filenames: dict[str, tuple[str, ...]] = field(default_factory=dict)
    allow_ambiguous_discovery: bool = False

    def get_effective_exact_paths(self) -> dict[str, Path]:
        """Generated: validation needed.

        Description:
            Return merged explicit path map from typed path fields and generic exact_paths.

        Returns:
            dict[str, Path]: Effective explicit path mapping keyed by artifact name.
        """

        typed_paths = {
            "model": self.model_path,
            "expression": self.expression_path,
            "ptr": self.ptr_path,
            "proteomics": self.proteomics_path,
            "kcat": self.kcat_path,
            "output": self.output_path,
        }
        merged_paths = dict(self.exact_paths)
        for artifact_name, artifact_path in typed_paths.items():
            if artifact_path is not None:
                merged_paths[artifact_name] = artifact_path
        return merged_paths

    def iter_search_roots(self, artifact_name: str) -> tuple[Path, ...]:
        """Generated: validation needed.

        Description:
            Return search roots for one artifact in stable evaluation order.

        Args:
            artifact_name (str): Logical artifact key.

        Returns:
            tuple[Path, ...]: Candidate roots in search order.
        """

        return self.search_roots

    def get_effective_in_memory_inputs(self) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Return merged in-memory inputs map from typed fields and generic in_memory_inputs.

        Returns:
            dict[str, Any]: Effective in-memory inputs keyed by artifact name.
        """

        typed_inputs = {
            "model": self.model_object,
        }
        merged_inputs = dict(self.in_memory_inputs)
        for artifact_name, artifact_object in typed_inputs.items():
            if artifact_object is not None:
                merged_inputs[artifact_name] = artifact_object
        return merged_inputs

    def get_output_directories(self) -> tuple[Path, ...]:
        """Generated: validation needed.

        Description:
            Return output directories that should exist before orchestration run.

        Returns:
            tuple[Path, ...]: Output root and run-results directory when configured.
        """

        output_root = self.get_effective_exact_paths().get("output")
        if output_root is None:
            return ()
        return (output_root, output_root / self.results_dir_name)

    def get_discovery_prefixes(self, artifact_name: str) -> tuple[str, ...]:
        """Generated: validation needed.

        Description:
            Return configured filename prefixes for one artifact discovery key.

        Args:
            artifact_name (str): Logical artifact key.

        Returns:
            tuple[str, ...]: Lower/upper agnostic filename prefixes for discovery.
        """

        return self.discovery_prefixes.get(artifact_name, ())

    def get_discovery_extensions(self, artifact_name: str) -> tuple[str, ...]:
        """Generated: validation needed.

        Description:
            Return configured allowed extensions for one artifact discovery key.

        Args:
            artifact_name (str): Logical artifact key.

        Returns:
            tuple[str, ...]: File extensions used during discovery.
        """

        return self.discovery_extensions.get(artifact_name, ())


@dataclass(slots=True)
class StageConfig:
    """Generated: validation needed.

    Description:
        Shared stage configuration model for all top-level pipeline stages.

    Args:
        enabled (bool): Enable or disable stage execution.
        method (str | None): Selected strategy key for stage implementation.
        options (dict[str, Any]): Arbitrary stage-local options.
        field_validation_modes (dict[str, ValidationMode]): Per-field validation overrides.
    """

    enabled: bool = True
    method: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    field_validation_modes: dict[str, ValidationMode] = field(default_factory=dict)


@dataclass(slots=True)
class ModelConfig(StageConfig):
    """Generated: validation needed.

    Description:
        Configuration for model loading and reaction notation convention.

    Args:
        reaction_notation (ReactionNotation): Reaction identifier convention.
        make_copy (bool): Copy model at preprocessing start before mutation. Default True.
        target_id_type (str): Canonical identifier type expected in model entities.
    """

    reaction_notation: ReactionNotation = ReactionNotation.STANDARD
    make_copy: bool = True
    target_id_type: str = "ensembl_gene_id"


@dataclass(slots=True)
class ExpressionInputConfig:
    """Generated: validation needed.

    Description:
        Expression input option group used by protein-stage expression->protein flow.

    Args:
        id_type (str): Identifier namespace for expression features.
        transformation_state (str): Data transform state, e.g. log or linear.
        origin_transcript_gene_level (str): Source granularity, transcript or gene.
        data_type (str): Expression quantification type, e.g. TPM, geTMM, raw_reads.
        thresholding (bool | str): Disabled flag or thresholding strategy name.
    """

    id_type: str = "ensembl_gene_id"
    transformation_state: str = "log"
    origin_transcript_gene_level: str = "gene"
    data_type: str = "TPM"
    thresholding: bool | str = False


@dataclass(slots=True)
class PTRInputConfig:
    """Generated: validation needed.

    Description:
        PTR input option group used by expression+PTR protein abundance flow.

    Args:
        id_type (str): Identifier namespace for PTR features.
        transformation_state (str): Data transform state, e.g. log or linear.
        origin_transcript_gene_level (str): Source granularity, transcript or gene.
    """

    id_type: str = "ensembl_gene_id"
    transformation_state: str = "log"
    origin_transcript_gene_level: str = "gene"


@dataclass(slots=True)
class ProteomicsInputConfig:
    """Generated: validation needed.

    Description:
        Proteomics input option group used by direct-proteomics protein flow.

    Args:
        id_type (str): Identifier namespace for proteomics features.
        origin_transcript_gene_level (str): Source granularity, transcript or gene.
        transformation_state (str): Data transform state, e.g. log or linear.
        imputation_strategy (str): Primary imputation strategy.
        fallback_imputation_strategy (str): Fallback imputation strategy.
    """

    id_type: str = "uniprot"
    origin_transcript_gene_level: str = "gene"
    transformation_state: str = "log"
    imputation_strategy: str = "weighted_gene_median"
    fallback_imputation_strategy: str = "weighted_sample_median"


@dataclass(slots=True)
class ProteinConfig(StageConfig):
    """Generated: validation needed.

    Description:
        Configuration for protein abundance construction.

    Args:
        source_mode (ProteinSourceMode): Protein source pathway.
        ptr_method (str): PTR submodule strategy key for expression+PTR mode.
        tissue_type (str | None): Optional tissue metadata.
        allow_direct_proteomics (bool): Enable direct proteomics pathway.
        ptr_required (bool): Require PTR pathway when expression integration is selected.
    """

    source_mode: ProteinSourceMode = ProteinSourceMode.EXPRESSION_PTR
    ptr_method: str = "ptr_weighted_median"
    tissue_type: str | None = None
    allow_direct_proteomics: bool = False
    ptr_required: bool = False


@dataclass(slots=True)
class AllocationConfig(StageConfig):
    """Generated: validation needed.

    Description:
        Configuration for IFP allocation and reaction capacity staging.

    Args:
        trim_genes (bool): Enable gene trimming before allocation.
        gpr_or_strategy (str): OR-rule aggregation strategy.
        gpr_and_strategy (str): AND-rule aggregation strategy.
        impute_expressionless_reactions (bool): Enable fallback imputation.
    """

    trim_genes: bool = True
    gpr_or_strategy: str = "sum"
    gpr_and_strategy: str = "trimmin3"
    impute_expressionless_reactions: bool = True


@dataclass(slots=True)
class VmaxConfig(StageConfig):
    """Generated: validation needed.

    Description:
        Configuration for kcat resolution and reaction capacity computation.

    Args:
        kcat_level (KcatLevel): Canonical kcat level consumed by Vmax.
        kcat_strategy (str | None): Selected kcat predictor or resolver strategy.
        allow_missing_kcat (bool): Allow fallback when kcat is unavailable.
    """

    kcat_level: KcatLevel = KcatLevel.IFP_REACTION
    kcat_strategy: str | None = None
    allow_missing_kcat: bool = True


@dataclass(slots=True)
class APIConfig:
    """Generated: validation needed.

    Description:
        Root configuration container for orchestrator, validation, loading, and stage config.

    Args:
        validation (ValidationPolicy): Validation policy for config and stage inputs.
        loading (LoadingPolicy): File/path loading policy.
        run_target_transcript_gene_level (str): Target analysis granularity,
            transcript or gene.
        model (ModelConfig): Model stage configuration.
        expression (ExpressionInputConfig): Expression input option group.
        ptr (PTRInputConfig): PTR input option group.
        proteomics (ProteomicsInputConfig): Proteomics input option group.
        protein (ProteinConfig): Protein stage configuration.
        allocation (AllocationConfig): Allocation stage configuration.
        vmax (VmaxConfig): Vmax stage configuration.
        metadata (dict[str, Any]): Arbitrary run metadata.
    """

    validation: ValidationPolicy = field(default_factory=ValidationPolicy)
    loading: LoadingPolicy = field(default_factory=LoadingPolicy)
    run_target_transcript_gene_level: str = "gene"
    model: ModelConfig = field(default_factory=ModelConfig)
    expression: ExpressionInputConfig = field(default_factory=ExpressionInputConfig)
    ptr: PTRInputConfig = field(default_factory=PTRInputConfig)
    proteomics: ProteomicsInputConfig = field(default_factory=ProteomicsInputConfig)
    protein: ProteinConfig = field(default_factory=ProteinConfig)
    allocation: AllocationConfig = field(default_factory=AllocationConfig)
    vmax: VmaxConfig = field(default_factory=VmaxConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_stage_config(
        self,
        stage_name: StageName,
    ) -> ModelConfig | ProteinConfig | AllocationConfig | VmaxConfig:
        """Generated: validation needed.

        Description:
            Return stage configuration object for one top-level stage.

        Args:
            stage_name (StageName): Stage name to resolve.

        Returns:
            StageConfig: Requested stage configuration object.

        Raises:
            ValueError: If stage name is unknown.
        """

        stage_map: dict[
            StageName, ModelConfig | ProteinConfig | AllocationConfig | VmaxConfig
        ] = {
            StageName.MODEL: self.model,
            StageName.PROTEIN: self.protein,
            StageName.ALLOCATION: self.allocation,
            StageName.VMAX: self.vmax,
        }
        try:
            return stage_map[stage_name]
        except KeyError as error:
            raise ValueError(f"Unknown stage: {stage_name!s}") from error
