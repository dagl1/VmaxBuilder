from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from VmaxBuilder.utils.plotting.colors import custom_colorblind_color_discrete_palette
from VmaxBuilder.utils.plotting.config import PlotConfig

COLORBLIND_COLORS = custom_colorblind_color_discrete_palette()[0]


def to_series(data: pd.DataFrame | pd.Series) -> pd.Series:
    """Generated: validation needed.

    Description:
        Convert one-column DataFrame or Series to a Series.

    Args:
        data (pd.DataFrame | pd.Series): Input values.

    Returns:
        pd.Series: Series view of input values.

    Raises:
        ValueError: If DataFrame has more than one column.
        TypeError: If input is not DataFrame or Series.
    """
    if isinstance(data, pd.Series):
        return data

    if isinstance(data, pd.DataFrame):
        if data.shape[1] != 1:
            raise ValueError("Expected DataFrame with exactly one column.")
        return data.iloc[:, 0]

    raise TypeError(f"Expected DataFrame or Series, got {type(data).__name__}.")


def match_two_samples(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Generated: validation needed.

    Description:
        Align two samples on shared index and remove null observations.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.

    Returns:
        tuple[pd.Series, pd.Series]: Matched first and second sample series.

    Raises:
        ValueError: If no overlapping non-null observations are found.
    """
    sample_1 = to_series(sample_data_1)
    sample_2 = to_series(sample_data_2)

    matched = pd.concat([sample_1, sample_2], axis=1, join="inner").dropna()
    if matched.empty:
        raise ValueError("No matching non-null observations found between two samples.")

    return matched.iloc[:, 0], matched.iloc[:, 1]


def _resolve_trendline(
    x_values: pd.Series,
    y_values: pd.Series,
    trendline_type: str,
) -> tuple[np.ndarray, np.ndarray, str]:
    x_numeric = x_values.to_numpy(dtype=float)
    y_numeric = y_values.to_numpy(dtype=float)
    x_range = np.linspace(x_numeric.min(), x_numeric.max(), 100)

    if trendline_type == "linear":
        coefficients = np.polyfit(x_numeric, y_numeric, deg=1)
        model = np.poly1d(coefficients)
        correlation = float(np.corrcoef(x_numeric, y_numeric)[0, 1])
        r_squared = correlation**2
        label = f"Linear trend (R²={r_squared:.2f})"
        return x_range, model(x_range), label

    if trendline_type in {"poly", "poly2", "quadratic"}:
        coefficients = np.polyfit(x_numeric, y_numeric, deg=2)
        model = np.poly1d(coefficients)
        y_pred = model(x_numeric)
        ss_res = np.sum((y_numeric - y_pred) ** 2)
        ss_tot = np.sum((y_numeric - np.mean(y_numeric)) ** 2)
        r_squared = 1.0 if ss_tot == 0 else float(1 - (ss_res / ss_tot))
        label = f"Quadratic trend (R²={r_squared:.2f})"
        return x_range, model(x_range), label

    raise ValueError(f"Unsupported trendline type: {trendline_type}")


def create_scatter_comparison_plot(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
    *,
    plot_config: PlotConfig | None = None,
    with_marginals: bool = False,
    with_trendline: bool = False,
    trendline_type: str | None = None,
    use_density: bool = False,
    observation_name: str = "Observations",
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Build scatter-style comparison with optional marginals and optional trendline.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.
        plot_config (PlotConfig | None): Optional plotting configuration.
        with_marginals (bool): If true, include x/y marginal histograms.
        with_trendline (bool): If true, add trendline to main panel.
        trendline_type (str | None): Trendline type. Defaults to config value.
        use_density (bool): If true, render 2D histogram as main panel.
        observation_name (str): Main trace name.

    Returns:
        go.Figure: Plotly figure object.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    x_data, y_data = match_two_samples(sample_data_1, sample_data_2)
    x_label = plot_config.x_label or x_data.name or "Sample 1"
    y_label = plot_config.y_label or y_data.name or "Sample 2"
    figure_title = plot_config.title or "Sample Comparison"

    if with_marginals:
        figure = make_subplots(
            rows=2,
            cols=2,
            row_heights=[0.2, 0.8],
            column_widths=[0.8, 0.2],
            shared_xaxes=True,
            shared_yaxes=True,
            horizontal_spacing=0.03,
            vertical_spacing=0.03,
            specs=[[{"type": "histogram"}, None], [{"type": "xy"}, {"type": "histogram"}]],
        )

        if use_density:
            figure.add_trace(
                go.Histogram2d(
                    x=x_data,
                    y=y_data,
                    colorscale="Viridis",
                    nbinsx=plot_config.histogram_nbinsx,
                    nbinsy=plot_config.histogram_nbinsy,
                    colorbar={"title": "Count"},
                    name=observation_name,
                ),
                row=2,
                col=1,
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode="markers",
                    marker={
                        "size": plot_config.point_size,
                        "opacity": plot_config.marker_opacity,
                        "color": COLORBLIND_COLORS[0],
                    },
                    name=observation_name,
                ),
                row=2,
                col=1,
            )

        figure.add_trace(
            go.Histogram(
                x=x_data,
                showlegend=False,
                marker={"color": COLORBLIND_COLORS[0]},
                nbinsx=plot_config.marginal_histogram_nbins,
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Histogram(
                y=y_data,
                showlegend=False,
                marker={"color": COLORBLIND_COLORS[1]},
                nbinsy=plot_config.marginal_histogram_nbins,
            ),
            row=2,
            col=2,
        )

        figure.update_xaxes(showticklabels=False, row=1, col=1)
        figure.update_yaxes(showticklabels=False, row=2, col=2)

        main_row = 2
        main_col = 1
    else:
        figure = go.Figure()
        if use_density:
            figure.add_trace(
                go.Histogram2d(
                    x=x_data,
                    y=y_data,
                    colorscale="Viridis",
                    nbinsx=plot_config.histogram_nbinsx,
                    nbinsy=plot_config.histogram_nbinsy,
                    colorbar={"title": "Count"},
                    name=observation_name,
                )
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode="markers",
                    marker={
                        "size": plot_config.point_size,
                        "opacity": plot_config.marker_opacity,
                        "color": COLORBLIND_COLORS[0],
                    },
                    name=observation_name,
                )
            )

        main_row = None
        main_col = None

    if with_trendline and not use_density:
        resolved_trendline_type = trendline_type or plot_config.trendline_type
        trendline_x, trendline_y, trendline_name = _resolve_trendline(
            x_data,
            y_data,
            resolved_trendline_type,
        )
        trend_trace = go.Scatter(
            x=trendline_x,
            y=trendline_y,
            mode="lines",
            name=trendline_name,
            line={"color": plot_config.trendline_color, "width": plot_config.trendline_width},
        )
        if main_row is None or main_col is None:
            figure.add_trace(trend_trace)
        else:
            figure.add_trace(trend_trace, row=main_row, col=main_col)

    if main_row is None or main_col is None:
        figure.update_xaxes(title_text=x_label)
        figure.update_yaxes(title_text=y_label)
    else:
        figure.update_xaxes(title_text=x_label, row=main_row, col=main_col)
        figure.update_yaxes(title_text=y_label, row=main_row, col=main_col)

    figure.update_layout(
        title=figure_title,
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height if not with_marginals else max(plot_config.height, 820),
    )
    return figure


def create_overlaid_histogram(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
    *,
    plot_config: PlotConfig | None = None,
    sample_names: tuple[str, str] = ("Sample 1", "Sample 2"),
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Create overlaid histograms for two aligned sample vectors.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.
        plot_config (PlotConfig | None): Optional plotting configuration.
        sample_names (tuple[str, str]): Display names for both samples.

    Returns:
        go.Figure: Plotly figure.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    sample_1, sample_2 = match_two_samples(sample_data_1, sample_data_2)

    figure = go.Figure()
    figure.add_trace(
        go.Histogram(
            x=sample_1,
            name=sample_names[0],
            opacity=0.75,
            marker={"color": COLORBLIND_COLORS[0]},
            nbinsx=plot_config.histogram_nbinsx,
        )
    )
    figure.add_trace(
        go.Histogram(
            x=sample_2,
            name=sample_names[1],
            opacity=0.75,
            marker={"color": COLORBLIND_COLORS[1]},
            nbinsx=plot_config.histogram_nbinsx,
        )
    )
    figure.update_layout(
        barmode="overlay",
        title=plot_config.title or "Overlaid Histogram",
        xaxis_title=plot_config.x_label,
        yaxis_title=plot_config.y_label or plot_config.histogram_axis_type.capitalize(),
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
    )
    return figure


def create_overlaid_cdf(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
    *,
    plot_config: PlotConfig | None = None,
    sample_names: tuple[str, str] = ("Sample 1", "Sample 2"),
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Create overlaid empirical CDF curves for two aligned sample vectors.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.
        plot_config (PlotConfig | None): Optional plotting configuration.
        sample_names (tuple[str, str]): Display names for both samples.

    Returns:
        go.Figure: Plotly figure.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    sample_1, sample_2 = match_two_samples(sample_data_1, sample_data_2)

    cdf_df = pd.DataFrame(
        {
            "value": pd.concat([sample_1, sample_2], ignore_index=True),
            "sample": [sample_names[0]] * len(sample_1) + [sample_names[1]] * len(sample_2),
        }
    )

    figure = px.ecdf(
        cdf_df,
        x="value",
        color="sample",
        title=plot_config.title or "Overlaid CDF",
        markers=True,
        lines=True,
    )
    for trace, color in zip(figure.data, COLORBLIND_COLORS[:2], strict=False):
        trace.update(line={"color": color}, marker={"color": color})

    figure.update_layout(
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
        xaxis_title=plot_config.x_label,
        yaxis_title=plot_config.y_label or "Cumulative probability",
        legend_title=plot_config.legend_title or None,
    )
    return figure


def create_difference_boxplot(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
    *,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Create boxplot of positive and negative paired differences.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.
        plot_config (PlotConfig | None): Optional plotting configuration.

    Returns:
        go.Figure: Plotly figure.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    sample_1, sample_2 = match_two_samples(sample_data_1, sample_data_2)
    difference = sample_1 - sample_2

    positive = difference[difference > 0]
    negative = difference[difference < 0]

    figure = go.Figure()
    figure.add_trace(
        go.Box(
            y=positive,
            name=plot_config.difference_positive_name,
            boxmean="sd",
            boxpoints="all",
            jitter=0.3,
            pointpos=0,
            marker={"color": COLORBLIND_COLORS[0]},
        )
    )
    figure.add_trace(
        go.Box(
            y=negative,
            name=plot_config.difference_negative_name,
            boxmean="sd",
            boxpoints="all",
            jitter=0.3,
            pointpos=0,
            marker={"color": COLORBLIND_COLORS[1]},
        )
    )
    figure.add_hline(y=0, line_dash="dash", line_width=1)

    figure.update_layout(
        title=plot_config.title or "Difference Boxplot",
        xaxis_title="",
        yaxis_title=plot_config.y_label or "Difference (Sample 1 - Sample 2)",
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
    )
    return figure


def create_rank_scatter_plot(
    sample_data_1: pd.DataFrame | pd.Series,
    sample_data_2: pd.DataFrame | pd.Series,
    *,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Compare rank ordering between two samples using a rank-rank scatter.

    Args:
        sample_data_1 (pd.DataFrame | pd.Series): First sample.
        sample_data_2 (pd.DataFrame | pd.Series): Second sample.
        plot_config (PlotConfig | None): Optional plotting configuration.

    Returns:
        go.Figure: Plotly figure.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    sample_1, sample_2 = match_two_samples(sample_data_1, sample_data_2)
    sample_1_rank = sample_1.rank(ascending=plot_config.rank_ascending)
    sample_2_rank = sample_2.rank(ascending=plot_config.rank_ascending)

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=sample_1_rank,
            y=sample_2_rank,
            mode="markers",
            marker={
                "size": plot_config.point_size,
                "opacity": plot_config.marker_opacity,
                "color": COLORBLIND_COLORS[0],
            },
            name="Ranks",
            text=sample_1.index.astype(str),
            hovertemplate=(
                "Reaction: %{text}<br>"
                "Rank (sample 1): %{x:.0f}<br>"
                "Rank (sample 2): %{y:.0f}<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        title=plot_config.title or "Rank Comparison",
        xaxis_title=plot_config.x_label or "Rank (sample 1)",
        yaxis_title=plot_config.y_label or "Rank (sample 2)",
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
    )
    return figure


def create_dual_axis_bar_plot(
    labels: Sequence[str],
    left_values: Sequence[float],
    right_values: Sequence[float],
    *,
    left_name: str,
    right_name: str,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """Generated: validation needed.

    Description:
        Create dual-axis bar/line chart for two aligned vectors.

    Args:
        labels (Sequence[str]): Category labels.
        left_values (Sequence[float]): Left axis bar values.
        right_values (Sequence[float]): Right axis line values.
        left_name (str): Legend name for left-axis bars.
        right_name (str): Legend name for right-axis line.
        plot_config (PlotConfig | None): Optional plotting configuration.

    Returns:
        go.Figure: Plotly figure.

    Raises:
        ValueError: If input sequence lengths do not match.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    if not (len(labels) == len(left_values) == len(right_values)):
        raise ValueError("labels, left_values, and right_values must have the same length.")

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=list(labels),
            y=list(left_values),
            name=left_name,
            marker={"color": COLORBLIND_COLORS[0]},
            opacity=0.8,
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=list(labels),
            y=list(right_values),
            mode="lines+markers",
            name=right_name,
            marker={"color": COLORBLIND_COLORS[1]},
            line={"color": COLORBLIND_COLORS[1], "width": 2},
        ),
        secondary_y=True,
    )

    figure.update_layout(
        title=plot_config.title or "Dual-Axis Comparison",
        template="plotly_white",
        width=plot_config.width,
        height=plot_config.height,
        xaxis_title=plot_config.x_label,
    )
    figure.update_yaxes(title_text=plot_config.y_label or left_name, secondary_y=False)
    figure.update_yaxes(title_text=right_name, secondary_y=True)
    return figure


if __name__ == "__main__":
    demo_index = [f"item_{index:03d}" for index in range(1, 401)]
    np.random.seed(7)

    sample_a = pd.Series(
        np.random.lognormal(mean=1.8, sigma=0.45, size=400), index=demo_index
    )
    sample_b = sample_a * np.random.normal(loc=1.02, scale=0.12, size=400)

    sample_a_log10 = sample_a.apply(lambda value: np.log10(value) if value > 0 else np.nan)
    sample_b_log10 = sample_b.apply(lambda value: np.log10(value) if value > 0 else np.nan)

    base_plot_config = PlotConfig(
        title="Scatter comparison",
        width=1100,
        height=760,
        x_label="Sample A (log10)",
        y_label="Sample B (log10)",
        point_size=5,
        histogram_nbinsx=55,
        histogram_nbinsy=55,
    )

    scatter_plot = create_scatter_comparison_plot(
        sample_a_log10,
        sample_b_log10,
        plot_config=base_plot_config,
        with_marginals=False,
        with_trendline=True,
        trendline_type="linear",
    )
    scatter_with_marginals_plot = create_scatter_comparison_plot(
        sample_a_log10,
        sample_b_log10,
        plot_config=PlotConfig(
            title="Scatter comparison with marginals",
            width=1200,
            height=820,
            x_label="Sample A (log10)",
            y_label="Sample B (log10)",
            point_size=5,
            marker_opacity=0.65,
            marginal_histogram_nbins=45,
        ),
        with_marginals=True,
        with_trendline=True,
        trendline_type="poly2",
    )

    histogram_plot = create_overlaid_histogram(
        sample_a_log10,
        sample_b_log10,
        plot_config=PlotConfig(title="Overlaid histogram", x_label="Value (log10)"),
    )
    cdf_plot = create_overlaid_cdf(
        sample_a_log10,
        sample_b_log10,
        plot_config=PlotConfig(title="Overlaid CDF", x_label="Value (log10)"),
    )
    difference_plot = create_difference_boxplot(
        sample_a_log10,
        sample_b_log10,
        plot_config=PlotConfig(title="Difference distribution"),
    )
    rank_plot = create_rank_scatter_plot(
        sample_a_log10,
        sample_b_log10,
        plot_config=PlotConfig(title="Rank-rank comparison", point_size=6),
    )

    shift_df = pd.DataFrame(
        {
            "reaction": [f"R_{index:03d}" for index in range(1, 16)],
            "delta": np.random.uniform(-0.8, 0.8, 15),
            "abs_delta": np.random.uniform(0.0, 0.8, 15),
        }
    )
    dual_axis_plot = create_dual_axis_bar_plot(
        labels=shift_df["reaction"].tolist(),
        left_values=shift_df["delta"].tolist(),
        right_values=shift_df["abs_delta"].tolist(),
        left_name="Signed shift",
        right_name="Absolute shift",
        plot_config=PlotConfig(
            title="Top reaction shifts",
            x_label="Reaction",
            y_label="Shift (log10)",
            width=1200,
            height=720,
        ),
    )

    scatter_plot.show()
    scatter_with_marginals_plot.show()
    histogram_plot.show()
    cdf_plot.show()
    difference_plot.show()
    rank_plot.show()
    dual_axis_plot.show()
