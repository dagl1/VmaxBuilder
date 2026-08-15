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
    main_substrate_prediction_value: float
    metabolites_considered: dict[str, float]


@dataclass
class ReactionMainSubstratePrediction:
    reaction_id: str
    gene_main_substrate_predictions: dict[str, GeneMainSubstratePrediction]
    genes_considered: set[str]
    substrates_considered: set[str]


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
    imputed: bool
    smiles_longer_than_218: bool

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
        if not isinstance(self.prediction_min, (float, int)):
            raise TypeError(
                f"prediction_min must be a float or int, got "
                f"{type(self.prediction_min).__name__}"
            )
        if not isinstance(self.prediction_max, (float, int)):
            raise TypeError(
                f"prediction_max must be a float or int, got "
                f"{type(self.prediction_max).__name__}"
            )
        if not isinstance(self.prediction_median, (float, int)):
            raise TypeError(
                f"prediction_median must be a float or int, got "
                f"{type(self.prediction_median).__name__}"
            )
        if not isinstance(self.prediction_mean, (float, int)):
            raise TypeError(
                f"prediction_mean must be a float or int, got "
                f"{type(self.prediction_mean).__name__}"
            )
        if not isinstance(self.prediction_sd, (float, int)):
            raise TypeError(
                f"prediction_sd must be a float or int, got "
                f"{type(self.prediction_sd).__name__}"
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
