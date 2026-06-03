"""Generated: validation needed.

Description:
    PTR submodule implementation used by protein-stage coordinator.
    Provides standardization, deduplication, linear transform, within-sample
    imputation, unobserved-gene imputation, and expression×PTR multiplication
    with optional sample-type column mapping.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.protein.input_resolution import resolve_dataframe_input
from VmaxBuilder.utils.extra_utils import (
    get_transport_reaction_gene_ids,
    resolve_gene_or_reaction_group_members,
)
from VmaxBuilder.utils.transformations import transform_dataframe

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
_PRETRANSFORM_ALIASES: dict[str, str] = {
    "none": "linear",
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
    # Within-sample imputation
    # ------------------------------------------------------------------

    @staticmethod
    def transform_ptr_to_linear(
        ptr_df: pd.DataFrame,
        pretransformed_type: str = "linear",
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Convert PTR frame to linear space from configured transform state.
            Supports ``none`` alias for ``linear``.

        Args:
            ptr_df (pd.DataFrame): PTR table in source transform space.
            pretransformed_type (str): Source transform key. One of
                ``linear``, ``log10``, ``log2``, ``ln``.

        Returns:
            pd.DataFrame: PTR table transformed to linear space.

        Raises:
            ValueError: When ``pretransformed_type`` is unsupported.
        """
        canonical_type = _PRETRANSFORM_ALIASES.get(pretransformed_type, pretransformed_type)
        return transform_dataframe(
            ptr_df,
            pretransformed_type=canonical_type,
            target_transformation="linear",
        )

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
        DefaultPTRImplementation._validate_within_sample_weighting(
            use_weighted,
            weighted_statistic,
        )
        imputation_statistic_function, weighted_statistic_function = (
            DefaultPTRImplementation._resolve_within_sample_stat_functions(
                use_weighted,
                weighted_statistic,
                imputation_statistic,
            )
        )

        df = ptr_df.copy().replace({pd.NA: np.nan}).astype(float)
        row_stats = df.apply(lambda row: float(imputation_statistic_function(row)), axis=1)
        if use_weighted:
            assert weighted_statistic_function is not None
            ratio = DefaultPTRImplementation.get_weights(df, weighted_statistic_function)
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
                DefaultPTRImplementation._compute_per_sample_fill_values(
                    group_frame,
                    statistic,
                )
            )

        assigned_values: dict[str, dict[str, float]] = {}
        if not target_gene_ids:
            return df

        df = df.copy().reindex(df.index.union(target_gene_ids))
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
                assigned_value = DefaultPTRImplementation._resolve_grouped_fill_value(
                    column_name=col,
                    group_name=group_name,
                    group_fill_values=group_fill_values,
                    fallback_fill_values=fallback_fill_values,
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
        expression_df: pd.DataFrame,
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
        source_df = DefaultPTRImplementation._resolve_unobserved_source_frame(
            ptr_df,
            strategy,
            reference_df,
        )
        fill_values = DefaultPTRImplementation._compute_per_sample_fill_values(
            source_df,
            statistic,
        )

        if not use_special_groups or not special_gene_groups:
            return DefaultPTRImplementation._apply_global_unobserved_fill(
                df,
                fill_values,
                unobserved_gene_ids,
            )

        return DefaultPTRImplementation._apply_grouped_unobserved_fill(
            df,
            source_df,
            statistic,
            special_gene_groups,
            fill_values,
            unobserved_gene_ids,
            trace=trace,
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
        model_artifact: Any | None = None,
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
            model_artifact (Any | None): Optional cobra-like model used to
                expand shorthand special gene groups such as
                ``transport_reactions``.

        Returns:
            pd.DataFrame: Fully preprocessed PTR table aligned to the
            expression gene index.
        """
        ptr_cfg = config.ptr
        ptr_imputation_trace: dict[str, Any] = {}

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

        df = self.transform_ptr_to_linear(
            df,
            pretransformed_type=ptr_cfg.pretransformed_type,
        )

        before_within_imputation_df = df.copy()

        df = self.impute_within_tissue_ptrs(
            df,
            use_weighted=ptr_cfg.partial_missing_use_weighted,
            weighted_statistic=ptr_cfg.partial_missing_weighted_statistic,
            imputation_statistic=ptr_cfg.partial_missing_imputation_statistic,
        )
        _logger.debug("PTR: within-sample imputation done.")

        unobserved_strategy = ptr_cfg.unobserved_gene_imputation_strategy
        special_gene_groups = self.resolve_special_gene_groups(
            config,
            model_artifact=model_artifact,
            expression_gene_ids=set(map(str, expression_df.index)),
        )

        if (
            not special_gene_groups
            and ptr_cfg.use_special_groups_for_unobserved_imputation
            and model_artifact is not None
        ):
            special_gene_groups = {
                "transport_reactions": get_transport_reaction_gene_ids(
                    model_artifact,
                    expression_gene_ids=set(map(str, expression_df.index)),
                )
            }
            _logger.debug(
                "PTR: auto-populated transport_reactions group (%d genes).",
                len(special_gene_groups.get("transport_reactions", [])),
            )

        unobserved_genes: set[str] = set(map(str, expression_df.index)) - set(
            map(str, df.index)
        )

        if not unobserved_genes:
            _logger.debug(
                "PTR: no unobserved genes to impute after within-sample imputation."
            )
            return df.reindex(expression_df.index)

        df = self.impute_unobserved_genes(
            df.reindex(df.index.union(unobserved_genes), fill_value=np.nan),
            expression_df,
            unobserved_gene_ids=unobserved_genes,
            strategy=unobserved_strategy,
            statistic=ptr_cfg.unobserved_gene_imputation_statistic,
            reference_df=before_within_imputation_df,
            special_gene_groups=special_gene_groups,
            use_special_groups=ptr_cfg.use_special_groups_for_unobserved_imputation,
            trace=ptr_imputation_trace,
        )
        _logger.debug("PTR: unobserved-gene imputation done, final shape %s.", df.shape)

        self._latest_ptr_preparation_diagnostics = {
            "special_gene_groups": special_gene_groups,
            "special_group_gene_mapping": ptr_imputation_trace.get(
                "special_group_gene_mapping", {}
            ),
            "special_group_fill_values_per_sample": ptr_imputation_trace.get(
                "special_group_fill_values_per_sample",
                {},
            ),
            "special_group_assigned_values_per_sample": ptr_imputation_trace.get(
                "special_group_assigned_values_per_sample",
                {},
            ),
        }

        return df

    def get_latest_preparation_diagnostics(self) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Return diagnostics captured during latest PTR preparation call.

        Returns:
            dict[str, Any]: PTR preparation diagnostics for inter-stage artifact
            persistence.
        """
        diagnostics = getattr(self, "_latest_ptr_preparation_diagnostics", {})
        return dict(diagnostics)

    @staticmethod
    def resolve_special_gene_groups(
        config: APIConfig,
        model_artifact: Any | None = None,
        expression_gene_ids: set[str] | None = None,
    ) -> dict[str, list[str]]:
        """Generated: validation needed.

        Description:
            Resolve user-provided special gene groups used by PTR unobserved-gene
            imputation. This endpoint enables independent group-wise imputation
            (e.g., transport genes or other custom partitions). Group values
            may contain gene IDs or reaction IDs; ``transport_reactions`` with
            an empty list auto-resolves transport-associated genes from model.

        Args:
            config (APIConfig): Root API configuration.
            model_artifact (Any | None): Optional cobra-like model used for
                shorthand and reaction-based group expansion.
            expression_gene_ids (set[str] | None): Optional expression-gene
                universe used to filter resolved group members.

        Returns:
            dict[str, list[str]]: Mapping of group name to normalized gene IDs.

        Raises:
            ValueError: When ``transport_reactions`` shorthand is requested
                without a model artifact.
        """
        raw_groups = config.ptr.special_gene_groups
        if raw_groups is None:
            return {}
        normalized_groups: dict[str, list[str]] = {}
        for group_name, group_genes in raw_groups.items():
            normalized_name = str(group_name).strip()
            if normalized_name == "":
                continue
            normalized_entries = [
                str(group_entry).strip()
                for group_entry in group_genes
                if str(group_entry).strip() != ""
            ]
            if normalized_name == "transport_reactions" and not normalized_entries:
                if model_artifact is None:
                    raise ValueError(
                        "special_gene_groups['transport_reactions'] requires a model "
                        "artifact when no explicit genes or reactions are supplied."
                    )
                normalized_groups[normalized_name] = get_transport_reaction_gene_ids(
                    model_artifact,
                    expression_gene_ids=expression_gene_ids,
                )
                continue
            normalized_groups[normalized_name] = resolve_gene_or_reaction_group_members(
                model_artifact,
                normalized_entries,
                expression_gene_ids=expression_gene_ids,
            )
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
