from __future__ import annotations

from typing import Any

import pandas as pd

from VmaxBuilder.base.classes import BaseImplementation, RealImplementation
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.stages.Kcat.main_substrate.main_substrate_implementation import (
    MainSubstrateImplementation,
)
from VmaxBuilder.stages.Kcat.UniKP.implementation import UniKPImplementation
from VmaxBuilder.typing_stubs.Kcat.UniKPMainSubstrate.implementation import (
    UniKPMainSubstrateImplementationConfigProtocol,
)


class UniKPMainSubstrateImplementation(
    BaseImplementation[UniKPMainSubstrateImplementationConfigProtocol]
):
    STAGE_NAME = "Kcat"
    IMPL_NAME = "UniKPMainSubstrateImplementation"
    CHILD_IMPLEMENTATIONS: list[type[BaseImplementation]] = [
        UniKPImplementation,
        MainSubstrateImplementation,
    ]

    OUTPUTS: list[OutputSpec] = []
    DIAGNOSTICS = []

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "UniKPMainSubstrateImplementation": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "Expression and PTR processed",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata
