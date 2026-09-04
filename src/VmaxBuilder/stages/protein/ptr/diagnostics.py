from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from cobra import Model
from scipy.stats.mstats import kruskal
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from statsmodels.stats.multitest import multipletests

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.stages.protein.ptr.ptr_utils import (
    resolve_special_gene_groups,
    transform_ptr_to_linear,
)
from VmaxBuilder.utils.custom_logging import CustomLogger
from VmaxBuilder.utils.plotting.colors import (
    COLORS_HEX,
    COLORS_RGB,
    custom_colorblind_color_discrete_palette,
    hex_to_rgb,
    rgb_to_hex,
    rgb_to_rgba,
    yield_discrete_colorblind_color,
)
from VmaxBuilder.utils.plotting.config import PlotConfig
from VmaxBuilder.utils.plotting.trendline import _create_trendline
from VmaxBuilder.utils.plotting.wrappers import (
    create_overlaid_cdf,
    create_overlaid_histogram,
    create_scatter_comparison_plot,
)

COLORS = custom_colorblind_color_discrete_palette()
COLORBLIND_COLORS_RGB = COLORS[4]  # RGB format for Plotly


class PTRDiagnostics(BaseImplementationDiagnostics[PTRInputConfig]):
    DIAGNOSTICS_NAME = "PTR Diagnostics"
    # todo: later on maybe amend model diagnostics
    # alluvial plot to include something related to PTR
    # has any missing from PTR data

    def __init__(
        self,
        full_config: FullConfig,
    ):
        self.logger = CustomLogger(f"{self.DIAGNOSTICS_NAME}")
        self.full_config = full_config

    def before_run(
        self,
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        base_ptr_df = cast(pd.DataFrame, scaffold.get_scaffold_value("PTR_df"))
        irreversible_cobra_model = cast(
            Model, scaffold.get_scaffold_value("irreversible_cobra_model")
        )
        if not isinstance(base_ptr_df, pd.DataFrame):
            raise ValueError(
                "PTR_df is not a DataFrame. "
                "Please ensure that the PTR data is loaded correctly."
            )

        plot_config = PlotConfig(
            trendline_type="poly",
            x_axis_title_size=16,
            x_axis_label_size=14,
            y_axis_title_size=16,
        )
        transformed_ptr_df = transform_ptr_to_linear(
            base_ptr_df, self.full_config.protein.PTR_pretransformed_type
        )

        metabolic_genes = [gene.id for gene in irreversible_cobra_model.genes]
        metabolic_ptr_df = transformed_ptr_df.loc[
            base_ptr_df.index.intersection(metabolic_genes)
        ]
        use_special_groups = (
            self.full_config.protein.use_special_groups_for_unobserved_imputation
        )
        special_gene_groups = None
        if use_special_groups:
            special_gene_groups = resolve_special_gene_groups(
                self.full_config,
                irreversible_cobra_model,
            )

        missing_value_plots = self.missing_value_plots(
            transformed_ptr_df, metabolic_ptr_df, special_gene_groups, plot_config=plot_config
        )

        gene_group_plots = self.gene_group_plots(
            transformed_ptr_df,
            metabolic_ptr_df,
            special_gene_groups,
            plot_config=plot_config,
        )

        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": {"PTR": [*missing_value_plots] + [*gene_group_plots]},
            "artifacts": {},
            "metadata": {},
        }
        # todo:
        return new_scaffold_objects

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "diagnostics": {},
            "artifacts": {},
            "metadata": {},
        }

    def missing_value_plots(
        self,
        transformed_ptr_df: pd.DataFrame,
        metabolic_ptr_df: pd.DataFrame,
        special_gene_groups: dict[str, list[str]] | None,
        plot_config: PlotConfig | None = None,
    ) -> list[DiagnosticOutputSpec]:
        if plot_config is None:
            plot_config = PlotConfig()
        plot_config.trendline_type = "poly"
        all_gene_name = "all"
        metabolic_gene_name = "metabolic"

        missing_value_correlation_plot_metabolic_only = (
            create_missing_value_PTR_correlation_plot(
                metabolic_ptr_df,
                statistic=self.full_config.protein.partial_missing_imputation_statistic,
                highlight_groups=special_gene_groups,
                plot_config=plot_config,
                name=metabolic_gene_name,
            )
        )
        missing_value_correlation_spec_metabolic_only = DiagnosticOutputSpec(
            data=missing_value_correlation_plot_metabolic_only,
            save_file_name="missing_value_correlation_plot_metabolic_only",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            saver_args={"plot_size": (1600, 1200)},
            data_type=go.Figure,
        )
        missing_value_correlation_plot_all_genes = create_missing_value_PTR_correlation_plot(
            transformed_ptr_df,
            statistic=self.full_config.protein.partial_missing_imputation_statistic,
            highlight_groups=special_gene_groups,
            plot_config=plot_config,
            name=all_gene_name,
        )
        missing_value_correlation_spec_all_genes = DiagnosticOutputSpec(
            data=missing_value_correlation_plot_all_genes,
            save_file_name="missing_value_correlation_plot_all_genes",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            saver_args={"plot_size": (1600, 1200)},
            data_type=go.Figure,
        )
        if special_gene_groups is None:
            special_gene_groups = {}

        missing_overlay_histogram_all_genes = create_overlaying_histograms(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            name=all_gene_name,
            plot_config=plot_config,
        )
        missing_overlay_histogram_spec_all_genes = DiagnosticOutputSpec(
            data=missing_overlay_histogram_all_genes,
            save_file_name="missing_overlay_histogram",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            data_type=go.Figure,
        )
        missing_overlay_histogram_metabolic_only = create_overlaying_histograms(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            name=metabolic_gene_name,
            plot_config=plot_config,
        )
        missing_overlay_histogram_spec_metabolic_only = DiagnosticOutputSpec(
            data=missing_overlay_histogram_metabolic_only,
            save_file_name="missing_overlay_histogram_metabolic_only",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            data_type=go.Figure,
        )

        missing_violin_plot_all_genes = create_violin_plot(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            name=all_gene_name,
            plot_config=plot_config,
        )
        missing_violin_plot_spec = DiagnosticOutputSpec(
            data=missing_violin_plot_all_genes,
            save_file_name="missing_violin_plot",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            data_type=go.Figure,
        )
        missing_violin_plot_metabolic_only = create_violin_plot(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            name=metabolic_gene_name,
            plot_config=plot_config,
        )
        missing_violin_plot_spec_metabolic_only = DiagnosticOutputSpec(
            data=missing_violin_plot_metabolic_only,
            save_file_name="missing_violin_plot_metabolic_only",
            extensions=[
                "html",
                # "png",
                "svg",
            ],
            data_type=go.Figure,
        )

        return [
            (missing_value_correlation_spec_metabolic_only),
            (missing_value_correlation_spec_all_genes),
            (missing_overlay_histogram_spec_all_genes),
            (missing_overlay_histogram_spec_metabolic_only),
            (missing_violin_plot_spec),
            (missing_violin_plot_spec_metabolic_only),
            *self._create_cross_sample_wrapper_plots(transformed_ptr_df, plot_config),
        ]

    def _create_cross_sample_wrapper_plots(
        self,
        transformed_ptr_df: pd.DataFrame,
        plot_config: PlotConfig,
    ) -> list[DiagnosticOutputSpec]:
        """Generated: validation needed.

        Description:
            Build wrapper-based cross-sample comparison plots for PTR data.

        Args:
            transformed_ptr_df (pd.DataFrame): PTR matrix with genes as index and
                samples as columns.
            plot_config (PlotConfig): Plot configuration.

        Returns:
            list[DiagnosticOutputSpec]: Plot outputs. Empty list when fewer than
                two sample columns are available.
        """
        sample_columns = transformed_ptr_df.columns.tolist()
        if len(sample_columns) < 2:
            return []

        sample_one = sample_columns[0]
        sample_two = sample_columns[1]
        sample_one_series = transformed_ptr_df[sample_one]
        sample_two_series = transformed_ptr_df[sample_two]

        scatter_plot = create_scatter_comparison_plot(
            sample_one_series,
            sample_two_series,
            plot_config=PlotConfig(
                title=(f"PTR sample comparison scatter ({sample_one} vs {sample_two})"),
                x_label=f"{sample_one} ({plot_config.Y_axis_unit})",
                y_label=f"{sample_two} ({plot_config.Y_axis_unit})",
                point_size=plot_config.point_size,
                marker_opacity=0.6,
                width=1100,
                height=760,
                histogram_nbinsx=plot_config.histogram_nbinsx,
                histogram_nbinsy=plot_config.histogram_nbinsy,
            ),
            with_marginals=True,
            with_trendline=True,
            trendline_type=plot_config.trendline_type,
        )
        histogram_plot = create_overlaid_histogram(
            sample_one_series,
            sample_two_series,
            plot_config=PlotConfig(
                title=(f"PTR sample comparison histogram ({sample_one} vs {sample_two})"),
                x_label=f"PTR value ({plot_config.Y_axis_unit})",
                y_label=plot_config.histogram_axis_type.capitalize(),
                width=1100,
                height=760,
                histogram_nbinsx=plot_config.histogram_nbinsx,
            ),
            sample_names=(str(sample_one), str(sample_two)),
        )
        cdf_plot = create_overlaid_cdf(
            sample_one_series,
            sample_two_series,
            plot_config=PlotConfig(
                title=f"PTR sample comparison CDF ({sample_one} vs {sample_two})",
                x_label=f"PTR value ({plot_config.Y_axis_unit})",
                y_label="Cumulative probability",
                width=1100,
                height=760,
            ),
            sample_names=(str(sample_one), str(sample_two)),
        )

        return [
            DiagnosticOutputSpec(
                data=scatter_plot,
                save_file_name=(
                    f"cross_sample_scatter_{sample_one}_vs_{sample_two}".replace("/", "_")
                ),
                extensions=["html", "svg"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=histogram_plot,
                save_file_name=(
                    f"cross_sample_histogram_{sample_one}_vs_{sample_two}".replace("/", "_")
                ),
                extensions=["html", "svg"],
                data_type=go.Figure,
            ),
            DiagnosticOutputSpec(
                data=cdf_plot,
                save_file_name=(
                    f"cross_sample_cdf_{sample_one}_vs_{sample_two}".replace("/", "_")
                ),
                extensions=["html", "svg"],
                data_type=go.Figure,
            ),
        ]

    def gene_group_plots(
        self,
        transformed_ptr_df: pd.DataFrame,
        metabolic_ptr_df: pd.DataFrame,
        special_gene_groups: dict[str, list[str]] | None,
        plot_config: PlotConfig | None = None,
    ) -> list[DiagnosticOutputSpec]:
        if special_gene_groups is None:
            special_gene_groups = {}
        if plot_config is None:
            plot_config = PlotConfig()

        all_gene_name = "all"
        metabolic_gene_name = "metabolic"
        statistic_gene_group_statistics_df_all_genes = calculate_statistics(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
        )

        statistic_gene_group_histogram_all_genes = create_overlaying_histograms(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
            name=all_gene_name,
            plot_config=plot_config,
        )

        statistic_gene_group_violin_all_genes = create_violin_plot(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
            name=all_gene_name,
            plot_config=plot_config,
        )
        # metabolic

        statistic_gene_group_statistics_df_metabolic_only = calculate_statistics(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
        )

        statistic_gene_group_histogram_metabolic_only = create_overlaying_histograms(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
            name=metabolic_gene_name,
            plot_config=plot_config,
        )

        statistic_gene_group_violin_metabolic_only = create_violin_plot(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type=self.full_config.protein.partial_missing_imputation_statistic,
            name=metabolic_gene_name,
            plot_config=plot_config,
        )

        default_gene_group_statistics_df_all_genes = calculate_statistics(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
        )
        default_gene_group_histogram_all_genes = create_overlaying_histograms(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
            name=all_gene_name,
            plot_config=plot_config,
        )
        default_gene_group_violin_all_genes = create_violin_plot(
            transformed_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
            name=all_gene_name,
            plot_config=plot_config,
        )

        default_gene_group_statistics_df_metabolic_only = calculate_statistics(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
        )
        default_gene_group_histogram_metabolic_only = create_overlaying_histograms(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
            name=metabolic_gene_name,
            plot_config=plot_config,
        )
        default_gene_group_violin_metabolic_only = create_violin_plot(
            metabolic_ptr_df,
            special_gene_groups=special_gene_groups,
            value_type="default",
            name=metabolic_gene_name,
            plot_config=plot_config,
        )

        # outputs

        statistic_gene_group_statistics_spec_all_genes = DiagnosticOutputSpec(
            data=statistic_gene_group_statistics_df_all_genes,
            save_file_name="statistic_gene_group_statistics_all_genes",
            extensions=["csv", "xlsx"],
            data_type=pd.DataFrame,
        )
        statistic_gene_group_histogram_spec_all_genes = DiagnosticOutputSpec(
            data=statistic_gene_group_histogram_all_genes,
            save_file_name="statistic_gene_group_histogram_all_genes",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )
        statistic_gene_group_violin_spec_all_genes = DiagnosticOutputSpec(
            data=statistic_gene_group_violin_all_genes,
            save_file_name="statistic_gene_group_violin_all_genes",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )
        statistic_gene_group_statistics_spec_metabolic_only = DiagnosticOutputSpec(
            data=statistic_gene_group_statistics_df_metabolic_only,
            save_file_name="statistic_gene_group_statistics_metabolic_only",
            extensions=["csv", "xlsx"],
            data_type=pd.DataFrame,
        )
        statistic_gene_group_histogram_spec_metabolic_only = DiagnosticOutputSpec(
            data=statistic_gene_group_histogram_metabolic_only,
            save_file_name="statistic_gene_group_histogram_metabolic_only",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )
        statistic_gene_group_violin_spec_metabolic_only = DiagnosticOutputSpec(
            data=statistic_gene_group_violin_metabolic_only,
            save_file_name="statistic_gene_group_violin_metabolic_only",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )

        default_gene_group_statistics_spec_all_genes = DiagnosticOutputSpec(
            data=default_gene_group_statistics_df_all_genes,
            save_file_name="default_gene_group_statistics_all_genes",
            extensions=["csv", "xlsx"],
            data_type=pd.DataFrame,
        )

        default_gene_group_histogram_spec_all_genes = DiagnosticOutputSpec(
            data=default_gene_group_histogram_all_genes,
            save_file_name="default_gene_group_histogram_all_genes",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )

        default_gene_group_violin_spec_all_genes = DiagnosticOutputSpec(
            data=default_gene_group_violin_all_genes,
            save_file_name="default_gene_group_violin_all_genes",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )

        default_gene_group_histogram_spec_metabolic_only = DiagnosticOutputSpec(
            data=default_gene_group_histogram_metabolic_only,
            save_file_name="default_gene_group_histogram_metabolic_only",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )

        default_gene_group_violin_spec_metabolic_only = DiagnosticOutputSpec(
            data=default_gene_group_violin_metabolic_only,
            save_file_name="default_gene_group_violin_metabolic_only",
            extensions=["html", "png", "svg"],
            data_type=go.Figure,
        )
        default_gene_group_statistics_spec_metabolic_only = DiagnosticOutputSpec(
            data=default_gene_group_statistics_df_metabolic_only,
            save_file_name="default_gene_group_statistics_metabolic_only",
            extensions=["csv", "xlsx"],
            data_type=pd.DataFrame,
        )

        return [
            (statistic_gene_group_statistics_spec_all_genes),
            (statistic_gene_group_histogram_spec_all_genes),
            (statistic_gene_group_violin_spec_all_genes),
            (statistic_gene_group_statistics_spec_metabolic_only),
            (statistic_gene_group_histogram_spec_metabolic_only),
            (statistic_gene_group_violin_spec_metabolic_only),
            (default_gene_group_statistics_spec_all_genes),
            (default_gene_group_histogram_spec_all_genes),
            (default_gene_group_violin_spec_all_genes),
            (default_gene_group_statistics_spec_metabolic_only),
            (default_gene_group_histogram_spec_metabolic_only),
            (default_gene_group_violin_spec_metabolic_only),
        ]


STATISTIC_FUNCTIONS = {
    "mean": lambda df, axis=None, skipna=True: df.mean(axis=axis, skipna=skipna),
    "median": lambda df, axis=None, skipna=True: df.median(axis=axis, skipna=skipna),
    "sum": lambda df, axis=None, skipna=True: df.sum(axis=axis, skipna=skipna),
}


def _apply_Y_transformation(
    PTR_df: pd.DataFrame,
    plot_config: PlotConfig | None = None,
    Y_transformation: str | None = None,
) -> pd.DataFrame:
    PTR_df = PTR_df.copy()
    data_cols = PTR_df.columns
    if Y_transformation is None and plot_config is None:
        raise ValueError("Either Y_transformation or plot_config must be provided.")

    if plot_config is not None:
        Y_transformation = plot_config.Y_transformation

    if Y_transformation == "log10":
        PTR_df[data_cols] = PTR_df[data_cols].infer_objects(copy=False).astype(float)
        PTR_df[data_cols] = PTR_df[data_cols].apply(
            lambda series: pd.Series(np.log10(series), index=series.index)
        )
    elif Y_transformation == "log" or Y_transformation == "ln":
        PTR_df[data_cols] = PTR_df[data_cols].infer_objects(copy=False).astype(float)
        PTR_df[data_cols] = PTR_df[data_cols].apply(
            lambda series: pd.Series(np.log(series), index=series.index)
        )
    elif Y_transformation == "sqrt":
        PTR_df[data_cols] = PTR_df[data_cols].infer_objects(copy=False).astype(float)
        PTR_df[data_cols] = PTR_df[data_cols].apply(
            lambda series: pd.Series(np.sqrt(series), index=series.index)
        )
    elif Y_transformation != "linear":
        raise ValueError(f"Y_transformation '{Y_transformation}' is not supported.")
    return PTR_df


def create_missing_value_PTR_correlation_plot(
    PTR_df: pd.DataFrame,
    name: str,
    statistic: str = "mean",
    highlight_groups: dict[str, list[str]] | None = None,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """
    Plots individual gene stats against missing counts to highlight linear decrease,
    optimized with micro-opacity for 20,000+ data points and a linear OLS trendline.
    """
    np.random.seed(999)
    PTR_df = PTR_df.copy()
    if plot_config is None:
        plot_config = PlotConfig()

    # coerce to numeric and handle non-numeric gracefully
    PTR_df = PTR_df.apply(pd.to_numeric, errors="coerce")
    PTR_df = _apply_Y_transformation(PTR_df, plot_config)

    missing_counts = PTR_df.isnull().sum(axis=1)
    if statistic not in STATISTIC_FUNCTIONS:
        raise ValueError(f"Statistic '{statistic}' is not supported.")

    statistic_values = STATISTIC_FUNCTIONS[statistic](PTR_df, axis=1, skipna=True)
    result_df = pd.DataFrame(
        {"missing_count": missing_counts, "stat_value": statistic_values}
    ).dropna()  # Safe drop for regression stability

    fig = go.Figure()
    # scatter with jitter
    non_highlight_jitter = np.random.uniform(-0.15, 0.15, len(result_df))
    non_highlight_df = result_df
    non_highlight_name = f"All Genes ({len(result_df):,})"

    if highlight_groups:
        all_highlighted_genes = set()
        color_generator = yield_discrete_colorblind_color(COLORBLIND_COLORS_RGB, 2)

        for group_name, group_genes in highlight_groups.items():
            group_genes = [gene for gene in group_genes if gene in result_df.index]
            highlight_df = result_df.loc[group_genes]
            highlight_jitter = np.random.uniform(-0.15, 0.15, len(highlight_df))
            highlight_name = (
                f"{group_name} ({len(highlight_df):,})"
                if group_name
                else f"Highlighted Genes ({len(highlight_df):,})"
            )
            color = rgb_to_rgba(
                next(color_generator),
                plot_config.highlight_opacity,
            )
            fig.add_trace(
                go.Scatter(
                    x=highlight_df["missing_count"] + highlight_jitter,
                    y=highlight_df["stat_value"],
                    mode="markers",
                    name=highlight_name,
                    marker=dict(
                        color=color,
                        size=plot_config.point_size + 1,
                    ),
                    text=highlight_df.index,
                    legendgroup="highlighted_genes",
                    legendgrouptitle_text="Special",
                    # Use customdata if you need to pass additional metadata fields later
                    hovertemplate=(
                        f"<b>%{{text}}</b><br>"
                        f"Gene {statistic.capitalize()}: %{{y:.3f}}<extra></extra>"
                    ),
                ),
            )
            all_highlighted_genes.update(group_genes)

        non_highlight_df = result_df.drop(all_highlighted_genes, errors="ignore")
        non_highlight_jitter = np.random.uniform(-0.15, 0.15, len(non_highlight_df))
        non_highlight_name = f"Non-Highlighted Genes ({len(non_highlight_df):,})"

        # on hover we want to highlight all values of this highlight group
        # as well as provide the gene name
        #

    fig.add_trace(
        go.Scatter(
            x=non_highlight_df["missing_count"] + non_highlight_jitter,
            y=non_highlight_df["stat_value"],
            mode="markers",
            name=non_highlight_name,
            marker=dict(
                size=plot_config.point_size,
                color=rgb_to_rgba(COLORS_RGB["lightblue_hex"], 0.2),
                line=dict(width=0),
            ),
            text=non_highlight_df.index,
            hovertemplate=(
                f"<b>%{{text}}</b><br>"
                f"Gene {statistic.capitalize()}: %{{y:.3f}}<extra></extra>"
            ),
            legendgroup="rows",
            legendgrouptitle_text="Main",
        ),
    )

    # boxplot overlay for median and IQR could be added here if desired
    if plot_config.with_boxplot:
        fig.add_trace(  # ty ignore: [unresolved-attribute]
            go.Box(  # ty ignore: [unresolved-attribute]
                x=result_df["missing_count"],
                y=result_df["stat_value"],
                name="Median & IQR",
                boxpoints=False,
                line=dict(color=rgb_to_rgba(COLORS_RGB["black_hex"], 0.5)),
                fillcolor=rgb_to_rgba(COLORS_RGB["black_hex"], 0.1),
                hoverinfo="skip",  # ty ignore: [unresolved-attribute]
                legendgroup="rows",  # ty ignore: [unresolved-attribute]
            ),  # ty ignore: [unresolved-attribute]
        )

    # trendline
    X = result_df["missing_count"].values.reshape(-1, 1)  # ty: ignore
    y = result_df["stat_value"].values.reshape(-1, 1)  # ty: ignore

    # use

    if plot_config.with_trendline:
        (x_range, y_pred, y_lower, y_upper, trace_name) = _create_trendline(
            X, result_df, y, trendline_type=plot_config.trendline_type
        )

        fig.add_trace(
            go.Scatter(
                x=x_range.flatten(),
                y=y_pred.flatten(),
                mode="lines",
                name=trace_name,
                line=dict(
                    color=rgb_to_rgba(COLORS_RGB["lightred_hex"], 0.8), width=2, dash="dash"
                ),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([x_range.flatten(), x_range.flatten()[::-1]]),
                y=np.concatenate([y_upper, y_lower[::-1]]),
                fill="toself",
                fillcolor=rgb_to_rgba(COLORS_RGB["gray_red_hex"], 0.2),
                line=dict(color=rgb_to_rgba(COLORS_RGB["gray_red_hex"], 0.2)),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # percentage bar charts
    counts_per_missing = result_df["missing_count"].value_counts().sort_index().astype(float)
    total_ptrs = len(result_df)
    percentages = counts_per_missing.div(float(total_ptrs)).mul(100.0)

    if plot_config.with_percentage_bar:
        fig.add_trace(
            go.Bar(
                x=percentages.index,
                y=percentages.values,
                name="Percentage of Dataset",
                yaxis="y2",
                marker=dict(color=rgb_to_rgba(COLORS_RGB["orange_hex"], 0.2)),
            )
        )

    # percentages x axis
    xaxis_ticks = percentages.index.tolist()
    fig.update_xaxes(
        range=[
            -plot_config.Y_axis_margin,
            result_df["missing_count"].max() + plot_config.Y_axis_margin,
        ],
        tickvals=xaxis_ticks,
        ticktext=[f"{x} ({percentages[x]:.1f}%)" for x in xaxis_ticks],
        tickangle=45,
        # size label and title
        title_font=dict(size=plot_config.x_axis_title_size),
        tickfont=dict(size=plot_config.x_axis_label_size),
    )

    #  layout
    fig.update_layout(
        title=f"Missing value PTR Correlation {name} (Total Rows: {total_ptrs:,})",
        xaxis_title="Number of missing values",
        yaxis=dict(
            title=f"Gene {statistic.capitalize()} value ({plot_config.Y_axis_unit})",
            side="left",
        ),
        yaxis2=dict(
            title="Percentage of Dataset (%)",
            overlaying="y",
            side="right",
            range=[0, max(percentages.values) * 1.1],
            showgrid=False,
        ),
        legend=dict(
            x=0.01 - (plot_config.Y_axis_margin * 0.05),
            y=0.99,
            bgcolor=rgb_to_rgba(COLORS_RGB["white_hex"], 0.8),
        ),
        template="plotly_white",
        barmode="overlay",
    )

    return fig


def _separate_special_gene_groups(
    PTR_df: pd.DataFrame, special_gene_groups: dict[str, list[str]]
) -> dict[str, pd.DataFrame]:
    separated_groups = {}
    for group_name, group_genes in special_gene_groups.items():
        group_genes = [gene for gene in group_genes if gene in PTR_df.index]
        separated_groups[group_name] = PTR_df.loc[group_genes]
    return separated_groups


def _overlay_opacity_function(num_groups: int, base_opacity: float = 0.55) -> float:
    """
    Calculate the overlay opacity for histograms based on the number of groups.

    Args:
        num_groups (int): Number of groups to overlay.
        base_opacity (float): Base opacity for 2 groups.

    Returns:
        float: Calculated opacity for the given number of groups.
    """
    if num_groups <= 1:
        return 1.0
    else:
        # Exponential decay function to reduce opacity as the number of groups increases
        return max(base_opacity * (0.8 ** (num_groups - 2)), 0.1)


def create_overlaying_histograms(
    PTR_df: pd.DataFrame,
    special_gene_groups: dict[str, list[str]],
    name: str,
    plot_config: PlotConfig | None = None,
    value_type: str = "missing",  # "default", if default we use the values
    # or median mean or sum when taking values together
) -> go.Figure:
    PTR_df = PTR_df.copy()
    if plot_config is None:
        plot_config = PlotConfig()
    # config includes hisogram type
    PTR_df = _apply_Y_transformation(PTR_df, plot_config)

    separated_groups = _separate_special_gene_groups(PTR_df, special_gene_groups)
    remaining_genes = set(PTR_df.index) - set(
        gene for group in special_gene_groups.values() for gene in group
    )
    fig = go.Figure()
    nbinsx = plot_config.histogram_nbinsx
    opacity = _overlay_opacity_function(
        len(separated_groups) + 1, plot_config.histogram_base_overlay_opacity
    )

    # print(PTR_df.describe())
    if value_type == "default":
        x_min = min(
            PTR_df.min().min(),
            *[group_df.min().min() for group_df in separated_groups.values()],
        )
        x_max = max(
            PTR_df.max().max(),
            *[group_df.max().max() for group_df in separated_groups.values()],
        )
        bin_size = (x_max - x_min) / nbinsx
        for group_name, group_df in separated_groups.items():
            group_values = group_df.values.flatten()[~np.isnan(group_df.values.flatten())]
            group_values = group_values[np.isfinite(group_values)]  # Remove inf values]
            fig.add_trace(
                go.Histogram(
                    x=group_values,
                    name=group_name,
                    histnorm=plot_config.histogram_axis_type,
                    opacity=opacity,
                    xbins=dict(start=x_min, end=x_max, size=bin_size),
                )
            )
        remaining_values = PTR_df.loc[list(remaining_genes)].values.flatten()
        remaining_values = remaining_values[~np.isnan(remaining_values)]
        remaining_values = remaining_values[
            np.isfinite(remaining_values)
        ]  # Remove inf values

        fig.add_trace(
            go.Histogram(
                x=remaining_values,
                name="Remaining Genes",
                histnorm=plot_config.histogram_axis_type,
                opacity=opacity,
                xbins=dict(start=x_min, end=x_max, size=bin_size),
            )
        )
        total_values = len(PTR_df.values.flatten()[~np.isnan(PTR_df.values.flatten())])
        title_name = f"Overlaying histograms of PTR values {name} genes ({total_values:,})"
        fig.update_layout(
            title=title_name,
            xaxis_title=f"PTR values ({plot_config.Y_axis_unit})",
            yaxis_title=(plot_config.histogram_axis_type.capitalize()),
            barmode="overlay",
            template="plotly_white",
        )

    elif value_type in STATISTIC_FUNCTIONS:
        for group_name, group_df in separated_groups.items():
            group_values = (
                STATISTIC_FUNCTIONS[value_type](group_df, axis=1, skipna=True)
                .to_numpy()
                .flatten()
            )
            group_values = group_values[~np.isnan(group_values)]
            group_values = group_values[np.isfinite(group_values)]  # Remove inf values
            x_min = min(
                group_values.min(),
                *[group_df.min().min() for group_df in separated_groups.values()],
            )
            x_max = max(
                group_values.max(),
                *[group_df.max().max() for group_df in separated_groups.values()],
            )
            bin_size = (x_max - x_min) / nbinsx
            fig.add_trace(
                go.Histogram(
                    x=group_values,
                    name=group_name,
                    histnorm=plot_config.histogram_axis_type,
                    opacity=opacity,
                    xbins=dict(start=x_min, end=x_max, size=bin_size),
                )
            )
        remaining_values = (
            STATISTIC_FUNCTIONS[value_type](
                PTR_df.loc[list(remaining_genes)], axis=1, skipna=True
            )
            .to_numpy()
            .flatten()
        )
        remaining_values = remaining_values[~np.isnan(remaining_values)]
        fig.add_trace(
            go.Histogram(
                x=remaining_values,
                name="Remaining Genes",
                histnorm=plot_config.histogram_axis_type,
                opacity=opacity,
                xbins=dict(start=x_min, end=x_max, size=bin_size),
            )
        )
        title_name = (
            f"Overlaying histograms of {value_type.capitalize()} "
            f"PTR values {name} genes ({len(PTR_df):,})"
        )
        fig.update_layout(
            title=title_name,
            xaxis_title=(f"{value_type.capitalize()} PTR values ({plot_config.Y_axis_unit})"),
            yaxis_title=(plot_config.histogram_axis_type.capitalize()),
            barmode="overlay",
            template="plotly_white",
        )
    elif value_type == "missing":
        for group_name, group_df in separated_groups.items():
            missing_counts = group_df.isnull().sum(axis=1)
            fig.add_trace(
                go.Histogram(
                    x=missing_counts,
                    name=group_name,
                    histnorm=plot_config.histogram_axis_type,
                    opacity=opacity,
                    nbinsx=nbinsx,
                )
            )
        remaining_missing_counts = PTR_df.loc[list(remaining_genes)].isnull().sum(axis=1)
        fig.add_trace(
            go.Histogram(
                x=remaining_missing_counts,
                name="Remaining Genes",
                histnorm=plot_config.histogram_axis_type,
                opacity=opacity,
                nbinsx=nbinsx,
            )
        )
        title_name = f"Overlaying histograms of missing values {name} genes ({len(PTR_df):,})"

        fig.update_layout(
            title=title_name,
            xaxis_title="Number of missing values",
            yaxis_title=(plot_config.histogram_axis_type.capitalize()),
            barmode="overlay",
            template="plotly_white",
        )

    # update xaxis tick and title size, as well as for y axxis title
    fig.update_xaxes(
        title_font=dict(size=plot_config.x_axis_title_size),
        tickfont=dict(size=plot_config.x_axis_label_size),
    )
    fig.update_yaxes(title_font=dict(size=plot_config.y_axis_title_size))

    return fig


def create_violin_plot(
    PTR_df: pd.DataFrame,
    special_gene_groups: dict[str, list[str]],
    name: str,
    plot_config: PlotConfig | None = None,
    value_type: str = "default",  # "default" for PTR values, "missing" for missing counts
) -> go.Figure:
    if plot_config is None:
        plot_config = PlotConfig()

    PTR_df = _apply_Y_transformation(PTR_df, plot_config)

    separated_groups = _separate_special_gene_groups(PTR_df, special_gene_groups)
    remaining_genes = set(PTR_df.index) - set(
        gene for group in special_gene_groups.values() for gene in group
    )

    fig = go.Figure()
    if value_type == "default":
        for group_name, group_df in separated_groups.items():
            group_values = group_df.values.flatten()[~np.isnan(group_df.values.flatten())]
            fig.add_trace(
                go.Violin(
                    y=group_values,
                    name=group_name,
                    box_visible=True,
                    meanline_visible=True,
                    opacity=0.75,
                    spanmode="hard",
                )
            )
        remaining_values = PTR_df.loc[list(remaining_genes)].values.flatten()
        remaining_values = remaining_values[~np.isnan(remaining_values)]
        fig.add_trace(
            go.Violin(
                y=remaining_values,
                name="Remaining Genes",
                box_visible=True,
                meanline_visible=True,
                opacity=0.75,
                spanmode="hard",
            )
        )
        # sum all non na values
        total_values = len(PTR_df.values.flatten()[~np.isnan(PTR_df.values.flatten())])

        title_name = f"Violin Plot of PTR values {name} genes ({total_values:,})"
        fig.update_layout(
            title=title_name,
            yaxis_title=f"PTR values ({plot_config.Y_axis_unit})",
            template="plotly_white",
        )

    elif value_type in STATISTIC_FUNCTIONS:
        for group_name, group_df in separated_groups.items():
            group_values = (
                STATISTIC_FUNCTIONS[value_type](group_df, axis=1, skipna=True)
                .to_numpy()
                .flatten()
            )
            group_values = group_values[~np.isnan(group_values)]
            fig.add_trace(
                go.Violin(
                    y=group_values,
                    name=group_name,
                    box_visible=True,
                    meanline_visible=True,
                    opacity=0.75,
                    spanmode="hard",
                )
            )
        remaining_values = (
            STATISTIC_FUNCTIONS[value_type](
                PTR_df.loc[list(remaining_genes)], axis=1, skipna=True
            )
            .to_numpy()
            .flatten()
        )
        remaining_values = remaining_values[~np.isnan(remaining_values)]
        fig.add_trace(
            go.Violin(
                y=remaining_values,
                name="Remaining Genes",
                box_visible=True,
                meanline_visible=True,
                opacity=0.75,
                spanmode="hard",
            )
        )
        title_name = (
            f"Violin Plot of {value_type.capitalize()} "
            f"PTR values {name} genes ({len(PTR_df):,})"
        )
        fig.update_layout(
            title=title_name,
            yaxis_title=f"{value_type.capitalize()} PTR values ({plot_config.Y_axis_unit})",
            template="plotly_white",
        )

    elif value_type == "missing":
        for group_name, group_df in separated_groups.items():
            missing_counts = group_df.isnull().sum(axis=1)
            fig.add_trace(
                go.Violin(
                    y=missing_counts,
                    name=group_name,
                    box_visible=True,
                    meanline_visible=True,
                    opacity=0.75,
                    spanmode="hard",
                )
            )

        remaining_missing_counts = PTR_df.loc[list(remaining_genes)].isnull().sum(axis=1)
        fig.add_trace(
            go.Violin(
                y=remaining_missing_counts,
                name="Remaining Genes",
                box_visible=True,
                meanline_visible=True,
                opacity=0.75,
                spanmode="hard",
            )
        )

        title_name = f"Violin Plot of missing values {name} genes ({len(PTR_df):,})"
        fig.update_layout(
            title=title_name,
            yaxis_title="Missing values",
            template="plotly_white",
        )
    # update xaxis tick and title size, as well as for y axxis title
    fig.update_xaxes(
        title_font=dict(size=plot_config.x_axis_title_size),
        tickfont=dict(size=plot_config.x_axis_label_size),
    )
    fig.update_yaxes(title_font=dict(size=plot_config.y_axis_title_size))

    return fig


def calculate_statistics(
    PTR_df: pd.DataFrame,
    special_gene_groups: dict[str, list[str]],
    value_type: str = "missing",  # "default" for PTR values, "missing" for missing counts
    y_transformation: str = "linear",  # Options: "linear", "log", "log10", "sqrt"
) -> pd.DataFrame:
    PTR_df = _apply_Y_transformation(PTR_df, Y_transformation=y_transformation)

    separate_groups = _separate_special_gene_groups(PTR_df, special_gene_groups)
    remaining_genes = set(PTR_df.index) - set(
        gene for group in special_gene_groups.values() for gene in group
    )
    if value_type == "default":
        values_per_group = {
            group_name: group_df.values.flatten()[~np.isnan(group_df.values.flatten())]
            for group_name, group_df in separate_groups.items()
        }
        values_per_group["Remaining Genes"] = PTR_df.loc[
            list(remaining_genes)
        ].values.flatten()[~np.isnan(PTR_df.loc[list(remaining_genes)].values.flatten())]
    elif value_type in STATISTIC_FUNCTIONS:
        values_per_group = {
            group_name: STATISTIC_FUNCTIONS[value_type](group_df, axis=1, skipna=True)
            .to_numpy()
            .flatten()
            for group_name, group_df in separate_groups.items()
        }
        values_per_group["Remaining Genes"] = (
            STATISTIC_FUNCTIONS[value_type](
                PTR_df.loc[list(remaining_genes)], axis=1, skipna=True
            )
            .to_numpy()
            .flatten()
        )

    elif value_type == "missing":
        values_per_group = {
            group_name: group_df.isnull().sum(axis=1).values
            for group_name, group_df in separate_groups.items()
        }
        values_per_group["Remaining Genes"] = (
            PTR_df.loc[list(remaining_genes)].isnull().sum(axis=1).values
        )

    stats_summaries = {}
    for group_name, raw_values in values_per_group.items():
        clean_values = np.asarray(raw_values, dtype=float)

        stats_summaries[group_name] = {
            f"mean_{value_type}": np.nanmean(clean_values),
            f"median_{value_type}": np.nanmedian(clean_values),
            f"std_{value_type}": np.nanstd(clean_values),
            "count": len(clean_values),
        }

    statistics_df = pd.DataFrame(stats_summaries).T
    # give index a name for clarity based on value_typeo
    statistics_df.index.name = f"{value_type.capitalize()} Group"

    # kruskal wallis test + multiple comparision with benjamin hochberg correction
    kruskal_results = kruskal(
        *[np.asarray(values, dtype=float) for values in values_per_group.values()]
    )
    comparison_results = {}

    if len(values_per_group) > 2:
        p_values = []
        group_names = list(values_per_group.keys())
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group_i = np.asarray(values_per_group[group_names[i]], dtype=float)
                group_j = np.asarray(values_per_group[group_names[j]], dtype=float)

                _, p_value = kruskal(
                    group_i,
                    group_j,
                )
                p_values.append(p_value)

        # Apply Benjamini-Hochberg correction
        reject, pvals_corrected, _, _ = multipletests(p_values, method="fdr_bh")
        comparison_results = {
            f"{group_names[i]} vs {group_names[j]}": {
                "p_value": p,
                "reject_null": r,
            }
            for (i, j), p, r in zip(
                [
                    (i, j)
                    for i in range(len(group_names))
                    for j in range(i + 1, len(group_names))
                ],
                pvals_corrected,
                reject,
                strict=False,
            )
        }
    # put into stats results

    statistics_df["kruskal_h"] = kruskal_results.statistic
    statistics_df["kruskal_p"] = kruskal_results.pvalue
    for comparison, result in comparison_results.items():
        statistics_df[f"{comparison}_p"] = result["p_value"]
        statistics_df[f"{comparison}_reject_null"] = result["reject_null"]

    return statistics_df


def calculate_PTR_values_special_gene_groups(
    PTR_df: pd.DataFrame,
    special_gene_groups: dict[str, list[str]],
) -> pd.DataFrame:
    """
    Calculate statistics for PTR values of special gene groups and remaining genes.

    Args:
        PTR_df (pd.DataFrame): DataFrame containing PTR values with genes as index.
        special_gene_groups (dict): Dictionary of special gene groups.

    Returns:
        pd.DataFrame: DataFrame containing statistics for each group.
    """
    per_group_values = {}
    remaining_genes = set(PTR_df.index)
    for group_name, group_genes in special_gene_groups.items():
        group_genes = [gene for gene in group_genes if gene in PTR_df.index]
        group_values = PTR_df.loc[group_genes].values.flatten()
        group_values = group_values[~np.isnan(group_values)]  # Remove NaN values
        per_group_values[group_name] = {
            "mean_value": np.mean(group_values),
            "median_value": np.median(group_values),
            "std_value": np.std(group_values),
            "count": len(group_values),
        }
        remaining_genes -= set(group_genes)

    remaining_values = PTR_df.loc[list(remaining_genes)].values.flatten()
    remaining_values = remaining_values[~np.isnan(list(remaining_values))]  # Remove NaN
    per_group_values["Remaining Genes"] = {
        "mean_value": np.mean(remaining_values),
        "median_value": np.median(remaining_values),
        "std_value": np.std(remaining_values),
        "count": len(remaining_values),
    }

    return pd.DataFrame(per_group_values).T


if __name__ == "__main__":
    ptr_data_path = Path(
        "/home/p70088775/git/SWAPAM/data/for_SWAMP"
        "/PTR_datasets/Eraslan2019V1_human/PTRs_all__PMC6379048_eraslan.csv"
    )

    PTR_df = pd.read_csv(ptr_data_path, index_col=0)
    PTR_df = transform_ptr_to_linear(PTR_df, pretransformed_type="log10")
    # take a gene every 20 genes for highlight names
    to_highlight_genes = PTR_df.index[::20].tolist()
    highlight_info = {
        "Highlighted Genes (every 20th gene)": to_highlight_genes,
    }
    plot_config = PlotConfig(
        point_size=3,
        highlight_opacity=0.8,
        x_axis_title_size=16,
        x_axis_label_size=14,
        y_axis_title_size=16,
        Y_axis_unit="Log10",
        Y_axis_margin=0.5,
        with_boxplot=True,
        with_percentage_bar=True,
        with_trendline=True,
        trendline_type="linear",
        Y_transformation="log10",
        histogram_axis_type="probability",
        histogram_nbinsx=80,
    )
    show_figs = False
    all_gene_name = "all"
    missing_correlation_fig = create_missing_value_PTR_correlation_plot(
        PTR_df,
        statistic="median",
        highlight_groups=highlight_info,
        plot_config=plot_config,
        name=all_gene_name,
    )
    missing_overlaying_histogram_fig = create_overlaying_histograms(
        PTR_df,
        special_gene_groups=highlight_info,
        name=all_gene_name,
        plot_config=plot_config,
    )
    missing_violin_fig = create_violin_plot(
        PTR_df,
        name=all_gene_name,
        special_gene_groups=highlight_info,
        plot_config=plot_config,
    )
    missing_statistics_df = calculate_statistics(
        PTR_df,
        special_gene_groups=highlight_info,
    )

    values_overlaying_histogram_fig = create_overlaying_histograms(
        PTR_df,
        special_gene_groups=highlight_info,
        name=all_gene_name,
        plot_config=plot_config,
        value_type="default",
    )

    values_violin_fig = create_violin_plot(
        PTR_df,
        special_gene_groups=highlight_info,
        name=all_gene_name,
        plot_config=plot_config,
        value_type="default",
    )

    values_statistics_df = calculate_statistics(
        PTR_df,
        special_gene_groups=highlight_info,
        value_type="default",
        y_transformation="log10",
    )

    median_values_overlaying_histogram_fig = create_overlaying_histograms(
        PTR_df,
        special_gene_groups=highlight_info,
        name=all_gene_name,
        plot_config=plot_config,
        value_type="median",
    )

    median_values_violin_fig = create_violin_plot(
        PTR_df,
        special_gene_groups=highlight_info,
        name=all_gene_name,
        plot_config=plot_config,
        value_type="median",
    )
    median_values_statistics_df = calculate_statistics(
        PTR_df,
        special_gene_groups=highlight_info,
        value_type="median",
        y_transformation="log10",
    )

    missing_correlation_fig.show()
    if show_figs:
        missing_correlation_fig.show()
        missing_overlaying_histogram_fig.show()
        missing_violin_fig.show()
        values_overlaying_histogram_fig.show()
        values_violin_fig.show()
        median_values_overlaying_histogram_fig.show()
        median_values_violin_fig.show()
        print(missing_statistics_df)
        print(values_statistics_df)
        print(median_values_statistics_df)
