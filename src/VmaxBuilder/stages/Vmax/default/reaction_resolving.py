from ast import In
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypedDict, cast

import pandas as pd
from cobra.core.model import Model
from cobra.io.json import load_json_model
from tqdm import tqdm

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    DiagnosticOutputSpec,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.Vmax.default.config import ReactionResolvingConfig
from VmaxBuilder.typing_stubs.Vmax.default.reaction_resolving import (
    ReactionResolvingConfigProtocol,
)


class DefaultVmaxReactionResolving(RealImplementation[ReactionResolvingConfigProtocol]):
    STAGE_NAME = "Vmax"
    IMPL_NAME = "DefaultVmaxReactionResolving"
    IMPLEMENTATION_CONFIG_CLASS = ReactionResolvingConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = []

    INPUTS: list[InputSpec] = [
        # inputs are IFP sample abundance, trimming output, per_reaction_per_gene_Kcats
        InputSpec(
            name="adjusted_irreversible_cobra_model",
            in_scaffold=True,
            data_type=Model,
        ),
        InputSpec(
            name="IFP_abundance_df",
            in_scaffold=True,
            data_type=pd.DataFrame,
        ),
        InputSpec(
            name="trimming_output",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="adjusted_reaction_to_IFP_mapping",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="adjusted_gene_to_IFP_mapping",
            in_scaffold=True,
            data_type=dict,
        ),
        InputSpec(
            name="per_reaction_per_gene_Kcats",
            in_scaffold=True,
            data_type=dict,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="non_imputed_reaction_capacity_df",
            data_type=pd.DataFrame,
            scaffold_location="artifacts",
            save_file_name="non_imputed_reaction_capacity_df",
            extension=".csv",
            validator=None,
        ),
        # OutputSpec(
        #     name="trimming_output",
        #     data_type=dict,
        #     scaffold_location="artifacts",
        #     save_file_name="trimming_output",
        #     extension=".json",
        #     validator=None,
        # ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "Vmax reaction resolving": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "All reactions with GPR resolved with Vmax values",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def generate_outputs(self, scaffold: Scaffold):
        IFP_abundance_df = cast(pd.DataFrame, scaffold.get_scaffold_value("IFP_abundance_df"))
        # cast to numeric
        IFP_abundance_df = IFP_abundance_df.apply(pd.to_numeric, errors="coerce")
        per_reaction_per_gene_Kcats = cast(
            dict, scaffold.get_scaffold_value("per_reaction_per_gene_Kcats")
        )
        trimming_output = cast(dict, scaffold.get_scaffold_value("trimming_output"))
        reaction_to_IFP_mapping = cast(
            dict, scaffold.get_scaffold_value("adjusted_reaction_to_IFP_mapping")
        )
        cobra_model = cast(
            Model, scaffold.get_scaffold_value("adjusted_irreversible_cobra_model")
        )
        gene_to_IFP_mapping = cast(
            dict, scaffold.get_scaffold_value("adjusted_gene_to_IFP_mapping")
        )

        _reaction_capacity_df = self.resolve_reaction_capacity(
            IFP_abundance_df,
            per_reaction_per_gene_Kcats,
            trimming_output,
            reaction_to_IFP_mapping,
            gene_to_IFP_mapping,
            cobra_model,
        )

        # for each reaction, get the IFPs that map to it
        # if not trimming, or if trimming but using
        # method_trim_genes_remain_part_for_Kcat
        # then we can just multiply each IFP's abundance by the highest Kcat among the genes
        # in the IFP in this reaction (as each reaction has different substrates). This
        # information is present in the Kcats_per_reaction_per_gene dictionary,
        #  and sum them up.

        # If we do do trimming and not using method_trim_genes_remain_part_for_Kcat,
        # then we check if the IFP is in the trimming output for this sample,
        # and if so we only consider the remaining genes and calculate the highest
        # Kcat among those

    def get_genes_for_IFP(
        self,
        IFP: str,
        sample: str,
        trimming_output: dict,
        IFP_to_genes: dict[str, list[str]],
        use_trimmed_genes_for_kcat: bool,
    ) -> list[str]:
        if use_trimmed_genes_for_kcat:
            trimming_info = trimming_output.get(IFP)

            if trimming_info is not None:
                sample_genes = trimming_info.get("genes_remaining_per_sample", {}).get(sample)

                if sample_genes is not None:
                    return sample_genes

        return IFP_to_genes.get(IFP, [])

    def resolve_reaction_capacity(
        self,
        IFP_abundance_df: pd.DataFrame,
        Kcats_per_reaction_per_gene: dict[str, dict[str, float]],
        trimming_output: dict,
        reaction_to_IFP_mapping: dict[str, dict[str, list[str]]],
        gene_to_IFP_mapping: dict[str, dict[str, list[str]]],
        cobra_model: Model,
    ) -> pd.DataFrame:
        IFP_to_genes = {
            IFP: [] for gene_info in gene_to_IFP_mapping.values() for IFP in gene_info["IFPs"]
        }

        for gene, gene_info in gene_to_IFP_mapping.items():
            for IFP in gene_info["IFPs"]:
                IFP_to_genes[IFP].append(gene)

        # comment part is too long for this thing but nothing else really like for real i
        # mean  it really
        samples = IFP_abundance_df.columns.tolist()
        reactions = [reaction.id for reaction in cobra_model.reactions]

        reaction_capacity_df = pd.DataFrame(
            0.0,
            index=reactions,
            columns=samples,
        )

        use_trimmed_genes_for_kcat = (
            self.full_config.protein.trim_enabled
            and not self.full_config.Vmax.trim_genes_remain_part_for_Kcat
        )
        IFPs_not_in_df = set()

        for sample in tqdm(
            samples,
            desc="Calculating reaction capacities",
        ):
            for reaction in reactions:
                IFPs_object = reaction_to_IFP_mapping.get(reaction, {})
                if not IFPs_object:
                    continue
                IFPs = IFPs_object.get("IFPs", [])
                if not IFPs:
                    continue

                kcats_of_genes_in_reaction = Kcats_per_reaction_per_gene.get(reaction, {})
                total_capacity = 0.0

                for _IFP in IFPs:
                    if _IFP not in IFP_abundance_df.index:
                        IFPs_not_in_df.add(_IFP)
                        continue
                    abundance = IFP_abundance_df.at[_IFP, sample]
                    genes = self.get_genes_for_IFP(
                        _IFP,
                        sample,
                        trimming_output,
                        IFP_to_genes,
                        use_trimmed_genes_for_kcat,
                    )

                    max_kcat = max(
                        (
                            kcats_of_genes_in_reaction[gene]
                            for gene in genes
                            if gene in kcats_of_genes_in_reaction
                        ),
                        default=0.0,
                    )
                    # print("Reaction:", reaction)
                    # print("IFP:", _IFP)
                    # print("Genes:", genes)
                    # print(
                    #     "Reaction Kcats:",
                    #     {
                    #         gene: kcats_of_genes_in_reaction[gene]
                    #         for gene in genes
                    #         if gene in kcats_of_genes_in_reaction
                    #     },
                    # )
                    # print("Abundance:", abundance)
                    # print("Max Kcat:", max_kcat)

                    total_capacity += abundance * max_kcat  # ty: ignore

                reaction_capacity_df.at[reaction, sample] = total_capacity

        print("not in df:", IFPs_not_in_df)
        print("not in df count:", len(IFPs_not_in_df))

        return reaction_capacity_df


if __name__ == "__main__":
    import json
    import random
    from pathlib import Path

    from VmaxBuilder.utils.custom_logging import CustomLogger

    base_dir = r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"

    IFP_mapping_path = Path(base_dir) / "outputs" / "adjusted_IFP_mapping.json"
    reaction_to_IFP_mapping_path = (
        Path(base_dir)
        / "artifacts"
        / "protein_stage"
        / "adjusted_reaction_to_IFP_mapping.json"
    )
    gene_to_IFP_mapping_path = (
        Path(base_dir) / "artifacts" / "protein_stage" / "adjusted_gene_to_IFP_mapping.json"
    )
    model_path = Path(base_dir) / "outputs" / "adjusted_irreversible_cobra_model.json"
    trimming_output_path = (
        Path(base_dir) / "artifacts" / "allocation_stage" / "trimming_output.json"
    )

    IFP_sample_abundance_df_path = Path(base_dir) / "outputs" / "IFP_abundance_df.csv"
    IFP_abundance_df = pd.read_csv(IFP_sample_abundance_df_path, index_col=0)

    with open(trimming_output_path, "r") as f:
        trimming_output = json.load(f)

    with open(reaction_to_IFP_mapping_path, "r") as f:
        reaction_to_IFP_mapping = json.load(f)

    with open(gene_to_IFP_mapping_path, "r") as f:
        gene_to_IFP_mapping = json.load(f)

    model = load_json_model(model_path)

    # fake kcats_per_reaction_per_gene dictionary
    random.seed(42)
    fake_kcats_per_reaction_per_gene = {}
    for reaction in model.reactions:
        genes_in_reaction = [gene.id for gene in reaction.genes]
        fake_kcats_per_reaction_per_gene[reaction.id] = {
            gene: random.uniform(0.1, 10.0) for gene in genes_in_reaction
        }

    resolver = object.__new__(DefaultVmaxReactionResolving)
    resolver.logger = CustomLogger(
        "DefaultVmaxReactionResolving",
    )

    class DummyFullConfig:
        protein = type("ProteinConfig", (), {"trim_enabled": True})()
        Vmax = type(
            "VmaxConfig",
            (),
            {"trim_genes_remain_part_for_Kcat": False},
        )()

    resolver.full_config = DummyFullConfig()  # ty: ignore

    reaction_activity_df = resolver.resolve_reaction_capacity(
        IFP_abundance_df,
        fake_kcats_per_reaction_per_gene,
        trimming_output,
        reaction_to_IFP_mapping,
        gene_to_IFP_mapping,
        model,
    )
    print("Reaction Activity DataFrame:")
    print(reaction_activity_df)
    print("number_of_reactions:", len(reaction_activity_df))
    print("reactions_in_model:", len(model.reactions))
    print("number_of_samples:", len(reaction_activity_df.columns))
    model_reaction_ids = set([reaction.id for reaction in model.reactions])
    reaction_activity_ids = set(reaction_activity_df.index)
    missing_reactions = model_reaction_ids - reaction_activity_ids
    print("missing_reactions:", missing_reactions)
