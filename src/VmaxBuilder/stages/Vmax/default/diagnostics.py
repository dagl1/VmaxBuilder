from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from VmaxBuilder.base.classes import BaseImplementationDiagnostics
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.utils.plotting.colors import (
    custom_colorblind_color_discrete_palette,
    rgb_to_rgba,
    yield_discrete_colorblind_color,
)
from VmaxBuilder.utils.plotting.config import PlotConfig
from VmaxBuilder.utils.transformations import (
    calculate_conversion_factor_per_sample_from_metabolic_protein_abundance,
)

COLORBLIND_COLORS = custom_colorblind_color_discrete_palette()[4]

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
        Model-stage diagnostics for preparing reaction alluvial data.
    """

    DIAGNOSTICS_NAME = "Vmax"

    def __init__(self, full_config: FullConfig):
        """Generated: validation needed.

        Description:
            Initialise model diagnostics state and logger.

        Args:
            full_config (FullConfig): Full pipeline configuration.

        Modifies:
            Internal diagnostics cache and base logger state.
        """
        super().__init__(full_config)

    def before_run(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        return {"outputs": {}, "diagnostics": {}, "metadata": {}, "artifacts": {}}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        # add in flux transformation

        # get
        # IFP_sample_abundance_dict
        # processed_expression_df
        # imputed_PTR_df

        # imputed_PTR_df = scaffold.get_scaffold_value("imputed_PTR_df")
        # resolved_sample_type_map = scaffold.get_scaffold_value("resolved_sample_type_map")
        #
        # protein_abundance_df = scaffold.get_scaffold_value("protein_abundance_df")
        # all_genes_protein_abundance_df = scaffold.get_scaffold_value(
        #     "all_genes_protein_abundance_df"
        # )
        #
        # IFP_sample_abundance_dict = scaffold.get_scaffold_value("IFP_sample_abundance_dict")
        # IFP_sample_abundance_dict_without_trimming = scaffold.get_scaffold_value(
        #     "IFP_sample_abundance_dict_without_trimming"
        # )
        # reaction_capacity_df = scaffold.get_scaffold_value("reaction_capacity_df")
        # reaction_capacity_df_without_trimming = scaffold.get_scaffold_value(
        #     "reaction_capacity_df_without_trimming"
        # )

        diagnostics = {"Vmax": []}
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": diagnostics,
            "metadata": {},
            "artifacts": {},
        }
        return new_scaffold_objects

    def amend_IFP_dicts_with_expression_and_PTR_data(
        self,
        ifp_dicts: dict[str, dict[str, Any]],
        processed_expression_df: pd.DataFrame,
        imputed_PTR_df: pd.DataFrame,
        protein_abundance_df: pd.DataFrame,
        resolved_sample_type_map: dict[str, str],
    ):
        for sample in resolved_sample_type_map.keys():
            sample_type = resolved_sample_type_map[sample]
            sample_specific_PTR = imputed_PTR_df[sample_type]
            sample_specific_expression_df = processed_expression_df[sample]
            protein_specific_abundance_df = protein_abundance_df[sample]
            for _reaction_id, reaction_data in ifp_dicts.items():
                reaction_genes = reaction_data["genes"]
                for gene_id, _gene_data in reaction_genes.items():
                    expression_value = sample_specific_expression_df.at[gene_id]
                    ptr_value = sample_specific_PTR.at[gene_id]
                    protein_abundance = protein_specific_abundance_df.at[gene_id]
                    reaction_data["genes"][gene_id]["expression"] = expression_value
                    reaction_data["genes"][gene_id]["PTR"] = ptr_value
                    reaction_data["genes"][gene_id]["abundance"] = protein_abundance
                for ifp_id, ifp_data in reaction_data["IFPs"].items():
                    # get expression and PTR for this IFP in this sample
                    IFP_Vmax = ifp_data["Vmax"]
                    genes = ifp_data["genes"]
                    for gene_id, _gene_data in genes:
                        expression_value = sample_specific_expression_df.at[gene_id]
                        ptr_value = sample_specific_PTR.at[gene_id]  # same here
                        protein_abundance = protein_specific_abundance_df.at[gene_id]
                        ifp_data["genes"][ifp_id]["expression"] = expression_value
                        ifp_data["genes"][ifp_id]["PTR"] = ptr_value
                        ifp_data["genes"][ifp_id]["abundance"] = protein_abundance
                        ifp_data["genes"][ifp_id]["expression_contribution_to_IFP_Vmax"] = (
                            expression_value / IFP_Vmax
                        )
                        ifp_data["genes"][ifp_id]["PTR_contribution_to_IFP_Vmax"] = (
                            ptr_value / IFP_Vmax
                        )
                        ifp_data["genes"][ifp_id]["abundance_contribution_to_IFP_Vmax"] = (
                            protein_abundance / IFP_Vmax
                        )
            return ifp_dicts

        pass

    def _one_to_one_comparision_plots(
        self,
    ):
        # hexbin scatter plot + marginal histograms
        # differnece boxplot
        # rank scatter
        pass

    def _compare_two_reaction_activity_dfs(
        self, df1: pd.DataFrame, df2: pd.DataFrame
    ) -> pd.DataFrame:
        pass

    def _plot_reaction_activity(
        self, df1: pd.DataFrame, df2: pd.DataFrame, title: str
    ) -> None:
        pass

    def _plot_trimming_effects_on_reaction_activity(
        self, df1: pd.DataFrame, df2: pd.DataFrame, title: str, top_n: int = 10
    ) -> None:
        # reaction activity plots (cdf /histogram) with top n shifted reactions
        # + showing how median value changed

        pass

    def correlate_kcat_and_abundance_to_vmax(self, scaffold: Scaffold):
        # todo:
        # calculate the correlation between the correlations of Kcat and abundance to Vmax
        # do the same for abundance contribution vs vmax contribution to total vmax
        # plot how the kcat predictions look in IFPs that make up the majority of a total Vmax
        # For 3 way correlation, we  can use VIF
        #
        pass

    def create_n_IFP_contribution_buckets(self, scaffold: Scaffold):
        # todo:
        # categorise reactions into buckets depending on how their IFP contributions differ.
        # Then per bucket, show the average contribution of the nth highest contributors
        # buckets are defined as majoirty (90% by one IFP)
        # or balanced (no IFP contributes more than 50%)
        # we look at whethher high kcat correlates with high contribution

        pass

    def plot_static_kcat_or_abundance_effects(self, scaffold: Scaffold):
        # todo:
        # plot at each level what happens if we would substitute abundance or kcat with
        # a static value
        # so scatter marginal plot and rank plot + difference boxplot for each level
        pass

    def plot_overlaid_histograms_and_cdfs(
        self,
        sample_data_1: pd.DataFrame,
        sample_data_2: pd.DataFrame,
        plot_config: PlotConfig,
    ):
        _overlaid_histogram = self._overlaid_histogram(sample_data_1, sample_data_2)
        _overlaid_cdf = self._overlaid_cdf(sample_data_1, sample_data_2)

        # overlaid histograms
        # overlaid cdfs for different samples
        pass

    def _to_series(
        self,
        data: pd.DataFrame | pd.Series,
    ) -> pd.Series:
        """Convert a DataFrame/Series input into a single Series."""
        if isinstance(data, pd.Series):
            return data

        if isinstance(data, pd.DataFrame):
            if data.shape[1] != 1:
                raise ValueError("Expected a DataFrame with exactly one column.")
            return data.iloc[:, 0]

        raise TypeError(f"Expected pd.DataFrame or pd.Series, got {type(data).__name__}")

    def _overlaid_histogram(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        sample_1 = self._to_series(sample_data_1)
        sample_2 = self._to_series(sample_data_2)

        fig = go.Figure()

        fig.add_trace(
            go.Histogram(
                x=sample_1,
                name="Sample 1",
                opacity=0.75,
                marker=dict(color=COLORBLIND_COLORS[0]),
            )
        )

        fig.add_trace(
            go.Histogram(
                x=sample_2,
                name="Sample 2",
                opacity=0.75,
                marker=dict(color=COLORBLIND_COLORS[1]),
            )
        )

        fig.update_layout(
            barmode="overlay",
            title=getattr(plot_config, "title", "Overlaid Histogram"),
            width=getattr(plot_config, "width", 800),
            height=getattr(plot_config, "height", 600),
        )

        return fig

    def _prepare_two_samples(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
    ) -> pd.DataFrame:
        sample_1 = self._to_series(sample_data_1).dropna()
        sample_2 = self._to_series(sample_data_2).dropna()

        return pd.DataFrame(
            {
                "value": pd.concat(
                    [sample_1, sample_2],
                    ignore_index=True,
                ),
                "sample": (["Sample 1"] * len(sample_1) + ["Sample 2"] * len(sample_2)),
            }
        )

    def _overlaid_cdf(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
        title: str,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        df = self._prepare_two_samples(
            sample_data_1,
            sample_data_2,
        )

        fig = px.ecdf(
            df,
            x="value",
            color="sample",
            title=title,
            markers=True,
            lines=True,
        )

        fig.update_traces(
            marker=dict(size=5),
        )

        for trace, color in zip(
            fig.data,
            COLORBLIND_COLORS[:2],
            strict=False,
        ):
            trace.update(
                line=dict(color=color),
                marker=dict(color=color),
            )

        fig.update_layout(
            width=getattr(plot_config, "width", 800),
            height=getattr(plot_config, "height", 600),
            xaxis_title=getattr(plot_config, "x_label", None),
            yaxis_title="Cumulative probability",
            legend_title=None,
        )

        return fig

    def _scatter_plot_with_marginal_histograms(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        x = self._to_series(sample_data_1).dropna()
        y = self._to_series(sample_data_2).dropna()

        if len(x) != len(y):
            raise ValueError(
                "sample_data_1 and sample_data_2 must contain "
                "the same number of observations."
            )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                marker=dict(
                    color=COLORBLIND_COLORS[0],
                    opacity=0.7,
                ),
                name="Observations",
            )
        )

        # Trendline
        z = np.polyfit(x, y, 1)
        trendline = np.poly1d(z)

        x_sorted = np.sort(x)

        fig.add_trace(
            go.Scatter(
                x=x_sorted,
                y=trendline(x_sorted),
                mode="lines",
                line=dict(
                    color=rgb_to_rgba(COLORBLIND_COLORS[1], 0.8),
                    width=2,
                ),
                name="Trendline",
            )
        )

        fig.update_layout(
            title=getattr(
                plot_config,
                "title",
                "Scatter Plot",
            ),
            width=getattr(
                plot_config,
                "width",
                800,
            ),
            height=getattr(
                plot_config,
                "height",
                600,
            ),
            xaxis_title=getattr(
                plot_config,
                "x_label",
                x.name or "Sample 1",
            ),
            yaxis_title=getattr(
                plot_config,
                "y_label",
                y.name or "Sample 2",
            ),
        )

        return fig

    def _difference_boxplot(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        # Convert DataFrame / Series to Series
        sample_1 = self._to_series(sample_data_1)
        sample_2 = self._to_series(sample_data_2)

        # Match observations by index
        matched = pd.concat(
            [sample_1, sample_2],
            axis=1,
            join="inner",
        )

        matched.columns = ["sample_1", "sample_2"]

        # Difference = Sample 1 - Sample 2
        difference = matched["sample_1"] - matched["sample_2"]

        positive = difference[difference > 0]
        negative = difference[difference < 0]

        fig = go.Figure()

        fig.add_trace(
            go.Box(
                y=positive,
                name="Positive Difference",
                marker=dict(
                    color=rgb_to_rgba(
                        COLORBLIND_COLORS[0],
                        0.7,
                    )
                ),
                boxmean="sd",
                boxpoints="all",
                jitter=0.3,
                pointpos=0,
            )
        )

        fig.add_trace(
            go.Box(
                y=negative,
                name="Negative Difference",
                marker=dict(
                    color=rgb_to_rgba(
                        COLORBLIND_COLORS[1],
                        0.7,
                    )
                ),
                boxmean="sd",
                boxpoints="all",
                jitter=0.3,
                pointpos=0,
            )
        )

        fig.add_hline(
            y=0,
            line_dash="dash",
            line_width=1,
        )

        fig.update_layout(
            title=getattr(
                plot_config,
                "title",
                "Difference Boxplot",
            ),
            width=getattr(
                plot_config,
                "width",
                800,
            ),
            height=getattr(
                plot_config,
                "height",
                600,
            ),
            yaxis_title="Difference (Sample 1 − Sample 2)",
            xaxis_title=None,
        )

        return fig

    def _rank_scatter_plot(
        self,
        sample_data_1: pd.DataFrame,
        sample_data_2: pd.DataFrame,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        df = pd.concat([sample_data_1, sample_data_2], axis=0)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                df.rank(),
                mode="markers",
                marker=dict(color=COLORBLIND_COLORS[0]),
                name="Rank Scatter",
            )
        )
        fig.update_layout(
            title=getattr(plot_config, "title", "Rank Scatter Plot"),
            width=getattr(plot_config, "width", 800),
            height=getattr(plot_config, "height", 600),
        )

        return fig

    def _hexbin_scatter_plot_with_marginal_histograms(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
        plot_config: PlotConfig | None = None,
    ):
        if plot_config is None:
            plot_config = PlotConfig()

        # Convert DataFrame / Series to Series
        x_data = self._to_series(sample_data_1)
        y_data = self._to_series(sample_data_2)

        # Match observations by index
        matched = pd.concat(
            [x_data, y_data],
            axis=1,
            join="inner",
        ).dropna()

        x_data = matched.iloc[:, 0]
        y_data = matched.iloc[:, 1]

        if len(x_data) == 0:
            raise ValueError(
                "No matching non-null observations found between "
                "sample_data_1 and sample_data_2."
            )

        # Create layout
        fig = make_subplots(
            rows=2,
            cols=2,
            row_heights=[0.2, 0.8],
            column_widths=[0.8, 0.2],
            shared_xaxes=True,
            shared_yaxes=True,
            horizontal_spacing=0.02,
            vertical_spacing=0.02,
            specs=[
                [{"type": "histogram"}, None],
                [{"type": "histogram2d"}, {"type": "histogram"}],
            ],
        )

        # Main 2D histogram
        fig.add_trace(
            go.Histogram2d(
                x=x_data,
                y=y_data,
                colorscale="Viridis",
                nbinsx=getattr(
                    plot_config,
                    "histogram_nbinsx",
                    30,
                ),
                nbinsy=getattr(
                    plot_config,
                    "histogram_nbinsy",
                    30,
                ),
                colorbar=dict(
                    title="Count",
                ),
            ),
            row=2,
            col=1,
        )

        # X marginal
        fig.add_trace(
            go.Histogram(
                x=x_data,
                nbinsx=getattr(
                    plot_config,
                    "histogram_nbinsx",
                    30,
                ),
                marker=dict(
                    color=COLORBLIND_COLORS[0],
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # Y marginal
        fig.add_trace(
            go.Histogram(
                y=y_data,
                nbinsy=getattr(
                    plot_config,
                    "histogram_nbinsy",
                    30,
                ),
                marker=dict(
                    color=COLORBLIND_COLORS[1],
                ),
                showlegend=False,
            ),
            row=2,
            col=2,
        )

        fig.update_layout(
            title=getattr(
                plot_config,
                "title",
                "Density Scatter Analysis",
            ),
            width=getattr(
                plot_config,
                "width",
                800,
            ),
            height=getattr(
                plot_config,
                "height",
                800,
            ),
            barmode="overlay",
        )

        # Hide marginal tick labels
        fig.update_xaxes(
            showticklabels=False,
            row=1,
            col=1,
        )

        fig.update_yaxes(
            showticklabels=False,
            row=2,
            col=2,
        )

        # Main axis labels
        fig.update_xaxes(
            title_text=getattr(
                plot_config,
                "x_label",
                x_data.name or "Sample 1",
            ),
            row=2,
            col=1,
        )

        fig.update_yaxes(
            title_text=getattr(
                plot_config,
                "y_label",
                y_data.name or "Sample 2",
            ),
            row=2,
            col=1,
        )

        return fig

    def _match_two_samples(
        self,
        sample_data_1: pd.DataFrame | pd.Series,
        sample_data_2: pd.DataFrame | pd.Series,
    ) -> tuple[pd.Series, pd.Series]:
        sample_1 = self._to_series(sample_data_1)
        sample_2 = self._to_series(sample_data_2)

        matched = pd.concat(
            [sample_1, sample_2],
            axis=1,
            join="inner",
        ).dropna()

        return matched.iloc[:, 0], matched.iloc[:, 1]

        # we want to be able to do the following plots;
        # so we need to generate this data:
        ##### gene-substrate predictions
        ##### main-substrate predictions
        ##### IFP-dominant kcat prediction
        ##### IFP-allocation
        ##### reaction-summed allocation
        ##### reaction-summed vmax
        ##### reaction contribution per IFP (for both kcat and allocation)


if __name__ == "__main__":
    # Example usage of the VmaxDiagnostics class
    from pathlib import Path

    diagnostics = object.__new__(VmaxDiagnostics)

    base_dir = Path(
        r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    )
    reaction_activity_path = base_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"
    reaction_activty_no_trimming_path = (
        base_dir / "artifacts" / "Vmax_stage" / "reaction_capacity_df_without_trimming.csv"
    )
    reaction_activity_df = pd.read_csv(reaction_activity_path, index_col=0)
    untrimmed_reaction_activity_df = pd.read_csv(
        reaction_activty_no_trimming_path, index_col=0
    )
    # take first sample of both
    reaction_activity_df = reaction_activity_df.iloc[:, :1]
    untrimmed_reaction_activity_df = untrimmed_reaction_activity_df.iloc[:, :1]

    # transform both to log10 scale
    reaction_activity_df = reaction_activity_df.applymap(
        lambda x: None if pd.isna(x) or x <= 0 else np.log10(x)
    )
    untrimmed_reaction_activity_df = untrimmed_reaction_activity_df.applymap(
        lambda x: None if pd.isna(x) or x <= 0 else np.log10(x)
    )

    # Create a hexbin scatter plot with marginal histograms
    hexbin_fig = diagnostics._hexbin_scatter_plot_with_marginal_histograms(
        reaction_activity_df, untrimmed_reaction_activity_df
    )

    scatter_fig = diagnostics._scatter_plot_with_marginal_histograms(
        reaction_activity_df, untrimmed_reaction_activity_df
    )

    boxplot_fig = diagnostics._difference_boxplot(
        reaction_activity_df, untrimmed_reaction_activity_df
    )
    # rank_fig = diagnostics._rank_scatter_plot(
    #     reaction_activity_df, untrimmed_reaction_activity_df
    # )
    # hexbin_fig.show()
    # scatter_fig.show()
    boxplot_fig.show()
    # rank_fig.show()
