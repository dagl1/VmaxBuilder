from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, OutputSpec, Scaffold
from VmaxBuilder.stages.allocation.FairAllocation.implementation import (
    FairAllocationImplementation,
)


class AllocationStage(BaseStage):
    DIAGNOSTICS = []
    OUTPUTS = []
    ADDITIONAL_IMPLEMENTATIONS = [FairAllocationImplementation]
    STAGE_NAME = "model"

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)
