from dataclasses import dataclass
from typing import Any, TypedDict, cast

import numpy as np
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
from VmaxBuilder.stages.Kcat.Kcat_utils import (
    GeneMainSubstratePrediction,
    ReactionMainSubstratePrediction,
)
from VmaxBuilder.stages.Vmax.default.config import ReactionResolvingConfig
from VmaxBuilder.stages.Vmax.default.diagnostics import VmaxDiagnostics
from VmaxBuilder.typing_stubs.Vmax.default.reaction_resolving import (
    ReactionResolvingConfigProtocol,
)


class DefaultVmaxReactionResolving(RealImplementation[ReactionResolvingConfigProtocol]):
    STAGE_NAME = "Vmax"
    IMPL_NAME = "DefaultVmaxReactionResolving"
    IMPLEMENTATION_CONFIG_CLASS = ReactionResolvingConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = [VmaxDiagnostics]

    INPUTS: list[InputSpec] = [
        # inputs are IFP sample abundance, trimming output, per_reaction_per_gene_Kcats
        InputSpec(
            name="adjusted_irreversible_cobra_model",
            in_scaffold=True,
            data_type=Model,
        ),
        InputSpec(
            name="IFP_sample_abundance_df",
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
            name="imputed_per_gene_per_reaction_main_substrate_predictions",
            in_scaffold=True,
            data_type=dict,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="non_imputed_reaction_capacity_df",
            data_type=pd.DataFrame,
            scaffold_location="outputs",
            save_file_name="non_imputed_reaction_capacity_df",
            # saver args should make sure we save the index of the reactions
            saver_args={"with_index": True},
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="IFP_sample_abundance_dict",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="IFP_sample_abundance_dict",
            saver_args={},
            extension=".pkl",
            validator=None,
        ),
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
        IFP_abundance_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("IFP_sample_abundance_df")
        )
        IFP_abundance_df = self._normalize_abundance_dataframe(IFP_abundance_df)
        per_reaction_per_gene_Kcats = cast(
            dict[str, ReactionMainSubstratePrediction],
            scaffold.get_scaffold_value(
                "imputed_per_gene_per_reaction_main_substrate_predictions"
            ),
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

        time_elapsed, (reaction_capacity_df, IFP_sample_abundance_dict) = (
            self.get_time_decorator(self.resolve_reaction_capacity)(
                IFP_abundance_df,
                per_reaction_per_gene_Kcats,
                trimming_output,
                reaction_to_IFP_mapping,
                gene_to_IFP_mapping,
                cobra_model,
                apply_trimming=True,
            )
        )
        print(f"Reaction resolving took {time_elapsed:.2f} seconds.")

        metadata = self.create_metadata(time_elapsed)

        # for each reaction, get the IFPs that map to it
        # if not trimming, or if trimming but using
        # trim_genes_remain_part_for_Kcat
        # then we can just multiply each IFP's abundance by the highest Kcat among the genes
        # in the IFP in this reaction (as each reaction has different substrates). This
        # information is present in the Kcats_per_reaction_per_gene dictionary,
        #  and sum them up.

        # If we do do trimming and not using trim_genes_remain_part_for_Kcat,
        # then we check if the IFP is in the trimming output for this sample,
        # and if so we only consider the remaining genes and calculate the highest
        # Kcat among those
        new_scaffold_objects = {
            "outputs": {
                "non_imputed_reaction_capacity_df": reaction_capacity_df,
            },
            "diagnostics": {},
            "artifacts": {
                "IFP_sample_abundance_dict": IFP_sample_abundance_dict,
            },
            "metadata": metadata,
        }

        return new_scaffold_objects

    def _normalize_abundance_dataframe(self, abundance_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize abundance table to numeric float32 for lower memory footprint.

        Args:
            abundance_df (pd.DataFrame): Raw abundance matrix.

        Returns:
            pd.DataFrame: Numeric abundance matrix in float32 where possible.
        """
        try:
            return abundance_df.astype(np.float32, copy=False)
        except (TypeError, ValueError):
            return abundance_df.apply(pd.to_numeric, errors="coerce").astype(np.float32)

    def _should_save_ifp_sample_abundance_artifact(self) -> bool:
        """Return whether the compact per-sample IFP artifact should be retained.

        Diagnostics require this nested structure, so the compact artifact remains enabled
        even when detailed gene payloads are disabled.
        """
        return True

    def _should_include_gene_details_in_ifp_artifact(self) -> bool:
        """Return whether gene-level payload is included in IFP artifact entries."""
        return bool(
            getattr(
                self.full_config.Vmax,
                "include_gene_details_in_ifp_sample_abundance_artifact",
                False,
            )
        )

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
                genes_trimmed_per_sample = trimming_info.get("genes_trimmed_per_sample", {})
                trimmed_genes_in_sample = genes_trimmed_per_sample.get(sample, [])
                if trimmed_genes_in_sample:
                    trimmed_gene_set = set(trimmed_genes_in_sample)
                    return [
                        gene
                        for gene in IFP_to_genes.get(IFP, [])
                        if gene not in trimmed_gene_set
                    ]

        return IFP_to_genes.get(IFP, [])

    def get_specific_abundance_additional_capacity(
        self,
        sample: str,
        reaction: str,
        IFP_abundance_df: pd.DataFrame,
        trimming_output: dict,
        IFP_to_genes: dict[str, list[str]],
        use_trimmed_genes_for_kcat: bool,
        kcats_of_genes_in_reaction: dict[str, GeneMainSubstratePrediction],
        _IFP: str,
    ) -> tuple[float, float, float, list[str]]:
        abundance_value = cast(Any, IFP_abundance_df.at[_IFP, sample])
        abundance = float(abundance_value)
        # make abundance  numeric
        genes = self.get_genes_for_IFP(
            _IFP,
            sample,
            trimming_output,
            IFP_to_genes,
            use_trimmed_genes_for_kcat,
        )

        max_kcat = max(
            (
                prediction_value
                for gene in genes
                if gene in kcats_of_genes_in_reaction
                and (
                    prediction_value := (
                        kcats_of_genes_in_reaction[
                            gene
                        ].stoichiometry_adjusted_main_substrate_prediction_value
                    )
                )
                is not None
            ),
            default=0.0,
        )
        additional_capacity = abundance * max_kcat
        if abundance < 0:
            self.logger.warning(
                f"Negative abundance for IFP {_IFP} in "
                f"sample {sample}: {abundance}. Setting to 0."
            )
        if max_kcat < 0:
            self.logger.warning(
                f"Negative max Kcat for reaction {reaction}"
                f"in sample {sample}: {max_kcat}. Setting to 0."
            )
        return additional_capacity, abundance, max_kcat, genes

    def _build_initial_IFP_reaction_dict(
        self,
        IFP_sample_abundance_dict: dict[str, dict[str, dict]],
        sample: str,
        reaction: str,
        _IFP: str,
        ifp_abundance: float,
        ifp_kcat: float,
        additional_capacity: float,
        kcats_of_genes_in_reaction: dict[str, GeneMainSubstratePrediction],
        genes: list[str],
        include_gene_details: bool,
    ):
        gene_payload: dict[str, Any] = {}
        if include_gene_details:
            gene_payload = {
                _gene: {
                    "stoichiometry_adjusted_main_substrate_prediction_value": (
                        kcats_of_genes_in_reaction[
                            _gene
                        ].stoichiometry_adjusted_main_substrate_prediction_value
                    ),
                    "main_substrate_prediction_value": kcats_of_genes_in_reaction[
                        _gene
                    ].main_substrate_prediction_value,
                    "substrate_stoichiometries": kcats_of_genes_in_reaction[
                        _gene
                    ].substrate_stoichiometries,
                }
                for _gene in genes
                if _gene in kcats_of_genes_in_reaction
            }

        IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP] = {
            "abundance": ifp_abundance,
            "abundance_contribution_to_reaction_Vmax": None,
            "Kcat": ifp_kcat,
            "Kcat_contribution_to_reaction_Vmax": None,
            "Vmax": additional_capacity,
            "Vmax_contribution_to_reaction_Vmax": None,
        }
        if include_gene_details:
            IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP]["genes"] = gene_payload
        return IFP_sample_abundance_dict

    def modify_IFP_reaction_dict(
        self,
        IFP_sample_abundance_dict: dict,
        sample: str,
        reaction: str,
        IFPs: list[str],
        IFP_abundance_df: pd.DataFrame,
        total_capacity: float,
    ):
        IFP_sample_abundance_dict[sample][reaction]["Vmax"] = total_capacity
        # add the contributions
        for _IFP in IFPs:
            if _IFP not in IFP_abundance_df.index:
                continue
            if total_capacity == 0:
                continue
            ifp_abundance = IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP][
                "abundance"
            ]
            ifp_kcat = IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP]["Kcat"]
            abundance_contribution = ifp_abundance / total_capacity
            kcat_contribution = ifp_kcat / total_capacity

            IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP][
                "abundance_contribution_to_reaction_Vmax"
            ] = abundance_contribution
            IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP][
                "Kcat_contribution_to_reaction_Vmax"
            ] = kcat_contribution
            # add Vmax_contribution_to_reaction_Vmax
            IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP][
                "Vmax_contribution_to_reaction_Vmax"
            ] = (
                IFP_sample_abundance_dict[sample][reaction]["IFPs"][_IFP]["Vmax"]
                / total_capacity
            )

    def resolve_reaction_capacity(  # noqa: C901
        self,
        IFP_abundance_df: pd.DataFrame,
        Kcats_per_reaction_per_gene: dict[str, ReactionMainSubstratePrediction],
        trimming_output: dict,
        reaction_to_IFP_mapping: dict[str, dict[str, list[str]]],
        gene_to_IFP_mapping: dict[str, dict[str, list[str]]],
        cobra_model: Model,
        apply_trimming: bool = True,
    ) -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
        """Resolve reaction capacities while minimizing temporary memory pressure.

        Args:
            IFP_abundance_df (pd.DataFrame): IFP abundance by sample.
            Kcats_per_reaction_per_gene (dict[str, ReactionMainSubstratePrediction]):
                Per-reaction Kcat predictions.
            trimming_output (dict): Trimming payload keyed by IFP.
            reaction_to_IFP_mapping (dict[str, dict[str, list[str]]]): Reaction to IFP map.
            gene_to_IFP_mapping (dict[str, dict[str, list[str]]]): Gene to IFP map.
            cobra_model (Model): COBRA model containing reactions/genes.
            apply_trimming (bool): Whether trimming-aware logic should apply.

        Returns:
            tuple[pd.DataFrame, dict[str, dict[str, dict]]]: Reaction-capacity matrix
            and optional per-sample IFP artifact.
        """
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
        reaction_index = {reaction_id: idx for idx, reaction_id in enumerate(reactions)}
        sample_index = {sample_name: idx for idx, sample_name in enumerate(samples)}
        reaction_capacity_matrix = np.zeros(
            (len(reactions), len(samples)),
            dtype=np.float32,
        )

        use_trimmed_genes_for_kcat = (
            apply_trimming
            and (
                self.full_config.protein.trim_enable
                if hasattr(self.full_config.protein, "trim_enable")
                else False
            )
            and not (
                self.full_config.Vmax.trim_genes_remain_part_for_Kcat
                if hasattr(self.full_config.Vmax, "trim_genes_remain_part_for_Kcat")
                else False
            )
        )

        self.logger.attention(f"Use trimmed genes for kcat: {use_trimmed_genes_for_kcat}")
        IFPs_not_in_df = set()
        reactions_skipped_due_to_missing_kcat = set()

        build_ifp_artifact = self._should_save_ifp_sample_abundance_artifact()
        include_gene_details = self._should_include_gene_details_in_ifp_artifact()

        reaction_to_runtime_metadata: dict[str, dict[str, Any]] = {}
        for reaction_obj in cobra_model.reactions:
            reaction_id = reaction_obj.id
            if reaction_id not in Kcats_per_reaction_per_gene:
                reactions_skipped_due_to_missing_kcat.add(reaction_id)
                continue

            IFPs_object = reaction_to_IFP_mapping.get(reaction_id, {})
            if not IFPs_object:
                continue

            IFPs = IFPs_object.get("IFPs", [])
            if not IFPs:
                continue

            reaction_to_runtime_metadata[reaction_id] = {
                "IFPs": IFPs,
                "GPR_rule": reaction_obj.gene_reaction_rule,
                "genes": tuple(gene.id for gene in reaction_obj.genes),
                "gene_objects": Kcats_per_reaction_per_gene[
                    reaction_id
                ].gene_main_substrate_predictions,
            }

        IFPs_in_abundance_df = set(IFP_abundance_df.index)
        IFP_sample_abundance_dict: dict[str, dict[str, dict]] = {}
        if build_ifp_artifact:
            IFP_sample_abundance_dict = {sample: {} for sample in samples}

        for sample in tqdm(
            samples,
            desc="Calculating reaction capacities",
        ):
            sample_abundance = IFP_abundance_df[sample]
            for reaction in reactions:
                runtime_metadata = reaction_to_runtime_metadata.get(reaction)
                if runtime_metadata is None:
                    continue

                IFPs = cast(list[str], runtime_metadata["IFPs"])
                kcats_of_genes_in_reaction = cast(
                    dict[str, GeneMainSubstratePrediction],
                    runtime_metadata["gene_objects"],
                )
                total_capacity = 0.0

                if build_ifp_artifact:
                    IFP_sample_abundance_dict[sample][reaction] = {
                        "IFPs": {},
                        "GPR_rule": runtime_metadata["GPR_rule"],
                        "Vmax": None,
                    }

                    if include_gene_details:
                        IFP_sample_abundance_dict[sample][reaction]["genes"] = {
                            gene_id: {
                                "expression": None,
                                "PTR": None,
                            }
                            for gene_id in cast(tuple[str, ...], runtime_metadata["genes"])
                        }

                for _IFP in IFPs:
                    if _IFP not in IFPs_in_abundance_df:
                        IFPs_not_in_df.add(_IFP)
                        continue

                    ifp_abundance = float(sample_abundance.get(_IFP, np.nan))
                    if pd.isna(ifp_abundance):
                        continue

                    genes = self.get_genes_for_IFP(
                        _IFP,
                        sample,
                        trimming_output,
                        IFP_to_genes,
                        use_trimmed_genes_for_kcat,
                    )
                    max_kcat = max(
                        (
                            prediction_value
                            for gene in genes
                            if gene in kcats_of_genes_in_reaction
                            and (
                                prediction_value := (
                                    kcats_of_genes_in_reaction[
                                        gene
                                    ].stoichiometry_adjusted_main_substrate_prediction_value
                                )
                            )
                            is not None
                        ),
                        default=0.0,
                    )

                    additional_capacity = ifp_abundance * max_kcat
                    if ifp_abundance < 0:
                        self.logger.warning(
                            f"Negative abundance for IFP {_IFP} in "
                            f"sample {sample}: {ifp_abundance}. Setting to 0."
                        )
                    if max_kcat < 0:
                        self.logger.warning(
                            f"Negative max Kcat for reaction {reaction}"
                            f"in sample {sample}: {max_kcat}. Setting to 0."
                        )

                    if build_ifp_artifact:
                        IFP_sample_abundance_dict = self._build_initial_IFP_reaction_dict(
                            IFP_sample_abundance_dict,
                            sample,
                            reaction,
                            _IFP,
                            ifp_abundance,
                            float(max_kcat),
                            additional_capacity,
                            kcats_of_genes_in_reaction,
                            genes,
                            include_gene_details=include_gene_details,
                        )

                    total_capacity += additional_capacity

                reaction_capacity_matrix[
                    reaction_index[reaction],
                    sample_index[sample],
                ] = total_capacity

                if build_ifp_artifact:
                    IFP_sample_abundance_dict[sample][reaction]["Vmax"] = total_capacity
                    self.modify_IFP_reaction_dict(
                        IFP_sample_abundance_dict,
                        sample,
                        reaction,
                        IFPs,
                        IFP_abundance_df,
                        total_capacity,
                    )

            del sample_abundance

        reaction_capacity_df = pd.DataFrame(
            reaction_capacity_matrix,
            index=reactions,
            columns=samples,
        )

        return reaction_capacity_df, IFP_sample_abundance_dict


if __name__ == "__main__":
    import json
    import random
    from pathlib import Path

    from VmaxBuilder.utils.custom_logging import CustomLogger

    base_dir = (
        r"/home/p70088775/git/VmaxBuilder"
        r"/data/run_example_output/DCM_test_Human-GEM-2.0.0_run/"
    )

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
    per_reaction_main_substrate_path = (
        Path(base_dir)
        / "outputs"
        / "imputed_per_gene_per_reaction_main_substrate_predictions.json"
    )
    IFP_abundance_df = pd.read_csv(IFP_sample_abundance_df_path, index_col=0)

    with open(trimming_output_path, "r") as f:
        trimming_output = json.load(f)

    with open(reaction_to_IFP_mapping_path, "r") as f:
        reaction_to_IFP_mapping = json.load(f)

    with open(gene_to_IFP_mapping_path, "r") as f:
        gene_to_IFP_mapping = json.load(f)

    with open(per_reaction_main_substrate_path, "r") as f:
        per_reaction_main_substrate_predictions = json.load(f)

    model = load_json_model(model_path)

    # fake kcats_per_reaction_per_gene dictionary
    random.seed(42)
    fake_kcats_per_reaction_per_gene = {}

    for reaction, dict_object in per_reaction_main_substrate_predictions.items():
        ReactionMainSubstratePrediction_obj = ReactionMainSubstratePrediction.from_dict(
            dict_object
        )
        fake_kcats_per_reaction_per_gene[reaction] = ReactionMainSubstratePrediction_obj

    resolver = object.__new__(DefaultVmaxReactionResolving)
    resolver.logger = CustomLogger(
        "DefaultVmaxReactionResolving",
    )

    class DummyFullConfig:
        protein = type("ProteinConfig", (), {"trim_enable": True})()
        Vmax = type(
            "VmaxConfig",
            (),
            {"trim_genes_remain_part_for_Kcat": False},
        )()

    resolver.full_config = cast(Any, DummyFullConfig())

    reaction_activity_df, IFP_sample_abundance_dict = resolver.resolve_reaction_capacity(
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
    print(
        f"example of IFP_sample_abundance_dict for sample {reaction_activity_df.columns[0]}:"
    )
    # select 3 random reactions for this sample
    sample = reaction_activity_df.columns[0]
    random_reactions = random.sample(list(reaction_activity_df.index), 3)
    for reaction in random_reactions:
        print(f"Reaction: {reaction}")
        print(
            json.dumps(
                IFP_sample_abundance_dict[sample][reaction],
                indent=4,
            )
        )
    #
