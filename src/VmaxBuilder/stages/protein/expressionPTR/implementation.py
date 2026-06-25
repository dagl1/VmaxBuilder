from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold
from VmaxBuilder.base.registry import register_implementation
from VmaxBuilder.stages.protein.expression.implementation import (
    DefaultExpressionImplementation,
)
from VmaxBuilder.stages.protein.ptr.implementation import SimplePTRImputationImplementation


@register_implementation("protein", "expression_ptr")
class ExpressionPTRImplementation(BaseImplementation):
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_ptr"
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [
        DefaultExpressionImplementation,
        SimplePTRImputationImplementation,
    ]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self):
        self.child_implementations = [impl() for impl in self.CHILD_IMPLEMENTATIONS]

    def run(self, scaffold: Scaffold) -> Scaffold:
        for impl in self.child_implementations:
            scaffold = impl.run(scaffold)
        return scaffold

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, any]:
        # This implementation does not generate new outputs directly,
        # it relies on child implementations
        return {}
