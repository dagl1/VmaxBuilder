from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.utils.plotting.config import PlotConfig
from VmaxBuilder.utils.plotting.wrappers import (
    create_difference_boxplot,
    create_dual_axis_bar_plot,
    create_overlaid_cdf,
    create_overlaid_histogram,
    create_rank_scatter_plot,
    create_scatter_comparison_plot,
    match_two_samples,
)

# model_path = base_dir / "outputs" / "adjusted_irreversible_cobra_model.json"
# protein_artifacts = base_dir / "artifacts" / "protein_stage"
# all_genes_protein_abundance_df = pd.read_csv(
#     protein_artifacts / "all_genes_protein_abundance_df.csv", index_col=0
# )
# cobra_model = load_json_model(str(model_path))
# metabolic_genes = {g.id for g in cobra_model.genes}
# metabolic_only_protein_abundance_df = all_genes_protein_abundance_df.loc[
#     all_genes_protein_abundance_df.index.isin(metabolic_genes)
# ]
#
# transformation_factor_per_sample = (
#     calculate_conversion_factor_per_sample_from_metabolic_protein_abundance(
#         metabolic_only_protein_abundance_df,
#         all_protein_abundance_df=all_genes_protein_abundance_df,
#     )
# )
# reaction_activity_path = base_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"

# todo:
# we want to be able to do the following plots;
# so we need to generate this data:
##### gene-substrate predictions
##### main-substrate predictions
##### IFP-dominant kcat prediction
##### IFP-allocation
##### reaction-summed allocation
##### reaction-summed vmax
##### reaction contribution per IFP (for both kcat and allocation)

# todo:
# calculate the correlation between the correlations of Kcat and abundance to Vmax
# do the same for abundance contribution vs vmax contribution to total vmax
# plot how the kcat predictions look in IFPs that make up the majority of a total Vmax
# For 3 way correlation, we  can use VIF
#

# todo:
# categorise reactions into buckets depending on how their IFP contributions differ.
# Then per bucket, show the average contribution of the nth highest contributors

# todo:
# plot at each level what happens if we would substitute abundance or kcat with
# a static value


class VmaxDiagnostics(BaseImplementationDiagnostics):
    """Generated: validation needed.

    Description:
        Create Vmax-stage comparison diagnostics plots between trimmed and
        untrimmed reaction-capacity outputs.
    """

    DIAGNOSTICS_NAME = "Vmax"
    MAX_SAMPLES_FOR_PLOTS = 5

    def __init__(self, full_config: FullConfig):
        """Generated: validation needed.

        Description:
            Initialise Vmax diagnostics state and logger.

        Args:
            full_config (FullConfig): Full pipeline configuration.

        Modifies:
            Base diagnostics logger state.
        """
        super().__init__(full_config)

    def before_run(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Return empty diagnostics payload for before-run hook.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Empty before-run diagnostics payload.
        """
        return {"outputs": {}, "diagnostics": {}, "metadata": {}, "artifacts": {}}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build Vmax diagnostics plots when trimmed and untrimmed outputs exist.

        Args:
            scaffold_objects (dict[str, dict[str, Any]]): Stage output payload.
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Diagnostics payload with generated figures
                and comparison table.
        """
        trimmed_reaction_capacity_df = cast(
            pd.DataFrame | None,
            scaffold.get_scaffold_value("non_imputed_reaction_capacity_df"),
        )
        untrimmed_reaction_capacity_df = cast(
            pd.DataFrame | None,
            scaffold.get_scaffold_value("reaction_capacity_df_without_trimming"),
        )

        if trimmed_reaction_capacity_df is None:
            self.logger.warning(
                "Skipping Vmax diagnostics: 'non_imputed_reaction_capacity_df' missing."
            )
            return {
                "outputs": {},
                "diagnostics": {"Vmax": []},
                "metadata": {},
                "artifacts": {},
            }

        if untrimmed_reaction_capacity_df is None:
            self.logger.warning(
                "Skipping Vmax comparison diagnostics: "
                "'reaction_capacity_df_without_trimming' missing."
            )
            return {
                "outputs": {},
                "diagnostics": {"Vmax": []},
                "metadata": {},
                "artifacts": {},
            }

        diagnostics_output: list[DiagnosticOutputSpec] = []
        for (
            trimmed_series,
            untrimmed_series,
            sample_name,
        ) in self._iter_trimmed_untrimmed_pairs(
            trimmed_reaction_capacity_df,
            untrimmed_reaction_capacity_df,
            max_samples=self.MAX_SAMPLES_FOR_PLOTS,
        ):
            sample_slug = self._slugify(sample_name)
            one_to_one_plots = self._one_to_one_comparison_plots(
                trimmed_series,
                untrimmed_series,
                sample_name,
            )
            distribution_plots = self.plot_overlaid_histograms_and_cdfs(
                trimmed_series,
                untrimmed_series,
                sample_name,
            )

            comparison_df = self._compare_two_reaction_activity_dfs(
                trimmed_series,
                untrimmed_series,
            )
            trimming_effect_plot = self._plot_trimming_effects_on_reaction_activity(
                comparison_df,
                title=f"Top trimming-induced shifts ({sample_name})",
                top_n=15,
            )

            diagnostics_output.extend(
                self._prefix_diagnostic_output_file_names(one_to_one_plots, sample_slug)
            )
            diagnostics_output.extend(
                self._prefix_diagnostic_output_file_names(distribution_plots, sample_slug)
            )
            diagnostics_output.extend(
                [
                    DiagnosticOutputSpec(
                        data=trimming_effect_plot,
                        save_file_name=f"{sample_slug}_top_trimming_effects_dual_axis",
                        extensions=[".svg", ".html"],
                        data_type=go.Figure,
                    ),
                    DiagnosticOutputSpec(
                        data=comparison_df,
                        save_file_name=(
                            f"{sample_slug}_trimmed_untrimmed_reaction_comparison"
                        ),
                        extensions=[".csv", ".xlsx"],
                        data_type=pd.DataFrame,
                    ),
                ]
            )

        return {
            "outputs": {},
            "diagnostics": {"Vmax": diagnostics_output},
            "metadata": {},
            "artifacts": {},
        }

    def _iter_trimmed_untrimmed_pairs(
        self,
        trimmed_df: pd.DataFrame,
        untrimmed_df: pd.DataFrame,
        max_samples: int,
    ) -> list[tuple[pd.Series, pd.Series, str]]:
        """Generated: validation needed.

        Description:
            Build per-sample trimmed/untrimmed comparison vectors.

        Args:
            trimmed_df (pd.DataFrame): Trimmed reaction-capacity matrix.
            untrimmed_df (pd.DataFrame): Untrimmed reaction-capacity matrix.
            max_samples (int): Maximum number of shared sample columns to process.

        Returns:
            list[tuple[pd.Series, pd.Series, str]]: List of per-sample pairs.

        Raises:
            ValueError: If no shared sample columns exist.
        """
        common_columns = [
            column for column in trimmed_df.columns if column in untrimmed_df.columns
        ]
        if not common_columns:
            raise ValueError(
                "Cannot create Vmax comparison plots: no shared sample columns found."
            )

        sample_pairs: list[tuple[pd.Series, pd.Series, str]] = []
        for sample_name in common_columns[:max_samples]:
            trimmed_series = self._safe_log10(trimmed_df[sample_name])
            untrimmed_series = self._safe_log10(untrimmed_df[sample_name])
            trimmed_series.name = f"trimmed:{sample_name}"
            untrimmed_series.name = f"untrimmed:{sample_name}"
            sample_pairs.append((trimmed_series, untrimmed_series, str(sample_name)))

        return sample_pairs

    def _prefix_diagnostic_output_file_names(
        self,
        diagnostic_output: list[DiagnosticOutputSpec],
        prefix: str,
    ) -> list[DiagnosticOutputSpec]:
        """Generated: validation needed.

        Description:
            Namespace diagnostic save-file names with sample prefix.

        Args:
            diagnostic_output (list[DiagnosticOutputSpec]): Existing output specs.
            prefix (str): Prefix to add.

        Returns:
            list[DiagnosticOutputSpec]: Namespaced output specs.
        """
        prefixed_specs: list[DiagnosticOutputSpec] = []
        for output_spec in diagnostic_output:
            prefixed_specs.append(
                replace(
                    output_spec,
                    save_file_name=f"{prefix}_{output_spec.save_file_name}",
                )
            )
        return prefixed_specs

    def _slugify(self, value: str) -> str:
        """Generated: validation needed.

        Description:
            Convert text into filesystem-safe lowercase slug.

        Args:
            value (str): Text value.

        Returns:
            str: Slugified text.
        """
        slug = value.strip().lower()
        slug = slug.replace(" ", "_")
        slug = slug.replace("/", "_")
        slug = slug.replace("\\", "_")
        return "".join(
            character for character in slug if character.isalnum() or character == "_"
        )

    def _prepare_trimmed_untrimmed_pair(
        self,
        trimmed_df: pd.DataFrame,
        untrimmed_df: pd.DataFrame,
    ) -> tuple[pd.Series, pd.Series, str]:
        """Generated: validation needed.

        Description:
            Select one shared sample and convert values to comparable log10 vectors.

        Args:
            trimmed_df (pd.DataFrame): Trimmed reaction-capacity matrix.
            untrimmed_df (pd.DataFrame): Untrimmed reaction-capacity matrix.

        Returns:
            tuple[pd.Series, pd.Series, str]: Trimmed series, untrimmed series,
                and sample name.

        Raises:
            ValueError: If no shared sample column exists.
        """
        common_columns = [
            column for column in trimmed_df.columns if column in untrimmed_df.columns
        ]
        if not common_columns:
            raise ValueError(
                "Cannot create Vmax comparison plots: no shared sample columns found."
            )

        selected_sample = str(common_columns[0])

        trimmed_series = self._safe_log10(trimmed_df[selected_sample])
        untrimmed_series = self._safe_log10(untrimmed_df[selected_sample])

        trimmed_series.name = f"trimmed:{selected_sample}"
        untrimmed_series.name = f"untrimmed:{selected_sample}"
        return trimmed_series, untrimmed_series, selected_sample

    def _safe_log10(self, series: pd.Series) -> pd.Series:
        """Generated: validation needed.

        Description:
            Convert strictly positive values to log10 scale and drop invalid values.

        Args:
            series (pd.Series): Numeric series.

        Returns:
            pd.Series: Log10-transformed series with invalid entries removed.
        """
        numeric_series = pd.to_numeric(series, errors="coerce")
        positive_mask = numeric_series > 0
        transformed = pd.Series(np.nan, index=numeric_series.index, dtype=float)
        transformed.loc[positive_mask] = np.log10(numeric_series.loc[positive_mask])
        return transformed.dropna()

    def _one_to_one_comparison_plots(
        self,
        trimmed_series: pd.Series,
        untrimmed_series: pd.Series,
        sample_name: str,
    ) -> list[DiagnosticOutputSpec]:
        """Generated: validation needed.

        Description:
            Build one-to-one trimmed vs untrimmed plots with and without marginals
            and trendlines.

        Args:
            trimmed_series (pd.Series): Trimmed values.
            untrimmed_series (pd.Series): Untrimmed values.
            sample_name (str): Sample identifier.

        Returns:
            list[DiagnosticOutputSpec]: Plot output specs.
        """
        base_config = PlotConfig(
            x_label=f"Trimmed reaction capacity (log10) | {sample_name}",
            y_label=f"Untrimmed reaction capacity (log10) | {sample_name}",
            width=1150,
            height=760,
            point_size=5,
            marker_opacity=0.65,
            histogram_nbinsx=60,
            histogram_nbinsy=60,
            marginal_histogram_nbins=55,
        )

        scatter_no_trendline = create_scatter_comparison_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=replace(base_config, title="Scatter without trendline"),
            with_marginals=False,
            with_trendline=False,
        )

        scatter_linear = create_scatter_comparison_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=replace(base_config, title="Scatter with linear trendline"),
            with_marginals=False,
            with_trendline=True,
            trendline_type="linear",
        )

        scatter_marginal_linear = create_scatter_comparison_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=replace(
                base_config,
                title="Scatter + marginals + linear trendline",
                height=860,
            ),
            with_marginals=True,
            with_trendline=True,
            trendline_type="linear",
        )

        scatter_marginal_poly = create_scatter_comparison_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=replace(
                base_config,
                title="Scatter + marginals + quadratic trendline",
                height=860,
            ),
            with_marginals=True,
            with_trendline=True,
            trendline_type="poly2",
        )

        density_marginal = create_scatter_comparison_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=replace(
                base_config,
                title="Density scatter + marginals",
                height=860,
            ),
            with_marginals=True,
            with_trendline=False,
            use_density=True,
        )

        difference_boxplot = create_difference_boxplot(
            trimmed_series,
            untrimmed_series,
            plot_config=PlotConfig(
                title="Difference boxplot (trimmed - untrimmed)",
                y_label="Difference (log10)",
                width=1000,
                height=700,
            ),
        )

        rank_scatter = create_rank_scatter_plot(
            trimmed_series,
            untrimmed_series,
            plot_config=PlotConfig(
                title="Rank comparison",
                x_label="Rank in trimmed",
                y_label="Rank in untrimmed",
                width=1000,
                height=760,
                point_size=5,
                marker_opacity=0.65,
            ),
        )

        return [
            DiagnosticOutputSpec(
                data=scatter_no_trendline,
                save_file_name="scatter_trimmed_vs_untrimmed",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=scatter_linear,
                save_file_name="scatter_trimmed_vs_untrimmed_linear",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=scatter_marginal_linear,
                save_file_name="scatter_marginal_trimmed_vs_untrimmed_linear",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=scatter_marginal_poly,
                save_file_name="scatter_marginal_trimmed_vs_untrimmed_quadratic",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=density_marginal,
                save_file_name="density_marginal_trimmed_vs_untrimmed",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=difference_boxplot,
                save_file_name="difference_boxplot_trimmed_vs_untrimmed",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=rank_scatter,
                save_file_name="rank_scatter_trimmed_vs_untrimmed",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
        ]

    def _compare_two_reaction_activity_dfs(
        self,
        trimmed_series: pd.Series,
        untrimmed_series: pd.Series,
    ) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Build per-reaction comparison table for trimmed vs untrimmed values.

        Args:
            trimmed_series (pd.Series): Trimmed values.
            untrimmed_series (pd.Series): Untrimmed values.

        Returns:
            pd.DataFrame: Comparison table with signed and absolute differences.
        """
        aligned_trimmed, aligned_untrimmed = match_two_samples(
            trimmed_series, untrimmed_series
        )
        comparison_df = pd.DataFrame(
            {
                "trimmed_log10": aligned_trimmed,
                "untrimmed_log10": aligned_untrimmed,
            }
        )
        comparison_df["delta_log10"] = (
            comparison_df["trimmed_log10"] - comparison_df["untrimmed_log10"]
        )
        comparison_df["abs_delta_log10"] = comparison_df["delta_log10"].abs()
        comparison_df["trimmed_rank"] = comparison_df["trimmed_log10"].rank(
            ascending=False,
            method="average",
        )
        comparison_df["untrimmed_rank"] = comparison_df["untrimmed_log10"].rank(
            ascending=False,
            method="average",
        )
        comparison_df["rank_shift"] = (
            comparison_df["trimmed_rank"] - comparison_df["untrimmed_rank"]
        )

        comparison_df.index.name = "reaction_id"
        return comparison_df.sort_values("abs_delta_log10", ascending=False)

    def plot_overlaid_histograms_and_cdfs(
        self,
        trimmed_series: pd.Series,
        untrimmed_series: pd.Series,
        sample_name: str,
    ) -> list[DiagnosticOutputSpec]:
        """Generated: validation needed.

        Description:
            Create overlaid histogram and CDF plots for trimmed vs untrimmed values.

        Args:
            trimmed_series (pd.Series): Trimmed values.
            untrimmed_series (pd.Series): Untrimmed values.
            sample_name (str): Sample identifier.

        Returns:
            list[DiagnosticOutputSpec]: Plot output specs.
        """
        histogram = create_overlaid_histogram(
            trimmed_series,
            untrimmed_series,
            plot_config=PlotConfig(
                title=f"Trimmed vs untrimmed histogram ({sample_name})",
                x_label="Reaction capacity (log10)",
                y_label="Count",
                histogram_nbinsx=70,
                width=1100,
                height=760,
            ),
            sample_names=("Trimmed", "Untrimmed"),
        )

        cdf = create_overlaid_cdf(
            trimmed_series,
            untrimmed_series,
            plot_config=PlotConfig(
                title=f"Trimmed vs untrimmed CDF ({sample_name})",
                x_label="Reaction capacity (log10)",
                y_label="Cumulative probability",
                width=1100,
                height=760,
            ),
            sample_names=("Trimmed", "Untrimmed"),
        )

        return [
            DiagnosticOutputSpec(
                data=histogram,
                save_file_name="trimmed_untrimmed_overlaid_histogram",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=cdf,
                save_file_name="trimmed_untrimmed_overlaid_cdf",
                extensions=[".svg", ".html"],
                data_type=go.Figure,
            ),
        ]

    def _plot_trimming_effects_on_reaction_activity(
        self,
        comparison_df: pd.DataFrame,
        title: str,
        top_n: int = 10,
    ) -> go.Figure:
        """Generated: validation needed.

        Description:
            Plot largest trimmed-untrimmed shifts using dual-axis bar-line chart.

        Args:
            comparison_df (pd.DataFrame): Per-reaction comparison table.
            title (str): Plot title.
            top_n (int): Number of reactions to display.

        Returns:
            go.Figure: Plotly figure.
        """
        top_shift_df = comparison_df.head(top_n).copy()
        top_shift_df = top_shift_df.sort_values("delta_log10", ascending=False)

        return create_dual_axis_bar_plot(
            labels=top_shift_df.index.astype(str).tolist(),
            left_values=top_shift_df["delta_log10"].astype(float).tolist(),
            right_values=top_shift_df["abs_delta_log10"].astype(float).tolist(),
            left_name="Signed shift (trimmed - untrimmed)",
            right_name="Absolute shift",
            plot_config=PlotConfig(
                title=title,
                x_label="Reaction",
                y_label="Signed shift (log10)",
                width=1200,
                height=760,
            ),
        )


if __name__ == "__main__":
    diagnostics = object.__new__(VmaxDiagnostics)

    base_dir = Path(
        "/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_Human-GEM-2.0.0_run/"
    )
    reaction_activity_path = base_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"
    untrimmed_reaction_activity_path = (
        base_dir / "outputs" / "reaction_capacity_df_without_trimming.csv"
    )

    reaction_activity_df = pd.read_csv(reaction_activity_path, index_col=0)
    untrimmed_reaction_activity_df = pd.read_csv(
        untrimmed_reaction_activity_path, index_col=0
    )

    trimmed_series, untrimmed_series, sample_name = (
        diagnostics._prepare_trimmed_untrimmed_pair(
            reaction_activity_df,
            untrimmed_reaction_activity_df,
        )
    )

    comparison_df = diagnostics._compare_two_reaction_activity_dfs(
        trimmed_series,
        untrimmed_series,
    )

    one_to_one_specs = diagnostics._one_to_one_comparison_plots(
        trimmed_series,
        untrimmed_series,
        sample_name,
    )
    distribution_specs = diagnostics.plot_overlaid_histograms_and_cdfs(
        trimmed_series,
        untrimmed_series,
        sample_name,
    )
    trimming_effects_figure = diagnostics._plot_trimming_effects_on_reaction_activity(
        comparison_df,
        title=f"Top trimming-induced shifts ({sample_name})",
        top_n=15,
    )

    for spec in [*one_to_one_specs, *distribution_specs]:
        figure = cast(go.Figure, spec.data)
        figure.show()

    trimming_effects_figure.show()
