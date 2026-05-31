"""Generated: validation needed.

Description:
    Expression submodule implementation used by protein-stage coordinator.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.validation import ConfigurationError
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.database_retrieval.identifier_translation import (
    IdentifierTranslationResult,
    IdentifierTranslationService,
)
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input


class IdentifierTranslationServiceProtocol(Protocol):
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


class DefaultExpressionImplementation:
    """Generated: validation needed.

    Description:
        Resolve and preprocess expression input for downstream protein abundance assembly.

    Args:
        translation_service (IdentifierTranslationServiceProtocol | None):
            Optional identifier translation service override.
    """

    def __init__(
        self,
        translation_service: IdentifierTranslationServiceProtocol | None = None,
    ) -> None:
        self._translation_service = translation_service or IdentifierTranslationService()

    def resolve_expression_frame(
        self,
        scaffold: Scaffold,
        config: APIConfig,
    ) -> pd.DataFrame | None:
        """Generated: validation needed.

        Description:
            Resolve expression dataframe from configured scaffold/config sources.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            pd.DataFrame | None: Expression dataframe when available.
        """

        return resolve_dataframe_input(scaffold, config, input_key="expression")

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
        scaffold: Scaffold,
        expression_df: pd.DataFrame,
        config: APIConfig,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Apply placeholder transcript-to-gene conversion when run
             target requests gene level.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_df (pd.DataFrame): Expression input table.
            config (APIConfig): Root API configuration.

        Returns:
            pd.DataFrame: Possibly converted expression table.

        Raises:
            ConfigurationError: If unsupported transcript aggregation policy is configured.

        Modifies:
            scaffold["artifacts"] and scaffold["diagnostics"] with translation metadata.
        """

        source_level = config.expression.level.lower()
        target_level = config.run_target_transcript_gene_level.lower()
        source_id_type = self._build_id_type_name(config.expression.id_type, source_level)
        target_id_type = self._build_id_type_name(config.model.id_type, config.model.level)
        expression_index = [str(index_value) for index_value in expression_df.index]
        diagnostics_payload = scaffold.setdefault("diagnostics", {}).setdefault(
            "expression_preparation", {}
        )

        if source_level == "transcript":
            # Transcript level requires valid id_types for mapping
            assert (
                source_id_type is not None
            ), "Expression id_type must be set for transcript-level conversion"
            assert (
                target_id_type is not None
            ), "Model id_type must be set for transcript-level conversion"
            transcript_map_df = self._translation_service.build_transcript_gene_dataframe(
                expression_index,
                transcript_id_type=source_id_type,
                target_gene_id_type=target_id_type,
                species=config.expression.id_translation_species,
                provider=config.expression.id_translation_provider,
                max_workers=config.expression.id_translation_max_workers,
                batch_size=config.expression.id_translation_batch_size,
            )
            scaffold.setdefault("artifacts", {})["transcript_gene_map"] = transcript_map_df
            diagnostics_payload["transcript_gene_map_rows"] = int(len(transcript_map_df))
            if target_level == "gene":
                return self._aggregate_transcripts_to_genes(
                    expression_df,
                    transcript_map_df,
                    aggregation_policy=config.expression.transcript_aggregation_policy,
                    diagnostics_payload=diagnostics_payload,
                )
            return expression_df

        if not source_id_type or not target_id_type:
            diagnostics_payload["id_translation"] = "skipped_missing_id_type"
            return expression_df
        if source_id_type == target_id_type:
            diagnostics_payload["id_translation"] = "skipped_matching_id_type"
            return expression_df

        translation_result = self._translation_service.translate_identifiers(
            expression_index,
            source_id_type=source_id_type,
            target_id_type=target_id_type,
            species=config.expression.id_translation_species,
            provider=config.expression.id_translation_provider,
            max_workers=config.expression.id_translation_max_workers,
            batch_size=config.expression.id_translation_batch_size,
        )
        diagnostics_payload["id_translation"] = {
            "source_id_type": source_id_type,
            "target_id_type": target_id_type,
            "mapped_identifiers": len(translation_result.mapped_identifiers),
            "unresolved_identifiers": translation_result.unresolved_identifiers,
        }
        return self._apply_identifier_mapping(
            expression_df,
            identifier_mapping=translation_result.mapped_identifiers,
        )

    @staticmethod
    def _aggregate_transcripts_to_genes(
        expression_df: pd.DataFrame,
        transcript_gene_map_df: pd.DataFrame,
        *,
        aggregation_policy: str,
        diagnostics_payload: dict[str, object],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Aggregate transcript expression rows to genes and keep unresolved transcripts.

        Args:
            expression_df (pd.DataFrame): Transcript-level expression table.
            transcript_gene_map_df (pd.DataFrame): Transcript-to-gene mapping dataframe.
            aggregation_policy (str): Configured aggregation policy.
            diagnostics_payload (dict[str, object]): Mutable diagnostics payload.

        Returns:
            pd.DataFrame: Gene-level table with unresolved transcripts retained.

        Raises:
            ConfigurationError: If unsupported aggregation policy is configured.
        """

        if aggregation_policy != "sum":
            raise ConfigurationError(
                "Unsupported transcript aggregation policy: "
                f"{aggregation_policy!r}. Supported values: ['sum']."
            )
        if transcript_gene_map_df.empty:
            diagnostics_payload["transcript_unresolved_count"] = int(len(expression_df.index))
            return expression_df

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
        aggregated_expression_df = mapped_expression_df.groupby(level=0).sum()

        unresolved_expression_df = expression_df.loc[
            [not row_is_mapped for row_is_mapped in mapped_rows]
        ].copy()
        diagnostics_payload["transcript_unresolved_count"] = int(
            len(unresolved_expression_df.index)
        )
        if unresolved_expression_df.empty:
            return aggregated_expression_df

        combined_expression_df = pd.concat(
            [aggregated_expression_df, unresolved_expression_df]
        )
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
