"""
Transformation utilities for converting dataframes between log and linear spaces.

Supports ``linear``, ``log10``, ``log2``, and ``ln`` transformations.
"""

import numpy as np
import pandas as pd
from cobra.io.json import load_json_model


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
    if pretransformed_type == "ln" or pretransformed_type == "log":
        return pd.Series(np.exp(series), index=series.index)
    if pretransformed_type == "sqrt":
        return pd.Series(series**2, index=series.index)
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
    if target_transformation == "ln" or target_transformation == "log":
        return pd.Series(np.log(series), index=series.index)
    if target_transformation == "sqrt":
        return pd.Series(np.sqrt(series), index=series.index)
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
    df = df.copy()
    df = df.replace({pd.NA: np.nan})
    _validate_transformation_type(pretransformed_type, field_name="pretransformed_type")
    _validate_transformation_type(target_transformation, field_name="target_transformation")
    data_cols = df.columns
    df[data_cols] = df[data_cols].apply(lambda x: pd.to_numeric(x, errors="coerce"))
    df[data_cols] = df[data_cols].infer_objects(copy=False).astype(float)
    df[data_cols] = df[data_cols].apply(
        lambda series: _apply_target_transformation(
            _apply_forward_transformation(series, pretransformed_type),
            target_transformation,
        )
    )

    return df


def calculate_conversion_factor_per_sample_from_metabolic_protein_abundance(
    metabolic_protein_abundance_df: pd.DataFrame,
    all_protein_abundance_df: pd.DataFrame | None = None,
    AVERAGE_HUMAN_PROTEIN_MOLECULAR_WEIGHT: float = 5 * 1e4,
    PROTEOME_FRACTION_OF_TOTAL_DRY_WEIGHT: float = 0.5,
    DEFAULT_HEURISTIC_FRACTION: float = 0.5,
    MAX_HEURISTIC_FRACTION: float = 0.9,
) -> pd.Series:
    """Calculate per-sample reaction activity conversion factors.

    The input protein abundance is assumed to contain metabolic proteins only.
    If the full protein abundance is available, the fraction of the proteome
    represented by the metabolic proteins is calculated per sample.

    If the calculated metabolic-protein fraction is >= MAX_HEURISTIC_FRACTION,
    the DEFAULT_HEURISTIC_FRACTION is used instead.

    The resulting conversion factor can be multiplied directly by reaction
    activities to convert them to mmol/gDW/hour.
    """

    if not isinstance(metabolic_protein_abundance_df, pd.DataFrame):
        raise ValueError("metabolic_protein_abundance_df must be a pandas DataFrame.")

    metabolic_protein_abundance_df = metabolic_protein_abundance_df.apply(
        pd.to_numeric, errors="coerce"
    )

    metabolic_total = metabolic_protein_abundance_df.sum(axis=0)

    if metabolic_total.isna().any() or (metabolic_total <= 0).any():
        raise ValueError(
            "All metabolic protein abundance totals must be numeric and strictly positive."
        )

    # Determine what fraction of the total proteome is represented by
    # the metabolic proteins.
    if all_protein_abundance_df is not None:
        if not isinstance(all_protein_abundance_df, pd.DataFrame):
            raise ValueError("all_protein_abundance_df must be a pandas DataFrame.")

        all_protein_abundance_df = all_protein_abundance_df.apply(
            pd.to_numeric, errors="coerce"
        )

        total_protein = all_protein_abundance_df.sum(axis=0)

        if total_protein.isna().any() or (total_protein <= 0).any():
            raise ValueError(
                "All total protein abundance totals must be numeric and strictly positive."
            )

        heuristic_fraction_per_sample = metabolic_total / total_protein

        # If the calculated fraction is implausibly high, assume that
        # the provided total proteome is itself effectively metabolic-only.
        heuristic_fraction_per_sample = heuristic_fraction_per_sample.where(
            heuristic_fraction_per_sample < MAX_HEURISTIC_FRACTION,
            DEFAULT_HEURISTIC_FRACTION,
        )

    else:
        # No full proteome is available, so use the default assumption.
        heuristic_fraction_per_sample = pd.Series(
            DEFAULT_HEURISTIC_FRACTION,
            index=metabolic_total.index,
        )

    if (heuristic_fraction_per_sample <= 0).any():
        raise ValueError("Heuristic fractions must be > 0.")

    # Estimate the total protein abundance from the metabolic-only abundance.
    estimated_total_protein_abundance = metabolic_total / heuristic_fraction_per_sample

    # Convert protein mass fraction to mmol protein/gDW.
    scaling_factor_mmol_per_gDW = (
        PROTEOME_FRACTION_OF_TOTAL_DRY_WEIGHT * 1e3
    ) / AVERAGE_HUMAN_PROTEIN_MOLECULAR_WEIGHT

    # Convert the arbitrary reaction activity scale to mmol/gDW/hour.
    conversion_factor_per_sample = (
        scaling_factor_mmol_per_gDW / estimated_total_protein_abundance
    ) * 3600

    conversion_factor_per_sample.name = "conversion_factor_mmol_per_gDW_hour"

    return conversion_factor_per_sample


if __name__ == "__main__":
    from pathlib import Path

    base_dir = Path(
        r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    )
    model_path = base_dir / "outputs" / "adjusted_irreversible_cobra_model.json"
    protein_artifacts = base_dir / "artifacts" / "protein_stage"
    all_genes_protein_abundance_df = pd.read_csv(
        protein_artifacts / "all_genes_protein_abundance_df.csv", index_col=0
    )
    cobra_model = load_json_model(str(model_path))
    metabolic_genes = {g.id for g in cobra_model.genes}
    metabolic_only_protein_abundance_df = all_genes_protein_abundance_df.loc[
        all_genes_protein_abundance_df.index.isin(metabolic_genes)
    ]

    transformation_factor_per_sample = (
        calculate_conversion_factor_per_sample_from_metabolic_protein_abundance(
            metabolic_only_protein_abundance_df,
            all_protein_abundance_df=all_genes_protein_abundance_df,
        )
    )
    reaction_activity_path = base_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"

    reaction_activity_df = pd.read_csv(reaction_activity_path, index_col=0)
    transformed_reaction_activity_df = reaction_activity_df * transformation_factor_per_sample
    # remove 0 values
    # remove duplicates
    # remove NaN values
    transformed_reaction_activity_df = transformed_reaction_activity_df.replace(0, np.nan)
    transformed_reaction_activity_df = transformed_reaction_activity_df.drop_duplicates()
    transformed_reaction_activity_df = transformed_reaction_activity_df.dropna()
    # trnasform to log10 space
    # transformed_reaction_activity_df = transform_dataframe(
    #     transformed_reaction_activity_df,
    #     pretransformed_type="linear",
    #     target_transformation="log10",
    # )

    # make for the first 5 an overlaid histogram plot for the transformed reaction activities
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import gaussian_kde

    plt.figure(figsize=(10, 6))

    for sample in transformed_reaction_activity_df.columns[:5]:
        values = transformed_reaction_activity_df[sample].dropna()
        values = values[values > 0]

        log_values = np.log10(values)

        # Histogram
        plt.hist(
            log_values,
            bins=100,
            alpha=0.4,
            label=sample,
            density=True,
        )

        # KDE smoothing
        kde = gaussian_kde(log_values)
        x = np.linspace(log_values.min(), log_values.max(), 500)
        y = kde(x)

        plt.plot(
            x,
            y,
            linewidth=2,
            label=f"{sample} KDE",
        )

    plt.xlabel("Reaction activity (log10 mmol/gDW/hour)")
    plt.ylabel("Density")
    plt.title("Distribution of transformed reaction activities")
    plt.legend()
    plt.tight_layout()
    plt.show()

    # same but then as cumulative distribution function (CDF) plot

    plt.figure(figsize=(10, 6))

    for sample in transformed_reaction_activity_df.columns[:5]:
        values = transformed_reaction_activity_df[sample].dropna()
        values = values[values > 0]

        log_values = np.log10(values)

        # CDF
        sorted_values = np.sort(log_values)
        cdf = np.arange(1, len(sorted_values) + 1) / len(sorted_values)

        plt.plot(
            sorted_values,
            cdf,
            linewidth=2,
            label=sample,
        )

    plt.xlabel("Reaction activity (log10 mmol/gDW/hour)")
    plt.ylabel("Cumulative distribution function (CDF)")
    plt.title("Cumulative distribution of transformed reaction activities")
    plt.legend()
    plt.tight_layout()
    plt.show()
