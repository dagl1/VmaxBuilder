from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.utils.custom_logging import CustomLogger


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
        base_ptr_df = scaffold.get_scaffold_value("PTR_df")
        if not isinstance(base_ptr_df, pd.DataFrame):
            raise ValueError(
                "PTR_df is not a DataFrame. "
                "Please ensure that the PTR data is loaded correctly."
            )
        correlation_plot = self.create_diagnostics_outputs(
            create_missing_value_PTR_correlation_plot,
            save_file_name="missing_value_correlation_plot.html",
            extensions=["html", "png"],
            data_type=go.Figure,
        )(
            base_ptr_df,
            statistic=self.full_config.protein.partial_missing_imputation_statistic,
        )
        new_scaffold_objects = {
            "output": {},
            "diagnostics": {"PTR": {"missing_value_correlation_plot": correlation_plot}},
            "artifacts": {},
            "metadata": {},
        }
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


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def rgb_to_rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    """Convert RGB tuple to RGBA string."""
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"


# rewrite as only rgba
COLORS_HEX = {
    "red_hex": "#FF0000",  # Standard red color
    "dark_purple_hex": "#800080",  # Dark purple for highlights
    "lightred_hex": "#FF6F21",  # A visually distinct light red color,
    "black_hex": "#000000",  # Black for trendline and boxplot
    "white_hex": "#FFFFFF",  # White for background
    "lightblue_hex": "#1F77B4",  # Light blue for scatter points
    "orange_hex": "#FFA500",  # Orange for background bars
}
COLORS_RGB = {name: hex_to_rgb(hex_color) for name, hex_color in COLORS_HEX.items()}


@dataclass
class PlotConfig:
    point_size: int = 3
    highlight_opacity: float = 0.8
    Y_axis_unit: str = "Log10"
    Y_axis_margin: float = 0.5


def create_missing_value_PTR_correlation_plot(
    PTR_df: pd.DataFrame,
    statistic: str = "mean",
    highlight_info: dict[str, list[str] | str] | None = None,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """
    Plots individual gene stats against missing counts to highlight linear decrease,
    optimized with micro-opacity for 20,000+ data points and a linear OLS trendline.
    """
    np.random.seed(999)
    if plot_config is None:
        plot_config = PlotConfig()
    highlight_genes = None
    highlight_title = None
    if highlight_info:
        highlight_genes = highlight_info.get("genes", None)
        highlight_title = highlight_info.get("title", None)

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

    if highlight_genes:
        highlight_df = result_df.loc[highlight_genes]
        highlight_jitter = np.random.uniform(-0.15, 0.15, len(highlight_df))
        highlight_name = (
            f"{highlight_title} ({len(highlight_df):,})"
            if highlight_title
            else f"Highlighted Genes ({len(highlight_df):,})"
        )

        non_highlight_df = result_df.drop(highlight_genes, errors="ignore")
        non_highlight_jitter = np.random.uniform(-0.15, 0.15, len(non_highlight_df))
        non_highlight_name = f"Non-Highlighted Genes ({len(non_highlight_df):,})"

        # on hover we want to highlight all values of this highlight group
        # as well as provide the gene name
        #
        fig.add_trace(
            go.Scatter(
                x=highlight_df["missing_count"] + highlight_jitter,
                y=highlight_df["stat_value"],
                mode="markers",
                name=highlight_name,
                marker=dict(
                    size=plot_config.point_size + 1,
                    color=rgb_to_rgba(COLORS_RGB["dark_purple_hex"], 0.8),
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
    X = result_df["missing_count"].values.reshape(-1, 1)
    y = result_df["stat_value"].values.reshape(-1, 1)

    lr = LinearRegression()
    lr.fit(X, y)

    # Calculate R² to display in the legend/title
    r_squared = lr.score(X, y)
    slope = lr.coef_[0][0]

    # Generate line endpoints based on unique X values
    x_range = np.array(
        [[result_df["missing_count"].min()], [result_df["missing_count"].max()]]
    )
    y_pred = lr.predict(x_range)

    fig.add_trace(
        go.Scatter(
            x=x_range.flatten(),
            y=y_pred.flatten(),
            mode="lines",
            name=f"Global Trend (R²={r_squared:.2f}, Slope={slope:.3f})",
            line=dict(
                color=rgb_to_rgba(COLORS_RGB["lightred_hex"], 0.8), width=2, dash="dash"
            ),
        )
    )

    # percentage bar charts
    counts_per_missing = result_df["missing_count"].value_counts().sort_index()
    total_ptrs = len(result_df)
    percentages = (counts_per_missing / total_ptrs) * 100

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
        "genes": to_highlight_genes,
        "title": "Highlighted Genes (every 20th gene)",
    }
    fig = create_missing_value_PTR_correlation_plot(
        PTR_df, statistic="median", highlight_info=highlight_info
    )
    fig.show()
