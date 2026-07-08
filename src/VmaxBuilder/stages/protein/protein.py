from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig
from VmaxBuilder.stages.protein.diagnostics import ProteinStageDiagnostics


class ProteinStage(BaseStage):
    DIAGNOSTICS = []
    OUTPUTS = []
    CORE_CONFIG_CLASS = None

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold):
        return scaffold
