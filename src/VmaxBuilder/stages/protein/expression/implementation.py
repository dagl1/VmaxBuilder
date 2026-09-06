from typing import Any, Protocol, Sequence, cast

import numpy as np
import pandas as pd
from cobra.core.model import Model
from pandas import DataFrame

from VmaxBuilder.base.classes import (
    DiagnosticOutputSpec,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.base.exceptions import ConfigurationError
from VmaxBuilder.database_retrieval.identifier_translation import (
    IdentifierTranslationResult,
    IdentifierTranslationService,
)
from VmaxBuilder.stages.protein.expression.config import ExpressionConfig
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.typing_stubs.protein.expression.implementation import (
    ExpressionConfigProtocol,
)
from VmaxBuilder.utils.transformations import transform_dataframe


# todo: take this and model's and put somewhere else
class TranscriptMetadataServiceProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for expression-level identifier translation and transcript mapping.
    """

    def translate_identifiers(
        self,
        identifiers: Sequence[str],
        *,
        source_id_type: str,
        target_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> IdentifierTranslationResult:
        """Generated: validation needed.

        Description:
            Translate identifier collection across namespaces.

        Args:
            identifiers (list[str]): Source identifiers.
            source_id_type (str): Source identifier namespace.
            target_id_type (str): Target identifier namespace.
            species (str | None): Optional species hint.
            provider (str): Translation provider key.
            max_workers (int): Maximum worker threads.
            batch_size (int): Identifier batch size.

        Returns:
            IdentifierTranslationResult: Mapping output.
        """

    def build_transcript_gene_dataframe(
        self,
        transcript_ids: Sequence[str],
        *,
        transcript_id_type: str,
        target_gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build transcript-to-gene mapping dataframe.

        Args:
            transcript_ids (list[str]): Transcript identifiers.
            transcript_id_type (str): Transcript namespace.
            target_gene_id_type (str): Target gene namespace.
            species (str | None): Optional species hint.
            provider (str): Translation provider key.
            max_workers (int): Maximum worker threads.
            batch_size (int): Identifier batch size.

        Returns:
            pd.DataFrame: Transcript mapping table.
        """


class DefaultExpressionImplementation(RealImplementation[ExpressionConfig]):
    BASE_STAGE_CONFIG = ProteinStageConfig
    IMPLEMENTATION_CONFIG_CLASS = ExpressionConfig
    _RESOLVED_CONFIG_CLASS = ExpressionConfigProtocol
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_only"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="irreversible_cobra_model",
            data_type=Model,
            in_scaffold=True,
        ),
        InputSpec(
            name="transcript_df",
            data_type=DataFrame,
            optional=True,
        ),
        InputSpec(
            name="expression_df",
            data_type=DataFrame,
            prefix="data__",
            loader_args={
                "index_col": 0,
            },
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            "processed_expression_df",
            data_type=DataFrame,
            scaffold_location="outputs",
            save_file_name="processed_expression_df",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            "unfiltered_processed_expression_df",
            data_type=DataFrame,
            scaffold_location="artifacts",
            save_file_name="unfiltered_processed_expression_df",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            "missing_genes",
            data_type=list,
            scaffold_location="outputs",
            save_file_name="missing_genes",
            extension=".json",
            validator=None,
        ),
    ]
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        self._translation_service: TranscriptMetadataServiceProtocol = (
            IdentifierTranslationService(logger=self.logger)
        )

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        irreversible_cobra_model: Model = cast(
            Model, scaffold.get_scaffold_value("irreversible_cobra_model")
        )
        expression_df: pd.DataFrame = cast(
            pd.DataFrame, scaffold.get_scaffold_value("expression_df")
        )
        # transcript_df: pd.DataFrame | None = cast(
        #     pd.DataFrame | None, scaffold.get_scaffold_value("transcript_df")
        # )

        (elapsed_time, new_scaffold_objects) = self.get_time_decorator(
            self.prepare_expression_frame
        )(expression_df, irreversible_cobra_model)

        new_scaffold_objects["metadata"] = self.create_metadata(elapsed_time=elapsed_time)

        return new_scaffold_objects

    @staticmethod
    def _build_id_type_name(provider: str | None, level: str) -> str | None:
        """Generated: validation needed.

        Description:
            Build full identifier type name from provider and level.

        Args:
            provider (str | None): Identifier provider.
            level (str): Gene or transcript granularity.

        Returns:
            str | None: Full identifier type name, or None if provider is None.
        """

        if provider is None:
            return None
        level_lower = level.lower()
        if provider == "ensembl":
            return f"ensembl_{level_lower}_id"
        return provider

    def prepare_expression_frame(
        self,
        expression_df: pd.DataFrame,
        cobra_model: Model,
    ) -> dict[
        str,
        dict[str, DataFrame | list[str]]
        | dict[
            str,
            str
            | list[DiagnosticOutputSpec]
            | dict[str, dict[str, str | int | list[str] | list[DiagnosticOutputSpec]]]
            | dict[str, list[str]],
        ]
        | dict[str, IdentifierTranslationResult | DataFrame]
        | dict[
            str,
            dict[str, dict[str, str]]
            | dict[str, dict[str, str | int | list[str]]]
            | list[DiagnosticOutputSpec],
        ],
    ]:
        """Generated: validation needed.

        Description:
            Apply placeholder transcript-to-gene conversion when run
             target requests gene level.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_df (pd.DataFrame): Expression input table.

        Returns:
            dict[str, dict[str, object]]: Scaffold updates with processed expression table.


        Raises:
            ConfigurationError: If unsupported transcript aggregation policy is configured.

        Modifies:
            scaffold["artifacts"] and scaffold["diagnostics"] with translation metadata.
        """

        source_level = self.full_config.protein.expression_level.lower()
        target_level = self.full_config.run.run_target_transcript_gene_level.lower()
        transformation_state = (
            self.full_config.protein.expression_transformation_state.lower()
        )
        # if pre transformed type is not linear, we need to transform it to linear first
        if transformation_state != "linear":
            expression_df = transform_dataframe(expression_df, transformation_state)

        if source_level == "transcript" or target_level == "transcript":
            raise NotImplementedError(
                "Transcript-level expression conversion is not yet implemented."
            )
        source_id_type = self._build_id_type_name(
            self.full_config.protein.expression_gene_id_type, source_level
        )
        target_id_type = self._build_id_type_name(
            self.full_config.model.gene_id_type, self.full_config.model.level
        )
        expression_index = [str(index_value) for index_value in expression_df.index]
        diagnostics = {}

        if source_level == "transcript":
            # Transcript level requires valid id_types for mapping
            assert (
                source_id_type is not None
            ), "Expression id_type must be set for transcript-level conversion"
            assert (
                target_id_type is not None
            ), "Model id_type must be set for transcript-level conversion"
            raise NotImplementedError(
                "Transcript-level expression conversion to gene-level is not yet implemented."
            )
            # transcript_map_df = self._translation_service.build_gene_transcript_dataframe(
            #     expression_index,
            #     transcript_id_type=source_id_type,
            #     target_gene_id_type=target_id_type,
            #     species=self.full_config.protein.id_translation_species,
            #     provider=self.full_config.protein.id_translation_provider,
            #     max_workers=self.full_config.protein.id_translation_max_workers,
            #     batch_size=self.full_config.protein.id_translation_batch_size,
            # )

            # artifacts = {"transcript_gene_map": transcript_map_df}
            # diagnostics["transcript_gene_map_rows"] = int(len(transcript_map_df))
            # if target_level == "gene":
            #     values =  self._aggregate_transcripts_to_genes(
            #         expression_df,
            #         transcript_map_df,
            #         aggregation_policy=(
            # self.full_config.protein.transcript_aggregation_policy),
            #         protein_coding_only=self.full_config.transcripts.protein_coding_only,
            #         protein_coding_aggregation_policy=(
            #             self.full_config.transcripts.aggregation_strategy
            #         ),
            #         diagnostics_payload=diagnostics,
            #     )

        if not source_id_type or not target_id_type:
            diagnostics["id_translation"] = {
                "translation_summary": {
                    "source_id_type": "skipped_missing_id_type",
                    "target_id_type": "skipped_missing_id_type",
                    "mapped_identifiers": "skipped_missing_id_type",
                    "unresolved_identifiers": "skipped_missing_id_type",
                }
            }

            mapped_df = expression_df.copy()
            translation_result = None
        elif source_id_type == target_id_type:
            diagnostics["id_translation"] = {
                "translation_summary": {
                    "source_id_type": "skipped_missing_id_type",
                    "target_id_type": "skipped_missing_id_type",
                    "mapped_identifiers": "skipped_missing_id_type",
                    "unresolved_identifiers": "skipped_missing_id_type",
                }
            }
            mapped_df = expression_df.copy()
            translation_result = None
        else:
            translation_result = self._translation_service.translate_identifiers(
                expression_index,
                source_id_type=source_id_type,
                target_id_type=target_id_type,
                species=self.full_config.protein.id_translation_species,
                provider=self.full_config.protein.id_translation_provider,
                max_workers=self.full_config.protein.id_translation_max_workers,
                batch_size=self.full_config.protein.id_translation_batch_size,
            )
            diagnostics["id_translation"] = {
                "translation_summary": {
                    "source_id_type": source_id_type,
                    "target_id_type": target_id_type,
                    "mapped_identifiers": len(translation_result.mapped_identifiers),
                    "unresolved_identifiers": translation_result.unresolved_identifiers,
                }
            }

            mapped_df = self._apply_identifier_mapping(
                expression_df,
                identifier_mapping=translation_result.mapped_identifiers,
            )

        (
            thresholded_df,
            missing_genes,
        ) = self.handle_missing_genes(
            expression_df=mapped_df,
            cobra_model=cobra_model,
            minimum_expression_value=self.full_config.protein.minimum_expression_threshold,
            minimum_gene_policy=self.full_config.protein.minimum_expression_threshold_policy,
            missing_gene_policy=self.full_config.protein.missing_gene_policy,
        )
        if missing_genes:
            missing_genes_spec = DiagnosticOutputSpec(
                data=missing_genes,
                save_file_name="missing_genes",
                extensions=".json",
                data_type=list,
            )
            diagnostics["expression_processing"] = [missing_genes_spec]
        else:
            missing_genes: list[str] = []

        artifacts = {}
        if translation_result is not None:
            artifacts["identifier_translation_result"] = translation_result

        artifacts["unfiltered_processed_expression_df"] = thresholded_df.copy()
        filtered_df = self.filter_expression_frame(thresholded_df, cobra_model)
        new_scaffold_objects = {
            "outputs": {
                "processed_expression_df": filtered_df,
                "missing_genes": missing_genes,
            },
            "diagnostics": diagnostics,
            "artifacts": artifacts,
        }

        return new_scaffold_objects

    def handle_missing_genes(
        self,
        expression_df: pd.DataFrame,
        cobra_model: Model,
        minimum_expression_value: float,
        minimum_gene_policy: str,
        missing_gene_policy: str,
    ) -> tuple[pd.DataFrame, list[str]]:
        # we add rows for the missing genes and give them a value of np.nan for all samples,
        # so that we can set them to GPRless in the model and keep track of them
        missing_genes = [
            gene_id
            for gene_id in [model_gene.id for model_gene in cobra_model.genes]
            if gene_id not in expression_df.index
        ]
        expression_df = expression_df.reindex(
            expression_df.index.union([gene.id for gene in cobra_model.genes]),
            fill_value=np.nan,
        )

        if minimum_gene_policy == "raise_to_threshold":
            expression_df = self.set_minimum_expression_value(
                expression_df, minimum_expression_value
            )
        elif minimum_gene_policy == "set_to_missing":
            expression_df = self.set_genes_below_minimum_to_missing(
                expression_df, minimum_expression_value
            )
            # only if a whole row is missing, we set the gene to GPRless in the model
            additional_missing_genes = [
                gene_id
                for gene_id in expression_df.index
                if expression_df.loc[gene_id].isnull().all()
            ]
            missing_genes = list(set(missing_genes + additional_missing_genes))
            non_missing_genes = [
                gene_id for gene_id in expression_df.index if gene_id not in missing_genes
            ]
            expression_df = self.set_minimum_expression_value(
                expression_df.loc[non_missing_genes], minimum_expression_value
            )
        else:
            raise ConfigurationError(
                f"Unsupported minimum_gene_policy: {minimum_gene_policy}. "
                "Supported values: ['raise_to_threshold', 'set_to_missing']."
            )

        if missing_gene_policy == "GPRless":
            self.logger.warning(
                f"{len(missing_genes)} genes from the model are missing "
                "in the expression data. "
                f"These genes will be ignored in the analysis. \n"
                f"Ignored genes will be set to 'GPRless', "
                "will delete their contribution from "
                "any reaction they are associated with.",
                print_level=2,
            )
            # todo:  validate that the genes are actually set to GPRless in the model
        elif missing_gene_policy == "impute":
            raise NotImplementedError(
                "The 'impute' missing_gene_policy is not yet implemented. "
                "Please use 'GPRless' or another supported policy."
            )
        else:
            raise ConfigurationError(
                f"Unsupported missing_gene_policy: {missing_gene_policy}. "
                "Supported values: ['GPRless']."
            )

        return (expression_df, missing_genes)

    def set_minimum_expression_value(
        self,
        expression_df: pd.DataFrame,
        minimum_expression_value: float,
        genes_below_minimum: list[str] | None = None,
    ):
        new_expression_df = expression_df.copy()
        if genes_below_minimum is not None:
            new_expression_df.loc[genes_below_minimum] = minimum_expression_value
        else:
            new_expression_df = new_expression_df.apply(
                lambda x: x.where(
                    x >= minimum_expression_value,
                    minimum_expression_value,
                ),
                axis=0,
            )
        return new_expression_df

    def set_genes_below_minimum_to_missing(
        self,
        expression_df: pd.DataFrame,
        minimum_expression_value: float,
    ):
        new_expression_df = expression_df.copy()
        new_expression_df = new_expression_df.apply(
            lambda x: x.where(
                x >= minimum_expression_value,
                np.nan,
            ),
            axis=0,
        )
        return new_expression_df

    def filter_expression_frame(
        self,
        expression_df: pd.DataFrame,
        cobra_model: Model,
    ) -> pd.DataFrame:
        """Generated: validation needed.


        Args:
            expression_df (pd.DataFrame): Expression input table.
            cobra_model (Model): COBRA model.

        Returns:
            pd.DataFrame: Filtered expression table with only
            identifiers present in the model.

        """

        model_ids = [gene.id for gene in cobra_model.genes]

        filtered_df = expression_df.loc[
            [gene_id in model_ids for gene_id in expression_df.index]
        ]

        return filtered_df

    @staticmethod
    def _aggregate_transcripts_to_genes(
        expression_df: pd.DataFrame,
        transcript_gene_map_df: pd.DataFrame,
        *,
        aggregation_policy: str,
        protein_coding_only: bool,
        protein_coding_aggregation_policy: str,
        diagnostics_payload: dict[str, object],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Aggregate transcript expression rows to genes and keep unresolved transcripts.

        Args:
            expression_df (pd.DataFrame): Transcript-level expression table.
            transcript_gene_map_df (pd.DataFrame): Transcript-to-gene mapping dataframe.
            aggregation_policy (str): Configured aggregation policy.
            protein_coding_only (bool): Whether to keep only protein-coding transcripts.
            protein_coding_aggregation_policy (str): Aggregation policy for
                protein-coding transcript rows.
            diagnostics_payload (dict[str, object]): Mutable diagnostics payload.

        Returns:
            pd.DataFrame: Gene-level table with unresolved transcripts retained.

        Raises:
            ConfigurationError: If unsupported aggregation policy is configured.
        """

        supported_policies = {"sum", "mean"}
        if aggregation_policy not in supported_policies:
            raise ConfigurationError(
                "Unsupported transcript aggregation policy: "
                f"{aggregation_policy!r}. Supported values: ['sum', 'mean']."
            )
        if protein_coding_aggregation_policy not in supported_policies:
            raise ConfigurationError(
                "Unsupported protein-coding transcript aggregation policy: "
                f"{protein_coding_aggregation_policy!r}. Supported values: ['sum', 'mean']."
            )
        if transcript_gene_map_df.empty:
            diagnostics_payload["transcript_unresolved_count"] = int(len(expression_df.index))
            return expression_df

        aggregation_policy_to_use = aggregation_policy
        if protein_coding_only and "is_protein_coding" in transcript_gene_map_df.columns:
            transcript_gene_map_df = transcript_gene_map_df[
                transcript_gene_map_df["is_protein_coding"]
            ]
            aggregation_policy_to_use = protein_coding_aggregation_policy
            diagnostics_payload["protein_coding_only_filter"] = True
            diagnostics_payload["protein_coding_map_rows"] = int(len(transcript_gene_map_df))

        transcript_to_gene = {
            str(row["transcript_id"]): str(row["gene_id"])
            for _, row in transcript_gene_map_df[["transcript_id", "gene_id"]]
            .dropna()
            .iterrows()
        }
        normalised_index = [str(index_value) for index_value in expression_df.index]
        mapped_rows = [index_value in transcript_to_gene for index_value in normalised_index]

        mapped_expression_df = expression_df.loc[mapped_rows].copy()
        mapped_expression_df.index = [
            transcript_to_gene[str(index_value)] for index_value in mapped_expression_df.index
        ]
        if aggregation_policy_to_use == "mean":
            aggregated_expression_df = mapped_expression_df.groupby(level=0).mean()
        else:
            aggregated_expression_df = mapped_expression_df.groupby(level=0).sum()

        unresolved_expression_df = expression_df.loc[
            [not row_is_mapped for row_is_mapped in mapped_rows]
        ].copy()
        diagnostics_payload["transcript_unresolved_count"] = int(
            len(unresolved_expression_df.index)
        )
        if unresolved_expression_df.empty:
            return pd.DataFrame(aggregated_expression_df)

        combined_expression_df = pd.concat(
            [aggregated_expression_df, unresolved_expression_df]
        )
        if aggregation_policy_to_use == "mean":
            return combined_expression_df.groupby(level=0).mean()
        return combined_expression_df.groupby(level=0).sum()

    @staticmethod
    def _apply_identifier_mapping(
        expression_df: pd.DataFrame,
        *,
        identifier_mapping: dict[str, str],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Apply partial identifier mapping and aggregate rows when mappings collide.

        Args:
            expression_df (pd.DataFrame): Input expression table.
            identifier_mapping (dict[str, str]):
                Source identifier to target identifier mapping.

        Returns:
            pd.DataFrame: Table indexed by mapped identifiers where available.
        """

        if not identifier_mapping:
            return expression_df
        mapped_df = expression_df.copy()
        mapped_df.index = [
            identifier_mapping.get(str(index_value), str(index_value))
            for index_value in mapped_df.index
        ]
        return mapped_df.groupby(level=0).sum()

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Create metadata dictionary for the expression stage.

        Args:
            elapsed_time (float): Time taken for processing.

        Returns:
            dict[str, object]: Metadata dictionary.
        """

        metadata = {
            "expression_processing": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "expression_processing_completed",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
