from VmaxBuilder.base.classes import BaseImplementation


class ModelStage:
    DIAGNOSTICS = []

    def __init__(self, implementation: type[BaseImplementation], config):
        self.config = config
        self.implementation = implementation()

    def run(self, scaffold):
        # Run diagnostics before the stage execution
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.before_run(scaffold)

        # Run the implementation
        scaffold = self.implementation.run(scaffold)

        # Run diagnostics after the stage execution
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.after_run(scaffold)

        return scaffold
