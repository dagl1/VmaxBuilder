import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, cast, no_type_check

import numpy as np
import pandas as pd
from cobra import Model

from VmaxBuilder.utils.extra_utils import (
    extract_compartment,
    match_metabolite_with_model_metabolites,
    remove_compartment,
)


@dataclass
class GeneMainSubstratePrediction:
    gene_id: str
    main_substrate: str
    main_substrate_compartment: str
    main_substrate_prediction_value: float
    stoichiometry_adjusted_main_substrate_prediction_value: float
    metabolites_considered: dict[str, float]
    metabolites_stoichiometry_adjusted_considered: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "main_substrate": self.main_substrate,
            "main_substrate_compartment": self.main_substrate_compartment,
            "main_substrate_prediction_value": self.main_substrate_prediction_value,
            "stoichiometry_adjusted_main_substrate_prediction_value": (
                self.stoichiometry_adjusted_main_substrate_prediction_value
            ),
            "metabolites_considered": self.metabolites_considered,
            "metabolites_stoichiometry_adjusted_considered": (
                self.metabolites_stoichiometry_adjusted_considered
            ),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GeneMainSubstratePrediction":
        return GeneMainSubstratePrediction(
            gene_id=data["gene_id"],
            main_substrate=data["main_substrate"],
            main_substrate_compartment=data["main_substrate_compartment"],
            main_substrate_prediction_value=data["main_substrate_prediction_value"],
            stoichiometry_adjusted_main_substrate_prediction_value=data[
                "stoichiometry_adjusted_main_substrate_prediction_value"
            ],
            metabolites_considered=data["metabolites_considered"],
            metabolites_stoichiometry_adjusted_considered=data[
                "metabolites_stoichiometry_adjusted_considered"
            ],
        )


@dataclass
class ReactionMainSubstratePrediction:
    reaction_id: str
    gene_main_substrate_predictions: dict[str, GeneMainSubstratePrediction]
    genes_considered: set[str]
    substrates_considered: set[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reaction_id": self.reaction_id,
            "gene_main_substrate_predictions": {
                gene_id: prediction.to_dict()
                for gene_id, prediction in self.gene_main_substrate_predictions.items()
            },
            "genes_considered": list(self.genes_considered),
            "substrates_considered": list(self.substrates_considered),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ReactionMainSubstratePrediction":
        return ReactionMainSubstratePrediction(
            reaction_id=data["reaction_id"],
            gene_main_substrate_predictions={
                gene_id: GeneMainSubstratePrediction(**prediction)
                for gene_id, prediction in data["gene_main_substrate_predictions"].items()
            },
            genes_considered=set(data["genes_considered"]),
            substrates_considered=set(data["substrates_considered"]),
        )


@dataclass
class GeneSubstratePrediction:
    gene_id: str
    substrate_id: str
    compartment: str
    prediction_value: float
    imputed: bool = False
    smiles_longer_than_218: bool = False
    missing_smiles: bool = False
    prediction_min: float | None = field(default=None)
    prediction_max: float | None = field(default=None)
    prediction_median: float | None = field(default=None)
    prediction_mean: float | None = field(default=None)
    prediction_sd: float | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "substrate_id": self.substrate_id,
            "compartment": self.compartment,
            "prediction_value": self.prediction_value,
            "prediction_min": self.prediction_min,
            "prediction_max": self.prediction_max,
            "prediction_median": self.prediction_median,
            "prediction_mean": self.prediction_mean,
            "prediction_sd": self.prediction_sd,
            "missing_smiles": self.missing_smiles,
            "imputed": self.imputed,
            "smiles_longer_than_218": self.smiles_longer_than_218,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GeneSubstratePrediction":
        return GeneSubstratePrediction(
            gene_id=data["gene_id"],
            substrate_id=data["substrate_id"],
            compartment=data["compartment"],
            prediction_value=data["prediction_value"],
            prediction_min=data["prediction_min"],
            prediction_max=data["prediction_max"],
            prediction_median=data["prediction_median"],
            prediction_mean=data["prediction_mean"],
            prediction_sd=data["prediction_sd"],
            missing_smiles=data["missing_smiles"],
            imputed=data["imputed"],
            smiles_longer_than_218=data["smiles_longer_than_218"],
        )

    def _validate_string_types(self):
        if not isinstance(self.gene_id, str):
            raise TypeError(f"gene_id must be a string, got {type(self.gene_id).__name__}")
        if not isinstance(self.substrate_id, str):
            raise TypeError(
                f"substrate_id must be a string, got {type(self.substrate_id).__name__}"
            )
        if not isinstance(self.compartment, str):
            raise TypeError(
                f"compartment must be a string, got {type(self.compartment).__name__}"
            )

    def _validate_numeric_types(self):
        if not isinstance(self.prediction_value, (float, int)):
            raise TypeError(
                f"prediction_value must be a float or int, got "
                f"{type(self.prediction_value).__name__}"
            )

    def _validate_boolean_types(self):
        if not isinstance(self.missing_smiles, bool):
            raise TypeError(
                f"missing_smiles must be a bool, got {type(self.missing_smiles).__name__}"
            )
        if not isinstance(self.smiles_longer_than_218, bool):
            raise TypeError(
                "smiles_longer_than_218 must be a bool, "
                "got {type(self.smiles_longer_than_218).__name__}"
            )
        if not isinstance(self.imputed, bool):
            raise TypeError(f"imputed must be a bool, got {type(self.imputed).__name__}")

    def __post_init__(self):
        self._validate_string_types()
        self._validate_numeric_types()
        self._validate_boolean_types()


def _build_metabolite_lookup(
    cobra_model: Model,
) -> dict[tuple[str, str], Any]:
    lookup = {}

    for metabolite in cobra_model.metabolites:
        compartment = extract_compartment(metabolite.id)
        metabolite_id = remove_compartment(metabolite.id)

        lookup[(metabolite_id, compartment)] = metabolite

    return lookup


def _validate_gene_substrate_predictions(
    df: pd.DataFrame,
) -> None:
    required_columns = {
        "ensemble_id",
        "metabolite_id",
        "median",
        "min",
        "max",
        "mean",
        "sd",
        "missing",
        "smiles_longer_than_218",
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "Gene substrate prediction DataFrame is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if not pd.api.types.is_string_dtype(df["ensemble_id"]):
        raise TypeError("'ensemble_id' column must contain strings.")

    if not pd.api.types.is_string_dtype(df["metabolite_id"]):
        raise TypeError("'metabolite_id' column must contain strings.")

    numeric_columns = {
        "median",
        "min",
        "max",
        "mean",
        "sd",
    }

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise TypeError(
                f"'{column}' column must contain numeric values. "
                f"Got dtype {df[column].dtype}."
            )

    boolean_columns = {
        "missing",
        "smiles_longer_than_218",
    }

    for column in boolean_columns:
        if not pd.api.types.is_bool_dtype(df[column]):
            raise TypeError(
                f"'{column}' column must contain boolean values. "
                f"Got dtype {df[column].dtype}."
            )
