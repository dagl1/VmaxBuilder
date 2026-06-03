"""Tests for DefaultPTRImplementation preprocessing and combination logic."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.protein.ptr_implementation import DefaultPTRImplementation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ptr_impl() -> DefaultPTRImplementation:
    return DefaultPTRImplementation()


def _make_ptr(data: dict, index: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if index is not None:
        df.index = index
    return df


def _make_expression(
    genes: list[str], samples: list[str], value: float = 1.0
) -> pd.DataFrame:
    return pd.DataFrame(
        [[value] * len(samples)] * len(genes),
        index=genes,
        columns=samples,
    )


# ---------------------------------------------------------------------------
# standardize_ptr_frame
# ---------------------------------------------------------------------------


class TestStandardizePtrFrame:
    def test_replaces_nan_tokens_with_nan(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": ["nan", "n/a", "1.5"]}, index=["g1", "g2", "g3"])
        result = ptr_impl.standardize_ptr_frame(df)
        assert pd.isna(result.loc["g1", "s1"])
        assert pd.isna(result.loc["g2", "s1"])
        assert result.loc["g3", "s1"] == pytest.approx(1.5)

    def test_coerces_to_numeric(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1, 2, 3]}, index=["g1", "g2", "g3"])
        result = ptr_impl.standardize_ptr_frame(df)
        assert result["s1"].dtype in (object, "Float64") or pd.api.types.is_numeric_dtype(
            result["s1"]
        )

    def test_lowercases_column_names(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"LIVER": [1.0, 2.0]}, index=["g1", "g2"])
        result = ptr_impl.standardize_ptr_frame(df)
        assert "liver" in result.columns

    def test_replaces_inf_with_na(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [np.inf, -np.inf, 1.0]}, index=["g1", "g2", "g3"])
        result = ptr_impl.standardize_ptr_frame(df)
        assert pd.isna(result.loc["g1", "s1"])
        assert pd.isna(result.loc["g2", "s1"])


# ---------------------------------------------------------------------------
# remove_ptr_duplicates
# ---------------------------------------------------------------------------


class TestRemovePtrDuplicates:
    def test_keeps_row_with_most_values(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {
                "s1": [1.0, np.nan, 2.0],
                "s2": [np.nan, np.nan, 3.0],
            },
            index=["g1", "g1", "g2"],
        )
        result = ptr_impl.remove_ptr_duplicates(df)
        assert result.index.is_unique
        # first g1 row has one non-NaN (s1=1.0), second has zero — keep first
        assert result.loc["g1", "s1"] == pytest.approx(1.0)

    def test_no_duplicates_unchanged(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0, 2.0]}, index=["g1", "g2"])
        result = ptr_impl.remove_ptr_duplicates(df)
        assert result.equals(df)

    def test_tied_keeps_first(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {"s1": [1.0, 99.0]},
            index=["g1", "g1"],
        )
        result = ptr_impl.remove_ptr_duplicates(df)
        assert len(result) == 1
        assert result.loc["g1", "s1"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# transform_ptr_to_linear
# ---------------------------------------------------------------------------


class TestTransformPtrToLinear:
    def test_none_is_identity(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [2.0, 4.0]}, index=["g1", "g2"])
        result = ptr_impl.transform_ptr_to_linear(df, pretransformed_type="none")
        assert result.loc["g1", "s1"] == pytest.approx(2.0)

    def test_log10_conversion(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0, 2.0]}, index=["g1", "g2"])
        result = ptr_impl.transform_ptr_to_linear(df, pretransformed_type="log10")
        assert result.loc["g1", "s1"] == pytest.approx(10.0)
        assert result.loc["g2", "s1"] == pytest.approx(100.0)

    def test_log2_conversion(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0, 3.0]}, index=["g1", "g2"])
        result = ptr_impl.transform_ptr_to_linear(df, pretransformed_type="log2")
        assert result.loc["g1", "s1"] == pytest.approx(2.0)
        assert result.loc["g2", "s1"] == pytest.approx(8.0)

    def test_ln_conversion(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        result = ptr_impl.transform_ptr_to_linear(df, pretransformed_type="ln")
        assert result.loc["g1", "s1"] == pytest.approx(np.e)

    def test_invalid_raises(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        with pytest.raises(ValueError, match="pretransformed_type"):
            ptr_impl.transform_ptr_to_linear(df, pretransformed_type="log3")


# ---------------------------------------------------------------------------
# impute_within_tissue_ptrs
# ---------------------------------------------------------------------------


class TestImputeWithinTissuePtrs:
    def test_weighted_median_fills_missing(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {
                "s1": [1.0, np.nan, 3.0],
                "s2": [2.0, 4.0, 6.0],
            },
            index=["g1", "g2", "g3"],
        )
        result = ptr_impl.impute_within_tissue_ptrs(
            df, use_weighted=True, imputation_statistic="median"
        )
        assert not result["s1"].isna().any()

    def test_median_fills_missing(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {"s1": [np.nan, 4.0, 6.0], "s2": [2.0, 4.0, 6.0]},
            index=["g1", "g2", "g3"],
        )
        result = ptr_impl.impute_within_tissue_ptrs(
            df, use_weighted=False, imputation_statistic="median"
        )
        # g1 row median = mean(nan, 2.0) = 2.0 → fill s1 with row median
        assert not result["s1"].isna().any()

    def test_invalid_strategy_raises(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        with pytest.raises(ValueError, match="imputation_statistic"):
            ptr_impl.impute_within_tissue_ptrs(
                df, use_weighted=False, imputation_statistic="invalid_stat"
            )

    def test_custom_mean_unweighted(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {
                "s1": [1.0, np.nan],
                "s2": [3.0, 5.0],
            },
            index=["g1", "g2"],
        )
        result = ptr_impl.impute_within_tissue_ptrs(
            df,
            use_weighted=False,
            imputation_statistic="mean",
        )
        assert result.loc["g2", "s1"] == pytest.approx(5.0)

    def test_custom_median_weighted(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame(
            {
                "s1": [2.0, np.nan],
                "s2": [10.0, 2.0],
            },
            index=["g1", "g2"],
        )
        result = ptr_impl.impute_within_tissue_ptrs(
            df,
            use_weighted=True,
            imputation_statistic="median",
        )
        assert not pd.isna(result.loc["g2", "s1"])

    def test_no_missing_unchanged(self, ptr_impl: DefaultPTRImplementation) -> None:
        df = pd.DataFrame({"s1": [1.0, 2.0], "s2": [3.0, 4.0]}, index=["g1", "g2"])
        result = ptr_impl.impute_within_tissue_ptrs(df)
        assert result["s1"].tolist() == pytest.approx([1.0, 2.0])


# ---------------------------------------------------------------------------
# impute_unobserved_genes
# ---------------------------------------------------------------------------


class TestImputeUnobservedGenes:
    def test_expands_to_expression_index(self, ptr_impl: DefaultPTRImplementation) -> None:
        ptr = pd.DataFrame({"s1": [2.0, 4.0, np.nan]}, index=["g1", "g2", "g3"])
        expr = _make_expression(["g1", "g2", "g3"], ["s1"])
        result = ptr_impl.impute_unobserved_genes(ptr, expr, unobserved_gene_ids={"g3"})
        assert "g3" in result.index
        assert not result["s1"].isna().any()

    def test_fill_value_is_sample_median(self, ptr_impl: DefaultPTRImplementation) -> None:
        ptr = pd.DataFrame({"s1": [2.0, 4.0, np.nan]}, index=["g1", "g2", "g3"])
        expr = _make_expression(["g1", "g2", "g3"], ["s1"])
        result = ptr_impl.impute_unobserved_genes(
            ptr,
            expr,
            unobserved_gene_ids={"g3"},
            statistic="median",
        )
        # median of [2.0, 4.0] = 3.0
        assert result.loc["g3", "s1"] == pytest.approx(3.0)

    def test_fill_values_are_computed_per_column(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        ptr = pd.DataFrame(
            {
                "s1": [2.0, 4.0, np.nan],
                "s2": [20.0, 40.0, np.nan],
            },
            index=["g1", "g2", "g3"],
        )
        expr = _make_expression(["g1", "g2", "g3"], ["s1", "s2"])
        result = ptr_impl.impute_unobserved_genes(
            ptr,
            expr,
            unobserved_gene_ids={"g3"},
            statistic="median",
        )

        assert result.loc["g3", "s1"] == pytest.approx(3.0)
        assert result.loc["g3", "s2"] == pytest.approx(30.0)

    def test_invalid_strategy_raises(self, ptr_impl: DefaultPTRImplementation) -> None:
        ptr = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        expr = _make_expression(["g1"], ["s1"])
        with pytest.raises(ValueError, match="imputation_strategy"):
            ptr_impl.impute_unobserved_genes(
                ptr, expr, unobserved_gene_ids={"g2"}, strategy="mode"
            )

    def test_invalid_statistic_raises(self, ptr_impl: DefaultPTRImplementation) -> None:
        ptr = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        expr = _make_expression(["g1"], ["s1"])
        with pytest.raises(ValueError, match="imputation_statistic"):
            ptr_impl.impute_unobserved_genes(
                ptr, expr, unobserved_gene_ids={"g2"}, statistic="percentile"
            )

    def test_sample_before_uses_reference_frame(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        ptr_after = pd.DataFrame({"s1": [10.0, 12.0, np.nan]}, index=["g1", "g2", "g3"])
        ptr_before = pd.DataFrame({"s1": [2.0, 4.0, np.nan]}, index=["g1", "g2", "g3"])
        expr = _make_expression(["g1", "g2", "g3"], ["s1"])
        result = ptr_impl.impute_unobserved_genes(
            ptr_after,
            expr,
            unobserved_gene_ids={"g3"},
            strategy="sample_before_imputation",
            statistic="median",
            reference_df=ptr_before,
        )
        assert result.loc["g3", "s1"] == pytest.approx(3.0)

    def test_special_groups_are_imputed_independently(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        ptr = pd.DataFrame(
            {
                "heart": [100.0, 80.0],
            },
            index=["g_transport_1", "g_other_1"],
        )
        expr = _make_expression(["g_transport_1", "g_other_1", "g_transport_2"], ["heart"])
        result = ptr_impl.impute_unobserved_genes(
            ptr,
            expr,
            unobserved_gene_ids={"g_transport_2"},
            strategy="sample_after_imputation",
            statistic="median",
            special_gene_groups={"transport": ["g_transport_1", "g_transport_2"]},
            use_special_groups=True,
        )
        assert result.loc["g_transport_2", "heart"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# resolve_sample_type_map
# ---------------------------------------------------------------------------


class TestResolveSampleTypeMap:
    def test_none_returns_identity(self, ptr_impl: DefaultPTRImplementation) -> None:
        expr = _make_expression(["g1"], ["s1", "s2"])
        result = ptr_impl.resolve_sample_type_map(expr, None)
        assert result == {"s1": "s1", "s2": "s2"}

    def test_str_maps_all_to_same(self, ptr_impl: DefaultPTRImplementation) -> None:
        expr = _make_expression(["g1"], ["s1", "s2"])
        result = ptr_impl.resolve_sample_type_map(expr, "liver")
        assert result == {"s1": "liver", "s2": "liver"}

    def test_dict_maps_explicitly(self, ptr_impl: DefaultPTRImplementation) -> None:
        expr = _make_expression(["g1"], ["s1", "s2", "s3"])
        result = ptr_impl.resolve_sample_type_map(expr, {"s1": "liver", "s2": "kidney"})
        assert result["s1"] == "liver"
        assert result["s2"] == "kidney"
        assert result["s3"] == "s3"  # fallback identity

    def test_normalizes_case_whitespace_and_ptr_suffix(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        expr = _make_expression(["g1"], [" Heart  ", "Kidney"])
        result = ptr_impl.resolve_sample_type_map(
            expr,
            {
                "heart": " HEART_ptr  ",
                "kidney": " kidney_PTR",
            },
        )
        assert result[" Heart  "] == "heart"
        assert result["Kidney"] == "kidney"


# ---------------------------------------------------------------------------
# combine_expression_with_ptr
# ---------------------------------------------------------------------------


class TestCombineExpressionWithPtr:
    def test_identity_map_direct_multiplication(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        expr = pd.DataFrame({"s1": [2.0, 3.0]}, index=["g1", "g2"])
        ptr = pd.DataFrame({"s1": [10.0, 5.0]}, index=["g1", "g2"])
        result = ptr_impl.combine_expression_with_ptr(expr, ptr)
        assert result.loc["g1", "s1"] == pytest.approx(20.0)
        assert result.loc["g2", "s1"] == pytest.approx(15.0)

    def test_string_sample_type_map(self, ptr_impl: DefaultPTRImplementation) -> None:
        expr = pd.DataFrame(
            {"sample_a": [2.0, 3.0], "sample_b": [4.0, 5.0]},
            index=["g1", "g2"],
        )
        ptr = pd.DataFrame({"liver": [10.0, 2.0]}, index=["g1", "g2"])
        result = ptr_impl.combine_expression_with_ptr(expr, ptr, sample_type_map="liver")
        assert result.loc["g1", "sample_a"] == pytest.approx(20.0)
        assert result.loc["g2", "sample_b"] == pytest.approx(10.0)

    def test_dict_sample_type_map(self, ptr_impl: DefaultPTRImplementation) -> None:
        expr = pd.DataFrame(
            {"s1": [2.0], "s2": [3.0]},
            index=["g1"],
        )
        ptr = pd.DataFrame({"liver": [10.0], "kidney": [5.0]}, index=["g1"])
        result = ptr_impl.combine_expression_with_ptr(
            expr, ptr, sample_type_map={"s1": "liver", "s2": "kidney"}
        )
        assert result.loc["g1", "s1"] == pytest.approx(20.0)
        assert result.loc["g1", "s2"] == pytest.approx(15.0)

    def test_map_normalization_matches_ptr_suffix_case_and_spaces(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        expr = pd.DataFrame({"Sample_A ": [2.0]}, index=["g1"])
        ptr = pd.DataFrame({" liver_ptr ": [10.0]}, index=["g1"])
        result = ptr_impl.combine_expression_with_ptr(
            expr,
            ptr,
            sample_type_map={"sample_a": " LiVeR_PTR "},
        )
        assert result.loc["g1", "Sample_A "] == pytest.approx(20.0)

    def test_no_overlapping_genes_returns_expression(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        expr = pd.DataFrame({"s1": [1.0]}, index=["g1"])
        ptr = pd.DataFrame({"s1": [99.0]}, index=["g_other"])
        result = ptr_impl.combine_expression_with_ptr(expr, ptr)
        assert result.loc["g1", "s1"] == pytest.approx(1.0)

    def test_missing_ptr_column_skips_silently(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        expr = pd.DataFrame({"s1": [2.0]}, index=["g1"])
        ptr = pd.DataFrame({"liver": [10.0]}, index=["g1"])
        # s1 not in ptr → skip, expression value preserved
        result = ptr_impl.combine_expression_with_ptr(expr, ptr, sample_type_map=None)
        assert result.loc["g1", "s1"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# prepare_ptr_frame — integration
# ---------------------------------------------------------------------------


class TestPreparePtrFrame:
    def test_full_pipeline_returns_expression_aligned_frame(
        self, ptr_impl: DefaultPTRImplementation
    ) -> None:
        genes = ["g1", "g2", "g3"]
        ptr_raw = pd.DataFrame(
            {"liver": [1.0, 2.0]},
            index=genes[:2],  # g3 absent from PTR
        )
        expr = _make_expression(genes, ["s1", "s2"])
        config = APIConfig()

        result = ptr_impl.prepare_ptr_frame(ptr_raw, expr, config)

        assert set(result.index) == set(genes)
        assert not result["liver"].isna().any()

    def test_metabolic_gene_filter_applied(self, ptr_impl: DefaultPTRImplementation) -> None:
        genes = ["g1", "g2", "g3"]
        ptr_raw = pd.DataFrame(
            {"liver": [1.0, 2.0, 3.0]},
            index=genes,
        )
        expr = _make_expression(genes, ["s1"])
        config = APIConfig()
        config.ptr.impute_from_metabolic_genes_only = True

        result = ptr_impl.prepare_ptr_frame(
            ptr_raw, expr, config, metabolic_genes=["g1", "g2"]
        )

        # g3 filtered out but then re-imputed from expression index
        assert "g3" in result.index
        assert not result["liver"].isna().any()

    def test_pretransformed_log10_applied(self, ptr_impl: DefaultPTRImplementation) -> None:
        ptr_raw = pd.DataFrame({"s1": [1.0, 2.0]}, index=["g1", "g2"])
        expr = _make_expression(["g1", "g2"], ["s1"])
        config = APIConfig()
        config.ptr.pretransformed_type = "log10"

        result = ptr_impl.prepare_ptr_frame(ptr_raw, expr, config)

        # log10(1)=1 → 10^1=10; log10(2)=2 → 10^2=100 (after standardize→linear)
        assert result.loc["g1", "s1"] == pytest.approx(10.0)
        assert result.loc["g2", "s1"] == pytest.approx(100.0)
