"""Generated: validation needed.

Description:
    API-level vmax stage orchestrator.

Args:
    None.

Returns:
    None.

Raises:
    None.

Requires:
    None.

Modifies:
    None.
"""

from __future__ import annotations

from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.core.protocols import Scaffold, StageProtocol
from VmaxBuilder.Vmax.implementation import DefaultVmaxStageImplementation

# ruff: noqa: I001


class VmaxStageOrchestrator(StageProtocol):
    """Generated: validation needed.

    Description:
        Orchestrate vmax stage by delegating to vmax implementation module.

    Args:
        implementation (DefaultVmaxStageImplementation | None):
            Optional vmax implementation override.

    Returns:
        None.

    Raises:
        None.

    Requires:
        name (StageName): Stage identifier.

    Modifies:
        None.
    """

    name: StageName = StageName.VMAX

    def __init__(
        self,
        implementation: DefaultVmaxStageImplementation | None = None,
    ) -> None:
        self._implementation = implementation or DefaultVmaxStageImplementation()

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Run vmax stage using configured implementation.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.
            config (APIConfig): Root API config.

        Returns:
            Scaffold: Updated scaffold.

        Raises:
            None.

        Requires:
            None.

        Modifies:
            scaffold payload.
        """

        return self._implementation.run(scaffold, config)
