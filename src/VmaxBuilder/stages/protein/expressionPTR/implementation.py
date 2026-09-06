from __future__ import annotations

from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation, RealImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.expression.implementation import (
    DefaultExpressionImplementation,
)
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.stages.protein.ptr.imputation_implementation import (
    SimplePTRImputationImplementation,
)
from VmaxBuilder.stages.protein.ptr.multiplication_implementation import (
    SimplePTRMultiplicationImplementation,
)
from VmaxBuilder.typing_stubs.protein.expressionPTR.implementation import (
    ExpressionPTRConfigProtocol,
)


class ExpressionPTRImplementation(BaseImplementation[ExpressionPTRConfigProtocol]):
    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "expression_ptr"
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [
        DefaultExpressionImplementation,
        SimplePTRImputationImplementation,
        SimplePTRMultiplicationImplementation,
    ]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "Expression_PTR": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Expression and PTR processed",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
