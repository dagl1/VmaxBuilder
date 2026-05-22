"""Generated: validation needed.

Description:
    API-level allocation stage orchestrator.

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

from VmaxBuilder.allocation.implementation import DefaultAllocationStageImplementation
from VmaxBuilder.config.dataclasses import APIConfig
from VmaxBuilder.config.enums import StageName
from VmaxBuilder.core.protocols import Scaffold, StageProtocol

# ruff:


class AllocationStageOrchestrator(StageProtocol):
    """Generated: validation needed.

    Description:
        Orchestrate allocation stage by delegating to allocation implementation module.

    Args:
        implementation (DefaultAllocationStageImplementation | None):
            Optional allocation implementation override.

    Returns:
        None.

    Raises:
        None.

    Requires:
        name (StageName): Stage identifier.

    Modifies:
        None.
    """

    name: StageName = StageName.ALLOCATION

    def __init__(
        self,
        implementation: DefaultAllocationStageImplementation | None = None,
    ) -> None:
        self._implementation = implementation or DefaultAllocationStageImplementation()

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Run allocation stage using configured implementation.

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
