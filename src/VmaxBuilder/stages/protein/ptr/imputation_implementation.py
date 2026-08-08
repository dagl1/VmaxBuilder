from collections.abc import Callable
from typing import Any, cast

import numpy as np
import pandas as pd
from cobra.core.model import Model
from pandas import DataFrame

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    DiagnosticOutputSpec,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.stages.protein.ptr.diagnostics import PTRDiagnostics
from VmaxBuilder.stages.protein.ptr.ptr_utils import (
    resolve_special_gene_groups,
    transform_ptr_to_linear,
)

_NA_TOKENS: frozenset[str] = frozenset(
    {
        "",
        "nan",
        "na",
        "n/a",
        "none",
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
    }
)


def _series_mode(series: pd.Series) -> float:
    """Generated: validation needed.

    Description:
        Compute one numeric mode for a series; return NaN when unavailable.

    Args:
        series (pd.Series): Input series.

    Returns:
        float: First mode value or ``np.nan`` when no mode exists.
    """
    mode_values = series.mode(dropna=True)
    if mode_values.empty:
        return float(np.nan)
    return float(mode_values.iloc[0])


_IMPUTATION_STATISTICS: dict[str, Any] = {
    "median": lambda s: s.median(skipna=True),
    "mean": lambda s: s.mean(skipna=True),
    "mode": _series_mode,
    "max": lambda s: s.max(skipna=True),
    "min": lambda s: s.min(skipna=True),
}
_PRETRANSFORM_ALIASES: dict[str, str] = {
    "none": "linear",
}


class SimplePTRImputationImplementation(RealImplementation[PTRInputConfig]):
    STAGE_NAME = "protein"
    IMPL_NAME = "simple_ptr_imputation"
    IMPLEMENTATION_CONFIG_CLASS = PTRInputConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = [PTRDiagnostics]
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="PTR_df",
            data_type=DataFrame,
            prefix="PTR__",
            loader_args={
                "index_col": 0,
            },
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
        InputSpec(
            name="irreversible_cobra_model",
            data_type=Model,
            in_scaffold=True,
        ),
        InputSpec(
            name="processed_expression_df",
            data_type=DataFrame,
            in_scaffold=True,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="imputed_PTR_df",
            data_type=DataFrame,
            scaffold_location="outputs",
            save_file_name="imputed_PTR_df",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="partially_imputed_PTR_df_metabolic_genes",
            data_type=DataFrame,
            scaffold_location="artifacts",
            save_file_name="partially_imputed_PTR_df_metabolic_genes",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="partially_imputed_PTR_df_all_genes",
            data_type=DataFrame,
            scaffold_location="artifacts",
            save_file_name="partially_imputed_PTR_df_all_genes",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="fully_imputed_PTR_df_metabolic_genes",
            data_type=DataFrame,
            scaffold_location="artifacts",
            save_file_name="fully_imputed_PTR_df_metabolic_genes",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="fully_imputed_PTR_df_all_genes",
            data_type=DataFrame,
            scaffold_location="artifacts",
            save_file_name="fully_imputed_PTR_df_all_genes",
            saver_args={
                "with_index": True,
            },
            extension=".csv",
            validator=None,
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold):
        # load ptr df
        ptr_df = cast(pd.DataFrame, scaffold.get_scaffold_value("PTR_df"))
        cobra_model = cast(Model, scaffold.get_scaffold_value("irreversible_cobra_model"))
        preprocessed_expression_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("processed_expression_df")
        )
        cobra_genes = {str(gene.id) for gene in cobra_model.genes}

        # preprocess ptr df
        time_start = pd.Timestamp.now()

        prepared_ptr_dfs = self.prepare_ptr_frames(
            ptr_df=ptr_df,
            expression_df=preprocessed_expression_df,
            cobra_model=cobra_model,
            metabolic_genes=list(cobra_genes),
        )
        imputed_ptr_dfs: dict[str, pd.DataFrame] = {}
        special_gene_groups = resolve_special_gene_groups(
            self.full_config,
            cobra_model=cobra_model,
            expression_gene_ids=set(map(str, preprocessed_expression_df.index)),
        )
        trace_dict: dict[str, Any] = {}
        for df_name, ptr_df in prepared_ptr_dfs.items():
            self.logger.debug(f"PTR: prepared frame '{df_name}' shape {ptr_df.shape}")
            # impute partially missing
            partially_imputed_df = self.impute_within_tissue_ptrs(
                ptr_df,
                use_weighted=self.full_config.protein.partial_missing_use_weighted,
                weighted_statistic=self.full_config.protein.partial_missing_weighted_statistic,
                imputation_statistic=self.full_config.protein.partial_missing_imputation_statistic,
            )
            unobserved_genes = self.get_unobserved_genes(
                partially_imputed_df, cobra_model=cobra_model
            )
            imputed_ptr_dfs[f"partially_imputed_{df_name}"] = partially_imputed_df
            # impute fully missing genes

            fully_imputed_df = self.impute_unobserved_genes(
                partially_imputed_df,
                unobserved_gene_ids=unobserved_genes,
                strategy=self.full_config.protein.unobserved_gene_imputation_strategy,
                statistic=self.full_config.protein.unobserved_gene_imputation_statistic,
                reference_df=ptr_df,
                special_gene_groups=special_gene_groups,
                use_special_groups=self.full_config.protein.use_special_groups_for_unobserved_imputation,
                trace=trace_dict,
            )
            imputed_ptr_dfs[f"fully_imputed_{df_name}"] = fully_imputed_df

        end_time = pd.Timestamp.now()
        time_elapsed = (end_time - time_start).total_seconds()
        metadata = self.create_metadata(time_elapsed)

        _latest_ptr_preparation_diagnostics = {
            "special_gene_groups": special_gene_groups,
            "special_group_gene_mapping": trace_dict.get("special_group_gene_mapping", {}),
            "special_group_fill_values_per_sample": trace_dict.get(
                "special_group_fill_values_per_sample",
                {},
            ),
            "special_group_assigned_values_per_sample": trace_dict.get(
                "special_group_assigned_values_per_sample",
                {},
            ),
        }
        ptr_diagnostic_spec = DiagnosticOutputSpec(
            data=_latest_ptr_preparation_diagnostics,
            save_file_name="special_gene_grouping",
            extensions=".json",
            data_type=dict,
        )
        new_scaffold_objects = {
            "outputs": {"imputed_PTR_df": fully_imputed_df},
            "diagnostics": {"PTR": ptr_diagnostic_spec},
            "metadata": metadata,
            "artifacts": imputed_ptr_dfs,
        }

        return new_scaffold_objects

    def get_unobserved_genes(self, ptr_df: pd.DataFrame, cobra_model: Model) -> set[str]:
        """Generated: validation needed.

        Description:
            Identify genes present in the cobra model but absent from the PTR frame.

        Args:
            ptr_df (pd.DataFrame): PTR table after within-sample imputation.
            cobra_model (Model): COBRA model used to define the gene universe.

        Returns:
            set[str]: Gene IDs present in the model but absent from PTR.
        """
        model_gene_ids = {str(gene.id) for gene in cobra_model.genes}
        ptr_gene_ids = set(map(str, ptr_df.index))
        unobserved_genes = model_gene_ids - ptr_gene_ids
        return unobserved_genes

    @staticmethod
    def standardize_ptr_frame(ptr_df: pd.DataFrame) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Standardize missing-value tokens, trim string whitespace, and
            coerce all values to numeric.  Resets integer-indexed frames to
            use the first column as the index.  Normalises column names to
            lower-case.

        Args:
            ptr_df (pd.DataFrame): Raw PTR table (genes × samples).

        Returns:
            pd.DataFrame: Numeric PTR frame with standardized missing values
            and lower-case column names.
        """
        df = ptr_df.copy()

        if df.index.dtype in ("int64", "float64") and df.index.min() in (0, 1):
            df = df.set_index(df.columns[0])

        df = df.replace({pd.NA: np.nan, np.inf: np.nan, -np.inf: np.nan, None: np.nan})

        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].map(
                    lambda v: (  # noqa: B023
                        np.nan
                        if isinstance(v, str) and v.strip().lower() in _NA_TOKENS
                        else v.strip()
                        if isinstance(v, str)
                        else v
                    )
                )

        df = df.apply(pd.to_numeric, errors="coerce")
        df = df.replace({np.nan: pd.NA})
        df.columns = df.columns.map(str).str.lower()
        return df

    def remove_ptr_duplicates(self, ptr_df: pd.DataFrame) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            For each duplicated gene row, retain the row with the most
            non-missing values.  When tied, keep the first occurrence.

        Args:
            ptr_df (pd.DataFrame): PTR table potentially containing duplicate
                gene identifiers in the index.

        Returns:
            pd.DataFrame: PTR table with unique gene index.
        """
        df = ptr_df.copy()
        duplicated_genes = df.index[df.index.duplicated(keep=False)].unique()
        for gene in duplicated_genes:
            gene_rows = df.loc[df.index == gene]
            non_nan_counts = gene_rows.notna().sum(axis=1)
            max_count = non_nan_counts.max()
            best_rows = gene_rows[non_nan_counts == max_count]
            drop_idx = gene_rows.index.difference(best_rows.index[:1])
            df = df.drop(drop_idx)

        if df.index.duplicated().any():
            n_before = len(df)
            df = df[~df.index.duplicated(keep="first")]
            self.logger.warning(
                f"PTR: removed {n_before - len(df)} residual "
                "duplicate rows after targeted deduplication."
            )
        return pd.DataFrame(df)

    # ------------------------------------------------------------------
    # Within-sample imputation
    # ------------------------------------------------------------------

    @staticmethod
    def get_weights(
        df: pd.DataFrame,
        col_stat_function: Callable[[pd.Series], float],
    ) -> pd.Series:
        """Generated: validation needed.

        Description:
            Compute per-column weighting ratios for within-sample imputation.

        Args:
            df (pd.DataFrame): PTR frame in linear space.
            col_stat_function (Callable[[pd.Series], float]): Statistic function
                for column aggregation and global normalisation.

        Returns:
            pd.Series: Weight ratio per PTR column.
        """

        col_stats = pd.Series({col: float(col_stat_function(df[col])) for col in df.columns})
        stat_of_col_stats = float(col_stat_function(col_stats))
        ratio = (
            col_stats / stat_of_col_stats
            if stat_of_col_stats != 0 and not np.isnan(stat_of_col_stats)
            else pd.Series(1.0, index=col_stats.index)
        )
        return ratio

    @staticmethod
    def _validate_within_sample_weighting(
        use_weighted: bool,
        weighted_statistic: str | None,
    ) -> None:
        """Generated: validation needed.

        Description:
            Validate effective within-sample weighting inputs.

        Args:
            use_weighted (bool): Weighted-imputation toggle.
            weighted_statistic (str | None): Column-statistic key for weighted mode.

        Raises:
            ValueError: When weighted mode lacks a strategy statistic.
        """
        if not use_weighted:
            return
        if weighted_statistic is None:
            raise ValueError(
                "Weighted imputation requires weighted_statistic to be specified."
            )

    @staticmethod
    def _resolve_within_sample_stat_functions(
        use_weighted: bool,
        weighted_statistic: str | None,
        imputation_statistic: str,
    ) -> tuple[Callable[[pd.Series], float], Callable[[pd.Series], float] | None]:
        """Generated: validation needed.

        Description:
            Resolve callable statistic functions used by within-sample imputation.

        Args:
            use_weighted (bool): Weighted-imputation toggle.
            weighted_statistic (str | None): Weighted-column statistic key.
            imputation_statistic (str): Row-wise statistic key.

        Returns:
            tuple[Callable[[pd.Series], float], Callable[[pd.Series], float] | None]:
            Row-statistic function and optional weighted-column statistic function.

        Raises:
            ValueError: When requested statistic keys are unsupported.
        """
        imputation_statistic_function = _IMPUTATION_STATISTICS.get(imputation_statistic)
        if imputation_statistic_function is None:
            raise ValueError(
                f"Unrecognised PTR partial_missing_imputation_statistic '"
                f"{imputation_statistic}'. "
                f"Expected one of: {', '.join(_IMPUTATION_STATISTICS)}."
            )

        weighted_statistic_function = (
            _IMPUTATION_STATISTICS.get(weighted_statistic) if weighted_statistic else None
        )
        if use_weighted and weighted_statistic_function is None:
            raise ValueError(
                f"Unrecognised PTR weighted imputation statistic "
                f"'{weighted_statistic}'. "
                f"Expected one of: {', '.join(_IMPUTATION_STATISTICS)}."
            )

        return imputation_statistic_function, weighted_statistic_function

    @staticmethod
    def impute_within_tissue_ptrs(
        ptr_df: pd.DataFrame,
        use_weighted: bool = True,
        weighted_statistic: str | None = "median",
        imputation_statistic: str = "median",
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Impute missing values for genes observed in at least one sample.
            Weighted behaviour is controlled by ``use_weighted``.

        Args:
            ptr_df (pd.DataFrame): PTR table in linear space (genes × samples).
            use_weighted (bool): Apply weighted per-column scaling during
                within-sample imputation.
            weighted_statistic (str | None): Statistic for weighted column ratio.
            imputation_statistic (str): Statistic used for row-wise base fill.

        Returns:
            pd.DataFrame: PTR table with within-sample missing values filled.

        Raises:
            ValueError: When weighting configuration or statistic is unrecognised.
        """
        SimplePTRImputationImplementation._validate_within_sample_weighting(
            use_weighted,
            weighted_statistic,
        )
        imputation_statistic_function, weighted_statistic_function = (
            SimplePTRImputationImplementation._resolve_within_sample_stat_functions(
                use_weighted,
                weighted_statistic,
                imputation_statistic,
            )
        )

        df = ptr_df.copy().replace({pd.NA: np.nan}).astype(float)
        row_stats = df.apply(lambda row: float(imputation_statistic_function(row)), axis=1)
        if use_weighted:
            assert weighted_statistic_function is not None
            ratio = SimplePTRImputationImplementation.get_weights(
                df, weighted_statistic_function
            )
        else:
            ratio = pd.Series(1.0, index=df.columns)

        for col in df.columns:
            mask = df[col].isna()
            if mask.any():
                df.loc[mask, col] = row_stats[mask].astype(float) * float(ratio[col])

        df.columns = df.columns.str.lower()
        return df

    # ------------------------------------------------------------------
    # Unobserved-gene imputation
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_unobserved_source_frame(
        ptr_df: pd.DataFrame,
        strategy: str,
        reference_df: pd.DataFrame | None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Resolve source PTR frame used to compute unobserved-gene fill
            statistics.

        Args:
            ptr_df (pd.DataFrame): PTR frame after within-sample imputation.
            strategy (str): Unobserved-gene strategy.
            reference_df (pd.DataFrame | None): Optional pre-imputation frame.

        Returns:
            pd.DataFrame: Source frame for per-sample statistics.

        Raises:
            ValueError: When before-imputation strategy is selected without
                a reference frame.
        """
        if strategy == "sample_before_imputation":
            if reference_df is None:
                raise ValueError(
                    "sample_before_imputation requires reference_df with original PTR values."
                )
            return reference_df.copy().replace({pd.NA: np.nan}).astype(float)
        return ptr_df.copy().replace({pd.NA: np.nan}).astype(float)

    @staticmethod
    def _compute_per_sample_fill_values(
        source_df: pd.DataFrame,
        statistic: str,
    ) -> dict[str, float]:
        """Generated: validation needed.

        Description:
            Compute one fill value per sample column from chosen source frame.

        Args:
            source_df (pd.DataFrame): Source frame used for statistics.
            statistic (str): Aggregation statistic key.

        Returns:
            dict[str, float]: Per-sample fill values.

        Raises:
            ValueError: When statistic key is unsupported.
        """
        base_statistic_function = _IMPUTATION_STATISTICS.get(statistic)
        if base_statistic_function is None:
            raise ValueError(
                f"Unrecognised unobserved_gene_imputation_statistic '{statistic}'. "
                f"Expected one of: {', '.join(_IMPUTATION_STATISTICS)}."
            )

        per_sample_values = {
            col: float(base_statistic_function(source_df[col])) for col in source_df.columns
        }

        return per_sample_values

    @staticmethod
    def _apply_global_unobserved_fill(
        df: pd.DataFrame,
        fill_values: dict[str, float],
        target_gene_ids: set[str],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Fill missing cells using one global per-sample statistic.

        Args:
            df (pd.DataFrame): Target PTR frame aligned to expression index.
            fill_values (dict[str, float]): Per-sample fallback values.
            target_gene_ids (set[str]): Gene IDs eligible for unobserved-gene fill.

        Returns:
            pd.DataFrame: Frame with missing values filled.
        """
        if not target_gene_ids:
            return df
        target_gene_mask = pd.Series(
            [str(gene_id) in target_gene_ids for gene_id in df.index],
            index=df.index,
            dtype=bool,
        )
        for col in df.columns:
            mask = df[col].isna() & target_gene_mask
            if mask.any():
                df.loc[mask, col] = fill_values.get(col, np.nan)
        return df

    @staticmethod
    def _apply_grouped_unobserved_fill(
        df: pd.DataFrame,
        source_df: pd.DataFrame,
        statistic: str,
        special_gene_groups: dict[str, list[str]],
        fallback_fill_values: dict[str, float],
        target_gene_ids: set[str],
        trace: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Fill missing cells by special-gene groups with independent per-group
            statistics and global fallback.

        Args:
            df (pd.DataFrame): Target PTR frame aligned to expression index.
            source_df (pd.DataFrame): Source frame for statistic calculation.
            statistic (str): Aggregation statistic key.
            special_gene_groups (dict[str, list[str]]): Group name to gene IDs.
            fallback_fill_values (dict[str, float]): Global per-sample fallback
                values.
            target_gene_ids (set[str]): Gene IDs eligible for unobserved-gene fill.
            trace (dict[str, Any] | None): Optional mutable trace dictionary
                populated with special-group mapping and assigned imputed values.

        Returns:
            pd.DataFrame: Frame with grouped missing-value imputation applied.
        """
        gene_group_lookup: dict[str, str] = {}
        for group_name, group_genes in special_gene_groups.items():
            for gene_id in group_genes:
                gene_group_lookup.setdefault(gene_id, group_name)

        group_fill_values: dict[str, dict[str, float]] = {}
        for group_name, group_genes in special_gene_groups.items():
            group_genes_in_source = source_df.index.intersection(group_genes)
            if len(group_genes_in_source) == 0:
                group_fill_values[group_name] = dict(fallback_fill_values)
                continue
            group_frame = pd.DataFrame(source_df.loc[group_genes_in_source])
            group_fill_values[group_name] = (
                SimplePTRImputationImplementation._compute_per_sample_fill_values(
                    group_frame,
                    statistic,
                )
            )

        assigned_values: dict[str, dict[str, float]] = {}
        if not target_gene_ids:
            return df

        df = df.copy().reindex(df.index.union(list(target_gene_ids)))
        target_gene_mask = pd.Series(
            [str(gene_id) in target_gene_ids for gene_id in df.index],
            index=df.index,
            dtype=bool,
        )
        for col in df.columns:
            mask = df[col].isna() & target_gene_mask
            if not bool(mask.any()):
                continue
            missing_gene_ids = df.index[mask]
            for gene_id in missing_gene_ids:
                group_name = gene_group_lookup.get(gene_id)
                assigned_value = (
                    SimplePTRImputationImplementation._resolve_grouped_fill_value(
                        column_name=col,
                        group_name=group_name,
                        group_fill_values=group_fill_values,
                        fallback_fill_values=fallback_fill_values,
                    )
                )
                df.at[gene_id, col] = assigned_value
                assigned_values.setdefault(str(gene_id), {})[str(col)] = assigned_value

        if trace is not None:
            trace["special_group_gene_mapping"] = dict(gene_group_lookup)
            trace["special_group_fill_values_per_sample"] = {
                group_name: dict(fill_values)
                for group_name, fill_values in group_fill_values.items()
            }
            trace["special_group_assigned_values_per_sample"] = assigned_values
        return df

    @staticmethod
    def _resolve_grouped_fill_value(
        *,
        column_name: Any,
        group_name: str | None,
        group_fill_values: dict[str, dict[str, float]],
        fallback_fill_values: dict[str, float],
    ) -> float:
        """Generated: validation needed.

        Description:
            Resolve one grouped unobserved-gene fill value with fallback.

        Args:
            column_name (Any): Sample/column identifier.
            group_name (str | None): Optional resolved group name.
            group_fill_values (dict[str, dict[str, float]]): Per-group fill values.
            fallback_fill_values (dict[str, float]): Global fallback fill values.

        Returns:
            float: Assigned fill value.
        """

        if group_name is None:
            return float(fallback_fill_values.get(column_name, np.nan))
        return float(
            group_fill_values[group_name].get(
                column_name,
                fallback_fill_values.get(column_name, np.nan),
            )
        )

    @staticmethod
    def impute_unobserved_genes(
        ptr_df: pd.DataFrame,
        unobserved_gene_ids: set[str],
        strategy: str = "sample_after_imputation",
        statistic: str = "median",
        reference_df: pd.DataFrame | None = None,
        special_gene_groups: dict[str, list[str]] | None = None,
        use_special_groups: bool = False,
        trace: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Expand PTR to match the full gene index of ``expression_df``.
            Genes present in expression but absent from PTR are filled using a
            per-sample statistic.  ``sample_after_imputation`` computes the
            statistic on the incoming (already-imputed) PTR values;
            ``sample_before_imputation`` behaves identically at call time since
            the pre-imputation snapshot must be supplied externally by the
            caller if needed.

        Args:
            ptr_df (pd.DataFrame): PTR table after within-sample imputation.
            expression_df (pd.DataFrame): Expression table whose index defines
                the target gene universe.
            unobserved_gene_ids (set[str]): Gene IDs present in expression but
                absent from PTR to be filled.
            strategy (str): Imputation strategy for unobserved genes.  One of
                ``sample_after_imputation``, ``sample_before_imputation``.
            statistic (str): Per-sample aggregation statistic.  One of
                ``median``, ``mean``, ``mode``, ``max``, ``min``.
            reference_df (pd.DataFrame | None): Pre-within-imputation PTR frame
                used when ``strategy='sample_before_imputation'``.
            special_gene_groups (dict[str, list[str]] | None): Optional
                special groups to impute independently.
            use_special_groups (bool): Enable special-group independent
                imputation behavior.
            trace (dict[str, Any] | None): Optional mutable trace dictionary
                populated with grouped-imputation diagnostics.

        Returns:
            pd.DataFrame: PTR table re-indexed to ``expression_df.index`` with
            unobserved genes filled.

        Raises:
            ValueError: When ``strategy``/``statistic`` is unrecognised or when
                ``sample_before_imputation`` lacks a reference frame.
        """
        if strategy not in ("sample_after_imputation", "sample_before_imputation"):
            raise ValueError(
                f"Unrecognised unobserved_gene_imputation_strategy '{strategy}'. "
                "Expected one of: sample_after_imputation, sample_before_imputation."
            )
        df = ptr_df.copy().replace({pd.NA: np.nan}).astype(float)
        source_df = SimplePTRImputationImplementation._resolve_unobserved_source_frame(
            ptr_df,
            strategy,
            reference_df,
        )
        fill_values = SimplePTRImputationImplementation._compute_per_sample_fill_values(
            source_df,
            statistic,
        )

        if not use_special_groups or not special_gene_groups:
            return SimplePTRImputationImplementation._apply_global_unobserved_fill(
                df,
                fill_values,
                unobserved_gene_ids,
            )

        return SimplePTRImputationImplementation._apply_grouped_unobserved_fill(
            df,
            source_df,
            statistic,
            special_gene_groups,
            fill_values,
            unobserved_gene_ids,
            trace=trace,
        )

    def prepare_ptr_frames(
        self,
        ptr_df: pd.DataFrame,
        expression_df: pd.DataFrame,
        cobra_model: Model,
        metabolic_genes: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        ptr_cfg = self.full_config.protein

        df = self.standardize_ptr_frame(ptr_df)
        self.logger.debug(f"PTR: standardized frame shape{df.shape}")

        full_df = self.remove_ptr_duplicates(df)
        dfs_to_impute = {"PTR_df_all_genes": full_df}
        self.logger.debug(f"PTR: deduplicated frame shape{df.shape}")
        if ptr_cfg.impute_from_metabolic_genes_only and metabolic_genes is not None:
            before = len(df)
            metabolic_df = df.loc[df.index.isin(metabolic_genes)]
            self.logger.debug(
                f"PTR: filtered to {len(df)} metabolic genes (dropped {before - len(df)})."
            )
            dfs_to_impute["PTR_df_metabolic_genes"] = metabolic_df

        prepared_dfs: dict[str, pd.DataFrame] = {}
        for df_name, df in dfs_to_impute.items():
            if df.empty:
                self.logger.warning(
                    "PTR: no genes remain after filtering for metabolic genes. "
                    "Skipping imputation."
                )
                continue
            df = transform_ptr_to_linear(df, self.full_config.protein.PTR_pretransformed_type)
            prepared_dfs[df_name] = df

        return prepared_dfs

    def create_metadata(
        self,
        elapsed_time: float,
        **kwargs,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Create metadata dictionary for the expression stage.

        Args:
            elapsed_time (float): Time taken for processing.

        Returns:
            dict[str, object]: Metadata dictionary.
        """

        metadata = {
            "PTR_imputation": {
                "implementation": self.__class__.__name__,
                "status": "ptr_imputation_completed",
                "elapsed_time_seconds": elapsed_time,
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
