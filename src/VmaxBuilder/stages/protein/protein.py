from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.stages.protein.diagnostics import ProteinStageDiagnostics


class ProteinStage:
    DIAGNOSTICS = [ProteinStageDiagnostics()]

    def __init__(self, implementation: type[BaseImplementation], config):
        self.config = config
        self.implementation = implementation()
