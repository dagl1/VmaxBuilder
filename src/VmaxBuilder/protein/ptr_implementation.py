"""Generated: validation needed.

Description:
    PTR submodule implementation used by protein-stage coordinator.
"""

from __future__ import annotations

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input


class DefaultPTRImplementation:
    """Generated: validation needed.

    Description:
        Resolve PTR input and combine it with expression as placeholder
        protein abundance logic.
    """

    def resolve_ptr_frame(
        self,
        scaffold: Scaffold,
        config: APIConfig,
    ) -> pd.DataFrame | None:
        """Generated: validation needed.

        Description:
            Resolve PTR dataframe from configured scaffold/config sources.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            pd.DataFrame | None: PTR dataframe when available.
        """

        return resolve_dataframe_input(scaffold, config, input_key="ptr")

    def combine_expression_with_ptr(
        self,
        expression_df: pd.DataFrame,
        ptr_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Combine expression and PTR by aligned element-wise multiplication.

        Args:
            expression_df (pd.DataFrame): Expression input table.
            ptr_df (pd.DataFrame): PTR input table.

        Returns:
            pd.DataFrame: Combined protein abundance table.
        """

        common_index = expression_df.index.intersection(ptr_df.index)
        common_columns = expression_df.columns.intersection(ptr_df.columns)
        if common_index.empty or common_columns.empty:
            return expression_df.copy()
        protein_df = expression_df.copy()
        protein_df.loc[common_index, common_columns] = (
            expression_df.loc[common_index, common_columns]
            * ptr_df.loc[common_index, common_columns]
        )
        return protein_df
