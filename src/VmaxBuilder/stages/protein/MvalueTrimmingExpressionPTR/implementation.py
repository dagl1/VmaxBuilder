from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation, RealImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.expressionPTR.implementation import (
    ExpressionPTRImplementation,
)
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.trimming.Mvalue.trimming_implementation import (
    MValueTrimmingImplementation,
)
from VmaxBuilder.typing_stubs.protein.MvalueTrimmingExpressionPTR.implementation import (
    MvalueTrimmingExpressionPTRConfigProtocol,
)


class MvalueTrimmingExpressionPTRImplementation(
    RealImplementation[MvalueTrimmingExpressionPTRConfigProtocol]
):
    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "M-value_trimming_expression_PTR"
    _RESOLVED_CONFIG_CLASS = MvalueTrimmingExpressionPTRConfigProtocol

    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [
        ExpressionPTRImplementation,
        MValueTrimmingImplementation,
    ]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)

    def generate_outputs(self, scaffold):
        return {}

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "Trimming_assessment": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Trimmable genes assessed",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
