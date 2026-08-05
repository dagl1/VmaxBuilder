from queue import Full
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from cobra.core.model import Model
from pandas import DataFrame
from typing_extensions import Protocol

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.database_retrieval.identifier_translation import IdentifierTranslationService
from VmaxBuilder.stages.model.default.config import ModelConfig
from VmaxBuilder.stages.model.default.diagnostics import ModelDiagnostics
from VmaxBuilder.stages.model.default.preprocessing import (
    _build_transcript_artifacts_for_model,
    create_irreversible_model,
)
from VmaxBuilder.stages.model.model import ModelCoreConfig
from VmaxBuilder.typing_stubs.model.default.implementation import DefaultModelConfigProtocol
from VmaxBuilder.utils.custom_logging import custom_asdict
from VmaxBuilder.utils.iterables import SortedSet


class TranscriptMetadataServiceProtocol(Protocol):
    """Generated: validation needed.

    Description:
        Protocol for model-stage transcript metadata lookup services.
    """

    def build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        *,
        gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> DataFrame:
        """Generated: validation needed.

        Description:
            Build transcript metadata dataframe for one list of model genes.

        Args:
            gene_ids (list[str]): Model gene identifiers.
            gene_id_type (str): Gene identifier namespace.
            species (str | None): Optional species hint.
            provider (str): Translation provider key.
            max_workers (int): Maximum worker thread count.
            batch_size (int): Query batch size.

        Returns:
            pd.DataFrame: Transcript metadata dataframe.
        """


class DefaultIrreversibleModelImplementation(BaseImplementation[DefaultModelConfigProtocol]):
    BASE_STAGE_CONFIG = ModelCoreConfig
    IMPLEMENTATION_CONFIG_CLASS = ModelConfig
    _RESOLVED_CONFIG_CLASS = DefaultModelConfigProtocol
    STAGE_NAME = "model"
    IMPL_NAME = "dummy_cobra"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=Model,
            loader_args={
                "is_cobra_model": True,
                # "load_cobra_fast": True,
            },
            prefix="model_",
            extensions=(
                ".json",
                ".xml",
                ".yml",
                ".yaml",
                ".mat",
            ),
        ),
        InputSpec(
            name="gene_transcript_mapping",
            data_type=DataFrame,
            optional=True,
            prefix="gene_transcript_mapping",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            "irreversible_cobra_model",
            data_type=Model,
            scaffold_location="outputs",
            saver_args={
                "is_cobra_model": True,
            },
            save_file_name="irreversible_cobra_model",
            extension=".json",
            validator=None,
        ),
        OutputSpec(
            "rev2irrev",
            data_type=dict,
            scaffold_location="outputs",
            save_file_name="rev2irrev",
            extension=".json",
            validator=None,
        ),
    ]
    DIAGNOSTICS = [
        # ModelDiagnostics,
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        self._translation_service: TranscriptMetadataServiceProtocol = (
            IdentifierTranslationService()
        )

    def create_metadata(
        self,
        elapsed_time: float,
        **kwargs,
    ) -> dict[str, Any]:
        metadata = {
            "model": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "irreversible_model_created",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def create_transcript_metadata(
        self,
        elapsed_time: float,
        implementation_name: str,
    ) -> dict[str, Any]:
        transcript_metadata = {
            "transcripts": {
                "implementation": implementation_name,
                "status": "transcript_artifacts_built",
                "elapsed_time_seconds": elapsed_time,
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params("transcripts"),
            }
        }
        return transcript_metadata

    def create_model_base_diagnostics(
        self, cobra_model: Model
    ) -> dict[str, dict[str, int | SortedSet[str]]]:
        model_diagnostics = {
            "model": {
                "reaction_count": len(cobra_model.reactions),
                "irreversible_reaction_count": len(
                    [rxn for rxn in cobra_model.reactions if not rxn.reversibility]
                ),
                "exchange_reaction_count": len(
                    [rxn for rxn in cobra_model.reactions if rxn.boundary]
                ),
                "metabolite_count": len(cobra_model.metabolites),
                "gene_count": len(cobra_model.genes),
                "subsystem_count": len(
                    SortedSet(
                        [rxn.subsystem for rxn in cobra_model.reactions if rxn.subsystem]
                    )
                ),
                "subsystems": SortedSet(
                    [rxn.subsystem for rxn in cobra_model.reactions if rxn.subsystem]
                ),
            },
        }
        return model_diagnostics

    def create_base_transcript_diagnostics(
        self, transcript_df: DataFrame
    ) -> dict[str, dict[str, int | float]]:
        transcript_diagnostics = {
            "transcripts": {
                "transcript_count": len(transcript_df),
                "gene_count": len(transcript_df["gene_id"].unique()),
                "mean_transcripts_per_gene": (
                    len(transcript_df) / len(transcript_df["gene_id"].unique())
                ),
                "median_transcript_length": transcript_df["cdna_len"].median(),
                "mean_transcript_length ": transcript_df["cdna_len"].mean(),
            },
        }
        return transcript_diagnostics

    def _build_model(self, scaffold: Scaffold):
        cobra_model = cast(Model, scaffold.get_scaffold_value("cobra_model"))
        irreversible_model, rev2irrev = create_irreversible_model(
            cobra_model, logger=self.logger
        )
        return irreversible_model, rev2irrev

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        model_elapsed_time, (irreversible_model, rev2irrev) = self.get_time_decorator(
            self._build_model
        )(scaffold)

        outputs = {
            "irreversible_cobra_model": irreversible_model,
        }
        artifacts = {
            "rev2irrev": rev2irrev,
        }
        diagnostics = self.create_model_base_diagnostics(irreversible_model)
        metadata = self.create_metadata(model_elapsed_time)

        if self.full_config.run.run_target_transcript_gene_level.lower() == "transcript":
            # todo: add ability to use already existing gene_transcript_mapping if
            # # provided in scaffold

            if scaffold.get_scaffold_value("gene_transcript_mapping"):
                self.logger.info(
                    "Using provided gene_transcript_mapping from "
                    "scaffold for transcript artifacts."
                )
                NotImplementedError(
                    "Using provided gene_transcript_mapping "
                    "from scaffold is not yet implemented."
                )
            transcript_elapsed_time, transcript_artifacts = self.get_time_decorator(
                _build_transcript_artifacts_for_model
            )(
                model=irreversible_model,
                config=self.full_config,
                translation_service=self._translation_service,
            )
            transcript_metadata = self.create_transcript_metadata(
                elapsed_time=transcript_elapsed_time,
                implementation_name=self._translation_service.__class__.__name__,
            )
            transcript_diagnostics = self.create_base_transcript_diagnostics(
                transcript_artifacts["gene_transcript_mapping"]
            )

            artifacts.update(transcript_artifacts)
            metadata.update(transcript_metadata)
            diagnostics.update(transcript_diagnostics)

        return {
            "outputs": outputs,
            "artifacts": artifacts,
            "metadata": metadata,
            "diagnostics": diagnostics,
        }
