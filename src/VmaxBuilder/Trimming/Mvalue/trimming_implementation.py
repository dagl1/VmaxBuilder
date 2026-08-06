from __future__ import annotations

from typing import Any, cast

import pandas as pd
from cobra import Model

from VmaxBuilder.base.classes import BaseImplementation, DiagnosticOutputSpec
from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
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

    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_ptr"
    IMPLEMENTATION_CONFIG_CLASS = MValueTrimmingConfig

    INPUTS: list[InputSpec] = [
        InputSpec(
            name="processed_expression_df",
            data_type=pd.DataFrame,
            in_scaffold=True,
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
        OutputSpec(
            name="non_trimmable_genes",
            data_type=set,
            scaffold_location="artifacts",
            save_file_name="non_trimmable_genes",
            extension=".json",
        ),
        OutputSpec(
            name="gene_stats",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="gene_stats",
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

        elapsed_time, (trimmable_genes, non_trimmable_genes, gene_stats) = (
            self.get_time_decorator(self._get_trimmable_genes)(
                processed_expression_df,
                sample_groups=sample_groups,
            )
        )

        diagnostics = self.create_diagnostics(trimmable_genes, non_trimmable_genes)
        metadata = self.create_metadata(elapsed_time)

        return {
            "outputs": {
                "trimmable_genes": trimmable_genes,
            },
            "artifacts": {
                "non_trimmable_genes": non_trimmable_genes,
                "gene_stats": gene_stats,
            },
            "diagnostics": diagnostics,
            "metadata": metadata,
        }

    def _get_trimmable_genes(
        self,
        expression_df: pd.DataFrame,
        sample_groups: dict[str, list[str]] | None = None,
    ) -> tuple[SortedSet[str], SortedSet[str], dict[str, dict[str, float]]]:
        """

        Description:
            Identify genes eligible for trimming based on expression data and config.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            expression_df (pd.DataFrame): Gene-level expression table.

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
        trimmable_genes = SortedSet()
        gene_stats = {}
        if sample_groups:
            for _group_name, samples in sample_groups.items():
                group_df = expression_df[samples]
                group_trimmable_genes, _, _gene_stats = self._assess_trimmability(group_df)
                gene_stats.update(_gene_stats)
                trimmable_genes.update(group_trimmable_genes)
            non_trimmable_genes = cast(
                SortedSet[str], SortedSet(expression_df.index) - trimmable_genes
            )
        else:
            trimmable_genes, non_trimmable_genes, _gene_stats = self._assess_trimmability(
                expression_df
            )
            gene_stats.update(_gene_stats)

        return trimmable_genes, non_trimmable_genes, gene_stats

    def _assess_trimmability(
        self,
        expression_df: pd.DataFrame,
    ) -> tuple[SortedSet[str], SortedSet[str], dict[str, dict[str, float]]]:
        """Assess trimmability of genes based on expression data and config.

        Args:
            expression_df (pd.DataFrame): Gene-level expression table.
        """

        # for typing to work, we explicitly define the types of the config values
        trim_addition_value: float = self.full_config.protein.trim_correction_addition
        trim_percentiles: tuple[float, float] = self.full_config.protein.trim_percentiles
        trim_threshold: float = self.full_config.protein.trim_threshold

        expression_df = expression_df.copy()
        expression_df = expression_df + trim_addition_value

        # calculate percentiles for each gene
        lower_percentile = expression_df.quantile(trim_percentiles[0] / 100, axis=1)
        upper_percentile = expression_df.quantile(trim_percentiles[1] / 100, axis=1)

        # calculate the difference between upper and lower percentiles
        percentile_diff = upper_percentile - lower_percentile

        # identify genes where the difference is below the threshold
        trimmable_genes = SortedSet(percentile_diff[percentile_diff < trim_threshold].index)
        non_trimmable_genes = SortedSet(
            percentile_diff[percentile_diff >= trim_threshold].index
        )

        gene_stats = {}
        for gene in trimmable_genes.union(non_trimmable_genes):
            gene_stats[gene] = {
                "M_value": expression_df.loc[gene].mean(),
                "percentile_diff": percentile_diff.loc[gene],
                "mean_expression": expression_df.loc[gene].mean(),
                "median_expression": expression_df.loc[gene].median(),
                "std_expression": expression_df.loc[gene].std(),
                "sem_expression": expression_df.loc[gene].sem(),
                "25q_expression": expression_df.loc[gene].quantile(0.25),
                "75q_expression": expression_df.loc[gene].quantile(0.75),
            }

        return trimmable_genes, non_trimmable_genes, gene_stats

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "gene_trimming": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Trimmable genes assessed",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def create_diagnostics(
        self,
        trimmable_genes: SortedSet[str],
        non_trimmable_genes: SortedSet[str],
    ) -> dict[str, Any]:
        gene_trimming_spec = DiagnosticOutputSpec(
            {
                "trimmable_gene_count": len(trimmable_genes),
                "total_gene_count": len(trimmable_genes) + len(non_trimmable_genes),
            },
            save_file_name="gene_trimming_summary",
            extensions=".json",
            data_type=dict,
        )

        diagnostics = {"gene_trimming": [gene_trimming_spec]}
        return diagnostics
