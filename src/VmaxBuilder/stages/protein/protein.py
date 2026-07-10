from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig
from VmaxBuilder.stages.protein.diagnostics import ProteinStageDiagnostics


@dataclass(slots=True)
class ProteinStageConfig:
    pass


class ProteinStage(BaseStage):
    STAGE_NAME = "protein"
    DIAGNOSTICS = []
    OUTPUTS = []
    CORE_CONFIG_CLASS = ProteinStageConfig
    ADDITIONAL_IMPLEMENTATIONS = []

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold):
        return scaffold
