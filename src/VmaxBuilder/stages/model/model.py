from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, OutputSpec, Scaffold
from VmaxBuilder.GPR.gpr_implementation import DefaultGPRImplementation
from VmaxBuilder.Kcat_preprocessing.smiles_getters_implementation import (
    TranscriptSMILESGetter,
)


@dataclass(slots=True)
class ModelCoreConfig:
    """Generated: validation needed.

    Description:
        Core configuration for model loading and reaction notation convention.

    Args:
        maximum_transcript_ifp_expansion (int): Maximum number of transcript-level
            IFPs to generate per gene-level IFP.

    """

    maximum_transcript_ifp_expansion: int = 1500


class ModelStage(BaseStage):
    DIAGNOSTICS = []
    OUTPUTS = []
    CORE_CONFIG_CLASS = ModelCoreConfig
    ADDITIONAL_IMPLEMENTATIONS = [DefaultGPRImplementation, TranscriptSMILESGetter]
    STAGE_NAME = "model"

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold: Scaffold):
        gpr_implementation = self.additional_implementations["DefaultGPRImplementation"]
        transcript_smiles_getter = self.additional_implementations["TranscriptSMILESGetter"]
        scaffold = gpr_implementation.run(scaffold)
        scaffold = transcript_smiles_getter.run(scaffold)

        return scaffold
