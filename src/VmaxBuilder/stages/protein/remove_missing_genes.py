from copy import deepcopy
from typing import Any, cast

from cobra.core.model import Model
from cobra.core.reaction import Reaction
from cobra.manipulation.delete import remove_genes

from VmaxBuilder.base.classes import DiagnosticOutputSpec, RealImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.GPR.gpr_preprocessing import (
    build_gene_to_IFP_mapping,
    build_IFP_mapping_from_gpr_rules,
    build_reaction_to_IFP_mapping,
    get_unique_gpr_rules,
    remove_gene_from_GPR_rule,
)


class MissingGeneRemoval(RealImplementation[FullConfig]):
    STAGE_NAME: str = "protein"
    IMPL_NAME: str = "missing_gene_removal"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="irreversible_cobra_model",
            data_type=Model,
            in_scaffold=True,
            validator=None,
        ),
        InputSpec(
            name="IFP_mapping",
            data_type=dict,
            in_scaffold=True,
            validator=None,
        ),
        InputSpec(
            name="reaction_to_IFP_mapping",
            data_type=dict,
            in_scaffold=True,
            validator=None,
        ),
        InputSpec(
            name="gene_to_IFP_mapping",
            data_type=dict,
            in_scaffold=True,
            validator=None,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="adjusted_irreversible_cobra_model",
            data_type=Model,
            scaffold_location="outputs",
            save_file_name="adjusted_irreversible_cobra_model",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="adjusted_IFP_mapping",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="adjusted_IFP_mapping",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="adjusted_gene_to_IFP_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="adjusted_gene_to_IFP_mapping",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            name="adjusted_reaction_to_IFP_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="adjusted_reaction_to_IFP_mapping",
            extension=".json",
            validator=None,
        ),
    ]

    def __init__(self, full_config):
        super().__init__(full_config)

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, Any]:
        # Generate outputs for the IFP adjustment stage
        missing_genes = cast(list[str], scaffold.get_scaffold_value("missing_genes"))
        IFP_mapping = cast(dict, scaffold.get_scaffold_value("IFP_mapping"))
        reaction_to_IFP_mapping = cast(
            dict, scaffold.get_scaffold_value("reaction_to_IFP_mapping")
        )
        gene_to_IFP_mapping = cast(dict, scaffold.get_scaffold_value("gene_to_IFP_mapping"))
        irreversible_cobra_model = cast(
            Model, scaffold.get_scaffold_value("irreversible_cobra_model")
        )
        if hasattr(self.full_config.protein, "missing_gene_policy"):
            missing_gene_policy = self.full_config.protein.missing_gene_policy
        else:
            missing_gene_policy = ""

        adjusted_irreversible_cobra_model = irreversible_cobra_model
        adjusted_IFP_mapping = IFP_mapping
        adjusted_reaction_to_IFP_mapping = reaction_to_IFP_mapping
        adjusted_gene_to_IFP_mapping = gene_to_IFP_mapping
        time_taken = 0.0
        if missing_genes and missing_gene_policy == "GPRless":
            (
                elapsed_time,
                (
                    adjusted_irreversible_cobra_model,
                    removed_genes,
                    affected_reactions,
                    affected_reactions_without_genes_left,
                ),
            ) = self.get_time_decorator(self.set_GPRless_genes_in_model)(
                irreversible_cobra_model, missing_genes
            )
            unique_GPR_rules = get_unique_gpr_rules(adjusted_irreversible_cobra_model)
            (
                adjusted_IFP_mapping,
                adjusted_reaction_to_IFP_mapping,
                adjusted_gene_to_IFP_mapping,
                total_elapsed_time,
            ) = self.adjust_IFP_mapping_for_missing_genes(
                unique_GPR_rules, adjusted_irreversible_cobra_model
            )
            time_taken = elapsed_time + total_elapsed_time
            removed_genes_diagnostics = DiagnosticOutputSpec(
                {
                    "removed_genes": list(removed_genes),
                    "affected_reactions": list(affected_reactions),
                    "affected_reactions_without_genes_left": list(
                        affected_reactions_without_genes_left
                    ),
                },
                save_file_name="missing_gene_removal_diagnostics",
                extensions=".json",
                data_type=dict,
            )

        metadata = self.create_metadata(elapsed_time=time_taken)

        new_scaffold_objects = {
            "outputs": {
                "adjusted_irreversible_cobra_model": adjusted_irreversible_cobra_model,
                "adjusted_IFP_mapping": adjusted_IFP_mapping,
            },
            "artifacts": {
                "adjusted_gene_to_IFP_mapping": adjusted_gene_to_IFP_mapping,
                "adjusted_reaction_to_IFP_mapping": adjusted_reaction_to_IFP_mapping,
            },
            "metadata": metadata,
            "diagnostics": {
                "missing_gene_removal": [removed_genes_diagnostics]
                if removed_genes_diagnostics
                else []
            },
        }

        return new_scaffold_objects

    def set_GPRless_genes_in_model(
        self,
        cobra_model: Model,
        genes_to_set_GPRless: list[str],
    ) -> tuple[Model, list[str], list[str], list[str]]:
        """
        Sets the genes in the model that are in the list of genes to set to GPRless.
        This means that the genes provided to this function are removed from any GPR rule
         they are associated with, which can lead to reactions being
         set to GPRless if all associated genes are in the list.
         :params:
            model: The COBRApy model to modify
            genes_to_set_GPRless: A list of gene ids to set to GPRless

        :return: Model
            The modified COBRApy model with the specified genes set to GPRless
        """
        reactions_affected = set()
        for gene_id in genes_to_set_GPRless:
            if gene_id in cobra_model.genes:
                gene = cobra_model.genes.get_by_id(gene_id)
                reactions = cast(set[Reaction], set(gene.reactions))
                reactions_affected.update(reactions)
                # we also need to adjust the gpr rules of the reactions affected by this gene
                for reaction in gene.reactions:
                    gpr_rule = reaction.gene_reaction_rule
                    new_gpr_rule = remove_gene_from_GPR_rule(gpr_rule, gene_id)
                    reaction.gene_reaction_rule = new_gpr_rule

        reactions_without_genes = [
            reaction for reaction in reactions_affected if not reaction.genes
        ]
        reactions_affected = [reaction.id for reaction in reactions_affected]
        reactions_without_genes = [reaction.id for reaction in reactions_without_genes]

        self.logger.attention(
            f"Setting {len(genes_to_set_GPRless)} genes to GPRless, "
            f"which affects {len(reactions_affected)} reactions: \n"
            f"Of these, {len(reactions_without_genes)} reactions have no genes "
            "left after missing gene removal. See diagnostics/protein/missing_gene_removal"
            " for a list of these reactions."
        )
        remove_genes(cobra_model, genes_to_set_GPRless, remove_reactions=False)
        return cobra_model, genes_to_set_GPRless, reactions_affected, reactions_without_genes

    def _remove_missing_genes_from_IFP(
        self,
        IFP: dict[str, Any],
        missing_genes: set[str],
    ) -> dict[str, Any] | None:
        """
        Remove missing genes from a single IFP.

        Example:
            A and B and C
            missing = {B}

            -> A and C

        Returns None if all genes in the IFP are missing.
        """
        adjusted_IFP = deepcopy(IFP)

        original_genes = adjusted_IFP.get("genes_in_IFP", [])
        remaining_genes = [gene for gene in original_genes if gene not in missing_genes]

        # An IFP with no genes left is no longer valid.
        if not remaining_genes:
            return None

        remaining_genes = sorted(set(remaining_genes))

        adjusted_IFP["genes_in_IFP"] = remaining_genes

        # Rebuild the IFP identifier from the remaining genes.
        adjusted_IFP["IFP"] = " and ".join(remaining_genes)

        return adjusted_IFP

    def adjust_IFP_mapping_for_missing_genes(
        self,
        gpr_rules: dict[str, list[str]],
        cobra_model: Model,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]:
        # remove missing genes from gpr rules
        # then remake the IFP mapping based on the new gpr rules

        (elapsed_time, adjusted_IFP_mapping) = self.get_time_decorator(
            build_IFP_mapping_from_gpr_rules
        )(gpr_rules)
        (elapsed_time_2, adjusted_gene_to_IFP_mapping) = self.get_time_decorator(
            build_gene_to_IFP_mapping
        )(adjusted_IFP_mapping)
        (elapsed_time_3, adjusted_reaction_to_IFP_mapping) = self.get_time_decorator(
            build_reaction_to_IFP_mapping
        )(adjusted_IFP_mapping, cobra_model)

        total_elapsed_time = elapsed_time + elapsed_time_2 + elapsed_time_3

        return (
            adjusted_IFP_mapping,
            adjusted_reaction_to_IFP_mapping,
            adjusted_gene_to_IFP_mapping,
            total_elapsed_time,
        )

    def create_metadata(
        self,
        elapsed_time: float | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        metadata_payload = {
            "missing_gene_removal": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "implemented_gene_rule_simplifier",
            },
        }
        return metadata_payload
