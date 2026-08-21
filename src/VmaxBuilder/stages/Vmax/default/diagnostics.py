from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementationDiagnostics
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.utils.transformations import (
    calculate_conversion_factor_per_sample_from_metabolic_protein_abundance,
)

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

    def ammend_IFP_dicts_with_expression_and_PTR_data(
        self, ifp_dicts: dict[str, dict[str, Any]], scaffold: Scaffold
    ):
        # get PTR in sample, and get expression in sample

        # Reaction: MAR03913
        # {
        #     "IFPs": {
        #         "ENSG00000171954": {
        #             "abundance": 125.02590302177214,
        #             "abundance_contribution_to_reaction_Vmax": 0.522946559528339,
        #             "Kcat": 0.5497039006447519,
        #             "Kcat_contribution_to_reaction_Vmax": 0.002299249648702168,
        #             "Vmax": 68.72722657270062,
        #             "Vmax_contribution_to_reaction_Vmax": 0.2874657636014809,
        #             "genes": {
        #                 "ENSG00000171954": {
        #                     "expression": null,
        #                     "expression_contribution_to_IFP_Vmax": null,
        #                     "PTR": null,
        #                     "PTR_contribution_to_IFP_Vmax": null,
        #                     "main_substrate_prediction_value": 0.5497039006447519,
        #                     "substrate_stoichiometries": {
        #                         "MAM02039[r]": -1.0,
        #                         "MAM02364[r]": -1.0,
        #                         "MAM02555[r]": -1.0,
        #                         "MAM02630[r]": -1.0
        #                     },
        #                     "stoichiometry_adjusted_main_substrate_prediction_value":
        #                     0.5497039006447519,
        #                     "GeneMainSubstratePrediction": {
        #                         "gene_id": "ENSG00000171954",
        #                         "reaction_id": "MAR03913",
        #                         "main_substrate": "MAM02630[r]",
        #                         "main_substrate_compartment": "r",
        #                         "main_substrate_prediction_value": 0.5497039006447519,
        #                         "stoichiometry_adjusted_main_substrate_prediction_value":
        #                         0.5497039006447519,
        #                         "metabolites_considered": {
        #                             "MAM02039[r]": 0.4790683769885233,
        #                             "MAM02555[r]": 0.18771652194732347,
        #                             "MAM02630[r]": 0.5497039006447519,
        #                             "MAM02364[r]": 0.20379943920078117
        #                         },
        #                         "substrate_stoichiometries": {
        #                             "MAM02039[r]": -1.0,
        #                             "MAM02364[r]": -1.0,
        #                             "MAM02555[r]": -1.0,
        #                             "MAM02630[r]": -1.0
        #                         },
        #                         "metabolites_stoichiometry_adjusted_considered": {
        #                             "MAM02039[r]": 0.4790683769885233,
        #                             "MAM02555[r]": 0.18771652194732347,
        #                             "MAM02630[r]": 0.5497039006447519,
        #                             "MAM02364[r]": 0.20379943920078117
        #                         }
        #                     }
        #                 }
        #             }
        # we want to be able to do the following plots;
        # so we need to generate this data:
        ##### gene-substrate predictions
        ##### main-substrate predictions
        ##### IFP-dominant kcat prediction
        ##### IFP-allocation
        ##### reaction-summed allocation
        ##### reaction-summed vmax
        ##### reaction contribution per IFP (for both kcat and allocation)
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
        self, df1: pd.DataFrame, df2: pd.DataFrame, title: str
    ) -> None:
        pass

    # def create CDF and histogram plot for
    # gene-substrate

    # we want to be able to do the following plots;
    # so we need to generate this data:
    ##### gene-substrate predictions
    ##### main-substrate predictions
    ##### IFP-dominant kcat prediction
    ##### IFP-allocation
    ##### reaction-summed allocation
    ##### reaction-summed vmax
    ##### reaction contribution per IFP (for both kcat and allocation)
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
        pass

    def plot_static_kcat_or_abundance_effects(self, scaffold: Scaffold):
        # todo:
        # plot at each level what happens if we would substitute abundance or kcat with
        # a static value
        pass

    def plot_overlaid_histograms_and_cdfs(self, scaffold: Scaffold):
        # overlaid histograms
        # overlaid cdfs for different samples
        pass
