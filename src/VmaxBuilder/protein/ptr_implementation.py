"""Generated: validation needed.

Description:
    PTR submodule implementation used by protein-stage coordinator.
    Provides standardization, deduplication, linear transform, within-sample
    imputation, unobserved-gene imputation, and expression×PTR multiplication
    with optional sample-type column mapping.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input

_logger = logging.getLogger(__name__)

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


def _normalize_sample_label(value: Any) -> str:
    """Generated: validation needed.

    Description:
        Normalize sample/tissue labels for robust matching across expression,
        PTR, and explicit tissue-map configuration.

    Args:
        value (Any): Raw label value.

    Returns:
        str: Normalized label (trimmed, lower-case, optional ``_ptr`` suffix removed).
    """
    text = str(value).strip().lower()
    if text.endswith("_ptr"):
        text = text[: -len("_ptr")]
    return text


_IMPUTATION_STATISTICS: dict[str, Any] = {
    "median": lambda s: s.median(skipna=True),
    "mean": lambda s: s.mean(skipna=True),
    "mode": _series_mode,
    "max": lambda s: s.max(skipna=True),
    "min": lambda s: s.min(skipna=True),
}


class DefaultPTRImplementation:
    """Generated: validation needed.

    Description:
        PTR preprocessing and combination logic for the expression+PTR protein
        abundance pathway.  Covers standardisation, deduplication, log→linear
        conversion, within-sample imputation, and expansion to the full
        expression gene index.
    """

    _METHODS_REQUIRING_SAMPLE_TYPE_MAP: frozenset[str] = frozenset({"ptr_weighted_median"})

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Standardization
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    def remove_ptr_duplicates(ptr_df: pd.DataFrame) -> pd.DataFrame:
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
            _logger.warning(
                "PTR: removed %d residual duplicate rows after targeted deduplication.",
                n_before - len(df),
            )
        return pd.DataFrame(df)

    # ------------------------------------------------------------------
    # Log → linear conversion
    # ------------------------------------------------------------------

    @staticmethod
    def transform_ptr_to_linear(
        ptr_df: pd.DataFrame,
        pretransformed_type: str = "none",
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Convert PTR values from a log scale back to linear space.

        Args:
            ptr_df (pd.DataFrame): PTR table in log or linear space.
            pretransformed_type (str): Log base applied to raw input.  One of
                ``none``, ``log10``, ``log2``, ``ln``.

        Returns:
            pd.DataFrame: PTR table in linear space.

        Raises:
            ValueError: When ``pretransformed_type`` is unrecognised.
        """
        df = ptr_df.copy().replace({pd.NA: np.nan}).astype(float)
        if pretransformed_type == "none":
            pass
        elif pretransformed_type == "log10":
            df = df.apply(lambda col: 10**col)
        elif pretransformed_type == "log2":
            df = df.apply(lambda col: 2**col)
        elif pretransformed_type == "ln":
            df = df.apply(lambda col: np.e**col)
        else:
            raise ValueError(
                f"Unrecognised PTR pretransformed_type '{pretransformed_type}'. "
                "Expected one of: none, log10, log2, ln."
            )
        return df

    # ------------------------------------------------------------------
    # Within-sample imputation
    # ------------------------------------------------------------------

    @staticmethod
    def impute_within_tissue_ptrs(
        ptr_df: pd.DataFrame,
        strategy: str = "weighted_median",
        statistic: str = "median",
        use_weighted: bool = True,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Impute missing values for genes that are *observed* in at least one
            sample.  Two strategies are available:

            * ``weighted_median``: fill each missing cell with
              ``row_median × (col_median / median_of_col_medians)``.
            * ``median``: fill each missing cell with the row median.

        Args:
            ptr_df (pd.DataFrame): PTR table in linear space (genes × samples).
            strategy (str): Imputation strategy.  One of ``weighted_median``,
                ``median``.
            statistic (str): Row/column statistic used for imputation. One of
                ``median``, ``mean``, ``mode``, ``max``, ``min``.
            use_weighted (bool): Whether to scale row statistic by tissue
                statistic ratio.

        Returns:
            pd.DataFrame: PTR table with within-sample missing values filled.

        Raises:
            ValueError: When ``strategy`` or ``statistic`` is unrecognised.
        """
        df = ptr_df.copy().replace({pd.NA: np.nan}).astype(float)
        if strategy == "weighted_median":
            statistic = "median"
            use_weighted = True
        elif strategy == "median":
            statistic = "median"
            use_weighted = False
        elif strategy != "custom":
            raise ValueError(
                f"Unrecognised PTR missing_value_strategy '{strategy}'. "
                "Expected one of: weighted_median, median, custom."
            )

        stat_fn = _IMPUTATION_STATISTICS.get(statistic)
        if stat_fn is None:
            raise ValueError(
                f"Unrecognised PTR partial_missing_imputation_statistic '{statistic}'. "
                f"Expected one of: {', '.join(_IMPUTATION_STATISTICS)}."
            )

        row_stats = df.apply(lambda row: float(stat_fn(row)), axis=1)
        if use_weighted:
            col_stats = pd.Series({col: float(stat_fn(df[col])) for col in df.columns})
            median_of_col_stats = float(col_stats.median(skipna=True))
            ratio = (
                col_stats / median_of_col_stats
                if median_of_col_stats != 0 and not np.isnan(median_of_col_stats)
                else pd.Series(1.0, index=col_stats.index)
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
        stat_fn = _IMPUTATION_STATISTICS.get(statistic)
        if stat_fn is None:
            raise ValueError(
                f"Unrecognised unobserved_gene_imputation_statistic '{statistic}'. "
                f"Expected one of: {', '.join(_IMPUTATION_STATISTICS)}."
            )
        return {col: float(stat_fn(source_df[col])) for col in source_df.columns}

    @staticmethod
    def _apply_global_unobserved_fill(
        df: pd.DataFrame,
        fill_values: dict[str, float],
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Fill missing cells using one global per-sample statistic.

        Args:
            df (pd.DataFrame): Target PTR frame aligned to expression index.
            fill_values (dict[str, float]): Per-sample fallback values.

        Returns:
            pd.DataFrame: Frame with missing values filled.
        """
        for col in df.columns:
            mask = df[col].isna()
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

        Returns:
            pd.DataFrame: Frame with grouped missing-value imputation applied.
        """
        stat_fn = _IMPUTATION_STATISTICS[statistic]

        gene_group_lookup: dict[str, str] = {}
        for group_name, group_genes in special_gene_groups.items():
            for gene_id in group_genes:
                gene_group_lookup.setdefault(gene_id, group_name)

        group_fill_values: dict[str, dict[str, float]] = {}
        for group_name, group_genes in special_gene_groups.items():
            group_genes_in_source = source_df.index.intersection(group_genes)
            if group_genes_in_source.empty:
                group_fill_values[group_name] = fallback_fill_values
                continue
            group_frame = source_df.loc[group_genes_in_source]
            group_fill_values[group_name] = {
                col: float(stat_fn(group_frame[col])) for col in source_df.columns
            }

        for col in df.columns:
            mask = df[col].isna()
            if not mask.any():
                continue
            missing_gene_ids = df.index[mask]
            for gene_id in missing_gene_ids:
                group_name = gene_group_lookup.get(gene_id)
                if group_name is None:
                    df.at[gene_id, col] = fallback_fill_values.get(col, np.nan)
                    continue
                df.at[gene_id, col] = group_fill_values[group_name].get(
                    col,
                    fallback_fill_values.get(col, np.nan),
                )
        return df

    @staticmethod
    def impute_unobserved_genes(
        ptr_df: pd.DataFrame,
        expression_df: pd.DataFrame,
        strategy: str = "sample_after_imputation",
        statistic: str = "median",
        reference_df: pd.DataFrame | None = None,
        special_gene_groups: dict[str, list[str]] | None = None,
        use_special_groups: bool = False,
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
        source_df = DefaultPTRImplementation._resolve_unobserved_source_frame(
            ptr_df,
            strategy,
            reference_df,
        )
        fill_values = DefaultPTRImplementation._compute_per_sample_fill_values(
            source_df,
            statistic,
        )

        df = df.reindex(expression_df.index)

        if not use_special_groups or not special_gene_groups:
            return DefaultPTRImplementation._apply_global_unobserved_fill(df, fill_values)

        return DefaultPTRImplementation._apply_grouped_unobserved_fill(
            df,
            source_df,
            statistic,
            special_gene_groups,
            fill_values,
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def prepare_ptr_frame(
        self,
        ptr_df: pd.DataFrame,
        expression_df: pd.DataFrame,
        config: APIConfig,
        metabolic_genes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Full PTR preprocessing pipeline: standardize → deduplicate →
            optionally filter to metabolic genes → convert to linear scale →
            impute within-sample missing values → expand to expression gene
            index.

        Args:
            ptr_df (pd.DataFrame): Raw PTR input table (genes × tissue-types).
            expression_df (pd.DataFrame): Preprocessed expression table used
                to define the target gene universe and guide imputation.
            config (APIConfig): Root API configuration.  PTR options read from
                ``config.ptr``.
            metabolic_genes (list[str] | None): Optional list of gene IDs from
                the metabolic model.  When provided and
                ``config.ptr.impute_from_metabolic_genes_only`` is ``True``,
                PTR is filtered to this set before imputation.

        Returns:
            pd.DataFrame: Fully preprocessed PTR table aligned to the
            expression gene index.
        """
        ptr_cfg = config.ptr

        df = self.standardize_ptr_frame(ptr_df)
        _logger.debug("PTR: standardized frame shape %s.", df.shape)

        df = self.remove_ptr_duplicates(df)
        _logger.debug("PTR: deduplicated frame shape %s.", df.shape)

        if ptr_cfg.impute_from_metabolic_genes_only and metabolic_genes is not None:
            before = len(df)
            df = df.loc[df.index.isin(metabolic_genes)]
            _logger.debug(
                "PTR: filtered to %d metabolic genes (dropped %d).",
                len(df),
                before - len(df),
            )

        df = self.transform_ptr_to_linear(df, pretransformed_type=ptr_cfg.pretransformed_type)
        _logger.debug("PTR: converted to linear scale.")

        before_within_imputation_df = df.copy()

        df = self.impute_within_tissue_ptrs(
            df,
            strategy=ptr_cfg.missing_value_strategy,
            statistic=ptr_cfg.partial_missing_imputation_statistic,
            use_weighted=ptr_cfg.partial_missing_use_weighted,
        )
        _logger.debug("PTR: within-sample imputation done.")

        unobserved_strategy = ptr_cfg.unobserved_gene_imputation_strategy
        if ptr_cfg.unobserved_gene_imputation_reference == "before_within_sample_imputation":
            unobserved_strategy = "sample_before_imputation"
        elif ptr_cfg.unobserved_gene_imputation_reference == "after_within_sample_imputation":
            unobserved_strategy = "sample_after_imputation"

        special_gene_groups = self.resolve_special_gene_groups(config)

        df = self.impute_unobserved_genes(
            df,
            expression_df,
            strategy=unobserved_strategy,
            statistic=ptr_cfg.unobserved_gene_imputation_statistic,
            reference_df=before_within_imputation_df,
            special_gene_groups=special_gene_groups,
            use_special_groups=ptr_cfg.use_special_groups_for_unobserved_imputation,
        )
        _logger.debug("PTR: unobserved-gene imputation done, final shape %s.", df.shape)

        return df

    @staticmethod
    def resolve_special_gene_groups(config: APIConfig) -> dict[str, list[str]]:
        """Generated: validation needed.

        Description:
            Resolve user-provided special gene groups used by PTR unobserved-gene
            imputation. This endpoint enables independent group-wise imputation
            (e.g., transport genes or other custom partitions).

        Args:
            config (APIConfig): Root API configuration.

        Returns:
            dict[str, list[str]]: Mapping of group name to normalized gene IDs.
        """
        raw_groups = config.ptr.special_gene_groups
        if raw_groups is None:
            return {}
        normalized_groups: dict[str, list[str]] = {}
        for group_name, group_genes in raw_groups.items():
            normalized_name = str(group_name).strip()
            if normalized_name == "":
                continue
            normalized_groups[normalized_name] = [
                str(gene_id).strip() for gene_id in group_genes if str(gene_id).strip() != ""
            ]
        return normalized_groups

    @classmethod
    def requires_sample_type_map(cls, ptr_method: str) -> bool:
        """Generated: validation needed.

        Description:
            Report whether a PTR implementation strategy requires an explicit
            expression→PTR sample/tissue mapping.

        Args:
            ptr_method (str): PTR strategy key from ``config.protein.ptr_method``.

        Returns:
            bool: ``True`` when selected PTR method requires
            ``expression.sample_type_map``.
        """
        return ptr_method in cls._METHODS_REQUIRING_SAMPLE_TYPE_MAP

    # ------------------------------------------------------------------
    # Sample-type map resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_sample_type_map(
        expression_df: pd.DataFrame,
        sample_type_map: dict[str, str] | str | None,
    ) -> dict[str, str]:
        """Generated: validation needed.

        Description:
            Build a ``{expression_column: ptr_column}`` mapping from the
            user-supplied ``sample_type_map``.

            * ``None`` → identity map (each expression column maps to itself).
            * ``str`` → every expression column maps to that single PTR column.
            * ``dict`` → used directly; expression columns absent from the dict
              fall back to an identity mapping.

            Labels are normalized for robust matching: lower-case, stripped
            whitespace, and ``_ptr`` suffix removed.

        Args:
            expression_df (pd.DataFrame): Expression table whose columns define
                the source keys.
            sample_type_map (dict[str, str] | str | None): User-configured
                column mapping.

        Returns:
            dict[str, str]: Mapping of expression column → PTR column.
        """
        expr_cols_normalized = {
            expr_col: _normalize_sample_label(expr_col) for expr_col in expression_df.columns
        }

        if sample_type_map is None:
            return expr_cols_normalized
        if isinstance(sample_type_map, str):
            normalized_target = _normalize_sample_label(sample_type_map)
            return {col: normalized_target for col in expression_df.columns}

        normalized_input_map: dict[str, str] = {
            _normalize_sample_label(src_col): _normalize_sample_label(dst_col)
            for src_col, dst_col in sample_type_map.items()
        }
        return {
            expr_col: normalized_input_map.get(expr_col_norm, expr_col_norm)
            for expr_col, expr_col_norm in expr_cols_normalized.items()
        }

    # ------------------------------------------------------------------
    # Combination
    # ------------------------------------------------------------------

    def combine_expression_with_ptr(
        self,
        expression_df: pd.DataFrame,
        ptr_df: pd.DataFrame,
        sample_type_map: dict[str, str] | str | None = None,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Multiply expression values by PTR values for each gene, using the
            resolved sample-type column mapping to pair expression columns with
            PTR columns.  Genes absent from PTR retain their expression values.

        Args:
            expression_df (pd.DataFrame): Preprocessed expression table
                (genes × expression-samples).
            ptr_df (pd.DataFrame): Preprocessed PTR table
                (genes × tissue-types).
            sample_type_map (dict[str, str] | str | None): Mapping from
                expression column names to PTR column names.  ``str`` maps
                every expression column to the same PTR column; ``None`` falls
                back to direct column intersection.

        Returns:
            pd.DataFrame: Combined protein abundance table with same shape as
            ``expression_df``.
        """
        col_map = self.resolve_sample_type_map(expression_df, sample_type_map)
        protein_df = expression_df.copy()
        common_genes = expression_df.index.intersection(ptr_df.index)

        ptr_col_lookup: dict[str, str] = {}
        for ptr_col in ptr_df.columns:
            normalized_ptr_col = _normalize_sample_label(ptr_col)
            ptr_col_lookup.setdefault(normalized_ptr_col, ptr_col)

        if common_genes.empty:
            _logger.warning(
                "PTR: no overlapping genes between expression and PTR; "
                "returning unmodified expression."
            )
            return protein_df

        for expr_col, ptr_col in col_map.items():
            if expr_col not in expression_df.columns:
                continue
            ptr_col_actual = ptr_col_lookup.get(ptr_col)
            if ptr_col_actual is None:
                _logger.warning(
                    "PTR: column '%s' not found in PTR frame; "
                    "skipping multiplication for expression column '%s'.",
                    ptr_col,
                    expr_col,
                )
                continue
            protein_df.loc[common_genes, expr_col] = (
                expression_df.loc[common_genes, expr_col]
                * ptr_df.loc[common_genes, ptr_col_actual]
            )

        return protein_df
