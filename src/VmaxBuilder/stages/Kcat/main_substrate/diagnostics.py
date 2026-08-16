from typing import Any, cast

import numpy as np
import pandas as pd
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
        )
        # convert to log 10 only for imputed reaction predictions (the whole dict)
        for (
            _reaction_id,
            reaction_pred,
        ) in imputed_per_gene_per_reaction_main_substrate_predictions.items():
            for _gene_id, gene_pred in reaction_pred.gene_main_substrate_predictions.items():
                if gene_pred.stoichiometry_adjusted_main_substrate_prediction_value > 0:
                    gene_pred.stoichiometry_adjusted_main_substrate_prediction_value = (
                        np.log10(
                            gene_pred.stoichiometry_adjusted_main_substrate_prediction_value
                        )
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
        )
        catagorised_metabolites = self._divide_model_metabolites_into_categories(
            adjusted_irreversible_cobra_model, imputed_gene_substrate_predictions
        )
        alluvial_plot_data = prepare_alluvial_plot_data(catagorised_metabolites)
        alluvial_plot = create_alluvial_plot(alluvial_plot_data, plot_config=plot_config)

        diagnostic_output = self._create_diagnostic_output(
            before_imputation_plots=before_imputation_reaction_plots,
            after_imputation_plots=after_imputation_reaction_plots,
            alluvial_plot=alluvial_plot,
        )
        # ensure we dont overwrite anything in the new_scaffold_objects diagnostics
        new_scaffold_objects = {
            "outputs": {},
            "diagnostics": {"main_substrate_aggregation": diagnostic_output},
            "metadata": {},
            "artifacts": {},
        }
        return new_scaffold_objects

    def _create_plots(
        self,
        reaction_main_substrate_predictions: dict[str, ReactionMainSubstratePrediction],
        gene_substrate_predictions: dict[str, dict[str, GeneSubstratePrediction]],
        plot_config: PlotConfig,
    ):
        # categories are compartments, we want to get the predictions per compartment
        reaction_values = [
            (
                pred.main_substrate_compartment,
                pred.stoichiometry_adjusted_main_substrate_prediction_value,
            )
            for reaction_main_substrate_object in reaction_main_substrate_predictions.values()
            for pred in reaction_main_substrate_object.gene_main_substrate_predictions.values()  # noqa: E501
        ]
        gene_values = [
            (pred.compartment, pred.prediction_value)
            for gene_preds in gene_substrate_predictions.values()
            for pred in gene_preds.values()
            if (not pred.missing_smiles or pred.imputed)
        ]
        reaction_values_per_compartment = {}
        for compartment, value in reaction_values:
            if compartment not in reaction_values_per_compartment:
                reaction_values_per_compartment[compartment] = []
            reaction_values_per_compartment[compartment].append(value)

        gene_values_per_compartment = {}
        for compartment, value in gene_values:
            if compartment not in gene_values_per_compartment:
                gene_values_per_compartment[compartment] = []
            gene_values_per_compartment[compartment].append(value)

        reaction_boxplot = create_per_category_boxplot(
            categories=[
                pred.main_substrate_compartment
                for reaction_main_substrate_object in reaction_main_substrate_predictions.values()  # noqa: E501
                for pred in reaction_main_substrate_object.gene_main_substrate_predictions.values()  # noqa: E501
            ],
            values=[
                pred.stoichiometry_adjusted_main_substrate_prediction_value
                for reaction_main_substrate_object in reaction_main_substrate_predictions.values()  # noqa: E501
                for pred in reaction_main_substrate_object.gene_main_substrate_predictions.values()  # noqa: E501
            ],
            name="Reaction Main Substrate Kcats",
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
            name="Gene Substrate Prediction Kcats",
            plot_config=plot_config,
        )

        reaction_histogram = self._create_histogram_distribution(
            data=[
                pred.stoichiometry_adjusted_main_substrate_prediction_value
                for reaction_main_substrate_object in reaction_main_substrate_predictions.values()  # noqa: E501
                for pred in reaction_main_substrate_object.gene_main_substrate_predictions.values()  # noqa: E501
            ],
            title="Reaction Main Substrate Prediction Kcat",
            xlabel="Kcat",
            ylabel="Count",
            bins=plot_config.histogram_nbinsx,
        )

        gene_histogram = self._create_histogram_distribution(
            data=[
                pred.prediction_value
                for gene_preds in gene_substrate_predictions.values()
                for pred in gene_preds.values()
                if (not pred.missing_smiles or pred.imputed)
            ],
            title="Gene Substrate Prediction Kcat",
            xlabel="Kcat",
            ylabel="Count",
            bins=plot_config.histogram_nbinsx,
        )

        return (reaction_boxplot, gene_boxplot, reaction_histogram, gene_histogram)

    # always use go graph objects plot
    def _create_histogram_distribution(self, data, title, xlabel, ylabel, bins):
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=data,
                nbinsx=bins,
                marker=dict(
                    color=rgb_to_rgba(
                        COLORS_RGB["lightblue_hex"],
                        0.5,
                    )
                ),
                opacity=0.75,
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            template="plotly_white",
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
                if rxn.metabolites.get(metabolite) < 0 and rxn.id in adjusted_model.reactions
            ]
        )
        input_reaction_count = len(
            [
                rxn
                for rxn in metabolite.reactions
                if rxn.metabolites.get(metabolite) > 0 and rxn.id in adjusted_model.reactions
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
            "missing_smiles": {"True": [], "False": []},
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


def create_per_category_boxplot(
    categories: list[str] | pd.Series,
    values: list[float] | pd.Series,
    name: str,
    plot_config: PlotConfig | None = None,
) -> go.Figure:
    """
    Create a boxplot of values grouped by category.

    Args:
        categories:
            Category for each value. Must have the same length as ``values``.

        values:
            Numeric value corresponding to each category.

        name:
            Name used in the plot title.

        plot_config:
            Optional plotting configuration.

    Returns:
        Plotly Figure containing one boxplot per category.
    """
    if plot_config is None:
        plot_config = PlotConfig()

    if len(categories) != len(values):
        raise ValueError(
            f"`categories` and `values` must have the same length. "
            f"Got {len(categories)} categories and {len(values)} values."
        )

    data_df = pd.DataFrame(
        {
            "category": categories,
            "value": pd.to_numeric(values, errors="coerce"),
        }
    )

    # Remove rows where either category or value is missing.
    data_df = data_df.dropna(subset=["category", "value"])

    if data_df.empty:
        raise ValueError("No valid data remains after removing missing values.")

    data_df["category"] = data_df["category"].astype(str)

    fig = go.Figure()

    # One boxplot per category.
    for category, category_df in data_df.groupby("category", sort=True):
        fig.add_trace(
            go.Box(
                x=[category] * len(category_df),
                y=category_df["value"],
                name=category,
                boxpoints="all",
                jitter=0.3,
                pointpos=0,
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

    fig.update_xaxes(
        title="Category",
        tickangle=45,
        title_font=dict(size=plot_config.x_axis_title_size),
        tickfont=dict(size=plot_config.x_axis_label_size),
    )

    fig.update_yaxes(
        title="Value",
        title_font=dict(size=plot_config.y_axis_title_size),
        tickfont=dict(size=plot_config.y_axis_label_size),
    )

    fig.update_layout(
        title=f"{name} (Total Values: {len(data_df):,})",
        template="plotly_white",
    )

    return fig


if __name__ == "__main__":
    from json import load
    from pathlib import Path
    from pprint import pprint

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
    print(
        f"Number of reactions with missing SMILES: {number_of_reactions_with_missing_smiles}"
    )
    diagnostics.logger.info("Running diagnostics for GeneSubstratePredictionDiagnostics")
    diagnostic_output = diagnostics._create_diagnostic_output(
        before_imputation_plots=diagnostics._create_plots(
            before_imputation_per_gene_per_reaction_main_substrate_predictions,
            before_imputation_gene_substrate_predictions,
            PlotConfig(),
        ),
        after_imputation_plots=diagnostics._create_plots(
            imputed_per_gene_per_reaction_main_substrate_predictions,
            imputed_gene_substrate_predictions,
            PlotConfig(),
        ),
        alluvial_plot=create_alluvial_plot(
            prepare_alluvial_plot_data(
                diagnostics._divide_model_metabolites_into_categories(
                    model, imputed_gene_substrate_predictions
                )
            )
        ),
    )
    for plot in diagnostic_output:
        plot.data.show()
