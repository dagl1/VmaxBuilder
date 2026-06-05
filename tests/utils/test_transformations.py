"""Tests for VmaxBuilder.utils.transformations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from VmaxBuilder.utils.transformations import (
    _apply_forward_transformation,
    _apply_target_transformation,
    _resolve_data_columns,
    _validate_transformation_type,
    transform_dataframe,
)

# ---------------------------------------------------------------------------
# _validate_transformation_type
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_transformation_type_raises_on_unsupported_label() -> None:
    with pytest.raises(ValueError, match="Invalid pretransformed_type"):
        _validate_transformation_type("log100", field_name="pretransformed_type")


@pytest.mark.unit
def test_validate_transformation_type_accepts_all_valid_labels() -> None:
    for label in ("linear", "log10", "log2", "ln"):
        _validate_transformation_type(label, field_name="pretransformed_type")


# ---------------------------------------------------------------------------
# _resolve_data_columns
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_data_columns_all_numeric_returns_all_columns() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    cols = _resolve_data_columns(df)
    assert list(cols) == ["a", "b"]


@pytest.mark.unit
def test_resolve_data_columns_skips_non_numeric_first_column() -> None:
    df = pd.DataFrame({"id": ["x", "y"], "val": [1.0, 2.0]})
    cols = _resolve_data_columns(df)
    assert list(cols) == ["val"]


@pytest.mark.unit
def test_resolve_data_columns_raises_when_multiple_non_numeric_columns() -> None:
    df = pd.DataFrame({"id": ["x", "y"], "name": ["a", "b"], "val": [1.0, 2.0]})
    with pytest.raises(ValueError, match="numeric"):
        _resolve_data_columns(df)


# ---------------------------------------------------------------------------
# _apply_forward_transformation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_forward_transformation_log10_reversal() -> None:
    series = pd.Series([1.0, 2.0, 3.0])
    result = _apply_forward_transformation(series, "log10")
    expected = pd.Series([10.0, 100.0, 1000.0])
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected)


@pytest.mark.unit
def test_apply_forward_transformation_linear_passthrough() -> None:
    series = pd.Series([1.0, 2.0])
    result = _apply_forward_transformation(series, "linear")
    pd.testing.assert_series_equal(result, series)


@pytest.mark.unit
def test_apply_forward_transformation_log2_reversal() -> None:
    series = pd.Series([1.0, 2.0])
    result = _apply_forward_transformation(series, "log2")
    expected = pd.Series([2.0, 4.0])
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected)


@pytest.mark.unit
def test_apply_forward_transformation_ln_reversal() -> None:
    series = pd.Series([1.0])
    result = _apply_forward_transformation(series, "ln")
    assert pytest.approx(result.iloc[0], rel=1e-6) == np.e


# ---------------------------------------------------------------------------
# _apply_target_transformation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_target_transformation_log10() -> None:
    series = pd.Series([100.0, 1000.0])
    result = _apply_target_transformation(series, "log10")
    expected = pd.Series([2.0, 3.0])
    pd.testing.assert_series_equal(result.reset_index(drop=True), expected)


@pytest.mark.unit
def test_apply_target_transformation_linear_passthrough() -> None:
    series = pd.Series([5.0, 10.0])
    result = _apply_target_transformation(series, "linear")
    pd.testing.assert_series_equal(result, series)


# ---------------------------------------------------------------------------
# transform_dataframe (public API)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_transform_dataframe_identity_linear_to_linear() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    result = transform_dataframe(
        df, pretransformed_type="linear", target_transformation="linear"
    )
    pd.testing.assert_frame_equal(result, df)


@pytest.mark.unit
def test_transform_dataframe_log10_to_linear() -> None:
    df = pd.DataFrame({"val": [1.0, 2.0]})
    result = transform_dataframe(
        df, pretransformed_type="log10", target_transformation="linear"
    )
    expected = pd.DataFrame({"val": [10.0, 100.0]})
    pd.testing.assert_frame_equal(result, expected)


@pytest.mark.unit
def test_transform_dataframe_linear_to_log10() -> None:
    df = pd.DataFrame({"val": [10.0, 100.0]})
    result = transform_dataframe(
        df, pretransformed_type="linear", target_transformation="log10"
    )
    expected = pd.DataFrame({"val": [1.0, 2.0]})
    pd.testing.assert_frame_equal(result, expected)


@pytest.mark.unit
def test_transform_dataframe_log10_roundtrip() -> None:
    original = pd.DataFrame({"val": [1.0, 2.0, 3.0]})
    log_space = transform_dataframe(
        original, pretransformed_type="linear", target_transformation="log10"
    )
    recovered = transform_dataframe(
        log_space, pretransformed_type="log10", target_transformation="linear"
    )
    pd.testing.assert_frame_equal(recovered, original, check_exact=False, rtol=1e-9)


@pytest.mark.unit
def test_transform_dataframe_raises_on_invalid_pretransformed_type() -> None:
    df = pd.DataFrame({"val": [1.0]})
    with pytest.raises(ValueError, match="Invalid pretransformed_type"):
        transform_dataframe(df, pretransformed_type="bad", target_transformation="linear")


@pytest.mark.unit
def test_transform_dataframe_raises_on_invalid_target_transformation() -> None:
    df = pd.DataFrame({"val": [1.0]})
    with pytest.raises(ValueError, match="Invalid target_transformation"):
        transform_dataframe(df, pretransformed_type="linear", target_transformation="bad")


@pytest.mark.unit
def test_transform_dataframe_does_not_mutate_original() -> None:
    df = pd.DataFrame({"val": [10.0, 100.0]})
    original_values = df["val"].tolist()
    transform_dataframe(df, pretransformed_type="linear", target_transformation="log10")
    assert df["val"].tolist() == original_values


@pytest.mark.unit
def test_transform_dataframe_with_non_numeric_first_column() -> None:
    df = pd.DataFrame({"id": ["gene_a", "gene_b"], "expr": [10.0, 100.0]})
    result = transform_dataframe(
        df, pretransformed_type="linear", target_transformation="log10"
    )
    assert result["expr"].tolist() == pytest.approx([1.0, 2.0])
