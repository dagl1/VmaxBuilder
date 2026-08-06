from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from cobra import Model
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.stages.protein.ptr.ptr_utils import (
    resolve_special_gene_groups,
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

COLORS = custom_colorblind_color_discrete_palette()
COLORBLIND_COLORS_RGB = COLORS[4]  # RGB format for Plotly


class PTRDiagnostics(BaseImplementationDiagnostics[PTRInputConfig]):
    DIAGNOSTICS_NAME = "PTR Diagnostics"

    def __init__(
        self,
        full_config: FullConfig,
    ):
        self.logger = CustomLogger(f"Fallback logger: {self.DIAGNOSTICS_NAME}")
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

        metabolic_genes = [gene.id for gene in irreversible_cobra_model.genes]
        metabolic_ptr_df = base_ptr_df.loc[base_ptr_df.index.intersection(metabolic_genes)]
        use_special_groups = (
            self.full_config.protein.use_special_groups_for_unobserved_imputation
        )
        special_gene_groups = None
        if use_special_groups:
            special_gene_groups = resolve_special_gene_groups(
                self.full_config,
                irreversible_cobra_model,
            )

        missing_value_correlation_plot_metabolic_only = (
            create_missing_value_PTR_correlation_plot(
                metabolic_ptr_df,
                statistic=self.full_config.protein.partial_missing_imputation_statistic,
                highlight_groups=special_gene_groups,
            )
        )
        missing_value_correlation_spec_metabolic_only = DiagnosticOutputSpec(
            data=missing_value_correlation_plot_metabolic_only,
            save_file_name="missing_value_correlation_plot_metabolic_only",
            extensions=["html", "png"],
            data_type=go.Figure,
        )
        missing_value_correlation_plot_all_genes = create_missing_value_PTR_correlation_plot(
            base_ptr_df,
            statistic=self.full_config.protein.partial_missing_imputation_statistic,
            highlight_groups=special_gene_groups,
        )
        missing_value_correlation_spec_all_genes = DiagnosticOutputSpec(
            data=missing_value_correlation_plot_all_genes,
            save_file_name="missing_value_correlation_plot_all_genes",
            extensions=["html", "svg"],
            data_type=go.Figure,
        )
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": {
                "PTR": [
                    missing_value_correlation_spec_all_genes,
                    missing_value_correlation_spec_metabolic_only,
                ]
            },
            "artifacts": {},
            "metadata": {},
        }
        # todo:
        return new_scaffold_objects

    def after_run(
        self,
        new_scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        return {
            "outputs": {},
            "diagnostics": {},
            "artifacts": {},
            "metadata": {},
        }


STATISTIC_FUNCTIONS = {
    "mean": pd.DataFrame.mean,
    "median": pd.DataFrame.median,
    "sum": pd.DataFrame.sum,
}


@dataclass
class PlotConfig:
    point_size: int = 3
    highlight_opacity: float = 0.8
    Y_axis_unit: str = "Log10"
    Y_axis_margin: float = 0.5
    with_boxplot: bool = True
    with_percentage_bar: bool = True
    with_trendline: bool = True
    trendline_type: str = "linear"  # Options: "linear" or "poly"


def create_missing_value_PTR_correlation_plot(
    PTR_df: pd.DataFrame,
    statistic: str = "mean",
    highlight_groups: dict[str, list[str]] | None = None,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """
    Plots individual gene stats against missing counts to highlight linear decrease,
    optimized with micro-opacity for 20,000+ data points and a linear OLS trendline.
    """
    np.random.seed(999)
    if plot_config is None:
        plot_config = PlotConfig()

    # coerce to numeric and handle non-numeric gracefully
    PTR_df = PTR_df.apply(pd.to_numeric, errors="coerce")
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
        if plot_config.trendline_type == "linear":
            lr = LinearRegression()
            lr.fit(X, y)

            # Calculate R² to display in the legend/title
            r_squared = lr.score(X, y)

            # Safely extract slope regardless of y shape (1D vs 2D)
            slope = lr.coef_[0][0] if lr.coef_.ndim > 1 else lr.coef_[0]

            # Generate line endpoints based on unique X values
            x_range = np.array(
                [[result_df["missing_count"].min()], [result_df["missing_count"].max()]]
            )
            y_pred = lr.predict(x_range)

            # Format the legend name for linear
            trace_name = f"Linear Trend (R²={r_squared:.2f}, Slope={slope:.3f})"

        elif plot_config.trendline_type == "poly":
            # Fit a polynomial regression model (degree 2)
            coeffs = np.polyfit(result_df["missing_count"], result_df["stat_value"], 2)
            poly_eq = np.poly1d(coeffs)

            # Calculate R² to display in the legend/title
            missing_scalar = result_df["missing_count"].values.reshape(-1, 1)  # ty: ignore
            y_pred_poly = poly_eq(missing_scalar.flatten()).reshape(-1, 1)

            ss_res = np.sum((result_df["stat_value"] - y_pred_poly.flatten()) ** 2)
            ss_tot = np.sum((result_df["stat_value"] - np.mean(result_df["stat_value"])) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            # Generate line endpoints based on unique X values
            x_range = np.linspace(
                result_df["missing_count"].min(), result_df["missing_count"].max(), 100
            ).reshape(-1, 1)
            y_pred = poly_eq(x_range.flatten()).reshape(-1, 1)

            # Format the legend name for polynomial (omitting slope)
            trace_name = f"Polynomial(2) trend (R²={r_squared:.2f})"

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

    # percentage bar charts
    counts_per_missing = result_df["missing_count"].value_counts().sort_index()
    total_ptrs = len(result_df)
    percentages = (counts_per_missing / total_ptrs) * 100

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
    )

    #  layout
    fig.update_layout(
        title=f"Missing Value PTR Correlation (Total Rows: {total_ptrs:,})",
        xaxis_title="Number of Missing Values per Gene",
        yaxis=dict(
            title=f"Gene {statistic.capitalize()} Value ({plot_config.Y_axis_unit})",
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


if __name__ == "__main__":
    ptr_data_path = Path(
        "/home/p70088775/git/SWAPAM/data/for_SWAMP"
        "/PTR_datasets/Eraslan2019V1_human/PTRs_all__PMC6379048_eraslan.csv"
    )

    PTR_df = pd.read_csv(ptr_data_path, index_col=0)
    # take a gene every 20 genes for highlight names
    to_highlight_genes = PTR_df.index[::20].tolist()
    highlight_info = {
        "Highlighted Genes (every 20th gene)": to_highlight_genes,
    }
    plot_config = PlotConfig(
        point_size=3,
        highlight_opacity=0.8,
        Y_axis_unit="Log10",
        Y_axis_margin=0.5,
        with_boxplot=True,
        with_percentage_bar=True,
        with_trendline=True,
        trendline_type="poly",
    )
    fig = create_missing_value_PTR_correlation_plot(
        PTR_df,
        statistic="median",
        highlight_groups=highlight_info,
        plot_config=plot_config,
    )
    fig.show()
