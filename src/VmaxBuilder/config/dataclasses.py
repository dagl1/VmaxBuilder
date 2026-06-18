"""Generated: validation needed.

Description:
    Dataclass configuration models for refactored VmaxBuilder API.
"""

from __future__ import annotations

import importlib
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
        output_path (Path): Required output directory root used directly,
            or as parent directory when ``create_dynamically_named_results`` is enabled.
        create_dynamically_named_results (bool): Whether to derive a run-specific
            child directory name from configured input paths.
        results_dir_name (str): Legacy user-facing results folder name.
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
    create_dynamically_named_results: bool = False
    results_dir_name: str = "VmaxResults"
    primary_output_format: PrimaryOutputFormat = PrimaryOutputFormat.FEATHER
    write_additional_csv: bool = False
    exact_paths: dict[str, Path] = field(default_factory=dict)
    in_memory_inputs: dict[str, Any] = field(default_factory=dict)
    discovery_prefixes: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "model": ("model_",),
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
        self._extend_user_paths()

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

    def _extend_user_paths(self) -> None:
        """
        Description:
            Takes userpaths and checks if `~` is present, if so, calls Path.expanduser()
            and modifies Config.
        """
        typed_paths = {
            "model_path": self.model_path,
            "expression_path": self.expression_path,
            "ptr_path": self.ptr_path,
            "proteomics_path": self.proteomics_path,
            "kcat_path": self.kcat_path,
            "output_path": self.output_path,
        }
        for artifact_name, artifact_path in typed_paths.items():
            if artifact_path is None:
                continue
            if "~/" in str(artifact_path):
                print(f"Changing path from {artifact_path} to {artifact_path.expanduser()}")
                setattr(self, artifact_name, artifact_path.expanduser())

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
            Return resolved output directories that should exist before orchestration run.

        Returns:
            tuple[Path, ...]: Final output directory plus standard subdirectories.
        """

        resolved_output_directory = self.get_resolved_output_directory()
        return (
            resolved_output_directory,
            resolved_output_directory / "artifacts",
            resolved_output_directory / "diagnostics",
            resolved_output_directory / "metadata",
            resolved_output_directory / "outputs",
        )

    def get_resolved_output_directory(self) -> Path:
        """Generated: validation needed.

        Description:
            Resolve final output directory from ``output_path`` and optional
            dynamic path naming.

        Returns:
            Path: Final run output directory.

        Raises:
            ValueError: When ``output_path`` is missing or dynamic naming cannot
                derive any path components.
        """

        if self.output_path is None:
            raise ValueError(
                "loading.output_path is required. "
                "Set explicit output directory before running."
            )

        base_output_directory = Path(self.output_path)
        if not self.create_dynamically_named_results:
            return base_output_directory
        return base_output_directory / self.build_dynamic_results_directory_name()

    def build_dynamic_results_directory_name(self) -> str:
        """Generated: validation needed.

        Description:
            Build deterministic run directory name from configured input paths.

        Returns:
            str: Sanitised directory name composed from configured input-path tails.

        Raises:
            ValueError: When no configured path or in-memory input can contribute
                a directory-name component.
        """

        path_components: list[str] = []
        candidate_paths = {
            "model": self.model_path,
            "expression": self.expression_path,
            "ptr": self.ptr_path,
            "proteomics": self.proteomics_path,
            "kcat": self.kcat_path,
        }
        for artifact_name, artifact_path in candidate_paths.items():
            if artifact_path is not None:
                path_components.append(
                    self._extract_output_name_component(Path(artifact_path))
                )
                continue
            if artifact_name == "model" and self.model_object is not None:
                path_components.append(f"{artifact_name}_in_memory")
                continue
            if artifact_name in self.in_memory_inputs:
                path_components.append(f"{artifact_name}_in_memory")

        unique_components = list(dict.fromkeys(path_components))
        if not unique_components:
            raise ValueError(
                "loading.create_dynamically_named_results requires at least one configured "
                "model/expression/ptr/proteomics/kcat path or in-memory input."
            )
        return "__".join(unique_components)

    @staticmethod
    def _extract_output_name_component(path: Path) -> str:
        """Generated: validation needed.

        Description:
            Extract sanitised trailing directory-like component from a configured path.

        Args:
            path (Path): Configured file or directory path.

        Returns:
            str: Sanitised path-tail component.
        """

        is_file_like = path.suffix != ""
        raw_component = path.parent.name if is_file_like else path.name
        if raw_component == "":
            raw_component = path.stem if is_file_like else str(path)
        return LoadingPolicy._sanitise_output_name_component(raw_component)

    @staticmethod
    def _sanitise_output_name_component(component: str) -> str:
        """Generated: validation needed.

        Description:
            Sanitise one output-directory name component for filesystem safety.

        Args:
            component (str): Raw component text.

        Returns:
            str: Filesystem-safe component.
        """

        replaced_component = component.strip().replace(" ", "_")
        sanitised_component = "".join(
            character if character.isalnum() or character in {"-", "_", "."} else "_"
            for character in replaced_component
        ).strip("_.-")
        return sanitised_component or "unknown"

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
        id_type (str): Canonical identifier provider expected in model entities.
        level (str): Gene or transcript level granularity.
    """

    reaction_notation: ReactionNotation = ReactionNotation.STANDARD
    make_copy: bool = True
    id_type: str = "ensembl"
    level: str = "gene"


@dataclass(slots=True)
class ExpressionInputConfig:
    """Generated: validation needed.

    Description:
        Expression input option group used by protein-stage expression->protein flow.

    Args:
        id_type (str | None): Identifier provider for expression features.
        level (str): Gene or transcript level granularity.
        sample_type_map (dict[str, str] | str | None): Mapping from expression
            sample columns to PTR tissue/sample columns used by expression+PTR
            protein flow. ``str`` maps all expression columns to one PTR
            column; ``dict`` maps each expression column individually.
        transformation_state (str): Data transform state, e.g. log or linear.
        data_type (str): Expression quantification type, e.g. TPM, geTMM, raw_reads.
        thresholding (bool | str): Disabled flag or thresholding strategy name.
        transcript_aggregation_policy (str): Transcript-to-gene aggregation policy.
        id_translation_provider (str): Identifier translation provider key.
        id_translation_species (str | None): Optional species hint for API lookups.
        id_translation_max_workers (int): Maximum worker threads for translation API calls.
        id_translation_batch_size (int): Identifier batch size for translation API calls.
    """

    id_type: str | None = "ensembl"
    level: str = "gene"
    sample_type_map: dict[str, str] | str | None = None
    transformation_state: str = "log"
    data_type: str = "TPM"
    thresholding: bool | str = False
    transcript_aggregation_policy: str = "sum"
    id_translation_provider: str = "auto"
    id_translation_species: str | None = None
    id_translation_max_workers: int = 8
    id_translation_batch_size: int = 500


@dataclass(slots=True)
class TranscriptProcessingConfig:
    """Generated: validation needed.

    Description:
        Transcript-level processing options shared across expression preprocessing
        and model-stage transcript metadata retrieval.

    Args:
        protein_coding_only (bool): Whether transcript->gene aggregation should keep
            only transcript rows marked as protein-coding when annotation is available.
        protein_coding_aggregation_policy (str): Aggregation policy for protein-coding
            transcript rows. Supported values: ``sum``, ``mean``.
        id_translation_provider (str): Translation provider key used when building
            model gene->transcript metadata.
        id_translation_species (str | None): Optional species hint for transcript lookup.
        id_translation_max_workers (int): Worker thread count for transcript lookup.
        id_translation_batch_size (int): Query batch size for transcript lookup.
    """

    protein_coding_only: bool = False
    protein_coding_aggregation_policy: str = "sum"
    id_translation_provider: str = "auto"
    id_translation_species: str | None = None
    id_translation_max_workers: int = 8
    id_translation_batch_size: int = 500


@dataclass(slots=True)
class PTRInputConfig:
    """Generated: validation needed.

    Description:
        PTR input option group used by expression+PTR protein abundance flow.

    Args:
        id_type (str): Identifier provider for PTR features.
        level (str): Gene or transcript level granularity.
        pretransformed_type (str): Log-scale used in raw PTR input before
            linear conversion. One of ``linear``, ``log10``, ``log2``, ``ln``.
        partial_missing_use_weighted (bool): Whether within-sample imputation
            should apply per-sample weighting. ``True`` keeps weighted column
            scaling; ``False`` uses unweighted row-statistic imputation.
        partial_missing_weighted_statistic (str): Column statistic used for
            weighted scaling during within-sample imputation. One of
            ``median``, ``mean``, ``mode``, ``max``, ``min``.
        partial_missing_imputation_statistic (str): Row statistic used for
            within-sample imputation of observed-but-missing PTR values.
            One of ``median``, ``mean``, ``mode``, ``max``, ``min``.
        unobserved_gene_imputation_strategy (str): Strategy used to fill genes
            present in expression but absent from PTR. One of
            ``sample_after_imputation``, ``sample_before_imputation``.
        unobserved_gene_imputation_statistic (str): Per-sample statistic used
            when imputing unobserved genes. One of ``median``, ``mean``,
            ``max``, ``min``.
        use_special_groups_for_unobserved_imputation (bool): Whether to impute
            configured special gene groups independently.
        special_gene_groups (dict[str, list[str]] | None): Optional custom
            grouping entries to impute independently. Values may contain gene
            IDs or reaction IDs; ``transport_reactions`` may be given with an
            empty list to auto-resolve transport-associated genes from model.
        impute_from_metabolic_genes_only (bool): Restrict PTR prior to
            imputation to genes found in the metabolic model.
    """

    id_type: str = "ensembl"
    level: str = "gene"
    pretransformed_type: str = "linear"
    partial_missing_use_weighted: bool = True
    partial_missing_weighted_statistic: str = "median"
    partial_missing_imputation_statistic: str = "median"
    unobserved_gene_imputation_strategy: str = "sample_after_imputation"
    unobserved_gene_imputation_statistic: str = "median"
    use_special_groups_for_unobserved_imputation: bool = False
    special_gene_groups: dict[str, list[str]] | None = None
    impute_from_metabolic_genes_only: bool = True


@dataclass(slots=True)
class ProteomicsInputConfig:
    """Generated: validation needed.

    Description:
        Proteomics input option group used by direct-proteomics protein flow.

    Args:
        id_type (str): Identifier provider for proteomics features.
        level (str): Gene or transcript level granularity.
        transformation_state (str): Data transform state, e.g. log or linear.
        imputation_strategy (str): Primary imputation strategy.
        fallback_imputation_strategy (str): Fallback imputation strategy.
    """

    id_type: str = "uniprot"
    level: str = "gene"
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
        trim_entities (bool): Enable gene/transcript trimming before allocation.
        trim_assesment_method (str): Method for determining trimmable entities,
            defaults to "M_value".

        impute_expressionless_reactions (bool): Enable fallback imputation.
        trim_minimum_entities_threshold (int): Minimum number of entities required
            in an IFP for iterative lowest-abundance trimming to proceed. Trimming
            inspects lowest-abundance entity and, if marked trimmable, removes it
            and repeats. If a non-trimmable entity is encountered or remaining
            entity count would fall below this threshold, trimming stops.
    """

    trim_entities: bool = True
    trim_assesment_method: str = "M_value"

    trim_minimum_entities_threshold: int = 3
    impute_expressionless_reactions: bool = True


@dataclass(slots=True)
class MValueTrimmingConfig:
    """Generated: validation needed.

    Description:
        Configuration for M_value trimming. To assess trimmability, M_value assumes that

        expression data is in linear space (not log transformed), and then checks for each
        gene across the samples if the high and low percentile values (denoted by the
        trim_percentiles config) of the gene's expression differ by more or less than the
        denoted threshold in log 2 (log2(high/low)). Note that trimmable genes are not
        automatically trimmed, only marked to be eligible for trimming during IFP allocation.

    Args:
        trim_correction_addition (float): Value added to all reactions' IFP sums during
            trimming to prevent extremely lowly expressed genes to be denoted as unstable.
        trim_percentiles (tuple[float, float]): Lower and upper percentiles used to
            determine whether gene is trimmable.
        trim_threshold (float): Threshold used to determine whether gene is trimmable:
            In particular genes whose upper and lower percentiles after addition of
            trim_correction_addition are below this threshold will be considered stable
            enough to be trimmed.
    """

    trim_correction_addition: float = 2
    trim_percentiles: tuple[float, float] = (2.5, 97.5)
    trim_threshold: float = 0.585  # is 1.5 in log2


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
        transcript_processing (TranscriptProcessingConfig): Transcript processing
            options for aggregation and transcript metadata retrieval.
        model (ModelConfig): Model stage configuration.
        expression (ExpressionInputConfig): Expression input option group.
        ptr (PTRInputConfig): PTR input option group.
        proteomics (ProteomicsInputConfig): Proteomics input option group.
        protein (ProteinConfig): Protein stage configuration.
        allocation (AllocationConfig): Allocation stage configuration.
        vmax (VmaxConfig): Vmax stage configuration.
        metadata (dict[str, Any]): Arbitrary run metadata.
    """

    trimming: MValueTrimmingConfig = field(default_factory=MValueTrimmingConfig)
    run_target_transcript_gene_level: str = "gene"
    model: ModelConfig = field(default_factory=ModelConfig)
    expression: ExpressionInputConfig = field(default_factory=ExpressionInputConfig)
    transcript_processing: TranscriptProcessingConfig = field(
        default_factory=TranscriptProcessingConfig
    )
    ptr: PTRInputConfig = field(default_factory=PTRInputConfig)
    proteomics: ProteomicsInputConfig = field(default_factory=ProteomicsInputConfig)
    protein: ProteinConfig = field(default_factory=ProteinConfig)
    allocation: AllocationConfig = field(default_factory=AllocationConfig)
    vmax: VmaxConfig = field(default_factory=VmaxConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_trimming_implementation(self) -> tuple[type, type | None]:
        """Resolve trimming implementation and expected trimming-config class.

        Returns:
            tuple[type, type|None]: (implementation class, trimming-config class or None)

        Behavior:
            - Look up implementation FQCN from allocation.trim_assesment_method.
            - Import implementation class dynamically.
            - Read implementation attributejjjjjjjjj `CONFIG_CLASS` if present to indicate
              which trimming config class pairs with implementation.

        Raises:
            ValueError: When method unknown or allocation.trim_assesment_method empty.
            ImportError / AttributeError: If module/class cannot be imported.
        """
        method_raw = (self.allocation.trim_assesment_method or "").strip().lower()
        if not method_raw:
            raise ValueError("allocation.trim_assesment_method not set")

        # normalise key
        key = method_raw.replace("-", "").replace("_", "")

        registry: dict[str, str] = {
            "mvalue": (
                "VmaxBuilder.expression.trimming_implementations.MValueTrimmingImplementation"
            ),
        }

        fqcn = registry.get(key)
        if fqcn is None:
            raise ValueError(
                f"Unknown trimming assessment method: "
                f"{self.allocation.trim_assesment_method!r}"
            )

        module_name, class_name = fqcn.rsplit(".", 1)
        module = importlib.import_module(module_name)
        impl = getattr(module, class_name)

        # implementation may advertise expected config class via CONFIG_CLASS attribute
        impl_config_cls = getattr(impl, "CONFIG_CLASS", None)

        return impl, impl_config_cls

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
