from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, cast

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.database_retrieval.identifier_translation import (
    IdentifierTranslationResult,
    IdentifierTranslationService,
)
from VmaxBuilder.Trimming.Mvalue.trimming_config import MValueTrimmingConfig
from VmaxBuilder.utils.iterables import SortedSet


class MValueTrimmingImplementation(BaseImplementation[MValueTrimmingConfig]):
    """Generated: validation needed.

    Description:
        Resolve and preprocess expression input for downstream protein abundance assembly.

    Args:
        translation_service (IdentifierTranslationServiceProtocol | None):
            Optional identifier translation service override.
    """

    INPUTS: list[InputSpec] = [
        InputSpec(
            name="processed_expression_df",
            data_type=pd.DataFrame,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="trimmable_genes",
            data_type=set,
            scaffold_location="outputs",
            save_file_name="trimmable_genes",
            extension=".json",
        ),
    ]

    def generate_outputs(
        self,
        scaffold: Scaffold,
    ) -> dict[str, Any]:
        processed_expression_df: pd.DataFrame = cast(
            pd.DataFrame, scaffold.get_scaffold_value("processed_expression_df")
        )
        sample_groups = cast(
            dict[str, list[str]] | None, scaffold.get_scaffold_value("sample_groups")
        )

        trimmable_genes, diagnostics = self._get_trimmable_genes(
            processed_expression_df,
            sample_groups=sample_groups,
        )
        return {
            "outputs": {
                "trimmable_genes": trimmable_genes,
            },
            "artifacts": {},
            "diagnostics": diagnostics,
            "metadata": {},
        }

    def _get_trimmable_genes(
        self,
        expression_df: pd.DataFrame,
        sample_groups: dict[str, list[str]] | None = None,
    ) -> tuple[set[str], dict[str, Any]]:
        """

        Description:
            Identify genes eligible for trimming based on expression data and config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_df (pd.DataFrame): Gene-level expression table.
            config (FullConfig): Root API configuration.

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
            for _group_name, samples in sample_groups.items():
                group_df = expression_df[samples]
                group_trimmable_genes = self._assess_trimmability(group_df)
                trimmable_genes.update(group_trimmable_genes)
        else:
            trimmable_genes = self._assess_trimmability(expression_df)

        diagnostics_payload = {
            "gene_trimming": {
                "trimming_enabled": True,
                "initial_trimmable_gene_count": len(trimmable_genes),
            }
        }
        return trimmable_genes, diagnostics_payload

    def _assess_trimmability(self, expression_df: pd.DataFrame) -> SortedSet[str]:
        """Assess trimmability of genes based on expression data and config.

        Args:
            expression_df (pd.DataFrame): Gene-level expression table.
            config (FullConfig): Root API configuration.
        """
        # add trim_correction_addition to all values

        expression_df = expression_df.copy()
        expression_df = expression_df + self.full_config.protein.trim_correction_addition

        # calculate percentiles for each gene
        lower_percentile = expression_df.quantile(
            self.full_config.protein.Mvalue.trim_percentiles[0] / 100, axis=1
        )
        upper_percentile = expression_df.quantile(
            self.full_config.protein.trimming.trim_percentiles[1] / 100, axis=1
        )

        # calculate the difference between upper and lower percentiles
        percentile_diff = upper_percentile - lower_percentile

        # identify genes where the difference is below the threshold
        trimmable_genes = set(
            percentile_diff[
                percentile_diff < self.full_config.protein.trimming.trim_threshold
            ].index
        )

        return trimmable_genes
