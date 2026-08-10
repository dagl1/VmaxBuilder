from __future__ import annotations

import re
from typing import Any

import plotly.graph_objects as go
from cobra import Metabolite, Model, Reaction

from VmaxBuilder.base.classes import BaseImplementationDiagnostics
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.utils.plotting.alluvial import (
    prepare_alluvial_data,
    prepare_alluvial_plot_data,
    create_alluvial_plot,
)
from VmaxBuilder.utils.extra_utils import (
    get_transport_reactions,
    _get_reaction_compartments

)
from VmaxBuilder.utils.plotting.config import PlotConfig


class ModelDiagnostics(BaseImplementationDiagnostics):
    """Generated: validation needed.

    Description:
        Model-stage diagnostics for preparing reaction alluvial data.
    """

    DIAGNOSTICS_NAME = "model"
    # todo: metabolite alluvial for metabolites [(missing smiles, present smiles),
    # ( compartments),
    #  (output reactions 2, 2, 3, <=10, >10), (input reactions 1, 2, 3, <=10, >10),
    # (total reactions 1, 2, 3, <=10, >10), (present in n_other_compartments)]
    # )

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
        self.category_participation_dict: dict[str, dict[str, list[str]]] | None = None
        self.alluvial_data: dict[str, Any] | None = None

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
        self.category_participation_dict = None
        self.alluvial_data = None
        return {}

    def after_run(
        self,
        new_scaffold_objects: dict[str, dict[str, Any]],
        scaffold: Scaffold,
    ) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Build reaction category mapping and alluvial data after model stage.

        Args:
            new_scaffold_objects (dict[str, dict[str, Any]]): Stage outputs to return.
            scaffold (Scaffold): Shared scaffold payload.

        Returns:
            dict[str, dict[str, Any]]: Unchanged stage outputs.

        Modifies:
            Cached diagnostics state.
        """
        irreversible_cobra_model = scaffold.get_scaffold_value("irreversible_cobra_model")
        if irreversible_cobra_model is None:
            raise ValueError("'irreversible_cobra_model' missing from scaffold.")
        reactions = irreversible_cobra_model.reactions
        category_participation_dict = self._divide_model_reactions_into_categories(
            reactions
        )
        alluvial_data = prepare_alluvial_data(category_participation_dict)
        alluvial_plot_data = prepare_alluvial_plot_data(category_participation_dict)
        plot_config = PlotConfig()
        reaction_alluvial_plot_figure = create_alluvial_plot(alluvial_plot_data,
                                                             plot_config=plot_config)
        # todo add to diagnosticoutput and put in scaffol

        return new_scaffold_objects


    def _divide_model_reactions_into_categories(
        self,

        reactions: list[Reaction],
    ) -> dict[str, dict[str, list[str]]]:
        """Generated: validation needed.

        Description:
            Divide reactions into category-to-label membership buckets.

        Args:
            reactions (list[Reaction]): Reactions from model.

        Returns:
            dict[str, dict[str, list[str]]]: Nested category membership mapping.
        """
        category_participation_dict: dict[str, dict[str, list[str]]] = {
            "reaction_type": {},
            "compartment": {},
            "gene_association": {},
            "reversibility": {},
            # "subsystem": {},
        }
        active_transport_reactions, passive_transport_reactions = get_transport_reactions(
            reactions
        )
        active_transport_reaction_ids = {rxn.id for rxn in active_transport_reactions}
        passive_transport_reaction_ids = {rxn.id for rxn in passive_transport_reactions}

        for reaction in reactions:
            if reaction.boundary:
                reaction_type_label = "exchange"
            elif reaction.id in active_transport_reaction_ids:
                reaction_type_label = "active transport"
            elif reaction.id in passive_transport_reaction_ids:
                reaction_type_label = "passive transport"
            else:
                reaction_type_label = "regular"

            category_participation_dict["reaction_type"].setdefault(
                reaction_type_label,
                [],
            ).append(reaction.id)

            compartments = _get_reaction_compartments(reaction)
            if len(compartments) == 1:
                compartment_label = next(iter(compartments))
            else:
                compartment_label = "multi_compartment"
            category_participation_dict["compartment"].setdefault(
                compartment_label,
                [],
            ).append(reaction.id)

            gene_rule = reaction.gene_reaction_rule.strip().lower()
            has_and = bool(re.search(r"\band\b", gene_rule))
            has_or = bool(re.search(r"\bor\b", gene_rule))
            if not gene_rule:
                gene_label = "gprless"
            elif has_and and has_or:
                gene_label = "multi-gene AND/OR"
            elif has_and:
                gene_label = "multi-gene AND"
            elif has_or:
                gene_label = "multi-gene OR"
            else:
                gene_label = "single gene"
            category_participation_dict["gene_association"].setdefault(
                gene_label,
                [],
            ).append(reaction.id)

            reversibility_label = "reversible" if reaction.reversibility else "irreversible"
            category_participation_dict["reversibility"].setdefault(
                reversibility_label,
                [],
            ).append(reaction.id)


        return category_participation_dict

    def _invert_category_participation_dict(
        self,
        category_participation_dict: dict[str, dict[str, list[str]]],
    ) -> dict[str, dict[str, str]]:
        """Generated: validation needed.

        Description:
            Flip category membership mapping to reaction-centric lookup.

        Args:
            category_participation_dict (dict[str, dict[str, list[str]]]):
                Category membership mapping.

        Returns:
            dict[str, dict[str, str]]: Reaction to category-label mapping.
        """
        inverted_dict: dict[str, dict[str, str]] = {}
        for category, subcategories in category_participation_dict.items():
            for subcategory, reaction_ids in subcategories.items():
                for reaction_id in reaction_ids:
                    inverted_dict.setdefault(reaction_id, {})[category] = subcategory
        return inverted_dict


if __name__ == "__main__":
    from pathlib import Path
    from cobra.io import load_json_model

    plot_config = PlotConfig()
    title = "Alluvial Plot Example"
    base_dir = Path(r"E:/git/SWAPAM/data/for_SWAMP")
    models_dir = base_dir / "models"
    model_name = "model_inhouse_v7"
    full_model_path = models_dir / f"{model_name}_human" / f"{model_name}.json"
    model = load_json_model(str(full_model_path))
    reactions = model.reactions
    output_path = base_dir / "results" / model_name
    create_dynamically_named_results = True

    diagnostics = object.__new__(ModelDiagnostics)
    category_participation_dict = diagnostics._divide_model_reactions_into_categories(
        list(model.reactions)
    )
    alluvial_data = prepare_alluvial_data(category_participation_dict)
    alluvial_plot_data = prepare_alluvial_plot_data(category_participation_dict)
    title = "Alluvial Plot Example"
    figure = create_alluvial_plot(alluvial_plot_data, plot_config)

    figure.show()
