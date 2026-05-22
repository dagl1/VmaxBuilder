"""Generated: validation needed.

Description:
    Proteomics submodule implementation used by protein-stage coordinator.
"""

from __future__ import annotations

import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input


class DefaultProteomicsImplementation:
    """Generated: validation needed.

    Description:
        Resolve proteomics input and apply placeholder imputation workflow.
    """

    def resolve_proteomics_frame(
        self,
        scaffold: Scaffold,
        config: APIConfig,
    ) -> pd.DataFrame | None:
        """Generated: validation needed.

        Description:
            Resolve proteomics dataframe from configured scaffold/config sources.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API configuration.

        Returns:
            pd.DataFrame | None: Proteomics dataframe when available.
        """

        return resolve_dataframe_input(scaffold, config, input_key="proteomics")

    def impute_proteomics(
        self,
        proteomics_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Apply simple two-step placeholder imputation for missing proteomics values.

        Args:
            proteomics_df (pd.DataFrame): Proteomics input table.

        Returns:
            pd.DataFrame: Imputed proteomics table.
        """

        if proteomics_df.empty:
            return proteomics_df.copy()
        imputed_df = proteomics_df.copy()
        row_medians = imputed_df.median(axis=1)
        imputed_df = imputed_df.T.fillna(row_medians).T
        sample_medians = imputed_df.median(axis=0)
        imputed_df = imputed_df.fillna(sample_medians)
        return imputed_df
