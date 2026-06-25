from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, OutputSpec
from VmaxBuilder.GPR.gpr_implementation import DefaultGPRImplementation


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
    NECESSARY_OUTPUTS = []
    CORE_CONFIG_CLASS = ModelCoreConfig

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold):
        gpr_implementation = DefaultGPRImplementation()
        scaffold = gpr_implementation.run(scaffold, self.config)

        return scaffold
