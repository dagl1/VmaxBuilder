"""
Transformation utilities for converting dataframes between log and linear spaces.

Supports ``linear``, ``log10``, ``log2``, and ``ln`` transformations.
"""

import numpy as np
import pandas as pd


def _validate_transformation_type(transformation_type: str, *, field_name: str) -> None:
    """Generated: validation needed.

    Description:
        Validate supported transformation label.

    Args:
        transformation_type (str): Requested transformation label.
        field_name (str): Label used in error message.

    Raises:
        ValueError: When transformation label is unsupported.
    """

    valid_types = {"linear", "log10", "log2", "ln"}
    if transformation_type not in valid_types:
        raise ValueError(
            f"Invalid {field_name}: {transformation_type}. Must be one of {valid_types}."
        )


def _resolve_data_columns(df: pd.DataFrame) -> pd.Index:
    """Generated: validation needed.

    Description:
        Resolve numeric data columns and allow optional leading identifier column.

    Args:
        df (pd.DataFrame): Input dataframe.

    Returns:
        pd.Index: Columns eligible for transformation.

    Raises:
        ValueError: When more than first column is non-numeric.
    """

    if all(pd.api.types.is_numeric_dtype(df[column]) for column in df.columns):
        return df.columns
    if all(pd.api.types.is_numeric_dtype(df[column]) for column in df.columns[1:]):
        return df.columns[1:]
    raise ValueError("All columns must be numeric except possibly first column (ID column).")


def _apply_forward_transformation(
    series: pd.Series,
    pretransformed_type: str,
) -> pd.Series:
    """Generated: validation needed.

    Description:
        Apply forward transformation from source space to linear space.

    Args:
        series (pd.Series): Column values.
        pretransformed_type (str): Source transformation label.

    Returns:
        pd.Series: Transformed values.
    """

    if pretransformed_type == "log10":
        return pd.Series(10**series, index=series.index)
    if pretransformed_type == "log2":
        return pd.Series(2**series, index=series.index)
    if pretransformed_type == "ln":
        return pd.Series(np.exp(series), index=series.index)
    return series


def _apply_target_transformation(series: pd.Series, target_transformation: str) -> pd.Series:
    """Generated: validation needed.

    Description:
        Apply target transformation from linear space.

    Args:
        series (pd.Series): Column values.
        target_transformation (str): Target transformation label.

    Returns:
        pd.Series: Transformed values.
    """

    if target_transformation == "log10":
        return pd.Series(np.log10(series), index=series.index)
    if target_transformation == "log2":
        return pd.Series(np.log2(series), index=series.index)
    if target_transformation == "ln":
        return pd.Series(np.log(series), index=series.index)
    return series


def transform_dataframe(
    df: pd.DataFrame,
    pretransformed_type: str = "linear",
    target_transformation: str = "linear",
) -> pd.DataFrame:
    """Generated: validation needed.

    Description:
    Converts a dataframe to a different transformation state.
    For example, from log10 space to linear space.

    Args:
        df (pd.DataFrame): table in log or linear space.
        pretransformed_type (str): Log base applied to raw input.  One of
            ``linear``, ``log10``, ``log2``, ``ln``.
        target_transformation (str): Log base to apply to output.  One of
            ``linear``, ``log10``, ``log2``, ``ln``.

    Returns:
        pd.DataFrame: table in target space.

    Raises:
        ValueError: When ``pretransformed_type`` is unrecognised.
    """
    df = df.copy().replace({pd.NA: np.nan})
    _validate_transformation_type(pretransformed_type, field_name="pretransformed_type")
    _validate_transformation_type(target_transformation, field_name="target_transformation")
    data_cols = _resolve_data_columns(df)
    df[data_cols] = df[data_cols].infer_objects(copy=False).astype(float)
    df[data_cols] = df[data_cols].apply(
        lambda series: _apply_target_transformation(
            _apply_forward_transformation(series, pretransformed_type),
            target_transformation,
        )
    )

    return df
