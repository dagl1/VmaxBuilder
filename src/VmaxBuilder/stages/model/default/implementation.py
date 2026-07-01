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
from VmaxBuilder.typing_stubs.model.default.implementation import DefaultConfig


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


class DefaultIrreversibleModelImplementation(BaseImplementation[DefaultConfig]):
    BASE_STAGE_CONFIG = ModelCoreConfig
    IMPLEMENTATION_CONFIG_CLASS = ModelConfig
    _RESOLVED_CONFIG_CLASS = DefaultConfig
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
            name="transcript_df",
            data_type=DataFrame,
            optional=True,
            prefix="transcript_df",
            extensions=(
                ".json",
                ".csv",
                ".tsv",
            ),
        ),
    ]
    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = ModelDiagnostics()

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        self._translation_service: TranscriptMetadataServiceProtocol = (
            IdentifierTranslationService()
        )

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        cobra_model = cast(Model, scaffold.get_scaffold_value("cobra_model"))
        irreversible_model, rev2irrev = create_irreversible_model(cobra_model)

        outputs = {
            "irreversible_model": irreversible_model,
        }
        artifacts_payload = {
            "rev2irrev": rev2irrev,
        }
        metadata = {
            "model_stage": {
                "model": {
                    "implementation": type(self).__name__,
                    "status": "irreversible_model_created",
                    "reaction_count": len(
                        irreversible_model.reactions
                    ),  # todo: add to diagnostics
                    "metabolite_count": len(irreversible_model.metabolites),
                }
            }
        }

        if self.full_config.run.run_target_transcript_gene_level.lower() == "transcript":
            transcript_artifacts = _build_transcript_artifacts_for_model(
                model=irreversible_model,
                config=self.full_config,
                translation_service=self._translation_service,
            )
            artifacts_payload.update(transcript_artifacts)
        metadata["model_stage"]["model"] = {
            "reaction_notation": self.full_config.model.reaction_notation.value,
            "make_copy": self.full_config.model.make_copy,
        }
        return {
            "outputs": outputs,
            "artifacts": artifacts_payload,
            "metadata": metadata,
        }
