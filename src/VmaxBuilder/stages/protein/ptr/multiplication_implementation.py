from __future__ import annotations

from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation
from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.protein.protein import ProteinStageConfig
from VmaxBuilder.stages.protein.ptr.config import PTRInputConfig
from VmaxBuilder.typing_stubs.protein.expressionPTR.implementation import (
    ExpressionPTRConfigProtocol,
)


class SimplePTRMultiplicationImplementation(BaseImplementation[PTRInputConfig]):
    BASE_STAGE_CONFIG = ProteinStageConfig
    STAGE_NAME = "protein"
    IMPL_NAME = "simple_ptr_imputation"

    IMPLEMENTATION_CONFIG_CLASS = PTRInputConfig
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = []

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: Any):
        super().__init__(full_config)

    def generate_outputs(self, scaffold):
        # Multiply expression values by PTR values
        _expression_df = scaffold.get("processed_expression_df")

    def create_metadata(self, elapsed_time: float) -> dict[str, Any]:
        metadata = {
            "PTR_Multiplication": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Expression values multiplied by PTR values",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
