import colorsys
from typing import Any, cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from cobra import Model

from VmaxBuilder.base.classes import BaseImplementationDiagnostics, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.Kcat.Kcat_utils import (
    GeneMainSubstratePrediction,
    GeneSubstratePrediction,
    ReactionMainSubstratePrediction,
)
from VmaxBuilder.utils.extra_utils import _get_reaction_compartments, get_transport_reactions
from VmaxBuilder.utils.plotting.alluvial import (
    create_alluvial_plot,
    prepare_alluvial_plot_data,
)
from VmaxBuilder.utils.plotting.colors import (
    COLORS_RGB,
    custom_colorblind_color_discrete_palette,
    rgb_to_rgba,
    yield_discrete_colorblind_color,
)
from VmaxBuilder.utils.plotting.config import PlotConfig
from VmaxBuilder.utils.plotting.trendline import _create_trendline

COLORS = custom_colorblind_color_discrete_palette()
COLORBLIND_COLORS_RGB = COLORS[4]  # RGB format for Plotly


class GeneSubstratePredictionDiagnostics(BaseImplementationDiagnostics):
    DIAGNOSTICS_NAME = "gene_substrate_prediction"

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
        """Generated: validation needed.

        Description:
            Reset cached diagnostics before stage execution.

        Args:
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Empty diagnostics mapping.

        Modifies:
            Cached diagnostics state.
        """
        return {}

    def after_run(
        self,
        scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        adjusted_irreversible_cobra_model = cast(
            Model, scaffold.get_scaffold_value("adjusted_irreversible_cobra_model")
        )
        imputed_per_gene_per_reaction_main_substrate_predictions = cast(
            dict[str, ReactionMainSubstratePrediction],
            scaffold.get_scaffold_value(
                "imputed_per_gene_per_reaction_main_substrate_predictions"
            ),
        )
        before_imputation_per_gene_per_reaction_main_substrate_predictions = cast(
            dict[str, ReactionMainSubstratePrediction],
            scaffold.get_scaffold_value(
                "before_imputation_per_gene_per_reaction_main_substrate_predictions"
            ),
        )

        imputed_gene_substrate_predictions = cast(
            dict[str, dict[str, GeneSubstratePrediction]],
            scaffold.get_scaffold_value("imputed_gene_substrate_predictions"),
        )

        before_imputation_gene_substrate_predictions = cast(
            dict[str, dict[str, GeneSubstratePrediction]],
            scaffold.get_scaffold_value("before_imputation_gene_substrate_predictions"),
        )
        plot_config = PlotConfig(
            histogram_nbinsx=80,
            Y_transformation="linear",  # Options: "linear", "log", "log10", "sqrt"
        )

        ## plots
        before_imputation_reaction_plots = self._create_plots(
            before_imputation_per_gene_per_reaction_main_substrate_predictions,
            before_imputation_gene_substrate_predictions,
            plot_config,
        )
        after_imputation_reaction_plots = self._create_plots(
            imputed_per_gene_per_reaction_main_substrate_predictions,
            imputed_gene_substrate_predictions,
            plot_config,
            is_imputed=True,
        )
        categorized_metabolites = self._divide_model_metabolites_into_categories(
            adjusted_irreversible_cobra_model, imputed_gene_substrate_predictions
        )

        alluvial_plot_data = prepare_alluvial_plot_data(categorized_metabolites)
        categorized_metabolites_spec = DiagnosticOutputSpec(
            save_file_name="categorized_metabolites",
            data=categorized_metabolites,
            extensions=[".json"],
        )
        categorized_metabolites_count = {
            category: {label: len(members) for label, members in labels.items()}
            for category, labels in categorized_metabolites.items()
        }
        categorized_metabolites_count_spec = DiagnosticOutputSpec(
            save_file_name="categorized_metabolites_count",
            data=categorized_metabolites_count,
            extensions=[".json"],
        )
        missing_smiles_diagnostics = self.create_missing_smiles_diagnostics(
            adjusted_irreversible_cobra_model,
            categorized_metabolites,
            imputed_gene_substrate_predictions,
        )

        missing_smiles_diagnostics_spec = DiagnosticOutputSpec(
            save_file_name="missing_smiles_diagnostics",
            data=missing_smiles_diagnostics,
            extensions=[".json"],
        )

        alluvial_plot = create_alluvial_plot(alluvial_plot_data, plot_config=plot_config)

        diagnostic_output = self._create_diagnostic_output(
            before_imputation_plots=before_imputation_reaction_plots,
            after_imputation_plots=after_imputation_reaction_plots,
            alluvial_plot=alluvial_plot,
        )
        # ensure we dont overwrite anything in the new_scaffold_objects diagnostics
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": {
                "main_substrate_aggregation": diagnostic_output
                + [
                    categorized_metabolites_spec,
                    categorized_metabolites_count_spec,
                    missing_smiles_diagnostics_spec,
                ]
            },
            "metadata": {},
            "artifacts": {},
        }
        return new_scaffold_objects

    def _assess_substrate_missingness(
        self,
        gene_ids: list[str],
        substrates: list[str],
        imputed_gene_substrate_predictions: dict[str, dict[str, GeneSubstratePrediction]],
        number_of_reactions_with_only_missing_smiles: int,
        number_of_reactions_with_at_least_one_missing_smiles: int,
    ):
        missing_smiles_count = 0
        # we only need to check 1 gene as whether its missing is per metabolite
        for gene_id in gene_ids:
            if gene_id in imputed_gene_substrate_predictions:
                for substrate_id in substrates:
                    if substrate_id in imputed_gene_substrate_predictions[gene_id]:
                        pred = imputed_gene_substrate_predictions[gene_id][substrate_id]
                        if pred.missing_smiles:
                            missing_smiles_count += 1
                break
        if missing_smiles_count == len(substrates):
            number_of_reactions_with_only_missing_smiles += 1
        if missing_smiles_count > 0:
            number_of_reactions_with_at_least_one_missing_smiles += 1

        return (
            number_of_reactions_with_only_missing_smiles,
            number_of_reactions_with_at_least_one_missing_smiles,
        )

    def count_reactions_with_missing_smiles(
        self,
        adjusted_irreversible_cobra_model: Model,
        imputed_gene_substrate_predictions: dict[str, dict[str, GeneSubstratePrediction]],
    ) -> tuple[int, int]:
        number_of_reactions_with_only_missing_smiles = 0
        number_of_reactions_with_at_least_one_missing_smiles = 0
        for reaction in adjusted_irreversible_cobra_model.reactions:
            genes = reaction.genes
            if not genes:
                continue
            gene_ids = [gene.id for gene in genes]
            substrates = reaction.metabolites
            substrates = [met.id for met in substrates if substrates[met] < 0]
            if not substrates:
                continue

            (
                number_of_reactions_with_only_missing_smiles,
                number_of_reactions_with_at_least_one_missing_smiles,
            ) = self._assess_substrate_missingness(
                gene_ids,
                substrates,
                imputed_gene_substrate_predictions,
                number_of_reactions_with_only_missing_smiles,
                number_of_reactions_with_at_least_one_missing_smiles,
            )

        return (
            number_of_reactions_with_only_missing_smiles,
            number_of_reactions_with_at_least_one_missing_smiles,
        )

    def create_missing_smiles_diagnostics(
        self,
        adjusted_irreversible_cobra_model: Model,
        categorized_metabolites: dict[str, dict[str, list[str]]],
        imputed_gene_substrate_predictions: dict[str, dict[str, GeneSubstratePrediction]],
    ) -> dict[str, int]:
        (
            number_of_reactions_with_only_missing_smiles,
            number_of_reactions_with_at_least_one_missing_smiles,
        ) = self.count_reactions_with_missing_smiles(
            adjusted_irreversible_cobra_model, imputed_gene_substrate_predictions
        )

        missing_smiles_diagnostics = {
            "number_of_reactions_with_GPR": sum(
                1
                for reaction in adjusted_irreversible_cobra_model.reactions
                if reaction.genes
            ),
            "number_of_reactions_with_only_missing_smiles": (
                number_of_reactions_with_only_missing_smiles
            ),
            "number_of_reactions_with_at_least_one_missing_smiles": (
                number_of_reactions_with_at_least_one_missing_smiles
            ),
            "number_of_substrates_with_GPR": len(
                categorized_metabolites["missing_smiles"]["True"]
                + categorized_metabolites["missing_smiles"]["False"]
            ),
            "number_of_substrates_with_no_GPR": len(
                categorized_metabolites["missing_smiles"]["No gene association"]
            ),
            "number_of_substrates_with_missing_smiles": sum(
                1
                for gene_id in imputed_gene_substrate_predictions.values()
                for pred in gene_id.values()
                if pred.missing_smiles
            ),
        }
        return missing_smiles_diagnostics

    def _create_plots(
        self,
        reaction_main_substrate_predictions: dict[str, ReactionMainSubstratePrediction],
        gene_substrate_predictions: dict[str, dict[str, GeneSubstratePrediction]],
        plot_config: PlotConfig,
        is_imputed: bool = False,
    ):
        imputed_title_addition = " (Imputed)" if is_imputed else "(Before Imputation)"
        # categories are compartments, we want to get the predictions per compartment
        reaction_values = self.safely_get_log10_value(reaction_main_substrate_predictions)

        gene_values = [
            (pred.compartment, pred.prediction_value)
            for gene_preds in gene_substrate_predictions.values()
            for pred in gene_preds.values()
            if (not pred.missing_smiles or pred.imputed)
        ]
        reaction_values_per_compartment = {}
        for _reaction_id, compartment, value in reaction_values:
            if compartment not in reaction_values_per_compartment:
                reaction_values_per_compartment[compartment] = []
            reaction_values_per_compartment[compartment].append(value)

        gene_values_per_compartment = {}
        for compartment, value in gene_values:
            if compartment not in gene_values_per_compartment:
                gene_values_per_compartment[compartment] = []
            gene_values_per_compartment[compartment].append(value)

        reaction_boxplot = create_per_category_boxplot(
            categories=[compartment for _, compartment, _ in reaction_values],
            values=[value for _, _, value in reaction_values],
            group_ids=[reaction_id for reaction_id, _, _ in reaction_values],
            name=f"Reaction Main Substrate Kcats {imputed_title_addition}",
            plot_config=plot_config,
        )

        gene_boxplot = create_per_category_boxplot(
            categories=[
                pred.compartment
                for gene_preds in gene_substrate_predictions.values()
                for pred in gene_preds.values()
                if (not pred.missing_smiles or pred.imputed)
            ],
            values=[
                pred.prediction_value
                for gene_preds in gene_substrate_predictions.values()
                for pred in gene_preds.values()
                if (not pred.missing_smiles or pred.imputed)
            ],
            name=f"Gene Substrate Prediction Kcats {imputed_title_addition}",
            plot_config=plot_config,
        )

        reaction_histogram = self._create_histogram_distribution(
            data=[value for _, _, value in reaction_values],
            title=f"Reaction Main Substrate Prediction Kcat "
            f"{imputed_title_addition} {len(reaction_values):,} values",
            plot_config=plot_config,
        )

        gene_histogram = self._create_histogram_distribution(
            data=[
                pred.prediction_value
                for gene_preds in gene_substrate_predictions.values()
                for pred in gene_preds.values()
                if (not pred.missing_smiles or pred.imputed)
            ],
            title=f"Gene Substrate Prediction Kcat "
            f"{imputed_title_addition} {len(gene_values):,} values",
            plot_config=plot_config,
        )

        return (reaction_boxplot, gene_boxplot, reaction_histogram, gene_histogram)

    def safely_get_log10_value(
        self,
        reaction_dict: dict[str, ReactionMainSubstratePrediction],
    ) -> list[tuple[str, str, float]]:
        reaction_values = []
        for (
            _reaction_id,
            reaction_pred,
        ) in reaction_dict.items():
            for _gene_id, gene_pred in reaction_pred.gene_main_substrate_predictions.items():
                if (
                    gene_pred.stoichiometry_adjusted_main_substrate_prediction_value
                    and gene_pred.stoichiometry_adjusted_main_substrate_prediction_value > 0
                ):
                    reaction_values.append(
                        (
                            reaction_pred.reaction_id,
                            gene_pred.main_substrate_compartment,
                            np.log10(
                                gene_pred.stoichiometry_adjusted_main_substrate_prediction_value
                            ),
                        )
                    )

        return reaction_values

    # always use go graph objects plot
    def _create_histogram_distribution(
        self,
        data: list[float],
        title: str,
        plot_config: PlotConfig,
    ):
        nbinsx = plot_config.histogram_nbinsx
        opacity = plot_config.histogram_base_overlay_opacity
        x_min = min(data)
        x_max = max(data)
        bin_size = (x_max - x_min) / nbinsx
        value_type = "Kcat"

        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=data,
                histnorm=plot_config.histogram_axis_type,
                opacity=opacity,
                xbins=dict(start=x_min, end=x_max, size=bin_size),
                marker=dict(
                    color=rgb_to_rgba(
                        COLORS_RGB["lightblue_hex"],
                        0.5,
                    )
                ),
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title=(f"{value_type.capitalize()} (log10)"),
            yaxis_title=(plot_config.histogram_axis_type.capitalize()),
            template="plotly_white",
            barmode="overlay",
        )
        return fig

    def _create_diagnostic_output(
        self,
        before_imputation_plots: tuple[go.Figure, go.Figure, go.Figure, go.Figure],
        after_imputation_plots: tuple[go.Figure, go.Figure, go.Figure, go.Figure],
        alluvial_plot: go.Figure,
    ) -> list[DiagnosticOutputSpec]:
        extensions = [".svg", ".html"]
        diagnostic_output = [
            DiagnosticOutputSpec(
                save_file_name="before_imputation_reaction_boxplot",
                data=before_imputation_plots[0],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="before_imputation_gene_boxplot",
                data=before_imputation_plots[1],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="before_imputation_reaction_histogram",
                data=before_imputation_plots[2],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="before_imputation_gene_histogram",
                data=before_imputation_plots[3],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="after_imputation_reaction_boxplot",
                data=after_imputation_plots[0],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="after_imputation_gene_boxplot",
                data=after_imputation_plots[1],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="after_imputation_reaction_histogram",
                data=after_imputation_plots[2],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="after_imputation_gene_histogram",
                data=after_imputation_plots[3],
                extensions=extensions,
            ),
            DiagnosticOutputSpec(
                save_file_name="metabolite_alluvial_plot",
                data=alluvial_plot,
                extensions=extensions,
            ),
        ]
        return diagnostic_output

    def _create_metabolite_to_GeneSubstratePrediction_map(
        self,
        after_imputation_gene_substrate_predictions: dict[
            str, dict[str, GeneSubstratePrediction]
        ],
    ) -> dict[str, list[GeneSubstratePrediction]]:
        metabolite_to_GeneSubstratePrediction_map: dict[
            str, list[GeneSubstratePrediction]
        ] = {}
        for (
            _gene_id,
            substrate_predictions,
        ) in after_imputation_gene_substrate_predictions.items():
            for substrate_id, prediction in substrate_predictions.items():
                if substrate_id not in metabolite_to_GeneSubstratePrediction_map:
                    metabolite_to_GeneSubstratePrediction_map[substrate_id] = []
                metabolite_to_GeneSubstratePrediction_map[substrate_id].append(prediction)
        return metabolite_to_GeneSubstratePrediction_map

    def _get_metabolite_reaction_counts(
        self, metabolite, adjusted_model: Model
    ) -> tuple[int, int, int]:
        output_reaction_count = len(
            [
                rxn
                for rxn in metabolite.reactions
                if rxn.id in adjusted_model.reactions
                and (
                    rxn.metabolites.get(metabolite) < 0
                    or (rxn.boundary and rxn.metabolites.get(metabolite) > 0)
                )
            ]
        )

        input_reaction_count = len(
            [
                rxn
                for rxn in metabolite.reactions
                if rxn.id in adjusted_model.reactions
                and (
                    rxn.metabolites.get(metabolite) > 0
                    or (rxn.boundary and rxn.metabolites.get(metabolite) < 0)
                )
            ]
        )
        total_reaction_count = output_reaction_count + input_reaction_count
        return output_reaction_count, input_reaction_count, total_reaction_count

    def _divide_model_metabolites_into_categories(
        self,
        adjusted_model: Model,
        after_imputation_gene_substrate_predictions: dict[
            str, dict[str, GeneSubstratePrediction]
        ],
    ) -> dict[str, dict[str, list[str]]]:
        # todo: metabolite alluvial for metabolites [(missing smiles, present smiles),
        # ( compartments),
        #  (output reactions 2, 2, 3, <=10, >10), (input reactions 1, 2, 3, <=10, >10),
        # (total reactions 1, 2, 3, <=10, >10), (present in n_other_compartments)]
        # )

        metabolites = list(adjusted_model.metabolites)
        metabolite_to_GeneSubstratePrediction_map = (
            self._create_metabolite_to_GeneSubstratePrediction_map(
                after_imputation_gene_substrate_predictions
            )
        )

        category_participation_dict: dict[str, dict[str, list[str]]] = {
            "missing_smiles": {"True": [], "False": [], "No gene association": []},
            "compartment": {},
            "output_reactions": {
                "0": [],
                "1": [],
                "2": [],
                "3": [],
                "<=10": [],
                ">10": [],
            },
            "input_reactions": {
                "0": [],
                "1": [],
                "2": [],
                "3": [],
                "<=10": [],
                ">10": [],
            },
            "total_reactions": {
                "0": [],
                "1": [],
                "2": [],
                "3": [],
                "<=10": [],
                ">10": [],
            },
            # "present_in_n_other_compartments": {},  # if we were to match the metabolite
        }
        for metabolite in metabolites:
            # missing smiles
            if metabolite.id in metabolite_to_GeneSubstratePrediction_map:
                predictions = metabolite_to_GeneSubstratePrediction_map[metabolite.id]
                if any(pred.missing_smiles for pred in predictions):
                    category_participation_dict["missing_smiles"]["True"].append(
                        metabolite.id
                    )
                else:
                    category_participation_dict["missing_smiles"]["False"].append(
                        metabolite.id
                    )
            else:
                category_participation_dict["missing_smiles"]["No gene association"].append(
                    metabolite.id
                )

            # compartment
            compartment = metabolite.compartment
            if compartment:
                if compartment not in category_participation_dict["compartment"]:
                    category_participation_dict["compartment"][compartment] = []
                category_participation_dict["compartment"][compartment].append(metabolite.id)

            # reaction counts
            output_count, input_count, total_count = self._get_metabolite_reaction_counts(
                metabolite, adjusted_model
            )
            for count_type, count in zip(
                ["output_reactions", "input_reactions", "total_reactions"],
                [output_count, input_count, total_count],
                strict=False,
            ):
                if count <= 3:
                    category_participation_dict[count_type][str(count)].append(metabolite.id)
                elif count <= 10:
                    category_participation_dict[count_type]["<=10"].append(metabolite.id)
                else:
                    category_participation_dict[count_type][">10"].append(metabolite.id)

        return category_participation_dict


def create_per_category_boxplot(  # noqa: C901
    categories: list[str] | pd.Series,
    values: list[float] | pd.Series,
    name: str,
    plot_config: PlotConfig | None = None,
    group_ids: list[str] | pd.Series | None = None,
) -> go.Figure:
    """
    Create a boxplot of values grouped by category.

    If ``group_ids`` are provided, individual datapoints are overlaid with
    deterministic colours based on their group ID. The same group therefore
    receives the same colour everywhere in the plot.

    The x-axis remains categorical-looking, while numeric x positions are used
    internally so that jittered scatter points align correctly with the
    boxplots.

    Args:
        categories:
            Category for each value. Must have the same length as ``values``.

        values:
            Numeric value corresponding to each category.

        name:
            Name used in the plot title.

        plot_config:
            Optional plotting configuration.

        group_ids:
            Optional group identifier for each value. Values belonging to the
            same group receive the same colour.

    Returns:
        Plotly Figure containing one boxplot per category.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    # ------------------------------------------------------------------
    # Validate inputs
    # ------------------------------------------------------------------

    if len(categories) != len(values):
        raise ValueError(
            f"`categories` and `values` must have the same length. "
            f"Got {len(categories)} categories and {len(values)} values."
        )

    if group_ids is not None and len(group_ids) != len(values):
        raise ValueError(
            f"`group_ids` and `values` must have the same length. "
            f"Got {len(group_ids)} group IDs and {len(values)} values."
        )

    # ------------------------------------------------------------------
    # Prepare dataframe
    # ------------------------------------------------------------------

    data: dict[str, object] = {
        "category": categories,
        "value": pd.to_numeric(values, errors="coerce"),
    }

    if group_ids is not None:
        data["group_id"] = group_ids

    data_df = pd.DataFrame(data)

    # Remove invalid observations.
    data_df = data_df.dropna(subset=["category", "value"])

    if data_df.empty:
        raise ValueError("No valid data remains after removing missing values.")

    data_df["category"] = data_df["category"].astype(str)

    if group_ids is not None:
        data_df["group_id"] = data_df["group_id"].astype(str)

    # ------------------------------------------------------------------
    # Category ordering and labels
    # ------------------------------------------------------------------

    category_order = sorted(data_df["category"].unique())

    category_counts = data_df["category"].value_counts()

    category_labels = {
        category: f"{category} (n={category_counts[category]:,})"
        for category in category_order
    }

    # Numeric x positions used internally by BOTH the boxplots and
    # scatter points. This is important: do not mix categorical x values
    # with numeric jittered x values.
    category_positions = {
        category: float(index) for index, category in enumerate(category_order)
    }

    # ------------------------------------------------------------------
    # Deterministic group colours
    # ------------------------------------------------------------------

    group_colors: dict[str, str] = {}

    if group_ids is not None:
        unique_group_ids = sorted(data_df["group_id"].unique())

        # Use a large continuous colour space rather than cycling through
        # a small colourblind palette. This is important because there may
        # be hundreds/thousands of reactions.
        #
        # The colour is determined by the group's position in the sorted
        # list, so the same reaction always receives the same colour.

        for index, group_id in enumerate(unique_group_ids):
            # Generate a deterministic RGB colour using HSV.
            # The golden-ratio step gives reasonably separated hues even
            # when there are many groups.
            hue = (index * 0.618033988749895) % 1.0
            saturation = 0.65
            value = 0.85

            red, green, blue = colorsys.hsv_to_rgb(
                hue,
                saturation,
                value,
            )

            group_colors[group_id] = (
                f"rgba({int(red * 255)}, {int(green * 255)}, {int(blue * 255)}, 0.8)"
            )

    fig = go.Figure()

    for category in category_order:
        category_df = data_df[data_df["category"] == category].copy()

        category_position = category_positions[category]
        display_category = category_labels[category]

        fig.add_trace(
            go.Box(
                x=[category_position] * len(category_df),
                y=category_df["value"],
                name=display_category,
                width=0.5,
                boxpoints=False if group_ids is not None else "all",
                marker=dict(
                    size=plot_config.point_size,
                    color=rgb_to_rgba(
                        COLORS_RGB["lightblue_hex"],
                        0.5,
                    ),
                ),
                line=dict(
                    color=rgb_to_rgba(
                        COLORS_RGB["black_hex"],
                        0.7,
                    )
                ),
                fillcolor=rgb_to_rgba(
                    COLORS_RGB["lightblue_hex"],
                    0.2,
                ),
                hovertemplate=(f"<b>{category}</b><br>Value: %{{y:.3f}}<extra></extra>"),
                showlegend=False,
            )
        )

        if group_ids is not None and not category_df.empty:
            jitter = (
                np.sin(np.arange(len(category_df)) * 12.9898 + category_position * 78.233)
                * 0.18
            )

            x_positions = category_position + jitter

            point_colors = [group_colors[group_id] for group_id in category_df["group_id"]]

            fig.add_trace(
                go.Scatter(
                    x=x_positions,
                    y=category_df["value"],
                    mode="markers",
                    marker=dict(
                        size=plot_config.point_size,
                        color=point_colors,
                    ),
                    customdata=category_df["group_id"],
                    hovertemplate=(
                        f"<b>{category}</b><br>"
                        "Reaction: %{customdata}<br>"
                        "Value: %{y:.3f}"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                )
            )

    fig.update_xaxes(
        tickmode="array",
        tickvals=[category_positions[category] for category in category_order],
        ticktext=[category_labels[category] for category in category_order],
        tickangle=45,
        title=plot_config.x_axis_title,
        title_font=dict(
            size=plot_config.x_axis_title_size,
        ),
        tickfont=dict(
            size=plot_config.x_axis_label_size,
        ),
        automargin=True,
        showgrid=False,
        zeroline=False,
    )

    yaxis_kwargs: dict[str, object] = {
        "title": plot_config.Y_axis_unit,
        "title_font": dict(
            size=plot_config.y_axis_title_size,
        ),
        "tickfont": dict(
            size=plot_config.y_axis_label_size,
        ),
        "automargin": True,
        "zeroline": False,
    }

    if plot_config.Y_transformation == "log":
        yaxis_kwargs["type"] = "log"

    elif plot_config.Y_transformation == "log10":
        yaxis_kwargs["type"] = "linear"

    elif plot_config.Y_transformation == "sqrt":
        yaxis_kwargs["type"] = "sqrt"

    else:
        yaxis_kwargs["type"] = "linear"

    fig.update_yaxes(**yaxis_kwargs)

    fig.update_layout(
        title=f"{name} (Total Values: {len(data_df):,})",
        template="plotly_white",
        hovermode="closest",
    )

    return fig


if __name__ == "__main__":
    from json import load
    from pathlib import Path

    from cobra.io import load_json_model

    from VmaxBuilder.utils.custom_logging import CustomLogger

    base_dir = r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"

    SWAPAM_data_dir = Path(r"/home/p70088775/git/SWAPAM/data/for_SWAMP")
    main_substrate_predictions_path = (
        SWAPAM_data_dir
        / "Kcat_predictions"
        / "UniKPV1"
        / "model_inhouse_v7_human"
        / "final_kcat_per_gene_combination_results.csv"
    )
    main_substrate_predictions_df = pd.read_csv(main_substrate_predictions_path)
    model_path = Path(base_dir) / "outputs" / "adjusted_irreversible_cobra_model.json"
    model = load_json_model(model_path)

    imputed_per_gene_per_reaction_main_substrate_predictions_path = (
        Path(base_dir)
        / "outputs"
        / "imputed_per_gene_per_reaction_main_substrate_predictions.json"
    )
    before_imputation_per_gene_per_reaction_main_substrate_predictions_path = (
        Path(base_dir)
        / "artifacts"
        / "Kcat_stage"
        / "before_imputation_per_gene_per_reaction_main_substrate_predictions.json"
    )
    imputed_gene_substrate_predictions_path = (
        Path(base_dir)
        / "artifacts"
        / "Kcat_stage"
        / "imputed_gene_substrate_predictions.json"
    )
    before_imputation_gene_substrate_predictions_path = (
        Path(base_dir)
        / "artifacts"
        / "Kcat_stage"
        / "before_imputation_gene_substrate_predictions.json"
    )
    # rebuild the imputed_per_gene_per_reaction_main_substrate_predictions dict

    # gene substrate is gene_id: {substrate_id: GeneSubstratePrediction}
    # reaction main substrate is reaction_id: ReactionMainSubstratePrediction
    # which itself contains a dict of gene_id: GeneMainSubstratePrediction

    with open(imputed_gene_substrate_predictions_path, "r") as f:
        data = load(f)
    for gene_id, gene_preds in data.items():
        for substrate_id, pred_dict in gene_preds.items():
            data[gene_id][substrate_id] = GeneSubstratePrediction.from_dict(pred_dict)
    imputed_gene_substrate_predictions = data

    with open(imputed_per_gene_per_reaction_main_substrate_predictions_path, "r") as f:
        data = load(f)
    for reaction_id, pred_dict in data.items():
        data[reaction_id] = ReactionMainSubstratePrediction.from_dict(pred_dict)
    imputed_per_gene_per_reaction_main_substrate_predictions = data

    with open(
        before_imputation_per_gene_per_reaction_main_substrate_predictions_path, "r"
    ) as f:
        data = load(f)
    for reaction_id, pred_dict in data.items():
        data[reaction_id] = ReactionMainSubstratePrediction.from_dict(pred_dict)
    before_imputation_per_gene_per_reaction_main_substrate_predictions = data

    with open(before_imputation_gene_substrate_predictions_path, "r") as f:
        data = load(f)

    for gene_id, gene_preds in data.items():
        for substrate_id, pred_dict in gene_preds.items():
            data[gene_id][substrate_id] = GeneSubstratePrediction.from_dict(pred_dict)
    before_imputation_gene_substrate_predictions = data

    diagnostics = object.__new__(GeneSubstratePredictionDiagnostics)

    diagnostics.logger = CustomLogger(
        "MainSubstrateImplementation",
    )

    class DummyFullConfig:
        protein = type("ProteinConfig", (), {"trim_enable": True})()
        kcat = type(
            "KcatConfig",
            (),
            {
                "prediction_transformation_state": "log10",
                "main_substrate_selection_statistic": "max",
                "missing_prediction_strategy": "all",  # alternative is "per_compartment"
                "missing_prediction_statistic": "median",
            },
        )()

    diagnostics.full_config = DummyFullConfig()  # ty:ignore
    number_of_reactions_with_missing_smiles = sum(
        1
        for gene_id in imputed_gene_substrate_predictions.values()
        for pred in gene_id.values()
        if pred.missing_smiles
    )

    plot_config = PlotConfig(
        histogram_nbinsx=80,
        Y_transformation="linear",  # Options: "linear", "log", "log10", "sqrt"
    )

    diagnostics.logger.info("Running diagnostics for GeneSubstratePredictionDiagnostics")
    diagnostic_output = diagnostics._create_diagnostic_output(
        before_imputation_plots=diagnostics._create_plots(
            before_imputation_per_gene_per_reaction_main_substrate_predictions,
            before_imputation_gene_substrate_predictions,
            plot_config,
            is_imputed=False,
        ),
        after_imputation_plots=diagnostics._create_plots(
            imputed_per_gene_per_reaction_main_substrate_predictions,
            imputed_gene_substrate_predictions,
            plot_config,
            is_imputed=True,
        ),
        alluvial_plot=create_alluvial_plot(
            prepare_alluvial_plot_data(
                diagnostics._divide_model_metabolites_into_categories(
                    model, imputed_gene_substrate_predictions
                )
            ),
            plot_config,
            title="Metabolite Categorization Alluvial Plot",
        ),
    )
    for plot in diagnostic_output:
        plot.data.show()
