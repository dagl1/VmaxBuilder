from __future__ import annotations

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.core.protocols import Scaffold, StageProtocol
from VmaxBuilder.GPR.gpr_implementation import DefaultGPRImplementation


class GPRStageOrchestrator(StageProtocol):
    """Generated: validation needed.

    Description:
        Orchestrate model stage by delegating execution to model implementation module.

    Args:
        implementation (DefaultModelStageImplementation | None):
            Optional model implementation override.
    """

    name: StageName = StageName.MODEL

    def __init__(
        self,
        implementation: DefaultGPRImplementation | None = None,
    ) -> None:
        self._implementation = implementation or DefaultGPRImplementation()

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Run model stage using configured implementation.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API config.

        Returns:
            Scaffold: Updated scaffold.

        Modifies:
            scaffold payload.
        """

        return self._implementation.run(scaffold, config)
