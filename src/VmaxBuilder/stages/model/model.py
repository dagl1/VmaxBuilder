from VmaxBuilder.base.classes import BaseImplementation


class ModelStage:
    def __init__(self, implementation: type[BaseImplementation], config):
        self.config = config
        self.implementation = implementation()
