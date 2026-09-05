from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from VmaxBuilder.utils.plotting.config import PlotConfig
from VmaxBuilder.utils.plotting.wrappers import create_dual_axis_bar_plot

# TODO diagnostics roadmap (trimming-threshold sensitivity):
# 1) Plot distribution of percentile pairs after flat-threshold addition
#    (x = adjusted m-value / percentile-pair score, y = density) with a vertical
#    red line at active trimmability threshold.
# 2) Repeat histogram for threshold multipliers: 0.2x, 0.5x, 1.0x, 2.0x, 4.0x,
#    so users can see inclusion-shift across strict/relaxed settings.
# 3) Add threshold sweep curve:
#    x = threshold multiplier, y = number (and fraction) of trimmable genes/
#    trimmable IFP events retained.
# 4) Add percentile-point sweep:
#    x = selected percentile point in trimming assessment, y = included value
#    count (or fraction) at fixed flat-threshold addition.
# 5) Add 2D sensitivity heatmap:
#    x = percentile point, y = threshold multiplier, z = retained trimmable
#    values/events.
# 6) Add before/after trim candidate diagnostics:
#    report how many candidate values are near threshold (e.g., +/-5%) to
#    highlight unstable decision regions.
# 7) Add sample-stratified versions of the above to show whether a small subset
#    of samples drives most threshold sensitivity.


def _trimmed_ifps_per_sample(
    trimming_output: Mapping[str, Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Generated: validation needed.

    Description:
        Build sample-to-trimmed-IFP mapping from trimming output.

    Args:
        trimming_output (dict[str, dict[str, Any]]): Per-IFP trimming payload.

    Returns:
        dict[str, set[str]]: Sample to set of trimmed IFPs.
    """
    per_sample_mapping: dict[str, set[str]] = {}
    for ifp_identifier, ifp_data in trimming_output.items():
        genes_trimmed_per_sample = ifp_data.get("genes_trimmed_per_sample", {})
        for sample_name, trimmed_genes in genes_trimmed_per_sample.items():
            if not trimmed_genes:
                continue
            per_sample_mapping.setdefault(str(sample_name), set()).add(str(ifp_identifier))
    return per_sample_mapping


def _samples_per_trimmed_ifp(
    trimming_output: Mapping[str, Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Generated: validation needed.

    Description:
        Build IFP-to-samples mapping for non-empty trimming events.

    Args:
        trimming_output (dict[str, dict[str, Any]]): Per-IFP trimming payload.

    Returns:
        dict[str, set[str]]: IFP to set of samples where trimming occurred.
    """
    per_ifp_mapping: dict[str, set[str]] = {}
    for ifp_identifier, ifp_data in trimming_output.items():
        genes_trimmed_per_sample = ifp_data.get("genes_trimmed_per_sample", {})
        for sample_name, trimmed_genes in genes_trimmed_per_sample.items():
            if not trimmed_genes:
                continue
            per_ifp_mapping.setdefault(str(ifp_identifier), set()).add(str(sample_name))
    return per_ifp_mapping


def create_trimming_summary_plots(
    trimming_output: Mapping[str, Mapping[str, Any]],
    *,
    plot_config: PlotConfig | None = None,
    top_n: int = 30,
) -> dict[str, go.Figure]:
    """Generated: validation needed.

    Description:
        Create trimming summary plots covering sample-level and IFP-level event counts.

    Args:
        trimming_output (dict[str, dict[str, Any]]): Per-IFP trimming payload.
        plot_config (PlotConfig | None): Plot configuration.
        top_n (int): Maximum number of categories in ranked bars.

    Returns:
        dict[str, go.Figure]: Named plot collection.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    ifps_per_sample = _trimmed_ifps_per_sample(trimming_output)
    samples_per_ifp = _samples_per_trimmed_ifp(trimming_output)

    ifp_counts_per_sample = {
        sample_name: len(trimmed_ifps)
        for sample_name, trimmed_ifps in ifps_per_sample.items()
    }
    sample_counts_per_ifp = {
        ifp_identifier: len(samples) for ifp_identifier, samples in samples_per_ifp.items()
    }

    ranked_sample_counts = sorted(
        ifp_counts_per_sample.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:top_n]
    ranked_ifp_counts = sorted(
        sample_counts_per_ifp.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:top_n]

    samples_histogram = go.Figure(
        data=[
            go.Bar(
                x=[label for label, _ in ranked_sample_counts],
                y=[count for _, count in ranked_sample_counts],
                name="Trimmed IFP count",
            )
        ]
    )
    samples_histogram.update_layout(
        title="Trimmed IFP count per sample",
        xaxis_title="Sample",
        yaxis_title="Trimmed IFPs",
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
    )

    ifp_histogram = go.Figure(
        data=[
            go.Bar(
                x=[label for label, _ in ranked_ifp_counts],
                y=[count for _, count in ranked_ifp_counts],
                name="Sample count",
            )
        ]
    )
    ifp_histogram.update_layout(
        title="Samples trimmed per IFP",
        xaxis_title="IFP",
        yaxis_title="Samples with trimming",
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
    )

    total_samples = set()
    for ifp_data in trimming_output.values():
        genes_trimmed_per_sample = ifp_data.get("genes_trimmed_per_sample", {})
        total_samples.update(genes_trimmed_per_sample.keys())
    total_sample_count = max(len(total_samples), 1)

    ranked_ifp_fraction_df = pd.DataFrame(
        {
            "ifp": [ifp_identifier for ifp_identifier, _ in ranked_ifp_counts],
            "sample_count": [count for _, count in ranked_ifp_counts],
        }
    )
    ranked_ifp_fraction_df["sample_fraction"] = ranked_ifp_fraction_df[
        "sample_count"
    ] / float(total_sample_count)

    ifp_dual_axis_plot = create_dual_axis_bar_plot(
        labels=ranked_ifp_fraction_df["ifp"].tolist(),
        left_values=ranked_ifp_fraction_df["sample_count"].astype(float).tolist(),
        right_values=ranked_ifp_fraction_df["sample_fraction"].astype(float).tolist(),
        left_name="Trimmed sample count",
        right_name="Trimmed sample fraction",
        plot_config=PlotConfig(
            title="Top trimmed IFPs: absolute and relative sample coverage",
            x_label="IFP",
            y_label="Samples",
            width=max(plot_config.width, 1200),
            height=plot_config.height,
        ),
    )

    similarity_heatmap = _create_sample_ifp_jaccard_heatmap(
        ifps_per_sample,
        plot_config=plot_config,
    )

    return {
        "trimmed_ifp_count_per_sample": samples_histogram,
        "sample_count_per_trimmed_ifp": ifp_histogram,
        "trimmed_ifp_sample_coverage": ifp_dual_axis_plot,
        "sample_ifp_jaccard_similarity": similarity_heatmap,
    }


def _create_sample_ifp_jaccard_heatmap(
    ifps_per_sample: dict[str, set[str]],
    *,
    plot_config: PlotConfig,
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Create pairwise Jaccard similarity heatmap between sample-specific trimmed IFP sets.

    Args:
        ifps_per_sample (dict[str, set[str]]): Sample to trimmed IFP set mapping.
        plot_config (PlotConfig): Plot configuration.

    Returns:
        go.Figure: Jaccard similarity heatmap.
    """
    sample_names = sorted(ifps_per_sample.keys())
    if not sample_names:
        sample_names = ["no_samples"]
        similarity_matrix = np.array([[1.0]])
    else:
        similarity_matrix = np.zeros((len(sample_names), len(sample_names)), dtype=float)
        for row_index, sample_row in enumerate(sample_names):
            row_ifps = ifps_per_sample[sample_row]
            for column_index, sample_column in enumerate(sample_names):
                column_ifps = ifps_per_sample[sample_column]
                union_size = len(row_ifps.union(column_ifps))
                if union_size == 0:
                    similarity_matrix[row_index, column_index] = 1.0
                else:
                    similarity_matrix[row_index, column_index] = len(
                        row_ifps.intersection(column_ifps)
                    ) / float(union_size)

    heatmap_figure = go.Figure(
        data=go.Heatmap(
            z=similarity_matrix,
            x=sample_names,
            y=sample_names,
            colorscale="Viridis",
            zmin=0.0,
            zmax=1.0,
            colorbar={"title": "Jaccard"},
        )
    )
    heatmap_figure.update_layout(
        title="Sample similarity of trimmed IFP sets",
        xaxis_title="Sample",
        yaxis_title="Sample",
        template="plotly_white",
        width=max(plot_config.width, 900),
        height=max(plot_config.height, 850),
    )
    return heatmap_figure


if __name__ == "__main__":
    base_dir = Path(
        "/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    )
    trimming_output_path = (
        base_dir / "artifacts" / "allocation_stage" / "trimming_output.json"
    )

    with open(trimming_output_path, "r") as output_file:
        trimming_output_data = json.load(output_file)

    plots = create_trimming_summary_plots(
        trimming_output_data,
        plot_config=PlotConfig(width=1200, height=700),
        top_n=25,
    )
    for figure in plots.values():
        figure.show()
