from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, OutputSpec, Scaffold


class VmaxStage(BaseStage):
    DIAGNOSTICS = []
    OUTPUTS = []
    ADDITIONAL_IMPLEMENTATIONS = []
    STAGE_NAME = "Vmax"

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)
