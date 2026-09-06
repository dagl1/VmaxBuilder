from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, OutputSpec, Scaffold


class KcatStage(BaseStage):
    DIAGNOSTICS = []
    OUTPUTS = []
    ADDITIONAL_IMPLEMENTATIONS = []
    STAGE_NAME = "Kcat"

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)
