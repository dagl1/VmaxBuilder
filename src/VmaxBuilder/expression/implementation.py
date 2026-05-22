"""Generated: validation needed.

Description:
    Expression submodule implementation used by protein-stage coordinator.
"""

from __future__ import annotations

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input


class DefaultExpressionImplementation:
    """Generated: validation needed.

    Description:
        Resolve and preprocess expression input for downstream protein abundance assembly.
    """

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

    def prepare_expression_frame(
        self,
        expression_df: pd.DataFrame,
        config: APIConfig,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Apply placeholder transcript-to-gene conversion when run
             target requests gene level.

        Args:
            expression_df (pd.DataFrame): Expression input table.
            config (APIConfig): Root API configuration.

        Returns:
            pd.DataFrame: Possibly converted expression table.
        """

        source_level = config.expression.origin_transcript_gene_level.lower()
        target_level = config.run_target_transcript_gene_level.lower()
        if source_level != "transcript" or target_level != "gene":
            return expression_df

        converted_df = expression_df.copy()
        converted_df.index = converted_df.index.map(lambda value: str(value).split(".")[0])
        return converted_df.groupby(level=0).sum()
