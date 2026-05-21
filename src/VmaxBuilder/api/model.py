"""Generated: validation needed.

Description:
    API-level model stage orchestrator.
"""

from __future__ import annotations

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.core.protocols import Scaffold, StageProtocol
from VmaxBuilder.model.implementation import DefaultModelStageImplementation

# ruff: noqa: I001


class ModelStageOrchestrator(StageProtocol):
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
        implementation: DefaultModelStageImplementation | None = None,
    ) -> None:
        self._implementation = implementation or DefaultModelStageImplementation()

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
