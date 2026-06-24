from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig


class ModelStage(BaseStage):
    DIAGNOSTICS = []
    NECESSARY_OUTPUTS = []

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold):
        return scaffold
