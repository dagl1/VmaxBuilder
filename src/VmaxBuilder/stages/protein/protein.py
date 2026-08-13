from dataclasses import dataclass

from VmaxBuilder.base.classes import BaseImplementation, BaseStage
from VmaxBuilder.base.configs import FullConfig, Scaffold
from VmaxBuilder.stages.protein.remove_missing_genes import MissingGeneRemoval


@dataclass(slots=True)
class ProteinStageConfig:
    pass


class ProteinStage(BaseStage):
    STAGE_NAME = "protein"
    DIAGNOSTICS = []
    OUTPUTS = []
    CORE_CONFIG_CLASS = ProteinStageConfig
    ADDITIONAL_IMPLEMENTATIONS = [MissingGeneRemoval]

    def __init__(self, implementation: BaseImplementation, full_config: FullConfig):
        super().__init__(implementation, full_config)

    def run_additional_processes(self, scaffold: Scaffold):
        missing_gene_removal_implementation = self.additional_implementations[
            "MissingGeneRemoval"
        ]
        scaffold = missing_gene_removal_implementation.run(scaffold)

        return scaffold
