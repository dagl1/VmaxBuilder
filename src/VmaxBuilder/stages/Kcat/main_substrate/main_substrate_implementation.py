from __future__ import annotations

from typing import Any, cast, no_type_check

import numpy as np
import pandas as pd
from cobra import Metabolite, Model

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    RealImplementation,
)
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.Kcat.Kcat_utils import (
    GeneMainSubstratePrediction,
    GeneSubstratePrediction,
    ReactionMainSubstratePrediction,
    _build_metabolite_lookup,
    _validate_gene_substrate_predictions,
)
from VmaxBuilder.stages.Kcat.main_substrate.config import MainSubstrateConfig
from VmaxBuilder.stages.Kcat.main_substrate.diagnostics import (
    GeneSubstratePredictionDiagnostics,
)
from VmaxBuilder.typing_stubs.Kcat.main_substrate.main_substrate_implementation import (
    MainSubstrateConfigProtocol,
)
from VmaxBuilder.utils.extra_utils import (
    extract_compartment,
    match_metabolite_with_model_metabolites,
    remove_compartment,
)

INVERSE_TRANSFORMATIONS_TO_LOG10 = {
    "linear": lambda x: np.log10(x),
    "log10": lambda x: x,
    "ln": lambda x: np.log10(np.e) * x,
    "log": lambda x: np.log10(np.e) * x,
    "log2": lambda x: np.log10(2) * x,
}


IMPUTE_STATISTIC = {
    "mean": lambda values: pd.Series(values).mean(),
    "median": lambda values: pd.Series(values).median(),
    "max": lambda values: pd.Series(values).max(),
    "min": lambda values: pd.Series(values).min(),
}


class MainSubstrateImplementation(RealImplementation[MainSubstrateConfigProtocol]):
    STAGE_NAME = "Kcat"
    IMPL_NAME = "main_substrate_aggregation"
    IMPLEMENTATION_CONFIG_CLASS = MainSubstrateConfig
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = [
        GeneSubstratePredictionDiagnostics
    ]
    # todo: add in possible option to ignore predictions for passive transport reactions
    # and impute them afterwards
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="adjusted_irreversible_cobra_model",
            in_scaffold=True,
            data_type=Model,
        ),
        InputSpec(
            name="gene_substrate_predictions",
            prefix="gene_substrate_predictions",
            in_scaffold=True,
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]

    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="imputed_per_gene_per_reaction_main_substrate_predictions",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="imputed_per_gene_per_reaction_main_substrate_predictions",
            extension=".json",
        ),
        OutputSpec(
            name="imputed_gene_substrate_predictions",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="imputed_gene_substrate_predictions",
            extension=".json",
        ),
        OutputSpec(
            name="before_imputation_per_gene_per_reaction_main_substrate_predictions",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="before_imputation_per_gene_per_reaction_main_substrate_predictions",
            extension=".json",
        ),
        OutputSpec(
            name="before_imputation_gene_substrate_predictions",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="before_imputation_gene_substrate_predictions",
            extension=".json",
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        # Load inputs
        adjusted_irreversible_cobra_model: Model = cast(
            Model, scaffold.get_scaffold_value("adjusted_irreversible_cobra_model")
        )
        gene_substrate_predictions: pd.DataFrame = cast(
            pd.DataFrame, scaffold.get_scaffold_value("gene_substrate_predictions")
        )

        (
            elapsed_time,
            (
                main_substrate_per_gene_per_reaction,
                imputed_main_substrate_per_gene_per_reaction,
                gene_substrate_prediction_dict,
                imputed_gene_substrate_prediction_dict,
            ),
        ) = self.get_time_decorator(self.aggregate_main_substrate_predictions)(
            adjusted_irreversible_cobra_model=adjusted_irreversible_cobra_model,
            gene_substrate_predictions=gene_substrate_predictions,
        )
        metadata = self.create_metadata(elapsed_time=elapsed_time)

        return {
            "outputs": {
                "imputed_per_gene_per_"
                "reaction_main_substrate_"
                "predictions": imputed_main_substrate_per_gene_per_reaction
            },
            "artifacts": {
                "before_imputation_per_gene_per_"
                "reaction_main_substrate_predictions": main_substrate_per_gene_per_reaction,
                "before_imputation_gene_"
                "substrate_predictions": gene_substrate_prediction_dict,
                "imputed_gene_substrate_predictions": imputed_gene_substrate_prediction_dict,
            },
            "diagnostics": {},  # todo: implement diagnostics for main substrate aggregation
            "metadata": metadata,
        }

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "Kcat": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": (
                    "All Kcat predictions imputed and aggregated to dominant (main) substrate"
                ),
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def aggregate_main_substrate_predictions(
        self,
        adjusted_irreversible_cobra_model: Model,
        gene_substrate_predictions: pd.DataFrame,
    ) -> tuple[
        dict[str, ReactionMainSubstratePrediction],
        dict[str, ReactionMainSubstratePrediction],
        dict[str, dict[str, GeneSubstratePrediction]],
        dict[str, dict[str, GeneSubstratePrediction]],
    ]:
        """
        Aggregate main substrate predictions for each gene associated with each reaction.

        For every reaction, the genes associated with the reaction are inspected.
        For each gene, the substrate with the highest prediction value is selected
        from the available gene-substrate predictions.

        If ``ignore_missing_predictions`` is True, predictions marked as having
        missing SMILES or overly long SMILES are ignored.

        Returns:
            Mapping from reaction ID to ReactionMainSubstratePrediction.
        """

        _gene_substrate_prediction_dict = self.deconstruct_gene_substrate_predictions(
            gene_substrate_predictions,
            cobra_model=adjusted_irreversible_cobra_model,
        )

        gene_substrate_prediction_dict = self._convert_predictions_to_log10_scale(
            _gene_substrate_prediction_dict
        )

        main_substrate_per_gene_per_reaction = (
            self.obtain_main_substrate_per_gene_per_reaction(
                gene_substrate_prediction_dict,
                adjusted_irreversible_cobra_model,
                ignore_missing_predictions=True,
            )
        )

        imputed_gene_substrate_prediction_dict = self.impute_missing_predictions(
            gene_substrate_prediction_dict,
            reaction_main_substrate_predictions=main_substrate_per_gene_per_reaction,
            missing_prediction_strategy=self.full_config.Kcat.missing_prediction_strategy,
            missing_prediction_statistic=self.full_config.Kcat.missing_prediction_statistic,
        )

        imputed_main_substrate_per_gene_per_reaction = (
            self.obtain_main_substrate_per_gene_per_reaction(
                imputed_gene_substrate_prediction_dict,
                adjusted_irreversible_cobra_model,
                ignore_missing_predictions=False,
            )
        )
        imputed_main_substrate_per_gene_per_reaction = (
            self._convert_predictions_to_linear_scale(
                imputed_main_substrate_per_gene_per_reaction
            )
        )

        imputed_main_substrate_per_gene_per_reaction = (
            self._assign_stoichiometry_adjusted_predictions(
                imputed_main_substrate_per_gene_per_reaction,
            )
        )

        main_substrate_per_gene_per_reaction = self._convert_predictions_to_linear_scale(
            main_substrate_per_gene_per_reaction
        )
        main_substrate_per_gene_per_reaction = (
            self._assign_stoichiometry_adjusted_predictions(
                main_substrate_per_gene_per_reaction,
            )
        )

        return (
            main_substrate_per_gene_per_reaction,
            imputed_main_substrate_per_gene_per_reaction,
            gene_substrate_prediction_dict,
            imputed_gene_substrate_prediction_dict,
        )

    def _assign_stoichiometry_adjusted_predictions(
        self,
        reaction_predictions: dict[str, ReactionMainSubstratePrediction],
    ) -> dict[str, ReactionMainSubstratePrediction]:
        """
        Adjust the main substrate predictions based on the stoichiometry of the substrates
        in the reactions.

        For each reaction, the stoichiometry of each substrate is considered. The main
        substrate prediction value for each gene is adjusted by dividing it by the
        absolute value of the stoichiometry of the main substrate in that reaction.

        Returns:
            Mapping from reaction ID to ReactionMainSubstratePrediction with adjusted values.
        """
        for reaction_id, reaction_prediction in reaction_predictions.items():
            substrate_stoichiometries: dict[str, float] = (
                reaction_prediction.substrate_stoichiometries
            )
            for (
                gene_id,
                gene_prediction,
            ) in reaction_prediction.gene_main_substrate_predictions.items():
                main_substrate_id = gene_prediction.main_substrate
                if main_substrate_id in substrate_stoichiometries:
                    stoichiometry = abs(substrate_stoichiometries[main_substrate_id])
                    gene_prediction.stoichiometry_adjusted_main_substrate_prediction_value = (
                        gene_prediction.main_substrate_prediction_value / stoichiometry
                    )
                    gene_prediction.metabolites_stoichiometry_adjusted_considered = {
                        substrate_id: prediction_value
                        / abs(substrate_stoichiometries[substrate_id])
                        for substrate_id, prediction_value in gene_prediction.metabolites_considered.items()  # noqa: E501
                        if substrate_id in substrate_stoichiometries
                    }
                else:
                    raise ValueError(
                        f"Main substrate {main_substrate_id} for gene {gene_id} "
                        f"in reaction {reaction_id} is not found in the substrate"
                        f"stoichiometries."
                    )

        return reaction_predictions

    def _convert_predictions_to_log10_scale(
        self, gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]]
    ) -> dict[str, dict[str, GeneSubstratePrediction]]:
        """
        Convert prediction values to log10 scale if specified in the configuration.
        """

        if (
            self.full_config.Kcat.prediction_transformation_state == "log10"
            or self.full_config.Kcat.prediction_transformation_state == "none"
        ):
            return gene_substrate_prediction_dict
        elif (
            self.full_config.Kcat.prediction_transformation_state
            not in INVERSE_TRANSFORMATIONS_TO_LOG10
        ):
            raise ValueError(
                f"Unknown prediction transformation state: "
                f"{self.full_config.Kcat.prediction_transformation_state!r}. "
                "Expected one of: "
                f"{list(INVERSE_TRANSFORMATIONS_TO_LOG10.keys())}"
            )
        for _gene_id, substrate_predictions in gene_substrate_prediction_dict.items():
            for _substrate_id, prediction in substrate_predictions.items():
                prediction.prediction_value = INVERSE_TRANSFORMATIONS_TO_LOG10[
                    self.full_config.Kcat.prediction_transformation_state
                ](prediction.prediction_value)
        return gene_substrate_prediction_dict

    def _convert_predictions_to_linear_scale(
        self, reaction_predictions: dict[str, ReactionMainSubstratePrediction]
    ):
        """
        Convert reaction predictions from log10 to linear scale.
        """
        for _reaction_id, reaction_prediction in reaction_predictions.items():
            for (
                _gene_id,
                gene_prediction,
            ) in reaction_prediction.gene_main_substrate_predictions.items():
                gene_prediction.main_substrate_prediction_value = (
                    10**gene_prediction.main_substrate_prediction_value
                )
                for substrate_id in gene_prediction.metabolites_considered:
                    gene_prediction.metabolites_considered[substrate_id] = (
                        10 ** gene_prediction.metabolites_considered[substrate_id]
                    )

        return reaction_predictions

    # required because ty does not infer the type of the df properly,
    @no_type_check
    def deconstruct_gene_substrate_predictions(
        self,
        gene_substrate_predictions: pd.DataFrame,
        cobra_model: Model,
    ) -> dict[str, dict[str, GeneSubstratePrediction]]:
        gene_substrate_predictions = _validate_gene_substrate_predictions(
            gene_substrate_predictions
        )
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]] = {}
        metabolite_lookup = _build_metabolite_lookup(cobra_model)
        compartments = set(
            extract_compartment(metabolite.id) for metabolite in cobra_model.metabolites
        )
        # Cache because the same metabolite can occur for many genes.
        metabolite_match_cache: dict[str, tuple[str, str]] = {}

        for row in gene_substrate_predictions.itertuples(index=False):
            gene_id = row.ensemble_id
            # could or could not have compartment id, if not then there might be multiple
            # cached matches with different compartments
            original_metabolite_id = row.metabolite_id  #
            metabolite_id_without_compartment = remove_compartment(original_metabolite_id)
            cached_match = metabolite_match_cache.get(metabolite_id_without_compartment)

            if cached_match is None:
                # todo: find  way to get compartment if not included in metabolite id
                # similarly we need to ensure that we can properly recognise bare
                # metabolite ids
                compartment = extract_compartment(original_metabolite_id)
                if compartment is None:
                    for compartment in compartments:
                        matched_metabolite = metabolite_lookup.get(
                            (original_metabolite_id, compartment)
                        )
                        if matched_metabolite is None:
                            continue
                        if original_metabolite_id not in metabolite_match_cache:
                            metabolite_match_cache[original_metabolite_id] = []

                        metabolite_id = matched_metabolite.id
                        cached_match = (compartment, metabolite_id)
                        metabolite_match_cache[original_metabolite_id].append(cached_match)

                else:
                    if original_metabolite_id not in metabolite_match_cache:
                        metabolite_match_cache[original_metabolite_id] = []

                    cached_match = (compartment, metabolite_id_without_compartment)
                    metabolite_match_cache[metabolite_id_without_compartment].append(
                        cached_match
                    )

            matches = metabolite_match_cache.get(metabolite_id_without_compartment)
            if not matches:
                self.logger.warning(
                    f"Metabolite {original_metabolite_id} not found in the model. "
                    f"Skipping gene {gene_id}."
                )
                continue
            for compartment, metabolite_id in matches:
                prediction = GeneSubstratePrediction(
                    gene_id=gene_id,
                    substrate_id=metabolite_id,
                    compartment=compartment,
                    # use the config prediction_value_column: str = "median"
                    prediction_value=getattr(
                        row, self.full_config.Kcat.prediction_value_column
                    ),
                    prediction_min=row.min if not pd.isna(row.min) else None,
                    prediction_max=row.max if not pd.isna(row.max) else None,
                    prediction_median=row.median if not pd.isna(row.median) else None,
                    prediction_mean=row.mean if not pd.isna(row.mean) else None,
                    prediction_sd=row.sd if not pd.isna(row.sd) else None,
                    missing_smiles=row.missing if not pd.isna(row.missing) else False,
                    imputed=False,  # Initially, predictions are not imputed
                    smiles_longer_than_218=row.smiles_longer_than_218
                    if not pd.isna(row.smiles_longer_than_218)
                    else False,
                )

                gene_substrate_prediction_dict.setdefault(gene_id, {})[metabolite_id] = (
                    prediction
                )

        return gene_substrate_prediction_dict

    def obtain_main_substrate_per_gene_per_reaction(
        self,
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]],
        adjusted_irreverisble_cobra_model: Model,
        ignore_missing_predictions: bool = True,
    ) -> dict[str, ReactionMainSubstratePrediction]:
        """
        Determine the main substrate for each gene associated with each reaction.

        For every reaction, the genes associated with the reaction are inspected.
        For each gene, the substrate with the highest prediction value is selected
        from the available gene-substrate predictions.

        If ``ignore_missing_predictions`` is True, predictions marked as having
        missing SMILES or overly long SMILES are ignored.

        Returns:
            Mapping from reaction ID to ReactionMainSubstratePrediction.
        """

        reaction_predictions: dict[str, ReactionMainSubstratePrediction] = {}

        # Cache the valid predictions per gene so that the same gene does not
        # need to be filtered repeatedly across reactions.
        gene_prediction_cache: dict[str, dict[str, GeneSubstratePrediction]] = {}

        for reaction in adjusted_irreverisble_cobra_model.reactions:
            reaction_id = reaction.id

            gene_main_substrate_predictions: dict[str, GeneMainSubstratePrediction] = {}

            genes_considered: set[str] = set()
            substrates_considered: set[str] = set()
            substrate_stoichiometries: dict[Metabolite, float] = reaction.metabolites
            # only get substrate
            substrate_stoichiometries: dict[str, float] = {
                met.id: stoich
                for met, stoich in substrate_stoichiometries.items()
                if stoich < 0
            }

            for gene in reaction.genes:
                gene_id = gene.id

                gene_predictions = gene_substrate_prediction_dict.get(gene_id)
                if not gene_predictions:
                    continue

                # we only consider subrates that are actually part of the reaction
                gene_predictions = {
                    substrate_id: prediction
                    for substrate_id, prediction in gene_predictions.items()
                }

                # Filter/cache predictions for this gene.
                if gene_id not in gene_prediction_cache:
                    if ignore_missing_predictions:
                        gene_prediction_cache[gene_id] = {
                            substrate_id: prediction
                            for substrate_id, prediction in gene_predictions.items()
                            if not prediction.missing_smiles
                        }
                    else:
                        gene_prediction_cache[gene_id] = gene_predictions

                valid_predictions = gene_prediction_cache[gene_id]

                valid_predictions = {
                    substrate_id: prediction
                    for substrate_id, prediction in valid_predictions.items()
                    if substrate_id in substrate_stoichiometries
                }

                if not valid_predictions:
                    continue

                genes_considered.add(gene_id)

                # Find the substrate with the highest stoichiometry-adjusted prediction.
                # if we predict a kcat for gene-H20 then if we have a reaction
                # that consumes 2 H20 we should divide the kcat in this reaction.
                # As if we ask, how fast can this enzyme go, it will be limited
                # by the substrate that is consumed the slowest. Thus if one has to
                # consume 2 H20 for the reaction to go, then the kcat for water will
                # be halved.
                main_prediction = max(
                    valid_predictions.values(),
                    key=lambda prediction: (
                        (10**prediction.prediction_value)
                        / abs(substrate_stoichiometries[prediction.substrate_id])
                    ),
                )

                gene_main_substrate_predictions[gene_id] = GeneMainSubstratePrediction(
                    gene_id=gene_id,
                    reaction_id=reaction_id,
                    main_substrate=main_prediction.substrate_id,
                    main_substrate_compartment=main_prediction.compartment,
                    main_substrate_prediction_value=(main_prediction.prediction_value),
                    substrate_stoichiometries=substrate_stoichiometries,
                    metabolites_considered={
                        prediction.substrate_id: prediction.prediction_value
                        for prediction in valid_predictions.values()
                    },
                )

                substrates_considered.update(valid_predictions.keys())

            reaction_predictions[reaction_id] = ReactionMainSubstratePrediction(
                reaction_id=reaction_id,
                gene_main_substrate_predictions=gene_main_substrate_predictions,
                genes_considered=genes_considered,
                substrate_stoichiometries=substrate_stoichiometries,
            )

        return reaction_predictions

    def _get_imputation_values(
        self,
        reaction_main_substrate_predictions: dict[str, ReactionMainSubstratePrediction],
        missing_prediction_strategy: str,
        missing_prediction_statistic: str,
    ) -> dict[str, float]:
        statistic = IMPUTE_STATISTIC[missing_prediction_statistic]
        main_substrate_values_per_category: dict[str, list[float]] = {}

        if missing_prediction_strategy == "all":
            main_substrate_values_per_category["all"] = []
        elif missing_prediction_strategy == "per_compartment":
            main_substrate_values_per_category = {}

        for _reaction_id, reaction_prediction in reaction_main_substrate_predictions.items():
            for (
                main_substrate_prediction
            ) in reaction_prediction.gene_main_substrate_predictions.values():
                category = (
                    "all"
                    if missing_prediction_strategy == "all"
                    else main_substrate_prediction.main_substrate_compartment
                )

                main_substrate_values_per_category.setdefault(category, []).append(
                    main_substrate_prediction.main_substrate_prediction_value
                )

        # Calculate the imputation value once per category.
        imputation_values = {
            category: statistic(values)
            for category, values in main_substrate_values_per_category.items()
            if values
        }
        return imputation_values

    def impute_missing_predictions(
        self,
        gene_substrate_prediction_dict: dict[str, dict[str, GeneSubstratePrediction]],
        reaction_main_substrate_predictions: dict[str, ReactionMainSubstratePrediction],
        missing_prediction_strategy: str,
        missing_prediction_statistic: str,
    ) -> dict[str, dict[str, GeneSubstratePrediction]]:
        """
        Impute predictions for substrates with missing SMILES.

        Imputation is performed either across all valid predictions or separately
        per compartment.
        """
        if missing_prediction_strategy not in {"all", "per_compartment"}:
            raise ValueError(
                f"Unknown missing prediction strategy: "
                f"{missing_prediction_strategy!r}. "
                "Expected 'all' or 'per_compartment'."
            )

        imputation_values = self._get_imputation_values(
            reaction_main_substrate_predictions,
            missing_prediction_strategy,
            missing_prediction_statistic,
        )

        # Collect valid prediction values for the required imputation categories.
        imputed_gene_substrate_prediction_dict: dict[
            str, dict[str, GeneSubstratePrediction]
        ] = {}

        for gene_id, substrate_predictions in gene_substrate_prediction_dict.items():
            imputed_gene_predictions = {}

            for substrate_id, prediction in substrate_predictions.items():
                if not prediction.missing_smiles:
                    imputed_gene_predictions[substrate_id] = prediction
                    continue

                category = (
                    "all" if missing_prediction_strategy == "all" else prediction.compartment
                )

                if category not in imputation_values:
                    # No valid values exist from which to impute this prediction.
                    # Keep the original prediction unchanged.
                    imputed_gene_predictions[substrate_id] = prediction
                    continue

                imputed_value = imputation_values[category]

                imputed_gene_predictions[substrate_id] = GeneSubstratePrediction(
                    gene_id=prediction.gene_id,
                    substrate_id=prediction.substrate_id,
                    compartment=prediction.compartment,
                    prediction_value=imputed_value,
                    prediction_min=prediction.prediction_min,
                    prediction_max=prediction.prediction_max,
                    prediction_median=prediction.prediction_median,
                    prediction_mean=prediction.prediction_mean,
                    prediction_sd=prediction.prediction_sd,
                    missing_smiles=True,
                    imputed=True,
                    smiles_longer_than_218=prediction.smiles_longer_than_218,
                )

            imputed_gene_substrate_prediction_dict[gene_id] = imputed_gene_predictions

        return imputed_gene_substrate_prediction_dict


if __name__ == "__main__":
    from pathlib import Path
    from pprint import pprint

    from cobra.io import load_json_model

    from VmaxBuilder.utils.custom_logging import CustomLogger

    base_dir = (
        r"/home/p70088775/git/VmaxBuilder/data"
        "/run_example_output/DCM_test_Human-GEM-2.0.0_run/"
    )

    SWAPAM_data_dir = Path(r"/home/p70088775/git/SWAPAM/data/for_SWAMP")
    main_substrate_predictions_path = (
        r"/home/p70088775/git/VmaxBuilder/data"
        r"/run_example_output/DCM_test_Human-GEM-2.0.0_run/outputs"
        r"/lean_kcat_inference/kcat_gene_metabolite_predictions.csv"
    )
    main_substrate_predictions_df = pd.read_csv(main_substrate_predictions_path)
    model_path = Path(base_dir) / "outputs" / "adjusted_irreversible_cobra_model.json"
    model = load_json_model(model_path)

    main_substrate_aggregegator = object.__new__(MainSubstrateImplementation)
    main_substrate_aggregegator.logger = CustomLogger(
        "MainSubstrateImplementation",
    )

    class DummyFullConfig:
        protein = type("ProteinConfig", (), {"trim_enable": True})()
        Kcat = type(
            "KcatConfig",
            (),
            {
                "prediction_value_column": "median",
                "prediction_transformation_state": "log10",
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
    substrate_predictions_dict = (
        main_substrate_aggregegator._convert_predictions_to_log10_scale(
            substrate_predictions_dict
        )
    )

    main_substrate_per_gene_per_reaction = (
        main_substrate_aggregegator.obtain_main_substrate_per_gene_per_reaction(
            substrate_predictions_dict, model
        )
    )

    imputed_substrate_predictions_dict = (
        main_substrate_aggregegator.impute_missing_predictions(
            substrate_predictions_dict,
            reaction_main_substrate_predictions=main_substrate_per_gene_per_reaction,
            missing_prediction_strategy="all",
            missing_prediction_statistic="median",
        )
    )

    imputed_main_substrate_per_gene_per_reaction = (
        main_substrate_aggregegator.obtain_main_substrate_per_gene_per_reaction(
            imputed_substrate_predictions_dict,
            model,
            ignore_missing_predictions=False,
        )
    )

    # pprint(substrate_predictions_dict)
    # pprint(main_substrate_per_gene_per_reaction)
    # pprint(imputed_substrate_predictions_dict)
    # pprint(imputed_main_substrate_per_gene_per_reaction)

    # validate that all reactions have all genes with valid predictions after imputation
    is_valid = True
    for (
        reaction_id,
        reaction_prediction,
    ) in imputed_main_substrate_per_gene_per_reaction.items():
        for gene_id in reaction_prediction.genes_considered:
            gene_predictions = imputed_substrate_predictions_dict.get(gene_id)
            if not gene_predictions:
                is_valid = False
                print(f"Gene {gene_id} has no predictions after imputation.")
                continue

            main_substrate_prediction = (
                reaction_prediction.gene_main_substrate_predictions.get(gene_id)
            )
            if not main_substrate_prediction:
                is_valid = False
                print(
                    f"Gene {gene_id} in reaction {reaction_id} "
                    f"has no main substrate prediction after imputation."
                )
                continue

            main_substrate_id = main_substrate_prediction.main_substrate
            if main_substrate_id not in gene_predictions:
                is_valid = False
                print(
                    f"Main substrate {main_substrate_id} for gene {gene_id} in reaction "
                    f"{reaction_id} is not in the predictions after imputation."
                )

    if is_valid:
        print("All reactions have all genes with valid predictions after imputation.")
