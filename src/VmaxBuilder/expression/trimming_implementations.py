"""Generated: validation needed.

Description:
    M
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


class MValueTrimmingImplementation(Protocol):
    """Generated: validation needed.

    Description:
        Resolve and preprocess expression input for downstream protein abundance assembly.

    Args:
        translation_service (IdentifierTranslationServiceProtocol | None):
            Optional identifier translation service override.
    """

    def run(
        self,
        scaffold: Scaffold,
        expression_input: pd.DataFrame,
        config: APIConfig,
        sample_groups: dict[str, list[str]] | None = None,
    ) -> set[str]:
        """Generated: validation needed.

        Description:
            Resolve and preprocess expression input for downstream protein abundance assembly.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_input (str | pd.DataFrame | Sequence[str]):
                Expression input source (file path, DataFrame, or list of gene IDs).
            config (APIConfig): Root API configuration.

        Returns:
            Scaffold: Updated scaffold with resolved expression data.
        """
        trimmable_genes = self._get_trimmable_genes(
            scaffold,
            expression_input,
            config,
            sample_groups=sample_groups,
        )
        return trimmable_genes

    @staticmethod
    def _get_trimmable_genes(
        scaffold: Scaffold,
        expression_df: pd.DataFrame,
        config: APIConfig,
        sample_groups: dict[str, list[str]] | None = None,
    ) -> set[str]:
        """

        Description:
            Identify genes eligible for trimming based on expression data and config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_df (pd.DataFrame): Gene-level expression table.
            config (APIConfig): Root API configuration.

        Requires:
            config.trimming.trim_correction_addition: float = 2
            config.trimming.trim_percentiles: tuple[float, float] = (2.5, 97.5)
            config.trimming.trim_threshold: float = 0.585  # is 1.5 in log2
            optional(sample_groups: dict[str, list[str]]): Optional mapping of
                sample groups for group-specific trimming.


        Returns:
            set[str]: Set of gene identifiers eligible for trimming.
        """
        # copy expression df
        # add trim_correction_addition to all values
        # if sample_groups is provided, separate expression_df into groups and assess
        # trimmability per group else, assess trimmability per gene
        if sample_groups:
            trimmable_genes = set()
            for group_name, samples in sample_groups.items():
                group_df = expression_df[samples]
                group_trimmable_genes = MValueTrimmingImplementation._assess_trimmability(
                    group_df, config
                )
                trimmable_genes.update(group_trimmable_genes)
        else:
            trimmable_genes = MValueTrimmingImplementation._assess_trimmability(
                expression_df, config
            )

        diagnostics_payload = scaffold.setdefault("diagnostics", {}).setdefault(
            "gene_trimming", {}
        )
        diagnostics_payload["trimming_enabled"] = True
        diagnostics_payload["initial_trimmable_gene_count"] = len(trimmable_genes)
        return trimmable_genes

    @staticmethod
    def _assess_trimmability(expression_df: pd.DataFrame, trimming_config: ) -> set[str]:
        """Assess trimmability of genes based on expression data and config.

        Args:
            expression_df (pd.DataFrame): Gene-level expression table.
            config (APIConfig): Root API configuration.
        """
        # add trim_correction_addition to all values
        expression_df = expression_df + trimming_config.trim_correction_addition

        # calculate percentiles for each gene
        lower_percentile = expression_df.quantile(
            trimming_config.Mvalue.trim_percentiles[0] / 100, axis=1
        )
        upper_percentile = expression_df.quantile(
            trimming_config.trimming.trim_percentiles[1] / 100, axis=1
        )

        # calculate the difference between upper and lower percentiles
        percentile_diff = upper_percentile - lower_percentile

        # identify genes where the difference is below the threshold
        trimmable_genes = set(
            percentile_diff[percentile_diff < trimming_config.trimming.trim_threshold].index
        )

        return trimmable_genes
