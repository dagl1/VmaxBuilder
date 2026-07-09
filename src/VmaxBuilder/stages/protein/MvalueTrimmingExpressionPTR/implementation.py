from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.expressionPTR.implementation import (
    ExpressionPTRImplementation,
)
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.stages.protein.ptr.implementation import SimplePTRImputationImplementation
from VmaxBuilder.typing_stubs.protein.MvalueTrimmingExpressionPTR.implementation import (
    MvalueTrimmingExpressionPTRConfigProtocol,
)


class MvalueTrimmingExpressionPTRImplementation(
    BaseImplementation[MvalueTrimmingExpressionPTRConfigProtocol]
):
    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_ptr"
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [ExpressionPTRImplementation]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)

    def generate_outputs(self, scaffold):
        return {}
