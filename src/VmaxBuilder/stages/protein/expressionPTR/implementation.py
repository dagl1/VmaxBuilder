from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.expression.implementation import (
    DefaultExpressionImplementation,
)
from VmaxBuilder.stages.protein.ptr.implementation import SimplePTRImputationImplementation


class ExpressionPTRImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_ptr"
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [
        DefaultExpressionImplementation,
        SimplePTRImputationImplementation,
    ]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def run(self, scaffold: Scaffold) -> Scaffold:
        for impl in self.child_implementations:
            scaffold = impl.run(scaffold)
        return scaffold

    def generate_outputs(self, scaffold):
        # This
        return {}
