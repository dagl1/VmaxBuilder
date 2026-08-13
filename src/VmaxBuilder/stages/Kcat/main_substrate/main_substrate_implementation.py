from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
from cobra.core.model import Model

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.Kcat.main_substrate.config import MainSubstrateConfig
from VmaxBuilder.typing_stubs.Kcat.main_substrate.main_substrate_implementation import (
    MainSubstrateConfigProtocol,
)
from VmaxBuilder.utils.extra_utils import extract_compartment


# progress bar

@dataclass
class GeneSubstratePrediction:
    gene_id: str
    substrate_id: str
    compartment: str
    prediction_value: float
    prediction_min: float
    prediction_max: float
    prediction_median: float
    prediction_mean: float
    prediction_sd: float
    missing_smiles: bool
    smiles_longer_than_218: bool

class MainSubstrate(RealImplementation[MainSubstrateConfigProtocol]):
    STAGE_NAME = "Kcat"
    IMPL_NAME = "main_substrate_aggregation"
    IMPLEMENTATION_CONFIG_CLASS = MainSubstrateConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = []
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="adjusted_irreverisble_cobra_model",
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
        adjusted_irreverisble_cobra_model: Model = cast(
            Model, scaffold.get_scaffold_value("adjusted_irreverisble_cobra_model")
        )
        gene_substrate_predictions: pd.DataFrame = cast(
            pd.DataFrame, scaffold.get_scaffold_value("gene_substrate_predictions")
        )

        gene_substrate_prediction_dict = self.deconstruct_gene_susbtrate_predictions(
            gene_substrate_predictions
        )


        return {
            "outputs": {},
            "artifacts": {},
            "diagnostics": {},
            "metadata": {},
        }



    def deconstruct_gene_susbtrate_predictions(

        self, gene_substrate_predictions: pd.DataFrame
    ) -> dict[str, dict[str, GeneSubstratePrediction]]:
        # ensembl_id, metabolite_id

        # so we need to get th esplit it by comma and remove the () to get the gene and
        # metabolite id, then we als ocheck if missing smiles, the median value, and smiles
        # longer than 218 and we create the GeneSubstratePrediction
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]] = {}

        for _, row in gene_substrate_predictions.iterrows():
            gene_id = row["ensembl_id"]
            metabolite_id = row["metabolite_id"]
            compartment = extract_compartment(metabolite_id)
            prediction_value = row["median"]
            prediction_min = row["min"]
            prediction_max = row["max"]
            prediction_median = row["median"]
            prediction_mean = row["mean"]
            prediction_sd = row["sd"]
            missing_smiles = row["missing_smiles"]
            smiles_longer_than_218 = row["smiles_longer_than_218"]

            gene_substrate_prediction = GeneSubstratePrediction(
                gene_id=gene_id,
                substrate_id=metabolite_id,
                compartment=compartment,
                prediction_value=prediction_value,
                prediction_min=prediction_min,
                prediction_max=prediction_max,
                prediction_median=prediction_median,
                prediction_mean=prediction_mean,
                prediction_sd=prediction_sd,
                missing_smiles=missing_smiles,
                smiles_longer_than_218=smiles_longer_than_218,
            )
            if gene_id not in gene_substrate_prediction_dict:
                gene_substrate_prediction_dict[gene_id] = {}
            gene_substrate_prediction_dict[gene_id][metabolite_id] = gene_substrate_prediction

        return gene_substrate_prediction_dict

    def obtain_main_substrate_per_gene_per_reaction(self,
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]],
        adjusted_irreverisble_cobra_model: Model,
        ignore_missing_predictions: bool = True
        ):
        main_substrate_per_gene_per_reaction: dict[str, dict[str, GeneSubstratePrediction]] = {}
        for gene_id, substrate_predictions in gene_substrate_prediction_dict.items():
            # Get the reactions associated with this gene
            associated_reactions = [
                rxn.id for rxn in adjusted_irreverisble_cobra_model.reactions if gene_id in [g.id for g in rxn.genes]
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
