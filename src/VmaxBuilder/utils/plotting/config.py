from dataclasses import dataclass


@dataclass
class PlotConfig:
    title: str = ""
    width: int = 1000
    height: int = 700
    x_label: str = ""
    y_label: str = ""
    legend_title: str = ""

    point_size: int = 3
    highlight_opacity: float = 0.8
    marker_opacity: float = 0.7

    x_axis_title_size: int = 14
    x_axis_label_size: int = 12
    x_axis_title: str = ""

    y_axis_title_size: int = 14
    y_axis_label_size: int = 12
    y_axis_margin: float = 0.5

    Y_axis_unit: str = "Log10"
    Y_axis_margin: float = 0.5

    with_marginals: bool = False
    marginal_histogram_nbins: int = 40

    with_scatter: bool = True
    with_boxplot: bool = True
    with_percentage_bar: bool = True
    with_trendline: bool = True
    trendline_type: str = "linear"  # Options: "linear" or "poly"

    trendline_color: str = "rgba(0, 0, 0, 0.8)"
    trendline_width: int = 2

    Y_transformation: str = "log10"  # Options: "linear", "log", "log10", "sqrt"
    histogram_axis_type: str = "probability"  # "count", "probability"
    histogram_nbinsx: int = 50  # Number of bins for histogram
    histogram_nbinsy: int = 50  # Number of bins for histogram

    histogram_base_overlay_opacity: float = 0.55  # if only 1 group then is 1,
    # otherwise start from this value (at 2 groups) and then reduce with an
    # exponential decay based on the number of groups to avoid

    rank_ascending: bool = False
    difference_positive_name: str = "Positive Difference"
    difference_negative_name: str = "Negative Difference"

    y_axis_title: str = "Value"
