from VmaxBuilder.base.classes import BaseImplementation


class ModelStage:
    DIAGNOSTICS = []

    def __init__(self, implementation: BaseImplementation, config):
        self.config = config
        self.implementation = implementation

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

    def validate_outputs(self, scaffold):
        # Validate the outputs of the stage
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.validate_outputs(scaffold)

    def run_diagnostics(self, scaffold):
        # Run diagnostics after the stage execution
        for diagnostic in self.DIAGNOSTICS:
            diagnostic.after_run(scaffold)
