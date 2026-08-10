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
        self.category_participation_dict = self._divide_model_reactions_into_categories(
            reactions
        )
        self.alluvial_data = self._create_alluvial_data(self.category_participation_dict)
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

            # subsystem_label = reaction.subsystem or "no_subsystem"
            # category_participation_dict["subsystem"].setdefault(
            #     subsystem_label,
            #     [],
            # ).append(reaction.id)

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




# def create_model_reactions_alluvial_plot(
#         self,
# ):
#     reactions = [rxn for rxn in self.cobra_model.reactions]
#     reversible_reactions = [rxn for rxn in reactions if rxn.reversibility]
#     irreversible_reactions = [rxn for rxn in reactions if not rxn.reversibility]
#     has_GPR_reactions = [rxn for rxn in reactions if rxn.gene_reaction_rule != ""]
#     has_no_GPR_reactions = [rxn for rxn in reactions if rxn.gene_reaction_rule == ""]
#     single_gene_reactions = [rxn for rxn in reactions if len(rxn.genes) == 1]
#     contains_only_AND_reactions = [
#         rxn
#         for rxn in reactions
#         if "and" in rxn.gene_reaction_rule and "or" not in rxn.gene_reaction_rule
#     ]
#     contains_only_OR_reactions = [
#         rxn
#         for rxn in reactions
#         if "or" in rxn.gene_reaction_rule and "and" not in rxn.gene_reaction_rule
#     ]
#     contains_mixed_AND_OR_reactions = [
#         rxn
#         for rxn in reactions
#         if "or" in rxn.gene_reaction_rule and "and" in rxn.gene_reaction_rule
#     ]
#
#     fast_cc_location = r"C:\Git\Metabolic_Task_Score\Data\Main_files\For_running\models\FastCCReducedHumanGem17\model_Human-GEM_fastCC.mat"
#     if os.path.exists(fast_cc_location):
#         fast_cc_model = load_matlab_model(fast_cc_location)
#         fast_cc_model_reaction_ids = [rxn.id for rxn in fast_cc_model.reactions]
#         blocked_reactions = [
#             rxn
#             for rxn in self.cobra_model.reactions
#             if rxn.id not in fast_cc_model_reaction_ids
#         ]
#         open_reactions = [
#             rxn for rxn in fast_cc_model.reactions if rxn.id in self.cobra_model.reactions
#         ]
#     else:
#         blocked_reactions = [rxn for rxn in self.cobra_model.reactions]
#         open_reactions = []
#
#     transport_reactions = [
#         rxn for rxn in self.cobra_model.reactions if len(rxn.compartments) > 1
#     ]
#     non_transport_reactions = [
#         rxn for rxn in self.cobra_model.reactions if len(rxn.compartments) == 1
#     ]
#
#     # reactions with fractional stoichiometries
#     reactions_with_fractional_stoichiometries = [
#         rxn
#         for rxn in self.cobra_model.reactions
#         if any([abs(stoich) % 1 != 0 for stoich in rxn.metabolites.values()])
#     ]
#     reactions_with_integer_stoichiometries = [
#         rxn
#         for rxn in self.cobra_model.reactions
#         if all([abs(stoich) % 1 == 0 for stoich in rxn.metabolites.values()])
#     ]
#     # reactions with energy carriers
#     results_energy_carriers = self.find_energy_carrier_reactions()
#     reactions_containing_energy_carriers = results_energy_carriers[0]
#     non_energy_carrier_containing_reaction = [
#         rxn
#         for rxn in self.cobra_model.reactions
#         if rxn not in reactions_containing_energy_carriers
#     ]
#
#     def build_reaction_dataframe(model):
#         rows = []
#         # Iterate through each reaction in your cobra model
#         for rxn in model.reactions:
#             # First column: reversible or irreversible
#             first_label = "reversible" if rxn.reversibility else "irreversible"
#             # second blocked or not
#             if rxn not in blocked_reactions:
#                 second_label = "open"
#             else:
#                 second_label = "blocked"
#             # third transport or not
#             if rxn not in transport_reactions and not rxn.boundary:
#                 third_label = "regular"
#             elif rxn.boundary:
#                 third_label = "exchange"
#                 reactions_with_glucose = [
#                     rxn
#                     for rxn in self.cobra_model.reactions
#                     if any(met in rxn.metabolites for met in ["glucose"])
#                 ]
#             else:
#                 third_label = "transport"
#
#             # fourth fractional
#             if rxn not in reactions_with_fractional_stoichiometries:
#                 fourth_label = "integer stoichiometry"
#             else:
#                 fourth_label = "fractional stoichiometry"
#
#             # fifth contains energy carrier metabolites (e.g. ATP UTP etc)
#             if rxn in reactions_containing_energy_carriers:
#                 fifth_label = "contains energy carrier"
#             else:
#                 fifth_label = "no energy carrier"
#
#             if rxn.gene_reaction_rule == "":
#                 sixth_label = "No_GPR"
#             else:
#                 # Check for single-gene reactions first
#                 rule = rxn.gene_reaction_rule.lower()
#                 if len(rxn.genes) == 1:
#                     sixth_label = "Single_gene"
#                 elif "and" in rule and "or" not in rule:
#                     sixth_label = "contains_only_AND"
#                 elif "or" in rule and "and" not in rule:
#                     sixth_label = "contains_only_OR"
#                 elif "and" in rule and "or" in rule:
#                     sixth_label = "contains_mixed_AND_OR"
#                 else:
#                     sixth_label = "Other"
#             # Append the new row with labels for each reaction
#             rows.append(
#                 {
#                     "first": first_label,
#                     "second": second_label,
#                     "third": third_label,
#                     "fourth": fourth_label,
#                     "fifth": fifth_label,
#                     "sixth": sixth_label,
#                 }
#             )
#         return pd.DataFrame(rows)
#
#     df = build_reaction_dataframe(self.cobra_model)
#
#     df_grouped = (
#         df.groupby(["first", "second", "third", "fourth", "fifth", "sixth"])
#         .size()
#         .reset_index(name="count")
#     )
#
#     color_first = {
#         "reversible": "#0000FF",  # dark blue
#         "irreversible": "#ADD8E6",  # light blue
#     }
#     color_second = {
#         "blocked": "#DC143C",  # dark crimson
#         "open": "#FF6347",  # bright red light
#     }
#     color_third = {
#         "transport": "#006400",  # dark green
#         "exchange": "#00FFFF",  # cyan
#         "regular": "#FFA500",  # orange
#     }
#     color_fourth = {
#         "fractional stoichiometry": "#800080",  # dark purple
#         "integer stoichiometry": "#90EE90",  # light green
#     }
#     color_fifth = {
#         "contains energy carrier": "#FFFF00",  # bright yellow
#         "no energy carrier": "#A52A2A",  # brown
#     }
#     color_sixth = {
#         "Single_gene": "#00FF00",  # green
#         "contains_only_AND": "#FFD700",  # gold
#         "contains_only_OR": "#00CED1",  # dark turquoise
#         "contains_mixed_AND_OR": "#FF69B4",  # hot pink
#         "No_GPR": "#A9A9A9",  # dark gray
#     }
#
#     # color_first = {
#     #     # dark blue
#     #     "reversible": "#0000FF",
#     #     # light blue
#     #     "irreversible": "#ADD8E6",
#     # }
#     #
#     # color_second = {
#     #     # dark crimson
#     #     "blocked": "#DC143C",
#     #     # bright red light
#     #     "open": "#FF6347",
#     # }
#     #
#     # color_third = {
#     #     # dark greenc
#     #     "transport": "#006400",
#     #     # cyan
#     #     "exchange": "#00FFFF",
#     #     # orange
#     #     "regular": "#FFA500"
#     # }
#     #
#     # color_fourth = {
#     #     # dark purple
#     #     "fractional stoichiometry": "#800080",
#     #     # light green
#     #     "integer stoichiometry": "#90EE90",
#     # }
#     #
#     # color_fifth = {
#     #     # bright yellow
#     #     "contains energy carrier": "#FFFF00",
#     #     # brown
#     #     "no energy carrier": "#A52A2A",
#     # }
#     #
#     # color_sixth = {
#     #     "Single_gene": "#00FF00",  # Green
#     #     "contains_only_AND": "#FFD700",  # Gold
#     #     "contains_only_OR": "#00CED1",  # Dark Turquoise
#     #     "contains_mixed_AND_OR": "#FF69B4",  # Hot Pink
#     #     "No_GPR": "#A9A9A9"  # Dark Gray
#     # }
#
#     def hex_to_rgb(h):
#         h = h.lstrip("#")
#         return tuple(int(h[i: i + 2], 16) for i in (0, 2, 4))
#
#     def rgb_to_hex(r, g, b):
#         return "#{:02X}{:02X}{:02X}".format(r, g, b)
#
#     def blend_color(hex1, hex2, factor=0.5):
#         """
#         Blends two hex colors.
#         """
#         r1, g1, b1 = hex_to_rgb(hex1)
#         r2, g2, b2 = hex_to_rgb(hex2)
#         r = int(r1 * factor + r2 * (1 - factor))
#         g = int(g1 * factor + g2 * (1 - factor))
#         b = int(b1 * factor + b2 * (1 - factor))
#         return rgb_to_hex(r, g, b)
#
#     def blend_three(row):
#         """
#         Compute a blended color for the full path.
#         First blend the color from stage 1 and stage 2, then blend the result with stage 3.
#         """
#
#         amount_of_steps = 6
#         factor_steps = 1 / (amount_of_steps - 1)
#         c1 = color_first[row["first"]]
#         c2 = color_second[row["second"]]
#         c3 = color_third[row["third"]]
#         c4 = color_fourth[row["fourth"]]
#         c5 = color_fifth[row["fifth"]]
#         c6 = color_sixth[row["sixth"]]
#         c12 = blend_color(c1, c2, factor=1 * factor_steps)
#         c23 = blend_color(c12, c3, factor=2 * factor_steps)
#         c34 = blend_color(c23, c4, factor=3 * factor_steps)
#         c45 = blend_color(c34, c5, factor=4 * factor_steps)
#         c56 = blend_color(c45, c6, factor=5 * factor_steps)
#
#         return c56
#
#     df_grouped["blend"] = df_grouped.apply(blend_three, axis=1)
#     # df_grouped["blend"] = "#00FF00"
#     # df_grouped_old = df_grouped.copy()
#
#     total_amounts_per_category = {
#         "first": {
#             "reversible": sum(df_grouped[df_grouped["first"] == "reversible"]["count"]),
#             "irreversible": sum(
#                 df_grouped[df_grouped["first"] == "irreversible"]["count"]
#             ),
#         },
#         "second": {
#             "blocked": sum(df_grouped[df_grouped["second"] == "blocked"]["count"]),
#             "open": sum(df_grouped[df_grouped["second"] == "open"]["count"]),
#         },
#         "third": {
#             "transport": sum(df_grouped[df_grouped["third"] == "transport"]["count"]),
#             "exchange": sum(df_grouped[df_grouped["third"] == "exchange"]["count"]),
#             "regular": sum(df_grouped[df_grouped["third"] == "regular"]["count"]),
#         },
#         "fourth": {
#             "fractional stoichiometry": sum(
#                 df_grouped[df_grouped["fourth"] == "fractional stoichiometry"]["count"]
#             ),
#             "integer stoichiometry": sum(
#                 df_grouped[df_grouped["fourth"] == "integer stoichiometry"]["count"]
#             ),
#         },
#         "fifth": {
#             "contains energy carrier": sum(
#                 df_grouped[df_grouped["fifth"] == "contains energy carrier"]["count"]
#             ),
#             "no energy carrier": sum(
#                 df_grouped[df_grouped["fifth"] == "no energy carrier"]["count"]
#             ),
#         },
#         "sixth": {
#             "Single_gene": sum(df_grouped[df_grouped["sixth"] == "Single_gene"]["count"]),
#             "contains_only_AND": sum(
#                 df_grouped[df_grouped["sixth"] == "contains_only_AND"]["count"]
#             ),
#             "contains_only_OR": sum(
#                 df_grouped[df_grouped["sixth"] == "contains_only_OR"]["count"]
#             ),
#             "contains_mixed_AND_OR": sum(
#                 df_grouped[df_grouped["sixth"] == "contains_mixed_AND_OR"]["count"]
#             ),
#             "No_GPR": sum(df_grouped[df_grouped["sixth"] == "No_GPR"]["count"]),
#         },
#     }
#
#     # todo add labels for amount using total_amounts_dict made above
#     # rename the df with the amoutns
#     df_grouped["first"] = df_grouped["first"].replace(
#         {
#             "reversible": f"reversible: {total_amounts_per_category['first']['reversible']}",
#             "irreversible": f"irreversible: {total_amounts_per_category['first']['irreversible']}",
#         }
#     )
#     df_grouped["second"] = df_grouped["second"].replace(
#         {
#             "blocked": f"blocked: {total_amounts_per_category['second']['blocked']}",
#             "open": f"open: {total_amounts_per_category['second']['open']}",
#         }
#     )
#     df_grouped["third"] = df_grouped["third"].replace(
#         {
#             "transport": f"transport: {total_amounts_per_category['third']['transport']}",
#             "exchange": f"exchange: {total_amounts_per_category['third']['exchange']}",
#             "regular": f"regular: {total_amounts_per_category['third']['regular']}",
#         }
#     )
#     df_grouped["fourth"] = df_grouped["fourth"].replace(
#         {
#             "fractional stoichiometry": f"fractional stoichiometry: {total_amounts_per_category['fourth']['fractional stoichiometry']}",
#             "integer stoichiometry": f"integer stoichiometry: {total_amounts_per_category['fourth']['integer stoichiometry']}",
#         }
#     )
#     df_grouped["fifth"] = df_grouped["fifth"].replace(
#         {
#             "contains energy carrier": f"contains energy carrier: {total_amounts_per_category['fifth']['contains energy carrier']}",
#             "no energy carrier": f"no energy carrier: {total_amounts_per_category['fifth']['no energy carrier']}",
#         }
#     )
#     df_grouped["sixth"] = df_grouped["sixth"].replace(
#         {
#             "Single_gene": f"Single_gene: {total_amounts_per_category['sixth']['Single_gene']}",
#             "contains_only_AND": f"contains_only_AND: {total_amounts_per_category['sixth']['contains_only_AND']}",
#             "contains_only_OR": f"contains_only_OR: {total_amounts_per_category['sixth']['contains_only_OR']}",
#             "contains_mixed_AND_OR": f"contains_mixed_AND_OR: {total_amounts_per_category['sixth']['contains_mixed_AND_OR']}",
#             "No_GPR": f"No_GPR: {total_amounts_per_category['sixth']['No_GPR']}",
#         }
#     )
#
#     fig = go.Figure(
#         data=go.Parcats(
#             dimensions=[
#                 dict(
#                     label="Reaction Type",
#                     values=df_grouped["first"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"reversible: {total_amounts_per_category['first']['reversible']}",
#                         f"irreversible: {total_amounts_per_category['first']['irreversible']}",
#                     ],
#                 ),
#                 dict(
#                     label="Blocked",
#                     values=df_grouped["second"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"blocked: {total_amounts_per_category['second']['blocked']}",
#                         f"open: {total_amounts_per_category['second']['open']}",
#                     ],
#                 ),
#                 dict(
#                     label="Transport",
#                     values=df_grouped["third"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"transport: {total_amounts_per_category['third']['transport']}",
#                         f"exchange: {total_amounts_per_category['third']['exchange']}",
#                         f"regular: {total_amounts_per_category['third']['regular']}",
#                     ],
#                 ),
#                 dict(
#                     label="Stoichiometry",
#                     values=df_grouped["fourth"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"fractional stoichiometry: {total_amounts_per_category['fourth']['fractional stoichiometry']}",
#                         f"integer stoichiometry: {total_amounts_per_category['fourth']['integer stoichiometry']}",
#                     ],
#                 ),
#                 dict(
#                     label="Energy Carrier",
#                     values=df_grouped["fifth"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"contains energy carrier: {total_amounts_per_category['fifth']['contains energy carrier']}",
#                         f"no energy carrier: {total_amounts_per_category['fifth']['no energy carrier']}",
#                     ],
#                 ),
#                 dict(
#                     label="Classification",
#                     values=df_grouped["sixth"],
#                     categoryorder="array",
#                     categoryarray=[
#                         f"Single_gene: {total_amounts_per_category['sixth']['Single_gene']}",
#                         f"contains_only_AND: {total_amounts_per_category['sixth']['contains_only_AND']}",
#                         f"contains_only_OR: {total_amounts_per_category['sixth']['contains_only_OR']}",
#                         f"contains_mixed_AND_OR: {total_amounts_per_category['sixth']['contains_mixed_AND_OR']}",
#                         f"No_GPR: {total_amounts_per_category['sixth']['No_GPR']}",
#                     ],
#                 ),
#             ],
#             counts=df_grouped["count"],
#             line=dict(color=df_grouped["blend"]),
#             hoveron="color",
#             hoverinfo="all",
#             labelfont=dict(color="black", size=14),
#             arrangement="freeform",
#         )
#     )
#
#     fig.update_layout(
#         title="Alluvial Diagram of Reaction Categories",
#         font=dict(size=12, color="black"),
#     )
#
#     # annotations = []
#     # for _, row in df_grouped.iterrows():
#     #     annotations.append(dict(
#     #         x=0.5, y=0.5,  # Adjust these as needed.
#     #         text=f"{row['count']}",
#     #         showarrow=False,
#     #         font=dict(color="black", size=12),
#     #         xanchor="center", yanchor="middle"
#     #     ))
#     # fig.update_layout(annotations=annotations)
#     fig.write_html(
#         os.path.join(
#             self.kcat_statistics_location, "model_reaction_alluvial_plot_new.html"
#         )
#     )


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
