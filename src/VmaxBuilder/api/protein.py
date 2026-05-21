"""Generated: validation needed.

Description:
    API-level protein stage orchestrator.

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
from VmaxBuilder.protein.implementation import DefaultProteinStageImplementation

# ruff: noqa: I001


class ProteinStageOrchestrator(StageProtocol):
    """Generated: validation needed.

    Description:
        Orchestrate protein stage by delegating execution to protein implementation module.

    Args:
        implementation (DefaultProteinStageImplementation | None):
            Optional protein implementation override.

    Returns:
        None.

    Raises:
        None.

    Requires:
        name (StageName): Stage identifier.

    Modifies:
        None.
    """

    name: StageName = StageName.PROTEIN

    def __init__(
        self,
        implementation: DefaultProteinStageImplementation | None = None,
    ) -> None:
        self._implementation = implementation or DefaultProteinStageImplementation()

    def run(self, scaffold: Scaffold, config: APIConfig) -> Scaffold:
        """Generated: validation needed.

        Description:
            Run protein stage using configured implementation.

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
