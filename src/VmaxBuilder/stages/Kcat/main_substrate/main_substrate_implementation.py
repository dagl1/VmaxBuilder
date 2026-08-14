from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast, no_type_check

import pandas as pd
from cobra import Model

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.Kcat.Kcat_utils import (
    GeneSubstratePrediction,
    _build_metabolite_lookup,
    _validate_gene_substrate_predictions,
)
from VmaxBuilder.stages.Kcat.main_substrate.config import MainSubstrateConfig
from VmaxBuilder.typing_stubs.Kcat.main_substrate.main_substrate_implementation import (
    MainSubstrateConfigProtocol,
)
from VmaxBuilder.utils.extra_utils import (
    extract_compartment,
    match_metabolite_with_model_metabolites,
    remove_compartment,
)


class MainSubstrateImplementation(RealImplementation[MainSubstrateConfigProtocol]):
    STAGE_NAME = "Kcat"
    IMPL_NAME = "main_substrate_aggregation"
    IMPLEMENTATION_CONFIG_CLASS = MainSubstrateConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="adjusted_irreversible_cobra_model",
            in_scaffold=True,
            data_type=Model,
        ),
        InputSpec(
            name="gene_substrate_predictions",
            prefix="gene_substrate_predictions",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="per_gene_per_reaction_main_substrate_predictions",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="per_gene_per_reaction_main_substrate_predictions",
            extension=".json",
        ),
        OutputSpec(
            name="before_imputation_per_gene_per_reaction_main_substrate_predictions",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="per_gene_per_reaction_main_substrate_predictions",
            extension=".json",
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        # Load inputs
        adjusted_irreversible_cobra_model: Model = cast(
            Model, scaffold.get_scaffold_value("adjusted_irreverisble_cobra_model")
        )
        gene_substrate_predictions: pd.DataFrame = cast(
            pd.DataFrame, scaffold.get_scaffold_value("gene_substrate_predictions")
        )

        _gene_substrate_prediction_dict = self.deconstruct_gene_substrate_predictions(
            gene_substrate_predictions,
            cobra_model=adjusted_irreversible_cobra_model,
        )

        return {
            "outputs": {},
            "artifacts": {},
            "diagnostics": {},
            "metadata": {},
        }

    # required because ty does not infer the type of the df properly,
    @no_type_check
    def deconstruct_gene_substrate_predictions(
        self,
        gene_substrate_predictions: pd.DataFrame,
        cobra_model: Model,
    ) -> dict[str, dict[str, GeneSubstratePrediction]]:
        _validate_gene_substrate_predictions(gene_substrate_predictions)
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]] = {}
        metabolite_lookup = _build_metabolite_lookup(cobra_model)
        # Cache because the same metabolite can occur for many genes.
        metabolite_match_cache: dict[str, tuple[str, str]] = {}

        for row in gene_substrate_predictions.itertuples(index=False):
            gene_id = row.ensemble_id
            original_metabolite_id = row.metabolite_id

            cached_match = metabolite_match_cache.get(original_metabolite_id)

            if cached_match is None:
                compartment = extract_compartment(original_metabolite_id)
                metabolite_id_without_compartment = remove_compartment(original_metabolite_id)

                matched_metabolite = metabolite_lookup.get(
                    (metabolite_id_without_compartment, compartment)
                )

                if matched_metabolite is not None:
                    metabolite_id = matched_metabolite.id
                else:
                    metabolite_id = (
                        f"COULD NOT FIND MATCH FOR "
                        f"{metabolite_id_without_compartment} "
                        f"IN COMPARTMENT {compartment}"
                    )

                cached_match = (compartment, metabolite_id)
                metabolite_match_cache[original_metabolite_id] = cached_match

            compartment, metabolite_id = cached_match

            prediction = GeneSubstratePrediction(
                gene_id=gene_id,
                substrate_id=metabolite_id,
                compartment=compartment,
                prediction_value=row.median,
                prediction_min=row.min,
                prediction_max=row.max,
                prediction_median=row.median,
                prediction_mean=row.mean,
                prediction_sd=row.sd,
                missing_smiles=row.missing,
                smiles_longer_than_218=row.smiles_longer_than_218,
            )

            gene_substrate_prediction_dict.setdefault(gene_id, {})[metabolite_id] = prediction

        return gene_substrate_prediction_dict

    def obtain_main_substrate_per_gene_per_reaction(
        self,
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]],
        adjusted_irreverisble_cobra_model: Model,
        ignore_missing_predictions: bool = True,
    ):
        _main_substrate_per_gene_per_reaction: dict[
            str, dict[str, GeneSubstratePrediction]
        ] = {}
        for gene_id, _substrate_predictions in gene_substrate_prediction_dict.items():
            _associated_reactions = [
                rxn.id
                for rxn in adjusted_irreverisble_cobra_model.reactions
                if gene_id in [g.id for g in rxn.genes]
            ]

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "allocation": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "All sample abundance allocated",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata


if __name__ == "__main__":
    import json
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

    main_substrate_aggregegator = object.__new__(MainSubstrateImplementation)
    main_substrate_aggregegator.logger = CustomLogger(
        "MainSubstrateImplementation",
    )

    class DummyFullConfig:
        protein = type("ProteinConfig", (), {"trim_enabled": True})()
        kcat = type(
            "KcatConfig",
            (),
            {
                "main_substrate_selection_statistic": "max",
                "missing_prediction_strategy": "all",  # alternative is "per_compartment"
                "missing_prediction_statistic": "median",
            },
        )()

    main_substrate_aggregegator.full_config = DummyFullConfig()  # ty: ignore
    substrate_predictions_dict = (
        main_substrate_aggregegator.deconstruct_gene_substrate_predictions(
            main_substrate_predictions_df, model
        )
    )
    print(substrate_predictions_dict)
